# Changelog

All notable changes to `sleap-roots-contracts` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
(with PEP 440 pre-release suffixes).

## [Unreleased]

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

[Unreleased]: https://github.com/talmolab/sleap-roots-contracts/compare/v0.1.0a0...HEAD
[0.1.0a0]: https://github.com/talmolab/sleap-roots-contracts/releases/tag/v0.1.0a0
