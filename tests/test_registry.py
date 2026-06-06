"""Tests for the trait-definitions registry and value validation."""

import pytest

from sleap_roots_contracts.registry import (
    TraitDefinition,
    load_registry,
    validate_trait,
)


def test_load_registry_has_entries():
    """The packaged registry loads known traits as TraitDefinition objects."""
    reg = load_registry()
    assert "primary_length" in reg
    assert isinstance(reg["primary_length"], TraitDefinition)


def test_known_trait_passes():
    """A known trait with an in-range value validates without raising."""
    reg = load_registry()
    validate_trait("primary_length", 10.0, reg)  # no raise


def test_unknown_trait_warns_by_default():
    """An unknown trait warns by default."""
    reg = load_registry()
    with pytest.warns(UserWarning):
        validate_trait("totally_made_up_trait", 1.0, reg)


def test_unknown_trait_errors_when_strict():
    """An unknown trait raises when on_unknown='error'."""
    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("totally_made_up_trait", 1.0, reg, on_unknown="error")


def test_range_violation_errors():
    """A value below the definition min raises."""
    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("lateral_count", -1.0, reg)  # count must be >= 0


def test_none_value_skips_range_check():
    """A None value skips range checks."""
    reg = load_registry()
    validate_trait("lateral_count", None, reg)  # no raise


def test_int_dtype_rejects_non_integer_value():
    """A trait declared dtype=int rejects a non-integer value."""
    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("lateral_count", 1.5, reg)  # lateral_count is dtype int


def test_int_dtype_accepts_integer_valued_float():
    """A dtype=int trait accepts an integer-valued float (e.g. 3.0)."""
    reg = load_registry()
    validate_trait("lateral_count", 3.0, reg)  # no raise


def test_non_numeric_value_rejected():
    """A non-numeric value raises rather than a TypeError during comparison."""
    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("primary_length", "not-a-number", reg)


def test_nan_value_rejected():
    """A NaN value is rejected rather than silently passing range checks."""
    import math

    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("primary_length", math.nan, reg)


def test_inf_value_rejected():
    """An inf value is rejected rather than silently passing range checks."""
    import math

    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("primary_length", math.inf, reg)


def test_above_max_value_rejected():
    """A value above the definition max raises."""
    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("crown_angle", 361.0, reg)  # max is 360


def test_exact_boundary_values_accepted():
    """Values exactly at min and max are accepted (inclusive bounds)."""
    reg = load_registry()
    validate_trait("crown_angle", 0.0, reg)  # min
    validate_trait("crown_angle", 360.0, reg)  # max
