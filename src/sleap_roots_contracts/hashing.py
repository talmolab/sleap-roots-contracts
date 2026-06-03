"""Canonical-JSON hashing for params (producer-side only; Bloom treats output as opaque)."""

import hashlib
import json
import math
from typing import Any


class NonCanonicalizableError(ValueError):
    """Raised when a value cannot be canonicalized (e.g. NaN/inf)."""


def _check_finite(obj: Any) -> None:
    """Recursively reject NaN/inf floats."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise NonCanonicalizableError(
                f"NaN/inf not allowed in hashed values: {obj}"
            )
    elif isinstance(obj, dict):
        for value in obj.values():
            _check_finite(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _check_finite(value)


def canonical_json(values: dict[str, Any]) -> str:
    """Serialize to deterministic JSON: sorted keys, compact, no NaN/inf."""
    _check_finite(values)
    return json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(text: str) -> str:
    """Return the hex sha256 of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_param_hash(values: dict[str, Any]) -> str:
    """Compute the canonical, deterministic hash of a resolved-params dict."""
    return sha256_hex(canonical_json(values))
