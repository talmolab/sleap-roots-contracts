# Tasks: add `Selector` and reshape `ModelCard`

Sequencing, corrected after measuring the suite rather than assuming: **adding `Selector` is additive
and green on its own**, so §2 and §3 are two separate RED→GREEN commits, not the single commit an
earlier draft claimed was forced. What *is* atomic is §3: the moment `ModelCard` loses its flat fields,
`make_card` and the 20 affected tests in `tests/test_model_card.py` must move with it. §4 (docs) and §5
(release) are separately green; §6 is the archive gate and runs last.

Measured baseline for `tests/test_model_card.py`: 29 test functions; 24 route through the `make_card`
helper (line 15, a plain helper — **not** a pytest fixture); **20 need edits and 9 do not**. Those two
sets are *not* nested — the overlap is 17, and three tests need edits without touching `make_card`:
`test_model_card_from_merged_metadata` (:297), `test_model_card_tolerates_extra_keys` (:313), and
`test_model_card_guards_apply_via_model_validate` (:340), all of which build card mappings inline. The
first two are the only tests behind the `Tolerant Construction From Registry Metadata` scenarios, so
they are called out explicitly in 3.9 rather than left to "the dependent tests".

## 1. Decisions to confirm before implementing

- [x] 1.1 Confirm `Selector` is `frozen` and sets `extra="ignore"`. Both are unstated in #31's shape
      sketch and are this repo's call; `design.md` decisions 1 and 2 give the reasoning (deep
      immutability for `ModelCard`, hashability for the producer's de-duplication, forward tolerance for
      an older-pinned consumer)
- [x] 1.2 Confirm the non-empty `selectors` check is a **`BeforeValidator`, not `Field(min_length=1)`**.
      Measured: `min_length` validates items first, drops the invalid ones, then checks length, so a
      card whose single selector is bad reports a real error **plus** a spurious `too_short` — it says
      the list was empty when it was not, makes the genuinely-empty case indistinguishable, and breaks
      five existing exact-equality error assertions. `design.md` decision 4 has the measured table
- [x] 1.3 Confirm the release target is **`0.1.0a8`**. `0.1.0a7` is already on PyPI, so unlike
      `tighten-model-card-validation` this cannot ride an unreleased version
- [x] 1.4 Confirm `param-resolution` is in scope. Its `Imaging Mode Resolution Seam` scenario
      *constructs* `ModelCard(mode="cylinder")`, which this change makes unsatisfiable — not stale
      prose but a statement no implementation could honor (`design.md` decision 9)

## 2. Add `Selector` — additive, green on its own

- [x] 2.1 **(RED)** Write `tests/test_model_card.py` tests for all 8 `Bundled Selection Selector`
      scenarios, against a `Selector` that does not exist yet: valid construction; own age bounds
      enforced **standalone** (inverted window, negative, `bool`, `numpy.bool_`); own mode vocabulary
      enforced standalone (off-vocabulary, cased, space-padded); an unmodelled `species` accepted;
      immutability; hashability with `set` de-duplication collapsing to one element; an unknown nested
      key ignored; and absence from every emitted schema. Also assert `Selector` is importable from the
      package root and present in `__all__` (the precedent for a new exported name —
      `prediction-manifest-contract` and `run-manifest-contract` both spec the `__all__` assertion)
- [x] 2.2 **(GREEN)** Add `Selector` to `src/sleap_roots_contracts/models.py`. It must be defined
      **after** `Mode` *and* **before** `ModelCard` (the module has no `from __future__ import
      annotations`, so both `Mode` in `Selector`'s annotations and `Selector` in `ModelCard`'s are
      evaluated at class-creation time). That leaves one legal insertion point, inside the definition-
      order comment block at `models.py:225-231`, so rewriting that comment is part of this task, not
      §3. `frozen=True, extra="ignore"`; `species: str`; `mode: Mode`;
      `age_min`/`age_max: NonBoolInt = Field(ge=0)`. Include a class docstring — `ruff` runs pydocstyle
      `D` on `src`, so a missing one fails `D101`
- [x] 2.3 **(GREEN)** Give `Selector` the age-ordering check by **sharing** the existing
      implementation, not restating it: `NonBoolInt` was strengthened to catch `numpy.bool_` in
      `tighten-model-card-validation`, and a hand-written bound check would silently reopen that hole.
      For this commit, extract the body of `ModelCard._check_age_range` into a module-level helper both
      validators call; §3 then deletes `ModelCard`'s copy. Note the return annotation must read
      `-> "Selector"` on the selector's validator — pydantic never evaluates it, so a copied
      `-> "ModelCard"` still *works* while `typing.get_type_hints` resolves it to the wrong class, and
      with no mypy in dev deps and no type-check step in CI nothing would catch it
- [x] 2.4 **(GREEN)** Export `Selector` from `src/sleap_roots_contracts/__init__.py` — both the import
      block and `__all__`
- [x] 2.5 Verify green and non-perturbing: `uv run pytest -v`, `uv run black --check src tests`,
      `uv run ruff check src tests`, `uv lock --check`, and
      `uv run python -m sleap_roots_contracts.schema && git diff --exit-code schema/` — adding
      `Selector` must not restamp the committed schemas, because nothing in `ResultEnvelope`'s field
      graph reaches it

## 3. Reshape `ModelCard` — atomic with its test rewrite

- [x] 3.1 **(RED)** Rewrite `make_card` (`tests/test_model_card.py:15`) to build `selectors`, and update
      the **17** of its 24 callers that pass a removed field (the other 7 — the two `root_type` tests,
      the `sleap_nn_version` optional test, and the four `to_model_ref` tests — need no edit). The
      remaining three of the 20 affected tests build mappings inline and are handled by 3.9.
      Route every **negative** selector test through
      `ModelCard.model_validate({..., "selectors": [{...}]})`, not through a `Selector`-object fixture:
      a `Selector` carrying an invalid value cannot be constructed, so an object-based fixture raises
      from `Selector` with an empty `loc` and stops exercising the card at all — the hole
      `test_model_card_guards_apply_via_model_validate` exists to close
- [x] 3.2 **(RED)** Re-point **all five** exact-`loc`/exact-error-list assertions under `selectors`, not
      just the inverted-window one: `tests/test_model_card.py:141` (`== ["int_type"]`), `:217`
      (`== [("mode",)]`), `:362` (`== [(bad_field,)]`), `:381` and `:386` (set equality over
      `("mode",)`/`("root_type",)`/`("age_min",)`/`("age_max",)`), and `:402` (`== [("mode",)]`).
      Two caveats: `("root_type",)` in the `:381` set **stays card-level** and must not be moved under
      `selectors`; and `:141` asserts error *types*, not `loc`s, so what changes there is only whether a
      second error appears (see 3.5)
- [x] 3.3 **(RED)** `test_model_card_field_error_masks_the_range_check` (`:393-402`) pins that a
      card-level field error **masks** the cross-field range check, because the `after` validator is
      gated on all fields passing. That changes level: the range check now gates on the *selector's*
      fields, so a bad card-level `root_type` no longer masks a selector's inverted window and both
      errors surface. Decide deliberately and re-pin the new behavior — this test documents a
      diagnostic contract, so it must be rewritten rather than deleted
- [x] 3.4 **(RED)** Fix `test_model_card_is_frozen` (`:251`), which asserts on `c.species` — a field the
      reshape removes. Measured: a frozen pydantic model raises `frozen_instance` on assignment to
      **any** name, including a removed field, so this test would keep passing while asserting nothing.
      Re-point it to a surviving field (`registry_id`) and add the nested `card.selectors[0]` case
- [x] 3.5 **(RED)** Add tests for the three new `Model Selection Card` scenarios — several selectors on
      one card retained in order; an empty `selectors` rejected as **exactly one** error at `selectors`
      for both `()` and `[]`; and a card whose only selector is invalid reporting **just** that
      selector with no spurious empty-list error (this is the regression test for the `min_length`
      trap, so assert the exact error list, not membership)
- [x] 3.6 **(RED)** Add tests for all three `No Tolerant Read Of The Legacy Flat Card` scenarios — a
      flat mapping failing with `selectors` missing; flat keys ignored not lifted (a flat mapping *plus*
      a disagreeing `selectors`, asserting the card reflects only the selector and has no `species`
      attribute); and `species`/`mode`/`age_min`/`age_max` absent from `ModelCard.model_fields`. These
      are the tests `design.md` decision 7 depends on: its whole argument for making the decision a
      named requirement is that a tolerant read cannot be re-added "without visibly deleting a
      requirement **and reddening tests**", which is false if no test exists
- [x] 3.7 **(RED)** Add tests for the two coercion scenarios: a list of `repr` strings does not
      validate, and a positional list (`["canola", "cylinder", 2, 13]`, the `NamedTuple` coercion shape)
      does not validate by position
- [x] 3.8 **(RED)** Extend the existing `test_model_card_absent_from_result_schema` (`:412`, one of the
      9 tests the reshape does not otherwise touch) to iterate **every** emitted schema rather than only
      `result_envelope`, and to assert against the expected `$defs` set rather than a bare
      `"Selector" not in defs`, which passes vacuously if either class is renamed. There are two emitted
      schemas: `schema/result_envelope.schema.json` and `schema/analysis_input.schema.json`
- [x] 3.9 **(RED)** Update the two `Tolerant Construction From Registry Metadata` tests, which build card
      mappings inline and so are **not** reached by 3.1's `make_card` rewrite:
      `test_model_card_from_merged_metadata` (`:297`) must merge a `selectors` list of dicts and assert
      the result's `selectors` are `Selector` **instances** (the scenario's THEN was strengthened to say
      so), and `test_model_card_tolerates_extra_keys` (`:313`) must keep its extras alongside the new
      shape. Also update `test_model_card_guards_apply_via_model_validate` (`:340`), the third inline
      builder, whose parametrized `bad_field` values are all card-level today
- [x] 3.9a **(RED)** Update `tests/test_params.py` — the `_card` helper (`:72-83`, five flat kwargs) and
      its single call site in the mode-vocabulary agreement test (`:142-145`; the `card.mode` read is at
      `:145`). This is the only `ModelCard` construction outside `test_model_card.py`; the three other
      files mentioning `ModelCard` do so only in prose
- [x] 3.10 **(GREEN)** Reshape `ModelCard`: drop `species`, `mode`, `age_min`, `age_max`; add
      `selectors: tuple[Selector, ...]` with the non-empty `BeforeValidator` from 1.2; delete
      `ModelCard._check_age_range` (now shared via 2.3). Keep `root_type`, `registry_id`, `version`,
      `weights_checksum`, `sleap_nn_version`, `frozen=True`, `extra="ignore"`, and `to_model_ref`
      untouched — verified that `to_model_ref` reads only `registry_id`, `version`, `root_type`,
      `weights_checksum`, so no removed field reaches it
- [x] 3.11 **(GREEN)** Rewrite the `ModelCard` docstring. It states the flat shape as fact in four
      places: the intro ("as flat wandb artifact metadata"), the selection-fields bullet, the
      `age_min`/`age_max` approved-window paragraph, and the `NonBoolInt` counterweight paragraph. State
      the any-selector rule and the "age against **a** matching selector, never a card-level window"
      corollary
- [x] 3.12 **(GREEN)** Fix the stale comment blocks **outside** that docstring, which §3.11 does not
      cover and which no test would catch:
      - `models.py:71-72` — "Applied to every integer field on LabelCard and to **ModelCard's age
        bounds**" → the bounds are `Selector`'s now
      - `models.py:216-217` — "Required on both cards: LabelCard since 0.1.0a6, **`ModelCard.mode`** as
        of the same release" → becomes false; `ModelCard` has no `mode`
      - `models.py:416` — "Mirrors **`ModelCard._check_age_range`**" → a dangling reference to the
        symbol 3.10 deletes, sitting in `LabelCard`, which this change otherwise does not touch
      - `models.py:324`, `:339` — `LabelCard`'s "mirror of `ModelCard`" / "`[age_min, age_max]` as on
        `ModelCard`" cross-references, now imprecise
- [x] 3.13 **(GREEN)** Fix `params.py:158` — `_mode_for_scan`'s docstring says `Mode` "types
      `ModelCard.mode` as well as `LabelCard.mode`". This is the docstring of the exact function whose
      requirement this change MODIFIES, so leaving it makes the permanent spec and its own
      implementation contradict each other. Check `params.py:142` in the same pass
- [x] 3.14 Verify: `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`,
      `uv lock --check`, `git diff --exit-code schema/`

## 4. Docs (separately green)

- [x] 4.1 `README.md` — two edits, not one. The model-selection paragraph names `mode` as a card field
      alongside `root_type` (rewrite for one-card-per-physical-model and `Selector`); and the paragraph
      below claims `Mode` types `mode` on "**both** cards", which becomes **false as written** — one of
      the two cards no longer has a `mode` field. Rewrite it to `Selector.mode` on the model side,
      `LabelCard.mode` on the label side
- [x] 4.2 **`openspec/project.md`** — the same "both cards" claim appears twice, at lines 22-23
      ("`Mode` … types `mode` on both cards (3) and (4) — since `0.1.0a6` for `ModelCard`") and 107-109
      ("`MODE_VOCAB` is redundant for `ModelCard` *and* `LabelCard`"). Both become false. This file is
      the conventions file loaded into agent context, so a stale copy mis-teaches every future change.
      Precedent: both prior changes to this contract updated it
- [x] 4.3 `docs/01-contract-library-design.md` — **not** a "capability list" edit; there is no
      `ModelCard` shape description in the body, and the body is a frozen point-in-time record
      ("superseded in specifics; kept as history"). The edit its own convention requires is appending a
      `v0.1.0a8` sentence to the running staleness banner (which currently stops at `a7`), noting the
      reshape. Leave the body untouched
- [x] 4.4 `docs/CHANGELOG.md` — a `0.1.0a8` section with its own **BREAKING** line, in the exact format
      the release build greps for (`^## \[0.1.0a8\] - YYYY-MM-DD`, plus the `(Pre-release)` suffix the
      file uses). Say plainly that card-level `species`/`mode`/`age_min`/`age_max` are gone, that there
      is deliberately no tolerant read of the flat shape, and that an upgraded reader must be deployed
      only after the producer's re-seed. Add the `[0.1.0a8]: …/compare/v0.1.0a7...v0.1.0a8` footer link
      and retarget the `[Unreleased]` link to `v0.1.0a8...HEAD`. Leave `0.1.0a6`'s released "both cards"
      entry alone — it is history
- [x] 4.5 `docs/02-contract-library-plan.md` — pre-answered: `grep` for `ModelCard`/`age_min`/`Selector`
      returns **zero** hits, and the file self-describes as a historical build record. No edit
- [x] 4.6 Leave the four dated `docs/superpowers/specs/*.md` design records untouched, including
      `2026-07-03-model-card-…-design.md`, which contains the literal flat `class ModelCard` body.
      Editing a dated design record would rewrite history; noted as a decision so it is not "fixed"
      later

## 5. Release

- [x] 5.1 Bump `pyproject.toml` to `0.1.0a8` **and re-lock `uv.lock` in the same commit** — a version
      bump without a re-lock hard-fails the release build, and PR CI catches it only via the explicit
      `uv lock --check` step (the `0.1.0a4` release history is the precedent). Consider driving it
      through the repo's `version.yml` (`workflow_dispatch`) rather than by hand
- [x] 5.2 **After** 5.1, order matters — `schema.py`'s `render()` embeds `__version__` in every schema's
      `$id`, so any version bump restamps `schema/*.json` even though this change touches neither
      `ResultEnvelope` nor `AnalysisInputRow`: run `uv run python -m sleap_roots_contracts.schema`, then
      re-run the full gate (`uv run pytest -v`, `black --check`, `ruff check`, `uv lock --check`,
      `git diff --exit-code schema/`) against the restamped `$id`
- [ ] 5.3 Set the ISO date on the `0.1.0a8` changelog heading in the release-cut commit, then tag and
      publish `v0.1.0a8`. **Do not yank or delete it once published**: consumers pin it in `uv.lock`
      with sdist and wheel hashes, so a vanished version fails `uv sync --locked` on every CI leg until
      the lock is regenerated
- [ ] 5.4 Verify from a clean isolated environment that `sleap-roots-contracts==0.1.0a8` installs and
      `Selector` imports, and that a card round-trips from a JSON-native `selectors` list of dicts

## 6. Archive gate — MUST be closed before `openspec archive`

Archiving folds the deltas into `openspec/specs/`, so anything wrong here becomes permanently wrong
with no later prompt to fix it.

- [ ] 6.1 **BLOCKING.** `0.1.0a8` must be tagged and published to PyPI before this change is archived
      (mirrors the `add-label-selection-contract` and `add-run-manifest-contract` gates) — archiving a
      contract whose release never happened leaves `openspec/specs/` describing a version consumers
      cannot install. This is also what makes 7.1 tickable
- [ ] 6.2 `openspec validate update-model-card-selectors --strict` passes
- [ ] 6.3 Run validation on the **oldest and newest** CLI binaries available (currently 1.5.0 and
      1.8.0), not just one, and for two different reasons. 1.5.0 rejects a requirement whose SHALL/MUST
      wraps past the first line while 1.6.0+ accepts it. Conversely **1.8.0 is the only version that
      checks MODIFIED-block scenario preservation** — verified by deleting a preserved scenario in a
      throwaway copy, where 1.8.0 fails with "omits scenario(s) the current spec still has" while
      1.5.0/1.6.0/1.7.0 all report valid. The binaries are in the npx cache, not on `PATH`:
      `for d in ~/.npm/_npx/*/node_modules/.bin/openspec; do echo "$($d --version) <- $d"; done`
- [ ] 6.4 **Dry-run the archive into a throwaway copy anyway.** 1.8.0's check covers only scenario
      *names*; **no** version checks that a normative prose clause survived, and none checks that a
      preserved clause is still *true*:
      `SB=$(mktemp -d); cp -R openspec "$SB/openspec"; (cd "$SB" && openspec archive update-model-card-selectors --yes)`
      Expect `+ 2 added, ~ 2 modified` for `model-selection-contract` and `~ 1 modified` for
      `param-resolution`
- [ ] 6.5 Diff the resulting specs against the live ones and assert that **`Model Card To ModelRef
      Conversion` is byte-identical** — it is the one `model-selection-contract` requirement this change
      does not touch
- [ ] 6.6 Assert the same for `param-resolution`: every requirement except `Imaging Mode Resolution
      Seam` byte-identical, and that requirement's three scenario names all still present. **Expect one
      cosmetic non-requirement hunk** — the archiver deletes the blank line between the Purpose
      paragraph and `## Requirements` in that file. It is not damage and it is not a reason to wave the
      diff through
- [ ] 6.7 Re-validate the **archived** tree, which the change-level gate does not cover:
      `(cd "$SB" && openspec validate --specs --strict)` — expect `7 passed, 0 failed`. Also assert the
      structural counts: `model-selection-contract` should end with **5 requirements and 35 scenarios**
      (19 on `Model Selection Card`, 8 on `Bundled Selection Selector`, 3 on `No Tolerant Read`, 4 on
      `Tolerant Construction`, 1 on `Model Card To ModelRef Conversion`)
- [ ] 6.8 Fix the `model-selection-contract` spec **Purpose**, still the literal
      `TBD - created by archiving change add-model-card-predict-inference-config. Update Purpose after
      archive.` placeholder. The archiver does not touch Purpose, so this is a manual edit and it will
      not prompt again. While in the file: the archiver appends ADDED requirements **after** the
      MODIFIED ones, so `Bundled Selection Selector` lands *below* the `Model Selection Card`
      requirement that references `Selector` — reorder so the type is defined before its use
- [ ] 6.9 Grep `openspec/specs/` for `ModelCard` after the dry run and confirm every surviving mention
      is still true. Six survive in `param-resolution`: the Purpose line and `Species Name
      Normalization`'s two mentions, all untouched by this change — the latter deliberately left per
      `design.md` decision 9, which accepts a residual imprecision rather than claiming accuracy, so
      **re-confirm that trade** rather than rubber-stamping it — plus three inside the rewritten
      `Imaging Mode Resolution Seam` (its requirement prose and its scenario), which are this change's
      own and are correct by construction. Reference requirements by name, not by line number: the
      archiver's blank-line deletion shifts them by one

## 7. Prerequisites and follow-on (not this repo's checkboxes)

Recorded so the ordering is greppable. Only 7.1 is ours, and it is gated on 6.1.

- [ ] 7.1 Comment on talmolab/sleap-roots-contracts#31 when `0.1.0a8` is released, so the producer is
      unblocked. No new issue is needed — #31 already carries the scope
- **`sleap-roots-training`** (talmolab/sleap-roots-training#39, PR #47) — bumps the pin, rewrites
  expansion to per-physical-model, renames every collection id, re-seeds. Must land **after** the
  `0.1.0a8` release.
- **`sleap-roots-predict`** (talmolab/sleap-roots-predict#34) — generalizes `choose_models` to the
  any-selector rule and matches age against a *matching* selector. May merge and pin at any time; its
  **deploy** must come after the producer's re-seed is live and verified, since without a tolerant read
  an upgraded predict deployed early skips all 13 old collections and finds nothing to select.
- **Retirement of the 13 old collections** is the producer's, gated on confirmed deployment of the
  upgraded predict — not on producer-side `--verify` passing. That step is the actual compatibility
  cliff.
