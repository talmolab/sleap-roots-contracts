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
    """A None weights_checksum must not raise and stays deterministic."""
    assert compute_idempotency_key(**BASE) == compute_idempotency_key(**BASE)


def test_idempotency_sensitive_to_weights_checksum():
    """Changing only a model's weights_checksum changes the key."""
    changed = {
        **BASE,
        "models": [("reg-primary", "v1", "DIFFERENT"), ("reg-lateral", "v2", None)],
    }
    assert compute_idempotency_key(**changed) != compute_idempotency_key(**BASE)


def test_idempotency_no_delimiter_collision():
    """Distinct model tuples must not collide via the field separator."""
    common = dict(
        scan_key="s",
        images_checksum="i",
        param_hash="p",
        predict_code_sha="pc",
        traits_code_sha="tc",
    )
    k1 = compute_idempotency_key(models=[("a::b", "c", "x")], **common)
    k2 = compute_idempotency_key(models=[("a", "b::c", "x")], **common)
    assert k1 != k2


def test_idempotency_distinguishes_none_and_empty_weights():
    """A None weights_checksum is distinct from an empty-string one."""
    common = dict(
        scan_key="s",
        images_checksum="i",
        param_hash="p",
        predict_code_sha="pc",
        traits_code_sha="tc",
    )
    k1 = compute_idempotency_key(models=[("a", "v", None)], **common)
    k2 = compute_idempotency_key(models=[("a", "v", "")], **common)
    assert k1 != k2


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


# --- predict_output_params contribution + byte-identity -----------------------

# Golden captured from PRE-CHANGE code over the BASE payload above. Pins the
# byte-stability of the six-key payload itself, independent of any Provenance.
_BASE_GOLDEN = "913e6492c459a4475231badb54c073243f98cfb0fed03db60b8bb507e2387e09"


def test_idempotency_base_golden():
    """The six-key BASE payload hashes to its pinned pre-change digest."""
    assert compute_idempotency_key(**BASE) == _BASE_GOLDEN


def test_output_params_none_equals_absent():
    """predict_output_params=None appends nothing (byte-identical to the old call)."""
    assert compute_idempotency_key(**BASE, predict_output_params=None) == (
        compute_idempotency_key(**BASE)
    )


def test_output_params_empty_equals_absent():
    """An empty output-params dict is truthy-gated out — same key as absent."""
    assert compute_idempotency_key(**BASE, predict_output_params={}) == (
        compute_idempotency_key(**BASE)
    )


def test_output_params_populated_differs():
    """A populated output-params subset changes the key."""
    assert compute_idempotency_key(
        **BASE, predict_output_params={"peak_threshold": 0.2}
    ) != compute_idempotency_key(**BASE)


def test_output_params_present_but_falsy_differs():
    """A present-but-falsy value (0.0) still changes the key (presence, not truth)."""
    assert compute_idempotency_key(
        **BASE, predict_output_params={"peak_threshold": 0.0}
    ) != compute_idempotency_key(**BASE)


def test_output_params_distinct_values_differ():
    """Distinct output-params dicts yield distinct keys."""
    k1 = compute_idempotency_key(**BASE, predict_output_params={"peak_threshold": 0.2})
    k2 = compute_idempotency_key(**BASE, predict_output_params={"peak_threshold": 0.3})
    assert k1 != k2


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_output_params_nonfinite_raises(bad):
    """Non-finite output-params values fail loud at the compute layer, like param_hash."""
    with pytest.raises(ValueError):  # NonCanonicalizableError subclasses ValueError
        compute_idempotency_key(**BASE, predict_output_params={"peak_threshold": bad})
