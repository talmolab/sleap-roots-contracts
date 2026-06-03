## ADDED Requirements

### Requirement: Result Envelope Structure
The library SHALL define a `ResultEnvelope` that bundles exactly one `Provenance`, a list of
`TraitValue` rows, and a list of `BlobRef` pointers, representing one per-scan pipeline run
(one envelope : one source : one scan).

#### Scenario: Envelope round-trips through JSON
- **WHEN** a `ResultEnvelope` is serialized to JSON and re-parsed
- **THEN** the restored envelope is equal to the original, including the derived
  `idempotency_key`

### Requirement: Provenance And Run Identity
`Provenance` SHALL capture the scan identity (`scan_key`), input identity (`InputRef` with
image ids and a content checksum), the list of models used (`ModelRef` per root type), the
predict and traits stage code/container versions, the resolved params, and optional
orchestration handles. It SHALL derive a deterministic `idempotency_key` from those inputs.

#### Scenario: Identical inputs yield the same key
- **WHEN** two `Provenance` instances are built from identical inputs, models, params, and code shas
- **THEN** their `idempotency_key` values are equal

#### Scenario: A changed model yields a new key
- **WHEN** a `Provenance` is rebuilt with a different model version
- **THEN** its `idempotency_key` differs from the original

### Requirement: Producer-Side Param Hashing
The library SHALL compute `param_hash` via a canonical-JSON encoding (recursively sorted keys,
compact separators, fixed float representation) and SHALL reject non-finite (`NaN`/`inf`)
values. Hashes are produced producer-side only; consumers treat them as opaque strings.

#### Scenario: Hash is key-order independent
- **WHEN** two param dicts contain the same keys and values in different orders
- **THEN** `compute_param_hash` returns the same hash for both

#### Scenario: Non-finite values are rejected
- **WHEN** a param dict contains `NaN` or `inf`
- **THEN** `compute_param_hash` raises an error

### Requirement: Trait Value Representation
`TraitValue` SHALL represent one long-format trait row (`name`, `value`, `grain`, `scan_key`)
where `value` is a float or `None`, and non-finite values (`NaN`/`inf`) SHALL normalize to
`None` so they serialize to SQL `NULL`.

#### Scenario: NaN normalizes to None
- **WHEN** a `TraitValue` is created with a `NaN` value
- **THEN** its `value` is `None`

### Requirement: Trait Definitions Registry
The library SHALL ship a trait-definitions registry (`name`, `unit`, `dtype`, `description`,
optional `min`/`max`) and SHALL validate a trait value against it, raising on out-of-range
values and warning (default) or erroring (when strict) on unknown trait names.

#### Scenario: Out-of-range value is rejected
- **WHEN** a value below a definition's `min` is validated
- **THEN** validation raises an error

#### Scenario: Unknown trait warns by default
- **WHEN** a trait name absent from the registry is validated with default settings
- **THEN** a warning is emitted and validation does not raise

### Requirement: Blob References
`BlobRef` SHALL identify an intermediate artifact with a controlled-vocabulary `kind` and
SHALL require at least one of `s3_location` or `box_link`.

#### Scenario: Blob with no location is rejected
- **WHEN** a `BlobRef` is created without an `s3_location` or `box_link`
- **THEN** validation raises an error

### Requirement: Versioned JSON Schema Artifact
The library SHALL emit a versioned JSON Schema (`schema/*.json`) generated from the Pydantic
models, with the package version carried in each schema's `$id`, and CI SHALL fail if the
committed schema differs from a fresh regeneration (drift guard).

#### Scenario: Stale committed schema fails CI
- **WHEN** the models change but `schema/*.json` is not regenerated
- **THEN** the drift-guard check fails
