# model-selection-contract Specification

## Purpose

Defines the contract by which a trained model advertises **what it may be used for**, so that a
producer publishing weights and a consumer selecting them agree without coordinating out of band.

The unit is the `ModelCard`: one card describes one **physical model** — a scalar `root_type` and
`sleap_nn_version`, both intrinsic to the weights, plus a non-empty list of `Selector`s naming every
`(species, mode, age_min, age_max)` context the model was actually validated for. Matching is the
**any-selector** rule: a card serves a request when *some single* selector matches all of species,
mode and age. It is deliberately not the cross product of independent fields, because that would let
a generalist model advertise combinations nobody trained; and there is deliberately no card-level age
window, because a card whose selectors span 2-13 and 2-14 advertises neither globally — age must be
read against the *matching* selector.

The contract is validation, not selection: it decides whether a card is well-formed and what it
claims, while which card wins a given request belongs to the consumer. Its job is to make sure at
most one card can honestly answer, and that an ill-formed card fails loudly at the producer rather
than silently mis-matching at the consumer.

## Requirements

### Requirement: Bundled Selection Selector

The library SHALL define an immutable (`frozen`) `Selector` model, importable from the package root
and present in `__all__`, that carries **one whole validated selection context** for a model:
`species` (str), `mode` drawn from the controlled vocabulary
`Mode = {cylinder, multiplant cylinder, plate}`, and an inclusive approved selection window
`age_min`/`age_max` (ints, each `>= 0`, with `age_min <= age_max`). The four fields are a unit: a
`Selector` asserts that the model was validated for *that* species in *that* mode over *that* age
window, and asserts nothing about any other combination of the same values.

`age_min` and `age_max` SHALL share the library's `NonBoolInt` guard and its `age_min <= age_max`
ordering check rather than restating either, so a selector age bound and every other curated age bound
in the library behave identically — including the `numpy.bool_` rejection and the lax parsing of `"7"`,
`7.0`, and `numpy.int64`. Sharing one implementation is an implementation obligation rather than
observable behavior; the observable guarantee is that equivalence, which the scenarios below and under
`Model Selection Card` pin.

`Selector.mode` SHALL be matched exactly against the vocabulary, with **no** normalization of case or
whitespace — the same treatment `root_type` gets on the card. Tolerant handling of a scan's
*requested* mode remains the responsibility of `resolve_params`, which normalizes and then degrades an
unmodelled value to a selection zero-match rather than an error; this requirement governs the selector
only.

`species` SHALL remain a plain `str` with no controlled vocabulary, because the registry's cards are
the single authority on which species have models and `resolve_params` deliberately lets an unmodelled
species pass through to a selection zero-match rather than rejecting it.

`Selector` SHALL be `frozen`, which makes `ModelCard`'s own immutability deep rather than shallow — a
mutable nested model would let `card.selectors[0].species` be reassigned on a card that advertises
itself as frozen, since the `tuple` annotation protects the sequence but not its elements. Being
`frozen` also makes a `Selector` hashable, which is what lets a producer de-duplicate selectors with a
`set` when several matrix rows contribute the same context to one physical model.

`Selector` SHALL set `extra="ignore"` explicitly, for the same load-bearing reason `ModelCard` does:
selectors arrive as nested mappings inside a raw wandb metadata blob, and a consumer pinned to an
older contract must tolerate a selector field added by a newer producer rather than failing the whole
card. `Selector` is a Python-side producer contract and SHALL NOT appear in any emitted JSON Schema.

#### Scenario: A valid selector is constructed
- **WHEN** a `Selector` is built with a `species`, a `mode` in the vocabulary, and `age_min <= age_max`
- **THEN** construction succeeds and the four field values are retained

#### Scenario: A selector enforces its own age bounds
- **WHEN** a `Selector` is built **on its own** with `age_min` greater than `age_max`, with a negative
  bound, or with a `bool` or `numpy.bool_` bound
- **THEN** validation raises an error in every case, because the age rules live on `Selector` itself
  and are not merely enforced by whatever contains it

#### Scenario: A selector enforces its own mode vocabulary
- **WHEN** a `Selector` is built **on its own** with a `mode` outside
  `{cylinder, multiplant cylinder, plate}`, or with a differently-cased or space-padded spelling of a
  member
- **THEN** validation raises an error, because the value is matched exactly and the selector does not
  normalize it

#### Scenario: An unmodelled species is accepted
- **WHEN** a `Selector` is built with a `species` no model was ever trained for (e.g. `"sorghum"`)
- **THEN** construction succeeds, because `species` carries no vocabulary — the registry's cards are
  the authority, and an unmodelled species is meant to degrade to a selection zero-match rather than a
  validation error

#### Scenario: A selector is immutable
- **WHEN** a field is reassigned on a standalone `Selector`
- **THEN** the assignment raises an error, which is what keeps a `ModelCard` immutable through its
  selectors — the card-level consequence is pinned separately under `Model Selection Card`

#### Scenario: A selector is hashable so a producer can de-duplicate
- **WHEN** two `Selector`s carrying identical field values are added to a `set`
- **THEN** the `set` holds exactly one element, so a producer collapsing several matrix rows onto one
  physical model can de-duplicate identical contexts without comparing fields by hand

#### Scenario: A selector tolerates an unknown nested key
- **WHEN** `Selector.model_validate(mapping)` is called where `mapping` carries the four known fields
  plus a key not defined on the model
- **THEN** validation succeeds and the extra key is ignored, so a newer producer adding a selector
  field does not make the card unreadable to an older consumer

#### Scenario: Selector is absent from every emitted schema
- **WHEN** each emitted JSON Schema is generated
- **THEN** `Selector` is not present among any of their `$defs`

### Requirement: Model Selection Card

The library SHALL define an immutable (`frozen`) `ModelCard` model that carries a production model's
selection metadata and the identity of its concrete registry artifact, importable from the package
root. One card describes **one physical model**. Its selection fields SHALL be `root_type` drawn from
the controlled vocabulary `RootType = {primary, lateral, crown}` and a non-empty `selectors`
(`tuple[Selector, ...]`) listing every selection context the model was validated for. Its identity
fields SHALL be `registry_id` (str), `version` (str), and an optional `weights_checksum`. The card
SHALL also carry an optional trained-with `sleap_nn_version`. Each selector's age window represents
the model's curated approved selection range for *that* context (which MAY be wider than its training
ages) and is assumed contiguous; the card never observes a scan's age.

`selectors` SHALL be rejected when empty: a card with no selection context is unselectable, so it is a
producer bug rather than a model that simply matches nothing. An empty `selectors` SHALL surface as a
**single** error located at `selectors`; conversely, a card whose `selectors` is non-empty but whose
only selector is invalid SHALL report **only** that selector's error and SHALL NOT additionally be
reported as empty. Keeping those two apart is the point rather than a detail: they are different
producer bugs, and reporting "the list is empty" for a card that supplied a selector misdescribes the
input and makes the genuinely-empty case indistinguishable from a merely-bad one.

A card SHALL be matched as follows: the card's scalar `root_type` is matched at the card level, and the
remaining axes are matched by the **any-selector** rule — a card matches a requested
(species, mode, age) when **some single selector on it matches all three**. A card SHALL NOT be matched
on the cross product of its selectors' values. This is what makes one card per physical model honest —
a generalist primary-root model serving canola in `cylinder` and arabidopsis in `multiplant cylinder`
must not thereby advertise canola in `multiplant cylinder`, a combination nobody trained. It equally
means a consumer SHALL compare a scan's age against **a matching selector's** window and never against
a card-level minimum or maximum, since a card whose selectors span 2–13 and 2–14 advertises neither
window globally. Matching is a disjunction over selectors rather than a lookup of one distinguished
selector, so a card whose selectors overlap for a given context is well-defined and selects the same
way. Selection itself lives in `sleap-roots-predict`'s `choose_models`; this requirement fixes the
semantics that consumer implements, in the same way this requirement has always fixed the meaning of
the age window without the card ever observing an age.

`root_type` SHALL stay scalar rather than moving into the selector, because it is intrinsic to the
weights: a primary-root model is never also a lateral one. Verified against the live selection matrix,
each physical model maps to exactly one root type. `sleap_nn_version` SHALL likewise stay a scalar
card-level field, because it describes the weights rather than a selection context.

A selector's `mode` SHALL be matched exactly against the vocabulary: the selector SHALL NOT normalize
case or whitespace, mirroring how `root_type` is validated on the card. Tolerant handling of a
scan's *requested* mode remains the responsibility of `resolve_params`, which normalizes and then
degrades an unmodelled value to a selection zero-match rather than an error; this requirement
governs the card and its selectors only.

A selector's `age_min` and `age_max` SHALL reject a `bool` rather than coerce it to `1`/`0`, while
leaving ordinary lax integer parsing (for example `"7"`, `7.0`, or a `numpy.int64`) unaffected. The
rejection SHALL cover a `numpy.bool_` as well as the builtin `bool`: `numpy.bool_` is not a `bool`
subclass, so a check that tests only for the builtin would let it through and read it as `1`/`0`.
The bool check SHALL apply to scalars only — a *container* of bools is not a bool, and SHALL be
rejected as a non-integer like any other container. Whatever the input, an invalid age bound SHALL
surface as a validation error and SHALL NOT propagate any other exception to the caller. Since the
bounds live on `Selector`, every one of these rules SHALL reach the card through its selectors:
an invalid bound anywhere in `selectors` SHALL fail construction of the whole card.

An invalid selection value reaches the card as a **mapping**, not as a `Selector` object, because a
`Selector` carrying an invalid value cannot be constructed at all. The scenarios below that describe a
card built from a mapping whose selector holds an invalid value are therefore satisfied through
`ModelCard.model_validate({..., "selectors": [{...}]})`, and validation errors from that path SHALL
locate the offending selector by index within `selectors`.

`ModelCard` is a Python-side producer contract and SHALL NOT appear in any emitted JSON Schema.

#### Scenario: A valid card is constructed
- **WHEN** a `ModelCard` is built with a `root_type` in the vocabulary, a non-empty `selectors` whose
  every selector is valid (`age_min <= age_max`, `mode` in its vocabulary), and identity fields
  (`registry_id`, `version`)
- **THEN** construction succeeds and the field values are retained

#### Scenario: A card carries several selectors for one physical model
- **WHEN** a `ModelCard` is built with several selectors — for example canola/`cylinder`/2–13 and
  pennycress/`cylinder`/2–14 — pointing at one set of weights
- **THEN** construction succeeds and all of them are retained in order, so one card can describe a
  generalist model without being registered once per species

#### Scenario: Overlapping or duplicate selectors are accepted
- **WHEN** a `ModelCard` is built with two selectors that match the same context — either byte-identical,
  or distinct but with overlapping age windows (e.g. canola/`cylinder`/2–13 alongside
  canola/`cylinder`/5–20)
- **THEN** construction succeeds and both are retained, because matching is a disjunction over
  selectors rather than a lookup of one distinguished selector: two matching selectors still make the
  card match exactly once, so neither is a validity problem. Rejecting them would fail a card that is
  semantically fine and turn a cosmetic producer bug into a hard read-path failure on the consumer,
  which is the wrong side to fail on — de-duplication is the producer's job

#### Scenario: An empty selectors list is rejected
- **WHEN** a `ModelCard` is built with `selectors` given as an empty tuple, or as an empty list
- **THEN** validation raises exactly one error, located at `selectors`, in both cases

#### Scenario: A card whose only selector is invalid reports just that selector
- **WHEN** a `ModelCard` is built from a mapping whose `selectors` holds a single invalid selector
- **THEN** validation reports exactly one error, locating that selector by index, and does **not**
  additionally report `selectors` as empty — the input had a selector, it was merely a bad one

#### Scenario: Age window well-formedness is enforced
- **WHEN** a `ModelCard` is built from a mapping whose selector has `age_min` greater than `age_max`
- **THEN** validation raises an error, and the error locates the offending selector by index within
  `selectors` rather than reporting a card-level field

#### Scenario: Negative ages are rejected
- **WHEN** a `ModelCard` is built from a mapping whose selector carries a negative `age_min` or
  `age_max`
- **THEN** validation raises an error

#### Scenario: A single-age, zero-inclusive window is valid
- **WHEN** a `ModelCard` is built with a selector whose `age_min` equals its `age_max` (e.g. both `0`,
  or both `7`)
- **THEN** construction succeeds, because the window is inclusive and `0` is an allowed bound

#### Scenario: A bool age bound is rejected rather than coerced
- **WHEN** a `ModelCard` is built from a mapping whose selector has `age_min` or `age_max` given as
  `True` or `False`
- **THEN** validation raises an error naming the bool, rather than coercing it to `1`/`0` and
  yielding a card that claims a plausible-but-wrong selection window

#### Scenario: A numpy bool age bound is rejected too
- **WHEN** a `ModelCard` is built from a mapping whose selector has an age bound given as a
  `numpy.bool_`
- **THEN** validation raises the same error, because `numpy.bool_` is not a `bool` subclass and
  would otherwise be read as `1`/`0` — the card must not be looser than `resolve_params`, which
  already refuses a `numpy.bool_` age

#### Scenario: A container of bools is rejected as a non-integer
- **WHEN** a `ModelCard` is built from a mapping whose selector has an age bound given as a
  one-element array of bools
- **THEN** validation raises a non-integer type error rather than reporting a bool, because the
  bool check applies to scalars and a container of ints in the same position is rejected the same way

#### Scenario: An unanticipated input still surfaces as a validation error
- **WHEN** a `ModelCard` is built from a mapping whose selector has an age bound whose scalar-unwrap
  raises an unexpected error
- **THEN** validation raises a validation error rather than propagating that error to the caller,
  because the guard is duck-typed and callers of `model_validate` handle only validation errors

#### Scenario: A fractional age bound is rejected rather than truncated
- **WHEN** a `ModelCard` is built from a mapping whose selector has an age bound given as `7.5` or
  `"7.5"`
- **THEN** validation raises an error rather than truncating to `7` and shifting which scans the
  model claims, mirroring how `resolve_params` refuses a non-integral age

#### Scenario: Lax integer parsing of the age bounds is preserved
- **WHEN** a `ModelCard` is built with a selector age bound given as `"7"`, `7.0`, or a `numpy.int64`
- **THEN** construction succeeds and the bound reads as the integer `7`

#### Scenario: root_type is controlled
- **WHEN** a `ModelCard` is built with a `root_type` outside `{primary, lateral, crown}`
- **THEN** validation raises an error

#### Scenario: mode is controlled
- **WHEN** a `ModelCard` is built from a mapping whose selector has a `mode` outside
  `{cylinder, multiplant cylinder, plate}` — for example the label registry's `cyl` shorthand, or a
  differently-cased `Cylinder`
- **THEN** validation raises an error

#### Scenario: Every mode in the vocabulary is accepted
- **WHEN** a `ModelCard` is built with a selector carrying each member of
  `{cylinder, multiplant cylinder, plate}` in turn
- **THEN** construction succeeds in every case and the value is retained unchanged

#### Scenario: The trained-with version is optional
- **WHEN** a `ModelCard` is built without a `sleap_nn_version`
- **THEN** construction succeeds and `sleap_nn_version` is `None`

#### Scenario: The card is immutable
- **WHEN** a card field (e.g. `registry_id`) is reassigned on a constructed `ModelCard`, or a field on
  one of its `Selector`s is reassigned
- **THEN** the assignment raises an error in both cases, so the card's immutability is deep rather
  than only covering its own attributes

#### Scenario: ModelCard is absent from the emitted result schema
- **WHEN** the `result_envelope` JSON Schema is generated
- **THEN** `ModelCard` is not present among its `$defs`

### Requirement: Model Card To ModelRef Conversion

`ModelCard` SHALL provide `to_model_ref(runtime_sleap_nn_version)` returning a `ModelRef` that pins
the card's `registry_id`, `version`, `root_type`, and `weights_checksum`, and stamps
`ModelRef.sleap_nn_version` with the **runtime** sleap-nn version passed in (not the card's
trained-with value). The method SHALL be pure and SHALL NOT emit warnings; comparing the runtime
version against the card's trained-with value is the reader's responsibility.

#### Scenario: to_model_ref stamps the runtime sleap-nn version
- **WHEN** `to_model_ref("runtime-x")` is called on a card whose trained-with `sleap_nn_version`
  differs from `"runtime-x"` (or is `None`)
- **THEN** the returned `ModelRef` has `sleap_nn_version == "runtime-x"` and carries the card's
  `registry_id`, `version`, `root_type`, and `weights_checksum`

### Requirement: Tolerant Construction From Registry Metadata

`ModelCard` SHALL validate successfully from a mapping that merges training-written selection metadata
with the artifact-intrinsic identity fields, and SHALL ignore extra keys not defined on the model, so
that a card can be built from a raw wandb metadata blob (boolean tag flags, spread training config,
eval metrics) merged with the artifact's identity without those extras causing failure.

The selection half of that mapping SHALL be readable in **JSON-native** form: `selectors` SHALL
validate from a list of plain dicts, because wandb artifact metadata is a JSON blob and cannot carry
Python objects. This is worth stating rather than assuming, because `wandb.Artifact(metadata=...)`
*coerces* rather than rejects non-JSON-native values. Verified against the pinned writer by the
producer: a tuple of `Selector` pydantic models — the most natural thing for a producer to pass, since
it already has them — comes back from the round trip as a list of `repr` **strings**, and a
`NamedTuple` comes back as a positional list with the field names gone. Both would publish unreadable
selection metadata with a successful exit code. The contract cannot prevent that write, but its read
path SHALL make it loud: the list-of-dicts form is guaranteed to work, and neither coerced form SHALL
validate.

#### Scenario: A card built from merged metadata and identity validates
- **WHEN** `ModelCard.model_validate(mapping)` is called where `mapping` merges the selection metadata
  (`root_type` and a `selectors` list of dicts, each carrying `species`, `mode`, `age_min`, `age_max`)
  with the artifact identity (`registry_id`, `version`)
- **THEN** validation succeeds and yields a full card whose `selectors` are `Selector` instances

#### Scenario: Extra metadata keys are tolerated
- **WHEN** `ModelCard.model_validate(mapping)` is called where `mapping` also contains keys not
  defined on the model (e.g. `soybean: True`, `oks_map: 0.8`, a nested `training_config`)
- **THEN** validation succeeds and the extra keys are ignored

#### Scenario: A repr-coerced selector list does not silently validate
- **WHEN** `ModelCard.model_validate(mapping)` is called where `selectors` is a list of `repr`
  strings — the shape `wandb.Artifact`'s metadata coercion produces from a tuple of pydantic models
- **THEN** validation raises an error rather than accepting the strings, so a producer that passed
  model objects instead of dicts fails loudly instead of publishing unreadable metadata

#### Scenario: A positionally-coerced selector list does not silently validate
- **WHEN** `ModelCard.model_validate(mapping)` is called where a selector is a positional list with
  its field names gone (e.g. `["canola", "cylinder", 2, 13]`) — the shape that coercion produces from
  a `NamedTuple`
- **THEN** validation raises an error rather than mapping the values onto fields by position, which
  would silently accept a reordering as a different selection context

### Requirement: No Tolerant Read Of The Legacy Flat Card

`ModelCard` SHALL NOT accept the legacy flat card shape, and SHALL NOT lift a flat card into a
single-selector card. A mapping carrying card-level `species`/`mode`/`age_min`/`age_max` but no
`selectors` SHALL fail validation on the missing `selectors`, and its flat keys SHALL be ignored as
ordinary extras rather than interpreted.

This is stated as a requirement rather than left implicit because a tolerant read is the intuitive
migration aid, it was the standing recommendation for several review rounds, and it was reversed on
evidence about the *consumer* rather than about this contract. `sleap-roots-predict` skips a card it
cannot validate, per artifact, with a warning, without aborting the listing, and its `choose_models`
raises when more than one card matches a selection context (established in
talmolab/sleap-roots-predict#32 and resolved against predict's code on 2026-08-11). Working the states
through against the producer's additive re-seed, in which the new selector cards appear under new
collection ids while the old flat collections keep their `production` alias:

| consumer contract | old flat cards | new selector cards | matches per context | outcome |
|---|---|---|---|---|
| old pin | valid, listed | fail on missing required fields, skipped | 1 | works |
| new pin **with** tolerant read | lifted to one selector, valid, listed | valid, listed | **2** | **raises** |
| new pin **without** tolerant read | `selectors` missing, skipped | valid, listed | 1 | works |

Skip-with-a-warning therefore already supplies the graceful degradation a tolerant read was meant to
supply, and supplies it in **both** directions. A tolerant read would not remove a migration window;
it would manufacture an ambiguous match inside one, throwing an unhandled `ValueError` on live traffic
the moment the first new collection picked up the `production` alias. Omitting it also removes the
"two valid production cards for one selection context" state permanently rather than surviving it
once.

Dual-writing both shapes for one release is ruled out for a second, independent reason: a card serving
four species has no honest value to put in a scalar card-level `species`, so any value chosen would be
wrong for three of them and an old-pinned consumer would make a *silently wrong* selection instead of
failing loudly.

#### Scenario: A legacy flat card fails validation
- **WHEN** `ModelCard.model_validate(mapping)` is called with the legacy flat shape
  (`species`, `mode`, `age_min`, `age_max`, `root_type`, `registry_id`, `version`) and no `selectors`
- **THEN** validation raises an error reporting `selectors` as missing, rather than succeeding

#### Scenario: The flat keys are ignored, not lifted
- **WHEN** that same flat mapping is given a valid `selectors` whose single selector disagrees with
  the flat `species`/`mode`/`age_min`/`age_max` values
- **THEN** validation succeeds and the card reflects only the `selectors`, with no card-level
  attribute carrying the flat values — confirming the flat keys were dropped as extras rather than
  merged, lifted, or preferred

#### Scenario: The flat selection fields are absent from the model
- **WHEN** `ModelCard.model_fields` is inspected
- **THEN** `species`, `mode`, `age_min`, and `age_max` are absent, so no code can read a card-level
  value for them and no producer can set one
