# Changelog

All notable changes to `sleap-roots-contracts` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with PEP 440 pre-release suffixes).

## [Unreleased]

## [0.1.0a2] - 2026-06-25 (Pre-release)

Revises the `BlobRef` contract for Bloom's change C (narrow the artifact kind and
attach a strict root-type vocabulary).

### Changed
- **BREAKING:** `BlobRef.kind` (`BlobKind`) narrowed to the single value
  `Literal["predictions_slp"]`; the controlled vocabulary is mirrored in the
  regenerated JSON Schema as a one-element `enum` (single-value `Literal`s are
  normalized from `const` to `enum` so a vocabulary's "allowed set" shape is
  uniform regardless of cardinality).
- **BREAKING:** `BlobRef` now has a **required** `root_type` field constrained to
  `RootType = Literal["primary", "lateral", "crown"]` (no default); a `BlobRef`
  built without `root_type` raises `ValidationError`.
- Exported `BlobKind` and `RootType` from the package root.
- `ModelRef.root_type` intentionally left as `str | None` (recorded decision,
  talmolab/sleap-roots-contracts#5) — it is a forward-looking model-registry
  pointer, not the artifact's root-type label.

### Removed
- **BREAKING:** Dropped `labels`, `h5`, and `qc_image` from `BlobKind`; `traits_csv`
  is permanently excluded (trait numbers are `TraitValue` rows, not blobs).

## [0.1.0a1] - 2026-06-11 (Pre-release)

### Added
- **`analysis-input-contract` capability** — a second contract for the wide
  analysis-input table that crosses the `sleap-roots-analyze` ↔ Bloom boundary:
  - `AnalysisInputRow` (Pydantic v2 row model) with fixed canonical role names
    (required `genotype`; optional `sample_id` / `replicate` / `image_path`) plus
    an open set of opaque numeric trait columns.
  - `validate_analysis_input(df, *, strict=False) -> ValidationResult` — a
    **structural** validator (role columns, dtypes, NaN policy, ≥1 numeric trait;
    trait names are opaque — no trait-name registry and no value-range checks). A
    three-tier severity model: hard errors / warnings that escalate under
    `strict=True` / NaN allowed in traits. `ValidationResult` carries `ok`,
    `errors`, `warnings`, and `raise_for_status()`; each issue names its column.
  - `canonicalize_role_dtypes(df)` — the shared role-dtype canonicalization (cast
    canonical role columns to string) that consumers apply before validating, since
    the validator is pure and does not coerce.
  - Emitted `schema/analysis_input.schema.json`, drift-guarded in CI.
  - pandas is an optional `[pandas]` install extra (lazy import + guided
    `ImportError`); the runtime core stays pydantic + pyyaml.
  - **Packaged example tables** under `sleap_roots_contracts.examples` (ship in the
    wheel): `load_analysis_input_example(name)` returns a frame with string-typed role
    columns that passes `validate_analysis_input` directly; covers replicate-present
    sample-level, replicate-absent sample-level (Bloom cylinder), and genotype-aggregated
    shapes — the source of truth for `talmolab/sleap-roots-analyze#120`.

## [0.1.0a0] - 2026-06-08 (Pre-release)

First release of the result + provenance contract — sub-project #1 of the
sleap-roots ↔ Bloom pipeline integration. Pure, dependency-light, Bloom-agnostic
(no DB / network / Argo / model code).

### Added
- Pydantic v2 contract models: `ResultEnvelope`, `Provenance`, `InputRef`,
  `ModelRef`, `ResolvedParams`, `TraitValue`, `BlobRef`. Models are immutable
  (`frozen`) so derived fields stay trustworthy after construction.
- Producer-side, canonical-JSON `compute_param_hash` (recursively sorted keys,
  fixed numeric representation, `NaN`/`inf` rejected) and a deterministic,
  model-order-independent `compute_idempotency_key` that is injective over models.
  Both are exported from the package root along with `NonCanonicalizableError`.
- Trait-definitions registry (`TraitDefinition`, `load_registry`,
  `validate_trait`) seeded from `trait_definitions.yaml`, with numeric/dtype/range
  validation and warn-on-unknown (default) or strict behavior.
- `TraitValue` normalizes non-finite values to `None` (→ SQL `NULL`); `BlobRef`
  enforces a controlled-vocabulary `kind` and at least one location, with that
  rule encoded in the emitted JSON Schema from a single source of truth.
- Versioned JSON Schema artifact (`schema/result_envelope.schema.json`,
  Draft 2020-12, version carried in `$id`) with a CI drift guard and
  meta-validation.
- CI (lint + drift guard + tests on Python 3.11/3.12) and a PyPI
  trusted-publishing workflow.

[Unreleased]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a2...HEAD
[0.1.0a2]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a1...v0.1.0a2
[0.1.0a1]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a0...v0.1.0a1
[0.1.0a0]: https://github.com/talmolab/sleap-roots-contracts/releases/tag/v0.1.0a0
