# Design Notes

Full brainstorming design:
`docs/superpowers/specs/2026-07-03-model-card-and-predict-inference-config-design.md`. This file
records the technical decisions that shape the specs and the commit sequencing.

## Decision: `predict_inference_config` is two flat dicts, not a typed submodel

The contract's real concern is **hash-participation**, not knob typing, and the library is
Bloom-agnostic. Layer 1 (`make_predictor`) exposes only `peak_threshold` (output-defining) plus
`batch_size`/`device` (hardware) today; `max_instances`/`input_scale`/integral-refinement are named
in the predict design but not yet exposed. Enumerating knobs as typed fields would bake
predict-specific names into this library and make every new knob a contract change + schema regen.

**Chosen:** two flat, optional `dict[str, Any] | None` fields on `Provenance`, mirroring the existing
`ResolvedParams.values` dict + canonical-hash precedent:

- `predict_inference_config` — the **full effective** config, recorded for audit (includes hardware
  knobs). Never hashed.
- `predict_output_params` — the **output-defining subset** that defines run identity. Hashed.

Keeping the hashed subset as its own explicit field makes "what was hashed" inspectable and
deterministic without a consumer having to know which keys are output-defining. Adding a new output
knob later is just another key in that dict — no contract change, no schema edit.

*Hygiene (predict's job, not the contract's):* the contract hashes whatever is in
`predict_output_params`; it cannot stop a producer from putting `device` there. Predict guarantees
`device`/`batch_size` land only in `predict_inference_config`.

## Decision: byte-identical backward compatibility of `idempotency_key`

`compute_idempotency_key` gains `predict_output_params: dict | None = None`. The new payload key is
added **only when the dict is truthy** (non-empty). Because `canonical_json` sorts keys, an
absent/empty value yields a payload string **byte-identical** to today's — so every existing producer
that does not record output params gets the exact same key it got before.

This is pinned two ways in tests: (1) a self-consistency test that `predict_output_params=None`
equals the prior six-arg call; and (2) a **golden test** that a fixed `Provenance` (built without the
new fields) hashes to an exact hardcoded hex digest captured from pre-change behavior. The golden
digest is what proves byte-identity rather than mere internal consistency.

## Decision: `ModelCard.sleap_nn_version` is optional; identity fields are artifact-intrinsic

`ModelCard` fields come from **two sources**:

- **Selection fields**, written by training as flat wandb artifact **metadata** keys: `species`,
  `mode`, `age_min`, `age_max`, `root_type` (and optionally trained-with `sleap_nn_version`).
- **Identity fields**, **intrinsic to the wandb artifact object** (not metadata): `registry_id`,
  `version`, `weights_checksum`. Predict's registry lister composes these from the artifact and
  merges them with the metadata before validating.

So a bare `ModelCard.model_validate(training_metadata_dict)` cannot build a full card — the round-trip
test validates a **merged** dict.

`sleap_nn_version` (trained-with) is **optional** (`str | None = None`): requiring it would force
training to always write the sleap-nn version into metadata (not obviously present in the spread
`training_config`); if it were missing, card construction would break. `to_model_ref` stamps the
**runtime** version into `ModelRef.sleap_nn_version`, so `ModelRef`'s required field is always
satisfied regardless of the card. The card's trained-with value is used only for predict's mismatch
warning (present → warn on mismatch; absent → skip). `to_model_ref` itself is pure and does not warn.

**`extra="ignore"` (pydantic v2 default, not `forbid`):** the real wandb metadata blob is large —
boolean tag flags (`soybean: True`), the entire spread `training_config`, eval metrics (`oks_map`).
`ModelCard.model_validate(...)` must tolerate all of it. An explicit extras-tolerance test pins this
so a future well-meaning `extra="forbid"` cannot silently break predict's lister.

## Decision: age window semantics + validation

`age_min`/`age_max` is the **approved selection window**, curated at promotion — it MAY be set wider
than the raw training ages to cover the data people actually scan. It is assumed **contiguous**
(`[age_min, age_max]`; non-contiguous approved sets are not expressible). The contract validates only
**well-formedness** (`age_min <= age_max`, `ge=0`); it never sees a scan's age. Running a model
outside its window is accommodated entirely by predict's explicit override, so the well-formedness
check does not conflict with out-of-range use. A distinct raw trained-age range is a future addition
(YAGNI now).

## Decision: `ModelCard` is not emitted to JSON Schema

The emitter renders only `MODELS = {result_envelope, analysis_input}`. `ModelCard` is not referenced
by `ResultEnvelope`, so it does not appear in any emitted schema — matching its role as a Python-side
producer↔producer contract (training writer ↔ predict reader), not a Bloom-facing shape. A test
asserts `ModelCard` is absent from `result_envelope`'s `$defs` to pin this. By contrast,
`predict_inference_config`/`predict_output_params` hang off `Provenance` → `ResultEnvelope`, so they
DO appear (two new optional properties — an additive, safe change for Bloom codegen).

## The version / `$id` coupling (the version bump restales BOTH schemas)

`schema.py` builds every schema's `$id` from `__version__` and drift-guards committed bytes against a
fresh `render()` over **all** `MODELS`. Advancing to `0.1.0a3` changes the `$id` line of **both**
committed schemas, even though only `result_envelope` changes shape. Regenerate both at once with
`python -m sleap_roots_contracts.schema` after `uv sync`; a partial regen turns the drift guard RED
on `analysis_input`. Versioning is single-source (`pyproject.toml:version`); `__init__.__version__`
resolves from metadata, and `test_schema_id_carries_package_version` already asserts the `$id`/version
linkage — no new `$id` test needed.

## Commit grouping (tasks.md is an implementation sequence, not a commit sequence)

The RED-first sub-steps in `tasks.md` are TDD *working-tree* order; a committed bare RED step is red
CI. The drift guard forces two atomic commit units, each green on its own:

- **Unit A — the contract change, still at `v0.1.0a2`:** `models.py` (`ModelCard`, two `Provenance`
  fields), `identity.py` (new kwarg), `__init__.py` (export `ModelCard`), `tests/*`, and the
  regenerated `result_envelope.schema.json` (`$id` still `v0.1.0a2`; content gains the two optional
  `Provenance` properties). `analysis_input.schema.json` is untouched and still matches. Green.
- **Unit B — the release bump:** `pyproject.toml:version` → `0.1.0a3`, `uv sync`, **both** regenerated
  schemas (`$id` → `v0.1.0a3`), and the `docs/CHANGELOG.md` entry. Green only if both schemas are
  regenerated together.

Single PR; proposal/spec committed first; archive only after merge.
