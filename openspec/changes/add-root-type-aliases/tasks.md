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
- [x] 0.4 **Seed only what is evidenced** — wheat `seminal` → `crown`. Maize brace/nodal is named in
      #34 but no maize data exists in either registry, and brace roots are aerial and visually
      unlike young wheat crown roots, so encoding them on an issue comment would be the worst error
      available here.
- [x] 0.5 **The display half is dropped** (D5), not deferred-but-specified. It is absent from the
      delta, so it cannot archive into permanent spec describing a function that does not exist.
- [ ] 0.6 **Elizabeth to confirm the one irreversible consequence.** Under #49's D4, collection names
      derive from the card, so the wheat collection becomes `wheat-cylinder-crown`, not
      `wheat-cylinder-seminal`. **W&B collections cannot be renamed or deleted**, so this executes
      once. "Use crown throughout" plainly covers the card field; whether it was meant to reach the
      registry collection name is the question. **This is the only genuinely blocking item.**

## 1. Cross-repo — correcting the record

- [ ] 1.1 Post a correction on **contracts#34**, stating the chronology: its "the resolution there is
      to store it as `crown` per team decision" describes the right outcome but post-dates #49's D3.
- [ ] 1.2 Post on **training#49**. Be precise about what it does and does not unblock, because the
      earlier draft of this task was wrong:
      **(a)** D3 is superseded; `LabelRootType` is not being added. #49's argument against *widening*
      `RootType` stands and is quoted approvingly.
      **(b)** What drops: tasks 1.2/1.3, and #49's whole §3 root-type half — `LABEL_ROOT_TYPE_VOCAB`
      is unnecessary since `crown` is already in `ROOT_TYPE_VOCAB`.
      **(c)** What does **not** drop: **#49 still needs a contracts release.** Its task 1.1 is the
      `0.1.0a6 → a8` pin catch-up (the breaking `Selector` reshape, with its ordered rollout), and
      D7/task 1.4's optional-field relaxation remains live — #49's own task 2.5 expects
      `n_plants`/`n_scans` to be unrecoverable. Claiming otherwise, as an earlier draft did, is false.
      **(d)** What #49 is asked to give up, so it can push back: its ADDED requirement
      *Label Root-Type Vocabulary* is deleted **in full, all three scenarios**, including "A label
      collection MAY describe a root type for which no trained model exists." This design forecloses
      that headroom. If the label side genuinely needs it, that argument should be made now.
      **(e)** `0.1.0a9` is claimed by this change, so #49's release target moves.
      **(f)** #49 need not wait on us — its backfill mapping is a hand-written table; writing
      `root_type="crown"` in the wheat row works today.
- [ ] 1.3 Confirm #34's open question during #49's provenance step: whether the rice half of the
      pooled model (`rice_3-10DAG`) is the same source as `rice_3DAG_crown_6nodes_labels`. Note the
      age windows differ (3-10 vs 3), so this is not a safe assumption.
- [ ] 1.4 **Pin the evidence before implementing.** Both load-bearing citations are unverifiable from
      any local checkout: the pooled model (`250328_095645.multi_instance.n=1658` /
      `labels_seminal_wheat_5-14DAG_rice_3-10DAG.v005.slp`) appears in no repo on this machine, and
      `sleap-roots-analyze` is not checked out. Record a wandb artifact URL for the model — confirming
      the frame count and both source label sets — and a commit SHA for the analyze config. The age
      window seeded in the table comes directly from this, so an unpinned citation means an unpinned
      window.
- [ ] 1.5 Correct `talmo-sleap-roots-training/docs/roadmap.md:313`, which asserts on `main` that
      "primary / lateral / seminal / crown keep their own skeletons" — it names seminal and crown as
      distinct root types, in the repo that owns the skeleton table #49 is about to mark verified.

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
      them is §4, and the guard must be re-run there. Also `grep -qE "^## \[0\.1\.0a9\]"
      docs/CHANGELOG.md` for heading shape (the *dated* form is `build.yml`'s job at release), and
      `uv build` + `uv run --isolated --with dist/*.whl python -c "from sleap_roots_contracts import
      canonical_root_type, ROOT_TYPE_ALIASES"` — the only check that 2.20's exports resolve from a
      built wheel. Record which interpreter it ran under; CI matrixes 3.11 and 3.12.

## 3. Docs

- [ ] 3.1 `docs/CHANGELOG.md`: add `## [0.1.0a9] (Pre-release)` **undated** — the release-cut commit
      sets the ISO date and `build.yml` fails an undated section at release, so this exact form is
      required. Keep the empty `[Unreleased]` above it. **Add the footer compare link**
      (`[0.1.0a9]: .../compare/v0.1.0a8...v0.1.0a9`) and retarget `[Unreleased]` to
      `v0.1.0a9...HEAD`. Record that the `schema/*.json` delta is **`$id`-only**, since Bloom consumes
      those for codegen and migration-match.
- [ ] 3.2 `openspec/project.md`: describe the alias table **beside the `Mode`/`RootType` vocabularies**
      (the paragraph after the numbered list) and in the External Dependencies paragraph naming "the
      controlled vocabularies contracts owns". **Not** in the six-contracts list — that list is data
      contracts crossing a producer↔consumer boundary, and an alias table is not one.
- [ ] 3.3 `README.md`: a paragraph mirroring how the `Mode` vocabulary is already documented there,
      since 2.20 adds package-root exports. `prepare-release.md` Step 4 re-checks README at release,
      so skipping it surfaces as a release blocker rather than a review comment.
- [ ] 3.4 `docs/01-contract-library-design.md`: its staleness banner enumerates capability names
      verbatim and carries a per-version running note; it was touched in every release from a3 to a8.
      Append the `v0.1.0a9` sentence and add the new capability name.
- [ ] 3.5 Record as an explicit no-op: `docs/02-contract-library-plan.md`'s seven `root_type` hits are
      historical code listings, and the dated design records under `docs/superpowers/` stay untouched.
      Written down so it is not re-litigated by the next person who greps.
- [ ] 3.6 State the routing-not-synonymy semantics in the module docstring, so it survives separately
      from this proposal once the change archives.

## 4. Release — `0.1.0a9`

- [ ] 4.1 Bump `pyproject.toml` **and re-lock in the same commit**; `uv lock --check` runs on every PR.
- [ ] 4.2 **After** 4.1, order matters: `uv sync`, regenerate the schemas, then re-run the full 2.G
      gate against the restamped `$id`. Splitting the bump from the restamp produces two red PR-CI
      commits. Precedent: `4b2073b`.
- [ ] 4.3 **Do not yank once published** — consumers pin with sdist and wheel hashes, so a vanished
      version fails `uv sync --locked` on every CI leg until the lock is regenerated.

## 5. Archive gate

- [ ] 5.1 Enumerate the CLI binaries — they are **not on `PATH`**:
      `for d in ~/.npm/_npx/*/node_modules/.bin/openspec; do echo "$($d --version) <- $d"; done`.
      Invoke by **absolute path**, never `npx`, and record the resolved path and `--version` when
      ticking, because the cached binary has updated in place **twice** (1.8.0 → 1.9.0 → 1.10.0).
      Run the oldest as well as the newest: 1.5.0 rejects a requirement whose `SHALL` wraps past the
      first line, and these deltas carry many. The ≥1.8.0 MODIFIED-scenario check is irrelevant here,
      since both deltas are ADDED-only.
- [ ] 5.2 Dry-run the archive into a throwaway copy **with the same binary that will archive**, and
      assert every pre-existing spec file is byte-identical afterwards. Note `validate --strict` does
      **not** surface the proposal-length warning that `archive` does, so the dry run is not optional.
- [ ] 5.3 The new capability's `Purpose` is written **into the delta file**, above
      `## ADDED Requirements` — verified to carry through the archiver verbatim. This avoids the
      post-archive edit that six of this repo's seven specs never got, leaving them reading
      `TBD - created by archiving change ...`.
