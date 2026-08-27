# root-type-aliases Specification

## Purpose

Records which botanical root-type terms **route to** which canonical `RootType` bucket, for which
species, and over which developmental window — so that the equivalence is stated once, with its
scope and its evidence attached, instead of being rediscovered per repository.

This capability is a **routing** record, not a botanical one. Terms grouped here resolve to the same
model weights because they are not separable enough, at the recorded ages and in the recorded
modality, to be worth separating for detection. Grouping asserts nothing about developmental
identity or trait comparability: wheat seminal roots are embryonic while crown roots are
post-embryonic nodal roots, and outside a recorded window the two are co-present populations rather
than one.

It owns normalization at the **ingestion boundary** only. Which card wins a given request remains the
selection contract's business, and this capability's rules exist partly to keep the two apart.

## ADDED Requirements

### Requirement: Root Type Alias Table

The library SHALL define an immutable, contract-owned table recording, for each entry, the incoming
term, the species it applies to, the canonical `RootType` it routes to, and the inclusive
developmental window (`age_min` / `age_max`, in days, matching the age vocabulary the cards already
use) over which the routing holds. The table SHALL be importable from the package root and SHALL be
pure data — no I/O, no network, and no new dependency.

The table SHALL NOT alter `RootType` membership. Widening the canonical vocabulary would fork the
modeling bucket and break the label-to-model lineage join: a wheat collection stamped with a distinct
seminal root type could no longer be joined to the crown model actually trained on it.

An entry SHALL carry an inclusive age window and SHALL assert nothing outside it. This is not
optional detail: the governing decision is explicitly age-scoped ("in wheat **at the age we study**
the roots are seminal but they look the same as crown roots"), and the pooled training set that
evidences it carries a different window per species. A species-keyed entry without a window would
record a claim that is false of the crop in general.

The table SHALL be **evidence-gated and non-exhaustive**. An entry MAY be added only where a trained
model or a labeled collection actually pooled the terms, and the entry SHALL cite that evidence. The
absence of a term is NOT a claim that it has no equivalent. Sparsity is safe only because an
unrecognized term is rejected rather than defaulted; softening that rejection would silently un-safe
it.

The table SHALL carry a single table-level statement of its routing-not-synonymy semantics. It SHALL
NOT carry free prose per entry, which cannot be validated beyond non-emptiness and multiplies the
same sentence per row.

#### Scenario: Wheat seminal roots route to the crown bucket within a recorded window

- **WHEN** the alias table is read for species `wheat` and term `seminal`
- **THEN** the entry's canonical bucket is `crown`
- **AND** the entry carries an inclusive age window and a non-empty evidence citation

#### Scenario: The table does not change the canonical vocabulary

- **WHEN** every term in the table is compared against `RootType`'s members
- **THEN** no term is a member of `RootType`
- **AND** the table is non-empty and includes `seminal`, so the comparison is not vacuous

#### Scenario: The table is immutable

- **WHEN** any attempt is made to add, remove, or reassign an entry or a field of an entry
- **THEN** it raises
- **AND** reading the table afterwards shows the attempted change did not take effect

### Requirement: Canonical Root Type Normalization

The library SHALL provide a pure function mapping an incoming root-type term to its canonical
`RootType`, scoped by species and optionally by age, for use at a data-ingestion boundary.

A term that is already a canonical `RootType` SHALL return unchanged, and this passthrough SHALL take
precedence over any table entry, so a caller that cannot tell whether its input is already normalized
may apply the function unconditionally. The table SHALL NOT key any canonical `RootType` string as an
alias term, so the precedence rule can never mask a live entry.

The incoming term SHALL be matched **exactly**, without case or whitespace normalization, mirroring
how `root_type` is validated on the cards. Only the species key is normalized, because species is an
uncontrolled free `str` while the term is drawn from this table.

The species key SHALL be normalized by the same rules `resolve_params` applies to a species: stripped
and lowercased, with a present non-string raising a `ValueError` naming `species` rather than being
stringified, and with `None` and the pandas/numpy missing sentinels treated as *species not supplied*.
No contract-owned species vocabulary exists — `Selector.species` and `LabelCard.species` are both free
`str` — so a caller-supplied species differing only in case SHALL NOT silently miss the table.

When `species` is not supplied, the function SHALL resolve only terms that are unambiguous across
every entry in the table, and SHALL raise naming the candidate species when a term is recorded for
more than one species. A term recorded for a species other than the one supplied SHALL NOT resolve.

When `age_days` is supplied and falls outside the matched entry's window, the function SHALL raise a
`ValueError` naming the term, the species, and the window. When `age_days` is omitted the function
SHALL resolve, because age is not always available at an ingestion boundary — but the entry still
records the bound, and applying the routing outside it is out of contract.

A term that is neither canonical nor a recorded alias SHALL raise a `ValueError` naming the offending
term and the accepted values. A silently mis-bucketed term produces a *valid* card pointing at the
wrong models, which no downstream validation can catch.

#### Scenario: A botanical term routes to its canonical bucket

- **WHEN** the function is called with term `seminal`, species `wheat`, and an age inside the entry's window
- **THEN** it returns `crown`

#### Scenario: Normalization composes with itself

- **WHEN** the function is applied to `seminal` for species `wheat`, and applied again to that result for the same species
- **THEN** the result is `crown` both times

#### Scenario: The species key is matched case- and whitespace-insensitively

- **WHEN** the function is called with a term recorded **only** under species `wheat`, passing species `"  Wheat "`
- **THEN** it returns that term's canonical bucket
- **AND** the same term passed with species `rice` raises a `ValueError`, so the species argument is load-bearing

#### Scenario: A non-string species is rejected rather than stringified

- **WHEN** the function is called with a present, non-string species such as `123`
- **THEN** it raises a `ValueError` naming `species`

#### Scenario: An age outside the recorded window is rejected

- **WHEN** the function is called with term `seminal`, species `wheat`, and an age beyond the entry's `age_max`
- **THEN** it raises a `ValueError` naming the term, the species, and the window
- **AND** the same call with an age inside the window returns `crown`, so the guard discriminates

#### Scenario: An unrecognized term is rejected rather than defaulted

- **WHEN** the function is called with a term that is neither canonical nor a recorded alias
- **THEN** it raises a `ValueError` naming the term and the accepted values
- **AND** a recognized term called the same way still resolves, so the guard discriminates

#### Scenario: The returned value is accepted by the cards

- **WHEN** the value returned for term `seminal`, species `wheat` is passed as `root_type` to a `LabelCard` and to a `ModelCard`
- **THEN** both construct successfully and store `crown`

### Requirement: Normalization Does Not Preserve The Source Term

This capability SHALL document that normalization is **lossy by construction**: once a term is
routed to its canonical bucket, the contract retains no record of the term that arrived. `LabelCard`
carries no source-root-type field, so a backfilled wheat collection is indistinguishable in-contract
from a genuine wheat crown-root collection.

The loss SHALL be stated rather than obscured. A producer that needs the original term
for provenance — for example to report in a methods section which collections were labeled "seminal"
— SHALL retain it outside this contract until a card field exists to carry it. Adding such a field is
tracked as a follow-up and is deliberately not bundled here, because it would require modifying
`label-selection-contract` rather than adding to it.

#### Scenario: The canonical value carries no trace of the source term

- **WHEN** a wheat collection whose source term was `seminal` is normalized and stamped onto a card
- **THEN** the card's `root_type` is `crown`
- **AND** no field on the card records that the source term was `seminal`
