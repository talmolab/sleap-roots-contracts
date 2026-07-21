## ADDED Requirements

### Requirement: Prediction Artifact Shape

The library SHALL define `PredictionArtifact`, describing one predicted root type's `.slp`
output: `kind` (`BlobKind`, defaults to `"predictions_slp"`), `root_type` (`RootType`), `model_id`
(`str`), `model` (`ModelRef`), `slp_path` (`str`), `checksum` (`str`), `file_size` (`int`). The
model SHALL be immutable (frozen).

#### Scenario: Kind defaults to predictions_slp
- **WHEN** a `PredictionArtifact` is constructed without an explicit `kind`
- **THEN** its `kind` equals `"predictions_slp"`

#### Scenario: Artifact is immutable
- **WHEN** a field is assigned on an existing `PredictionArtifact` instance
- **THEN** a validation error is raised

#### Scenario: An unrecognized kind is rejected
- **WHEN** a `PredictionArtifact` is constructed with a `kind` outside the current `BlobKind`
  vocabulary
- **THEN** validation raises an error

#### Scenario: An unrecognized root_type is rejected
- **WHEN** a `PredictionArtifact` is constructed with a `root_type` outside `{primary, lateral,
  crown}`
- **THEN** validation raises an error

### Requirement: Prediction Manifest Shape

The library SHALL define `PredictionManifest`, the per-scan output contract: `schema_version`
(`str`, default `"1"`), `scan_key` (`str`), `plant_qr_code` (`str`, defaults to `scan_key` when
unset), `artifacts` (`list[PredictionArtifact]`, default empty), `predict_inference_config`
(`dict`, default empty), `predict_output_params` (`dict`, default empty), `predict_code_sha`
(`str`, default `""`), `predict_container_digest` (`str`, default `""`). The model SHALL be
immutable (frozen).

#### Scenario: plant_qr_code defaults to scan_key
- **WHEN** a `PredictionManifest` is constructed without `plant_qr_code`
- **THEN** `plant_qr_code` equals `scan_key`

#### Scenario: Manifest round-trips through JSON
- **WHEN** a `PredictionManifest` with artifacts is serialized to JSON and re-parsed
- **THEN** the restored manifest equals the original

#### Scenario: Empty defaults for a scan with no resolved roots
- **WHEN** a `PredictionManifest` is constructed with only `scan_key`
- **THEN** `artifacts` is an empty list and `predict_inference_config`/`predict_output_params`
  are empty dicts

#### Scenario: Manifest is immutable
- **WHEN** a field is assigned on an existing `PredictionManifest` instance
- **THEN** a validation error is raised

### Requirement: Package Export

The library SHALL export `PredictionArtifact` and `PredictionManifest` from the package root.

#### Scenario: Models importable from package root
- **WHEN** a consumer does `from sleap_roots_contracts import PredictionArtifact,
  PredictionManifest`
- **THEN** the import succeeds and both names appear in `sleap_roots_contracts.__all__`

### Requirement: No JSON Schema Emission

`PredictionManifest` and `PredictionArtifact` SHALL NOT be emitted to `schema/*.json` — this is a
producer-to-producer contract between `sleap-roots-predict` and `bloomctl`, not a Bloom-DB-facing
shape.

#### Scenario: Schema emission set is unchanged
- **WHEN** `sleap_roots_contracts.schema.MODELS` is inspected
- **THEN** it contains only `result_envelope` and `analysis_input`, with no entry for the
  prediction manifest
