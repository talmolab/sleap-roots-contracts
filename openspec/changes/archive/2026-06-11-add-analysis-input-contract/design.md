## Context

Issue #3 specifies a canonical schema + `validate_analysis_input(df) -> ValidationResult` + an
emitted JSON Schema for the wide analysis-input CSV. Two facts about the existing repo shape the
design: (1) runtime deps are deliberately only `pydantic` + `pyyaml`; (2) `schema.py` emits JSON
Schema from Pydantic models (`model_json_schema()`) and CI drift-guards the result.

**The problem being solved (the crux of this design).** In `sleap-roots-analyze`, the role column
*names* are configurable (`ColumnConfig`: `genotype` defaults to `"geno"`, sample id to `"Barcode"`,
replicate to `"rep"`). A contract cannot validate against names that vary per dataset, and the
emitted JSON Schema (which Bloom / TypeScript validate against) needs **fixed** names. **This
contract hardcodes the canonical role names** and takes **no column-mapping parameter** — it is the
canonical Bloom-exchange shape with fixed role names, and consumers canonicalize their own data to it
before validating (`bloom-mcp` data-access already does; `sleap-roots-analyze` renames
config → canonical at its loader boundary, `talmolab/sleap-roots-analyze#144`). It is deliberately
**not** Bloom's internal schema; the Bloom-columns → canonical mapping lives in the data-access
layer, not here.

## Goals / Non-Goals

- Goals: a canonical row schema with **fixed** role names; a structured, importable validator; an
  emitted, drift-guarded JSON Schema; example fixtures per shape — all matching existing conventions.
- Non-Goals:
  - A **column-mapping parameter** — the contract validates fixed canonical names only; consumers
    canonicalize upstream.
  - A **trait-name registry** for analysis input, and **any value-range / out-of-range checks**. This
    contract is **structural-only**: trait names are opaque. Per-trait name/dtype/range validation
    and `trait_definitions.yaml` stay a `result-contract` (write-side) concern (`validate_trait`),
    and statistical outlier handling stays `sleap-roots-analyze`'s QC (`detect_outliers` / `cleanup`).
    Nothing here reads `trait_definitions.yaml`.
  - Wiring the validator into `sleap-roots-analyze` / `bloom-mcp` (separate downstream issues:
    `talmolab/sleap-roots-analyze#144` and the bloom-mcp data-access consumer).

## Decisions

- **Fixed canonical role names; no mapping parameter.** Roles are hardcoded: `genotype` (required,
  `str`), `sample_id` / `replicate` / `image_path` (optional, `str`). `replicate` is optional because
  its value is never load-bearing in analysis and Bloom cylinder data has no replicate factor
  (`talmolab/sleap-roots-analyze#142`). `sample_id` is optional but *flagged when absent* (warn;
  error under `strict`) because the only legitimately sample-id-less inputs are genotype-aggregated
  tables. The four names align with `ColumnConfig`'s roles (note `image_path`, absent from earlier
  drafts).

- **Pydantic row model, not pandera.** The issue leaves this to the implementer. Pandera would add a
  heavy new dependency to a lib whose value proposition is being dependency-light, and would bypass
  the pydantic-native `schema.py` emission/drift-guard pipeline. An `AnalysisInputRow` Pydantic model
  plugs straight into `MODELS` and gets `analysis_input.schema.json` + the drift guard for free.
  *Alternative considered:* pandera `DataFrameSchema` — rejected for the dependency + dual
  emission-path cost.

- **Row schema for a wide table; cardinality lives in the validator.** JSON Schema describes one row
  object: `genotype` required string, optional role columns string, `additionalProperties` typed
  `number|null` (the open set of trait columns). Row-level JSON Schema cannot express "≥1 trait
  column", so that table-level cardinality rule is enforced (and tested) only in the Python validator
  and documented as a known schema limitation for non-Python consumers.

- **Three-tier severity model.** Only three rules are universal hard errors: `genotype` present,
  `genotype` typed `str`, and ≥1 numeric trait column (plus dtype sanity on any declared role column).
  Everything else warns by default and escalates under `strict=True`: a missing `sample_id`, an
  unknown/unexpected column (the metadata column *set* is open — no closed allowlist), and `NaN` in
  optional metadata. `NaN` is allowed in trait columns. This mirrors `validate_trait`'s
  warn-vs-error model while delivering structured output.

- **Validate the canonicalized, trait-subsetted frame; do not duplicate the consumer's metadata
  exclusion.** Precondition: the validator receives role columns + trait columns, with non-trait
  metadata already excluded upstream. `sleap-roots-analyze` already owns a robust, dataset-aware
  exclusion at its load boundary — `get_trait_columns` (`data_cleanup.py`) drops role columns, a
  hardcoded metadata denylist (`scan_*`, `*_id`, `plant_age`, `wave_*`, `Plot`, `date`/`time`, …),
  and user-configurable `additional_exclude_cols` — and per-operation trait selection means metadata
  never reaches its stats/PCA/heritability. Replicating that denylist here would (a) violate the
  structural-only / opaque-names decision, (b) create a second source of truth that drifts from
  analyze's, and (c) inherit its brittleness — analyze's Bug #75 (a bare `"id"` substring excluded
  real traits `solidity`/`width` until narrowed to the `_id` suffix) is exactly the name-guessing this
  contract avoids. So the contract stays structural: any numeric non-role column is an opaque trait,
  and the consumer canonicalizes (rename roles + drop metadata) *before* calling
  `validate_analysis_input` (`talmolab/sleap-roots-analyze#144`). The shipped example fixtures are
  therefore canonical (role + trait only); the metadata-as-trait limitation is pinned by an inline
  unit test rather than baked into the example tables.
  *Alternative considered:* a built-in metadata denylist / `traits=`/`exclude=` parameter — rejected
  per (a)–(c); column selection belongs in the consumer where the config + dataset knowledge lives.

- **`ValidationResult` + `raise_for_status()`, not a bare-raise validator.** The issue asks for both
  a `-> ValidationResult` return *and* "missing-required raise". A function cannot both return
  structured warnings and raise on the same call, so the validator always returns a `ValidationResult`
  (collecting every error and warning with the offending column), and callers who want exception
  semantics call `result.raise_for_status()`.
  *Alternative considered:* raise immediately on the first hard error — rejected because it reports
  only one problem per call and discards the warnings channel.

- **pandas as an optional extra.** The validator inherently consumes a DataFrame, but adding pandas
  to runtime core deps contradicts the lib's minimalism. pandas becomes the `[pandas]` install
  extra; `validate_analysis_input` imports it lazily and raises a guided `ImportError` if absent.
  Both real consumers (`sleap-roots-analyze`, `bloom-mcp`) already ship pandas. The pydantic model
  and the emitted JSON Schema add zero new dependencies.

## Risks / Trade-offs

- "≥1 trait column" is invisible to JSON-Schema-only (Bloom) consumers → mitigate by documenting it
  in the spec and the schema's description, and enforcing it in the Python validator.
- Distinguishing a "trait column" from numeric metadata is structural (numeric dtype ⇒ trait). A
  numeric-but-not-a-trait column (e.g. `Computation.Time.s`, root-core's `Plot`, `scan_id`) would
  classify as a trait — accepted by design (see the canonicalization decision above): the consumer
  excludes such columns *before* validating. The risk surfaces for **non-analyze** consumers (bloom-mcp,
  Bloom via the JSON Schema) that lack analyze's `get_trait_columns` — mitigated by documenting the
  precondition in the spec + the validator docstring, and pinning the limitation with a unit test.
  Pinned against the real EDPIE fixtures (`talmolab/sleap-roots-analyze#120`).
