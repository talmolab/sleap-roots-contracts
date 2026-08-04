## ADDED Requirements

### Requirement: Run Manifest Shape

The library SHALL define `RunManifest`, the run-scoping contract written by `bloomctl` and read by
`sleap-roots-predict`/`sleap-roots`-traits: `schema_version` (`str`, default `"1"`),
`pipeline_run_id` (`str`, required), `scan_keys` (`list[str]`, required). The model SHALL be
immutable (frozen).

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

`RunManifest.scan_keys` SHALL reject an empty list and SHALL reject a list containing duplicate
entries, both at construction time.

#### Scenario: Empty scan_keys is rejected
- **WHEN** a `RunManifest` is constructed with `scan_keys=[]`
- **THEN** validation raises an error

#### Scenario: Duplicate scan_keys is rejected
- **WHEN** a `RunManifest` is constructed with `scan_keys=["scan_1", "scan_1"]`
- **THEN** validation raises an error

### Requirement: Well-Known Filename Constant

The library SHALL export `RUN_MANIFEST_FILENAME`, a string constant equal to `"run_manifest.json"`,
as the single source of truth for the manifest's on-disk filename.

#### Scenario: Filename constant has the expected literal value
- **WHEN** `sleap_roots_contracts.RUN_MANIFEST_FILENAME` is inspected
- **THEN** it equals `"run_manifest.json"`

### Requirement: Package Export

The library SHALL export `RunManifest` and `RUN_MANIFEST_FILENAME` from the package root.

#### Scenario: Names importable from package root
- **WHEN** a consumer does `from sleap_roots_contracts import RunManifest, RUN_MANIFEST_FILENAME`
- **THEN** the import succeeds and both names appear in `sleap_roots_contracts.__all__`

### Requirement: No JSON Schema Emission

`RunManifest` SHALL NOT be emitted to `schema/*.json` — this is a producer-to-producer contract
between `bloomctl` and `sleap-roots-predict`/`sleap-roots`-traits, not a Bloom-DB-facing shape.

#### Scenario: Schema emission set is unchanged
- **WHEN** `sleap_roots_contracts.schema.MODELS` is inspected
- **THEN** it contains only `result_envelope` and `analysis_input`, with no entry for the run
  manifest
