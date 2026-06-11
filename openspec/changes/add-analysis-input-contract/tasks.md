## 0. Packaging first (CI needs pandas before the validator tests run)

- [x] 0.1 Add optional `[pandas]` extra in `pyproject.toml`; add pandas to the dev group so tests run.
      Commit `pyproject.toml` + `uv.lock` as a matched pair (keeps `uv sync` reproducible).
- [x] 0.2 Add `.gitattributes` pinning `schema/*.json text eol=lf` and
      `tests/fixtures/analysis_input/*.csv text eol=lf` so the drift guard is autocrlf-independent.

## 1. Schema model (test-first)

- [x] 1.1 Add `src/sleap_roots_contracts/analysis_input.py` with `from __future__ import annotations`
- [x] 1.2 Write the model test first (red): a well-formed row validates against `AnalysisInputRow`;
      a non-string `genotype` (int) is rejected
- [x] 1.3 Define `AnalysisInputRow` (Pydantic v2): required `genotype: str`; optional `str`
      `sample_id` / `replicate` / `image_path`; `extra="allow"` for the open set of trait columns;
      `json_schema_extra` so additional properties are typed `{"type": ["number", "null"]}` (NaN
      allowed). Green.

## 2. ValidationResult + validator (test-first, per check)

- [x] 2.1 Test then define `ValidationIssue` (`column`, `message`, `severity`) and `ValidationResult`
      (`ok`, `errors`, `warnings`, `raise_for_status()`)
- [x] 2.2 Implement `validate_analysis_input(df, *, strict=False)`. Lazy pandas import **inside the
      function body** (never at module top) with a guided `ImportError` naming the
      `sleap-roots-contracts[pandas]` extra. NO column-mapping parameter — fixed canonical names.
- [x] 2.2a Test (red first): patch the import so `pandas` is absent → `validate_analysis_input` raises
      `ImportError` whose message contains `[pandas]`; AND `import sleap_roots_contracts` /
      `from sleap_roots_contracts import validate_analysis_input` both still succeed with pandas
      absent (guards against a top-level pandas import)
- [x] 2.3 dtype detection must handle pandas ≥2 **and** 3.0 string semantics (object dtype *and*
      `StringDtype`): a string-valued `genotype` passes; integer/float `genotype` is an error. Use
      `pandas.api.types` (`is_numeric_dtype` / `is_string_dtype`), not naive `== object`.
- [x] 2.4 Implement + test the three-tier severity checks (one failing test each, then green):
      - **Errors:** missing `genotype` (2.4a); `genotype` not `str`, incl. int64 dtype (2.4b);
        `NaN` / all-NaN in the required `genotype` (2.4c); a declared role column
        (`sample_id`/`replicate`/`image_path`) with a numeric dtype (2.4d); zero numeric trait
        columns (2.4e). Each names its column; `raise_for_status()` raises.
      - **Classification (both directions):** a numeric non-role column counts as a **trait**
        (≥1-trait passes, no warning) (2.4f); a **non-numeric** stray column → unknown (2.4g).
      - **Warnings → error under `strict`:** missing `sample_id` (2.4h); unknown column (2.4i);
        `NaN` in optional metadata (2.4j). Each: warn + `ok` true by default; error + `ok` false
        under `strict=True`.
      - **Allowed:** `NaN` in a trait column → `ok` true (2.4k).
      - **Empty table:** canonical columns + zero rows → column/dtype checks apply, no per-row NaN
        issues (2.4l).
      (No trait-name registry, no value-range checks — value range lives in `result-contract` +
      analyze QC.)

## 3. Schema emission + drift guard (atomic with model registration)

- [x] 3.1 Register `"analysis_input": AnalysisInputRow` in `schema.py`'s `MODELS`
- [x] 3.2 Regenerate `uv run python -m sleap_roots_contracts.schema`; commit
      `schema/analysis_input.schema.json` **in the same commit as 3.1 + the model** (registering
      without the committed `.json` red-fails the drift guard step *and* test)
- [x] 3.3 Positive schema-shape test (not just drift): `render("analysis_input")` has `genotype` in
      `required`, `properties.genotype.type == "string"`, and **exactly one** `additionalProperties`
      equal to `{"type": ["number", "null"]}` (pydantic's default `true` from `extra="allow"` must
      be overridden, not duplicated)
- [x] 3.4 Confirm the existing `MODELS`-iterating drift-guard + meta-validation tests now cover the
      new schema (no edits needed — they loop over `MODELS`)

## 4. Public API

- [x] 4.1 Export `validate_analysis_input`, `ValidationResult`, `AnalysisInputRow` from
      `__init__.py` `__all__` (only after the symbols exist); add an export-presence test

## 5. Fixtures + tests

- [x] 5.1 Add `tests/fixtures/analysis_input/{cylinder,field,turface,genotype_means}.csv` — small
      **real** subsets of the wheat EDPIE post-QC `10_final_data.csv` tables (bundle:
      `talmolab/sleap-roots-analyze#120`), committed static (no network). Rename only the role columns
      to canonical (`Genotype`/`Barcode`/`Replicate`); keep real trait names + 1–2 numeric-metadata
      **decoy** columns (`scan_id`, `plant_age_days`, `Plot`, `Computation.Time.s`) to pin the
      structural classifier. Three are sample-level; `genotype_means.csv` is genotype-aggregated
      (no `sample_id`) for the warn path. Document provenance in a fixtures README.
- [x] 5.2 Wire the fixture **loader as a pytest fixture** (`tests/conftest.py`), not a plain helper;
      read via `pd.read_csv` (line-ending tolerant)
- [x] 5.3 `tests/test_analysis_input.py`: `@pytest.mark.parametrize` "each example validates cleanly"
      over the three shapes (`ok` true)

## 6. Docs

- [x] 6.1 Update `README.md`: name the `analysis-input-contract` / `validate_analysis_input` alongside
      the result+provenance contract, and note the optional `[pandas]` install extra (runtime core
      stays pydantic + pyyaml)
- [x] 6.2 Add an `### Added` entry under `## [Unreleased]` in `docs/CHANGELOG.md` for the capability
- [x] 6.3 Update `openspec/project.md`: Purpose now covers two contracts; add pandas as an **optional**
      extra under Tech Stack / External Dependencies (keep "runtime core = pydantic + pyyaml")

## 8. Canonicalization precondition (post-review refinement)

- [x] 8.1 Document the precondition (validator validates the canonicalized role+trait frame; non-trait
      metadata excluded upstream — analyze's `get_trait_columns`, analyze#144) in the validator
      docstring, `proposal.md`, `design.md`, and `spec.md`. Add a design decision: do NOT duplicate
      analyze's metadata denylist (structural-only; avoids a second source of truth + Bug #75
      brittleness).
- [x] 8.2 Regenerate the example fixtures as **canonical** tables (role + trait columns only — drop the
      numeric-metadata decoys `scan_id`/`plant_age_days`/`Plot`/`Cid`/`Computation.Time.s`/`n_samples`).
- [x] 8.3 Move the metadata-as-trait pin to an inline unit test
      (`test_metadata_named_numeric_column_is_still_a_trait`); add a test asserting the shipped
      examples carry no metadata decoys; update the fixtures README.

## 9. Packaged example tables (post-review: ship in the wheel)

- [x] 9.1 Relocate the canonical example CSVs from `tests/fixtures/analysis_input/` to
      `src/sleap_roots_contracts/examples/` so they ship in the wheel (`tests/` is not packaged).
- [x] 9.2 Add the `sleap_roots_contracts.examples` accessor: `load_analysis_input_example(name)`
      (reads role columns as `str` so the frame validates as-is), `analysis_input_example_path(name)`,
      `analysis_input_example_names()` / `ANALYSIS_INPUT_EXAMPLES`.
- [x] 9.3 Add `cylinder_no_replicate.csv` (replicate-absent sample-level — Bloom cylinder,
      `talmolab/sleap-roots-analyze#142`) so the example set covers replicate present + absent +
      genotype-aggregated (`talmolab/sleap-roots-analyze#120`).
- [x] 9.4 Point `conftest.py` at the packaged accessor; add tests: each example loads + validates;
      the accessor canonicalizes role dtypes (raw `read_csv` fails); the examples ship in the built
      wheel. Update `.gitattributes` for the new CSV path.
- [x] 9.5 Bump the package version `0.1.0a0` → `0.1.0a1` (so consumers can pin the analysis-input
      contract); regenerate both `schema/*.json` (`$id` carries the version).

## 7. Verify

- [x] 7.1 `uv run black --check src tests` && `uv run ruff check src tests`
- [x] 7.2 `uv run python -m sleap_roots_contracts.schema && git diff --exit-code schema/`
- [x] 7.3 `uv run pytest -v --cov=sleap_roots_contracts --cov-report=term-missing` (full suite green;
      eyeball coverage of `analysis_input.py`, incl. the no-pandas branch)
- [x] 7.4 `openspec validate add-analysis-input-contract --strict`
