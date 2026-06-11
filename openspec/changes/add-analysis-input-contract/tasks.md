## 1. Schema model

- [ ] 1.1 Add `src/sleap_roots_contracts/analysis_input.py` with `from __future__ import annotations`
- [ ] 1.2 Define `AnalysisInputRow` (Pydantic v2): required `genotype: str`; optional `str`
      `sample_id` / `replicate` / `image_path`; `extra="allow"` for the open set of trait columns
- [ ] 1.3 Customize JSON Schema (`json_schema_extra`) so additional properties are typed
      `{"type": ["number", "null"]}` (NaN allowed); write the model test first (red → green)

## 2. ValidationResult + validator

- [ ] 2.1 Define `ValidationResult` (`ok`, `errors`, `warnings`, `raise_for_status()`) and a
      `ValidationIssue` (column + message + severity); test the type first
- [ ] 2.2 Implement `validate_analysis_input(df, *, strict=False)` with lazy pandas import and a
      guided `ImportError` naming the `[pandas]` extra. NO column-mapping parameter — fixed canonical
      names.
- [ ] 2.3 Implement the three-tier severity checks (TDD per check):
      - **Errors:** missing `genotype`; `genotype` not `str`; zero numeric trait columns; wrong dtype
        on a declared role column; `NaN` in required `genotype`.
      - **Warnings** (error under `strict`): missing `sample_id`; unknown/unexpected column; `NaN` in
        optional metadata.
      - **Allowed:** `NaN` in trait columns.
      Each issue names the offending column. (No trait-name registry, no value-range checks — value
      range lives in `result-contract` + analyze QC.)

## 3. Schema emission + drift guard

- [ ] 3.1 Register `"analysis_input": AnalysisInputRow` in `schema.py`'s `MODELS`
- [ ] 3.2 Regenerate: `uv run python -m sleap_roots_contracts.schema`; commit
      `schema/analysis_input.schema.json`
- [ ] 3.3 Confirm the existing drift-guard and meta-validation tests now cover the new schema

## 4. Public API

- [ ] 4.1 Export `validate_analysis_input`, `ValidationResult`, `AnalysisInputRow` from
      `__init__.py` `__all__`; add an export-presence test

## 5. Fixtures + tests

- [ ] 5.1 Add `tests/fixtures/analysis_input/{cylinder,field,turface}.csv` built from the real
      EDPIE vocabularies (turface `Genotype`/`Barcode`, cylinder `accession_name`/`qr_code`,
      field/root-core) canonicalized to the canonical names; bundle: `talmolab/sleap-roots-analyze#120`
- [ ] 5.2 Wire the fixture **loader as a pytest fixture** (`tests/conftest.py` or a fixtures module),
      not a plain helper
- [ ] 5.3 `tests/test_analysis_input.py`: `@pytest.mark.parametrize` "each example validates" over the
      three shapes; missing-genotype error + `raise_for_status` raises; no-trait error; NaN
      allowed-in-trait / warn-in-metadata; unknown column warns-default / errors-strict; malformed
      table → column-named messages; missing-pandas `ImportError`; schema round-trip + drift guard

## 6. Packaging + docs

- [ ] 6.1 Add optional `[pandas]` extra in `pyproject.toml`; add pandas to the dev group so tests run
- [ ] 6.2 Note the new capability + validator in `README.md`

## 7. Verify

- [ ] 7.1 `uv run black --check src tests` && `uv run ruff check src tests`
- [ ] 7.2 `uv run python -m sleap_roots_contracts.schema && git diff --exit-code schema/`
- [ ] 7.3 `uv run pytest -v` (full suite green)
- [ ] 7.4 `openspec validate add-analysis-input-contract --strict`
