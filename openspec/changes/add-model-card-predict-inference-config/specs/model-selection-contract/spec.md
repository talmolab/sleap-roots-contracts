## ADDED Requirements

### Requirement: Model Selection Card

The library SHALL define an immutable (`frozen`) `ModelCard` model that carries a production model's
selection metadata and the identity of its concrete registry artifact, importable from the package
root. Its selection fields SHALL be `species` (str), `mode` (str), an inclusive approved selection
window `age_min`/`age_max` (ints, each `>= 0`, with `age_min <= age_max`), and `root_type` drawn from
the controlled vocabulary `RootType = {primary, lateral, crown}`. Its identity fields SHALL be
`registry_id` (str), `version` (str), and an optional `weights_checksum`. The card SHALL also carry an
optional trained-with `sleap_nn_version`. The age window represents the model's curated approved
selection range (which MAY be wider than its training ages) and is assumed contiguous; the card never
observes a scan's age. `ModelCard` is a Python-side producer contract and SHALL NOT appear in the
emitted JSON Schema.

#### Scenario: A valid card is constructed
- **WHEN** a `ModelCard` is built with valid selection fields (`age_min <= age_max`, `root_type` in
  the vocabulary) and identity fields (`registry_id`, `version`)
- **THEN** construction succeeds and the field values are retained

#### Scenario: Age window well-formedness is enforced
- **WHEN** a `ModelCard` is built with `age_min` greater than `age_max`
- **THEN** validation raises an error

#### Scenario: Negative ages are rejected
- **WHEN** a `ModelCard` is built with a negative `age_min` or `age_max`
- **THEN** validation raises an error

#### Scenario: root_type is controlled
- **WHEN** a `ModelCard` is built with a `root_type` outside `{primary, lateral, crown}`
- **THEN** validation raises an error

#### Scenario: The trained-with version is optional
- **WHEN** a `ModelCard` is built without a `sleap_nn_version`
- **THEN** construction succeeds and `sleap_nn_version` is `None`

#### Scenario: The card is immutable
- **WHEN** a field on a constructed `ModelCard` is reassigned
- **THEN** the assignment raises an error

#### Scenario: ModelCard is absent from the emitted result schema
- **WHEN** the `result_envelope` JSON Schema is generated
- **THEN** `ModelCard` is not present among its `$defs`

### Requirement: Model Card To ModelRef Conversion

`ModelCard` SHALL provide `to_model_ref(runtime_sleap_nn_version)` returning a `ModelRef` that pins
the card's `registry_id`, `version`, `root_type`, and `weights_checksum`, and stamps
`ModelRef.sleap_nn_version` with the **runtime** sleap-nn version passed in (not the card's
trained-with value). The method SHALL be pure and SHALL NOT emit warnings; comparing the runtime
version against the card's trained-with value is the reader's responsibility.

#### Scenario: to_model_ref stamps the runtime sleap-nn version
- **WHEN** `to_model_ref("runtime-x")` is called on a card whose trained-with `sleap_nn_version`
  differs from `"runtime-x"` (or is `None`)
- **THEN** the returned `ModelRef` has `sleap_nn_version == "runtime-x"` and carries the card's
  `registry_id`, `version`, `root_type`, and `weights_checksum`

### Requirement: Tolerant Construction From Registry Metadata

`ModelCard` SHALL validate successfully from a mapping that merges training-written selection metadata
with the artifact-intrinsic identity fields, and SHALL ignore extra keys not defined on the model, so
that a card can be built from a raw wandb metadata blob (boolean tag flags, spread training config,
eval metrics) merged with the artifact's identity without those extras causing failure.

#### Scenario: A card built from merged metadata and identity validates
- **WHEN** `ModelCard.model_validate(mapping)` is called where `mapping` merges the selection metadata
  (`species`, `mode`, `age_min`, `age_max`, `root_type`) with the artifact identity (`registry_id`,
  `version`)
- **THEN** validation succeeds and yields a full card

#### Scenario: Extra metadata keys are tolerated
- **WHEN** `ModelCard.model_validate(mapping)` is called where `mapping` also contains keys not
  defined on the model (e.g. `soybean: True`, `oks_map: 0.8`, a nested `training_config`)
- **THEN** validation succeeds and the extra keys are ignored
