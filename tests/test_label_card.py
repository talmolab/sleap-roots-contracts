"""Tests for the label-selection contract (Mode vocabulary + LabelCard)."""

import json
from typing import get_args

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.schema import render

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


@pytest.mark.parametrize(
    "field",
    [
        "source_experiment",
        "bloom_experiment_id",
        "accessions",
        "labeler",
        "box_link",
        "source_sha256",
        "sleap_io_version",
    ],
)
def test_label_card_optional_provenance_defaults_to_none(field):
    """Every best-effort provenance field is optional and defaults to None.

    The resolved design (Elizabeth, Slack 2026-07-21) relaxed the Bloom-trace
    provenance fields to optional so #11's as-is backfill isn't gated on metadata it
    cannot recover for the eight legacy collections.
    """
    c = make_label_card()
    assert getattr(c, field) is None


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


def test_label_card_rejects_zero_node_count():
    """node_count = 0 is rejected (a skeleton has at least one node)."""
    with pytest.raises(ValidationError):
        make_label_card(node_count=0, node_names=())


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
