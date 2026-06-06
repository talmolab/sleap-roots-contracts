"""Tests for canonical-JSON param hashing."""

import math

import pytest

from sleap_roots_contracts.hashing import NonCanonicalizableError, compute_param_hash


def test_hash_is_deterministic():
    """The same dict hashes to the same value across calls."""
    v = {"species": "rice", "scale": 1.5}
    assert compute_param_hash(v) == compute_param_hash(v)


def test_hash_is_key_order_independent():
    """Key insertion order does not affect the hash."""
    assert compute_param_hash({"a": 1, "b": 2}) == compute_param_hash({"b": 2, "a": 1})


def test_hash_changes_with_value():
    """A different value yields a different hash."""
    assert compute_param_hash({"a": 1}) != compute_param_hash({"a": 2})


def test_hash_nested_key_order_independent():
    """Nested-dict key order does not affect the hash."""
    a = {"outer": {"x": 1, "y": 2}}
    b = {"outer": {"y": 2, "x": 1}}
    assert compute_param_hash(a) == compute_param_hash(b)


def test_hash_rejects_nan():
    """NaN values are rejected."""
    with pytest.raises(NonCanonicalizableError):
        compute_param_hash({"a": math.nan})


def test_hash_rejects_inf():
    """Inf values are rejected."""
    with pytest.raises(NonCanonicalizableError):
        compute_param_hash({"a": math.inf})


def test_hash_is_hex_sha256():
    """The hash is a 64-char lowercase hex sha256 string."""
    h = compute_param_hash({"a": 1})
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_hash_int_equals_integer_valued_float():
    """An int and the equal integer-valued float hash the same."""
    assert compute_param_hash({"a": 1}) == compute_param_hash({"a": 1.0})


def test_hash_negative_zero_equals_zero():
    """-0.0 and 0.0 hash the same."""
    assert compute_param_hash({"a": -0.0}) == compute_param_hash({"a": 0.0})


def test_hash_non_integer_float_distinct_from_int():
    """A genuine fractional value stays distinct from a nearby integer."""
    assert compute_param_hash({"a": 1.5}) != compute_param_hash({"a": 1})
    assert compute_param_hash({"a": 1.5}) != compute_param_hash({"a": 2})


def test_hash_normalizes_nested_numbers():
    """Int/float normalization applies recursively in nested containers."""
    assert compute_param_hash({"o": {"x": [2]}}) == compute_param_hash(
        {"o": {"x": [2.0]}}
    )


def test_hash_rejects_nan_nested_in_list():
    """NaN nested inside a list is rejected (not just top-level values)."""
    with pytest.raises(NonCanonicalizableError):
        compute_param_hash({"a": [1, math.nan]})


def test_hash_empty_dict_is_stable():
    """An empty params dict hashes deterministically."""
    assert compute_param_hash({}) == compute_param_hash({})
