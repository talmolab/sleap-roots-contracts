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
        species="rice",
        mode="cylinder",
        age_min=2,
        age_max=5,
        root_type="primary",
        registry_id="reg-primary",
        version="v1",
        weights_checksum="wc-primary",
        sleap_nn_version="0.1.0",
    )
    base.update(overrides)
    return ModelCard(**base)


def test_model_card_valid():
    """A ModelCard constructs and retains its selection + identity fields."""
    c = make_card()
    assert c.species == "rice"
    assert c.mode == "cylinder"
    assert (c.age_min, c.age_max) == (2, 5)
    assert c.root_type == "primary"
    assert c.registry_id == "reg-primary"
    assert c.version == "v1"
    assert c.weights_checksum == "wc-primary"
    assert c.sleap_nn_version == "0.1.0"


def test_model_card_rejects_reversed_age_range():
    """age_min greater than age_max is rejected, and the error names both bounds.

    Mirrors test_label_card_rejects_inverted_age_window: a bare `raises` here would
    also pass on any *other* validation failure, so the message is asserted to pin
    that it is the window check that fired.

    The offending *values* are asserted alongside the field names, which the sibling
    does and this test did not: field names alone are satisfied by a message that
    names the fields without reporting the numbers, and the numbers are what makes a
    bad card diagnosable from a log line without re-running validation.
    """
    with pytest.raises(ValidationError) as exc:
        make_card(age_min=6, age_max=3)
    msg = str(exc.value)
    assert "age_min" in msg and "age_max" in msg
    assert "6" in msg and "3" in msg


def test_model_card_allows_equal_age_bounds():
    """A single-age window (age_min == age_max) is valid — the window is inclusive."""
    c = make_card(age_min=7, age_max=7)
    assert c.age_min == c.age_max == 7


def test_model_card_allows_zero_age():
    """Zero is a valid inclusive lower bound (ge=0)."""
    c = make_card(age_min=0, age_max=0)
    assert c.age_min == 0 and c.age_max == 0


@pytest.mark.parametrize("field", ["age_min", "age_max"])
def test_model_card_rejects_negative_age(field):
    """A negative age bound is rejected (ge=0)."""
    with pytest.raises(ValidationError):
        make_card(**{field: -1})


@pytest.mark.parametrize("field", ["age_min", "age_max"])
@pytest.mark.parametrize("value", [True, False])
def test_model_card_rejects_bool_age(field, value):
    """A bool age bound is rejected, not coerced to 1/0.

    Python's bool subclasses int, so pydantic's lax mode would read True/False as
    1/0 and yield a card claiming a plausible-but-wrong approved window. ModelCard
    sets extra="ignore" so it can validate straight from a raw wandb metadata blob,
    and in this registry that blob is boolean-key soup ({"v007": true}) — field
    validation is the only defense left.

    The companion bound is pinned to 0 so a coerced value cannot trip the
    age_min <= age_max check instead: without it, age_max=True coerces to 1 against
    the fixture's age_min=2 and the test would pass on the *range* error while the
    bool sailed through. The message assertion closes the same hole from the other
    side — only the bool guard names the bool.
    """
    bounds = {"age_min": 0, "age_max": 0, field: value}
    with pytest.raises(ValidationError, match="bool"):
        make_card(**bounds)


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
    bounds = {"age_min": 0, "age_max": 0, field: value}
    with pytest.raises(ValidationError, match="bool"):
        make_card(**bounds)


@pytest.mark.parametrize("field", ["age_min", "age_max"])
def test_model_card_rejects_bool_container_as_a_non_bool_error(field):
    """A *container* of bools is rejected as a non-integer, not described as a bool.

    The unwrap is duck-typed on `.item()` and gated on scalar-ness (`ndim == 0`), so
    a one-element array falls through to pydantic's accurate `int_type` error — the
    same error `np.array([1])` gets. Without the gate, `.item()` would unwrap the
    single element and the card would report "got a bool" for what is really an
    array, making the diagnostic asymmetric between bool and int containers.
    """
    bounds = {"age_min": 0, "age_max": 0, field: np.array([True])}
    with pytest.raises(ValidationError) as exc:
        make_card(**bounds)
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

    bounds = {"age_min": 0, "age_max": 0, field: HostileScalar()}
    with pytest.raises(ValidationError):
        make_card(**bounds)


@pytest.mark.parametrize("field", ["age_min", "age_max"])
@pytest.mark.parametrize("bad", [7.5, "7.5"])
def test_model_card_rejects_non_integral_age(field, bad):
    """A fractional age bound is rejected, never silently truncated to 7.

    Mirrors test_params.py's test_fractional_decimal_age_is_not_silently_truncated on
    the card side: lax parsing accepts 7.0 (task 2.2 pins that), and the failure mode
    worth guarding is the neighbouring one — 7.5 quietly becoming a 7-day bound that
    shifts which scans a model claims.
    """
    with pytest.raises(ValidationError):
        make_card(**{"age_min": 0, "age_max": 0, field: bad})


@pytest.mark.parametrize("raw,expected", [("7", 7), (7.0, 7), (np.int64(7), 7)])
def test_model_card_age_lax_parsing_preserved(raw, expected):
    """Ordinary lax int parsing still works — the bool guard rejects only bool.

    Regression guard that keeps the NonBoolInt fix narrow: a BeforeValidator that
    rejected anything broader than bool would break these inputs.
    """
    c = make_card(age_min=raw, age_max=raw)
    assert c.age_min == expected and c.age_max == expected


def test_model_card_rejects_bad_root_type():
    """A root_type outside {primary, lateral, crown} is rejected."""
    with pytest.raises(ValidationError):
        make_card(root_type="seedling")


@pytest.mark.parametrize("rt", ["primary", "lateral", "crown"])
def test_model_card_accepts_all_root_types(rt):
    """Every RootType vocabulary member constructs and carries through to_model_ref.

    Guards the vocabulary against silent narrowing (positive coverage; the negative
    case is test_model_card_rejects_bad_root_type).
    """
    c = make_card(root_type=rt)
    assert c.root_type == rt
    assert c.to_model_ref("9.9.9").root_type == rt


def test_model_card_rejects_bad_mode():
    """A mode outside the Mode vocabulary is rejected, and the error names the field.

    `cyl` is the concrete value this guard exists to stop: it is the shorthand the
    existing label collection names use, and the reason the model and label
    registries cannot be joined today (sleap-roots-training#10).
    """
    with pytest.raises(ValidationError) as exc:
        make_card(mode="cyl")
    assert [e["loc"] for e in exc.value.errors()] == [("mode",)]


@pytest.mark.parametrize("bad", ["Cylinder", "cylinder ", " cylinder", "CYLINDER"])
def test_model_card_mode_is_not_normalized(bad):
    """The card matches the vocabulary exactly — it does not repair case or space.

    Pins the decision that normalization belongs to resolve_params (the tolerant
    scan-parameter side), not to the card. A card is written once by a script at
    promotion, so a loud failure is cheap and a silent repair is not. Adding a
    normalizing BeforeValidator to ModelCard.mode must fail this test.
    """
    with pytest.raises(ValidationError):
        make_card(mode=bad)


@pytest.mark.parametrize("mode", get_args(Mode))
def test_model_card_accepts_all_modes(mode):
    """Every Mode vocabulary member constructs and is retained unchanged.

    Guards the vocabulary against silent narrowing (positive coverage; the negative
    case is test_model_card_rejects_bad_mode). Parametrized over get_args(Mode) so a
    future vocabulary member is covered without editing this test.
    """
    c = make_card(mode=mode)
    assert c.mode == mode


def test_model_card_sleap_nn_version_optional():
    """The trained-with sleap_nn_version defaults to None when absent."""
    c = make_card(sleap_nn_version=None)
    assert c.sleap_nn_version is None


def test_model_card_is_frozen():
    """A ModelCard is immutable; reassigning a field raises."""
    c = make_card()
    with pytest.raises(ValidationError):
        c.species = "canola"


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

    Selection fields are written by training as flat wandb metadata; identity
    fields are intrinsic to the artifact and composed by predict's lister. A full
    card needs both sources merged.
    """
    selection_metadata = dict(
        species="rice", mode="cylinder", age_min=2, age_max=5, root_type="primary"
    )
    artifact_identity = dict(registry_id="reg-primary", version="v1")
    c = ModelCard.model_validate({**selection_metadata, **artifact_identity})
    assert c.registry_id == "reg-primary"
    assert c.age_max == 5


def test_model_card_tolerates_extra_keys():
    """Extra keys in the raw metadata blob are ignored (not extra='forbid').

    The real wandb metadata carries boolean tag flags, the spread training_config,
    and eval metrics; ModelCard must tolerate all of it.
    """
    blob = dict(
        species="rice",
        mode="cylinder",
        age_min=2,
        age_max=5,
        root_type="primary",
        registry_id="reg-primary",
        version="v1",
        # noise that must be ignored
        soybean=True,
        oks_map=0.8,
        training_config={"epochs": 100, "lr": 1e-4},
    )
    c = ModelCard.model_validate(blob)
    assert c.species == "rice"
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
    blob = dict(
        species="rice",
        mode="cylinder",
        age_min=0,
        age_max=0,
        root_type="primary",
        registry_id="reg-primary",
        version="v1",
        v007=True,  # the legacy boolean-key soup this blob really carries
    )
    blob[bad_field] = bad_value
    with pytest.raises(ValidationError) as exc:
        ModelCard.model_validate(blob)
    assert [e["loc"] for e in exc.value.errors()] == [(bad_field,)]


def test_model_card_field_errors_aggregate():
    """Two bad fields surface as two errors in one pass (mirrors LabelCard).

    Matters for anyone diagnosing a batch of registry cards: a per-field report over
    a bad blob is complete for field-level errors, so it is fix-all-then-rerun rather
    than fix-one-rerun.

    Two vocabulary errors aggregate, and so does a `Field(ge=0)` violation next to a
    bool rejection — those take different paths (pydantic's constraint machinery vs
    NonBoolInt's BeforeValidator), and only the mixed case proves a raised
    BeforeValidator does not abort the pass and swallow its neighbour. Mirrors the
    `n_frames=-1, n_plants=True` block in test_label_card.py's
    test_validation_error_aggregation_is_field_level_only, which ModelCard lacked.
    """
    with pytest.raises(ValidationError) as exc:
        make_card(mode="cyl", root_type="bogus")
    assert {e["loc"] for e in exc.value.errors()} == {("mode",), ("root_type",)}

    with pytest.raises(ValidationError) as exc:
        make_card(age_min=-1, age_max=True)
    mixed = exc.value.errors()
    assert {e["loc"] for e in mixed} == {("age_min",), ("age_max",)}
    # ...and each is reported for its own reason, not one type for both.
    by_loc = {e["loc"]: e for e in mixed}
    assert by_loc[("age_min",)]["type"] == "greater_than_equal"
    assert "bool" in by_loc[("age_max",)]["msg"]


def test_model_card_field_error_masks_the_range_check():
    """A bad field hides the cross-field range error — the validators are gated.

    The age_min <= age_max validator is mode="after", so it runs only once every
    field has passed. Pinned (rather than left implicit) because it sets the
    expectation for a backfill: a card can need more than one round of fixes.
    """
    with pytest.raises(ValidationError) as exc:
        make_card(mode="cyl", age_min=9, age_max=2)
    assert [e["loc"] for e in exc.value.errors()] == [("mode",)]


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
