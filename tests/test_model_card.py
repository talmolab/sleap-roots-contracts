"""Tests for the ModelCard model-selection contract."""

import json
import warnings
from typing import get_args

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.models import Mode, ModelCard, ModelRef
from sleap_roots_contracts.schema import render


def make_card(**overrides):
    """Build a valid ModelCard with sensible defaults, overridable per-test."""
    base = dict(
        species="rice",
        mode="proximal",
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
    assert c.mode == "proximal"
    assert (c.age_min, c.age_max) == (2, 5)
    assert c.root_type == "primary"
    assert c.registry_id == "reg-primary"
    assert c.version == "v1"
    assert c.weights_checksum == "wc-primary"
    assert c.sleap_nn_version == "0.1.0"


def test_model_card_rejects_reversed_age_range():
    """age_min greater than age_max is rejected (window well-formedness)."""
    with pytest.raises(ValidationError):
        make_card(age_min=6, age_max=3)


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


@pytest.mark.parametrize("raw,expected", [("7", 7), (7.0, 7)])
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
    """A mode outside the Mode vocabulary is rejected.

    `cyl` is the concrete value this guard exists to stop: it is the shorthand the
    existing label collection names use, and the reason the model and label
    registries cannot be joined today (sleap-roots-training#10).
    """
    with pytest.raises(ValidationError):
        make_card(mode="cyl")


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
        species="rice", mode="proximal", age_min=2, age_max=5, root_type="primary"
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
        mode="proximal",
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


def test_model_card_importable_from_package_root():
    """ModelCard is exported from the package root for producers to import."""
    import sleap_roots_contracts

    assert sleap_roots_contracts.ModelCard is ModelCard


def test_model_card_absent_from_result_schema():
    """ModelCard does not leak into the Bloom-facing result_envelope schema.

    It is a Python-side producer<->producer contract, not referenced by
    ResultEnvelope, so it must not appear among the emitted schema's $defs.
    """
    defs = json.loads(render("result_envelope"))["$defs"]
    assert "ModelCard" not in defs
