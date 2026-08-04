# model-selection-contract Specification

## Purpose
TBD - created by archiving change add-model-card-predict-inference-config. Update Purpose after archive.
## Requirements
### Requirement: Model Selection Card

The library SHALL define an immutable (`frozen`) `ModelCard` model that carries a production model's
selection metadata and the identity of its concrete registry artifact, importable from the package
root. Its selection fields SHALL be `species` (str), `mode` drawn from the controlled vocabulary
`Mode = {cylinder, multiplant cylinder, plate}`, an inclusive approved selection window
`age_min`/`age_max` (ints, each `>= 0`, with `age_min <= age_max`), and `root_type` drawn from the
controlled vocabulary `RootType = {primary, lateral, crown}`. Its identity fields SHALL be
`registry_id` (str), `version` (str), and an optional `weights_checksum`. The card SHALL also carry an
optional trained-with `sleap_nn_version`. The age window represents the model's curated approved
selection range (which MAY be wider than its training ages) and is assumed contiguous; the card never
observes a scan's age.

`mode` SHALL be matched exactly against the vocabulary: the card SHALL NOT normalize case or
whitespace, mirroring how `root_type` is validated on the same model. Tolerant handling of a
scan's *requested* mode remains the responsibility of `resolve_params`, which normalizes and then
degrades an unmodelled value to a selection zero-match rather than an error; this requirement
governs the card only.

`age_min` and `age_max` SHALL reject a `bool` rather than coerce it to `1`/`0`, while leaving
ordinary lax integer parsing (for example `"7"`, `7.0`, or a `numpy.int64`) unaffected. The
rejection SHALL cover a `numpy.bool_` as well as the builtin `bool`: `numpy.bool_` is not a `bool`
subclass, so a check that tests only for the builtin would let it through and read it as `1`/`0`.
The bool check SHALL apply to scalars only — a *container* of bools is not a bool, and SHALL be
rejected as a non-integer like any other container. Whatever the input, an invalid age bound SHALL
surface as a validation error and SHALL NOT propagate any other exception to the caller.

`ModelCard` is a Python-side producer contract and SHALL NOT appear in the emitted JSON Schema.

#### Scenario: A valid card is constructed
- **WHEN** a `ModelCard` is built with valid selection fields (`age_min <= age_max`, `mode` and
  `root_type` in their vocabularies) and identity fields (`registry_id`, `version`)
- **THEN** construction succeeds and the field values are retained

#### Scenario: Age window well-formedness is enforced
- **WHEN** a `ModelCard` is built with `age_min` greater than `age_max`
- **THEN** validation raises an error

#### Scenario: Negative ages are rejected
- **WHEN** a `ModelCard` is built with a negative `age_min` or `age_max`
- **THEN** validation raises an error

#### Scenario: A single-age, zero-inclusive window is valid
- **WHEN** a `ModelCard` is built with `age_min` equal to `age_max` (e.g. both `0`, or both `7`)
- **THEN** construction succeeds, because the window is inclusive and `0` is an allowed bound

#### Scenario: A bool age bound is rejected rather than coerced
- **WHEN** a `ModelCard` is built with `age_min` or `age_max` given as `True` or `False`
- **THEN** validation raises an error naming the bool, rather than coercing it to `1`/`0` and
  yielding a card that claims a plausible-but-wrong selection window

#### Scenario: A numpy bool age bound is rejected too
- **WHEN** a `ModelCard` is built with an age bound given as a `numpy.bool_`
- **THEN** validation raises the same error, because `numpy.bool_` is not a `bool` subclass and
  would otherwise be read as `1`/`0` — the card must not be looser than `resolve_params`, which
  already refuses a `numpy.bool_` age

#### Scenario: A container of bools is rejected as a non-integer
- **WHEN** a `ModelCard` is built with an age bound given as a one-element array of bools
- **THEN** validation raises a non-integer type error rather than reporting a bool, because the
  bool check applies to scalars and a container of ints in the same position is rejected the same way

#### Scenario: An unanticipated input still surfaces as a validation error
- **WHEN** a `ModelCard` is built with an age bound whose scalar-unwrap raises an unexpected error
- **THEN** validation raises a validation error rather than propagating that error to the caller,
  because the guard is duck-typed and callers of `model_validate` handle only validation errors

#### Scenario: A fractional age bound is rejected rather than truncated
- **WHEN** a `ModelCard` is built with an age bound given as `7.5` or `"7.5"`
- **THEN** validation raises an error rather than truncating to `7` and shifting which scans the
  model claims, mirroring how `resolve_params` refuses a non-integral age

#### Scenario: Lax integer parsing of the age bounds is preserved
- **WHEN** a `ModelCard` is built with an age bound given as `"7"`, `7.0`, or a `numpy.int64`
- **THEN** construction succeeds and the bound reads as the integer `7`

#### Scenario: root_type is controlled
- **WHEN** a `ModelCard` is built with a `root_type` outside `{primary, lateral, crown}`
- **THEN** validation raises an error

#### Scenario: mode is controlled
- **WHEN** a `ModelCard` is built with a `mode` outside `{cylinder, multiplant cylinder, plate}` —
  for example the label registry's `cyl` shorthand, or a differently-cased `Cylinder`
- **THEN** validation raises an error

#### Scenario: Every mode in the vocabulary is accepted
- **WHEN** a `ModelCard` is built with each member of `{cylinder, multiplant cylinder, plate}` in turn
- **THEN** construction succeeds in every case and the value is retained unchanged

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

