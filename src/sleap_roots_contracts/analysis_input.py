"""Canonical contract for the wide analysis-input table (structural validation).

This is the canonical Bloom-exchange shape with **fixed** role names. Consumers
canonicalize their own (configurable) column names to these before validating; the
contract takes no column-mapping parameter. Validation is **structural** — role
columns, dtypes, NaN policy, and "at least one numeric trait column." Trait names are
opaque: there is no trait-name registry and no value-range checking here (those stay a
``result-contract`` write-side concern and ``sleap-roots-analyze``'s statistical QC).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime pandas import
    import pandas as pd

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


# Fixed canonical role names. genotype is required and string; the rest are optional
# string metadata. Everything else in a table is an opaque numeric trait column.
REQUIRED_ROLE = "genotype"
OPTIONAL_ROLES = ("sample_id", "replicate", "image_path")
ROLE_COLUMNS = (REQUIRED_ROLE, *OPTIONAL_ROLES)

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class ValidationIssue:
    """One structural problem found in an analysis-input table.

    Attributes:
        column: The offending column, or ``None`` for a table-level issue.
        message: A human-readable description of the problem.
        severity: ``"error"`` (fails validation) or ``"warning"`` (advisory; an
            escalated warning under ``strict=True`` is recorded as an ``"error"``).
    """

    column: str | None
    message: str
    severity: Severity


@dataclass
class ValidationResult:
    """The outcome of validating an analysis-input table.

    ``ok`` is true exactly when there are no errors (warnings never flip it).
    """

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no errors were recorded."""
        return not self.errors

    def raise_for_status(self) -> None:
        """Raise ``ValueError`` if any error was recorded; no-op otherwise."""
        if not self.errors:
            return
        detail = "; ".join(
            f"[{issue.column}] {issue.message}" if issue.column else issue.message
            for issue in self.errors
        )
        raise ValueError(f"analysis input validation failed: {detail}")


def _import_pandas() -> ModuleType:
    """Import pandas lazily, with a guided error naming the optional extra.

    Kept inside this function (never imported at module top) so the package's
    runtime core stays pydantic + pyyaml — importing the library without pandas
    must succeed; only calling the validator requires it.
    """
    try:
        import pandas as pd
    except ImportError as exc:  # pragma: no cover - exercised via import mocking
        raise ImportError(
            "validate_analysis_input requires pandas, which is not installed. "
            "Install the optional extra: pip install 'sleap-roots-contracts[pandas]'"
        ) from exc
    return pd


def _is_numeric(series: "pd.Series", pd: ModuleType) -> bool:
    """True for a real-number (trait-eligible) column, excluding bool and complex."""
    return (
        pd.api.types.is_numeric_dtype(series)
        and not pd.api.types.is_bool_dtype(series)
        and not pd.api.types.is_complex_dtype(series)
    )


def _is_string(series: "pd.Series", pd: ModuleType) -> bool:
    """True for a role column holding strings (object or pandas StringDtype).

    Numeric/bool dtypes are rejected outright; for object/string dtypes every
    non-null value must be a ``str`` so an int-coded column read as ``object`` (or a
    numeric column) still fails the role dtype check — robust across pandas 2/3
    string-inference semantics.
    """
    if _is_numeric(series, pd) or pd.api.types.is_bool_dtype(series):
        return False
    return all(isinstance(value, str) for value in series.dropna())


def validate_analysis_input(
    df: "pd.DataFrame", *, strict: bool = False
) -> ValidationResult:
    """Structurally validate a wide analysis-input table against the fixed contract.

    Validates role columns, dtypes, NaN policy, and the "at least one numeric trait
    column" rule against the **fixed** canonical names — there is no column-mapping
    parameter; consumers canonicalize their own column names first. Trait names are
    opaque: no trait-name registry and no value-range checks are applied.

    Severity tiers:
        - **Errors** (always fail): missing ``genotype``; ``genotype`` not string-typed;
          ``NaN`` in ``genotype``; a declared role column with a wrong (non-string)
          dtype; zero numeric trait columns.
        - **Warnings** (advisory; escalate to errors when ``strict=True``): a missing
          ``sample_id``; an unexpected non-numeric column; ``NaN`` in optional metadata.
        - **Allowed**: ``NaN`` in trait columns.

    Args:
        df: The analysis-input table (a pandas DataFrame).
        strict: When true, warnings are recorded as errors.

    Returns:
        A :class:`ValidationResult` collecting every error and warning, each naming
        the offending column. Call ``raise_for_status()`` for exception semantics.

    Raises:
        ImportError: If pandas is not installed (install the ``[pandas]`` extra).
    """
    pd = _import_pandas()
    result = ValidationResult()

    def warn_or_error(column: str | None, message: str) -> None:
        if strict:
            result.errors.append(ValidationIssue(column, message, "error"))
        else:
            result.warnings.append(ValidationIssue(column, message, "warning"))

    columns = list(df.columns)

    # Duplicate column labels make df[name] return a DataFrame (not a Series), which
    # breaks every per-column check below. Reject up front with a table-level error
    # instead of crashing on the malformed structure.
    duplicates = sorted({c for c in columns if columns.count(c) > 1})
    if duplicates:
        result.errors.append(
            ValidationIssue(
                None, f"duplicate column names not allowed: {duplicates}", "error"
            )
        )
        return result

    # Required genotype: present, string-typed, non-null.
    if REQUIRED_ROLE not in columns:
        result.errors.append(
            ValidationIssue(
                REQUIRED_ROLE, "required column 'genotype' is missing", "error"
            )
        )
    elif not _is_string(df[REQUIRED_ROLE], pd):
        result.errors.append(
            ValidationIssue(
                REQUIRED_ROLE, "column 'genotype' must be string-typed", "error"
            )
        )
    elif df[REQUIRED_ROLE].isna().any():
        result.errors.append(
            ValidationIssue(
                REQUIRED_ROLE,
                "column 'genotype' contains missing values (NaN)",
                "error",
            )
        )

    # Recommended sample identifier: warn when absent (error under strict).
    if "sample_id" not in columns:
        warn_or_error("sample_id", "recommended column 'sample_id' is missing")

    # Optional metadata roles: wrong (non-string) dtype is a hard error; a NaN in an
    # otherwise-valid metadata column is a warning.
    for role in OPTIONAL_ROLES:
        if role not in columns:
            continue
        series = df[role]
        if not _is_string(series, pd):
            result.errors.append(
                ValidationIssue(
                    role,
                    f"role column '{role}' must be string-typed",
                    "error",
                )
            )
        elif series.isna().any():
            warn_or_error(role, f"optional metadata column '{role}' contains NaN")

    # Classify the remaining columns: numeric -> trait (opaque); else -> unexpected.
    trait_columns = []
    for column in columns:
        if column in ROLE_COLUMNS:
            continue
        if _is_numeric(df[column], pd):
            trait_columns.append(column)
        else:
            warn_or_error(column, f"unexpected non-numeric column '{column}'")

    if not trait_columns:
        result.errors.append(
            ValidationIssue(
                None, "no numeric trait column found (need at least one)", "error"
            )
        )

    return result
