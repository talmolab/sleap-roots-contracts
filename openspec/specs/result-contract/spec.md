# result-contract Specification

## Purpose
TBD - created by archiving change add-result-provenance-contract. Update Purpose after archive.
## Requirements
### Requirement: Result Envelope Structure
The library SHALL define a `ResultEnvelope` that bundles exactly one `Provenance`, a list of
`TraitValue` rows, and a list of `BlobRef` pointers, representing one per-scan pipeline run
(one envelope : one source : one scan).

#### Scenario: Envelope round-trips through JSON
- **WHEN** a `ResultEnvelope` is serialized to JSON and re-parsed
- **THEN** the restored envelope is equal to the original, including the derived
  `idempotency_key`

### Requirement: Provenance And Run Identity

`Provenance` SHALL capture the scan identity (`scan_key`), input identity (`InputRef` with image ids
and a content checksum), the list of models used (`ModelRef` per root type), the predict and traits
stage code/container versions, the effective predict inference config and its output-defining subset,
the resolved params, and optional orchestration handles. It SHALL derive a deterministic
`idempotency_key` from the scan/input/model/param/code inputs and, when present and non-empty, from
the output-defining subset of the predict inference config (`predict_output_params`).
Hardware/throughput knobs recorded only in the effective `predict_inference_config` SHALL NOT
contribute to the key. When no output-defining subset is recorded, the derived `idempotency_key`
SHALL be byte-identical to the value derived from the same scan/input/model/param/code inputs before
this field existed, so previously computed keys never change.

#### Scenario: Identical inputs yield the same key
- **WHEN** two `Provenance` instances are built from identical inputs, models, params, and code shas
- **THEN** their `idempotency_key` values are equal

#### Scenario: A changed model yields a new key
- **WHEN** a `Provenance` is rebuilt with a different model version
- **THEN** its `idempotency_key` differs from the original

#### Scenario: Output-defining params change the key
- **WHEN** two `Provenance` instances differ only in their `predict_output_params` (e.g. a different
  `peak_threshold`)
- **THEN** their `idempotency_key` values differ

#### Scenario: Hardware knobs do not change the key
- **WHEN** two `Provenance` instances have identical `predict_output_params` but differ in their
  `predict_inference_config` (e.g. a different `device` or `batch_size`)
- **THEN** their `idempotency_key` values are equal

#### Scenario: A present-but-falsy output param still changes the key
- **WHEN** a `Provenance` records a `predict_output_params` whose only value is present but falsy
  (e.g. `{"peak_threshold": 0.0}`)
- **THEN** its `idempotency_key` differs from the same `Provenance` with no `predict_output_params`
  (a non-empty subset participates by presence, regardless of the truthiness of its values)

#### Scenario: Absent inference config preserves the prior key
- **WHEN** a `Provenance` is built without a `predict_output_params` (or with an empty one)
- **THEN** its `idempotency_key` equals the key derived from the same scan/input/model/param/code
  inputs without any inference-config contribution (byte-identical to the pre-existing derivation)

### Requirement: Producer-Side Param Hashing
The library SHALL compute `param_hash` via a canonical-JSON encoding (recursively sorted keys,
compact separators, fixed float representation) and SHALL reject non-finite (`NaN`/`inf`)
values. Hashes are produced producer-side only; consumers treat them as opaque strings. The
producer-facing helper `compute_param_hash` and its dedicated failure type
`NonCanonicalizableError` SHALL be importable from the package root.

#### Scenario: Hash is key-order independent
- **WHEN** two param dicts contain the same keys and values in different orders
- **THEN** `compute_param_hash` returns the same hash for both

#### Scenario: Non-finite values are rejected
- **WHEN** a param dict contains `NaN` or `inf`
- **THEN** `compute_param_hash` raises an error

#### Scenario: The non-finite failure type is importable and catchable
- **WHEN** a producer imports `NonCanonicalizableError` and `compute_param_hash` from the
  package root and calls the helper with a `NaN` value
- **THEN** the call raises `NonCanonicalizableError`

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
`BlobRef` SHALL identify an intermediate artifact via a controlled-vocabulary `kind` whose **only**
permitted value is `predictions_slp`. Each `BlobRef` SHALL carry a **required** `root_type` drawn
from the controlled vocabulary `{primary, lateral, crown}`, and SHALL require at least one of
`s3_location` or `box_link`. The at-least-one-location rule SHALL be encoded in the emitted JSON
Schema, derived from the model's own location field names so the model validator and the schema
constraint cannot drift apart. The narrowed `kind` vocabulary and the `root_type` vocabulary SHALL
both be reflected in the emitted JSON Schema.

#### Scenario: Only predictions_slp is an accepted kind
- **WHEN** a `BlobRef` is created with a `kind` other than `predictions_slp` (e.g. `labels`, `h5`,
  `qc_image`, or any other string)
- **THEN** validation raises an error

#### Scenario: root_type is required
- **WHEN** a `BlobRef` is created without a `root_type`
- **THEN** validation raises an error

#### Scenario: root_type is controlled
- **WHEN** a `BlobRef` is created with a `root_type` outside `{primary, lateral, crown}`
  (e.g. `seedling`)
- **THEN** validation raises an error

#### Scenario: A valid predictions blob carries a root type
- **WHEN** a `BlobRef` is created with `kind="predictions_slp"`, a `root_type` in
  `{primary, lateral, crown}`, and at least one location
- **THEN** validation succeeds and the `root_type` is retained

#### Scenario: Blob with no location is rejected
- **WHEN** a `BlobRef` is created without an `s3_location` or `box_link`
- **THEN** validation raises an error

#### Scenario: The emitted schema encodes the location constraint
- **WHEN** the JSON Schema is generated from `BlobRef`
- **THEN** it requires at least one location field, and the constrained field names are a
  subset of the model's actual fields

#### Scenario: The emitted schema reflects the narrowed kind and root_type vocabularies
- **WHEN** the JSON Schema is generated from `BlobRef`
- **THEN** the `kind` property's enum is exactly `["predictions_slp"]`, and `root_type` is a
  required property whose enum is exactly `{primary, lateral, crown}`

### Requirement: Versioned JSON Schema Artifact
The library SHALL emit a versioned JSON Schema (`schema/*.json`) generated from the Pydantic
models, with the package version carried in each schema's `$id`, and CI SHALL fail if the
committed schema differs from a fresh regeneration (drift guard).

#### Scenario: Stale committed schema fails CI
- **WHEN** the models change but `schema/*.json` is not regenerated
- **THEN** the drift-guard check fails

### Requirement: Predict Inference Config Recording

`Provenance` SHALL record the predict inference config it was run with via two optional fields: a
`predict_inference_config` mapping holding the **full effective** config for audit (including
hardware/throughput knobs such as `device` and `batch_size`), and a `predict_output_params` mapping
holding the **output-defining** subset (e.g. `peak_threshold`). Both fields SHALL default to absent,
so a `Provenance` built without them remains valid and unchanged. These two fields SHALL be reflected
in the emitted `result_envelope` JSON Schema as optional properties (an additive change).
Producers SHALL record hardware/throughput knobs (e.g. `device`, `batch_size`) only in
`predict_inference_config` and SHALL NOT place them in `predict_output_params`, so that two runs
differing only in hardware derive the same `idempotency_key`; the library records
`predict_output_params` as given and does not itself enforce this partition (it is a producer
obligation, and only the enforceable consequence — hardware not changing the key — is tested). Because
`predict_output_params` participates in the key, its values SHALL be canonicalizable (finite numbers,
strings, booleans, and nested mappings/lists thereof); a non-finite (`NaN`/`inf`) value SHALL be
rejected, consistent with `param_hash`.

#### Scenario: Effective config and output params are recorded
- **WHEN** a `Provenance` is built with a `predict_inference_config` (full effective config) and a
  `predict_output_params` (output-defining subset)
- **THEN** both mappings are retained on the instance

#### Scenario: Both fields are optional
- **WHEN** a `Provenance` is built without either field
- **THEN** construction succeeds and both fields are absent (default)

#### Scenario: The emitted schema exposes the two optional properties
- **WHEN** the `result_envelope` JSON Schema is generated
- **THEN** the `Provenance` definition exposes `predict_inference_config` and `predict_output_params`
  as optional properties, and they are absent from `Provenance`'s required list

#### Scenario: Non-canonicalizable output params are rejected
- **WHEN** a `Provenance` is built with a `predict_output_params` containing a non-finite value
  (`NaN` or `inf`)
- **THEN** construction raises an error, consistent with `param_hash`'s rejection of non-finite
  values

