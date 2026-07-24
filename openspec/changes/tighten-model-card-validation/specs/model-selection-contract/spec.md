## MODIFIED Requirements

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
ordinary lax integer parsing (for example `"7"` or `7.0`) unaffected.

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

#### Scenario: Lax integer parsing of the age bounds is preserved
- **WHEN** a `ModelCard` is built with an age bound given as `"7"` or `7.0`
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
