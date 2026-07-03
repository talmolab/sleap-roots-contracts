## Why

`sleap-roots-predict` is building a warm, in-memory model worker (design:
`sleap-roots-predict/docs/superpowers/specs/2026-07-03-warm-model-worker-design.md`, roadmap tier
A3-predict). It fetches root models from the wandb registry, chooses one per root type from Bloom
scan metadata, and keeps them resident across scans. That slice is **blocked** on two additions to
this contracts library, after which it pins to the new release:

1. There is no shared **model-selection contract**. `sleap-roots-training` writes selection metadata
   at promotion and `sleap-roots-predict` reads it to choose models, but they have no agreed shape to
   coordinate on. Predict's pure matcher needs `list[ModelCard] -> dict[RootType, ModelRef]`.
2. `Provenance` cannot record the **inference config predict actually used**. Reproducibility
   requires that the output-defining knobs (e.g. `peak_threshold`) participate in `idempotency_key`,
   while hardware/throughput knobs (`device`, `batch_size`) are recorded but **not** hashed — hashing
   them would break cross-node idempotency dedup (a rerun on a different GPU must still dedup).

Full design + decisions:
`docs/superpowers/specs/2026-07-03-model-card-and-predict-inference-config-design.md`.

## What Changes

- Add a frozen **`ModelCard`** model (new `model-selection-contract` capability) next to `ModelRef`,
  exported from the package root:
  - Selection fields (training-written wandb metadata): `species`, `mode`, an inclusive approved
    selection window `age_min`/`age_max` (`ge=0`, `age_min <= age_max`), and `root_type: RootType`.
  - Identity fields (artifact-intrinsic, composed by predict's lister): `registry_id`, `version`,
    optional `weights_checksum`.
  - Optional trained-with `sleap_nn_version` (used only for predict's mismatch warning).
  - `to_model_ref(runtime_sleap_nn_version) -> ModelRef` stamps the **runtime** sleap-nn version.
  - `ModelCard` is a Python-side producer contract; it is **not** referenced by `ResultEnvelope` and
    is **not** emitted to the JSON Schema.
- Add two optional dict fields to **`Provenance`** (`result-contract`):
  - `predict_inference_config: dict | None` — the full effective config, recorded for audit
    (includes hardware knobs); **not** hashed.
  - `predict_output_params: dict | None` — the output-defining subset; **hashed** into
    `idempotency_key`.
- Extend `compute_idempotency_key` with an optional `predict_output_params` kwarg that contributes to
  the key **only when populated**. When absent/empty, the derived key is **byte-identical** to the
  prior contract's, so existing keys never silently change.
- Regenerate `schema/result_envelope.schema.json` (additive: `Provenance` gains two optional
  properties). `ModelCard` does not enter any emitted schema.
- Release **`v0.1.0a3`**: bump `pyproject.toml` version (single source of truth), regenerate **both**
  schemas (each `$id` embeds the version), update `docs/CHANGELOG.md`.

## Impact

- **Affected specs:**
  - `model-selection-contract` (NEW capability) — ADDED: `ModelCard` shape/validation,
    card→`ModelRef` conversion, tolerant construction from registry metadata.
  - `result-contract` — ADDED: predict inference config recording; MODIFIED: **Provenance And Run
    Identity** (folds the output-defining subset into `idempotency_key`; hardware knobs excluded;
    backward compatibility preserved).
- **Affected code:**
  - `src/sleap_roots_contracts/models.py` — add `ModelCard` (+ `Field` import); add
    `Provenance.predict_inference_config` and `predict_output_params`; pass the output params into the
    `idempotency_key` derivation.
  - `src/sleap_roots_contracts/identity.py` — add the optional `predict_output_params` kwarg,
    truthy-gated so an absent/empty value appends nothing.
  - `src/sleap_roots_contracts/__init__.py` — export `ModelCard`.
  - `schema/result_envelope.schema.json` **and** `schema/analysis_input.schema.json` — both
    regenerated (the model change touches only `result_envelope`, but the version bump restales both
    `$id`s; CI drift-guards all `MODELS` together).
  - `pyproject.toml` — `version` → `0.1.0a3` (single source; `__version__` resolves from metadata).
  - `tests/` — new `ModelCard`, idempotency, `Provenance`, and schema tests (real TDD, no mocks);
    the shared `example_envelope` fixture is untouched (both new fields default to `None`, so the
    existing envelope stays valid).
  - `docs/CHANGELOG.md` — `0.1.0a3` entry (`### Added` + a short `### Changed` note for the
    `compute_idempotency_key` signature/behavior extension) + footer compare-link refresh.
  - `openspec/project.md` — Purpose updated from "**two** contracts" to **three** (name the
    model-selection contract); add `sleap-roots-training` to consumers as the ModelCard writer.
  - `README.md` — name the model-selection contract / `ModelCard` alongside the existing contracts.
- **`contract_version`** is a producer-set field value, not a package constant. This change is
  additive and backward-compatible, so no forced bump; producers may set it to `0.1.0a3` when they
  adopt the new fields.
- **Consumers to keep in sync (not edited here):**
  - `sleap-roots-predict` (branch `add-warm-model-worker`) — reads `ModelCard`, returns `ModelRef`
    via `to_model_ref(runtime)`, exposes `inference_config()` → the two new fields; pins to this
    release. Owns `predict_output_params` hygiene (keep `device`/`batch_size` out of it).
  - `sleap-roots-training` — writes the `ModelCard` selection fields (`species, mode, age_min,
    age_max, root_type`, optional trained-with `sleap_nn_version`) as flat wandb artifact metadata at
    promotion; field names must match this contract exactly.
- **Not modified here:** the A3/A4 reproducibility notes in
  `sleap-roots-pipeline/docs/bloom-integration/roadmap.md` are updated post-merge by the predict
  slice (which owns the roadmap), to reflect the `predict_output_params` → `idempotency_key`
  contribution. **This session does not modify the predict, training, or pipeline repos.**
