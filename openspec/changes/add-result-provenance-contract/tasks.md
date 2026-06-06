## 1. Hashing & identity
- [x] 1.1 `compute_param_hash` — canonical-JSON (sorted keys, fixed float repr), reject NaN/inf
- [x] 1.2 `compute_idempotency_key` — order-independent over models, sensitive to each component

## 2. Contract models
- [x] 2.1 `ModelRef`, `InputRef`, `ResolvedParams` (auto-computed `param_hash`)
- [x] 2.2 `Provenance` (auto-derived `idempotency_key`)
- [x] 2.3 `TraitValue` (NaN/inf → None) + `BlobRef` (controlled-vocab `kind`, ≥1 location)
- [x] 2.4 `ResultEnvelope` + public package exports
- [x] 2.5 Export producer-side `compute_param_hash` + `NonCanonicalizableError` from the root
- [x] 2.6 Derive `BlobRef`'s at-least-one-location schema constraint from its field names (single
  source of truth) + drift-guard test

## 3. Trait definitions registry
- [x] 3.1 `TraitDefinition` + `load_registry` + `validate_trait` + seed `trait_definitions.yaml`

## 4. JSON Schema artifact
- [x] 4.1 Schema emitter (`emit_schema`) + committed `schema/*.json`
- [x] 4.2 Drift-guard + meta-validation + fixture tests; wire drift guard into CI

## 5. Release
- [x] 5.1 PyPI trusted-publish workflow + build-includes-YAML check
