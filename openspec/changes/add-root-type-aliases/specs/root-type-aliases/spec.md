# root-type-aliases Specification

## Purpose

Records which botanical root-type terms **route to** which canonical `RootType` bucket, for which
species, and over which developmental window — so that the equivalence is stated once, with its
scope and its evidence attached, instead of being rediscovered per repository.

This capability is a **routing** record, not a botanical one. Terms grouped here resolve to the same
model weights because they are not separable enough, at the recorded ages and in the recorded
modality, to be worth separating for detection. Grouping asserts nothing about developmental
identity or trait comparability: wheat seminal roots are embryonic while crown roots are
post-embryonic nodal roots. **Above** a recorded window the two are co-present populations rather
than one, so pooling them merges distinct root systems. **Below** it the failure is different: a
young enough wheat plant has only its embryonic system, whose radicle the `primary` bucket also has
a claim on, so the window's lower bound guards a bucket collision rather than a co-presence.

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

An entry SHALL carry an inclusive age window, expressed in **days after germination (DAG)**, and
SHALL assert nothing outside it. The epoch SHALL be stated because it is load-bearing and is
recorded nowhere else in this library: the seeded window is read off a `DAG`-labelled dataset, while
the consumer side takes its age from Bloom's `plant_age_days`, whose epoch this contract has never
pinned. Wheat germinates roughly two to three days after imbibition, so a DAG-versus-DAP mismatch
shifts a 5-14 window by a fifth to a third of its span — enough to admit a plant that is already
tillering. An entry's bounds SHALL satisfy `0 <= age_min <= age_max`.

An entry's window SHALL be the window its cited evidence establishes and SHALL NOT be widened beyond
it. A window spanning a crop's whole studied age range is not evidence-gated and SHALL NOT be
seeded — such a window would satisfy every scenario below while defeating the scoping this
requirement exists to impose. This is not
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
more than one species.

A term recorded only for a species other than the one supplied SHALL NOT resolve, and SHALL raise an
error naming the term, the species supplied, and the species the term **is** recorded for. It SHALL
NOT reuse the unknown-term error, which lists accepted *terms* and would send the caller to correct
the wrong argument — the term is fine; the species is the mismatch.

`age_days`, when supplied, SHALL be validated the way this library validates every other age: a
`bool` SHALL be rejected rather than read as `1`, and the rejection SHALL cover `numpy.bool_`, which
is not a `bool` subclass; a fractional or non-finite value SHALL be rejected rather than truncated.
Ordinary lax integer parsing is unaffected. Without this a `True` age compares as `1` and sits
silently inside any window starting at zero.

When `age_days` is supplied and falls outside the matched entry's window, the function SHALL raise a
`ValueError` naming the term, the species, and the window. The window is **inclusive**: an age equal
to `age_min` or to `age_max` is inside it. When `age_days` is omitted the function
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

#### Scenario: The window bounds are inside it

- **WHEN** the function is called with an age exactly equal to the entry's `age_min`, and again with
  an age exactly equal to its `age_max`
- **THEN** both resolve, and an age one day beyond `age_max` raises

#### Scenario: A bool age is rejected rather than read as day one

- **WHEN** the function is called with `age_days` of `True`, or of `numpy.bool_(True)`
- **THEN** it raises a `ValueError` naming `age_days`, and never treats the value as the integer `1`

#### Scenario: A term recorded for another species names the species, not the term

- **WHEN** the function is called with a term recorded only under `wheat`, passing species `rice`
- **THEN** it raises an error naming the term, `rice`, and `wheat`
- **AND** the message is not the unknown-term error, whose accepted-values list would point at the
  wrong argument

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

#### Scenario: Normalization returns a bucket and communicates nothing else

- **WHEN** a term that is an alias and a term that is already canonical are both normalized to the
  same bucket
- **THEN** the two results are indistinguishable, so nothing downstream can recover which input
  arrived
