## 1. Hashing & identity
- [ ] 1.1 `compute_param_hash` — canonical-JSON (sorted keys, fixed float repr), reject NaN/inf
- [ ] 1.2 `compute_idempotency_key` — order-independent over models, sensitive to each component

## 2. Contract models
- [ ] 2.1 `ModelRef`, `InputRef`, `ResolvedParams` (auto-computed `param_hash`)
- [ ] 2.2 `Provenance` (auto-derived `idempotency_key`)
- [ ] 2.3 `TraitValue` (NaN/inf → None) + `BlobRef` (controlled-vocab `kind`, ≥1 location)
- [ ] 2.4 `ResultEnvelope` + public package exports

## 3. Trait definitions registry
- [ ] 3.1 `TraitDefinition` + `load_registry` + `validate_trait` + seed `trait_definitions.yaml`

## 4. JSON Schema artifact
- [ ] 4.1 Schema emitter (`emit_schema`) + committed `schema/*.json`
- [ ] 4.2 Drift-guard + meta-validation + fixture tests; wire drift guard into CI

## 5. Release
- [ ] 5.1 PyPI trusted-publish workflow + build-includes-YAML check
