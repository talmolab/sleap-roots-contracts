## ADDED Requirements

### Requirement: Scan Metadata Resolution To Params

The library SHALL provide a pure function `resolve_params(metadata, overrides=None) ->
ResolvedParams` that maps a single Bloom `cyl_scans_extended` scan-metadata record (the dict shape
bloomcli's download writes to `scans.csv`) to a `ResolvedParams` carrying `species`, `mode`, and
`age`. It SHALL read the load-bearing fields via module constants matching bloomcli's column names:
`species_name` → `species` (normalized), the scan's scanner → `mode` (via the imaging-mode seam),
and `plant_age_days` → `age`. A load-bearing field that is **absent or blank** (missing key, `None`,
a non-string sentinel such as a `NaN`, or an empty/whitespace-only string) SHALL be treated as not
provided — the function SHALL omit that derived param (deferring to `overrides` and then to
post-override validation) rather than raising at read time or emitting a blank param. It SHALL
construct `ResolvedParams(values=…)` so the contract computes `param_hash`. The function SHALL be
pure: it SHALL perform no network access and no filesystem I/O, and SHALL NOT mutate the input
`metadata`.

This is the library's single **soft, documented** coupling to Bloom's column vocabulary: dict keys
only, hoisted into module constants so the cross-repo coupling is explicit and greppable. It
introduces no Bloom import and no DB, network, or filesystem dependency, so the library remains a
pure, dependency-light leaf.

#### Scenario: A sample cylinder scan row resolves to species/mode/age

- **WHEN** `resolve_params` is called with a `cyl_scans_extended` row carrying
  `species_name="Pennycress"` and `plant_age_days=14`
- **THEN** it returns a `ResolvedParams` whose `values` are
  `{"species": "pennycress", "mode": "cylinder", "age": 14}` and whose `param_hash` is populated by
  the contract

#### Scenario: The load-bearing field constants match bloomcli's columns

- **WHEN** the module constants `SPECIES_NAME_FIELD` and `PLANT_AGE_DAYS_FIELD` are read
- **THEN** they equal `"species_name"` and `"plant_age_days"` respectively

#### Scenario: Extra columns are ignored and the input is not mutated

- **WHEN** `resolve_params` is called with a full `cyl_scans_extended` row carrying many
  non-load-bearing columns (e.g. `species_genus`, `scan_id`, timestamps)
- **THEN** only `species`, `mode`, and `age` appear in the resolved `values`, and the passed-in
  `metadata` dict is unchanged

#### Scenario: A blank species value is treated as not provided

- **WHEN** `species_name` is present but blank (`""`, `"   "`, `None`, or a `NaN`) with no `species`
  override
- **THEN** `resolve_params` raises a `ValueError` naming `species` (the blank is treated as missing,
  not resolved to an empty species)

### Requirement: Species Name Normalization

The library SHALL normalize the Bloom `species_name` to the `ModelCard` species vocabulary via
`_normalize_species`, which strips and lowercases the name and then applies an alias map keyed by the
**lowercased** name. The alias map is the single extension point for any Bloom name that does not
lowercase cleanly to the card string (e.g. a Latin binomial); names not in the map fall through as
their stripped, lowercased form (**lowercase passthrough fallback**). Unknown species SHALL pass
through rather than being rejected or dropped — the registry/`ModelCard`s are the single authority on
which species have models, so an unmodelled species degrades to a downstream selection zero-match
(skip), not a resolver error. The resolver SHALL NOT maintain a whitelist or hard-fail on species.

#### Scenario: A seeded species normalizes to the card vocabulary

- **WHEN** `species_name` is `"Pennycress"`
- **THEN** the resolved `species` is `"pennycress"`

#### Scenario: Surrounding whitespace and case are normalized

- **WHEN** `species_name` is `"  Rice  "`
- **THEN** the resolved `species` is `"rice"`

#### Scenario: An unknown species passes through lowercased

- **WHEN** `species_name` is `"Sorghum"` (a real Bloom species with no seeded model)
- **THEN** the resolved `species` is `"sorghum"` (passthrough), and no error is raised

#### Scenario: A blank or non-string species normalizes to empty

- **WHEN** `_normalize_species` is called with `""`, `"   "`, `None`, or a `NaN`
- **THEN** it returns `""` so callers treat the value as not provided

#### Scenario: The alias map substitutes a non-identity alias

- **WHEN** the (normally empty) alias map is populated with `"thlaspi arvense" -> "pennycress"` and
  `species_name` is `"Thlaspi arvense"`
- **THEN** the resolved `species` is `"pennycress"`

### Requirement: Imaging Mode Resolution Seam

The library SHALL derive `mode` through a single `_mode_for_scan(metadata)` function that returns
`"cylinder"` for the current cylinder stage-in path (the cylinder pipeline yields cylinder scans
only). This function SHALL be the one place mode is decided, so future GraviScan/multiscanner modes
slot in here without changing `resolve_params`'s body, its callers, or its output shape. The mode
strings it returns MUST equal the exact seeded `ModelCard` mode vocabulary. A mode value SHALL be
normalized (strip + lowercase) by `_normalize_mode`, mirroring species normalization, so a derived
mode and an override mode canonicalize identically. The scanner→mode lookup table for deferred
modalities is explicitly out of scope for this change.

#### Scenario: A cylinder scan resolves mode "cylinder"

- **WHEN** `resolve_params` resolves a `cyl_scans_extended` row
- **THEN** the resolved `mode` is `"cylinder"`

#### Scenario: The resolved mode matches the seeded ModelCard mode vocabulary

- **WHEN** a `ModelCard` is constructed with `mode="cylinder"` and a row is resolved
- **THEN** the resolved `mode` equals that card's `mode`

#### Scenario: Mode normalization strips and lowercases

- **WHEN** `_normalize_mode` is called with `"  Cylinder "`
- **THEN** it returns `"cylinder"`

### Requirement: Age Resolution In Days

The library SHALL resolve `age` from `plant_age_days` as an integer number of days via `_coerce_age`.
It SHALL accept both an integer and an int-coercible whole-number string (Bloom metadata read from
`scans.csv` may arrive as a string, e.g. `"14"`), canonicalizing both to the same `int` so the
resolved `age` — and therefore `param_hash` — does not depend on the incoming representation. A
present, non-blank, but non-whole or non-coercible value (e.g. `14.5`, `"14.5"`, `"abc"`, or a bool)
SHALL raise a `ValueError` naming `age`, rather than silently truncating. A whole float (e.g. `14.0`,
as produced when pandas coerces a NaN-containing numeric column) SHALL coerce cleanly to `int`. A
resolved `age` of `0` SHALL be valid (validation checks key presence, not truthiness).

#### Scenario: An integer age passes through as days

- **WHEN** the row's `plant_age_days` is `14`
- **THEN** the resolved `age` is the integer `14`

#### Scenario: An int-coercible string age is coerced to the same int

- **WHEN** the row's `plant_age_days` is the string `"14"`
- **THEN** the resolved `age` is the integer `14`, and the resulting `param_hash` is identical to the
  `plant_age_days=14` case (representation-independent)

#### Scenario: A whole float age is coerced to int

- **WHEN** `_coerce_age` is called with `14.0`
- **THEN** it returns the integer `14`

#### Scenario: A non-whole, non-coercible, or bool age raises naming age

- **WHEN** the row's `plant_age_days` is `14.5`, `"14.5"`, `"abc"`, or `True`
- **THEN** `resolve_params` raises a `ValueError` whose message names `age`

#### Scenario: An age of zero is valid

- **WHEN** the row's `plant_age_days` is `0`
- **THEN** the resolved `age` is `0` and resolution succeeds (0 is not treated as missing)

#### Scenario: A blank age is treated as not provided

- **WHEN** the row's `plant_age_days` is blank (`""`, whitespace, `None`, or `NaN`) with no `age`
  override
- **THEN** `resolve_params` raises a `ValueError` naming `age` as **missing** (treated as not
  provided — the same as a blank `species_name`), rather than a "not a whole number" error

### Requirement: Override Merge Semantics

The optional `overrides` argument SHALL be a param-space dict merged last so a supplied field
replaces the derived one (**override wins per field**). Override keys SHALL be restricted to the
resolvable params `{species, mode, age}`; an unrecognized override key SHALL raise a `ValueError`
naming the offending key. Override **values** SHALL be canonicalized by the same per-field rules as
derived values (`species` via `_normalize_species`, `mode` via `_normalize_mode`, `age` via
`_coerce_age`), so a logically identical run produces an identical `param_hash` regardless of whether
a value arrived derived or as an override. A blank override value is treated as not provided: the
field is dropped, deferring to the post-override validation requirement below.

#### Scenario: Override wins per field

- **WHEN** `resolve_params(row, overrides={"mode": "graviscan", "species": "canola"})` is called
- **THEN** `mode` is `"graviscan"` and `species` is `"canola"` (the overrides), while any field not
  present in `overrides` (e.g. `age`) keeps its derived value

#### Scenario: An empty overrides dict changes nothing

- **WHEN** `resolve_params(row, overrides={})` is called
- **THEN** the resolved `values` equal those of `resolve_params(row)`

#### Scenario: Override values are canonicalized like derived values

- **WHEN** `resolve_params(row, overrides={"species": "Rice", "age": "14"})` is called
- **THEN** the resolved `species` is `"rice"` and `age` is the integer `14` (normalized/coerced, not
  stored raw), so the `param_hash` matches the equivalent derived run

#### Scenario: A mode override is canonicalized

- **WHEN** `resolve_params(row, overrides={"mode": "  Cylinder "})` is called
- **THEN** the resolved `mode` is `"cylinder"`, so the `param_hash` matches the equivalent derived run
  and selection is not broken by casing

#### Scenario: A bool age override is rejected naming age

- **WHEN** `resolve_params(row, overrides={"age": True})` is called
- **THEN** it raises a `ValueError` whose message names `age`

#### Scenario: An unknown override key is rejected

- **WHEN** `resolve_params(row, overrides={"specis": "rice"})` is called (a typo'd key)
- **THEN** it raises a `ValueError` whose message names the unrecognized key

#### Scenario: A blank mode override is treated as absent

- **WHEN** `resolve_params(row, overrides={"mode": ""})` is called
- **THEN** it raises a `ValueError` whose message names `mode`

#### Scenario: A blank age override drops the derived age

- **WHEN** `resolve_params(row, overrides={"age": blank})` is called for a row carrying a valid
  `plant_age_days`, where `blank` is `""`, `"   "`, `None`, or a `NaN`
- **THEN** the derived `age` is dropped rather than retained, and it raises a `ValueError` whose
  message names `age`

### Requirement: Strict Post-Override Validation

After merging and canonicalizing, `resolve_params` SHALL require that `species`, `mode`, and `age`
are all present (by key) and SHALL raise a clear `ValueError` naming **every** missing param when any
is absent. It SHALL NOT return a half-resolved `ResolvedParams`. Presence is checked by key, not by
truthiness, so a resolved `age` of `0` satisfies validation.

#### Scenario: Missing required fields raise naming each missing param

- **WHEN** `resolve_params` is called with a row missing both `species_name` and `plant_age_days` and
  no compensating overrides
- **THEN** it raises a `ValueError` whose message names both missing params (`species` and `age`)

#### Scenario: A blank age does not mask a blank species

- **WHEN** a row carries a blank `species_name` **and** a blank `plant_age_days`
- **THEN** the raised `ValueError` names both `species` and `age`

#### Scenario: A missing derived field can be supplied by an override

- **WHEN** a row is missing `species_name` but the call passes `overrides={"species": "rice"}`
- **THEN** resolution succeeds with `species="rice"` (the override satisfies post-override validation)

#### Scenario: A blank derived age can be supplied by an override

- **WHEN** a row's `plant_age_days` is `NaN` and the call passes `overrides={"age": 5}`
- **THEN** resolution succeeds with `age=5` (the blank defers to the override rather than raising)

### Requirement: Public API Export

The library SHALL export `resolve_params` from the package's public API — importable as
`from sleap_roots_contracts import resolve_params` and listed in `__all__` — giving it drop-in parity
with `ResolvedParams` so consumers swap the import with no call-site changes. The Bloom column-name
constants `SPECIES_NAME_FIELD` and `PLANT_AGE_DAYS_FIELD` SHALL remain module-public (referenceable
by consumers) but SHALL NOT be added to the package `__all__`.

#### Scenario: resolve_params is importable and in __all__

- **WHEN** a caller runs `from sleap_roots_contracts import resolve_params`
- **THEN** the import succeeds and `"resolve_params"` is present in `sleap_roots_contracts.__all__`

#### Scenario: Bloom column-name constants are module-public but not package API

- **WHEN** the `params` module is imported and the package `__all__` is inspected
- **THEN** `SPECIES_NAME_FIELD` and `PLANT_AGE_DAYS_FIELD` are readable on the module, and neither
  name appears in `sleap_roots_contracts.__all__`

### Requirement: Resolved Params Known-Answer Anchor

The library SHALL pin the resolver's end-to-end output with a known-answer test over a canonical
resolved row — the row's `param_hash`, not merely its `values` — so that any change to the resolver's
normalization fails loudly rather than silently rotating every previously computed
`Provenance.idempotency_key` (first-writer-wins). Comparing two resolved rows to each other is
insufficient: both sides move together under a canonicalization change, so only a literal anchor
detects it.

The hashing algorithm itself, and its independence from the package version, remain owned by the
`result-contract` capability's producer-side hashing requirement; this requirement pins only the
composition of `resolve_params` with that hash.

#### Scenario: The canonical row hashes to its known answer

- **WHEN** `resolve_params` resolves a row to
  `{"species": "pennycress", "mode": "cylinder", "age": 14}`
- **THEN** the resulting `param_hash` is exactly
  `d7562d09b93a57ba6c1a128f27c6c8022c023365a3243e7508423b45756faecb`
