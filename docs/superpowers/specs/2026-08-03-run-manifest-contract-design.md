# `RunManifest` in contracts — design

**Date:** 2026-08-03
**Repo:** `sleap-roots-contracts`
**Target release:** `0.1.0a7`
**Tracking issue:** talmolab/sleap-roots-pipeline#37 (cross-repo; this is sub-project 1 of 4)
**Design doc (cross-repo reasoning):** [sleap-roots-pipeline `2026-08-03-manifest-scoped-processing-redesign.md`](https://github.com/talmolab/sleap-roots-pipeline/blob/main/docs/superpowers/specs/2026-08-03-manifest-scoped-processing-redesign.md)
**Status:** design approved in brainstorming; pending OpenSpec proposal

## Context

Two real contamination incidents happened during `sleap-roots-pipeline` PR #33's cluster
testing: (1) a leftover scan directory from one Argo run got reprocessed by a later run's
predict step, because predict discovers scans by directory-wide-scanning whatever sidecars are
present rather than consuming an explicit scoped list; (2) a stale prediction output from a
previous run blocked a corrected sidecar from propagating, because skip-if-done is a bare
`Path.exists()` check, not an idempotency-key comparison.

The originally assumed fix — per-run/per-`pipeline_run_id`-keyed storage paths — is wrong: the
cluster-side skip-if-done dedup this whole program relies on (including Bloom's own
trigger-route architecture, whose `pipeline.py` docstring states the real GPU-avoidance decision
is made cluster-side by predict's skip-if-done check) only works because paths are currently
*shared* across runs. The actual fix is **manifest-scoped processing**: producers stay
directory-shared, but each run's producers only ever touch the exact `scan_key`s that run was
told to process. Shared paths stay shared — deliberate, not a gap.

This session's job is step 1 of 4 in the dependency chain: define the manifest shape in
`sleap-roots-contracts`, following this program's established pattern for shared cross-repo
shapes (`ResultEnvelope`, `Provenance`, `ModelCard`, `ResolvedParams`, `PredictionManifest`).
It will be **written** by `bloomctl` (`salk-bloom`, staging branch) during
`batch-download-for-predict` — which already writes one `{scan_key}.scan_metadata.json` sidecar
per scan into the shared staging directory, so this is one more file alongside those, not a new
mechanism — and **read** by `sleap-roots-predict` (to scope `run_batch` instead of
directory-wide-scanning) and `sleap-roots`/`trait_extractor` (same, plus it needs to gain
skip-if-done, which it lacks entirely today).

## Goals / Non-Goals

**Goals**

- Define `RunManifest`: the run/workflow identifier a batch belongs to, plus the exact
  `scan_key`s it is scoped to process.
- Ship a well-known filename constant (`RUN_MANIFEST_FILENAME`) so bloomctl/predict/traits agree
  on the file name via import, not by each hardcoding the string.
- New capability `run-manifest-contract` (own OpenSpec capability, own module).
- No JSON Schema emission — producer↔producer, same treatment as `PredictionManifest`.
- Cut `0.1.0a7`.

**Non-Goals**

- **No bloomctl changes.** Actually writing `run_manifest.json` during `images-downloader`/
  `batch-download-for-predict` is the next session in this chain (`salk-bloom`), handed off
  separately after this ships.
- **No predict/traits changes.** Consuming the manifest to scope `run_batch`/`discover_scans`,
  and traits gaining skip-if-done, are their own sessions further down the chain.
- **No idempotency-key upgrade.** Skip-if-done moving from `Path.exists()` to a real
  `idempotency_key` comparison is tracked separately in predict/traits; this manifest only
  carries the scoping data, not the comparison logic. (`pipeline_run_id` is included now because
  it is cheap and load-bearing for scoping; a future field to aid the idempotency-key comparison
  is an open extension point, not built here.)
- **No `sleap-roots-pipeline` template changes** — a direct consequence of Decision 2 below.

## Decisions

### 1. `scan_keys: list[str]`, not `scan_ids: list[int]`

Bloom's DB uses integer `scan_id` primary keys, but `bloomctl`'s own `scan_key_for()`
(`bloomcli/src/bloomctl/cyl/download_for_predict.py`, staging branch) converts every `scan_id`
to a string `scan_key` (`f"scan_{scan_id}"`) before it ever reaches the shared staging
directory — that string is the sidecar filename stem, and it is the *only* thing
`sleap-roots-predict`'s `discover_scans` ever reads (it globs `*.scan_metadata.json` and takes
the filename stem; it never sees a raw int). Every existing identifier field in this library
(`Provenance.scan_key`, `TraitValue.scan_key`, `BlobRef.scan_key`, `PredictionManifest.scan_key`)
is already `str`.

Naming this field `scan_ids: list[int]` (matching the issue's/Argo's own vocabulary, where the
`scan-ids` workflow parameter and bloomctl's `read_scan_ids`/`parse_scan_ids_flag` genuinely
handle raw ints) would reintroduce, at this exact contract boundary, the class of bug bloom#555
already hit once: `build_sidecar()` wrote `image_ids` as raw ints straight from a DB row against
a contract (`trait_extractor.manifest.ScanMetadata`) that required `list[str]`, and every real
sidecar failed 100% of the time until the mismatch was caught. `RunManifest.scan_keys` is
`list[str]` and carries the already-converted `scan_key` values (e.g. `"scan_1009"`), matching
what predict/traits actually key off, not what Bloom's DB happens to use internally.

### 2. File-based, not a CLI argument

Confirmed directly: both `sleap-roots-predict`'s and `sleap-roots`/traits' container
entrypoints use `argparse` with exactly two required positional arguments each; argparse
hard-fails (`unrecognized arguments`, exit 2) on a third, it does not silently ignore it.
Confirmed in `sleap-roots-pipeline.yaml`: the `scan-ids` workflow parameter is wired only to
`images-downloader` today, not to predictor/trait-extractor.

A file sitting in the already-shared, already-mounted staging directory is forward-compatible
today — predict/traits simply don't look for it yet, and `sleap-roots-pipeline`'s Argo templates
need **zero** changes for this to land. A CLI-arg interface would instead require a coordinated,
sequenced change: predict's and traits' argparse signatures change first, then
`sleap-roots-pipeline` needs a follow-up PR wiring `{{workflow.parameters.scan-ids}}` into their
templates' args — extra cross-repo coordination for no offsetting benefit at this layer, since
nothing here needs CLI-time validation that a file-based read can't also provide.

### 3. New module `run_manifest.py`; new capability `run-manifest-contract`

**Module.** Not folded into `prediction_manifest.py` or `models.py`, matching this repo's
one-contract-per-module pattern (`analysis_input.py`, `params.py`, `prediction_manifest.py`).

**Capability.** A new `openspec/specs/run-manifest-contract/` capability, not folded into
`prediction-manifest-contract`. The two contracts have opposite writer/reader directions:
`PredictionManifest` is written by predict and read by `bloomctl`; `RunManifest` is written by
`bloomctl` and read by predict *and* traits. Per this program's own per-contract breakdown
(project.md lists five distinct contracts), each gets its own capability.

**Field naming.** The run/workflow identifier reuses `Provenance`'s existing field name,
`pipeline_run_id: str`, rather than inventing `run_id`/`workflow_name`. This keeps a manifest's
`pipeline_run_id` directly comparable to a later `ResultEnvelope.provenance.pipeline_run_id` for
the same run, and avoids adding a second synonymous field name to the vocabulary. Unlike
`Provenance.pipeline_run_id` (`str | None`, since it's optional there), `RunManifest.pipeline_run_id`
is **required** — a manifest with no run identity would defeat the point of scoping.

**Validation.** `scan_keys` must be non-empty and contain no duplicates. Both are cheap,
construction-time guards against the exact failure modes this manifest exists to prevent: an
empty manifest would scope a run to nothing (silently making directory-wide-scanning look like
the safer fallback), and a duplicate would raise later anyway once predict's `discover_scans`
hits it — failing here, at the earliest point, gives a clearer error.

```python
RUN_MANIFEST_FILENAME = "run_manifest.json"

class RunManifest(BaseModel):
    schema_version: str = "1"
    pipeline_run_id: str
    scan_keys: list[str]
```

Frozen, like every other contract model. Written once per batch invocation (one manifest per
`batch-download-for-predict` call), at the top level of the shared staging directory — sibling
to the per-scan `{scan_key}/` subdirectories, not nested inside one.

### 4. No JSON Schema emission

Same treatment as `PredictionManifest`/`ModelCard`: producer↔producer between `bloomctl` (Bloom
side) and predict/traits (non-Bloom repos), never schema-validated by anything on the Bloom-DB
side. `schema.py`'s `MODELS` dict stays `{"result_envelope", "analysis_input"}`, untouched by
this change.

### 5. Release

Bump `pyproject.toml` to `0.1.0a7` in this PR and re-lock `uv.lock` in the same commit (a version
bump without a re-lock hard-fails the release build, and PR CI does not catch it — see this
repo's own `0.1.0a4` release history). No `CHANGELOG.md` exists in this repo; version history
lives in PR titles by established convention.

## Testing

New `tests/test_run_manifest.py`, mirroring `test_prediction_manifest.py`'s structure:

- `schema_version` defaults to `"1"`.
- `pipeline_run_id` required (missing raises `ValidationError`).
- `scan_keys` required; empty list rejected; duplicate entries rejected (new validators, no
  existing precedent to mirror — these are the two failure modes that would let contamination
  back in).
- Frozen (mutation raises).
- Round-trips through JSON (`model_dump_json`/`model_validate_json`) and through dict
  (`model_dump`/`model_validate`).
- Package-level import (`from sleap_roots_contracts import RunManifest,
  RUN_MANIFEST_FILENAME`) and presence in `__all__`.
- Absent from `schema.py`'s `MODELS` (extends the existing
  `test_prediction_manifest_absent_from_schema_models`-style assertion).
- **Realistic fixtures, not placeholders**: `scan_keys=["scan_1009", "scan_577", "scan_289"]`
  (the exact scans from bloom#555's repro) and `pipeline_run_id="sleap-roots-pipeline-abc123xy"`
  (Argo's real `generateName` shape), so the fixture itself is an accurate reference for the
  bloomctl/predict implementers, not an abstract shape check.
- **Real-file round-trip**: write `model_dump_json()` to a `tmp_path` file and read it back with
  `Path.read_text()` + `model_validate_json()` — exercising the literal write/read boundary the
  filesystem contract actually crosses (encoding, whitespace), not just an in-memory round-trip.
- **Filename constant pinned**: `RUN_MANIFEST_FILENAME == "run_manifest.json"` asserted
  literally, so a future rename is a visible, deliberate diff here rather than a silent desync
  with repos that haven't migrated to importing the constant.

**What this repo's tests cannot cover, made an explicit obligation instead**: bloom#555's root
cause was that no test ever fed a real producer's output through a real consumer's validator —
both sides tested only hand-typed fixtures. The OpenSpec spec for this capability states
consumers MUST import `RunManifest`/`RUN_MANIFEST_FILENAME` from this package rather than
reimplementing the shape or hardcoding the filename (mirroring bloom#555's own prescribed fix
for `InputRef`). This obligation is carried forward explicitly into the `bloomctl` handoff: its
implementation PR should include a test that constructs a `RunManifest`, writes it via
bloomctl's real write path, and reads it back through `RunManifest.model_validate_json` in the
same test — proving the producer's write path produces bytes this contract's own reader accepts.
The same obligation restates when predict/traits pick this up.

Full suite via `/pre-merge-check`: `uv run pytest -v`, `uv run black --check src tests`,
`uv run ruff check src tests`, coverage, schema drift guard (expected unaffected — no schema
changes).

## Follow-ups (not this change)

- **PyPI publish** — `/prepare-release` after this PR merges.
- **`bloomctl` (`salk-bloom`, staging branch)** — write `run_manifest.json` during
  `images-downloader`/`batch-download-for-predict`, re-pin `sleap-roots-contracts>=0.1.0a7`.
  Include the producer-round-trip test described above.
- **`sleap-roots-predict`** — read the manifest, scope `run_batch` to exactly its `scan_keys`
  instead of directory-wide-scanning; separately upgrade skip-if-done to a real
  `idempotency_key` comparison.
- **`sleap-roots`/`trait_extractor`** — read the manifest; add skip-if-done (currently absent
  entirely).
- **`sleap-roots-pipeline` roadmap** — flip the contracts row from ⬜ to ✅ once this ships,
  record the version, and note the file-based (not CLI-arg) decision so the roadmap's own open
  question (§ "if contracts prefers a CLI-arg interface...") is resolved for readers.
- **talmolab/sleap-roots-pipeline#37** — comment with what shipped.
