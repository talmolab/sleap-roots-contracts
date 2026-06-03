"""Tests for deterministic idempotency-key derivation."""

import pytest

from sleap_roots_contracts.identity import compute_idempotency_key

BASE = dict(
    scan_key="scan-1",
    images_checksum="img-abc",
    models=[("reg-primary", "v1", "wc1"), ("reg-lateral", "v2", None)],
    param_hash="ph-1",
    predict_code_sha="p-sha",
    traits_code_sha="t-sha",
)


def test_idempotency_is_deterministic():
    """The same inputs yield the same key."""
    assert compute_idempotency_key(**BASE) == compute_idempotency_key(**BASE)


def test_idempotency_model_order_independent():
    """Reordering the model list does not change the key."""
    reordered = {**BASE, "models": list(reversed(BASE["models"]))}
    assert compute_idempotency_key(**reordered) == compute_idempotency_key(**BASE)


def test_idempotency_handles_none_weights_checksum():
    """A None weights_checksum must not raise when sorting models."""
    compute_idempotency_key(**BASE)


@pytest.mark.parametrize(
    "field,newval",
    [
        ("scan_key", "scan-2"),
        ("images_checksum", "img-xyz"),
        ("param_hash", "ph-2"),
        ("predict_code_sha", "p-sha2"),
        ("traits_code_sha", "t-sha2"),
        ("models", [("reg-primary", "v9", "wc1")]),
    ],
)
def test_idempotency_sensitive_to_each_component(field, newval):
    """Changing any component changes the key."""
    changed = {**BASE, field: newval}
    assert compute_idempotency_key(**changed) != compute_idempotency_key(**BASE)
