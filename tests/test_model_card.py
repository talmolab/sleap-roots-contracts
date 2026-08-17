"""Tests for the ModelCard model-selection contract."""

import json
import warnings
from typing import get_args

import numpy as np
import pytest
from pydantic import ValidationError

from sleap_roots_contracts.models import Mode, ModelCard, ModelRef, Selector
from sleap_roots_contracts.schema import MODELS, render


def make_selector(**overrides):
    """Build a valid Selector with sensible defaults, overridable per-test."""
    base = dict(species="rice", mode="cylinder", age_min=2, age_max=5)
    base.update(overrides)
    return Selector(**base)


def make_card(**overrides):
    """Build a valid ModelCard with sensible defaults, overridable per-test."""
    base = dict(
        root_type="primary",
        selectors=(make_selector(),),
        registry_id="reg-primary",
        version="v1",
        weights_checksum="wc-primary",
        sleap_nn_version="0.1.0",
    )
    base.update(overrides)
    return ModelCard(**base)


def card_mapping(selector=None, **overrides):
    """Build a raw card mapping — the production `model_validate` entry point.

    Every *negative* selector case must go through here rather than through a
    `Selector` object. A Selector carrying an invalid value cannot be constructed
    at all, so an object-based fixture would raise from Selector with an empty
    `loc` and stop exercising the card — exactly the hole
    test_model_card_guards_apply_via_model_validate exists to close.
    """
    sel = dict(species="rice", mode="cylinder", age_min=2, age_max=5)
    sel.update(selector or {})
    base = dict(
        root_type="primary",
        selectors=[sel],
        registry_id="reg-primary",
        version="v1",
        weights_checksum="wc-primary",
        sleap_nn_version="0.1.0",
    )
    base.update(overrides)
    return base


def validate_card(selector=None, **overrides):
    """Validate a raw card mapping with one (possibly invalid) selector."""
    return ModelCard.model_validate(card_mapping(selector, **overrides))


def test_model_card_valid():
    """A ModelCard constructs and retains its selection + identity fields."""
    c = make_card()
    assert c.root_type == "primary"
    assert c.selectors == (make_selector(),)
    assert c.registry_id == "reg-primary"
    assert c.version == "v1"
    assert c.weights_checksum == "wc-primary"
    assert c.sleap_nn_version == "0.1.0"


def test_model_card_carries_several_selectors_for_one_physical_model():
    """One card describes one physical model across every context it serves.

    This is the whole point of the reshape: the generalist primary-root model in
    the live registry was registered once per species because `species` was a
    scalar. Here canola 2-13 and pennycress 2-14 sit on one card pointing at one
    set of weights, in order.
    """
    canola = make_selector(species="canola", age_min=2, age_max=13)
    pennycress = make_selector(species="pennycress", age_min=2, age_max=14)
    c = make_card(selectors=(canola, pennycress))
    assert c.selectors == (canola, pennycress)
    assert {s.species for s in c.selectors} == {"canola", "pennycress"}


def test_model_card_accepts_overlapping_and_duplicate_selectors():
    """Two selectors matching one context are accepted, not a validity problem.

    Matching is a **disjunction** over selectors, not a lookup of one
    distinguished selector, so two matching selectors still make the card match
    exactly once — the age of 7 below satisfies both windows and the card is still
    one card. Rejecting them would fail something semantically fine and turn a
    cosmetic producer bug into a hard read-path failure on the consumer, which is
    the wrong side to fail on; de-duplication is the producer's job.

    Covers both shapes: byte-identical duplicates (which the producer's set-based
    dedup is meant to remove) and distinct-but-overlapping windows (which it does
    not, since dedup only removes exact repeats). The second is the one with no
    other coverage anywhere.

    Asserted through both entry points, since the production reader uses
    model_validate on a JSON-native blob rather than kwargs.
    """
    identical = make_selector(species="canola", age_min=2, age_max=13)
    c = make_card(selectors=(identical, identical))
    assert len(c.selectors) == 2
    assert c.selectors[0] == c.selectors[1]

    wide = make_selector(species="canola", age_min=5, age_max=20)
    c = make_card(selectors=(identical, wide))
    assert len(c.selectors) == 2
    matching = [
        s
        for s in c.selectors
        if s.species == "canola"
        and s.mode == "cylinder"
        and s.age_min <= 7 <= s.age_max
    ]
    assert len(matching) == 2  # both match; the card still matches once

    sel = dict(species="canola", mode="cylinder", age_min=2, age_max=13)
    c = ModelCard.model_validate(card_mapping(selectors=[sel, dict(sel)]))
    assert len(c.selectors) == 2


@pytest.mark.parametrize("empty", [(), []])
def test_model_card_rejects_empty_selectors(empty):
    """A card with no selection context is unselectable, so it is a producer bug.

    Asserted as *exactly one* error at `selectors`: the alternative implementation
    (`Field(min_length=1)`) reports this same case correctly but also fires on a
    card whose only selector is merely invalid, which is the neighbouring test.
    """
    with pytest.raises(ValidationError) as exc:
        make_card(selectors=empty)
    assert [e["loc"] for e in exc.value.errors()] == [("selectors",)]


def test_model_card_bad_only_selector_is_not_also_reported_as_empty():
    """A one-bad-selector card reports the selector, not an empty list.

    The regression test for `Field(min_length=1)`, which was measured and rejected
    for exactly this: pydantic validates items first, drops the invalid ones, then
    applies the length constraint to what survives — so the card would report both
    "this selector is invalid" and "the list is empty". That misdescribes the input
    and makes the genuinely-empty case indistinguishable from a merely-bad one,
    which is the distinction a producer debugging a failed seed needs.

    Asserts the exact error list rather than membership, since the defect this
    guards against is an *extra* error.
    """
    with pytest.raises(ValidationError) as exc:
        validate_card({"age_min": 6, "age_max": 3})
    assert [e["loc"] for e in exc.value.errors()] == [("selectors", 0)]


def test_model_card_rejects_reversed_age_range():
    """age_min greater than age_max is rejected, and the error names both bounds.

    Mirrors test_label_card_rejects_inverted_age_window: a bare `raises` here would
    also pass on any *other* validation failure, so the message is asserted to pin
    that it is the window check that fired.

    The offending *values* are asserted alongside the field names: field names
    alone are satisfied by a message that names the fields without reporting the
    numbers, and the numbers are what makes a bad card diagnosable from a log line
    without re-running validation.

    The error now locates the offending selector by index rather than naming a
    card-level field, because the window rule lives on Selector. That is visible to
    anyone logging per-artifact validation errors, so it is pinned rather than
    left to be discovered.
    """
    with pytest.raises(ValidationError) as exc:
        validate_card({"age_min": 6, "age_max": 3})
    assert [e["loc"] for e in exc.value.errors()] == [("selectors", 0)]
    msg = str(exc.value)
    assert "age_min" in msg and "age_max" in msg
    assert "6" in msg and "3" in msg


def test_model_card_reports_the_offending_selector_by_index():
    """With several selectors, the error points at the one that failed.

    A card can carry many contexts; "some selector is bad" would be a poor
    diagnostic for the generalist model this reshape exists to support.
    """
    good = dict(species="rice", mode="cylinder", age_min=2, age_max=5)
    bad = dict(species="canola", mode="cylinder", age_min=9, age_max=2)
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(card_mapping(selectors=[good, bad]))
    assert [e["loc"] for e in exc.value.errors()] == [("selectors", 1)]


def test_model_card_allows_equal_age_bounds():
    """A single-age window (age_min == age_max) is valid — the window is inclusive."""
    c = make_card(selectors=(make_selector(age_min=7, age_max=7),))
    assert c.selectors[0].age_min == c.selectors[0].age_max == 7


def test_model_card_allows_zero_age():
    """Zero is a valid inclusive lower bound (ge=0)."""
    c = make_card(selectors=(make_selector(age_min=0, age_max=0),))
    assert c.selectors[0].age_min == 0 and c.selectors[0].age_max == 0


@pytest.mark.parametrize("field", ["age_min", "age_max"])
def test_model_card_rejects_negative_age(field):
    """A negative age bound is rejected (ge=0)."""
    with pytest.raises(ValidationError):
        validate_card({field: -1})


@pytest.mark.parametrize("field", ["age_min", "age_max"])
@pytest.mark.parametrize("value", [True, False])
def test_model_card_rejects_bool_age(field, value):
    """A bool age bound is rejected, not coerced to 1/0.

    Python's bool subclasses int, so pydantic's lax mode would read True/False as
    1/0 and yield a card claiming a plausible-but-wrong approved window. The card
    and its selectors both set extra="ignore" so they can validate straight from a
    raw wandb metadata blob, and in this registry that blob is boolean-key soup
    ({"v007": true}) — field validation is the only defense left.

    The companion bound is pinned to 0 so a coerced value cannot trip the
    age_min <= age_max check instead: without it, age_max=True coerces to 1 against
    the fixture's age_min=2 and the test would pass on the *range* error while the
    bool sailed through. The message assertion closes the same hole from the other
    side — only the bool guard names the bool.
    """
    with pytest.raises(ValidationError, match="bool"):
        validate_card({"age_min": 0, "age_max": 0, field: value})


@pytest.mark.parametrize("field", ["age_min", "age_max"])
@pytest.mark.parametrize("value", [np.bool_(True), np.bool_(False)])
def test_model_card_rejects_numpy_bool_age(field, value):
    """np.bool_ is rejected like a Python bool — it is not a bool subclass.

    The mirror of test_numpy_bool_age_is_rejected_like_a_python_bool in
    test_params.py: _coerce_age already refuses np.bool_ on the tolerant scan-param
    side, and the curated card must not be looser than it for the same quantity.
    An isinstance(v, bool) check alone does not catch this, so the card would
    otherwise read np.True_ as a selection window bound of 1.

    Reachable on the write side: training builds cards in-process at promotion,
    where a value stitched from a pandas row is a numpy scalar, not a Python bool.

    Parametrized over both values: the .item() unwrap path is the one numpy-specific
    branch in the guard, so proving it for np.True_ alone would leave the falsy half
    — the one that coerces to a plausible 0 — unpinned.
    """
    with pytest.raises(ValidationError, match="bool"):
        validate_card({"age_min": 0, "age_max": 0, field: value})


@pytest.mark.parametrize("field", ["age_min", "age_max"])
def test_model_card_rejects_bool_container_as_a_non_bool_error(field):
    """A *container* of bools is rejected as a non-integer, not described as a bool.

    The unwrap is duck-typed on `.item()` and gated on scalar-ness (`ndim == 0`), so
    a one-element array falls through to pydantic's accurate `int_type` error — the
    same error `np.array([1])` gets. Without the gate, `.item()` would unwrap the
    single element and the card would report "got a bool" for what is really an
    array, making the diagnostic asymmetric between bool and int containers.

    Still exactly one error: the non-empty check runs before item validation, so a
    bad selector does not also produce a spurious "list is empty".
    """
    with pytest.raises(ValidationError) as exc:
        validate_card({"age_min": 0, "age_max": 0, field: np.array([True])})
    assert [e["type"] for e in exc.value.errors()] == ["int_type"]


@pytest.mark.parametrize("field", ["age_min", "age_max"])
def test_model_card_hostile_item_still_raises_validation_error(field):
    """An object whose `.item()` raises is rejected, not propagated to the caller.

    The guard unwraps anything exposing `.item()`, so a value it was never designed
    for can reach that call. The contract promises a ValidationError from
    `model_validate` — a raw KeyError escaping would break every caller's except
    clause, on exactly the boolean-key-soup path `extra="ignore"` exists to survive.
    """

    class HostileScalar:
        """A duck-typed scalar whose unwrap raises something unanticipated."""

        def item(self):
            raise KeyError("not really a scalar")

    with pytest.raises(ValidationError):
        validate_card({"age_min": 0, "age_max": 0, field: HostileScalar()})


@pytest.mark.parametrize("field", ["age_min", "age_max"])
@pytest.mark.parametrize("bad", [7.5, "7.5"])
def test_model_card_rejects_non_integral_age(field, bad):
    """A fractional age bound is rejected, never silently truncated to 7.

    Mirrors test_params.py's test_fractional_decimal_age_is_not_silently_truncated on
    the card side: lax parsing accepts 7.0 (the next test pins that), and the failure
    mode worth guarding is the neighbouring one — 7.5 quietly becoming a 7-day bound
    that shifts which scans a model claims.
    """
    with pytest.raises(ValidationError):
        validate_card({"age_min": 0, "age_max": 0, field: bad})


@pytest.mark.parametrize("raw,expected", [("7", 7), (7.0, 7), (np.int64(7), 7)])
def test_model_card_age_lax_parsing_preserved(raw, expected):
    """Ordinary lax int parsing still works — the bool guard rejects only bool.

    Regression guard that keeps the NonBoolInt fix narrow: a BeforeValidator that
    rejected anything broader than bool would break these inputs.
    """
    c = validate_card({"age_min": raw, "age_max": raw})
    assert c.selectors[0].age_min == expected
    assert c.selectors[0].age_max == expected


def test_model_card_rejects_bad_root_type():
    """A root_type outside {primary, lateral, crown} is rejected."""
    with pytest.raises(ValidationError):
        make_card(root_type="seedling")


@pytest.mark.parametrize("rt", ["primary", "lateral", "crown"])
def test_model_card_accepts_all_root_types(rt):
    """Every RootType vocabulary member constructs and carries through to_model_ref.

    Guards the vocabulary against silent narrowing (positive coverage; the negative
    case is test_model_card_rejects_bad_root_type). root_type stays *scalar* and
    card-level under the reshape — it is intrinsic to the weights, so a physical
    model is never both primary and lateral.
    """
    c = make_card(root_type=rt)
    assert c.root_type == rt
    assert c.to_model_ref("9.9.9").root_type == rt


def test_model_card_rejects_bad_mode():
    """A mode outside the Mode vocabulary is rejected, and the error names the field.

    `cyl` is the concrete value this guard exists to stop: it is the shorthand the
    existing label collection names use, and the reason the model and label
    registries cannot be joined today (sleap-roots-training#10).

    The `loc` reaches into the selector, since `mode` now lives there.
    """
    with pytest.raises(ValidationError) as exc:
        validate_card({"mode": "cyl"})
    assert [e["loc"] for e in exc.value.errors()] == [("selectors", 0, "mode")]


@pytest.mark.parametrize("bad", ["Cylinder", "cylinder ", " cylinder", "CYLINDER"])
def test_model_card_mode_is_not_normalized(bad):
    """The card matches the vocabulary exactly — it does not repair case or space.

    Pins the decision that normalization belongs to resolve_params (the tolerant
    scan-parameter side), not to the card. A card is written once by a script at
    promotion, so a loud failure is cheap and a silent repair is not. Adding a
    normalizing BeforeValidator to Selector.mode must fail this test.
    """
    with pytest.raises(ValidationError):
        validate_card({"mode": bad})


@pytest.mark.parametrize("mode", get_args(Mode))
def test_model_card_accepts_all_modes(mode):
    """Every Mode vocabulary member constructs and is retained unchanged.

    Guards the vocabulary against silent narrowing (positive coverage; the negative
    case is test_model_card_rejects_bad_mode). Parametrized over get_args(Mode) so a
    future vocabulary member is covered without editing this test.
    """
    c = validate_card({"mode": mode})
    assert c.selectors[0].mode == mode


def test_model_card_sleap_nn_version_optional():
    """The trained-with sleap_nn_version defaults to None when absent.

    It stays a *card-level scalar* under the reshape: it describes the physical
    weights, not a selection context, so it does not belong on Selector.
    """
    c = make_card(sleap_nn_version=None)
    assert c.sleap_nn_version is None
    assert "sleap_nn_version" not in Selector.model_fields


def test_model_card_is_frozen():
    """A ModelCard is immutable, and deeply so — its selectors are frozen too.

    Names a *surviving* field deliberately. A frozen pydantic model raises
    `frozen_instance` on assignment to **any** name, including one the reshape
    removed, so an immutability test still naming `species` would keep passing
    while asserting nothing at all.

    The nested case is the one that matters: `tuple` protects the sequence, not its
    elements, so without a frozen Selector `card.selectors[0].species = ...` would
    rewrite what a "frozen" production card claims to select.
    """
    c = make_card()
    with pytest.raises(ValidationError) as exc:
        c.registry_id = "reg-other"
    assert exc.value.errors()[0]["type"] == "frozen_instance"

    with pytest.raises(ValidationError):
        c.selectors[0].species = "canola"


def test_to_model_ref_stamps_runtime_version():
    """to_model_ref stamps the RUNTIME version and carries the card's identity."""
    c = make_card(sleap_nn_version="0.1.0")  # trained-with differs from runtime
    ref = c.to_model_ref("9.9.9")
    assert isinstance(ref, ModelRef)
    assert ref.sleap_nn_version == "9.9.9"  # runtime, NOT the card's "0.1.0"
    assert ref.registry_id == "reg-primary"
    assert ref.version == "v1"
    assert ref.root_type == "primary"
    assert ref.weights_checksum == "wc-primary"


def test_to_model_ref_when_card_version_none():
    """to_model_ref works when the card carries no trained-with version."""
    c = make_card(sleap_nn_version=None)
    ref = c.to_model_ref("9.9.9")
    assert ref.sleap_nn_version == "9.9.9"


def test_to_model_ref_is_pure_and_silent():
    """to_model_ref emits no warning even on a trained-vs-runtime mismatch.

    The mismatch warning is the reader's (predict's) responsibility; this method is
    pure. The card here has trained-with 0.1.0 while runtime is 9.9.9.
    """
    c = make_card(sleap_nn_version="0.1.0")
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning becomes an error
        c.to_model_ref("9.9.9")


def test_to_model_ref_carries_none_weights_checksum():
    """A card with no weights_checksum yields a ModelRef with None checksum."""
    c = make_card(weights_checksum=None)
    ref = c.to_model_ref("9.9.9")
    assert ref.weights_checksum is None
    assert ref.sleap_nn_version == "9.9.9"  # required field still satisfied


def test_model_card_from_merged_metadata():
    """A card validates from merged selection-metadata + artifact-identity dicts.

    Selection fields are written by training as wandb metadata; identity fields are
    intrinsic to the artifact and composed by predict's lister. A full card needs
    both sources merged.

    `selectors` arrives as a list of plain dicts, because wandb artifact metadata is
    a JSON blob and cannot carry Python objects. The result is asserted to be
    `Selector` *instances*, not the raw mappings.
    """
    selection_metadata = dict(
        root_type="primary",
        selectors=[
            dict(species="rice", mode="cylinder", age_min=2, age_max=5),
            dict(species="canola", mode="multiplant cylinder", age_min=2, age_max=13),
        ],
    )
    artifact_identity = dict(registry_id="reg-primary", version="v1")
    c = ModelCard.model_validate({**selection_metadata, **artifact_identity})
    assert c.registry_id == "reg-primary"
    assert all(isinstance(s, Selector) for s in c.selectors)
    assert c.selectors[1].age_max == 13


def test_model_card_tolerates_extra_keys():
    """Extra keys in the raw metadata blob are ignored (not extra='forbid').

    The real wandb metadata carries boolean tag flags, the spread training_config,
    and eval metrics; ModelCard must tolerate all of it.
    """
    blob = card_mapping(
        # noise that must be ignored
        soybean=True,
        oks_map=0.8,
        training_config={"epochs": 100, "lr": 1e-4},
    )
    c = ModelCard.model_validate(blob)
    assert c.selectors[0].species == "rice"
    assert not hasattr(c, "soybean")


@pytest.mark.parametrize(
    "bad_field,bad_value", [("mode", "cyl"), ("age_min", True), ("age_max", True)]
)
def test_model_card_guards_apply_via_model_validate(bad_field, bad_value):
    """Both guards fire on the model_validate path, not just kwargs construction.

    This is the production entry point: predict's registry lister builds every card
    with ModelCard.model_validate(raw_wandb_metadata), never with keyword arguments.
    A guard that only held for direct construction would leave exactly the path the
    guards exist to defend (a raw metadata blob) unprotected, so it is pinned here
    explicitly rather than assumed from pydantic's internals.
    """
    blob = card_mapping(
        {"age_min": 0, "age_max": 0, bad_field: bad_value},
        v007=True,  # the legacy boolean-key soup this blob really carries
    )
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(blob)
    assert [e["loc"] for e in exc.value.errors()] == [("selectors", 0, bad_field)]


def test_model_card_field_errors_aggregate():
    """Two bad fields surface as two errors in one pass (mirrors LabelCard).

    Matters for anyone diagnosing a batch of registry cards: a per-field report over
    a bad blob is complete for field-level errors, so it is fix-all-then-rerun rather
    than fix-one-rerun.

    A card-level error and a selector-level one aggregate, and so does a
    `Field(ge=0)` violation next to a bool rejection — those take different paths
    (pydantic's constraint machinery vs NonBoolInt's BeforeValidator), and only the
    mixed case proves a raised BeforeValidator does not abort the pass and swallow
    its neighbour. Mirrors the `n_frames=-1, n_plants=True` block in
    test_label_card.py's test_validation_error_aggregation_is_field_level_only.
    """
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(card_mapping({"mode": "cyl"}, root_type="bogus"))
    assert {e["loc"] for e in exc.value.errors()} == {
        ("selectors", 0, "mode"),
        ("root_type",),
    }

    with pytest.raises(ValidationError) as exc:
        validate_card({"age_min": -1, "age_max": True})
    mixed = exc.value.errors()
    assert {e["loc"] for e in mixed} == {
        ("selectors", 0, "age_min"),
        ("selectors", 0, "age_max"),
    }
    # ...and each is reported for its own reason, not one type for both.
    by_loc = {e["loc"]: e for e in mixed}
    assert by_loc[("selectors", 0, "age_min")]["type"] == "greater_than_equal"
    assert "bool" in by_loc[("selectors", 0, "age_max")]["msg"]


def test_selector_field_error_masks_its_own_range_check():
    """A bad selector field hides that selector's range error — validators are gated.

    The age_min <= age_max validator is mode="after", so it runs only once every
    field on that model has passed. Pinned (rather than left implicit) because it
    sets the expectation for a backfill: a card can need more than one round of
    fixes.

    The masking is now scoped to the *selector*, which is a real behavior change
    from the flat card: a bad card-level field no longer suppresses a selector's
    window error, so the two surface together (asserted below). Only a bad field
    within the same selector still masks it.
    """
    # Same selector: the mode error gates its own window check.
    with pytest.raises(ValidationError) as exc:
        validate_card({"mode": "cyl", "age_min": 9, "age_max": 2})
    assert [e["loc"] for e in exc.value.errors()] == [("selectors", 0, "mode")]

    # Different levels: a card-level error no longer masks the selector's window.
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(
            card_mapping({"age_min": 9, "age_max": 2}, root_type="bogus")
        )
    assert {e["loc"] for e in exc.value.errors()} == {
        ("root_type",),
        ("selectors", 0),
    }


# --- No tolerant read of the legacy flat card -------------------------------
#
# The decision not to lift a legacy flat card into a single-selector card was
# reversed onto evidence about the *consumer* and is load-bearing: predict skips a
# card it cannot validate (per artifact, with a warning), and choose_models raises
# when more than one card matches a context. A tolerant read would make both the
# old flat cards and the new selector cards valid at once during the migration
# window, manufacturing exactly that ambiguous match on live traffic.
#
# These tests are what make that decision expensive to reverse by accident.


def test_legacy_flat_card_fails_validation():
    """The pre-selectors shape is rejected, reporting the missing `selectors`."""
    flat = dict(
        species="rice",
        mode="cylinder",
        age_min=2,
        age_max=5,
        root_type="primary",
        registry_id="reg-primary",
        version="v1",
    )
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(flat)
    errors = exc.value.errors()
    assert [e["loc"] for e in errors] == [("selectors",)]
    assert errors[0]["type"] == "missing"


def test_legacy_flat_keys_are_ignored_not_lifted():
    """Flat keys are dropped as extras, never merged into or preferred over selectors.

    The disagreeing values are the point: if a tolerant read were ever added, the
    card would reflect the flat `species`/age window instead of the selector's, and
    this test would catch it.
    """
    blob = card_mapping(
        species="canola",  # disagrees with the selector's "rice"
        mode="plate",  # disagrees with "cylinder"
        age_min=99,
        age_max=100,
    )
    c = ModelCard.model_validate(blob)
    assert c.selectors == (
        Selector(species="rice", mode="cylinder", age_min=2, age_max=5),
    )
    for removed in ("species", "mode", "age_min", "age_max"):
        assert not hasattr(c, removed)


def test_flat_selection_fields_are_absent_from_the_model():
    """No code can read a card-level species/mode/age bound, and none can set one."""
    assert set(ModelCard.model_fields) == {
        "root_type",
        "selectors",
        "registry_id",
        "version",
        "weights_checksum",
        "sleap_nn_version",
    }


# --- wandb metadata coercion ------------------------------------------------
#
# wandb.Artifact(metadata=...) runs the mapping through validate_metadata, which
# *coerces* rather than rejects anything non-JSON-native. A producer that passes
# the Selector models it already has gets back a list of repr strings; a NamedTuple
# comes back as a positional list with the field names gone. Both would publish
# unreadable selection metadata with a successful exit code, so the read path has
# to make them loud. This is the one failure mode that survives a green producer
# test run.


def test_repr_coerced_selector_list_does_not_validate():
    """A list of repr strings is rejected, not parsed back into selectors."""
    blob = card_mapping(selectors=[repr(make_selector()), str(make_selector())])
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(blob)
    assert all(e["type"] == "model_type" for e in exc.value.errors())


def test_positionally_coerced_selector_list_does_not_validate():
    """A positional list is rejected rather than mapped onto fields by position.

    The NamedTuple coercion shape. Mapping by position would silently accept a
    reordering as a different, wrong selection context.
    """
    blob = card_mapping(selectors=[["rice", "cylinder", 2, 5]])
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(blob)
    assert [e["loc"] for e in exc.value.errors()] == [("selectors", 0)]


def test_model_card_importable_from_package_root():
    """ModelCard is exported from the package root for producers to import."""
    import sleap_roots_contracts

    assert sleap_roots_contracts.ModelCard is ModelCard


def test_model_card_absent_from_result_schema():
    """Neither card model leaks into any emitted Bloom-facing schema.

    They are Python-side producer<->producer contracts, not referenced by
    ResultEnvelope or AnalysisInputRow, so they must not appear among any emitted
    schema's $defs.

    Iterates every emitted schema rather than only result_envelope, so a future
    reference from the analysis-input side is caught too, and asserts the whole
    $defs set rather than a bare `"ModelCard" not in defs` — the latter passes
    vacuously if either class is ever renamed.
    """
    for name in MODELS:
        rendered = json.loads(render(name))
        defs = set(rendered.get("$defs", {}))
        assert {"ModelCard", "Selector"} & defs == set(), (name, sorted(defs))


# --- Selector ---------------------------------------------------------------
#
# The bundled selection context: one whole validated (species, mode, age window)
# a model was approved for. The card-level consequences of these rules live with
# the ModelCard tests above; what is pinned here is that the rules belong to
# Selector *itself* and hold when it is built standalone.


def test_selector_valid():
    """A Selector constructs and retains its four fields."""
    s = make_selector()
    assert s.species == "rice"
    assert s.mode == "cylinder"
    assert (s.age_min, s.age_max) == (2, 5)


@pytest.mark.parametrize(
    "bounds",
    [
        {"age_min": 6, "age_max": 3},  # inverted window
        {"age_min": -1},  # negative bound
        {"age_min": True},  # builtin bool
        {"age_max": np.bool_(True)},  # numpy bool (not a bool subclass)
    ],
)
def test_selector_enforces_its_own_age_bounds(bounds):
    """The age rules live on Selector, not on whatever contains it.

    Built standalone, with no ModelCard in sight. If these only fired through the
    card, a producer assembling selectors before wrapping them would get no
    feedback until the whole card was built — and `NonBoolInt`'s numpy.bool_ half
    (strengthened in tighten-model-card-validation) would be trivially re-openable
    by anyone hand-writing a bound check here.
    """
    with pytest.raises(ValidationError):
        make_selector(**bounds)


@pytest.mark.parametrize(
    "bad", ["cyl", "Cylinder", "cylinder ", " cylinder", "CYLINDER"]
)
def test_selector_enforces_its_own_mode_vocabulary(bad):
    """Selector.mode is matched exactly — no case or whitespace repair.

    `cyl` is the concrete value this exists to stop (the label registry's
    shorthand). The cased and space-padded spellings pin that normalization stays
    resolve_params' job, not the selector's.
    """
    with pytest.raises(ValidationError):
        make_selector(mode=bad)


@pytest.mark.parametrize("mode", get_args(Mode))
def test_selector_accepts_all_modes(mode):
    """Every Mode vocabulary member constructs and is retained unchanged."""
    assert make_selector(mode=mode).mode == mode


def test_selector_accepts_an_unmodelled_species():
    """species carries no vocabulary — an unmodelled one is not a validation error.

    The registry's cards are the authority on which species have models, and
    resolve_params deliberately lets an unknown species pass through to a
    selection zero-match rather than rejecting it (param-resolution's "An unknown
    species passes through lowercased"). A vocabulary here would turn that
    designed skip into a hard failure.
    """
    assert make_selector(species="sorghum").species == "sorghum"


def test_selector_is_frozen():
    """A Selector is immutable, which is what makes a ModelCard deeply immutable.

    The card's `tuple[Selector, ...]` protects the sequence but not its elements,
    so a mutable Selector would let `card.selectors[0].species = ...` rewrite what
    a "frozen" production card claims to select.
    """
    s = make_selector()
    with pytest.raises(ValidationError):
        s.species = "canola"


def test_selector_is_hashable_and_set_deduplicates():
    """Frozen makes Selector hashable, which is what the producer's dedup needs.

    sleap-roots-training collapses several matrix rows onto one physical model and
    de-duplicates identical contexts with a set. Equal-valued selectors must
    therefore collapse to one element, including across lax-parsed inputs, since
    the matrix can supply an age as a string.
    """
    assert len({make_selector(), make_selector()}) == 1
    assert len({make_selector(), make_selector(age_min="2")}) == 1
    assert len({make_selector(), make_selector(age_max=14)}) == 2


def test_selector_tolerates_an_unknown_nested_key():
    """extra="ignore", so a newer producer's added field does not break an old reader.

    Selectors arrive as nested mappings inside a raw wandb metadata blob. A
    consumer pinned to an older contract must drop an unknown selector key rather
    than fail the whole card and silently remove the model from selection.

    The accepted cost, flagged on contracts#32: a *typo'd* key is dropped just as
    quietly, surfacing only as a missing-field error at that selector's index. The
    producer side guards the extras direction itself
    (sleap-roots-training#47 task 3.23b).
    """
    s = Selector.model_validate(
        dict(species="rice", mode="cylinder", age_min=2, age_max=5, provenance="v7")
    )
    assert s.species == "rice"
    assert not hasattr(s, "provenance")


def test_selector_importable_from_package_root():
    """Selector is exported from the package root, and listed in __all__."""
    import sleap_roots_contracts

    assert sleap_roots_contracts.Selector is Selector
    assert "Selector" in sleap_roots_contracts.__all__
