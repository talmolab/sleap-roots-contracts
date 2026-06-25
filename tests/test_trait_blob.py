"""Tests for TraitValue (NaN/inf normalization) and BlobRef validators."""

import math
from typing import get_args

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.models import BlobKind, BlobRef, RootType, TraitValue


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


def test_blobkind_allowed_set_is_exactly_predictions_slp():
    """BlobKind's controlled vocabulary is exactly {predictions_slp}."""
    assert set(get_args(BlobKind)) == {"predictions_slp"}


def test_blobref_rejects_previously_valid_kind():
    """A kind that used to be valid (e.g. 'labels') is now rejected."""
    with pytest.raises(ValidationError):
        BlobRef(
            kind="labels",
            scan_key="s1",
            s3_location="s3://b/k",
            root_type="primary",
        )


def test_roottype_vocabulary_is_primary_lateral_crown():
    """RootType's controlled vocabulary is exactly {primary, lateral, crown}."""
    assert set(get_args(RootType)) == {"primary", "lateral", "crown"}


def test_blobref_requires_root_type():
    """A BlobRef without a root_type is rejected."""
    with pytest.raises(ValidationError):
        BlobRef(kind="predictions_slp", scan_key="s1", s3_location="s3://b/k")


def test_blobref_rejects_unknown_root_type():
    """A BlobRef with an out-of-vocabulary root_type is rejected."""
    with pytest.raises(ValidationError):
        BlobRef(
            kind="predictions_slp",
            scan_key="s1",
            s3_location="s3://b/k",
            root_type="seedling",
        )


def test_blobref_retains_root_type():
    """A valid predictions blob keeps its root_type."""
    b = BlobRef(
        kind="predictions_slp",
        scan_key="s1",
        s3_location="s3://b/k",
        root_type="primary",
    )
    assert b.root_type == "primary"


def test_blobref_requires_a_location():
    """A BlobRef with no location is rejected (root_type supplied to isolate the rule)."""
    with pytest.raises(ValidationError):
        BlobRef(kind="predictions_slp", scan_key="s1", root_type="primary")


def test_blobref_s3_only_ok():
    """An s3-only BlobRef is valid."""
    b = BlobRef(
        kind="predictions_slp",
        scan_key="s1",
        s3_location="s3://b/k",
        root_type="primary",
    )
    assert b.box_link is None


def test_blobref_rejects_unknown_kind():
    """A BlobRef with an out-of-vocabulary kind is rejected (root_type isolates the rule)."""
    with pytest.raises(ValidationError):
        BlobRef(
            kind="not_a_kind",
            scan_key="s1",
            s3_location="s3://b/k",
            root_type="primary",
        )


def test_traitvalue_is_frozen():
    """A TraitValue cannot be mutated after construction (integrity holds)."""
    t = TraitValue(name="x", value=1.0, scan_key="s1")
    with pytest.raises(ValidationError):
        t.value = float("nan")


def test_blobref_location_constraint_derives_from_fields():
    """The emitted anyOf is built from real model fields (no rename drift)."""
    from sleap_roots_contracts.models import BlobRef, _BLOB_LOCATION_FIELDS

    # The single source of truth must be real fields on the model.
    assert set(_BLOB_LOCATION_FIELDS) <= set(BlobRef.model_fields)

    # The emitted schema's anyOf must require exactly those fields.
    schema = BlobRef.model_json_schema()
    required = {req for branch in schema["anyOf"] for req in branch["required"]}
    assert required == set(_BLOB_LOCATION_FIELDS)
