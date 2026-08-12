# Design: `Selector`, and the shape of one card per physical model

## Context

The approved shape, the axis analysis, and the migration reasoning were settled on the producer side
across five review rounds and approved on 2026-08-12. They are **not** re-derived here. Sources:

- talmolab/sleap-roots-contracts#31 — this change's tracking issue, carrying the approved shape and the
  tolerant-read state table (three rows over the pin × card-shape space).
- talmolab/sleap-roots-training#47 (`openspec/changes/update-model-card-selectors/`) — the producer
  change: the 13→8 measurement, the 1-of-5 species-tuple measurement, the collection-id decision, the
  wandb link-into-many-collections investigation, and the live-registry migration plan.

What this document records is the set of decisions that are **this repo's** to make: the ones #31's
shape sketch leaves unstated, and the ones about how the delta is written.

## Goals / non-goals

**Goals.** Express "one artifact, several validated selection contexts" in the contract. Keep the
existing age/mode validation exactly as strict as it is today, by reuse rather than restatement. Leave
the spec saying only true things after archive, including in the `param-resolution` capability that
references the card.

**Non-goals.** Implementing selection (`choose_models` is predict's). Deciding age windows (#46).
Changing what any model does.

## Decisions this repo owns

### 1. `Selector` is `frozen`

#31 writes `class Selector(BaseModel)` with no config, leaving this unstated. It must be `frozen`, for
two reasons that are not stylistic:

- **`ModelCard`'s immutability is otherwise a lie.** The card is `frozen`, but `frozen` on a pydantic
  model prevents attribute assignment *on that model only*. With a mutable `Selector`,
  `card.selectors[0].species = "sorghum"` succeeds and silently rewrites what a "frozen" production
  card claims to select. The `tuple` annotation protects the sequence, not the elements.
- **The producer needs selectors hashable.** Its expansion collapses several matrix rows onto one
  physical model and de-duplicates identical contexts; a `set` is the obvious way, and pydantic makes a
  model hashable only when it is `frozen`. Leaving it mutable would push the producer into hand-rolled
  field-by-field comparison for no gain.

Every other card in this library is `frozen`, so this is also the consistent choice.

### 2. `Selector` sets `extra="ignore"` explicitly

Same load-bearing reason `ModelCard` does it, one level down. Selectors arrive as nested mappings
inside a raw wandb metadata blob. Setting it explicitly (rather than relying on it as pydantic's
default) records that tolerating unknown keys is contractual: a consumer pinned to an older contract
must survive a newer producer adding a selector field, rather than failing the whole card and dropping
the model from selection. A future `extra="forbid"` here would be a silent breaking change for exactly
the consumer this library exists to decouple.

### 3. Age validation is reused, not restated

`age_min`/`age_max` on `Selector` take the existing `NonBoolInt` annotation and `Field(ge=0)`, and the
ordering check reuses the body of `ModelCard._check_age_range` rather than being re-written. #31 is
explicit about the reuse ("reuse the existing validation … rather than restating it"), and it matters
more than it looks: `NonBoolInt` was strengthened to catch `numpy.bool_` in
`tighten-model-card-validation` only weeks ago, and a hand-written bound check on `Selector` would
silently reopen that hole. The delta spec therefore re-states the *guarantees* (so they stay specified)
while the code shares one implementation.

**How the sharing is staged follows from the two-commit split (see Risks).** Because commit 1 adds
`Selector` while `ModelCard` still has its flat bounds, the check cannot simply be *moved*: both models
need it at once. So commit 1 lifts the body into a module-level helper that `Selector`'s validator calls,
and commit 2 deletes `ModelCard`'s now-redundant validator when its bounds go. `LabelCard` keeps its own
separate copy either way — it is out of scope here, though the duplication is now visible enough to be
worth its own cleanup later. An earlier draft of this decision said the validator "moves … with its body
unchanged", which described a single-commit mechanism the plan abandoned; `tasks.md` 2.3 and 3.10 carry
the staged version.

One trap in the mechanical part: `models.py`'s validator is annotated `-> "ModelCard"`, and left that
way on `Selector` it still *works* (pydantic never evaluates the annotation) while
`typing.get_type_hints` resolves it to the wrong class — verified, and there is no mypy in this repo's
dev dependencies and no type-check step in CI, so nothing would catch it. `tasks.md` 2.3 says so
explicitly for that reason.

Note the ordering check moves **down** a level, which changes where the error surfaces: an inverted
window now reports a `loc` inside `selectors` (`('selectors', 0)`), not a card-level field. The delta
says so, and the scenario asserts it, because a consumer logging validation errors per artifact will
see the new shape. That guarantee is only reachable on the **mapping** path — `ModelCard(selectors=(
Selector(...),))` cannot even be written with an invalid bound, since `Selector` raises first with an
empty `loc`. The delta states this so the negative tests are not accidentally written against a
`Selector`-object fixture, which would stop exercising the card at all.

### 4. `selectors` is non-empty, checked **before** items are validated

An empty `selectors` is a producer bug, not a model that matches nothing — a card that can never be
selected has no reason to be published, and silently accepting one turns a seeding bug into an
invisible gap in registry coverage.

The obvious mechanism, `Field(min_length=1)` on the tuple, is **wrong here**, and this was measured
rather than reasoned. pydantic validates items first, drops the invalid ones, *then* applies the length
constraint to what survives — so a card whose single selector is bad reports **two** errors, the real
one plus a spurious `too_short`:

```
selectors=[{...age_min=6, age_max=3}]  ->  [(('selectors',0),'value_error'), (('selectors',),'too_short')]
selectors=[{...mode='cyl'}]            ->  [(('selectors',0,'mode'),'literal_error'), (('selectors',),'too_short')]
selectors=()                           ->  [(('selectors',),'too_short')]
```

That is actively misleading — it says the list was empty when it was not — and it makes the
genuinely-empty case indistinguishable from the one-bad-selector case, which is precisely the
distinction a producer debugging a failed seed needs. It would also break five existing exact-equality
error assertions in `tests/test_model_card.py` for no reason.

A `BeforeValidator` on the field runs against the raw input instead, and yields exactly one precise
error in every case — verified across the empty tuple, the empty list, a missing key, and each
single-invalid-selector form. So the non-empty check is a `BeforeValidator`, and the delta spec states
the **observable** guarantee (one error, located at `selectors`, no spurious companion) rather than the
mechanism, since that is what a consumer can actually depend on.

The cost is real and worth stating precisely, since decision 4's job is to price its own choice.
Measured: `Field(min_length=1)` puts `MinLen(min_length=1)` in `model_fields["selectors"].metadata`,
whereas the `BeforeValidator` puts `BeforeValidator(func=...)` there and **no `MinLen` at all**. So both
the machine-readable `too_short` error *type* and the introspectable length constraint are lost — a tool
that reads the constraint off the model rather than reading the spec cannot see a minimum length. That
is the price of one honest error instead of two confusing ones, and it is worth paying: the audience for
this error is a producer debugging a failed seed, not a schema-introspection tool, and `ModelCard` is
never emitted to JSON Schema for anything to introspect.

### 5. Duplicate and overlapping selectors are **not** rejected

Considered and declined. The producer de-duplicates during expansion (its design decision 3), so
duplicates should not arrive; and a duplicate selector is harmless under the any-selector rule — it
matches exactly what one copy would. Rejecting it would add a validator whose only effect is to fail a
card that is semantically fine, and would push a cosmetic producer bug into a hard read-path failure on
the consumer, which is the wrong side to fail on. #31 does not ask for it. Left out deliberately rather
than overlooked.

The same answer covers **overlapping-but-distinct** selectors (say canola/`cylinder`/2–13 alongside
canola/`cylinder`/5–20), which neither #31 nor the producer's de-duplication addresses, since de-duping
removes only exact repeats. Matching is a **disjunction** over selectors, not a lookup of one
distinguished selector, so overlap changes no selection outcome — a duplicate is just the degenerate
case of it. What overlap *does* threaten is the prose: "compare the age against **the** matching
selector's window" does not denote when two match, and a consumer reading it literally would write
`next(s for s in ...)` and either silently take the first or trip over the second. The delta therefore
says "**a** matching selector's window" and states the disjunction explicitly. Note also that the
guard against two *cards* claiming one context is the producer's, and its spec takes it on directly —
which is why this contract does not attempt a cross-card check either.

### 6. The any-selector rule is specified here even though selection lives in predict

`choose_models` is predict's, and this change adds no method. But the semantics of the field belong to
the contract that defines it: if predict re-derives them, "cross product" is the natural wrong reading,
and its failure mode is a *silent wrong match* — canola scored by a model never validated for canola in
that mode. There is direct precedent in this same requirement, which has always specified that the age
window is inclusive and assumed contiguous while stating that "the card never observes a scan's age."
So the rule goes in as normative prose, with no scenario claiming this library implements it.

The corollary is stated too, because it is the easiest thing to get wrong: age must be compared against
the **matching selector's** window, never a card-level min/max. A card whose selectors span 2–13 and
2–14 advertises neither globally, and a consumer that computed a card-level window would hand canola a
year of coverage it was never validated for.

### 7. No tolerant read — and why it is a requirement, not an omission

The decision and its evidence are #31's; not re-argued. What is decided here is that it becomes a
**named requirement** (`No Tolerant Read Of The Legacy Flat Card`) rather than simply being left out.

An omission is invisible. Someone hitting the migration window sees old cards being skipped, reaches for
the obvious fix, and re-introduces the outage; the state table lives in a closed issue and a
producer-side design doc in another repo, neither of which a future implementer greps. Writing it as a
requirement with the table attached puts the reasoning where the next person looks, and gives it
scenarios — a flat mapping fails, its flat keys are ignored rather than lifted, and the flat field names
are absent from `model_fields` — so a tolerant read cannot be added without visibly deleting a
requirement and reddening tests.

### 8. The delta uses MODIFIED for `Model Selection Card`, not REMOVED + re-ADDED

The sibling producer change had to REMOVE two requirements and re-ADD them under new names, because
their scenario *names* asserted the old rule (`Shared model expands per species`) and the archiver
hard-fails a MODIFIED block that omits any scenario name present in the current spec.

Checked all 16 scenario names on `Model Selection Card` against the reshape: **none of them asserts the
flat shape by name.** "Age window well-formedness is enforced", "mode is controlled", "Negative ages are
rejected" and the rest are behavior-neutral labels that stay true — the behavior still happens, one
level down. So MODIFIED is available, and it is the right choice: it preserves the requirement name that
`param-resolution` and the README both refer to, and it keeps the tightening work from
`tighten-model-card-validation` (archived 2026-07-31, shipped in `0.1.0a6`) intact instead of silently
dropping the `numpy.bool_`, container-of-bools, and unanticipated-input scenarios that a fresh ADDED
block would have had to remember to re-write.

All 16 names are therefore carried forward verbatim. Most needed only their WHEN clause re-plumbed
through a selector; **four** preserved THENs also changed, and every change tightens rather than
weakens. Two are on this requirement: `Age window well-formedness is enforced` gained the by-index
`loc` assertion (decision 3), and `The card is immutable` gained the nested-selector case. The other
two are on the remaining MODIFIED requirements: `A card built from merged metadata and identity
validates` now asserts the `selectors` are `Selector` **instances**, and `param-resolution`'s
`The resolved mode matches the seeded ModelCard mode vocabulary` now compares against the selector's
`mode`. Recorded exhaustively because a silently-weakened THEN is the one preservation failure neither
the archiver nor any validator checks. Three new scenarios join them (several
selectors on one card; an empty `selectors` is rejected; a card whose only selector is invalid reports
just that selector).

One consequence of carrying prose forward verbatim is worth flagging, because the first draft of this
delta got it wrong: a preserved clause can become **false** even when its SHALL is still true. The
`mode` paragraph read "the card SHALL NOT normalize case or whitespace, mirroring how `root_type` is
validated on the same model" — accurate while `mode` and `root_type` sat together, false once `mode`
moves to `Selector`. Since a MODIFIED block replaces the requirement wholesale, the archiver punishes
only *omission*, never rewording, so re-homing such a clause is free and skipping it would have
archived a false statement permanently. Every carried clause was re-read against the new shape for
this, not just checked for presence.

The same check was run on `Tolerant Construction From Registry Metadata`: both its scenario names are
neutral, so MODIFIED again, with two scenarios added for the two metadata-coercion shapes (see 10).

### 9. `param-resolution` is in scope, and only one of its requirements is

`openspec/specs/param-resolution/spec.md:185` has a scenario whose WHEN is "a `ModelCard` is
constructed with `mode="cylinder"`". After this change that construction raises, so the scenario is not
merely stale prose — it is unsatisfiable, and archiving without touching it would leave a permanent spec
statement that no implementation can honor. Hence the MODIFIED block for `Imaging Mode Resolution Seam`,
preserving all three of its scenario names and rewriting the one WHEN plus the sentence naming the card
mode vocabulary.

**`Species Name Normalization` (same requirement's neighbour, at lines 116 and 121) was reviewed and
deliberately left alone — but on a narrower ground than "it is still accurate."** It says the resolver
normalizes to "the `ModelCard` species vocabulary" and that "the registry/`ModelCard`s are the single
authority on which species have models." The second is fully true. The first is *imprecise* in exactly
the way the mode sentence was: species now lives on `Selector.species`, so "the `ModelCard` species
vocabulary" names a vocabulary the card no longer carries directly.

So the honest statement of this decision is not that there is nothing to fix, but that **the fix is not
worth the re-paste risk**: MODIFIED-ing that requirement means reproducing seven scenarios verbatim, and
a dropped scenario there is an archive failure or a silent spec loss — the exact hazard this change is
being careful about — in exchange for tightening one adjectival phrase that misleads nobody, since the
card remains the authority and the delta's new `Bundled Selection Selector` requirement says plainly
that `species` is uncontrolled and why. The mode sentence earns its edit because its requirement had to
be MODIFIED anyway for the unsatisfiable scenario; this one does not.

`tasks.md` 6.9 re-confirms the judgment after the dry-run rather than assuming it still holds. Recorded
at this length because an earlier draft justified the omission by claiming the prose was simply accurate,
which its own sibling edit contradicts.

### 10. The read path guarantees the JSON-native form, and refuses the coerced one

From the producer's risk analysis, verified against the pinned writer: `wandb.Artifact(metadata=...)`
runs the mapping through `validate_metadata`, which **coerces rather than rejects** non-JSON-native
values. A tuple of `Selector` models — the most natural thing for a producer to pass, since it already
has them — comes back as a list of `repr` strings (`"species='canola' …"`); a `NamedTuple` comes back as
a positional list with the field names gone. Both publish unreadable selection metadata with a
successful exit code.

The contract cannot stop the producer from doing that, but it can make the failure loud on read, and
it should, because this is the one failure mode that survives a green producer test run. So the delta
states that `selectors` validates from a list of plain dicts, and adds a scenario per coercion shape
asserting that neither a list of `repr` strings nor a positional list validates. Those two are the
valuable ones: they are the regression tests for a silent-corruption path, and the positional case is
the nastier of the two, since a list of the right length would otherwise be a candidate for
field-order-dependent interpretation.

## Risks

- **The reshape and its test rewrite are atomic, but adding `Selector` is not.** An earlier draft
  claimed §2 had to be a single commit because "every test builds a flat card, so there is no
  incremental green state." Measured, that is wrong twice over. Of the 29 test functions in
  `tests/test_model_card.py`, **20 need edits and 9 pass unchanged**; and `make_card` (line 15) is a
  plain module-level helper, not a pytest fixture. More importantly, **adding `Selector` on its own is
  green**: it is purely additive, touches no existing model, and cannot perturb `schema/*.json` because
  nothing in `ResultEnvelope`'s field graph reaches it. So the plan is two green code commits — add and
  prove `Selector`, then reshape `ModelCard` with its test rewrite — not one. What *is* genuinely
  atomic is the second commit: the moment `ModelCard` loses its flat fields, `make_card` and the 20
  dependent tests must move with it.
- **Reusing `_check_age_range` by moving it hides a scope error.** Moved onto `Selector` it validates a
  selector's own bounds — correct. But nothing then validates any *relationship between* selectors, and
  nothing should; a reviewer expecting a card-level window check will find none. Stated here so its
  absence is not mistaken for an oversight.
- **An old-pinned consumer reading a new card fails rather than degrades.** `extra="ignore"` means it
  drops the unknown `selectors` and then fails on the missing flat required fields. That is the intended
  outcome — see requirement `No Tolerant Read Of The Legacy Flat Card` — and it is why the producer's
  re-seed is additive and the old collections keep their alias until predict is confirmed deployed. The
  compatibility cliff is the producer's retirement step, not anything in this repo.
- **Archiving is the irreversible step, and whether validation gates it depends on the CLI version.**
  On **1.5.0 through 1.7.0**, `openspec validate --strict` passes on deltas the archiver rejects: it
  does not check that a MODIFIED block preserves the current spec's scenario names. **1.8.0 added that
  check** — verified by deleting a preserved scenario in a throwaway copy, where 1.8.0's `validate
  --strict` fails with "omits scenario(s) the current spec still has" while 1.5.0/1.6.0/1.7.0 all
  report valid. So the safety net exists only on the newest binary, and only for the *scenario-name*
  half of the hazard: **no** version checks that a normative prose clause survived, and none checks
  that a preserved clause is still *true* (see decision 8's `mode`-paragraph note). `tasks.md` §6
  therefore still dry-runs `archive` into a throwaway copy and diffs the result, asserting that
  `Model Card To ModelRef Conversion` comes out **byte-identical**, and runs validation on the oldest
  and newest binaries available rather than one.
- **Validation is CLI-version dependent in the other direction too.** 1.5.0 rejects a requirement whose
  SHALL wraps past the first line while 1.6.0+ accepts it, so every requirement here opens with SHALL
  on line one and the gate runs 1.5.0 as well as 1.8.0. Neither binary is on `PATH` — they live in the
  npx cache.
