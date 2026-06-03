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
) -> str:
    """Derive the run identity from inputs, models, params, and code versions.

    Args:
        scan_key: Producer-side scan identifier.
        images_checksum: Checksum over the input image set.
        models: (registry_id, version, weights_checksum) per model; order-independent.
        param_hash: Output of compute_param_hash.
        predict_code_sha: Git sha of the predict producer.
        traits_code_sha: Git sha of the traits producer.

    Returns:
        Hex sha256 identity string.
    """
    model_keys = sorted(
        f"{registry_id}::{version}::{weights_checksum or ''}"
        for registry_id, version, weights_checksum in models
    )
    payload = {
        "scan_key": scan_key,
        "images_checksum": images_checksum,
        "models": model_keys,
        "param_hash": param_hash,
        "predict_code_sha": predict_code_sha,
        "traits_code_sha": traits_code_sha,
    }
    return sha256_hex(canonical_json(payload))
