# Add a per-run run-manifest filename and its resolution policy

## Why

`bloomctl`'s `write_run_manifest` unions `scan_keys` into a single shared `run_manifest.json`
and never prunes, and `sleap-roots-pipeline#37` established that `out_dir` is permanently shared
across all runs by design (isolating it breaks the skip-if-done the batch oracle depends on). So
every run operates on the union of all runs. Measured four times on 2026-09-21 on current pins: a
1-scan request carried a 12-key manifest and write-back delivered all 12, creating
`cyl_trait_sources` rows for eleven unrequested scans.

Fix shape (a) from talmolab/sleap-roots-pipeline#71: give the manifest a per-run *identity*
while artifacts stay shared, so dedup keeps working. That needs a filename convention, and it
needs one shared definition of how a reader resolves and falls back — three consumers
(`bloomctl`, `sleap-roots-predict`, `sleap-roots`) must agree exactly or the rollout skews.

## What Changes

- **ADDED** `run_manifest_filename(pipeline_run_id)` — the per-run filename, with validation that
  the id is safe to use as a path component.
- **ADDED** `pipeline_run_id_from_env()` — one definition of "which run am I", read from
  `ARGO_WORKFLOW_NAME`.
- **ADDED** `resolve_run_manifest_name(pipeline_run_id, exists)` — the resolution policy: per-run
  name, then the legacy name, then raise if the run id is known and neither is present, else
  `None`. Pure: the caller supplies `exists`, so the library keeps doing no filesystem I/O.
- **ADDED** `check_run_manifest_identity(...)` — the cross-check that a per-run-named manifest
  names the run reading it. This is bloom#703's cross-check, possible for the first time.
- **ADDED** `RunManifestMissingError`, `RunManifestIdentityError`.

`RUN_MANIFEST_FILENAME` and `RunManifest` are unchanged. This release is additive; 0.1.0a8
consumers are unaffected until they adopt the new names.

## Impact

- Affected specs: `run-manifest-contract`
- Affected code: `src/sleap_roots_contracts/run_manifest.py`, `__init__.py`
- Downstream (separate changes, not this one): `salk-bloom` bloomctl writer + ingest reader,
  `sleap-roots-predict`, `sleap-roots` traits, then template pin bumps in `sleap-roots-pipeline`.
