# run-manifest-contract Specification

## Purpose
TBD - created by archiving change add-run-manifest-contract. Update Purpose after archive.
## Requirements
### Requirement: Run Manifest Shape

The library SHALL define `RunManifest`, the run-scoping contract written by `bloomctl` and read by
`sleap-roots-predict`/`sleap-roots-traits`: `schema_version` (`str`, default `"1"`),
`pipeline_run_id` (`str`, required), `scan_keys` (`list[str]`, required). Every `scan_keys`
element SHALL be a string, and the list's given order SHALL be preserved (no reordering or
deduplication beyond the uniqueness check in "Scan Keys Are Non-Empty And Unique"). The model
SHALL be immutable (frozen).

#### Scenario: schema_version defaults to "1"
- **WHEN** a `RunManifest` is constructed without an explicit `schema_version`
- **THEN** its `schema_version` equals `"1"`

#### Scenario: pipeline_run_id is required
- **WHEN** a `RunManifest` is constructed without `pipeline_run_id`
- **THEN** validation raises an error

#### Scenario: scan_keys is required
- **WHEN** a `RunManifest` is constructed without `scan_keys`
- **THEN** validation raises an error

#### Scenario: Manifest is immutable
- **WHEN** a field is assigned on an existing `RunManifest` instance
- **THEN** a validation error is raised

#### Scenario: Manifest round-trips through JSON
- **WHEN** a `RunManifest` is serialized to JSON and re-parsed
- **THEN** the restored manifest equals the original

### Requirement: Scan Keys Are Non-Empty And Unique

`RunManifest.scan_keys` SHALL reject an empty list, SHALL reject a list containing duplicate
entries, and SHALL reject a list containing a blank (empty or whitespace-only) string element, all
at construction time.

#### Scenario: Empty scan_keys is rejected
- **WHEN** a `RunManifest` is constructed with `scan_keys=[]`
- **THEN** validation raises an error

#### Scenario: Duplicate scan_keys is rejected
- **WHEN** a `RunManifest` is constructed with `scan_keys=["scan_1", "scan_1"]`
- **THEN** validation raises an error

#### Scenario: Blank scan_key element is rejected
- **WHEN** a `RunManifest` is constructed with `scan_keys=["scan_1", ""]`
- **THEN** validation raises an error

#### Scenario: Whitespace-only scan_key element is rejected
- **WHEN** a `RunManifest` is constructed with `scan_keys=["scan_1", "  "]`
- **THEN** validation raises an error

#### Scenario: Non-string scan_key element is rejected
- **WHEN** a `RunManifest` is constructed with `scan_keys=[1009, 577]`
- **THEN** validation raises an error

### Requirement: Well-Known Filename Constant

The library SHALL export `RUN_MANIFEST_FILENAME`, a string constant equal to
`"run_manifest.json"`. It is the filename used when no run identity is available — outside Argo,
where `ARGO_WORKFLOW_NAME` is unset — and the legacy name that readers may still accept during a
rollout. It is no longer the only on-disk name: see "Per-Run Manifest Filename" for the per-run
form and "Manifest Resolution And Reading" for how a reader chooses between them.

#### Scenario: Filename constant has the expected literal value
- **WHEN** `sleap_roots_contracts.RUN_MANIFEST_FILENAME` is inspected
- **THEN** it equals `"run_manifest.json"`

#### Scenario: It is the name a writer uses without a run identity
- **WHEN** `run_manifest_name_for_writing(None)` is called
- **THEN** it returns `RUN_MANIFEST_FILENAME`

### Requirement: Package Export

The library SHALL export the following fourteen names from the package root and list each of
them in `__all__`:

- `RunManifest` and `RUN_MANIFEST_FILENAME` — the two pre-existing names, unchanged.
- `PIPELINE_RUN_ID_ENV_VAR`, `RunManifestError`, `RunManifestIdentityError`,
  `RunManifestMissingError`, `RunManifestRead`, `check_run_manifest_identity`,
  `pipeline_run_id_from_env`, `read_run_manifest`, `run_manifest_filename` and
  `run_manifest_name_for_writing` — the ten resolution-and-identity names this change adds.
- `LoadedRunManifest` and `load_run_manifest` — the composed entry point and its result shape
  (see "Composed Load"), which this change adds alongside those primitives.

One export requirement covers the whole capability: consumers import the run-manifest contract
from the package root, not from `sleap_roots_contracts.run_manifest`, so the root is the surface
that must be stated in one place rather than split across a per-release list.

#### Scenario: Names importable from package root
- **WHEN** a consumer does `from sleap_roots_contracts import RunManifest, RUN_MANIFEST_FILENAME`
- **THEN** the import succeeds and both names appear in `sleap_roots_contracts.__all__`

#### Scenario: The new names are importable from the package root too
- **WHEN** a consumer imports the ten resolution-and-identity names from `sleap_roots_contracts`
- **THEN** the import succeeds and each name appears in `sleap_roots_contracts.__all__`

#### Scenario: The composed entry point is importable from the package root
- **WHEN** a consumer does
  `from sleap_roots_contracts import LoadedRunManifest, load_run_manifest`
- **THEN** the import succeeds and both names appear in `sleap_roots_contracts.__all__`

### Requirement: No JSON Schema Emission

`RunManifest` SHALL NOT be emitted to `schema/*.json` — this is a producer-to-producer contract
between `bloomctl` and `sleap-roots-predict`/`sleap-roots-traits`, not a Bloom-DB-facing shape.

#### Scenario: Schema emission set is unchanged
- **WHEN** `sleap_roots_contracts.schema.MODELS` is inspected
- **THEN** it contains only `result_envelope` and `analysis_input`, with no entry for the run
  manifest

### Requirement: Per-Run Manifest Filename

The library SHALL export `run_manifest_filename(pipeline_run_id: str) -> str`, returning
`"run_manifest.<pipeline_run_id>.json"`. Because the returned value is used as a path component
and `pipeline_run_id` originates in an environment variable, the function SHALL reject any id
that is not a safe single path component: it SHALL accept only `str` ids matching
`[A-Za-z0-9][A-Za-z0-9._-]*` whose length does not exceed 237, and SHALL raise `ValueError`
otherwise.

The limit is 237 because the filename adds 18 characters and 237 + 18 is 255, the `NAME_MAX` of
the filesystems this runs on. This is below Kubernetes' own 253-character object-name limit, so a
maximally long workflow name is rejected loudly rather than producing an unwritable filename.

#### Scenario: Filename is built from the run id
- **WHEN** `run_manifest_filename("sleap-roots-pipeline-9s92h")` is called
- **THEN** it returns `"run_manifest.sleap-roots-pipeline-9s92h.json"`

#### Scenario: An id of exactly the maximum length is accepted
- **WHEN** `run_manifest_filename` is called with a 237-character id
- **THEN** it returns a 255-character filename

#### Scenario: An over-long id is rejected
- **WHEN** `run_manifest_filename` is called with a 238-character id
- **THEN** `ValueError` is raised

#### Scenario: A path separator is rejected
- **WHEN** `run_manifest_filename("../etc/passwd")` is called
- **THEN** `ValueError` is raised

#### Scenario: An empty id is rejected
- **WHEN** `run_manifest_filename("")` is called
- **THEN** `ValueError` is raised

#### Scenario: A whitespace-only id is rejected
- **WHEN** `run_manifest_filename("   ")` is called
- **THEN** `ValueError` is raised

#### Scenario: A non-string id is rejected as a ValueError
- **WHEN** `run_manifest_filename(12345)` is called
- **THEN** `ValueError` is raised, not `TypeError`

### Requirement: Run Identity Is Read From One Place

The library SHALL export `PIPELINE_RUN_ID_ENV_VAR`, equal to `"ARGO_WORKFLOW_NAME"`, and
`pipeline_run_id_from_env(env=None) -> str | None`, returning that variable's value stripped of
surrounding whitespace, or `None` when it is unset or blank. When `env` is omitted, `os.environ`
is read.

Both writers and readers SHALL derive the run identity from this function rather than reading the
environment themselves. A writer that reads it independently can differ on whitespace or on
whether a blank value counts as an identity, which would make the filename and the manifest's own
`pipeline_run_id` disagree and fail the identity cross-check on every stage.

#### Scenario: The run id is returned when set
- **WHEN** `ARGO_WORKFLOW_NAME` is `"sleap-roots-pipeline-9s92h"`
- **THEN** `pipeline_run_id_from_env()` returns `"sleap-roots-pipeline-9s92h"`

#### Scenario: An unset variable reads as no run identity
- **WHEN** `ARGO_WORKFLOW_NAME` is not present in the environment
- **THEN** `pipeline_run_id_from_env()` returns `None`

#### Scenario: A blank variable reads as no run identity
- **WHEN** `ARGO_WORKFLOW_NAME` is `"   "`
- **THEN** `pipeline_run_id_from_env()` returns `None`

#### Scenario: Surrounding whitespace is stripped
- **WHEN** `ARGO_WORKFLOW_NAME` is `" wf1\n"`
- **THEN** `pipeline_run_id_from_env()` returns `"wf1"`

#### Scenario: The variable name is exported
- **WHEN** `sleap_roots_contracts.PIPELINE_RUN_ID_ENV_VAR` is inspected
- **THEN** it equals `"ARGO_WORKFLOW_NAME"`

### Requirement: The Writer's Filename Rule

The library SHALL export `run_manifest_name_for_writing(pipeline_run_id: str | None) -> str`,
returning the per-run filename when `pipeline_run_id` is not `None`, and `RUN_MANIFEST_FILENAME`
otherwise. Keying per-run naming to the presence of a run identity is what leaves runs outside
orchestration on exactly their previous behavior.

#### Scenario: A writer with an identity uses the per-run name
- **WHEN** `run_manifest_name_for_writing("wf1")` is called
- **THEN** it returns `"run_manifest.wf1.json"`

#### Scenario: A writer without an identity uses the legacy name
- **WHEN** `run_manifest_name_for_writing(None)` is called
- **THEN** it returns `RUN_MANIFEST_FILENAME`

#### Scenario: An invalid id is rejected at the writer too
- **WHEN** `run_manifest_name_for_writing("../escape")` is called
- **THEN** `ValueError` is raised

### Requirement: Manifest Resolution And Reading

The library SHALL export `read_run_manifest(directory, pipeline_run_id, *, allow_legacy)`,
returning a `RunManifestRead` carrying the filename read, its raw bytes, the source file's
permission bits, and whether that filename was the per-run form; or `None`. `allow_legacy` SHALL
be keyword-only and SHALL have no default, so that every call site states its position and the
fleet's migration state is discoverable by search.

The candidate list SHALL depend on whether a run identity exists. When `pipeline_run_id` is not
`None`, it SHALL be the per-run filename followed by `RUN_MANIFEST_FILENAME`, the latter only
when `allow_legacy` is true. When `pipeline_run_id` is `None`, it SHALL be
`RUN_MANIFEST_FILENAME` alone, **regardless of `allow_legacy`**: with no run identity that name
is not a legacy fallback but the correct and only name, so gating it would leave no candidate at
all and silently return an unscoped result to every caller outside orchestration.

Each candidate SHALL be opened rather than tested for existence. Every error other than the
candidate being absent, notably `PermissionError`, SHALL propagate rather than advance to the
next candidate.
Returning the bytes rather than a path SHALL leave no window in which the file changes between
being found and being read. The permission bits SHALL be taken from the already-open descriptor,
not by a second lookup by name, so that they describe the bytes returned; a forwarding consumer
needs them to reproduce the source's mode for a downstream container running as another user.

Only a candidate that is *genuinely absent* SHALL advance to the next one, and that rule SHALL be
expressed as a condition on the path rather than as an exception type. `open()` raises
`FileNotFoundError` both for a candidate that does not exist and for one that exists as a
**dangling symlink** — the link is present, its target is not — so the exception alone cannot
tell the two apart. A candidate path that exists as a symlink SHALL therefore raise
`FileNotFoundError` naming that path rather than advance. A dangling link is a broken tree, not
an absent candidate, and advancing past it would hand this run an older run's scope through the
legacy name: exactly the silent foreign scope that opening rather than probing exists to prevent.

`RunManifestRead.filename` SHALL always be a bare filename — the candidate name as chosen, with
no directory component, absolute or relative. Consumers join it to a directory of their own when
they need a path, and "Run Identity Cross-Check" relies on it being the name this function chose.

If `directory` itself does not exist, the function SHALL raise `FileNotFoundError` naming the
directory, rather than reporting a missing manifest — under orchestration a mis-mounted input is
the likelier cause and the two need different responses.

When no candidate is found, the function SHALL raise `RunManifestMissingError` if
`pipeline_run_id` is not `None`, and SHALL return `None` otherwise.

The asymmetry is deliberate. A caller that knows its run id is running under orchestration, where
a manifest is always written and its absence is a fault; a caller with no run id is running
locally, where unscoped discovery is the established behavior.

#### Scenario: The per-run manifest is preferred
- **GIVEN** both `run_manifest.wf1.json` and `run_manifest.json` are present
- **WHEN** `read_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** it returns the bytes of `run_manifest.wf1.json`, with `is_per_run` true

#### Scenario: Falls back to the legacy manifest
- **GIVEN** only `run_manifest.json` is present
- **WHEN** `read_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** it returns that file's bytes, with `is_per_run` false

#### Scenario: The legacy manifest is refused when the fallback is disabled
- **GIVEN** only `run_manifest.json` is present
- **WHEN** `read_run_manifest(directory, "wf1", allow_legacy=False)` is called
- **THEN** `RunManifestMissingError` is raised

#### Scenario: Without a run identity the legacy name is used even when the fallback is disabled
- **GIVEN** only `run_manifest.json` is present
- **WHEN** `read_run_manifest(directory, None, allow_legacy=False)` is called
- **THEN** it returns that file's bytes, with `is_per_run` false

#### Scenario: Without a run identity and with nothing present the result is still not an error
- **GIVEN** neither candidate is present
- **WHEN** `read_run_manifest(directory, None, allow_legacy=False)` is called
- **THEN** it returns `None`

#### Scenario: A blank run id is invalid, not an absent identity
- **WHEN** `read_run_manifest(directory, "", allow_legacy=True)` is called
- **THEN** `ValueError` is raised, and the legacy name is not read

#### Scenario: A missing directory is reported as such
- **GIVEN** `directory` does not exist
- **WHEN** `read_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** `FileNotFoundError` naming the directory is raised, not `RunManifestMissingError`

#### Scenario: The source file's mode is returned
- **GIVEN** a readable manifest is present
- **WHEN** `read_run_manifest` reads it
- **THEN** the returned permission bits equal the source file's

#### Scenario: A known run id with no manifest is an error
- **GIVEN** neither candidate is present
- **WHEN** `read_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** `RunManifestMissingError` is raised

#### Scenario: An unknown run id with no manifest is not an error
- **GIVEN** neither candidate is present
- **WHEN** `read_run_manifest(directory, None, allow_legacy=True)` is called
- **THEN** it returns `None`

#### Scenario: An unknown run id never reads a per-run manifest
- **GIVEN** only `run_manifest.wf1.json` is present
- **WHEN** `read_run_manifest(directory, None, allow_legacy=True)` is called
- **THEN** it returns `None`

#### Scenario: An unreadable manifest raises rather than falling through
- **GIVEN** `run_manifest.wf1.json` is present but cannot be opened for permission reasons, and
  `run_manifest.json` is present and readable
- **WHEN** `read_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** `PermissionError` propagates and the legacy file is not read

#### Scenario: An invalid run id is rejected
- **WHEN** `read_run_manifest(directory, "../escape", allow_legacy=True)` is called
- **THEN** `ValueError` is raised

#### Scenario: A dangling symlink raises rather than advancing
- **GIVEN** `run_manifest.wf1.json` is a symlink whose target does not exist, and
  `run_manifest.json` is present and readable
- **WHEN** `read_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** `FileNotFoundError` naming the symlink is raised, and the legacy file is not read

#### Scenario: The filename returned is bare
- **GIVEN** a manifest is present in `directory`, which is given as an absolute path
- **WHEN** `read_run_manifest` returns a `RunManifestRead`
- **THEN** `read.filename` is a bare filename carrying no directory component

### Requirement: Run Identity Cross-Check

The library SHALL export
`check_run_manifest_identity(manifest, pipeline_run_id: str | None, read: RunManifestRead)`,
raising `RunManifestIdentityError` when `read.is_per_run` is true and
`manifest.pipeline_run_id` differs from `pipeline_run_id`, and returning `None` otherwise.

The decision SHALL be taken from `read.is_per_run` and SHALL NOT be re-derived by comparing
`read.filename` against `RUN_MANIFEST_FILENAME`. `read_run_manifest` already recorded which
candidate it opened; a second derivation would be a second source of truth, and would disagree
with the first for any caller holding something other than a bare filename. `read.filename`
SHALL be used only to name the file in the error message.

The check SHALL be a no-op when `read.is_per_run` is false, because the legacy name carries no
run identity and routinely names an earlier run; callers can therefore pass whatever
`read_run_manifest` returned without testing it themselves.

`pipeline_run_id` SHALL accept `None`, so the natural read → parse → check call chain can pass
the `str | None` identity straight through. A `None` identity SHALL be a no-op when
`read.is_per_run` is false — the only combination `read_run_manifest` can hand a caller that has
no identity, since without one the per-run filename is never a candidate.

A `None` identity with `read.is_per_run` true SHALL raise `ValueError`, and SHALL NOT raise
`RunManifestIdentityError`. Because that combination cannot arise from `read_run_manifest`, it
indicates a caller error — a hand-built or mismatched `RunManifestRead` — rather than a foreign
manifest. The error type is what carries the distinction: `RunManifestIdentityError` tells a
consumer that the tree it is reading belongs to another run and that the run should be escalated,
which is the wrong response to a bug in the calling code.

#### Scenario: A matching identity passes
- **WHEN** a manifest with `pipeline_run_id="wf1"` is checked against `"wf1"` under a read with
  `is_per_run` true and `filename="run_manifest.wf1.json"`
- **THEN** no exception is raised

#### Scenario: A foreign manifest is rejected
- **WHEN** a manifest with `pipeline_run_id="wf2"` is checked against `"wf1"` under a read with
  `is_per_run` true and `filename="run_manifest.wf1.json"`
- **THEN** `RunManifestIdentityError` is raised, and its message names both ids and the filename

#### Scenario: A read that is not the per-run form is exempt
- **WHEN** a manifest with `pipeline_run_id="some-older-run"` is checked against `"wf1"` under a
  read with `is_per_run` false
- **THEN** no exception is raised

#### Scenario: A caller with no run identity is exempt
- **WHEN** a manifest is checked with `pipeline_run_id=None` under a read with `is_per_run` false
- **THEN** no exception is raised

#### Scenario: No run identity with a per-run read is a caller error
- **WHEN** a manifest is checked with `pipeline_run_id=None` under a read with `is_per_run` true
  and `filename="run_manifest.wf1.json"`
- **THEN** `ValueError` is raised, and its message names the filename

#### Scenario: That caller error is not reported as an identity mismatch
- **WHEN** a manifest is checked with `pipeline_run_id=None` under a read with `is_per_run` true
- **THEN** the error raised is not a `RunManifestIdentityError`, and so is not a
  `RunManifestError`

### Requirement: Error Taxonomy

The library SHALL export `RunManifestError` as the common base of the run-manifest *resolution
and identity* failures — exactly `RunManifestMissingError` and `RunManifestIdentityError`.
`RunManifestMissingError` SHALL derive from both `RunManifestError` and `LookupError`.
`RunManifestIdentityError` SHALL derive from `RunManifestError` and SHALL NOT derive from
`ValueError`.

`RunManifestError` is NOT the base of every failure these functions raise. An unusable
`pipeline_run_id` SHALL raise a bare `ValueError` (see "Per-Run Manifest Filename") and a missing
`directory` SHALL raise `FileNotFoundError` (see "Manifest Resolution And Reading"); neither SHALL
derive from `RunManifestError`. A consumer that must catch everything therefore catches
`RunManifestError`, `ValueError` and `OSError`.

The exclusion is deliberate. Pydantic's `ValidationError` is a `ValueError`, and consumers wrap
manifest parsing in handlers that catch it; a manifest belonging to another run is a different
and stronger signal than a malformed one, and must not be swallowed by the same handler.

#### Scenario: Both errors share one catchable base
- **WHEN** `RunManifestMissingError` and `RunManifestIdentityError` are inspected
- **THEN** both are subclasses of `RunManifestError`

#### Scenario: A missing manifest is also a LookupError
- **WHEN** `RunManifestMissingError` is inspected
- **THEN** it is a subclass of `LookupError`

#### Scenario: An identity mismatch is not a ValueError
- **WHEN** `RunManifestIdentityError` is inspected
- **THEN** it is not a subclass of `ValueError`

#### Scenario: An invalid run id is not a RunManifestError
- **WHEN** `run_manifest_filename("../escape")` raises
- **THEN** the raised error is a `ValueError` and is not a `RunManifestError`

#### Scenario: A missing directory is not a RunManifestError
- **WHEN** `read_run_manifest` is called on a directory that does not exist
- **THEN** the raised error is a `FileNotFoundError` and is not a `RunManifestError`

### Requirement: Composed Load

The library SHALL export `load_run_manifest(directory, pipeline_run_id, *, allow_legacy) ->
LoadedRunManifest | None`, together with `LoadedRunManifest`, a named tuple of two fields:
`manifest`, the parsed `RunManifest`, and `read`, the `RunManifestRead` it was parsed from.
`allow_legacy` SHALL be keyword-only and SHALL have no default, matching `read_run_manifest`.

`load_run_manifest` SHALL perform read → parse → cross-check, in that order: `read_run_manifest`
with the same three arguments, then validation of `read.data` as a `RunManifest`, then
`check_run_manifest_identity` with the parsed manifest, the same `pipeline_run_id`, and that same
`read`. It SHALL return `None` exactly when `read_run_manifest` returns `None` — nothing found
and no run identity — and SHALL otherwise return a `LoadedRunManifest`. Every error the three
primitives raise SHALL propagate unchanged, including pydantic's `ValidationError` for a
malformed manifest and `RunManifestIdentityError` for a foreign per-run one.

`load_run_manifest` SHALL be documented as the recommended entry point for consumers. Three
primitives that four repositories must compose in the right order, where omitting the third one
fails silently rather than loudly, is precisely the divergence this capability exists to prevent.

The three primitives SHALL remain exported and supported. A forwarding stage that republishes
bytes it never parses needs `read_run_manifest` alone, and a consumer whose parsing is already
wrapped in its own error handling needs the pieces separately; the composed function is the
recommended path, not the only one. Because `LoadedRunManifest` carries both halves, a consumer
that both forwards and scopes needs only the one call: `read.data`, `read.mode` and
`read.filename` to republish, `manifest` to scope.

#### Scenario: A per-run manifest is read, parsed and cross-checked in one call
- **GIVEN** `run_manifest.wf1.json` is present and names run `"wf1"`
- **WHEN** `load_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** it returns a `LoadedRunManifest` whose `manifest.pipeline_run_id` is `"wf1"` and whose
  `read.is_per_run` is true

#### Scenario: A foreign per-run manifest raises through the composed call
- **GIVEN** `run_manifest.wf1.json` is present but names run `"wf2"`
- **WHEN** `load_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** `RunManifestIdentityError` is raised

#### Scenario: Nothing found and no run identity returns None
- **GIVEN** neither candidate is present
- **WHEN** `load_run_manifest(directory, None, allow_legacy=False)` is called
- **THEN** it returns `None`

#### Scenario: Nothing found with a run identity is an error
- **GIVEN** neither candidate is present
- **WHEN** `load_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** `RunManifestMissingError` is raised

#### Scenario: A legacy manifest naming an earlier run is loaded without a cross-check
- **GIVEN** only `run_manifest.json` is present and it names run `"some-older-run"`
- **WHEN** `load_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** it returns a `LoadedRunManifest` with `read.is_per_run` false, and no exception is
  raised

#### Scenario: A malformed manifest raises the parse error unchanged
- **GIVEN** `run_manifest.wf1.json` is present and its contents are not a valid `RunManifest`
- **WHEN** `load_run_manifest(directory, "wf1", allow_legacy=True)` is called
- **THEN** pydantic's `ValidationError` propagates

