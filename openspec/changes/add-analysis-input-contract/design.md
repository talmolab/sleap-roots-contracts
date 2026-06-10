## Context

Issue #3 specifies a canonical schema + `validate_analysis_input(df) -> ValidationResult` + an
emitted JSON Schema for the wide analysis-input CSV, mirroring the existing `validate_trait` +
`trait_definitions.yaml` + `result_envelope.schema.json` triad. Two facts about the existing repo
shape the design: (1) runtime deps are deliberately only `pydantic` + `pyyaml`; (2) `schema.py`
emits JSON Schema from Pydantic models (`model_json_schema()`) and CI drift-guards the result.

## Goals / Non-Goals

- Goals: a canonical row schema; a structured, importable validator; an emitted, drift-guarded JSON
  Schema; example fixtures per shape — all matching existing conventions.
- Non-Goals: wiring the validator into `sleap-roots-analyze`/`bloom-mcp` (separate downstream
  issues); a trait-name registry for analysis input (the per-trait registry stays the
  `result-contract` concern; range checks here reuse `trait_definitions.yaml` only where a column
  name matches a known trait).

## Decisions

- **Pydantic row model, not pandera.** The issue leaves this to the implementer. Pandera would add a
  heavy new dependency to a lib whose value proposition is being dependency-light, and would bypass
  the pydantic-native `schema.py` emission/drift-guard pipeline. A `AnalysisInputRow` Pydantic model
  plugs straight into `MODELS` and gets `analysis_input.schema.json` + the drift guard for free.
  *Alternative considered:* pandera `DataFrameSchema` — rejected for the dependency + dual
  emission-path cost.

- **Row schema for a wide table; cardinality lives in the validator.** JSON Schema describes one row
  object: `genotype` required string, metadata columns string, `additionalProperties` typed
  `number|null` (the trait columns). Row-level JSON Schema cannot express "≥1 trait column", so that
  table-level cardinality rule is enforced (and tested) only in the Python validator and documented
  as a known schema limitation for non-Python consumers.

- **`ValidationResult` + `raise_for_status()`, not a bare-raise validator.** The issue asks for both
  a `-> ValidationResult` return *and* "missing-required/out-of-range raise". A function cannot both
  return structured warnings and raise on the same call, so the validator always returns a
  `ValidationResult` (collecting every error and warning with the offending column), and callers who
  want exception semantics call `result.raise_for_status()`. This preserves `validate_trait`'s
  warn-vs-error severity model while delivering the structured output the issue requires.
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
- Distinguishing a "trait column" from an "unknown metadata column" is heuristic (numeric dtype +
  not a known metadata name) → mitigate with explicit fixtures and malformed-table tests pinning the
  classification, and `strict=True` to surface anything unexpected.

## Open Questions

- Should out-of-range trait values reuse `trait_definitions.yaml` ranges when a column name matches a
  registered trait, or stay name-agnostic for v1? (Lean: reuse where the name matches; skip range
  checks for unregistered trait columns.) — resolve during TDD; does not change the public API.
