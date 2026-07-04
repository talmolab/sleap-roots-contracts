"""Tests for the Provenance model and its auto-derived idempotency_key."""

import pytest

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


def test_provenance_accepts_matching_explicit_key():
    """A correct explicit idempotency_key (e.g. on round-trip) is accepted."""
    key = make_provenance().idempotency_key
    assert make_provenance(idempotency_key=key).idempotency_key == key


def test_provenance_rejects_mismatched_explicit_key():
    """A wrong explicit idempotency_key raises rather than being overwritten."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        make_provenance(idempotency_key="deadbeef")


# --- predict inference config -------------------------------------------------


def test_provenance_records_inference_config_fields():
    """Both predict inference-config mappings are recorded and retained."""
    p = make_provenance(
        predict_inference_config={"device": "cuda", "batch_size": 4},
        predict_output_params={"peak_threshold": 0.2},
    )
    assert p.predict_inference_config == {"device": "cuda", "batch_size": 4}
    assert p.predict_output_params == {"peak_threshold": 0.2}


def test_provenance_inference_config_fields_default_none():
    """Both new fields are optional and default to None."""
    p = make_provenance()
    assert p.predict_inference_config is None
    assert p.predict_output_params is None


def test_provenance_new_fields_survive_json_round_trip():
    """The two new mappings and the derived key survive a JSON round-trip."""
    p = make_provenance(
        predict_inference_config={"device": "cuda", "batch_size": 4},
        predict_output_params={"peak_threshold": 0.2},
    )
    restored = Provenance.model_validate_json(p.model_dump_json())
    assert restored.predict_inference_config == {"device": "cuda", "batch_size": 4}
    assert restored.predict_output_params == {"peak_threshold": 0.2}
    assert restored.idempotency_key == p.idempotency_key


# --- idempotency: output-params contribution + byte-identity ------------------

# Captured from PRE-CHANGE code (see the change's tasks.md group 3). This self-
# contained Provenance is built from inlined literals — NOT make_provenance — so a
# later fixture edit cannot silently re-baseline the byte-identity guarantee.
_GOLDEN_KEY = "42f67605ab4eac398f6c7c331cb4f267b6c5864a609bedc741b8dca8ea5f98d3"


def _golden_provenance(**overrides):
    """Build the fixed golden Provenance from inlined literals."""
    base = dict(
        contract_version="0.1.0a2",
        scan_key="golden-scan",
        inputs=InputRef(image_ids=["img-1", "img-2"], images_checksum="golden-images"),
        predict_models=[
            ModelRef(
                registry_id="reg-primary",
                version="v1",
                sleap_nn_version="0.1.0",
                root_type="primary",
                weights_checksum="wc-primary",
            )
        ],
        predict_container_digest="sha256:pred",
        predict_code_sha="predict-sha",
        traits_sleap_roots_version="1.0.0",
        traits_container_digest="sha256:traits",
        traits_code_sha="traits-sha",
        params=ResolvedParams(values={"species": "rice", "age": 7}),
    )
    base.update(overrides)
    return Provenance(**base)


def test_provenance_golden_key_is_byte_identical_to_pre_change():
    """A fixed Provenance with no new fields hashes to the pre-change golden digest.

    This proves BYTE-IDENTITY with keys produced before predict_output_params
    existed — not mere post-change self-consistency. If this moves, a truthy-gate or
    canonicalization regression has changed existing producers' keys; investigate
    rather than re-baseline.
    """
    assert _golden_provenance().idempotency_key == _GOLDEN_KEY


def test_absent_output_params_preserves_key():
    """Recording no output params leaves the key exactly as before."""
    from sleap_roots_contracts.identity import compute_idempotency_key

    p = _golden_provenance()
    expected = compute_idempotency_key(
        scan_key="golden-scan",
        images_checksum="golden-images",
        models=[("reg-primary", "v1", "wc-primary")],
        param_hash=p.params.param_hash,
        predict_code_sha="predict-sha",
        traits_code_sha="traits-sha",
    )
    assert p.idempotency_key == expected


def test_output_params_change_the_key():
    """Adding a populated output-params subset changes the key."""
    without = _golden_provenance()
    with_params = _golden_provenance(predict_output_params={"peak_threshold": 0.2})
    assert with_params.idempotency_key != without.idempotency_key


def test_hardware_knobs_do_not_change_the_key():
    """Two runs differing only in predict_inference_config dedup identically."""
    a = _golden_provenance(
        predict_inference_config={"device": "cuda", "batch_size": 4},
        predict_output_params={"peak_threshold": 0.2},
    )
    b = _golden_provenance(
        predict_inference_config={"device": "cpu", "batch_size": 1},
        predict_output_params={"peak_threshold": 0.2},
    )
    assert a.idempotency_key == b.idempotency_key


def test_inference_config_alone_preserves_the_golden_key():
    """Recording the full config but no output params leaves the key byte-identical.

    Guards the byte-identity guarantee directly at the Provenance layer (not only via
    transitivity through the hardware-knob comparison).
    """
    p = _golden_provenance(predict_inference_config={"device": "cuda", "batch_size": 4})
    assert p.idempotency_key == _GOLDEN_KEY


def test_empty_output_params_preserves_the_golden_key():
    """An empty output-params dict is truthy-gated out at the Provenance layer too."""
    assert _golden_provenance(predict_output_params={}).idempotency_key == _GOLDEN_KEY


def test_output_param_value_changes_the_key():
    """Two runs differing only in a peak_threshold get different keys."""
    a = _golden_provenance(predict_output_params={"peak_threshold": 0.2})
    b = _golden_provenance(predict_output_params={"peak_threshold": 0.3})
    assert a.idempotency_key != b.idempotency_key


def test_present_but_falsy_output_param_changes_the_key():
    """A present-but-falsy 0.0 still changes the Provenance key (presence, not truth).

    Pins the result-contract scenario at the Provenance layer where it is phrased,
    not only transitively via the compute-layer test.
    """
    p = _golden_provenance(predict_output_params={"peak_threshold": 0.0})
    assert p.idempotency_key != _golden_provenance().idempotency_key


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_output_param_raises(bad):
    """A non-finite (NaN/inf) output param fails loud at construction, like param_hash."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _golden_provenance(predict_output_params={"peak_threshold": bad})
