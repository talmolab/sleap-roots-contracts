## ADDED Requirements

### Requirement: Analysis-Input Table Schema
The library SHALL define a canonical schema for the wide analysis-input table as a Pydantic row
model (`AnalysisInputRow`) describing one row with **fixed canonical role names**: a required
`genotype` column (`str`), optional `str` metadata columns `sample_id`, `replicate`, and
`image_path`, and an open set of numeric **trait** columns whose names are opaque (not fixed in
advance). The schema SHALL NOT accept a column-mapping parameter; consumers canonicalize their own
column names to these fixed names before validating. Trait names SHALL NOT be validated against any
registry, and trait values SHALL NOT be range-checked — those remain `result-contract` and
statistical-QC concerns.

#### Scenario: A well-formed row validates against the model
- **WHEN** a row with a string `genotype`, an optional string `sample_id`, and one or more numeric
  trait values is validated against `AnalysisInputRow`
- **THEN** validation succeeds

#### Scenario: A non-string genotype is rejected
- **WHEN** a row whose `genotype` is numeric (not a string) is validated against `AnalysisInputRow`
- **THEN** validation raises an error

### Requirement: Analysis-Input DataFrame Validator
The library SHALL provide `validate_analysis_input(df, *, strict=False) -> ValidationResult`,
importable from the package root, that validates a tabular analysis input against the fixed canonical
names and returns a structured `ValidationResult` carrying `ok`, `errors`, and `warnings`. The
validator SHALL apply a three-tier severity model. As **errors** (always failing): a missing
`genotype` column, a `genotype` column that is not string-typed, a declared role column with a wrong
dtype, the absence of any numeric trait column, and a `NaN` in the required `genotype` column. As
**warnings** by default and **errors** when `strict=True`: a missing `sample_id` column, an
unknown/unexpected column, and a `NaN` in an optional metadata column. `NaN` SHALL be permitted in
trait columns. The metadata column set SHALL NOT be a closed allowlist. `ValidationResult` SHALL
expose `raise_for_status()` that raises when any error is present and is a no-op otherwise, and each
recorded issue SHALL identify the offending column.

The validator SHALL operate on the **canonicalized** analysis input — role columns plus trait
columns, with non-trait metadata already excluded upstream (the consumer's responsibility, e.g.
`sleap-roots-analyze`'s `get_trait_columns` boundary per `talmolab/sleap-roots-analyze#144`). Because
the validator has no metadata registry, any numeric non-role column SHALL be treated as a trait; the
contract SHALL NOT attempt to distinguish phenotypic traits from numeric metadata by name.

#### Scenario: A valid analysis-input table passes
- **WHEN** a table with a string `genotype` column, a `sample_id` column, and at least one numeric
  trait column is validated
- **THEN** the result's `ok` is true and `errors` is empty

#### Scenario: A missing required column is an error
- **WHEN** a table without a `genotype` column is validated
- **THEN** the result's `ok` is false, `errors` is non-empty, and `raise_for_status()` raises

#### Scenario: A table with no trait column is an error
- **WHEN** a table that has only role/metadata columns and no numeric trait column is validated
- **THEN** the result's `ok` is false and `errors` is non-empty

#### Scenario: A non-string genotype column is an error
- **WHEN** a table whose `genotype` column is numeric-typed (e.g. integer codes, not strings) is
  validated
- **THEN** the result's `ok` is false, `errors` is non-empty, and the offending issue names the
  `genotype` column

#### Scenario: A wrong dtype on a declared role column is an error
- **WHEN** a table whose optional `replicate` column is numeric-typed (not string) is validated
- **THEN** the result's `ok` is false, `errors` is non-empty, the offending issue names the
  `replicate` column, and `raise_for_status()` raises

#### Scenario: NaN in the required genotype column is an error
- **WHEN** a table contains `NaN` in the required `genotype` column
- **THEN** the result's `ok` is false, `errors` is non-empty, and the offending issue names the
  `genotype` column
- **WHEN** that same `NaN` instead appears only in an optional metadata column with default settings
- **THEN** the result's `ok` remains true (a warning, not an error)

#### Scenario: NaN is allowed in traits but warned in optional metadata
- **WHEN** a table contains `NaN` in a trait column and valid values in every role column
- **THEN** the result's `ok` is true
- **WHEN** a table contains `NaN` in an optional metadata column (e.g. `replicate`) with default
  settings
- **THEN** a warning is recorded and `ok` remains true
- **WHEN** the same table is validated with `strict=True`
- **THEN** the `NaN` in optional metadata is recorded as an error and `ok` is false

#### Scenario: A missing sample_id warns by default and errors when strict
- **WHEN** a table with a `genotype` column and trait columns but no `sample_id` column is validated
  with default settings
- **THEN** a warning is recorded and `ok` remains true
- **WHEN** the same table is validated with `strict=True`
- **THEN** the missing `sample_id` is recorded as an error and `ok` is false

#### Scenario: An unknown column warns by default and errors when strict
- **WHEN** a table with an unrecognized non-numeric column is validated with default settings
- **THEN** a warning is recorded and `ok` remains true
- **WHEN** the same table is validated with `strict=True`
- **THEN** the unknown column is recorded as an error and `ok` is false

#### Scenario: Validation errors carry useful messages
- **WHEN** a malformed table is validated
- **THEN** each recorded issue exposes a `column` naming the offending column (or no column for a
  table-level issue) and a human-readable `message`

#### Scenario: A numeric non-role column is treated as an opaque trait
- **WHEN** a table includes a numeric column that is not a declared role (e.g. an id, count, or
  timing column such as `scan_id` or `Computation.Time.s`)
- **THEN** it is counted as a trait column (it satisfies the "at least one numeric trait" rule) and
  no warning or error is raised for it — the structural validator has no metadata registry, so
  excluding such columns is the consumer's canonicalization responsibility, not the contract's

#### Scenario: Duplicate column names are a table-level error
- **WHEN** a table has duplicate column names (which would otherwise make per-column lookups
  ambiguous)
- **THEN** the result's `ok` is false and a table-level error names the duplicated columns, and the
  validator does not raise an unhandled exception

#### Scenario: An empty table is validated structurally
- **WHEN** a table that has the canonical columns but zero rows is validated
- **THEN** column-presence and dtype checks still apply (e.g. a missing `genotype` column is still an
  error) and no per-row `NaN` issues are raised for the absent rows

### Requirement: Pandas Is An Optional Dependency
The validator SHALL operate on a pandas DataFrame, and pandas SHALL be an optional install extra so
the library's runtime core depends only on pydantic and pyyaml. When `validate_analysis_input` is
called without pandas installed, it SHALL raise an `ImportError` whose message names the
`sleap-roots-contracts[pandas]` extra.

#### Scenario: Missing pandas raises a guided ImportError
- **WHEN** `validate_analysis_input` is invoked in an environment without pandas installed
- **THEN** it raises an `ImportError` that tells the caller to install the `[pandas]` extra

### Requirement: Emitted Analysis-Input JSON Schema Artifact
The library SHALL emit a versioned JSON Schema (`schema/analysis_input.schema.json`) generated from
`AnalysisInputRow`, describing one table row: `genotype` required and typed `string`, the optional
metadata columns typed `string`, and additional (trait) properties typed as `number` or `null`. The
package version SHALL be carried in the schema's `$id`, and CI SHALL fail if the committed schema
differs from a fresh regeneration (the existing drift guard).

#### Scenario: The emitted schema marks genotype required and types trait columns
- **WHEN** the JSON Schema is generated from `AnalysisInputRow`
- **THEN** `genotype` is required and typed `string`, and additional properties are typed `number`
  or `null`

#### Scenario: Stale committed analysis-input schema fails CI
- **WHEN** `AnalysisInputRow` changes but `schema/analysis_input.schema.json` is not regenerated
- **THEN** the drift-guard check fails

### Requirement: Example Fixtures Per Shape
The library SHALL ship example analysis-input tables for the cylinder, field, and turface shapes
(plus a genotype-aggregated table) under `tests/fixtures/`, loaded via a pytest fixture, each of which
validates (its `ok` is true) via `validate_analysis_input`. The examples SHALL be small real subsets
of the wheat EDPIE post-QC tables in **canonical** form — role columns plus opaque numeric trait
columns only, with non-trait metadata excluded (mirroring a consumer's canonicalization). Only the
role columns SHALL be canonical; trait column names SHALL remain opaque and realistic (units, parens,
dotted names). At least one example SHALL be sample-level (has `sample_id`) and at least one SHALL be
genotype-aggregated (no `sample_id`), so the missing-`sample_id` warning path is exercised in both
directions. The structural classifier's metadata-as-trait limitation SHALL be pinned by a unit test
(an inline DataFrame), not by embedding metadata decoy columns in the shipped example tables.

#### Scenario: Each shipped example validates
- **WHEN** the cylinder, field, and turface example tables are each validated
- **THEN** every result's `ok` is true

#### Scenario: A genotype-aggregated example warns on the missing sample identifier
- **WHEN** the genotype-aggregated example (no `sample_id` column) is validated with default settings
- **THEN** its `ok` is true and a warning naming `sample_id` is recorded
- **WHEN** a sample-level example (has `sample_id`) is validated
- **THEN** its `ok` is true and no warning is recorded
