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

Two consequences of that are stated here as prose rather than as scenarios, because no selection
code lives in this repo and a scenario with no possible local test is a promise nothing keeps.
Consumers SHALL store the canonical bucket at ingestion and match on it by exact equality; and a
selection request naming a non-canonical root type SHALL be rejected, never routed through the alias
table into a bucket. The precedent this requirement's placement follows,
`No Tolerant Read Of The Legacy Flat Card`, had all three of its scenarios locally tested and rested
its force on a re-added tolerance "visibly deleting a requirement and reddening tests" — that
argument does not transfer to a scenario nothing here can exercise, so it is not borrowed.

#### Scenario: An aliased term is not a legal card value

- **WHEN** a card is constructed directly with an un-normalized alias term
- **THEN** validation rejects it, because `RootType` membership is unchanged
- **AND** the same card constructed with the canonical bucket succeeds
