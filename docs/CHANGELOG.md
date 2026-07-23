# Changelog

All notable changes to `sleap-roots-contracts` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with PEP 440 pre-release suffixes).

## [Unreleased]

## [0.1.0a6] - 2026-07-22 (Pre-release)

Adds the **label-selection contract** — `LabelCard` plus the contract-owned `Mode`
capture-mode vocabulary — the Python-side label-provenance shape shared by the
`/build-labeling-package` workflow (writer) and training/lineage tooling (reader). Like
`ModelCard`, this is a producer↔producer contract and is **not** emitted to JSON Schema.

### Added
- **`LabelCard` / `Mode`** — new label-selection-contract capability (mirrors `ModelCard`).
  Training's `MODE_VOCAB` collapses into the contract-owned `Mode`, closing the
  `cylinder`/`cyl` split from sleap-roots-training#10.

### Changed
- Both emitted schemas (`result_envelope`, `analysis_input`) are regenerated and their `$id`
  advances to `v0.1.0a6`. Bytes-only restamp — no model changes.

## [0.1.0a5] - 2026-07-21 (Pre-release)

Promotes `PredictionArtifact`/`PredictionManifest` from `sleap-roots-predict` into this
library so `bloomctl` can read predict's per-scan manifest without depending on an
unpublished package. Unblocks bloom's blob-upload work (bloom#407).

### Added
- **`PredictionArtifact`/`PredictionManifest`** — a new **prediction-manifest-contract**
  capability, a straight lift (all fields) of predict's `output_contract.py`, plus one new
  field: `PredictionArtifact.kind: BlobKind` (defaults to `"predictions_slp"`), reusing the
  existing `BlobKind` controlled vocabulary rather than redefining it. `PredictionManifest` is
  the per-scan output record (`schema_version`, `scan_key`, `plant_qr_code` defaulting to
  `scan_key`, `artifacts: list[PredictionArtifact]`, plus predict's on-disk provenance fields
  `predict_inference_config`/`predict_output_params`/`predict_code_sha`/
  `predict_container_digest`). Both models are frozen and exported from the package root.

  It was promoted out of `sleap-roots-predict` (which will consume it from here, predict#30)
  because `bloomctl` (bloom#407) needs this shape to construct `cyl_scan_intermediates` blob
  bytes, and `sleap-roots-predict` is not published to PyPI — a direct dependency on it was
  already rejected for a sibling bloom change. Like `ModelCard`, this is a Python-side
  **producer↔producer contract** between `sleap-roots-predict` and `bloomctl` and is **not**
  emitted to the JSON Schema.

### Changed
- Both emitted schemas (`result_envelope`, `analysis_input`) are regenerated and their `$id`
  advances to `v0.1.0a5`. This is a **bytes-only restamp** — `schema.py`'s `MODELS` dict gains
  no entries and no model in either schema changes — matching the `0.1.0a4` precedent.

## [0.1.0a4] - 2026-07-09 (Pre-release)

Promotes the param-resolution oracle from `sleap-roots-predict` into this library so
`sleap-roots-predict` and `bloomctl` share one implementation. Unblocks the Bloom A4
"images-downloader" stage-in (roadmap A3-params).

### Added
- **`resolve_params(metadata, overrides=None) -> ResolvedParams`** — a pure param-resolution
  oracle mapping a single Bloom `cyl_scans_extended` scan-metadata row to the
  `{species, mode, age}` params that select a `ModelCard`. Exported from the package root.
  It normalizes `species_name` (strip + lowercase, with an alias seam), derives `mode` through
  a single decision point (currently the constant `"cylinder"`), and coerces `plant_age_days`
  to a whole-number `int` (rejecting bools and non-whole floats). Optional `overrides` (a
  subset of `{species, mode, age}`) win per field and are canonicalized by the same rules, so
  `param_hash` is representation-independent. Blank/`None`/`NaN` fields are treated as not
  provided; anything still missing after the merge raises a `ValueError` naming every absent
  param.

  It was promoted out of `sleap-roots-predict` (which will consume it from here) because the
  resolved values feed `ResolvedParams.param_hash` → `Provenance.idempotency_key`
  (first-writer-wins): two producers normalizing differently would compute different keys for
  the same logical scan, both "win" the dedup race, and break idempotency with no error
  raised anywhere. The module's Bloom column-name constants `SPECIES_NAME_FIELD` and
  `PLANT_AGE_DAYS_FIELD` are module-public (so consumers can reference them) but are
  deliberately not part of the package `__all__`.

### Fixed
- **`resolve_params` rejects pandas/numpy missing-data sentinels instead of silently hashing
  them.** The oracle's guards were written against Python types, but its documented input is a
  pandas-parsed CSV row. A `pandas.NA`/`NaT` species was stringified to `"<na>"`, a
  `numpy.bool_(True)` age became `1`, a non-string species became `"123"`, and a fractional
  `decimal.Decimal` truncated — each **silently folded into `param_hash` → `idempotency_key`**
  with no error raised. A `float("inf")` age raised an uncaught `OverflowError` rather than the
  documented `ValueError`. All now raise a `ValueError` naming the offending field.

  Behavior is **unchanged for every well-formed input** — verified by a 2,268-case differential
  against the originating implementation showing identical `values`, `param_hash`, exception type,
  and exception message. Only rows that previously produced a corrupt hash (or the wrong exception)
  behave differently. Sentinel detection is duck-typed, so pandas is still never imported.

  Note `sleap-roots-predict` continues to carry the unhardened copy until it consumes this one
  (predict#28).

### Changed
- Both emitted schemas are regenerated and their `$id` advances to `v0.1.0a4`. This is a
  **bytes-only restamp**: no properties are added, removed, or altered (`resolve_params` is a
  producer-side function and is never emitted to JSON Schema). Downstream consumers should do
  the **standard full re-pin** — `pin.json`, the vendored schema (accept the `$id`-only diff),
  and regenerated TypeScript — **not** merely a pip-floor bump.
- CI now runs `uv lock --check` on pull requests. Previously a stale `uv.lock` passed PR CI
  (which uses a non-frozen `uv sync`) and only hard-failed later in the release build.

## [0.1.0a3] - 2026-07-04 (Pre-release)

Adds the model-selection contract (`ModelCard`) and records the predict inference
config in `Provenance`, folding its output-defining subset into `idempotency_key`.
Unblocks the `sleap-roots-predict` warm-model-worker slice (roadmap A3-predict).

### Added
- **`ModelCard`** — a new **model-selection contract** (frozen Pydantic model) carrying a
  production model's selection metadata (`species`, `mode`, an inclusive **approved
  selection window** `age_min`/`age_max` with `age_min <= age_max` and `ge=0`, and
  `root_type: RootType`) plus its concrete artifact identity (`registry_id`, `version`,
  optional `weights_checksum`) and an optional trained-with `sleap_nn_version`.
  `to_model_ref(runtime_sleap_nn_version)` returns a `ModelRef` stamped with the **runtime**
  sleap-nn version. Written by `sleap-roots-training` (as wandb artifact metadata) and read
  by `sleap-roots-predict`; it is a Python-side producer↔producer contract and is **not**
  emitted to the JSON Schema. Exported from the package root.
- **`Provenance.predict_inference_config`** and **`Provenance.predict_output_params`** — two
  optional mappings recording the predict inference config: the full effective config for
  audit (including hardware/throughput knobs like `device`/`batch_size`) and the
  output-defining subset (e.g. `peak_threshold`), respectively. Reflected in the regenerated
  `result_envelope.schema.json` as two **additive** optional properties.

### Changed
- `compute_idempotency_key` gains an optional `predict_output_params` argument, whose
  non-empty contents are folded into the derived key — output-defining knobs
  (`peak_threshold`) participate; hardware/throughput knobs recorded only in
  `predict_inference_config` do **not** (preserving cross-node dedup). When absent or empty,
  the derived `idempotency_key` is **byte-identical** to the pre-existing derivation, so
  previously computed keys never change. `contract_version` is producer-set and needs no
  forced bump for this additive, backward-compatible change.

### Fixed
- Corrected the `[0.1.0a0]` note below: `compute_idempotency_key` is **not** exported from the
  package root (only `compute_param_hash` and `NonCanonicalizableError` are; the idempotency
  key is derived via `Provenance`, not a public helper).

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
  `compute_param_hash` is exported from the package root along with
  `NonCanonicalizableError` (`compute_idempotency_key` is producer-internal, applied
  via `Provenance` — corrected in 0.1.0a3).
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

[Unreleased]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a5...HEAD
[0.1.0a5]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a4...v0.1.0a5
[0.1.0a4]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a3...v0.1.0a4
[0.1.0a3]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a2...v0.1.0a3
[0.1.0a2]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a1...v0.1.0a2
[0.1.0a1]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a0...v0.1.0a1
[0.1.0a0]: https://github.com/talmolab/sleap-roots-contracts/releases/tag/v0.1.0a0
