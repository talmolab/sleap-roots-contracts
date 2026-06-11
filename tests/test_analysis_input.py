"""Tests for the analysis-input contract: row model, schema, and validator."""

import json

import pytest

from sleap_roots_contracts.analysis_input import AnalysisInputRow
from sleap_roots_contracts.schema import render


class TestAnalysisInputRow:
    """The canonical row model with fixed role names + open trait columns."""

    def test_wellformed_row_validates(self):
        """A string genotype + optional sample_id + numeric traits is accepted."""
        row = AnalysisInputRow(genotype="A10", sample_id="bc-1", total_length_mm=123.4)
        assert row.genotype == "A10"
        assert row.sample_id == "bc-1"

    def test_optional_role_fields_default_to_none(self):
        """sample_id / replicate / image_path are optional."""
        row = AnalysisInputRow(genotype="A10")
        assert row.sample_id is None
        assert row.replicate is None
        assert row.image_path is None

    def test_nonstring_genotype_is_rejected(self):
        """A numeric genotype (not a string) raises a validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AnalysisInputRow(genotype=123)

    def test_trait_columns_are_allowed_as_extra(self):
        """Open-set trait columns ride along via extra='allow'."""
        row = AnalysisInputRow(genotype="A10", network_area=1.0, primary_count=3.0)
        dumped = row.model_dump()
        assert dumped["network_area"] == 1.0
        assert dumped["primary_count"] == 3.0


class TestAnalysisInputSchema:
    """The emitted JSON Schema artifact for AnalysisInputRow."""

    def test_genotype_required_and_string(self):
        """genotype is required and typed string."""
        schema = json.loads(render("analysis_input"))
        assert "genotype" in schema["required"]
        assert schema["properties"]["genotype"]["type"] == "string"

    def test_additional_properties_typed_number_or_null(self):
        """Exactly one additionalProperties, typed number|null (not pydantic's true)."""
        schema = json.loads(render("analysis_input"))
        assert schema["additionalProperties"] == {"type": ["number", "null"]}
