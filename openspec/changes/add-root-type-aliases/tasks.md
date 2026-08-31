# Tasks

**Priority: low.** Issue #34 says so. It is written down now because the equivalence has been
reinvented three times, most recently as a contract fork.

**Proposal only — no code in this PR.** Implementation is gated on §0 and follows on the same branch,
matching this repo's precedent (contracts#32 opened proposal-only and pushed
`test(RED)` → `feat(GREEN)` to the same PR after approval).

**TDD.** Group 2 is ordered tests-first and is meant to be worked top-down; there is no
"numbered by subject" disclaimer to ignore.

## 0. Decisions

`design.md` D1-D7 are **taken**, and the delta specs encode them. They are listed here for
ratification, not as open choices — an earlier draft declared them "BLOCKING and unanswered" while
the spec had already answered them, which made the section decoration.

- [x] 0.1 **Canonical bucket is `crown`.** Elizabeth, 2026-08-27.
- [x] 0.2 **Unknown terms raise** (D6), coupled to evidence-gated sparsity.
- [x] 0.3 **`species` scoped, `age_days` optional** (D4); an unsupplied species resolves only
      unambiguous terms.
- [x] 0.4 **Seed only what is evidenced** — wheat `seminal` → `crown`. **Maize** is declined because
      no maize data exists in either registry; the morphology point is secondary and only half right
      (brace roots are aerial and unlike young wheat crown roots, but maize *below-ground* nodal
      roots are the direct developmental analogue, so "brace/nodal" over-claims). **Rice** is
      declined even though it is half the cited evidence, and the reason is not sparsity: rice has no
      `seminal` term to alias. `sleap-roots-training`'s `skeletons.yaml` records rice as `primary` +
      `crown` with no `seminal` row anywhere, because rice nodal roots emerge within days and
      dominate by 3-10 DAG. There is no rice alias to record, so the table is not under-seeded from
      its own evidence.
- [x] 0.5 **The display half is dropped** (D5), not deferred-but-specified. It is absent from the
      delta, so it cannot archive into permanent spec describing a function that does not exist.
- [ ] 0.6 **Elizabeth to confirm the one irreversible consequence.** Under #49's D4, collection names
      derive from the card, so the wheat collection becomes `wheat-cylinder-crown`, not
      `wheat-cylinder-seminal`. **W&B collections cannot be renamed or deleted**, so this executes
      once. "Use crown throughout" plainly covers the card field; whether it was meant to reach the
      registry collection name is the question. **This is the only genuinely blocking item.**

## 1. Cross-repo

**#49 got here on its own.** An earlier draft of this section was written against #49 at `1015d59`
and would have asked its author to give up a `LabelRootType` fork she had **already withdrawn** four
days earlier at `f484a4d` ("Root type does **not** split (D3). Only species does."). It would have
read as not having looked. What follows is what is actually left.

- [ ] 1.1 Comment on **contracts#34** linking #35 and noting that #49 and this change converged
      independently on `crown`. No correction is owed: #34's "the resolution there is to store it as
      `crown` per team decision" was ahead of the evidence when written and is now simply true.
- [ ] 1.2 Comment on **training#49** — informational, not a request. Note that D3's rewrite and this
      proposal reached the same place from different directions; that #49's `## 1. Upstream: contracts
      pin (no new release unless §2 requires one)` is **correct as written** — the `a6 → a8` catch-up
      needs no release because both are published, and only its D7/task-**1.3** conditional can force
      one; and that this change does not move #49's release target, because #49 claims no version.
      Flag one thing for its author to push back on if she disagrees: **#34's headroom question — "a
      label collection MAY describe a root type for which no trained model exists" — is foreclosed by
      this design**, since every label root type must now be a modeling bucket. #49 dropped that
      requirement for its own reasons; this change makes the foreclosure permanent, which is a
      different decision and deserves a deliberate yes.
- [ ] 1.3 **Not a gate.** #34's rice-provenance question (whether the pooled model's `rice_3-10DAG`
      half is `rice_3DAG_crown_6nodes_labels`) belongs to #49's §2, and #49 task 2.6 independently
      checks the wheat blob's skeleton is crown-shaped. The seeded window comes from the *wheat* half
      of the filename, so this does not block 1.4.
- [ ] 1.4 **Pin the window's provenance.** Two of the three citations turned out to be verifiable and
      an earlier draft claimed otherwise, which understated the change's own evidence:
      **(a) `sleap-roots-analyze` is checked out** at `95dfcd1` — `configs/active/qc/qc_cylinder_edpie.yaml:55`
      carries `crown: "seminal"  # Wheat: crown roots → seminal roots`. Cite that SHA and line.
      **(b) The model artifact exists on the analysis machine** as
      `250328_095645.multi_instance.n=1658.root_crown.slp`. Note the **`.root_crown` suffix**: the
      pooled model's wheat output was already filed under `crown` at the trait stage, which
      corroborates this change's thesis from a direction it did not claim.
      **(c) Still unpinned, and it is the load-bearing one:**
      `labels_seminal_wheat_5-14DAG_rice_3-10DAG.v005.slp` is absent everywhere. Pin a wandb artifact
      URL and confirm the training-set composition, the 1,658 frame count, and **the window**.
      **(d) Pin the epoch too.** The window is read off a `DAG`-labelled filename while the consumer
      side reads Bloom's `plant_age_days`, whose epoch is asserted nowhere in either repo. Confirm
      whether it is DAG or DAP; a mismatch shifts a 5-14 window by a fifth to a third of its span.
      **(e) Once (c) and (d) land, write the concrete window into the wheat scenario before archive.**
      Today no delta contains a single age digit, so every age scenario is self-referential and
      `age_min=0, age_max=200` would satisfy all of them while defeating D4 entirely.
- [ ] 1.5 Correct `sleap-roots-training/docs/roadmap.md:313`, which still reads
      "(primary / lateral / seminal / crown keep their own skeletons)". Genuinely additive: #49's own
      task 7.6 names `:221`, `:284`, `:326/:329` but not `:313`.

## 2. Implementation — tests first

- [ ] 2.1 **Test:** no term in the table is a `RootType` member, having first asserted the table is
      non-empty and includes `seminal`, so an empty or wrongly-accessed table cannot pass the loop by
      doing nothing.
- [ ] 2.2 **Test:** the table is immutable, deeply — a nested entry field cannot be reassigned either,
      and the mutation is asserted not to have taken effect. Precedent: `test_model_card_is_frozen`,
      where `tuple` protected the sequence but not its elements.
- [ ] 2.3 **Test:** every entry carries an age window with `age_min <= age_max` and a non-empty
      evidence citation.
- [ ] 2.4 **Test:** `seminal` + `wheat` + an in-window age returns `crown`.
- [ ] 2.5 **Test:** idempotence, both species-free and composed under a species —
      `canonical_root_type(canonical_root_type("seminal", "wheat"), "wheat")` is `crown`.
- [ ] 2.6 **Test:** canonical passthrough beats any species-scoped entry, and the table keys no
      canonical string as an alias term.
- [ ] 2.7 **Test:** the species key matches `"  Wheat "` as `"wheat"`, asserted on a term that
      resolves **only** under its species, with the same term under `rice` raising — so a function
      that ignores `species` entirely cannot pass.
- [ ] 2.8 **Test:** the species key mirrors `params._normalize_species`' full contract — a present
      non-string raises `ValueError` naming `species` (never `AttributeError`, never a `"<na>"` key),
      and `None`/`NaN`/`pandas.NA`/`NaT` are treated as species-not-supplied. Parametrized over the
      same sentinel set as `tests/test_params.py`.
- [ ] 2.9 **Test:** the two species normalizers do not drift — a monkeypatched entry in
      `params._ALIASES` does not silently cause a table miss. `_ALIASES` is empty today; this is what
      keeps it safe to fill.
- [ ] 2.10 **Test:** an age outside the window raises naming term, species and window, **and** an
      in-window age still resolves, so the guard discriminates.
- [ ] 2.11 **Test:** an omitted `age_days` resolves, per D4.
- [ ] 2.12 **Test:** the term is matched exactly — `"Seminal"` and `" seminal "` both raise, pinning
      the deliberate asymmetry with the normalized species key.
- [ ] 2.13 **Test:** an unrecognized term raises naming the term and the accepted set, and a
      recognized term still resolves.
- [ ] 2.14 **Test:** round-trip — the returned value constructs a real `LabelCard` and `ModelCard`
      storing `crown`. This is the only check that catches a return value that *looks* canonical but
      is not a `RootType` member.
- [ ] 2.15 **Test:** a card built directly with `root_type="seminal"` raises, the error locates to
      `root_type`, and the same card with `crown` constructs — the positive control, so an unrelated
      construction bug cannot make the rejection pass for the wrong reason.
- [ ] 2.16 **Test:** the table and accessor are importable from the package root and in `__all__`;
      internal helpers are not exported.
- [ ] 2.17 Implement the table in a new `src/sleap_roots_contracts/root_type_aliases.py`. **Not
      `models.py`** — `params.py` imports `models`, so a species-normalization helper shared by both
      cannot live there without a cycle.
- [ ] 2.18 Implement `canonical_root_type(term, species=None, age_days=None)`.
- [ ] 2.19 Share `params`' species normalization rather than reimplementing strip+lower, per 2.9.
- [ ] 2.20 Export from the package root and add to `__all__`.
- [ ] 2.G Gate: `uv sync --frozen`, `uv run pytest`, `uv run black --check src tests`,
      `uv run ruff check src tests`, `uv lock --check`, and the schema drift guard
      (`uv run python -m sleap_roots_contracts.schema` then `git diff --exit-code schema/`). At this
      point the guard asserts the new symbols restamp **nothing** — the version bump that does restamp
      them is §4, and the guard must be re-run there. Also `rm -rf dist/` then `uv build` and
      `uv run --isolated --with dist/*.whl python -c "from sleap_roots_contracts import
      canonical_root_type, ROOT_TYPE_ALIASES"` — the only check that 2.20's exports resolve from a
      built wheel. The `rm` is load-bearing: `dist/` is gitignored and never cleaned, so a second run
      at §4.2 leaves both the a8 and a9 wheels there and `--with dist/*.whl` silently takes one and
      treats the other as the command. Run it under **3.11**: `build.yml` pins 3.12 for the wheel
      check it mirrors, so 3.11 is the leg no CI job covers. The changelog heading-shape check moves
      to §3 (it tests a heading §3.1 adds, so it fails here if §2 lands first).

## 3. Docs

- [ ] 3.1 `docs/CHANGELOG.md`: add `## [0.1.0a9] (Pre-release)` **undated** — the release-cut commit
      sets the ISO date and `build.yml` fails an undated section at release, so this exact form is
      required. Keep the empty `[Unreleased]` above it. **Add the footer compare link**
      (`[0.1.0a9]: .../compare/v0.1.0a8...v0.1.0a9`) and retarget `[Unreleased]` to
      `v0.1.0a9...HEAD`. Record that the `schema/*.json` delta is **`$id`-only**, since Bloom consumes
      those for codegen and migration-match.
- [ ] 3.2 `openspec/project.md`. There is no "paragraph after the numbered list" holding the
      vocabularies — `:4-27` is one unbroken paragraph containing both the six-contracts list and the
      `Mode` sentence, and `RootType` is not documented there at all. Edit **`:79-84` Domain Context**,
      which is the one place root types are enumerated as biology rather than as a type and the first
      place a reader looks, and the **External Dependencies** paragraph at `:107-108` naming "the
      controlled vocabularies contracts owns". **Not** the six-contracts list — that list is data
      contracts crossing a producer↔consumer boundary, and an alias table is not one.
- [ ] 3.3 `README.md`: a paragraph mirroring how the `Mode` vocabulary is already documented there,
      since 2.20 adds package-root exports. **There is no safety net here** — an earlier draft claimed `prepare-release.md` Step 4 would catch
      a missing paragraph; Step 4 checks only the Python badge, the install instructions and the
      `pip`/`uv add` examples, so this is review-enforced.
- [ ] 3.4 `docs/01-contract-library-design.md`: its staleness banner enumerates capability names
      verbatim and carries a per-version running note; it was touched in every release from a3 to a8.
      Append the `v0.1.0a9` sentence and add the new capability name.
- [ ] 3.5 Record as an explicit no-op: `docs/02-contract-library-plan.md`'s seven `root_type` hits are
      historical code listings, and the dated design records under `docs/superpowers/` stay untouched.
      Written down so it is not re-litigated by the next person who greps.
- [ ] 3.6 State the routing-not-synonymy semantics in the module docstring, so it survives separately
      from this proposal once the change archives.

## 4. Release — `0.1.0a9`

- [ ] 4.1 Bump `pyproject.toml`, re-lock, `uv sync`, regenerate the schemas, and commit **all three
      of `pyproject.toml`, `uv.lock` and `schema/*.json` together**. Splitting them produces a commit
      that passes `uv lock --check` and then fails the schema drift guard, because `schema.py` builds
      `$id` from `__version__` while the committed schemas still say `v0.1.0a8`. Note the real reason
      to combine is **bisect and revert hygiene**, not CI redness — CI evaluates the PR head, so
      pushing both together shows no red run either way. Precedent and rationale: `4b2073b`.
- [ ] 4.2 Re-run the full 2.G gate against the restamped `$id`. This is the run of the schema drift
      guard that can actually fail; the one at 2.G asserts the new symbols restamp nothing.
- [ ] 4.3 **Do not yank once published** — consumers pin with sdist and wheel hashes, so a vanished
      version fails `uv sync --locked` on every CI leg until the lock is regenerated.

## 5. Archive gate

- [ ] 5.0 **BLOCKING: `contracts#33` MUST merge before this change archives.** The *merge* order of
      #33 and #35 is free — neither touches a file the other touches. The *archive* order is not.
      Archiving this first makes #33 unmergeable, and #33's blob is a generated archive snapshot
      carrying five requirements, none of them `Alias Normalization Is An Ingestion Boundary Only`,
      because it predates this change. So the natural resolution of that conflict — "take the
      generated version" — **silently deletes this change's requirement from permanent spec with
      nothing failing**. §5.2's dry run cannot catch it, because it archives in isolation and never
      against #33. #33 is archive-only, `CLEAN`, and approved; merging it first removes the hazard.

- [ ] 5.1 Enumerate the cached CLI binaries. **The glob is platform-specific** — it is
      `~/.npm/_npx/*/node_modules/.bin/openspec` on macOS and `$LOCALAPPDATA/npm-cache/_npx/` on
      Windows, so use whichever resolves. `openspec` **is** on `PATH`, but as `@fission-ai/openspec`
      **0.13.0** — older than every cached copy — which makes pinning more important than a bare
      invocation suggests, not less. Invoke by **absolute path or a version-pinned
      `npx @fission-ai/openspec@<version>`**, never bare `npx`, and record the resolved path and
      `--version` when ticking: the cached binary has updated in place more than once
      (observed 1.9.0 → 1.10.0 on the authoring machine; no 1.8.0 is present on the review machine,
      so the exact starting version is not reproducible and should not be asserted).
      Run the oldest as well as the newest: 1.5.0 rejects a requirement whose `SHALL` wraps past the
      first line, and these deltas carry many. The ≥1.8.0 MODIFIED-scenario check is irrelevant here,
      since both deltas are ADDED-only.
- [ ] 5.2 Dry-run the archive into a throwaway copy **with the same binary that will archive**, and
      assert every spec file this change does **not** target is byte-identical; the targeted
      `model-selection-contract` differs only by the appended requirement plus the archiver's
      blank-line normalization (it inserts one after `## Purpose` and after `## Requirements`). A
      literal byte-identity assertion on the targeted file trips every time and is not the check. Note `validate --strict` does
      **not** surface the proposal-length warning that `archive` does, so the dry run is not optional.
- [ ] 5.3 The new capability's `Purpose` is written **into the delta file**, above
      `## ADDED Requirements` — verified to carry through the archiver verbatim. This avoids the
      post-archive edit that six of this repo's seven specs never got, leaving them reading
      `TBD - created by archiving change ...`.
