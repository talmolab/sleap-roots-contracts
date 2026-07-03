## ADDED Requirements

### Requirement: Predict Inference Config Recording

`Provenance` SHALL record the predict inference config it was run with via two optional fields: a
`predict_inference_config` mapping holding the **full effective** config for audit (including
hardware/throughput knobs such as `device` and `batch_size`), and a `predict_output_params` mapping
holding the **output-defining** subset (e.g. `peak_threshold`). Both fields SHALL default to absent,
so a `Provenance` built without them remains valid and unchanged. These two fields SHALL be reflected
in the emitted `result_envelope` JSON Schema as optional properties (an additive change).
Hardware/throughput knobs (e.g. `device`, `batch_size`) SHALL be recorded only in
`predict_inference_config` and SHALL NOT appear in `predict_output_params`, so that two runs
differing only in hardware derive the same `idempotency_key`. Because `predict_output_params`
participates in the key, its values SHALL be canonicalizable (finite numbers, strings, booleans, and
nested mappings/lists thereof); a non-finite (`NaN`/`inf`) value SHALL be rejected, consistent with
`param_hash`.

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

## MODIFIED Requirements

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

#### Scenario: Absent inference config preserves the prior key
- **WHEN** a `Provenance` is built without a `predict_output_params` (or with an empty one)
- **THEN** its `idempotency_key` equals the key derived from the same scan/input/model/param/code
  inputs without any inference-config contribution (byte-identical to the pre-existing derivation)
