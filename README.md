# sleap-roots-contracts

Shared **result + provenance contract** for the sleap-roots ↔ Bloom pipeline.

This is a small, dependency-light library — code-agnostic toward Bloom (no Bloom import, no
DB/network/filesystem I/O) — that defines the shape of a per-scan pipeline result and its
provenance (Pydantic v2 models), emits a versioned JSON Schema artifact, and ships a
trait-definitions registry. The Python producers (`sleap-roots-predict`, `sleap-roots-traits`)
import it; Bloom consumes the emitted schema.

It also defines the **analysis-input contract** — the canonical shape of the wide trait
table that crosses the `sleap-roots-analyze` ↔ Bloom boundary.
`validate_analysis_input(df, *, strict=False)` structurally validates that table against
fixed canonical role names (`genotype` + optional `sample_id` / `replicate` /
`image_path`) plus an open set of opaque numeric trait columns, returning a structured
`ValidationResult`. It operates on a pandas DataFrame, so pandas is an optional install
extra — `pip install sleap-roots-contracts[pandas]` — while the runtime core stays
pydantic + pyyaml. Canonical example tables ship in the package
(`sleap_roots_contracts.examples.load_analysis_input_example(...)`) so consumers can load a
validating frame straight from the released wheel.

It also defines the **model-selection contract** — `ModelCard`, the Python-side shape shared
by `sleap-roots-training` (which writes a production model's selection metadata as wandb
artifact metadata at promotion) and `sleap-roots-predict` (which reads cards to choose a model
per root type and calls `to_model_ref(runtime_sleap_nn_version)`). Unlike the other two, it is
a producer↔producer contract that never crosses the Bloom boundary, so it is **not** emitted to
the JSON Schema.

Since `0.1.0a5` it also defines the **prediction-manifest contract** — `PredictionArtifact`/
`PredictionManifest`, the Python-side shape of predict's per-scan `.slp` output, written by
`sleap-roots-predict` and read by `bloomctl` to construct `cyl_scan_intermediates` blob bytes.
Like `ModelCard`, it is a producer↔producer contract and is **not** emitted to the JSON Schema.

Since `0.1.0a4` it also ships the **param-resolution oracle** —
`resolve_params(metadata, overrides=None) -> ResolvedParams` maps a single Bloom
`cyl_scans_extended` scan-metadata row to the `{species, mode, age}` params that select a
`ModelCard`. It is a pure producer-side function (not emitted to the JSON Schema), and it is
the single source of truth for that mapping: its resolved values feed `param_hash` →
`idempotency_key`, so a second copy in a consumer would silently break first-writer-wins
idempotency. `sleap-roots-predict` and `bloomctl` both import it. It reads Bloom's column names
(`species_name`, `plant_age_days`) as dict keys — a deliberate, documented soft coupling,
hoisted into the module constants `SPECIES_NAME_FIELD` / `PLANT_AGE_DAYS_FIELD`.

It is sub-project #1 of the sleap-roots ↔ Bloom integration program. Design and plan:
`docs/01-contract-library-design.md` and `docs/02-contract-library-plan.md`.

## Develop

```bash
uv sync
uv run pytest -v
uv run black --check src tests && uv run ruff check src tests
```

## Key ideas

- **Pydantic is canonical**; `schema/*.json` is generated and drift-guarded in CI.
- Trait **values** are long-format rows (no jsonb); provenance is a jsonb blob on the source.
- Hashes (`param_hash`, `idempotency_key`) are **producer-side only**; Bloom treats them as
  opaque strings.
- Distributed via **PyPI** (no Docker image — this is a library).
