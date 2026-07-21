## Context

Full background, alternatives considered, and rationale are captured in
`docs/superpowers/specs/2026-07-21-prediction-manifest-in-contracts-design.md` (brainstormed and
approved before this proposal was scaffolded). This file summarizes the decisions that shape the
spec deltas and tasks.

## Goals / Non-Goals

- Goals: port `PredictionArtifact`/`PredictionManifest` verbatim (all fields) plus one new
  `kind: BlobKind` field on `PredictionArtifact`; new module + new capability; no schema
  emission; version bump to `0.1.0a5` in this change.
- Non-Goals: no changes to `sleap-roots-predict` (predict#30, separate session); no writer/I-O
  helpers move; no bloomctl changes; no PyPI publish.

## Decisions

- **Straight lift, no trimming.** `Provenance` is never actually constructed anywhere in
  `sleap-roots-predict` today, so the manifest's `predict_inference_config`/
  `predict_output_params`/`predict_code_sha`/`predict_container_digest` fields are not currently
  redundant — they're predict's only on-disk provenance record. Trimming them would lose data for
  no benefit, since `bloomctl` can simply ignore fields it doesn't need.
- **New module, not `models.py`.** `prediction_manifest.py` imports `BlobKind`/`RootType`/
  `ModelRef` from `.models`. Keeps `models.py` from growing further; mirrors predict's own
  `output_contract.py` module name.
- **New capability `prediction-manifest-contract`**, separate from `result-contract` (owns
  `ResultEnvelope`/`Provenance`/`BlobRef` — what actually reaches Bloom's DB) and
  `model-selection-contract` (owns `ModelCard`). This manifest is its own producer↔producer
  contract between predict and `bloomctl`.
- **New `kind` field on `PredictionArtifact`**, defaulting to `"predictions_slp"`. Makes each
  artifact self-describing, reuses `BlobKind` rather than redefining the vocabulary, and is
  additive (default value) so it doesn't break predict's existing construction call sites once
  predict#30 imports from here.
- **No JSON Schema emission.** Same treatment as `ModelCard`: both ends of this contract
  (predict, `bloomctl`) are Python and already depend on this package directly, so nothing needs
  a standalone JSON Schema document. What actually reaches Bloom's DB is the `BlobRef` that
  `bloomctl` derives from the manifest — and `BlobRef`'s schema (nested in `ResultEnvelope`) is
  already emitted and unaffected by this change.
- **Version bump lands in this PR** (`0.1.0a5`), matching both prior promotion precedents (PR #10
  → `0.1.0a3`, PR #16 → `0.1.0a4`). `uv.lock` must be re-locked in the same commit — a known gotcha
  where a version bump without a re-lock hard-fails the release build without PR CI catching it.
- **Config mirrors predict's `_FROZEN`, including `protected_namespaces=()`.**
  `PredictionArtifact.model_id`/`.model` are protected-namespace-shaped fields; predict's own
  `output_contract.py` already disables the guard for exactly this reason. Verified empirically:
  silent under the currently-locked pydantic 2.13.4, but reproducibly emits a `UserWarning` on
  class definition under the declared floor `pydantic>=2.7` (tested against 2.7.4) without it.

## Risks / Trade-offs

- **Schema drift between contracts and predict's local copy** until predict#30 lands and predict
  actually switches its import. Mitigated by scope: this change doesn't touch predict, and
  predict#30 is already tracked as an explicit, imminent follow-on (not indefinitely deferred).
- **New `kind` field is a widening, not a narrowing**, so it can't break predict's existing
  manifest JSON on disk from prior runs — old JSON without a `kind` key still validates via the
  default.
- **No structural duplicate-`root_type` guard on `PredictionManifest.artifacts`.** Predict's
  writer can't produce duplicates today (it iterates a `dict[str, ...]` keyed by root type), but
  a manifest built directly from the promoted models (e.g. by `bloomctl`, or by hand in a test)
  has no such guarantee. Accepted as consistent with "straight lift, no new validation" — not
  fixed here.
- **No format validation on `scan_key`/`slp_path` outside predict's writer.** Predict's
  `_validate_scan_key` (path-separator/control-char rejection) stays in predict per the I/O
  boundary decision, so a `PredictionManifest` constructed directly via the promoted models
  inherits no path-safety guarantee — that guarantee currently exists only in predict's writer
  function.
- **Version bump forces a schema `$id` restamp**, even though `MODELS` gains no entries: bumping
  `pyproject.toml` changes `__version__`, which is embedded in both existing schemas' `$id`.
  `schema/*.json` must be regenerated and committed in this same change or CI's drift guard
  fails — this is the same `$id`-only restamp the `0.1.0a4` promotion already went through.
- **No cross-validation between `PredictionArtifact.root_type` (strict `RootType` literal) and
  `PredictionArtifact.model.root_type` (loose `str | None` on `ModelRef`)** — the two can
  silently disagree. Not a new gap: predict's current `output_contract.py` has the identical
  shape with the identical absence of cross-validation, so a straight lift necessarily preserves
  it. Adding a validator here would diverge from predict's actual behavior today (breaking
  round-trip parity for predict#30's eventual migration) and isn't required by "straight lift, no
  new validation." Accepted as-is, same reasoning as the duplicate-`root_type`-in-`artifacts` risk
  above.
- **`predict_inference_config`/`predict_output_params` silently lose `NaN`/`inf` values on JSON
  dump** (pydantic-core's default `ser_json_inf_nan="null"` — a non-finite float round-trips as
  `None`, indistinguishable from an absent value). Not a new gap: `Provenance`'s identical fields
  (added in `0.1.0a3`) have the exact same behavior — neither is hashed or canonicalized (only
  `ResolvedParams.values` goes through `hashing.py`'s NaN/inf-rejecting canonicalization, because
  it feeds `param_hash`). Consistent with existing precedent in this codebase; not addressed here.

## Migration Plan

Not applicable — this is a net-new module/capability with no existing consumers of the promoted
shape inside this repo. Downstream migration (predict#30, then bloom's `add-cyl-blob-upload`) is
tracked as follow-up work outside this change.

## Open Questions

None — all five design decisions were resolved during brainstorming before this proposal was
scaffolded (see the linked design doc).
