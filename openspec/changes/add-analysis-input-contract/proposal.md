## Why

The canonical input to `sleap-roots-analyze` — the **wide trait CSV** (a `genotype` column, optional
sample/replicate/image metadata, and an open set of numeric trait columns) — is a data shape that
crosses repo boundaries. It is consumed by `sleap-roots-analyze` directly (`run-all --manifest`, the
CLI, notebooks, golden tests) **and** by `bloom-mcp`'s data-access layer, **and** validated by Bloom
(non-Python) against an emitted JSON Schema. A contract consumed by more than one repo belongs in
this dependency-light, Bloom-agnostic library alongside `result-contract`, not inside one of its
consumers.

**The problem this contract solves.** In `sleap-roots-analyze` the role column *names* are
configurable (`ColumnConfig`: `genotype` defaults to `"geno"`, sample id to `"Barcode"`, replicate to
`"rep"`). A contract cannot validate against names that vary per dataset, and the emitted JSON Schema
(which Bloom / TypeScript validate against) needs **fixed** names. **Resolution: this contract
hardcodes the canonical role names** and takes **no column-mapping parameter**. It is the canonical
Bloom-exchange shape with fixed role names; consumers canonicalize their own data to it
(`bloom-mcp` data-access already does; `sleap-roots-analyze` renames config → canonical at its loader
boundary, `talmolab/sleap-roots-analyze#144`). It is deliberately **not** Bloom's internal schema —
the Bloom-columns → canonical mapping lives in the data-access layer, not here.

**This contract is STRUCTURAL.** It validates *shape only*: role columns, dtypes, NaN policy, and
"≥1 numeric trait column." **Trait names are opaque.** There is **no trait-name registry** and **no
value-range checking** here — those stay a `result-contract` (write-side) concern
(`validate_trait` + `trait_definitions.yaml`, already shipped) and `sleap-roots-analyze`'s statistical
QC (`detect_outliers` / `cleanup`). Nothing in this change reads `trait_definitions.yaml`.

Tracks `talmolab/sleap-roots-contracts#3` (re-homed from `sleap-roots-analyze#121`).

## What Changes

- Add a new capability **`analysis-input-contract`**: a canonical schema for the wide analysis-input
  table plus a validator and an emitted JSON Schema.
- Define a Pydantic **row model** (`AnalysisInputRow`) describing one row with **fixed canonical role
  names**: required `genotype` (`str`); optional `sample_id`, `replicate`, `image_path` (`str`); and
  an open set of numeric **trait** columns (≥1, names opaque) carried via `extra="allow"` and typed
  in the JSON Schema as `{"type": ["number", "null"]}` (NaN allowed).
- Add `validate_analysis_input(df, *, strict=False) -> ValidationResult`, exported from the package
  root. It validates against the **fixed** canonical names (no mapping parameter) under a three-tier
  severity model:
  - **Errors** (always fail): missing `genotype`; `genotype` not `str`; `NaN` in the required
    `genotype`; zero numeric trait columns; wrong dtype on a declared role column.
  - **Warnings** (fail only under `strict=True`): missing `sample_id`; unknown/unexpected columns;
    `NaN` in optional metadata.
  - **Allowed**: `NaN` in trait columns.
  `ValidationResult` carries `ok`, `errors`, `warnings`, and a `.raise_for_status()` that raises on
  any error. Each `ValidationIssue` names the offending column. **Precondition:** the input is the
  canonicalized analysis table (role + trait columns); non-trait metadata is excluded upstream by the
  consumer (`sleap-roots-analyze`'s `get_trait_columns`, `talmolab/sleap-roots-analyze#144`). The
  contract has no metadata registry — any numeric non-role column is an opaque trait — so it does not
  (and is not meant to) replicate analyze's column-exclusion config.
- Register the row model in `schema.py` and emit **`schema/analysis_input.schema.json`**, picked up
  by the existing CI drift guard exactly like `result_envelope.schema.json`.
- Add **example fixtures** for each shape (cylinder / field / turface) under
  `tests/fixtures/analysis_input/`, loaded via pytest fixtures, each validating cleanly.
- Add **pandas** as an optional install extra (`sleap-roots-contracts[pandas]`);
  `validate_analysis_input` imports it lazily and raises a guided `ImportError` if absent. Runtime
  core deps stay pydantic + pyyaml.

## Impact

- Affected specs: `analysis-input-contract` (new capability).
- Affected code:
  - `src/sleap_roots_contracts/analysis_input.py` (new) — `AnalysisInputRow`, `ValidationIssue`,
    `ValidationResult`, `validate_analysis_input`.
  - `src/sleap_roots_contracts/__init__.py` — export `validate_analysis_input`, `ValidationResult`,
    `AnalysisInputRow`.
  - `src/sleap_roots_contracts/schema.py` — add `analysis_input` to `MODELS`.
  - `schema/analysis_input.schema.json` (new, generated + drift-guarded).
  - `pyproject.toml` — optional `[pandas]` extra; pandas added to the dev group.
  - `tests/` — `test_analysis_input.py`, `conftest.py` fixtures,
    `tests/fixtures/analysis_input/{cylinder,field,turface}.csv`.
- Downstream follow-ups (separate issues, after this ships): `sleap-roots-analyze` imports + calls
  `validate_analysis_input` at its loader boundary, canonicalizing config-names → canonical first
  (`talmolab/sleap-roots-analyze#144`); `bloom-mcp` data-access consumes it. Real-data validation
  bundle: `talmolab/sleap-roots-analyze#120` (wheat EDPIE, all three trait vocabularies). `replicate`
  is optional per `talmolab/sleap-roots-analyze#142`.
