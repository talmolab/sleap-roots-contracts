## Why

The canonical input to `sleap-roots-analyze` — the **wide trait CSV**
(`genotype`/`replicate`/`barcode` + numeric trait columns) — is a data shape that crosses repo
boundaries. It is consumed by `sleap-roots-analyze` directly (`run-all --manifest`, the CLI,
notebooks, golden tests) **and** by `bloom-mcp`'s data-access layer, **and** validated by Bloom
(non-Python) against an emitted JSON Schema. A contract consumed by more than one repo belongs in
this dependency-light, Bloom-agnostic library alongside `result-contract`, not inside one of its
consumers. This follows the pattern already established here: the lib owns a canonical model
**and** a validator backed by a shipped artifact (cf. `validate_trait` + `trait_definitions.yaml`).

Tracks `talmolab/sleap-roots-contracts#3` (re-homed from `sleap-roots-analyze#121`).

## What Changes

- Add a new capability **`analysis-input-contract`**: a canonical schema for the wide analysis-input
  table plus a validator and an emitted JSON Schema.
- Define a Pydantic **row model** (`AnalysisInputRow`) describing one row of the table: required
  `genotype` (str), optional metadata columns (`replicate`, `barcode`, `wave`, `experiment`; str,
  non-null), and an open set of numeric trait columns (`float64`, NaN allowed) via
  `additionalProperties`.
- Add `validate_analysis_input(df, *, strict=False) -> ValidationResult`, exported from the package
  root (mirrors `validate_trait`): collects structured errors/warnings — missing-required column or
  zero trait columns, wrong dtype, out-of-range trait value, and NaN-in-metadata are **errors**;
  unknown columns **warn** by default and **error** under `strict=True`. `ValidationResult` carries
  `ok`, `errors`, `warnings`, and a `.raise_for_status()` that raises on any error.
- Register the row model in `schema.py` and emit **`schema/analysis_input.schema.json`**, picked up
  by the existing CI drift guard exactly like `result_envelope.schema.json`.
- Add **example fixtures** for each shape (cylinder / field / turface) under `tests/fixtures/`, plus
  a malformed-DataFrame test asserting useful error messages.
- Add **pandas** as an optional install extra (`sleap-roots-contracts[pandas]`); `validate_analysis_input`
  imports it lazily and raises a clear `ImportError` if absent. Runtime core deps stay pydantic + pyyaml.

## Impact

- Affected specs: `analysis-input-contract` (new capability).
- Affected code:
  - `src/sleap_roots_contracts/analysis_input.py` (new) — `AnalysisInputRow`, `ValidationResult`,
    `validate_analysis_input`.
  - `src/sleap_roots_contracts/__init__.py` — export `validate_analysis_input`, `ValidationResult`,
    `AnalysisInputRow`.
  - `src/sleap_roots_contracts/schema.py` — add `analysis_input` to `MODELS`.
  - `schema/analysis_input.schema.json` (new, generated + drift-guarded).
  - `pyproject.toml` — optional `[pandas]` extra.
  - `tests/` — `test_analysis_input.py`, `tests/fixtures/analysis_input/*.csv`.
- Downstream follow-ups (separate issues, after this ships): `sleap-roots-analyze` imports + calls
  `validate_analysis_input` in `run-all`/loaders; `bloom-mcp` data-access consumes it.
