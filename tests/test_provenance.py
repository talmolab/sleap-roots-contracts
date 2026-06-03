"""Tests for the Provenance model and its auto-derived idempotency_key."""

from sleap_roots_contracts.identity import compute_idempotency_key
from sleap_roots_contracts.models import InputRef, ModelRef, Provenance, ResolvedParams


def make_provenance(**overrides):
    """Build a Provenance with sensible defaults, overridable per-test."""
    base = dict(
        contract_version="0.1.0a0",
        scan_key="scan-1",
        inputs=InputRef(image_ids=["i1", "i2"], images_checksum="img-abc"),
        predict_models=[
            ModelRef(
                registry_id="r",
                version="v1",
                sleap_nn_version="0.1",
                root_type="primary",
            )
        ],
        predict_container_digest="sha256:pred",
        predict_code_sha="p-sha",
        traits_sleap_roots_version="1.0",
        traits_container_digest="sha256:tr",
        traits_code_sha="t-sha",
        params=ResolvedParams(values={"species": "rice"}),
    )
    base.update(overrides)
    return Provenance(**base)


def test_provenance_autofills_idempotency_key():
    """The idempotency_key matches a direct compute_idempotency_key call."""
    p = make_provenance()
    expected = compute_idempotency_key(
        scan_key="scan-1",
        images_checksum="img-abc",
        models=[("r", "v1", None)],
        param_hash=p.params.param_hash,
        predict_code_sha="p-sha",
        traits_code_sha="t-sha",
    )
    assert p.idempotency_key == expected


def test_same_inputs_same_key():
    """Identical inputs yield the same key."""
    assert make_provenance().idempotency_key == make_provenance().idempotency_key


def test_changed_model_changes_key():
    """A changed model version yields a new key."""
    other = make_provenance(
        predict_models=[
            ModelRef(
                registry_id="r",
                version="v2",
                sleap_nn_version="0.1",
                root_type="primary",
            )
        ]
    )
    assert other.idempotency_key != make_provenance().idempotency_key


def test_orchestration_fields_optional():
    """Orchestration and warm-worker handles default to None."""
    p = make_provenance()
    assert p.argo_workflow_uid is None and p.worker_request_id is None
