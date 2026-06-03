"""Tests for TraitValue (NaN/inf normalization) and BlobRef validators."""

import math

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.models import BlobRef, TraitValue


def test_traitvalue_defaults_grain_scan():
    """grain defaults to 'scan'."""
    t = TraitValue(name="primary_length", value=12.5, scan_key="s1")
    assert t.grain == "scan"


def test_traitvalue_nan_becomes_none():
    """A NaN value normalizes to None."""
    assert TraitValue(name="x", value=math.nan, scan_key="s1").value is None


def test_traitvalue_inf_becomes_none():
    """An inf value normalizes to None."""
    assert TraitValue(name="x", value=math.inf, scan_key="s1").value is None


def test_traitvalue_explicit_none_allowed():
    """An explicit None value is allowed."""
    assert TraitValue(name="x", value=None, scan_key="s1").value is None


def test_blobref_requires_a_location():
    """A BlobRef with no location is rejected."""
    with pytest.raises(ValidationError):
        BlobRef(kind="predictions_slp", scan_key="s1")


def test_blobref_s3_only_ok():
    """An s3-only BlobRef is valid."""
    b = BlobRef(kind="predictions_slp", scan_key="s1", s3_location="s3://b/k")
    assert b.box_link is None


def test_blobref_rejects_unknown_kind():
    """A BlobRef with an out-of-vocabulary kind is rejected."""
    with pytest.raises(ValidationError):
        BlobRef(kind="not_a_kind", scan_key="s1", s3_location="s3://b/k")
