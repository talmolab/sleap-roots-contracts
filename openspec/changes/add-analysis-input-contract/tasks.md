## 1. Schema model

- [ ] 1.1 Add `src/sleap_roots_contracts/analysis_input.py` with `from __future__ import annotations`
- [ ] 1.2 Define `AnalysisInputRow` (Pydantic v2, frozen): required `genotype: str`; optional
      non-null metadata `replicate`/`barcode`/`wave`/`experiment`; `extra="allow"` for trait columns
- [ ] 1.3 Customize JSON Schema (`json_schema_extra`, derived from field names — no drift) so
      additional properties are typed `{"type": ["number", "null"]}` and metadata columns are
      `string` (not nullable); write the model test first (red → green)

## 2. ValidationResult + validator

- [ ] 2.1 Define `ValidationResult` (`ok`, `errors`, `warnings`, `raise_for_status()`) and a
      `ValidationIssue` (column + message + severity); test the type first
- [ ] 2.2 Implement `validate_analysis_input(df, *, strict=False)` with lazy pandas import and a
      guided `ImportError` naming the `[pandas]` extra
- [ ] 2.3 Implement checks: missing `genotype` → error; zero numeric trait columns → error; wrong
      dtype → error; out-of-range trait → error; NaN-in-metadata → error; NaN-in-trait → allowed;
      unknown column → warning (error under `strict`). Each error names the column. (TDD per check.)

## 3. Schema emission + drift guard

- [ ] 3.1 Register `"analysis_input": AnalysisInputRow` in `schema.py`'s `MODELS`
- [ ] 3.2 Regenerate: `uv run python -m sleap_roots_contracts.schema`; commit
      `schema/analysis_input.schema.json`
- [ ] 3.3 Confirm the existing drift-guard and meta-validation tests now cover the new schema

## 4. Public API

- [ ] 4.1 Export `validate_analysis_input`, `ValidationResult`, `AnalysisInputRow` from
      `__init__.py` `__all__`; add an export-presence test

## 5. Fixtures + tests

- [ ] 5.1 Add `tests/fixtures/analysis_input/{cylinder,field,turface}.csv` and a loader helper
- [ ] 5.2 `tests/test_analysis_input.py`: each example validates clean; malformed DataFrame asserts
      useful, column-named error messages; strict-vs-default unknown-column behavior; NaN policy

## 6. Packaging + docs

- [ ] 6.1 Add optional `[pandas]` extra in `pyproject.toml`; add pandas to the dev group so tests run
- [ ] 6.2 Note the new capability + validator in `README.md`

## 7. Verify

- [ ] 7.1 `uv run black --check src tests` && `uv run ruff check src tests`
- [ ] 7.2 `uv run python -m sleap_roots_contracts.schema && git diff --exit-code schema/`
- [ ] 7.3 `uv run pytest -v` (full suite green)
- [ ] 7.4 `openspec validate add-analysis-input-contract --strict`
