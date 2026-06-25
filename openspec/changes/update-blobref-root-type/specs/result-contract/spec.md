## MODIFIED Requirements

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
