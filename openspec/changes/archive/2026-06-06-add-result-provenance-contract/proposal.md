## Why

The sleap-roots ↔ Bloom integration needs a single source of truth for the shape of a
per-scan pipeline result and its provenance, so the Python producers (`sleap-roots-predict`,
`sleap-roots-traits`) and the Bloom (TypeScript/Postgres) consumer never drift, and so every
trait value is traceable to the exact run, model(s), params, inputs, and code that produced it.

## What Changes

- Add Pydantic v2 models: `ResultEnvelope`, `Provenance`, `InputRef`, `ModelRef`,
  `ResolvedParams`, `TraitValue`, `BlobRef`.
- Add **producer-side** canonical-JSON param hashing and deterministic idempotency-key
  derivation (Bloom treats both as opaque).
- Add a trait-definitions registry (name / unit / dtype / range), seeded from sleap-roots'
  trait set, with warn-on-unknown validation.
- Emit a **versioned JSON Schema artifact** (`schema/*.json`) with a CI drift guard.
- Publish the library to PyPI (no Docker image — it is a leaf library).

## Impact

- Affected specs: `result-contract` (new capability).
- Affected code: new repo `talmolab/sleap-roots-contracts` —
  `src/sleap_roots_contracts/*`, `schema/*`, CI + publish workflows.
- Downstream consumers: `sleap-roots-predict`, `sleap-roots-traits` (import); Bloom (#2)
  consumes the emitted schema. No DB/network/Argo/model code lives here.
