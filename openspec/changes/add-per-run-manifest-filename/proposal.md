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
needs one shared definition of how a reader resolves, falls back, and fails — three consumers
(`bloomctl`, `sleap-roots-predict`, `sleap-roots`) must agree exactly or the rollout skews.

## What Changes

- **ADDED** `run_manifest_filename(pipeline_run_id)` — the per-run filename, validating that the
  id is safe as a path component and short enough that the filename fits in `NAME_MAX`.
- **ADDED** `PIPELINE_RUN_ID_ENV_VAR` and `pipeline_run_id_from_env(env=None)` — one definition
  of "which run am I". Writers and readers must both use it; a writer that reads the environment
  itself can disagree about whitespace and make the identity cross-check fail on every stage.
- **ADDED** `run_manifest_name_for_writing(pipeline_run_id)` — the writer's rule: per-run name
  when an identity is known, legacy name otherwise.
- **ADDED** `read_run_manifest(directory, pipeline_run_id, *, allow_legacy)` and
  `RunManifestRead` — the resolution policy, performed by *opening* each candidate rather than
  probing, so an unreadable manifest cannot be mistaken for an absent one. Returns the bytes,
  the name they came from, and whether that name was the per-run form.
- **ADDED** `check_run_manifest_identity(...)` — the cross-check that a per-run-named manifest
  names the run reading it; a no-op for the legacy name. This is bloom#703's cross-check,
  possible for the first time.
- **ADDED** `RunManifestMissingError`, `RunManifestIdentityError`.
- **MODIFIED** the `Well-Known Filename Constant` requirement — `RUN_MANIFEST_FILENAME` keeps its
  exact value, but it is no longer the only on-disk name, so describing it as "the single source
  of truth for the manifest's on-disk filename" would become false.

`RunManifest` is unchanged. This release is additive in behavior; 0.1.0a8 consumers are
unaffected until they adopt the new names.

## Impact

- Affected specs: `run-manifest-contract`
- Affected code: `src/sleap_roots_contracts/run_manifest.py`, `__init__.py`
- Affected docs: `README.md`, `openspec/project.md`, `docs/CHANGELOG.md`. Two claims in
  `project.md` are corrected in passing — both predate this change and were verified false during
  review: that the library does no filesystem I/O (`schema.py:93-98`'s `emit_schema` writes
  files), and that `sleap-roots-predict`/`sleap-roots`-traits have not yet landed their consuming
  PRs (both have read the manifest since `0.1.0a7`).
- Downstream (separate changes, not this one): `salk-bloom` bloomctl writer + ingest reader,
  `sleap-roots-predict`, `sleap-roots` traits, then template pin bumps in `sleap-roots-pipeline`.
