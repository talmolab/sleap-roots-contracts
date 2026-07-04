"""Deterministic idempotency-key derivation (producer-side only)."""

from .hashing import canonical_json, sha256_hex


def compute_idempotency_key(
    *,
    scan_key: str,
    images_checksum: str,
    models: list[tuple[str, str, str | None]],
    param_hash: str,
    predict_code_sha: str,
    traits_code_sha: str,
    predict_output_params: dict | None = None,
) -> str:
    """Derive the run identity from inputs, models, params, and code versions.

    Args:
        scan_key: Producer-side scan identifier.
        images_checksum: Checksum over the input image set.
        models: (registry_id, version, weights_checksum) per model; order-independent.
        param_hash: Output of compute_param_hash.
        predict_code_sha: Git sha of the predict producer.
        traits_code_sha: Git sha of the traits producer.
        predict_output_params: The output-defining subset of the predict inference
            config (e.g. ``{"peak_threshold": 0.2}``). Contributes to the key **only
            when non-empty** — an absent or empty mapping appends nothing, so the
            derived key is byte-identical to the value produced before this argument
            existed. Hardware/throughput knobs must be kept out of this mapping (they
            are recorded elsewhere and must not affect cross-node dedup). Its values
            are canonicalized like ``param_hash``, so non-finite (``NaN``/``inf``)
            values raise.

    Returns:
        Hex sha256 identity string.
    """
    # Encode each model as a structured triple and order them by their canonical
    # JSON, so the key is order-independent yet injective: no delimiter ambiguity
    # and None (unpinned) stays distinct from "" (empty checksum).
    model_entries = sorted(
        (
            [registry_id, version, weights_checksum]
            for registry_id, version, weights_checksum in models
        ),
        key=canonical_json,
    )
    payload = {
        "scan_key": scan_key,
        "images_checksum": images_checksum,
        "models": model_entries,
        "param_hash": param_hash,
        "predict_code_sha": predict_code_sha,
        "traits_code_sha": traits_code_sha,
    }
    # Truthy-gate the output-params contribution: an absent/empty mapping adds no
    # key, so canonical_json emits the exact bytes it did before this field existed
    # and previously computed keys stay identical. canonical_json normalizes the
    # nested mapping (sorted keys, int-valued floats collapsed) and rejects NaN/inf.
    if predict_output_params:
        payload["predict_output_params"] = predict_output_params
    return sha256_hex(canonical_json(payload))
