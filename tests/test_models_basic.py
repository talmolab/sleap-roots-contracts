"""Tests for the basic contract models: ModelRef, InputRef, ResolvedParams."""

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.models import InputRef, ModelRef, ResolvedParams


def test_modelref_minimal():
    """A ModelRef needs only registry_id, version, and sleap_nn_version."""
    m = ModelRef(registry_id="r", version="v1", sleap_nn_version="0.1")
    assert m.root_type is None and m.weights_checksum is None


def test_modelref_full():
    """A ModelRef accepts the optional root_type and weights_checksum."""
    m = ModelRef(
        registry_id="r",
        version="v1",
        sleap_nn_version="0.1",
        root_type="primary",
        weights_checksum="abc",
    )
    assert m.root_type == "primary"


def test_inputref_requires_images_checksum():
    """InputRef requires an images_checksum."""
    with pytest.raises(ValidationError):
        InputRef(image_ids=["i1"])  # missing images_checksum


def test_resolvedparams_computes_hash_when_absent():
    """ResolvedParams auto-fills param_hash."""
    p = ResolvedParams(values={"species": "rice"})
    assert len(p.param_hash) == 64


def test_resolvedparams_hash_matches_values():
    """The auto-filled hash matches compute_param_hash of the values."""
    from sleap_roots_contracts.hashing import compute_param_hash

    vals = {"species": "rice", "scale": 2}
    assert ResolvedParams(values=vals).param_hash == compute_param_hash(vals)


def test_resolvedparams_accepts_matching_explicit_hash():
    """A correct explicit param_hash (e.g. on round-trip) is accepted."""
    from sleap_roots_contracts.hashing import compute_param_hash

    vals = {"species": "rice"}
    h = compute_param_hash(vals)
    assert ResolvedParams(values=vals, param_hash=h).param_hash == h


def test_resolvedparams_rejects_mismatched_explicit_hash():
    """A wrong explicit param_hash raises rather than being silently overwritten."""
    with pytest.raises(ValidationError):
        ResolvedParams(values={"species": "rice"}, param_hash="deadbeef")


def test_resolvedparams_is_frozen():
    """A derived field cannot be tampered with after construction."""
    p = ResolvedParams(values={"species": "rice"})
    with pytest.raises(ValidationError):
        p.param_hash = "deadbeef"
