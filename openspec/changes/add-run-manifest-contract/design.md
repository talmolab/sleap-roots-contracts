## Context

Full cross-repo reasoning and the evidence trail (verified against live code in `bloomctl`,
`sleap-roots-predict`, `sleap-roots`-traits, and `sleap-roots-pipeline`) lives in
`docs/superpowers/specs/2026-08-03-run-manifest-contract-design.md`. This file captures the
decisions in the format this repo's other changes use.

`bloomctl`'s `scan_key_for()` (`bloomcli/src/bloomctl/cyl/download_for_predict.py`, staging
branch) converts every Bloom `scan_id` (int, DB primary key) to a string `scan_key` (e.g.
`"scan_1009"`) before it reaches the shared staging directory — the sidecar filename stem.
`sleap-roots-predict`'s `discover_scans` globs `*.scan_metadata.json` and reads only that stem; it
never sees a raw int. Every existing identifier field in this library (`Provenance.scan_key`,
`TraitValue.scan_key`, `BlobRef.scan_key`, `PredictionManifest.scan_key`) is already `str`.

## Goals / Non-Goals

- **Goals:** a minimal manifest carrying the run identity and the exact scoped `scan_key`s, file-
  based so no `sleap-roots-pipeline` template change is required to land it; a well-known filename
  constant so downstream repos import rather than hardcode it.
- **Non-Goals:** any producer/consumer code in `bloomctl`, `sleap-roots-predict`, or
  `sleap-roots`-traits; the idempotency-key comparison upgrade; any change to
  `sleap-roots-pipeline`'s Argo templates.

## Decisions

**Decision: `scan_keys: list[str]`, not `scan_ids: list[int]`.**
The issue's/Argo's own vocabulary calls these `scan_ids` (the `scan-ids` workflow parameter and
`bloomctl`'s `read_scan_ids`/`parse_scan_ids_flag` genuinely handle raw ints at that layer), but by
the time processing reaches the shared staging directory, the only identifier that exists on disk
is the string `scan_key`. Naming this field `scan_ids: list[int]` would reintroduce, at this exact
boundary, the bug bloom#555 already hit once: `build_sidecar()` wrote `image_ids` as raw ints
against a contract requiring `list[str]`, and every real sidecar failed 100% of the time until
caught. `scan_keys: list[str]` matches what predict/traits actually key off, not what Bloom's DB
happens to use internally.

**Decision: file-based, not a CLI argument.**
Confirmed both `sleap-roots-predict`'s and `sleap-roots`-traits' entrypoints use `argparse` with
exactly two required positional arguments — a third hard-fails (`unrecognized arguments`, exit 2),
it does not silently no-op. Confirmed `sleap-roots-pipeline.yaml`'s `scan-ids` parameter is wired
only to `images-downloader` today. A file in the already-shared, already-mounted staging directory
is forward-compatible today (predict/traits simply don't look for it yet) and needs zero
`sleap-roots-pipeline` template changes; a CLI-arg interface would need a coordinated, sequenced
change across three repos for no offsetting benefit at this layer.

**Decision: `run-manifest-contract` as a new sibling capability, not folded into
`prediction-manifest-contract`.**
The two contracts have opposite writer/reader directions: `PredictionManifest` is written by
predict and read by `bloomctl`; `RunManifest` is written by `bloomctl` and read by predict *and*
traits. This repo's convention is one capability per contract shape.

**Decision: `pipeline_run_id` reuses `Provenance`'s existing field name, and is required here.**
Keeps a manifest's `pipeline_run_id` directly comparable to a later
`ResultEnvelope.provenance.pipeline_run_id` for the same run, rather than adding a second
synonymous field name. It is required (unlike `Provenance.pipeline_run_id: str | None`) because a
manifest with no run identity would defeat the point of scoping. Note this is precedent, not reuse
of an established convention: `Provenance.pipeline_run_id` is `None` in every real fixture today
across predict, traits, and `bloomctl` — nothing populates it yet, and Bloom PR #570 separately
defines `cyl_pipeline_runs` with its own bigint PK, so whether `Provenance.pipeline_run_id`
ultimately holds Bloom's numeric run ID or Argo's `{{workflow.name}}`-style string is still open.
This design populates `RunManifest.pipeline_run_id` with the latter (e.g.
`"sleap-roots-pipeline-abc123xy"`) and is the first real consumer of the field name — a future
write-back implementer should treat this as the intended meaning or explicitly revisit it.

**Decision: `scan_keys` must be non-empty and free of duplicates, enforced at construction.**
An empty manifest would scope a run to nothing (silently making directory-wide-scanning look like
a safer fallback than it is); a duplicate would raise later anyway once predict's `discover_scans`
hits it. Failing at construction gives the earliest, clearest error.

**Decision: no JSON Schema emission.**
Same treatment as `PredictionManifest`/`ModelCard`: producer↔producer, never schema-validated by
anything on the Bloom-DB side. `schema.py`'s `MODELS` dict is untouched.

## Downstream testing obligation (not enforceable in this repo's CI)

bloom#555's root cause was that no test ever fed a real producer's output through a real
consumer's validator — both sides tested only hand-typed fixtures. `spec.md`'s "Package Export"
requirement guarantees `RunManifest`/`RUN_MANIFEST_FILENAME` are importable, but this repo's own
spec/tests cannot compel another repo to actually import them instead of reimplementing the shape
or hardcoding the filename — that expectation is stated here as design intent (mirroring
bloom#555's prescribed fix for `InputRef`), not as a checkable requirement, since no scenario in
this repo could verify another repo's import statements. Carried forward explicitly into the
`bloomctl` handoff and restated when predict/traits pick this up: each producer/consumer PR should
include a test that round-trips a real `RunManifest` through its own real write/read path.

## Known limitations (explicitly out of scope, not silently omitted)

Adversarial review (2026-08-04) surfaced three gaps this change deliberately does not solve. Full
reasoning in `docs/superpowers/specs/2026-08-03-run-manifest-contract-design.md` §6; summarized
here:

- **Fixed-filename overwrite race.** `RUN_MANIFEST_FILENAME` names one file at a fixed path in a
  directory that is deliberately shared across runs. Two concurrent `images-downloader` runs would
  race on it (last-writer-wins, not corruption-safe but also not isolation-safe). This design
  assumes at most one in-flight run against the shared staging directory at a time, matching
  today's operational reality (the original incidents were sequential, not concurrent). Not fixed
  here — flagged for talmolab/sleap-roots-pipeline#37.
- **`write-back` (`bloomctl cyl batch-ingest-result`) has the identical unscoped-glob
  vulnerability** as predict's pre-fix `discover_scans` and was not originally identified as a
  manifest consumer. Needs the same scoping fix in a follow-up step, not this change.
- **`bloomctl` has no `pipeline_run_id` source today** — no sidecar field or Argo env var carries
  a `{{workflow.name}}`-equivalent value into its container. The `bloomctl` implementation session
  must add that wiring; stated explicitly here so it isn't discovered mid-implementation.
