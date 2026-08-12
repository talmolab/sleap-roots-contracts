# Proposal: Add `Selector` and reshape `ModelCard` to carry bundled selectors

## Why

`ModelCard.species` is a scalar `str`, so a model validated for several species must be registered
once per species. In the live registry that is **13 `ModelCard` registrations backed by 8 physically
distinct model files**, with one generalist primary-root model registered four times. Give a card a
bundled selector list instead and one card describes one physical model, taking registrations to
exactly 8. Tracking issue: talmolab/sleap-roots-contracts#31.

## Background

The duplication is a limitation of **this** contract, not of wandb. A wandb `ArtifactCollection`
exposes only `description` and `tags` and appears unable to carry its own structured metadata, so the
`ModelCard` blob lives on `Artifact.metadata` and is shared by every collection the artifact is linked
into. Under a scalar `species`, linking one artifact into four collections would give all four a blob
whose single `species` is whichever card published it, silently breaking selection for the other three.
So the storage-dedup workaround is unavailable *because* of the card shape.

Carrying the producer's caveat rather than dropping it: that finding is offline API-surface
introspection against the pinned writer, **not** a live test against the production registry, and
registry collections may differ from ordinary project artifact collections in ways the local classes do
not reveal. It is strong evidence about the shape and it is not load-bearing for this change — the
reshape is justified by the contract's inability to express a generalist model either way — but anything
built *on* link-into-many later must verify it live first.

**Widening `species` to a tuple does not fix it.** Measured against the live selection matrix it
removes 1 of the 5 redundant registrations (13 → 12), because species is not the only axis the same
weights repeat across: the `arabidopsis/lateral` pair differs only by **mode**, and the
canola/pennycress lateral pair differs by species **and** age window, so tupling species leaves the age
difference behind.

**Tupling `species` and `mode` independently is worse.** A card would then match the *cross product*
of its axes and advertise combinations nobody trained — for example canola in `multiplant cylinder`.
Silent wrong matches are worse than duplicated registrations.

The producer-side analysis, including the per-model breakdown and the 1-of-5 measurement regenerated
from the committed matrix, is talmolab/sleap-roots-training#47. This change is the contract half and
must land first: that repo cannot bump a pin that does not exist.

## What Changes

**BREAKING** — a shape change to a released contract (`ModelCard` shipped in `0.1.0a3`).

```python
class Selector(BaseModel):          # NEW, frozen, extra="ignore"
    species: str
    mode: Mode
    age_min: NonBoolInt = Field(ge=0)
    age_max: NonBoolInt = Field(ge=0)

class ModelCard(BaseModel):         # reshaped
    root_type: RootType
    selectors: tuple[Selector, ...]     # non-empty
    registry_id: str
    version: str
    weights_checksum: str | None = None
    sleap_nn_version: str | None = None   # stays card-level: describes the weights
```

- **Add `Selector`**, one whole validated `(species, mode, age_min, age_max)` context. Its age bounds
  **reuse** the existing `NonBoolInt` guard and the existing `age_min <= age_max` ordering check rather
  than restating either, so a selector age bound behaves exactly as a card age bound did.
- **`ModelCard` becomes `root_type` + `selectors` + identity**, and rejects an empty `selectors`.
  Card-level `species`/`mode`/`age_min`/`age_max` are removed.
- **`root_type` stays scalar** — intrinsic to the weights, and verified: each of the 8 physical models
  maps to exactly one root type. `sleap_nn_version` stays scalar for the same reason.
- **Matching is the any-selector rule** — the card's scalar `root_type` is matched card-level, and a
  card matches a requested (species, mode, age) when *some single* selector matches all three, never on
  the cross product. Matching is a disjunction over selectors, not a lookup of one distinguished
  selector, so overlapping selectors stay well-defined. Selection itself stays in
  `sleap-roots-predict`'s `choose_models`; this change fixes the semantics that consumer implements,
  the way the spec has always fixed the meaning of the age window without the card observing an age.
  (#31 phrases this as "any selector match all four fields", counting the window's two bounds
  separately; the three-axis phrasing here is the same rule stated against what a request carries.)
- **No tolerant read of the legacy flat shape**, written as its own requirement so the decision is
  permanently greppable rather than an absence. See Design; reversing it would manufacture an
  ambiguous match on live traffic.

## Impact

- **Affected specs:** `model-selection-contract` (2 MODIFIED, 2 ADDED) and `param-resolution`
  (1 MODIFIED). The `param-resolution` edit is not cosmetic: its `Imaging Mode Resolution Seam`
  scenario *constructs* `ModelCard(mode="cylinder")`, which this change makes impossible, so leaving it
  would put an unsatisfiable scenario in the permanent spec. `Model Card To ModelRef Conversion` is
  deliberately **untouched** — `to_model_ref` pins `registry_id`, `version`, `root_type`, and
  `weights_checksum`, none of which move.
- **Affected code:** `src/sleap_roots_contracts/models.py` (add `Selector`, reshape `ModelCard`, move
  `_check_age_range` onto `Selector`, rewrite the `ModelCard` docstring **and** the four comment blocks
  outside it that state the flat shape as fact — `models.py:71`, `:216`, `:225-231`, and `:416`, the
  last a dangling reference to the `ModelCard._check_age_range` this change deletes);
  `__init__.py` (export `Selector`); and `params.py:158` and `:142`, whose docstrings say `Mode` types
  `ModelCard.mode` and that "`ModelCard`/`LabelCard` match `Mode` exactly" — `:158` is the docstring of
  the very function whose requirement this change modifies, so leaving it would make the spec and its
  implementation contradict each other on day one. `params.py`'s three looser "`ModelCard` species
  vocabulary" mentions (`:50`, `:114`, `:120`) are left as-is — imprecise but harmless for the reason
  Design decision 9 gives, since the card remains the authority on which species have models. `:5` needs
  nothing: it says the resolved params "select a `ModelCard`", which stays true.
- **Affected tests:** `tests/test_model_card.py` — 20 of its 29 tests need edits. Most reach the card
  through the `make_card` helper (line 15), but **three do not** and are easy to miss:
  `test_model_card_from_merged_metadata`, `test_model_card_tolerates_extra_keys`, and
  `test_model_card_guards_apply_via_model_validate` build card mappings inline, and the first two are
  the only tests behind the `Tolerant Construction From Registry Metadata` scenarios. Also
  `tests/test_params.py` (its `_card` helper and the one mode-vocabulary agreement test that uses it).
  Five tests assert exact error `loc`s or error lists and must be re-pointed under `selectors`; one
  immutability test would otherwise keep passing while asserting on a deleted field.
- **Affected docs:** `README.md`'s model-selection paragraph names `mode` as a card field, and its next
  paragraph claims `Mode` types `mode` on "both cards"; **`openspec/project.md`** says the same thing
  twice (lines 22-23 and 107-109) and is the conventions file loaded into agent context, so a stale
  copy there mis-teaches every future change; `docs/01-contract-library-design.md` (its running
  staleness banner, not its frozen body); `docs/CHANGELOG.md`. The `model-selection-contract` spec
  Purpose is still a literal `TBD` placeholder and is fixed at the archive gate. The four dated
  `docs/superpowers/specs/*.md` design records are deliberately **not** touched — they are historical.
- **Affected release artifacts:** `pyproject.toml`, `uv.lock` (CI runs `uv lock --check`), and both
  committed `schema/*.json` files, whose `$id` carries the package version and is drift-guarded in CI.
- **Release:** its own pre-release, **`0.1.0a8`**, and its own changelog line. `0.1.0a7` is already on
  PyPI, so nothing can ride an unreleased version this time. **Do not yank or delete the pre-release
  once published** — the consumer repos pin it in `uv.lock` with sdist and wheel hashes, so a vanished
  version fails `uv sync --locked` on every CI leg until the lock is regenerated.
- **Consumers, and the ordering that matters.** Contracts releases, then `sleap-roots-training`
  re-seeds the registry, then `sleap-roots-predict` **deploys**, then the old collections are retired.
  Predict may merge and pin at any time; only its deploy is ordered, because without a tolerant read an
  upgraded predict deployed before the re-seed would skip all 13 old collections and find nothing to
  select. Neither of those repos' work is tickable here; both are recorded as prerequisites in
  `tasks.md` §7 so this change stays archivable.
- **One downstream consequence, for the record.** `registry_id` is an input to this library's
  `compute_idempotency_key`, so the producer renaming every collection resets Bloom's idempotency keys
  even though `weights_checksum` is unchanged. Accepted on the producer side, since that pipeline is
  not in production yet. Nothing in this repo changes for it.

## Out of scope

- **Deriving or validating age windows from `LabelCard`s** — talmolab/sleap-roots-training#46. This
  change deliberately does not decide whether canola's window should extend to 14: under bundled
  selectors it does not need to, since canola keeps a 2–13 selector while pennycress keeps 2–14 on the
  same card.
- **A matching helper on `ModelCard`.** #31's approved shape carries no method, and `choose_models`
  lives in predict. This change specifies the any-selector semantics without implementing selection.
- **Rejecting duplicate or overlapping selectors.** The producer de-duplicates before writing, and
  matching is a disjunction so overlap is well-defined; see Design decision 5 for why the contract does
  not also enforce uniqueness.
- **Consolidating `LabelCard`'s duplicate `_check_age_range`.** Moving the model-side check onto
  `Selector` makes the label-side copy visibly redundant, but `LabelCard` stays flat and out of scope
  here. Noted so the duplication is a known deferral rather than a new one.
