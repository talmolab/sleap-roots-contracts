## ADDED Requirements

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

Each candidate SHALL be opened rather than tested for existence. Only `FileNotFoundError` SHALL
advance to the next candidate; every other error, notably `PermissionError`, SHALL propagate.
Returning the bytes rather than a path SHALL leave no window in which the file changes between
being found and being read. The permission bits SHALL be taken from the already-open descriptor,
not by a second lookup by name, so that they describe the bytes returned; a forwarding consumer
needs them to reproduce the source's mode for a downstream container running as another user.

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

### Requirement: Run Identity Cross-Check

The library SHALL export `check_run_manifest_identity(manifest, pipeline_run_id, filename)`,
raising `RunManifestIdentityError` when `filename` is not `RUN_MANIFEST_FILENAME` and
`manifest.pipeline_run_id` differs from `pipeline_run_id`, and returning `None` otherwise. It
SHALL be a no-op when `filename` is `RUN_MANIFEST_FILENAME`, because the legacy name carries no
run identity and routinely names an earlier run; callers can therefore pass whatever
`read_run_manifest` returned without testing the name themselves.

#### Scenario: A matching identity passes
- **WHEN** a manifest with `pipeline_run_id="wf1"` is checked against `"wf1"` under
  `run_manifest.wf1.json`
- **THEN** no exception is raised

#### Scenario: A foreign manifest is rejected
- **WHEN** a manifest with `pipeline_run_id="wf2"` is checked against `"wf1"` under
  `run_manifest.wf1.json`
- **THEN** `RunManifestIdentityError` is raised, and its message names both ids and the filename

#### Scenario: The legacy filename is exempt
- **WHEN** a manifest with `pipeline_run_id="some-older-run"` is checked against `"wf1"` under
  `RUN_MANIFEST_FILENAME`
- **THEN** no exception is raised

### Requirement: Error Taxonomy

The library SHALL export `RunManifestError` as the common base of every run-manifest failure it
raises. `RunManifestMissingError` SHALL derive from both `RunManifestError` and `LookupError`.
`RunManifestIdentityError` SHALL derive from `RunManifestError` and SHALL NOT derive from
`ValueError`.

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

### Requirement: New Names Are Exported From The Package Root

The library SHALL export `run_manifest_filename`, `pipeline_run_id_from_env`,
`PIPELINE_RUN_ID_ENV_VAR`, `run_manifest_name_for_writing`, `read_run_manifest`,
`RunManifestRead`, `check_run_manifest_identity`, `RunManifestError`,
`RunManifestMissingError` and `RunManifestIdentityError` from the package root, and list them in
`__all__`.

#### Scenario: Names importable from the package root
- **WHEN** a consumer imports all ten names from `sleap_roots_contracts`
- **THEN** the import succeeds and each name appears in `sleap_roots_contracts.__all__`

## MODIFIED Requirements

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
