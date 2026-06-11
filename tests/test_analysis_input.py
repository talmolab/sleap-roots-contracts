"""Tests for the analysis-input contract: row model, schema, and validator."""

import json
import subprocess
import sys
import textwrap

import numpy as np
import pandas as pd
import pytest

from sleap_roots_contracts.analysis_input import (
    AnalysisInputRow,
    ValidationIssue,
    ValidationResult,
    validate_analysis_input,
)
from sleap_roots_contracts.schema import render


def _df(**columns) -> pd.DataFrame:
    """Build a DataFrame from explicit column arrays (keeps dtypes predictable)."""
    return pd.DataFrame(columns)


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


class TestPublicAPI:
    """The analysis-input surface is importable from the package root."""

    def test_exports_from_package_root(self):
        """validate_analysis_input, ValidationResult, AnalysisInputRow are exported."""
        import sleap_roots_contracts as src

        assert src.validate_analysis_input is validate_analysis_input
        assert src.ValidationResult is ValidationResult
        assert src.AnalysisInputRow is AnalysisInputRow
        for name in ("validate_analysis_input", "ValidationResult", "AnalysisInputRow"):
            assert name in src.__all__


class TestValidationResultType:
    """The structured result + issue types."""

    def test_ok_is_true_when_no_errors(self):
        """ok derives from the absence of errors (warnings don't flip it)."""
        result = ValidationResult(warnings=[ValidationIssue("c", "w", "warning")])
        assert result.ok is True

    def test_ok_is_false_when_errors_present(self):
        """Any error makes ok false."""
        result = ValidationResult(errors=[ValidationIssue("c", "e", "error")])
        assert result.ok is False

    def test_raise_for_status_raises_on_error(self):
        """raise_for_status raises when an error is present, naming the column."""
        result = ValidationResult(errors=[ValidationIssue("genotype", "bad", "error")])
        with pytest.raises(Exception, match="genotype"):
            result.raise_for_status()

    def test_raise_for_status_noop_when_ok(self):
        """raise_for_status is a no-op when there are no errors."""
        ValidationResult().raise_for_status()  # must not raise


class TestValidator:
    """validate_analysis_input three-tier severity model (structural-only)."""

    def test_valid_table_passes(self):
        """genotype + sample_id + a numeric trait validates clean."""
        df = _df(genotype=["A", "B"], sample_id=["s1", "s2"], total_length=[1.0, 2.0])
        result = validate_analysis_input(df)
        assert result.ok is True
        assert result.errors == []
        assert result.warnings == []

    # --- hard errors -------------------------------------------------------

    def test_missing_genotype_is_error_and_raises(self):
        """Missing genotype is an error; raise_for_status raises."""
        df = _df(sample_id=["s1"], total_length=[1.0])
        result = validate_analysis_input(df)
        assert result.ok is False
        assert any(i.column == "genotype" for i in result.errors)
        with pytest.raises(Exception):
            result.raise_for_status()

    def test_integer_genotype_dtype_is_error(self):
        """An int-typed genotype column (not str) is a hard error."""
        df = _df(genotype=[1, 2], sample_id=["s1", "s2"], total_length=[1.0, 2.0])
        result = validate_analysis_input(df)
        assert result.ok is False
        assert any(i.column == "genotype" for i in result.errors)

    def test_string_genotype_dtype_passes(self):
        """A string-typed genotype passes the dtype check."""
        df = _df(genotype=["A"], sample_id=["s1"], total_length=[1.0])
        assert validate_analysis_input(df).ok is True

    def test_nan_in_genotype_is_error(self):
        """A NaN in the required genotype column is an error."""
        df = _df(genotype=["A", None], sample_id=["s1", "s2"], total_length=[1.0, 2.0])
        result = validate_analysis_input(df)
        assert result.ok is False
        assert any(i.column == "genotype" for i in result.errors)

    def test_all_nan_genotype_is_error(self):
        """An all-NaN genotype column errors for the NaN reason, naming genotype."""
        df = _df(
            genotype=pd.Series([np.nan, np.nan], dtype="object"),
            sample_id=["s1", "s2"],
            total_length=[1.0, 2.0],
        )
        result = validate_analysis_input(df)
        assert result.ok is False
        # Must error for the NaN rule (not silently slip to a dtype error).
        assert any(
            i.column == "genotype" and "missing" in i.message.lower()
            for i in result.errors
        )

    def test_numeric_role_column_is_wrong_dtype_error(self):
        """A numeric (non-str) replicate column is a hard error; raises."""
        df = _df(
            genotype=["A", "B"],
            sample_id=["s1", "s2"],
            replicate=[1, 2],
            total_length=[1.0, 2.0],
        )
        result = validate_analysis_input(df)
        assert result.ok is False
        assert any(i.column == "replicate" for i in result.errors)
        with pytest.raises(Exception):
            result.raise_for_status()

    def test_zero_trait_columns_is_error(self):
        """A table with only role columns and no numeric trait is an error."""
        df = _df(genotype=["A", "B"], sample_id=["s1", "s2"], replicate=["1", "2"])
        result = validate_analysis_input(df)
        assert result.ok is False
        assert any("trait" in i.message.lower() for i in result.errors)

    # --- trait vs unknown classification (both directions) -----------------

    def test_numeric_non_role_column_counts_as_trait(self):
        """Any numeric non-role column is a trait (so >=1-trait passes, no warning)."""
        df = _df(genotype=["A"], sample_id=["s1"], some_opaque_metric=[42.0])
        result = validate_analysis_input(df)
        assert result.ok is True
        assert result.warnings == []

    def test_non_numeric_stray_column_warns_then_errors_strict(self):
        """A non-numeric stray column warns by default, errors under strict."""
        df = _df(genotype=["A"], sample_id=["s1"], total_length=[1.0], notes=["hello"])
        default = validate_analysis_input(df)
        assert default.ok is True
        assert any(i.column == "notes" for i in default.warnings)

        strict = validate_analysis_input(df, strict=True)
        assert strict.ok is False
        assert any(i.column == "notes" for i in strict.errors)

    # --- warnings that escalate under strict -------------------------------

    def test_missing_sample_id_warns_then_errors_strict(self):
        """Missing sample_id warns by default, errors under strict."""
        df = _df(genotype=["A", "B"], total_length=[1.0, 2.0])
        default = validate_analysis_input(df)
        assert default.ok is True
        assert any(i.column == "sample_id" for i in default.warnings)

        strict = validate_analysis_input(df, strict=True)
        assert strict.ok is False
        assert any(i.column == "sample_id" for i in strict.errors)

    def test_nan_in_optional_metadata_warns_then_errors_strict(self):
        """A NaN in an optional metadata column warns by default, errors strict."""
        df = _df(
            genotype=["A", "B"],
            sample_id=["s1", "s2"],
            replicate=["1", None],
            total_length=[1.0, 2.0],
        )
        default = validate_analysis_input(df)
        assert default.ok is True
        assert any(i.column == "replicate" for i in default.warnings)

        strict = validate_analysis_input(df, strict=True)
        assert strict.ok is False
        assert any(i.column == "replicate" for i in strict.errors)

    def test_all_nan_optional_role_warns_not_dtype_error(self):
        """An all-NaN optional role column is dtype-valid -> NaN warning, not error."""
        df = _df(
            genotype=["A", "B"],
            sample_id=["s1", "s2"],
            replicate=pd.Series([None, None], dtype="object"),
            total_length=[1.0, 2.0],
        )
        default = validate_analysis_input(df)
        assert default.ok is True
        assert any(i.column == "replicate" for i in default.warnings)
        assert not any(i.column == "replicate" for i in default.errors)

    # --- degenerate structure ----------------------------------------------

    def test_duplicate_role_column_is_error_not_crash(self):
        """Duplicate role columns are a table-level error, never an exception."""
        for role in ("genotype", "replicate"):
            df = pd.DataFrame(
                [["A", "A", 1.0]],
                columns=(
                    [role, role, "trait"]
                    if role != "genotype"
                    else ["genotype", "genotype", "trait"]
                ),
            )
            result = validate_analysis_input(df)  # must not raise
            assert result.ok is False
            assert any("duplicate" in i.message.lower() for i in result.errors)

    def test_duplicate_trait_column_is_error_not_misclassified(self):
        """A duplicated trait column is reported, not silently mis-rejected."""
        df = pd.DataFrame(
            [["A", "s1", 1.0, 2.0]], columns=["genotype", "sample_id", "t", "t"]
        )
        result = validate_analysis_input(df)
        assert result.ok is False
        assert any("duplicate" in i.message.lower() for i in result.errors)

    def test_complex_dtype_column_is_not_a_trait(self):
        """A complex-dtype column does not satisfy the >=1 real-number-trait rule."""
        df = _df(
            genotype=["A"], sample_id=["s1"], z=pd.Series([1 + 2j], dtype="complex128")
        )
        result = validate_analysis_input(df)
        assert result.ok is False
        assert any("trait" in i.message.lower() for i in result.errors)

    def test_bool_column_is_not_a_trait(self):
        """A bool column is excluded from numeric traits (warns as non-numeric)."""
        df = _df(genotype=["A", "B"], sample_id=["s1", "s2"], flag=[True, False])
        result = validate_analysis_input(df)
        assert result.ok is False  # bool doesn't satisfy the >=1-trait rule
        assert any("trait" in i.message.lower() for i in result.errors)
        assert any(i.column == "flag" for i in result.warnings)

    def test_all_roles_present_valid(self):
        """A table exercising every role column (incl. image_path) validates clean."""
        df = _df(
            genotype=["A", "B"],
            sample_id=["s1", "s2"],
            replicate=["1", "2"],
            image_path=["a.png", "b.png"],
            total_length=[1.0, 2.0],
        )
        result = validate_analysis_input(df)
        assert result.ok is True
        assert result.warnings == []

    # --- allowed -----------------------------------------------------------

    def test_nan_in_trait_is_allowed(self):
        """A NaN in a trait column is allowed (ok stays true)."""
        df = _df(
            genotype=["A", "B"],
            sample_id=["s1", "s2"],
            total_length=[1.0, np.nan],
        )
        assert validate_analysis_input(df).ok is True

    # --- empty table -------------------------------------------------------

    def test_empty_table_with_columns_validates_structurally(self):
        """Canonical columns + zero rows: structural checks apply, no row NaN issues."""
        df = _df(
            genotype=pd.Series([], dtype="object"),
            sample_id=pd.Series([], dtype="object"),
            total_length=pd.Series([], dtype="float64"),
        )
        result = validate_analysis_input(df)
        assert result.ok is True
        # No per-row NaN issue should fire for the absent rows.
        assert not any(
            "nan" in i.message.lower() for i in result.warnings + result.errors
        )

    def test_empty_table_missing_genotype_is_error(self):
        """A zero-row table still errors on a missing genotype column."""
        df = _df(total_length=pd.Series([], dtype="float64"))
        assert validate_analysis_input(df).ok is False

    # --- message quality ---------------------------------------------------

    def test_issues_carry_column_and_message(self):
        """Each issue exposes a column (or None for table-level) and a message."""
        df = _df(genotype=[1], replicate=[2])  # int genotype + no trait + numeric rep
        result = validate_analysis_input(df)
        assert result.errors
        for issue in result.errors:
            assert issue.message
            assert issue.severity == "error"
        # The column-attribution contract: the genotype dtype error names genotype,
        # and the table-level "no trait" error carries column=None.
        assert any(i.column == "genotype" for i in result.errors)
        assert any(
            i.column is None and "trait" in i.message.lower() for i in result.errors
        )


class TestExampleFixtures:
    """The shipped examples are real subsets of the wheat EDPIE post-QC tables.

    Only the role columns are canonical; trait names stay opaque and realistic
    (units, parens, dots: ``Network Area (mm²)``, ``Computation.Time.s``,
    ``Root Count 0cm``). Each table also carries a couple of real numeric-metadata
    decoy columns (e.g. ``scan_id``, ``plant_age_days``, ``Plot``) — the structural
    classifier has no registry, so it (correctly, by design) treats them as opaque
    trait columns; consumers drop such columns when canonicalizing (analyze#144).
    """

    def test_example_validates(self, example_analysis_input):
        """Each shipped example passes (ok, no errors); warnings are allowed."""
        result = validate_analysis_input(example_analysis_input)
        assert result.ok is True
        assert result.errors == []

    def test_sample_level_examples_have_no_warnings(self, load_analysis_input):
        """Sample-level examples (have sample_id) validate with zero warnings."""
        for name in ("cylinder", "field", "turface"):
            result = validate_analysis_input(load_analysis_input(name))
            assert result.ok is True
            assert result.warnings == [], name

    def test_genotype_aggregated_example_warns_missing_sample_id(
        self, load_analysis_input
    ):
        """The genotype-aggregated example (no sample_id) warns but stays ok."""
        result = validate_analysis_input(load_analysis_input("genotype_means"))
        assert result.ok is True
        assert any(i.column == "sample_id" for i in result.warnings)

    def test_examples_carry_realistic_opaque_trait_names(self, load_analysis_input):
        """Real fixtures preserve units/parens/dotted trait names (not synthetic)."""
        turface = load_analysis_input("turface")
        # "Network Area (mm²)" — match by prefix to avoid a unicode literal in source.
        assert any(c.startswith("Network Area (mm") for c in turface.columns)
        assert "Computation.Time.s" in turface.columns
        assert "Total Root Length (mm)" in turface.columns
        assert "Root Count 0cm" in load_analysis_input("field").columns

    def test_fixtures_require_role_dtype_canonicalization(self, analysis_input_dir):
        """The shipped CSVs validate only after role-dtype canonicalization.

        The real `10_final_data.csv` tables store `Replicate` as integers, so a plain
        `pd.read_csv` infers a numeric `replicate` (a wrong-dtype error). The conftest
        loader casts role columns to string — exactly the canonicalization a consumer
        must do — so make that requirement explicit rather than hidden.
        """
        raw = pd.read_csv(analysis_input_dir / "field.csv")  # no astype
        assert pd.api.types.is_numeric_dtype(raw["replicate"])  # documents the quirk
        assert validate_analysis_input(raw).ok is False  # raw fails by design
        canon = raw.astype({"replicate": "string", "genotype": "string"})
        assert validate_analysis_input(canon).ok is True

    def test_numeric_metadata_decoys_are_structurally_traits(self, load_analysis_input):
        """Pin the known limitation: real numeric-metadata cols classify as traits.

        cylinder ships ``scan_id`` / ``plant_age_days`` — numeric, not roles, so the
        structural validator counts them as (opaque) trait columns. The table still
        validates ok; nothing flags them. This is why consumers must canonicalize
        (drop non-trait numeric columns) before validating, not the contract's job.
        """
        cylinder = load_analysis_input("cylinder")
        assert {"scan_id", "plant_age_days"} <= set(cylinder.columns)
        result = validate_analysis_input(cylinder)
        assert result.ok is True
        assert result.errors == []
        # No warning is raised for the decoys (numeric ⇒ trait, by design).
        assert all(
            i.column not in {"scan_id", "plant_age_days"} for i in result.warnings
        )


class TestPandasOptional:
    """pandas is an optional [pandas] extra: lazy import + guided ImportError."""

    def test_missing_pandas_raises_guided_importerror(self, monkeypatch):
        """With pandas import blocked, the validator raises a guided ImportError."""
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "pandas" or name.startswith("pandas."):
                raise ImportError("No module named 'pandas'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        # The arg is never inspected — the lazy pandas import fails first. That this
        # ImportError fires at all proves the import is inside the function body
        # (a top-level import would not re-trigger __import__ on the call).
        with pytest.raises(ImportError, match=r"\[pandas\]"):
            validate_analysis_input(object())

    def test_package_imports_without_pandas(self):
        """import sleap_roots_contracts succeeds with pandas absent (no eager import)."""
        code = textwrap.dedent("""
            import sys
            class _Block:
                def find_spec(self, name, path, target=None):
                    if name == "pandas" or name.startswith("pandas."):
                        raise ImportError("pandas blocked")
                    return None
            sys.meta_path.insert(0, _Block())
            sys.modules.pop("pandas", None)
            import sleap_roots_contracts  # noqa: F401
            from sleap_roots_contracts.analysis_input import (  # noqa: F401
                validate_analysis_input,
            )
            print("OK")
            """)
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert proc.returncode == 0, proc.stderr
        assert "OK" in proc.stdout
