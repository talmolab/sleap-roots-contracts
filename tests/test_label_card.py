"""Tests for the label-selection contract (Mode vocabulary + LabelCard)."""

import json
from typing import get_args

import numpy as np
import pytest
from pydantic import ValidationError

from sleap_roots_contracts.schema import render

# The best-effort provenance fields — all optional, all seven populated by the publish
# path. Stated once so the "all seven" invariant can't drift between tests.
PROVENANCE_FIELDS = (
    "source_experiment",
    "bloom_experiment_id",
    "accessions",
    "labeler",
    "box_link",
    "source_sha256",
    "sleap_io_version",
)

# Every integer-typed field. A bool must not be coerced into any of them.
INT_FIELDS = (
    "age_min",
    "age_max",
    "node_count",
    "n_frames",
    "n_instances",
    "n_plants",
    "n_scans",
)

# sha256 of b"" — a valid-shaped digest; the value is never recomputed here.
_SOURCE_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

# Every field a valid LabelCard requires (no provenance fields — those are optional).
REQUIRED_FIELDS = (
    "species",
    "mode",
    "root_type",
    "age_min",
    "age_max",
    "skeleton_name",
    "node_count",
    "node_names",
    "n_frames",
    "n_instances",
    "n_plants",
    "n_scans",
    "images_embedded",
    "registry_id",
    "version",
)


def valid_label_card_kwargs():
    """A fresh dict of valid LabelCard kwargs.

    Defaults keep ``node_count == len(node_names)`` and ``age_min <= age_max`` so the
    bare mapping is valid. Returned fresh each call so callers can mutate it.
    """
    return dict(
        # selection
        species="rice",
        mode="cylinder",
        root_type="primary",
        age_min=2,
        age_max=5,
        # skeleton
        skeleton_name="rice_primary_v2",
        node_count=2,
        node_names=("r1", "r2"),
        # content
        n_frames=40,
        n_instances=40,
        n_plants=10,
        n_scans=10,
        images_embedded=True,
        # registry identity
        registry_id="reg-labels-primary",
        version="v1",
    )


def make_label_card(**overrides):
    """Build a valid LabelCard with sensible defaults, overridable per-test."""
    base = valid_label_card_kwargs()
    base.update(overrides)
    from sleap_roots_contracts import LabelCard

    return LabelCard(**base)


def test_mode_importable_from_package_root():
    """Mode is exported from the package root for producers/consumers to import."""
    import sleap_roots_contracts

    assert hasattr(sleap_roots_contracts, "Mode")


def test_mode_vocabulary_is_exactly_the_three_capture_modes():
    """Mode's members are the canonical capture modes, in order, and nothing else.

    Guards the vocabulary against silent widening/narrowing. The `cyl` absence is the
    specific defect issue #10 exists to fix (`cylinder` vs `cyl` split the two
    registries); it is asserted explicitly as a negative case.
    """
    from sleap_roots_contracts import Mode

    assert get_args(Mode) == ("cylinder", "multiplant cylinder", "plate")
    assert "cyl" not in get_args(Mode)


def test_label_card_importable_from_package_root():
    """LabelCard is exported from the package root for producers to import."""
    import sleap_roots_contracts

    assert hasattr(sleap_roots_contracts, "LabelCard")


def test_label_card_valid_construction():
    """A LabelCard builds from complete metadata and carries its fields through."""
    c = make_label_card()
    assert c.species == "rice"
    assert c.mode == "cylinder"
    assert c.root_type == "primary"
    assert c.node_names == ("r1", "r2")
    assert c.n_frames == 40
    assert c.images_embedded is True
    assert c.registry_id == "reg-labels-primary"


def test_label_card_is_frozen():
    """A LabelCard is immutable; reassigning a field raises."""
    c = make_label_card()
    with pytest.raises(ValidationError):
        c.species = "canola"


def _provenance_kwargs():
    """All seven provenance fields, each with a distinct, recognizable value.

    Values are deliberately all different so a crossed assignment (two fields wired to
    each other) fails as loudly as a dropped one.
    """
    return dict(
        source_experiment="2026-05-12_rice_cyl_batch3",
        bloom_experiment_id="exp_01HQ8Z3KQW",
        accessions=("PI562993", "PI603911"),
        labeler="eberrigan",
        box_link="https://app.box.com/folder/123456789",
        source_sha256=_SOURCE_SHA256,
        sleap_io_version="0.2.0",
    )


@pytest.mark.parametrize("field", PROVENANCE_FIELDS)
def test_label_card_optional_provenance_defaults_to_none(field):
    """Every best-effort provenance field is optional and defaults to None.

    The resolved design (Elizabeth, Slack 2026-07-21) relaxed the Bloom-trace
    provenance fields to optional so #11's as-is backfill isn't gated on metadata it
    cannot recover for the eight legacy collections.
    """
    c = make_label_card()
    assert getattr(c, field) is None


def test_provenance_kwargs_covers_every_provenance_field():
    """The populated fixture covers all seven provenance fields, and only those.

    Without this, a newly added provenance field could be left out of
    ``_provenance_kwargs`` and the round-trip guards below would silently stop
    covering it.
    """
    from sleap_roots_contracts import LabelCard

    assert set(_provenance_kwargs()) == set(PROVENANCE_FIELDS)
    optional = {
        name for name, f in LabelCard.model_fields.items() if not f.is_required()
    }
    assert optional == set(PROVENANCE_FIELDS)


def test_label_card_carries_every_populated_provenance_field():
    """Every provenance field passed in lands on the card under that same name.

    The guard the rest of the suite lacked: every other test leaves these seven as
    None, so a renamed or typo'd field would be dropped by ``extra="ignore"``, still
    read ``None``, and pass. Populating all seven from a raw wandb-shaped blob ties the
    writer's key names to the contract's attribute names.
    """
    from sleap_roots_contracts import LabelCard

    provenance = _provenance_kwargs()
    blob = {
        **_label_metadata(),
        "registry_id": "reg-labels-soy",
        "version": "v7",
        **provenance,
    }
    c = LabelCard.model_validate(blob)
    for field, expected in provenance.items():
        assert getattr(c, field) == expected, f"{field} did not survive validation"


def test_label_card_provenance_survives_json_round_trip():
    """A fully populated card serializes and re-validates without losing provenance.

    Covers the wire hop the registry lister makes (card -> JSON -> card): every
    provenance key must appear in the dumped payload, and ``accessions`` must come back
    as a tuple, not the list JSON turns it into.
    """
    from sleap_roots_contracts import LabelCard

    c = make_label_card(**_provenance_kwargs())
    dumped = c.model_dump_json()
    payload = json.loads(dumped)
    for field in PROVENANCE_FIELDS:
        assert field in payload, f"{field} missing from serialized payload"

    back = LabelCard.model_validate_json(dumped)
    assert back == c
    assert back.accessions == ("PI562993", "PI603911")
    assert back.source_sha256 == _SOURCE_SHA256


def test_label_card_typo_in_provenance_key_is_dropped_silently():
    """A misspelled provenance key is ignored, not rejected — the hazard guarded above.

    ``extra="ignore"`` is required for #11's backfill (it tolerates the legacy
    boolean-key soup), but it means the contract cannot tell a typo from a legacy tag.
    This pins that failure mode as known and deliberate: the defense is the populated
    round-trip test, not validation.
    """
    from sleap_roots_contracts import LabelCard

    blob = {
        **_label_metadata(),
        "registry_id": "reg-labels-soy",
        "version": "v7",
        "box_lnk": "https://app.box.com/folder/123456789",  # typo: box_link
    }
    c = LabelCard.model_validate(blob)
    assert c.box_link is None
    assert not hasattr(c, "box_lnk")


def test_label_card_has_no_data_path_field():
    """The broken ``data_path`` field does not exist on LabelCard.

    It is replaced by ``source_sha256``; #10 found ``data_path`` unusable in all eight
    collections (Windows temp dirs / an unmountable ``Z:`` drive).
    """
    from sleap_roots_contracts import LabelCard

    assert "data_path" not in LabelCard.model_fields


# --- Task 3: model validators -------------------------------------------------


def test_label_card_rejects_inverted_age_window():
    """age_min > age_max is rejected, and the error names both bounds."""
    with pytest.raises(ValidationError) as exc:
        make_label_card(age_min=6, age_max=5)
    msg = str(exc.value)
    assert "6" in msg and "5" in msg


@pytest.mark.parametrize("bound", ["age_min", "age_max"])
def test_label_card_rejects_negative_age_bound(bound):
    """Neither age bound may be negative (Field(ge=0))."""
    with pytest.raises(ValidationError):
        make_label_card(**{bound: -1})


@pytest.mark.parametrize("field", ["n_frames", "n_instances", "n_plants", "n_scans"])
def test_label_card_rejects_negative_content_count(field):
    """No content count may be negative (Field(ge=0))."""
    with pytest.raises(ValidationError):
        make_label_card(**{field: -1})


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_label_card_requires_every_non_provenance_field(field):
    """Every non-provenance field is required; omitting any one raises.

    Guards against a required field silently gaining a default (becoming optional).
    The provenance fields are deliberately excluded — they are optional by design
    (Elizabeth, Slack 2026-07-21).
    """
    from sleap_roots_contracts import LabelCard

    kwargs = valid_label_card_kwargs()
    del kwargs[field]
    with pytest.raises(ValidationError):
        LabelCard(**kwargs)


@pytest.mark.parametrize("age", [0, 3])
def test_label_card_accepts_inclusive_single_age_window(age):
    """A single-age window (age_min == age_max) is valid, including age 0."""
    c = make_label_card(age_min=age, age_max=age)
    assert c.age_min == age == c.age_max


def test_label_card_rejects_node_count_name_mismatch():
    """node_count must equal len(node_names); the error names both numbers."""
    with pytest.raises(ValidationError) as exc:
        make_label_card(node_count=3, node_names=("r1", "r2"))
    msg = str(exc.value)
    assert "3" in msg  # declared count
    assert "2" in msg  # actual number of names


def test_label_card_rejects_more_names_than_node_count():
    """The mismatch is rejected in both directions — more names than the declared count.

    The spec's own worked example (declared 4, five names given); the test above only
    covered the declared > actual direction, which a one-sided ``<`` comparison would
    also pass.
    """
    with pytest.raises(ValidationError) as exc:
        make_label_card(node_count=4, node_names=("r1", "r2", "r3", "r4", "r5"))
    msg = str(exc.value)
    assert "4" in msg  # declared count
    assert "5" in msg  # actual number of names


def test_label_card_rejects_zero_node_count():
    """node_count = 0 is rejected (a skeleton has at least one node)."""
    with pytest.raises(ValidationError):
        make_label_card(node_count=0, node_names=())


def _bool_probe_kwargs(field, value):
    """Kwargs putting ``value`` in ``field`` with every *other* validator satisfied.

    The trap these tests exist to avoid: on the ordinary fixture (``age_min=2``, two
    ``node_names``), a coerced bool trips a *different* validator, so the test passes
    on an unrelated error while the bool sails through the guard. Measured — with the
    ``raise`` in ``_reject_bool`` made unreachable, five of the nineteen bool cells
    still passed: ``age_max``/``node_count`` for both values, and ``node_count`` for
    ``np.False_``.

    So the window is widened to ``[0, 1]`` — a coerced ``0`` *or* ``1`` sits inside it
    either way — and the skeleton is shrunk to one node, so a ``node_count`` coerced to
    ``1`` matches rather than mismatching. Both make the card *valid* absent the guard,
    which is what turns these into real assertions.

    ``node_count=False`` is the one cell this cannot neutralize: ``ge=1`` rejects a
    coerced ``0`` no matter what else is set. The message assertion covers it from the
    other side — only the guard says "got a bool".
    """
    return {
        "age_min": 0,
        "age_max": 1,
        "node_count": 1,
        "node_names": ("r1",),
        field: value,
    }


# The guard's own wording (models._reject_bool). Asserted instead of a bare "bool":
# pydantic's error repr carries `input_type=bool` for any numpy-bool input, so
# `match="bool"` is satisfied by the *input* regardless of which validator raised.
_GUARD_MESSAGE = "got a bool"


@pytest.mark.parametrize("field", INT_FIELDS)
@pytest.mark.parametrize("value", [True, False])
def test_label_card_rejects_bool_for_int_field(field, value):
    """A bool is rejected wherever an integer is expected.

    Pydantic's lax mode otherwise coerces ``True``/``False`` to ``1``/``0``, so a card
    would validate and read a plausible-but-wrong number. This contract is unusually
    exposed: #11 backfills from legacy wandb metadata that stores provenance as
    boolean-key soup (keys whose value is ``True``), and ``extra="ignore"`` means field
    validation is the only thing standing between that blob and a valid-but-wrong card.

    See ``_bool_probe_kwargs`` for why the fixture is neutralized and the message
    asserted — without both, this test passed for four of the seven fields with the
    guard removed.
    """
    with pytest.raises(ValidationError, match=_GUARD_MESSAGE):
        make_label_card(**_bool_probe_kwargs(field, value))


@pytest.mark.parametrize("field", INT_FIELDS)
@pytest.mark.parametrize("value", [np.bool_(True), np.bool_(False)])
def test_label_card_rejects_numpy_bool_for_int_field(field, value):
    """np.bool_ is rejected too — it is not a ``bool`` subclass.

    An ``isinstance(v, bool)`` check alone misses it, so the guard would have been
    bypassed by any producer stitching values from a pandas row. ``node_count`` is the
    sharpest case: coerced to ``1`` it would *satisfy* the skeleton-coherence check
    against a single node name, yielding a card that validates while claiming a
    one-node skeleton. ``params._coerce_age`` documents the same trap for ages.

    Both values are exercised: the builtin-bool tests parametrize over ``[True,
    False]``, and the ``.item()`` unwrap this test covers deserves the same, so the
    falsy half — which coerces to a plausible ``0`` — is not left unpinned.
    """
    with pytest.raises(ValidationError, match=_GUARD_MESSAGE):
        make_label_card(**_bool_probe_kwargs(field, value))


@pytest.mark.parametrize("field", INT_FIELDS)
def test_label_card_rejects_bool_container_as_a_non_bool_error(field):
    """A *container* of bools is rejected as a non-integer, not described as a bool.

    The mirror of test_model_card.py's twin. The unwrap is duck-typed on ``.item()``
    and gated on scalar-ness (``ndim == 0``), so a one-element array falls through to
    pydantic's accurate ``int_type`` error — the same error ``np.array([1])`` gets.
    Without the gate, ``.item()`` would unwrap the single element and the card would
    report "got a bool" for what is really an array, making the diagnostic asymmetric
    between bool and int containers.
    """
    with pytest.raises(ValidationError) as exc:
        make_label_card(**_bool_probe_kwargs(field, np.array([True])))
    assert [e["type"] for e in exc.value.errors()] == ["int_type"]


@pytest.mark.parametrize("field", INT_FIELDS)
def test_label_card_hostile_item_still_raises_validation_error(field):
    """An object whose ``.item()`` raises is rejected, not propagated to the caller.

    The guard unwraps anything exposing ``.item()``, so a value it was never designed
    for can reach that call. The contract promises a ValidationError from
    ``model_validate`` — a raw KeyError escaping would break every caller's except
    clause, on exactly the boolean-key-soup path ``extra="ignore"`` exists to survive.
    """

    class HostileScalar:
        """A duck-typed scalar whose unwrap raises something unanticipated."""

        def item(self):
            raise KeyError("not really a scalar")

    with pytest.raises(ValidationError):
        make_label_card(**_bool_probe_kwargs(field, HostileScalar()))


def test_every_int_field_is_guarded_against_bools():
    """``INT_FIELDS`` is exactly the model's plain-int fields, and all are guarded.

    Both the spec's "every integer field" SHALL and ``INT_FIELDS`` above hardcode the
    same seven names, with nothing tying either to the model — so an eighth plain
    ``int`` field added with ``NonBoolInt`` forgotten would leave a green suite and a
    silently false requirement. Derived from ``model_fields`` so the SHALL enforces
    itself, following ``test_provenance_kwargs_covers_every_provenance_field``.

    ``images_embedded`` is annotated ``bool`` and correctly excluded: it is a genuine
    boolean, not an int field a bool could be smuggled into.
    """
    from pydantic import BeforeValidator

    from sleap_roots_contracts import LabelCard
    from sleap_roots_contracts.models import _reject_bool

    plain_ints = {
        name for name, f in LabelCard.model_fields.items() if f.annotation is int
    }
    guarded = {
        name
        for name, f in LabelCard.model_fields.items()
        if any(
            isinstance(m, BeforeValidator) and m.func is _reject_bool
            for m in f.metadata
        )
    }
    assert plain_ints == set(INT_FIELDS)
    assert guarded == set(INT_FIELDS)


def test_label_card_bool_node_count_does_not_satisfy_skeleton_check():
    """``node_count=True`` must not pass by coercing to 1 against a single node name.

    The sharpest form of the coercion bug: bool -> 1 would make the skeleton-coherence
    validator compare 1 == 1 and accept, producing a card claiming a one-node skeleton.
    """
    with pytest.raises(ValidationError):
        make_label_card(node_count=True, node_names=("r1",))


@pytest.mark.parametrize("value", [7, "7", 7.0])
def test_label_card_still_accepts_ordinary_int_input(value):
    """Rejecting bool leaves normal (lax) int parsing untouched.

    The str/float forms are pydantic's existing lax behavior; the bool guard is
    surgical and must not narrow them.
    """
    c = make_label_card(n_frames=value)
    assert c.n_frames == 7


def test_label_card_accepts_coherent_skeleton():
    """node_count == len(node_names) constructs cleanly."""
    c = make_label_card(node_count=3, node_names=("r1", "r2", "r3"))
    assert c.node_count == len(c.node_names) == 3


def test_label_card_rejects_cyl_mode():
    """mode='cyl' is rejected — the split issue #10 fixes; 'cylinder' succeeds."""
    with pytest.raises(ValidationError):
        make_label_card(mode="cyl")
    assert make_label_card(mode="cylinder").mode == "cylinder"


def test_label_card_rejects_root_type_outside_vocabulary():
    """A root_type outside the RootType vocabulary is rejected."""
    with pytest.raises(ValidationError):
        make_label_card(root_type="taproot")


def test_validation_error_aggregation_is_field_level_only():
    """One ValidationError is not a complete defect list — guidance for #11's backfill.

    Not a bug; it is how pydantic is specified to work. Pinned here because the change's
    design.md tells #11's backfill script to loop ``model_validate`` until clean rather
    than treat a single error as the full diagnostic, and that advice should fail loudly
    if the behavior ever changes.

    Three distinct behaviors, in order of how much they hide:
      1. field-level errors aggregate — two bad fields give two entries;
      2. any field-level error suppresses the ``mode="after"`` validators entirely, so a
         single typo'd field hides every cross-field defect;
      3. the two model validators are sequential in definition order, so an inverted age
         window short-circuits the skeleton-coherence check.
    """

    def errors_for(**overrides):
        with pytest.raises(ValidationError) as exc:
            make_label_card(**overrides)
        return exc.value.errors()

    # 1. Two independent field-level defects both surface.
    both = errors_for(mode="cyl", root_type="bogus")
    assert {e["loc"] for e in both} == {("mode",), ("root_type",)}

    # ...including a constraint violation alongside a bool rejection, which take
    # different paths (Field(ge=...) vs NonBoolInt's BeforeValidator).
    mixed = errors_for(n_frames=-1, n_plants=True)
    assert {e["loc"] for e in mixed} == {("n_frames",), ("n_plants",)}

    # 2. A bad field hides a cross-field defect: node_count=9 against two names is a
    # real skeleton mismatch, but only the mode error is reported.
    masked = errors_for(mode="cyl", node_count=9)
    assert {e["loc"] for e in masked} == {("mode",)}

    # 3. Model validators are sequential — the age check short-circuits the skeleton
    # check, so the skeleton mismatch stays invisible even with all fields well-typed.
    shadowed = errors_for(age_min=10, age_max=3, node_count=9)
    assert len(shadowed) == 1
    assert "age_min" in shadowed[0]["msg"]
    assert "node_count" not in shadowed[0]["msg"]


# --- Task 4: tolerant construction from raw wandb metadata --------------------


def _label_metadata():
    """The label-selection fields as a flat mapping, as build_slp_project writes them."""
    return dict(
        species="soybean",
        mode="cylinder",
        root_type="lateral",
        age_min=3,
        age_max=8,
        skeleton_name="soy_lateral_v7",
        node_count=4,
        node_names=("r1", "r2", "r3", "r4"),
        n_frames=120,
        n_instances=360,
        n_plants=30,
        n_scans=30,
        images_embedded=True,
    )


def test_label_card_model_validate_merges_metadata_and_identity():
    """A card builds from label metadata merged with artifact-intrinsic identity.

    Mirrors how the registry lister composes a card: the flat selection/content
    metadata written by the build script, merged with the wandb artifact's own
    ``registry_id``/``version`` (which are not metadata keys).
    """
    from sleap_roots_contracts import LabelCard

    blob = {**_label_metadata(), "registry_id": "reg-labels-soy", "version": "v7"}
    c = LabelCard.model_validate(blob)
    assert c.species == "soybean"
    assert c.root_type == "lateral"
    assert c.node_names == ("r1", "r2", "r3", "r4")
    assert c.registry_id == "reg-labels-soy"
    assert c.version == "v7"


def test_label_card_ignores_legacy_boolean_flags_and_stale_data_path():
    """Legacy boolean tag flags and the broken ``data_path`` are ignored, not fatal.

    The eight collections store provenance as boolean-key soup (keys with value
    ``True``) and carry an unusable ``data_path`` (a Windows temp dir). ``extra=ignore``
    must tolerate that blob so #11 can backfill without pre-scrubbing it.
    """
    from sleap_roots_contracts import LabelCard

    blob = {
        **_label_metadata(),
        "registry_id": "reg-labels-soy",
        "version": "v7",
        # legacy boolean-key soup
        "v007": True,
        "4nodes": True,
        "soybean": True,
        "lateral": True,
        # the broken pointer LabelCard replaces with source_sha256
        "data_path": "C:/Users/ELIZAB~1/AppData/Local/Temp/reembed_9f3a/proj.slp",
    }
    c = LabelCard.model_validate(blob)
    assert c.species == "soybean"
    # the stale field is dropped, not surfaced
    assert not hasattr(c, "data_path")
    assert not hasattr(c, "v007")


# --- Task 5: schema boundary --------------------------------------------------


def test_label_card_absent_from_result_schema():
    """LabelCard does not leak into the Bloom-facing result_envelope schema.

    Like ModelCard, it is a Python-side producer<->producer contract, not referenced
    by ResultEnvelope, so it must not appear among the emitted schema's $defs. If it
    ever surfaces here, the CI drift guard would ship a Bloom-facing schema change for
    a card Bloom never consumes.
    """
    defs = json.loads(render("result_envelope"))["$defs"]
    assert "LabelCard" not in defs
