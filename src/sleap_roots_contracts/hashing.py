"""Canonical-JSON hashing for params (producer-side only; Bloom treats output as opaque)."""

import hashlib
import json
import math
from typing import Any


class NonCanonicalizableError(ValueError):
    """Raised when a value cannot be canonicalized (e.g. NaN/inf)."""


def _normalize(obj: Any) -> Any:
    """Recursively reject NaN/inf and normalize numbers to a fixed representation.

    Integer-valued floats collapse to int (``1.0`` -> ``1``, ``-0.0`` -> ``0``) so
    that type-variant params (int vs float) hash identically; ``bool`` is left
    untouched. The walk is byte-stable within a CPython version.
    """
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise NonCanonicalizableError(
                f"NaN/inf not allowed in hashed values: {obj}"
            )
        if obj == int(obj):
            return int(obj)
        return obj
    if isinstance(obj, dict):
        return {key: _normalize(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_normalize(value) for value in obj]
    return obj


def canonical_json(values: Any) -> str:
    """Serialize any JSON value to deterministic JSON: sorted keys, compact, no NaN/inf."""
    return json.dumps(
        _normalize(values),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(text: str) -> str:
    """Return the hex sha256 of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_param_hash(values: dict[str, Any]) -> str:
    """Compute the canonical, deterministic hash of a resolved-params dict.

    Raises:
        NonCanonicalizableError: a value is NaN/inf.
        TypeError: a value is not JSON-serializable.
    """
    return sha256_hex(canonical_json(values))
