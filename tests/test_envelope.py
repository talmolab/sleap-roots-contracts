"""Tests for ResultEnvelope round-trip and public package exports."""

from sleap_roots_contracts import (
    BlobRef,
    InputRef,
    ModelRef,
    Provenance,
    ResolvedParams,
    ResultEnvelope,
    TraitValue,
)


def _provenance():
    return Provenance(
        contract_version="0.1.0a0",
        scan_key="scan-1",
        inputs=InputRef(image_ids=["i1"], images_checksum="img-abc"),
        predict_models=[
            ModelRef(registry_id="r", version="v1", sleap_nn_version="0.1")
        ],
        predict_container_digest="sha256:p",
        predict_code_sha="p",
        traits_sleap_roots_version="1.0",
        traits_container_digest="sha256:t",
        traits_code_sha="t",
        params=ResolvedParams(values={"species": "rice"}),
    )


def test_envelope_round_trips():
    """A ResultEnvelope survives JSON serialization and re-parsing."""
    env = ResultEnvelope(
        provenance=_provenance(),
        traits=[TraitValue(name="primary_length", value=1.0, scan_key="scan-1")],
        blobs=[
            BlobRef(kind="predictions_slp", scan_key="scan-1", s3_location="s3://b/k")
        ],
    )
    restored = ResultEnvelope.model_validate_json(env.model_dump_json())
    assert restored.provenance.idempotency_key == env.provenance.idempotency_key
    assert restored.traits[0].name == "primary_length"


def test_public_exports_importable():
    """All core symbols are importable from the package root."""
    assert ResultEnvelope and Provenance and TraitValue and BlobRef


def test_producer_hashing_helpers_exported():
    """compute_param_hash and its failure type are importable from the root."""
    import math

    import pytest

    from sleap_roots_contracts import NonCanonicalizableError, compute_param_hash

    assert compute_param_hash({"a": 1})  # callable from the root
    with pytest.raises(NonCanonicalizableError):
        compute_param_hash({"a": math.nan})


def test_all_lists_exported_symbols():
    """Every name in __all__ is actually present on the package."""
    import sleap_roots_contracts as src

    for name in src.__all__:
        assert hasattr(src, name), name
