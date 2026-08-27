## ADDED Requirements

### Requirement: Alias Normalization Is An Ingestion Boundary Only

Root-type alias normalization SHALL be applied when data enters the pipeline — labeling, backfill, or
a hand-authored config — and SHALL NOT be applied to either side of a model-selection match.

Selection matches `root_type` by exact equality. Normalizing during matching would let a request for
one bucket match cards in another with no error raised anywhere, which is the same silent-widening
failure that exact-match selection exists to prevent.

The prohibition is on the **effect**, not merely on a call site: a requested root type that is not a
canonical `RootType` SHALL be **rejected**, not normalized into one, at every point downstream of
ingestion. Normalizing a request at a consumer's own CLI boundary and then matching on the result
complies with the letter of an ingestion-only rule while producing exactly the widening this
forbids.

This requirement is stated here, alongside the matching rule it constrains, rather than only in the
capability that owns the alias table — a prohibition filed away from the decision it governs is not
discoverable by the reader who is about to violate it.

This is a normative statement this library makes about how consumers use it. It is **not** enforced
by the type system: the normalization function accepts an already-canonical value by design, so
nothing mechanically prevents calling it on both sides of a comparison. Enforcement is by review.

#### Scenario: Normalized data is stored, not normalized at match time

- **WHEN** a card is constructed from a source whose term was an alias
- **THEN** the card's stored `root_type` is the canonical bucket
- **AND** a selection request carrying that same canonical bucket matches it by exact equality

#### Scenario: A non-canonical requested root type is rejected, not normalized

- **WHEN** a selection request names a root type that is not a member of `RootType`
- **THEN** it is rejected
- **AND** it is not routed through the alias table into a canonical bucket

#### Scenario: An aliased term is not a legal card value

- **WHEN** a card is constructed directly with an un-normalized alias term
- **THEN** validation rejects it, because `RootType` membership is unchanged
- **AND** the same card constructed with the canonical bucket succeeds
