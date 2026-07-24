## ADDED Requirements

### Requirement: Capture Mode Vocabulary

The library SHALL define the controlled capture-mode vocabulary `Mode = Literal["cylinder",
"multiplant cylinder", "plate"]`, importable from the package root, mirroring how `RootType` is
defined and consumed as a field type. The vocabulary SHALL have exactly one definition in the
program; downstream consumers SHALL import it rather than re-declaring the value set, and callers
needing the values for a manual membership check SHALL use `typing.get_args(Mode)`.

#### Scenario: The vocabulary is importable and enumerable

- **WHEN** `Mode` is imported from the package root and `typing.get_args(Mode)` is called
- **THEN** it yields exactly `("cylinder", "multiplant cylinder", "plate")`

#### Scenario: The label shorthand is not in the vocabulary

- **WHEN** `typing.get_args(Mode)` is inspected for the shorthand `cyl` used by the existing label
  collection names
- **THEN** `cyl` is absent

### Requirement: Label Provenance Card

The library SHALL define an immutable (`frozen`) `LabelCard` model, importable from the package root,
that carries a label set's provenance and the identity of its concrete registry artifact.

Its **selection** fields SHALL be `species` (str), `mode` (`Mode`), `root_type` (`RootType`), and an
inclusive age window `age_min`/`age_max` (ints, each `>= 0`). Its **skeleton** fields SHALL be
`skeleton_name` (str), `node_count` (int, `>= 1`), and `node_names` (tuple of str). Its **content**
fields SHALL be `n_frames`, `n_instances`, `n_plants`, `n_scans` (ints, each `>= 0`) and
`images_embedded` (bool). Its **provenance** fields SHALL all be optional and default to `None`,
because #11's as-is backfill cannot recover them for the eight legacy collections (resolved:
Elizabeth, Slack 2026-07-21): `source_experiment` (str), `bloom_experiment_id` (str), `accessions`
(tuple of str), `labeler` (str), `source_sha256` (str), `box_link` (str), and `sleap_io_version`
(str). Its **identity** fields SHALL be `registry_id` (str) and `version` (str).

`LabelCard` SHALL NOT define a `data_path` field: row-level origin travels in the sample manifest
attached to the artifact, and content identity is carried by `source_sha256`.

`LabelCard` is a Python-side producer contract and SHALL NOT appear in the emitted JSON Schema.

#### Scenario: A valid card is constructed

- **WHEN** a `LabelCard` is built with valid selection, skeleton, content, provenance, and identity
  fields
- **THEN** construction succeeds and the field values are retained

#### Scenario: The card is immutable

- **WHEN** a field on a constructed `LabelCard` is reassigned
- **THEN** the assignment raises an error

#### Scenario: The optional fields are optional

- **WHEN** a `LabelCard` is built without a `box_link` and without a `sleap_io_version`
- **THEN** construction succeeds and both are `None`

#### Scenario: There is no data_path field

- **WHEN** a constructed `LabelCard`'s fields are inspected
- **THEN** no `data_path` field is present

#### Scenario: LabelCard is absent from the emitted result schema

- **WHEN** the `result_envelope` JSON Schema is generated
- **THEN** `LabelCard` is not present among its `$defs`

### Requirement: Label Card Mode Is Controlled

`LabelCard.mode` SHALL be typed `Mode`, so that a value outside the vocabulary is rejected at
construction. In particular the `cyl` shorthand used by the existing label collection names SHALL be
rejected, so that a label card and a model card cannot disagree about what the same capture mode is
called.

#### Scenario: The cyl shorthand is rejected

- **WHEN** a `LabelCard` is built with `mode` set to `cyl`
- **THEN** validation raises an error

#### Scenario: A canonical mode is accepted

- **WHEN** a `LabelCard` is built with `mode` set to `cylinder`
- **THEN** construction succeeds

#### Scenario: root_type is controlled

- **WHEN** a `LabelCard` is built with a `root_type` outside `{primary, lateral, crown}`
- **THEN** validation raises an error

### Requirement: Label Card Age Window Well-Formedness

`LabelCard` SHALL enforce `age_min <= age_max` at construction, and SHALL reject negative bounds. The
window is inclusive, so `age_min == age_max` is valid.

#### Scenario: An inverted window is rejected

- **WHEN** a `LabelCard` is built with `age_min` greater than `age_max`
- **THEN** validation raises an error

#### Scenario: Negative ages are rejected

- **WHEN** a `LabelCard` is built with a negative `age_min` or `age_max`
- **THEN** validation raises an error

#### Scenario: A single-age, zero-inclusive window is valid

- **WHEN** a `LabelCard` is built with `age_min` equal to `age_max` (e.g. both `0`, or both `7`)
- **THEN** construction succeeds, because the window is inclusive and `0` is an allowed bound

### Requirement: Label Card Skeleton Coherence

`LabelCard` SHALL enforce `node_count == len(node_names)` at construction, so that a card cannot
claim a node count its skeleton does not describe and node counts become queryable without parsing
free-text artifact descriptions.

#### Scenario: A coherent skeleton is accepted

- **WHEN** a `LabelCard` is built with `node_count` of `4` and four `node_names`
- **THEN** construction succeeds

#### Scenario: A node count disagreeing with the node names is rejected

- **WHEN** a `LabelCard` is built with `node_count` of `4` and six `node_names`
- **THEN** validation raises an error naming both the declared count and the actual number of names

#### Scenario: An empty skeleton is rejected

- **WHEN** a `LabelCard` is built with `node_count` of `0` and no `node_names`
- **THEN** validation raises an error

### Requirement: Tolerant Construction From Registry Metadata

`LabelCard` SHALL validate successfully from a mapping that merges label metadata with the
artifact-intrinsic identity fields, and SHALL ignore extra keys not defined on the model, so that a
card can be built from a raw wandb metadata blob — including the legacy boolean tag flags the
existing collections carry — merged with the artifact's identity without those extras causing
failure.

#### Scenario: A card built from merged metadata and identity validates

- **WHEN** `LabelCard.model_validate(mapping)` is called where `mapping` merges the label metadata
  with the artifact identity (`registry_id`, `version`)
- **THEN** validation succeeds and yields a full card

#### Scenario: Legacy boolean tag flags are tolerated

- **WHEN** `LabelCard.model_validate(mapping)` is called where `mapping` also contains keys not
  defined on the model (e.g. `v007: True`, `4nodes: True`, `images_embedded_repair: True`, a stale
  `data_path`)
- **THEN** validation succeeds and the extra keys are ignored
