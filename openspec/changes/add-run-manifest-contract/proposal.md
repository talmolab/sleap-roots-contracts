## Why

Two real contamination incidents happened during `sleap-roots-pipeline` PR #33's cluster testing:
(1) a leftover scan directory from one Argo run got reprocessed by a later run's predict step,
because predict discovers scans by directory-wide-scanning whatever sidecars are present rather
than consuming an explicit scoped list; (2) a stale prediction output from a previous run blocked
a corrected sidecar from propagating, because skip-if-done is a bare `Path.exists()` check, not an
idempotency-key comparison.

The originally assumed fix — per-run/per-`pipeline_run_id`-keyed storage paths — is wrong: the
cluster-side skip-if-done dedup this whole program relies on (including Bloom's own trigger-route
architecture, whose `pipeline.py` docstring states the real GPU-avoidance decision is made
cluster-side by predict's skip-if-done check) only works because paths are currently *shared*
across runs. Isolating them would silently break that dedup and the A4 "batch oracle" acceptance
test (re-running an already-done batch must schedule 0 GPU pods, all scans reused).

The actual fix is **manifest-scoped processing**: producers stay directory-shared, but each run's
producers only ever touch the exact scans that run was told to process. This is step 1 of 4 in
that fix (tracked cross-repo at talmolab/sleap-roots-pipeline#37): define the manifest shape here,
following this program's established pattern for shared cross-repo shapes (`ResultEnvelope`,
`Provenance`, `ModelCard`, `ResolvedParams`, `PredictionManifest`).

## What Changes

- Add a **`run-manifest-contract`** capability defining `RunManifest` — an immutable (`frozen`)
  Pydantic model carrying `schema_version` (`str`, default `"1"`), `pipeline_run_id` (`str`,
  required), and `scan_keys` (`list[str]`, required, non-empty, no duplicates).
- Ship `RUN_MANIFEST_FILENAME = "run_manifest.json"` as the single source of truth for the
  manifest's on-disk filename, so `bloomctl`/`sleap-roots-predict`/`sleap-roots`-traits agree on
  it via import rather than each hardcoding the string.
- `scan_keys` is deliberately `list[str]`, not `list[int]`: Bloom's DB uses integer `scan_id`
  primary keys, but `bloomctl` converts every `scan_id` to a string `scan_key` (e.g.
  `"scan_1009"`) before it reaches the shared staging directory, and that string is the *only*
  thing `sleap-roots-predict`'s `discover_scans` ever reads. Naming this field to match the raw DB
  type would reintroduce, at this exact contract boundary, the class of bug bloom#555 already hit
  once (an `image_ids` int/str mismatch that failed every real sidecar).
- `RunManifest` is **file-based**, not a CLI argument: both `sleap-roots-predict`'s and
  `sleap-roots`-traits' entrypoints use `argparse` with exactly two required positional arguments,
  which hard-fails on a third; a file in the already-shared, already-mounted staging directory
  needs zero `sleap-roots-pipeline` template changes to land.
- `RunManifest` is **producer↔producer** — like `PredictionManifest`/`ModelCard`, it never crosses
  the Bloom-DB boundary and is **not** emitted to JSON Schema.

Not in scope: `bloomctl` actually writing the manifest, `sleap-roots-predict`/`sleap-roots`-traits
actually reading it or gaining skip-if-done, and the idempotency-key comparison upgrade — all
tracked separately as the next three steps in talmolab/sleap-roots-pipeline#37.

Three additional gaps are deliberately deferred, not silently missed (full reasoning in design.md,
"Known limitations"), and not yet tracked anywhere until this change's follow-up comment lands:

- `write-back`'s `discover_envelopes()` has the identical unscoped-glob vulnerability predict's
  `discover_scans` had. It is a 4th consumer this manifest should eventually scope, not previously
  identified as one.
- This design assumes at most one in-flight pipeline run against the shared staging directory at a
  time. A concurrent-run race on the fixed manifest filename is a known, accepted limitation, not
  solved here.
- `bloomctl` has no existing source for `pipeline_run_id` today (no sidecar field, no Argo env
  var) — the `bloomctl` implementation session must add that wiring.

## Impact

- Affected specs: `run-manifest-contract` (new capability). No change to any existing capability.
- Affected code: new `src/sleap_roots_contracts/run_manifest.py`,
  `src/sleap_roots_contracts/__init__.py` (export `RunManifest`, `RUN_MANIFEST_FILENAME`), new
  `tests/test_run_manifest.py`, `openspec/project.md`, `docs/CHANGELOG.md`, `README.md`,
  `docs/01-contract-library-design.md`, `pyproject.toml` + `uv.lock` (version bump), `schema/*.json`
  (regenerated for the `$id` version restamp; no structural diff expected).
- Release: cuts the next contracts alpha (`0.1.0a7`). Consumed next by `bloomctl` (`salk-bloom`,
  staging branch), then `sleap-roots-predict`, then `sleap-roots`-traits — each a separate,
  sequenced session per talmolab/sleap-roots-pipeline#37.
- Runtime deps unchanged (pydantic only; no filesystem/network I/O in this library).
