"""Canonical contract for the wide analysis-input table (structural validation).

This is the canonical Bloom-exchange shape with **fixed** role names. Consumers
canonicalize their own (configurable) column names to these before validating; the
contract takes no column-mapping parameter. Validation is **structural** — role
columns, dtypes, NaN policy, and "at least one numeric trait column." Trait names are
opaque: there is no trait-name registry and no value-range checking here (those stay a
``result-contract`` write-side concern and ``sleap-roots-analyze``'s statistical QC).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# The trait columns are an open set carried via ``extra="allow"``. Pydantic emits
# ``additionalProperties: true`` for ``extra="allow"``; override it via json_schema_extra
# so every additional (trait) property types as a nullable number in the emitted JSON
# Schema (NaN is allowed in trait columns). Kept as a module constant so the override is
# the single source of truth for the row model's additionalProperties.
_TRAIT_ADDITIONAL_PROPERTIES = {"additionalProperties": {"type": ["number", "null"]}}


class AnalysisInputRow(BaseModel):
    """One row of the canonical wide analysis-input table.

    Fixed canonical role names: a required string ``genotype`` plus optional string
    ``sample_id``, ``replicate``, and ``image_path``. Any further columns are treated as
    numeric **trait** columns (an open set with opaque names) carried via
    ``extra="allow"`` and typed ``number | null`` in the emitted JSON Schema.
    """

    model_config = ConfigDict(
        extra="allow", json_schema_extra=_TRAIT_ADDITIONAL_PROPERTIES
    )

    genotype: str
    sample_id: str | None = None
    replicate: str | None = None
    image_path: str | None = None
