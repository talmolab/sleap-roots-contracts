# `PredictionArtifact`/`PredictionManifest` in contracts — design

**Date:** 2026-07-21
**Repo:** `sleap-roots-contracts`
**Target release:** `0.1.0a5`
**Issue:** talmolab/sleap-roots-contracts#22
**Companion issue (separate, later session):** talmolab/sleap-roots-predict#30
**Status:** design approved in brainstorming; pending OpenSpec proposal

## Context

`sleap-roots-predict` defines `PredictionArtifact`/`PredictionManifest` locally in
`sleap_roots_predict/output_contract.py` (predict PR #16, `a252cdc`): the per-scan on-disk
contract — one named `.slp` per predicted root type plus a combined
`{scan_key}.predictions.json` manifest. The module's own docstring already anticipated this
move: "the schema is predict-local for now... it is promoted to the shared contract once [a
later stage] consumes it."

That consumer has arrived, but it isn't the traits stage — it's `bloomctl`. Bloom issue #407
(`bloomctl cyl ingest-result`) needs to read the manifest to construct + upload
`cyl_scan_intermediates` blob bytes. A `salk-bloom` OpenSpec proposal
(`add-cyl-blob-upload`) scaffolded this, but adversarial review found it assumed `bloomctl`
could import `PredictionArtifact`/`PredictionManifest` straight from `sleap-roots-predict` —
which isn't published to PyPI, and a sibling bloom change already rejected taking it as a
bloomcli dependency for exactly that reason.

`sleap-roots-contracts` is already a real `bloomctl` dependency and already hosts the model
this data feeds (`BlobRef`), so it's the right home. There's exact precedent for this shape of
promotion: `resolve_params` originated in predict (predict PR #18) and was promoted here in
PR #16 (`cfe6a2c`, `0.1.0a4`), after which predict dropped its local copy (predict#28/#29).
This is the same move, one level over.

## Goals / Non-Goals

**Goals**

- Port `PredictionArtifact`/`PredictionManifest` into contracts with all fields intact (no
  trimming) plus one new field: `PredictionArtifact.kind: BlobKind = "predictions_slp"`.
- Expose both as `from sleap_roots_contracts import PredictionArtifact, PredictionManifest`.
- Reuse the existing `BlobKind`/`RootType`/`ModelRef` vocabulary already in `models.py` — no
  redefinition.
- New capability `prediction-manifest-contract`, mirroring `model-selection-contract`'s
  producer↔producer treatment (no JSON Schema emission).
- Cut `0.1.0a5` so `bloomctl`/`add-cyl-blob-upload` can re-pin once this session's PR merges.

**Non-Goals**

- **No changes to `sleap-roots-predict`.** Predict keeps defining its own
  `PredictionArtifact`/`PredictionManifest` locally in this change; swapping predict to import
  from contracts and delete its local copy is predict#30, a separate follow-on session (mirrors
  how predict#28/#29 followed contracts#16 — not the same PR).
- **No writer/I-O helpers.** `write_prediction_outputs`, `predict_and_write_batch`,
  `slugify_model_id`, `_validate_scan_key`, `_resolve_identity`, and the `ScanRequest` dataclass
  all stay in predict. Only the two frozen Pydantic model classes move — this library stays free
  of filesystem/hashing/naming logic.
- **No JSON Schema emission** for the new models (see Decision 3).
- **No PyPI publish and no bloomctl changes** in this session — those are explicit follow-ups.

## Decisions

### 1. Straight lift, not a trimmed subset

The issue's acceptance criteria don't mandate a 1:1 port, and `bloomctl` only strictly needs
`kind`/`root_type`/`scan_key`/`checksum`/`file_size`/`slp_path`. The temptation was to trim
`model_id`/`model`/`predict_inference_config`/`predict_output_params`/`predict_code_sha`/
`predict_container_digest` since those look redundant with `Provenance`.

They are not redundant today: **`Provenance` is never actually constructed anywhere in
`sleap-roots-predict`** (verified — no traits-stage/Bloom-writer code exists yet). The
manifest's provenance fields are currently the *only* on-disk record of that data. Trimming them
would remove predict's only current audit trail for zero benefit (bloomctl simply ignores fields
it doesn't need). So: straight lift, all fields, no change in predict's on-disk behavior once
predict#30 swaps the import.

### 2. New module `prediction_manifest.py`; new capability `prediction-manifest-contract`

**Module.** Not folded into `models.py`. `models.py` already hosts `ModelCard` — also a
producer↔producer contract — which sets one precedent for co-location, but this repo's broader
pattern is one distinct contract per module (`analysis_input.py`, `params.py`). Given
`PredictionManifest` is a sizeable, self-contained shape (two classes, several fields, its own
validator), a dedicated module keeps `models.py` from growing further and mirrors predict's own
`output_contract.py` naming. Imports `BlobKind`, `RootType`, `ModelRef` from `.models`.

**Capability.** A new `openspec/specs/prediction-manifest-contract/` capability, not folded
into `result-contract` (which owns `ResultEnvelope`/`Provenance`/`BlobRef` — the shape that
actually crosses into Bloom's DB) or `model-selection-contract` (which owns `ModelCard`'s
selection shape). `PredictionManifest` is its own producer↔producer contract between predict
and `bloomctl`.

**New field.** `PredictionArtifact` gains `kind: BlobKind = "predictions_slp"`. It has no
`kind` field today because predict only ever produces one artifact kind; adding it explicitly
makes each artifact self-describing, reuses `BlobKind` rather than redefining the vocabulary,
and future-proofs the manifest if predict ever emits a second kind (e.g. the deferred
`viewer_html`) without a breaking schema change. `bloomctl` can then read `artifact.kind`
directly when constructing a `BlobRef` instead of hardcoding the literal. The default value
means predict's existing (unexported) construction call sites don't need any change to satisfy
the new field once predict#30 imports from here.

### 3. No JSON Schema emission

`schema.py`'s `MODELS` dict lists only `result_envelope` and `analysis_input` —
`ModelCard` is deliberately absent (confirmed by reading `schema.py`), matching
`project.md`'s statement that contract (3) is "producer↔producer... not emitted to JSON
Schema."

`PredictionManifest` is the same shape as `ModelCard`, not `ResultEnvelope`: predict writes it
(Python), `bloomctl` reads it directly (also Python, and already a real dependency on this
package) — no non-Python tool anywhere needs `PredictionManifest`'s shape as a standalone JSON
document. Even though `bloomctl` genuinely uploads data derived from the manifest to Bloom, what
lands in Bloom's DB is the resulting `BlobRef` row (`cyl_scan_intermediates`), and `BlobRef`'s
schema story is already covered — it's nested inside `ResultEnvelope`, which is already emitted.
The manifest JSON itself is never schema-validated by anything on the Bloom side. So:
`schema.py`'s `MODELS` dict is untouched by this change.

### 4. Release: version bump lands in this PR, matching precedent

Both prior promotions bumped `pyproject.toml`'s version inside the feature PR itself (PR #10 →
`0.1.0a3`, PR #16 → `0.1.0a4`); the actual PyPI publish via `/prepare-release` is a separate
later step. This change follows the same pattern: bump to `0.1.0a5` and **re-lock `uv.lock` in
the same commit** (a version bump without it hard-fails the release build, and PR CI does not
catch it — a known gotcha from the `0.1.0a4` release).

There is no `CHANGELOG.md` in this repo (checked — none exists), so there's nothing to update
there; version history lives in PR titles by established convention.

## Testing

New `tests/test_prediction_manifest.py`, adapting the pure-model assertions from predict's
`tests/test_output_contract.py` (`test_manifest_round_trips`,
`test_plant_qr_code_defaults_to_scan_key`) — the only two of predict's 26 tests in that file
that don't require the real warm-worker/filesystem writer infrastructure. Plus new
contracts-side coverage:

- JSON round-trip equality (ported).
- `plant_qr_code` defaults to `scan_key` when unset (ported).
- `PredictionArtifact.kind` defaults to `"predictions_slp"` when unset.
- Both models are frozen (mutation raises).
- `PredictionManifest.artifacts` defaults to `[]`; `predict_inference_config`/
  `predict_output_params` default to `{}`.
- Package-level import: `from sleap_roots_contracts import PredictionArtifact,
  PredictionManifest` and presence in `__all__`.

Full suite via `/pre-merge-check`: `uv run pytest -v`, `uv run black --check src tests`,
`uv run ruff check src tests`, coverage, schema drift guard (expected unaffected since no
schema changes).

## Follow-ups (not this change)

- **PyPI publish** — `/prepare-release` after this PR merges.
- **predict#30** — re-pin `sleap-roots-contracts>=0.1.0a5`, import
  `PredictionArtifact`/`PredictionManifest` from contracts, delete predict's local definitions
  in `output_contract.py`, update predict's own tests. Mirrors predict PR #29 (predict#28's
  resolution).
- **`salk-bloom` `add-cyl-blob-upload`** (branch `eberrigan/cyl-blob-upload`) — bump bloomcli's
  `sleap-roots-contracts` floor, rewrite `tasks.md` section 2 to import the promoted model
  instead of the superseded `sleap_roots_predict.output_contract` reference, resume the normal
  approval flow.
- **`sleap-roots-pipeline` roadmap** — optionally note that this prerequisite surfaced and was
  filed as contracts#22/predict#30, blocking the A4 write-back row's blob-upload sub-item (use
  judgment; may already be covered generically by the #407 reference).
