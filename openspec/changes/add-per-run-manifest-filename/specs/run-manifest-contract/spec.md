## ADDED Requirements

### Requirement: Per-Run Manifest Filename

The library SHALL export `run_manifest_filename(pipeline_run_id: str) -> str`, returning
`"run_manifest.<pipeline_run_id>.json"`. Because the returned value is used as a path component
and `pipeline_run_id` originates in an environment variable, the function SHALL reject any id
that is not a safe single path component: it SHALL accept only ids matching
`[A-Za-z0-9][A-Za-z0-9._-]*` with length at most 200, and SHALL raise `ValueError` otherwise.

#### Scenario: Filename is built from the run id
- **WHEN** `run_manifest_filename("sleap-roots-pipeline-9s92h")` is called
- **THEN** it returns `"run_manifest.sleap-roots-pipeline-9s92h.json"`

#### Scenario: A path separator is rejected
- **WHEN** `run_manifest_filename("../etc/passwd")` is called
- **THEN** `ValueError` is raised

#### Scenario: An empty or blank id is rejected
- **WHEN** `run_manifest_filename("")` or `run_manifest_filename("   ")` is called
- **THEN** `ValueError` is raised

#### Scenario: An over-long id is rejected
- **WHEN** `run_manifest_filename("a" * 201)` is called
- **THEN** `ValueError` is raised

### Requirement: Run Identity Is Read From One Place

The library SHALL export `pipeline_run_id_from_env(env=None) -> str | None`, returning the value
of `ARGO_WORKFLOW_NAME` when it is set and not blank, and `None` otherwise. Leading and trailing
whitespace SHALL be stripped. When `env` is omitted, `os.environ` is read.

#### Scenario: The run id is returned when set
- **WHEN** `ARGO_WORKFLOW_NAME` is `"sleap-roots-pipeline-9s92h"`
- **THEN** `pipeline_run_id_from_env()` returns `"sleap-roots-pipeline-9s92h"`

#### Scenario: An unset variable reads as no run identity
- **WHEN** `ARGO_WORKFLOW_NAME` is not present in the environment
- **THEN** `pipeline_run_id_from_env()` returns `None`

#### Scenario: A blank variable reads as no run identity
- **WHEN** `ARGO_WORKFLOW_NAME` is `"   "`
- **THEN** `pipeline_run_id_from_env()` returns `None`

### Requirement: Manifest Resolution Policy

The library SHALL export `resolve_run_manifest_name(pipeline_run_id, exists) -> str | None`,
where `exists` is a callable taking a filename and returning whether it is present. The library
SHALL perform no filesystem access itself. Resolution order SHALL be: the per-run filename when
`pipeline_run_id` is not `None`; then `RUN_MANIFEST_FILENAME`. When neither is present, the
function SHALL raise `RunManifestMissingError` if `pipeline_run_id` is not `None`, and SHALL
return `None` otherwise.

The asymmetry is deliberate. A caller that knows its run id is running under orchestration, where
a missing manifest is a fault; a caller with no run id is running locally, where unscoped
discovery is the established behavior.

#### Scenario: The per-run manifest is preferred
- **GIVEN** both `run_manifest.wf1.json` and `run_manifest.json` exist
- **WHEN** `resolve_run_manifest_name("wf1", exists)` is called
- **THEN** it returns `"run_manifest.wf1.json"`

#### Scenario: Falls back to the legacy name
- **GIVEN** only `run_manifest.json` exists
- **WHEN** `resolve_run_manifest_name("wf1", exists)` is called
- **THEN** it returns `"run_manifest.json"`

#### Scenario: A known run id with no manifest is an error
- **GIVEN** neither file exists
- **WHEN** `resolve_run_manifest_name("wf1", exists)` is called
- **THEN** `RunManifestMissingError` is raised

#### Scenario: An unknown run id with no manifest is not an error
- **GIVEN** neither file exists
- **WHEN** `resolve_run_manifest_name(None, exists)` is called
- **THEN** it returns `None`

#### Scenario: An unknown run id never looks for a per-run name
- **GIVEN** only `run_manifest.wf1.json` exists
- **WHEN** `resolve_run_manifest_name(None, exists)` is called
- **THEN** it returns `None`

### Requirement: Run Identity Cross-Check

The library SHALL export `check_run_manifest_identity(manifest, pipeline_run_id, filename)`,
raising `RunManifestIdentityError` when `manifest.pipeline_run_id` differs from `pipeline_run_id`,
and returning `None` otherwise. Consumers call it only for a manifest read under a per-run
filename, where the two are required to agree.

#### Scenario: A matching identity passes
- **WHEN** a manifest with `pipeline_run_id="wf1"` is checked against `"wf1"`
- **THEN** no exception is raised

#### Scenario: A foreign manifest is rejected
- **WHEN** a manifest with `pipeline_run_id="wf2"` is checked against `"wf1"`
- **THEN** `RunManifestIdentityError` is raised, and its message names both ids and the filename

### Requirement: New Names Are Exported From The Package Root

The library SHALL export `run_manifest_filename`, `pipeline_run_id_from_env`,
`resolve_run_manifest_name`, `check_run_manifest_identity`, `RunManifestMissingError` and
`RunManifestIdentityError` from the package root, and list them in `__all__`.

#### Scenario: Names importable from the package root
- **WHEN** a consumer imports all six names from `sleap_roots_contracts`
- **THEN** the import succeeds and each name appears in `sleap_roots_contracts.__all__`
