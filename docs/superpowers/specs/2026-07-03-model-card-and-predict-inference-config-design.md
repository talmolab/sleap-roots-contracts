# ModelCard + predict_inference_config — design

**Date:** 2026-07-03
**Repo:** `sleap-roots-contracts`
**Branch:** `add-model-card-predict-inference-config`
**Target release:** `0.1.0a3`
**Roadmap tier:** A3-predict (unblocks the `sleap-roots-predict` warm-model-worker slice)
**Status:** design approved in brainstorming (with two refinements folded in); pending OpenSpec proposal

## Context

`sleap-roots-predict` is building a warm, in-memory model worker (design:
`sleap-roots-predict/docs/superpowers/specs/2026-07-03-warm-model-worker-design.md`). It fetches
root models from the wandb registry and chooses them from Bloom scan metadata. That slice depends
on two additions to this contracts library, then pins to the new release:

1. **`ModelCard`** — the shared model-selection contract. `sleap-roots-training` **writes** its
   selection fields as wandb artifact metadata at promotion; `sleap-roots-predict` **reads** cards
   to choose a model per root type.
2. **`Provenance.predict_inference_config`** (+ a hashed `predict_output_params`) — predict must
   record the inference config it actually used, and the output-defining subset must participate in
   `idempotency_key`.

This library is a pure, dependency-light, Bloom-agnostic leaf (pydantic + pyyaml; no DB / network /
Argo / model code). Pydantic models are canonical; `schema/*.json` is generated from them and
drift-guarded in CI. Hashes are producer-side only; Bloom treats them as opaque.

## Goals / Non-Goals

**Goals**
- Add a frozen `ModelCard` model next to `ModelRef`, with a `to_model_ref(runtime_sleap_nn_version)`
  method that stamps the **runtime** sleap-nn version.
- Record the full effective predict inference config for audit, and fold only its **output-defining
  subset** into `idempotency_key` — hardware/throughput knobs are recorded but never hashed.
- Preserve **byte-identical backward compatibility** of `idempotency_key` for existing producers.
- Regenerate the emitted JSON Schema and keep the drift guard green; bump the package to `0.1.0a3`.

**Non-Goals**
- No matcher / selection logic, no wandb access, no registry enumeration — those live in
  `sleap-roots-predict`. This library only defines the shared shapes.
- `ModelCard` is **not** part of the Bloom-facing result envelope and is **not** emitted to
  `result_envelope.schema.json`.
- No GPU/host env fingerprint, container-digest discipline, or parity harness — those are roadmap
  items owned by the predict slice.

## Decisions

### 1. `ModelCard` (new `model-selection-contract` capability)

A frozen pydantic model in `src/sleap_roots_contracts/models.py`, next to `ModelRef`, exported from
the package root. Field names are **flat and stable** — they are the training↔predict wire contract.

```python
class ModelCard(BaseModel):
    """Model-selection metadata + identity for one production model.

    Written by sleap-roots-training at promotion (selection fields, as wandb artifact
    metadata) and read by sleap-roots-predict to choose a model per root type.

    Field sourcing (so training knows exactly what to write, and predict knows what to
    compose):
      * Selection fields — WRITTEN by training as flat wandb artifact metadata keys:
        ``species``, ``mode``, ``age_min``, ``age_max``, ``root_type`` (and optionally
        the trained-with ``sleap_nn_version``).
      * Identity fields — INTRINSIC to the wandb artifact, NOT metadata: ``registry_id``,
        ``version``, ``weights_checksum``. Predict's registry lister composes these from
        the artifact object and merges them with the metadata before validating.

    A bare ``ModelCard.model_validate(training_metadata_dict)`` therefore cannot build a
    full card (it lacks the identity fields); predict validates a MERGED dict.

    The age window is the *approved selection window* (curated at promotion — it MAY be
    wider than the raw training ages to cover the data people actually scan), assumed
    CONTIGUOUS (``[age_min, age_max]``; non-contiguous approved sets are not expressible).
    The card never sees a scan's age; running a model outside its window is handled by
    predict's explicit override, not by this contract.
    """

    model_config = _FROZEN  # frozen=True; extra defaults to "ignore" — see note below.

    # selection dimensions (training-written metadata)
    species: str
    mode: str
    age_min: int = Field(ge=0)   # approved selection window (min)
    age_max: int = Field(ge=0)   # approved selection window (max)
    root_type: RootType          # reuse existing Literal["primary","lateral","crown"]

    # identity of the concrete production artifact (artifact-intrinsic, composed by predict)
    registry_id: str
    version: str                 # concrete wandb version (alias already resolved)
    weights_checksum: str | None = None

    # trained-with sleap-nn version — OPTIONAL; used only for predict's mismatch warning
    sleap_nn_version: str | None = None

    @model_validator(mode="after")
    def _check_age_range(self) -> "ModelCard":
        if self.age_min > self.age_max:
            raise ValueError("age_min must be <= age_max")
        return self

    def to_model_ref(self, runtime_sleap_nn_version: str) -> ModelRef:
        """Build a fully-pinned ModelRef, stamping the RUNTIME sleap-nn version.

        The runtime version (what actually runs inference) is what gets pinned into
        ModelRef.sleap_nn_version, so ModelRef's required field is always satisfied
        regardless of whether the card carried a trained-with value. Predict compares
        the card's trained-with value against the runtime version and warns on mismatch;
        this method is pure and does not warn.
        """
        return ModelRef(
            registry_id=self.registry_id,
            version=self.version,
            sleap_nn_version=runtime_sleap_nn_version,
            root_type=self.root_type,
            weights_checksum=self.weights_checksum,
        )
```

**Rationale for the refinements**
- **`sleap_nn_version` optional:** making it required would force training to always write the
  sleap-nn version into metadata (it is not obviously present in the spread `training_config`); if it
  doesn't, card construction breaks. Optional means "warn if present, skip the warning if absent" —
  lower coupling, same reproducibility (the runtime version is what's pinned).
- **`extra="ignore"` (default, not `forbid`):** the real wandb metadata blob is large — boolean tag
  flags (`soybean: True`), the entire spread `training_config`, eval metrics (`oks_map`, …).
  `ModelCard.model_validate(...)` must tolerate all of it and pick out its fields. This is pinned by
  an explicit extras-tolerance test so a future well-meaning `extra="forbid"` cannot silently break
  predict's lister.

`ModelCard` is **not** referenced by `ResultEnvelope`, so it does not appear in the emitted JSON
Schema (`MODELS = {result_envelope, analysis_input}`). A test asserts `ModelCard` is absent from
`result_envelope`'s `$defs` to pin that decision.

### 2. `predict_inference_config` + `predict_output_params` (`result-contract`)

Two flat, optional dict fields on `Provenance` (a two-dict split, not a typed submodel — the knob set
grows and the contract stays Bloom-agnostic, mirroring the existing `ResolvedParams.values`
dict+canonical-hash precedent):

```python
# on Provenance:
predict_inference_config: dict[str, Any] | None = None  # FULL effective config (audit;
                                                         #   incl. device/batch_size). NOT hashed.
predict_output_params: dict[str, Any] | None = None      # output-defining subset, e.g.
                                                         #   {"peak_threshold": 0.2}. HASHED.
```

- **`predict_inference_config`** — the full effective config, recorded for audit only (never hashed).
  Includes hardware/throughput knobs (`device`, `batch_size`) and the output knobs too.
- **`predict_output_params`** — the output-defining subset that defines run identity, hashed into
  `idempotency_key`. Keeping "what was hashed" as its own explicit field makes it inspectable and
  deterministic without a consumer having to know which keys are "output-defining."

`identity.compute_idempotency_key` gains an optional keyword:

```python
def compute_idempotency_key(*, scan_key, images_checksum, models, param_hash,
                            predict_code_sha, traits_code_sha,
                            predict_output_params: dict | None = None) -> str:
    payload = { ...existing six keys... }
    if predict_output_params:                    # truthy: non-empty dict only
        payload["predict_output_params"] = predict_output_params  # canonical_json normalizes
    return sha256_hex(canonical_json(payload))
```

Because `canonical_json` sorts keys and the new key is only added when the dict is **truthy**, an
absent/empty `predict_output_params` yields a payload **byte-identical to today** — existing keys are
unchanged. `Provenance._fill_idempotency_key` passes `self.predict_output_params` through.

**Consequences (pinned by tests):**
- Two runs differing only in `peak_threshold` → **different** `idempotency_key`.
- Two runs differing only in `device`/`batch_size` (i.e. only `predict_inference_config`) → **same**
  key — cross-node idempotency dedup is preserved (a rerun on a different GPU still dedups).
- A `Provenance` built without either new field → key identical to the prior contract's.

*Hygiene note (not a contracts concern):* the contract hashes whatever is in `predict_output_params`;
it cannot stop a producer from putting `device` there. Predict is responsible for guaranteeing
`device`/`batch_size` land only in `predict_inference_config`, never in `predict_output_params`.
Noted so it is not lost when the predict slice resumes.

### 3. Versioning & schema

- `pyproject` version `0.1.0a2 → 0.1.0a3`. The schema `$id` derives from the package version and
  tracks automatically.
- Regenerate **both** emitted schemas. `schema/result_envelope.schema.json` changes shape:
  `Provenance` gains two optional properties (an **additive** change — Bloom codegen simply gains two
  optional fields, safe). `schema/analysis_input.schema.json` does not change shape, but its `$id`
  embeds the package version, so the `0.1.0a3` bump restales it too; the CI drift guard renders all
  `MODELS` together, so both committed files must be regenerated in the release commit or the guard
  goes red on `analysis_input`. (See the OpenSpec `design.md` "version / `$id` coupling" for the
  commit sequencing.)
- `contract_version` is a producer-set field value, **not** a package constant. The change is additive
  and backward-compatible, so no forced bump is required; producers may set it to the new release when
  they adopt the fields. Noted in the changelog.
- New `[0.1.0a3]` CHANGELOG entry.

## Testing strategy (real TDD — pure pydantic/schema/idempotency; no mocks)

Write failing tests first, then implement minimally.

**`ModelCard`** (`tests/test_models_basic.py` or a new `tests/test_model_card.py`)
- Minimal valid card; full card with all fields.
- `age_min > age_max` raises `ValidationError`.
- Negative age (`ge=0`) raises.
- `root_type` outside `{primary, lateral, crown}` raises.
- Frozen (assignment after construction raises).
- `to_model_ref("runtime-x")` returns a `ModelRef` whose `sleap_nn_version == "runtime-x"` (the
  RUNTIME value, **not** the card's trained-with value), carrying `registry_id`, `version`,
  `root_type`, `weights_checksum`.
- `to_model_ref` works when the card's `sleap_nn_version is None`.
- **Merged-dict round-trip:** `ModelCard.model_validate({**training_metadata, **artifact_intrinsic})`
  succeeds (honest about the two-source composition).
- **Extras-tolerance:** `model_validate({...6 real fields..., "soybean": True, "oks_map": 0.8,
  "training_config": {...}})` succeeds and ignores the extras.
- `ModelCard` absent from `result_envelope`'s emitted `$defs`.

**`compute_idempotency_key`** (`tests/test_identity.py`)
- `predict_output_params=None` ⇒ identical to the prior six-arg call (append nothing).
- `predict_output_params={}` (empty) ⇒ identical to `None` (truthy-gated).
- A populated `predict_output_params` ⇒ different key.
- Two distinct `predict_output_params` dicts ⇒ distinct keys.

**`Provenance`** (`tests/test_provenance.py`)
- Built without the new fields ⇒ `idempotency_key` equals `compute_idempotency_key(...)` with no
  output params (unchanged behavior).
- **Golden test:** a fixed `Provenance` (fixed inputs, no new fields) hashes to an exact, hardcoded
  pre-change hex digest — proves byte-identical backward compatibility, not just self-consistency.
- Populated `predict_output_params={"peak_threshold": 0.2}` ⇒ key differs from the same provenance
  without it.
- Two provenances differing **only** in `predict_inference_config` (e.g. `device`) with identical
  `predict_output_params` ⇒ **same** key.
- Two provenances differing **only** in `predict_output_params` (e.g. `peak_threshold`) ⇒ different
  keys.

**Schema** (`tests/test_schema.py`)
- Drift guard: regenerate == committed.
- An example envelope with both new fields populated validates against the emitted schema.
- The `Provenance` schema exposes the two new optional properties.

## Impact

- **Affected specs:** new `model-selection-contract` capability (ADDED: `ModelCard`); `result-contract`
  (ADDED: predict inference config recording + hashing requirement; MODIFIED: "Provenance And Run
  Identity" to include the output-params contribution to `idempotency_key`).
- **Affected code:** `src/sleap_roots_contracts/models.py` (`ModelCard`, two `Provenance` fields),
  `identity.py` (new kwarg), `__init__.py` (exports), `schema/result_envelope.schema.json` (regen,
  shape change) **and** `schema/analysis_input.schema.json` (regen, `$id`-only from the version bump),
  `pyproject.toml` (version), `docs/CHANGELOG.md`, `openspec/project.md` + `README.md` (contract
  inventory: two → three contracts).

## Consumers to keep in sync (mention in the PR; do not edit here)

- **`sleap-roots-predict`** (branch `add-warm-model-worker`) — reads `ModelCard`, returns `ModelRef`
  via `to_model_ref(runtime)`, exposes `inference_config()` → `predict_inference_config` +
  `predict_output_params`; will pin to this release. Owns `predict_output_params` hygiene.
- **`sleap-roots-training`** — writes the `ModelCard` selection fields (`species, mode, age_min,
  age_max, root_type`, optional trained-with `sleap_nn_version`) as flat wandb artifact metadata at
  promotion. Field names must match this contract exactly.

## Post-merge (required)

After merge + release: (1) the predict slice pins to `0.1.0a3` and resumes; (2) coordinate with the
predict slice (which owns the roadmap update) so the A3/A4 reproducibility notes in
`sleap-roots-pipeline/docs/bloom-integration/roadmap.md` reflect the
`predict_inference_config`/`predict_output_params` → `idempotency_key` contribution.

## Open questions / future work

- A distinct trained-age range (`trained_age_min/max`) alongside the approved selection window — nice
  for provenance, deferred (YAGNI); override + a curated window already cover the need.
- Non-contiguous approved age sets — not expressible with a single `[age_min, age_max]` window; all
  current windows are contiguous, so deferred.
