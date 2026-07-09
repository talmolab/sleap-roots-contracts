> **Note:** the sub-steps below are the TDD *working-tree* order (RED→GREEN), **not** a commit
> sequence. Commits split along the code/release/docs seam (see `design.md` "Commit grouping"), each
> green on its own. Prefixes follow this repo's actual history (`feat:`, bare `chore:`, `docs:` —
> there is **no** `chore(release):` precedent):
> - **Commit 1 (`feat:`)** — groups 1–2: `params.py`, the package export, and `tests/test_params.py`.
>   Pure Python; touches **no schema** and **no version**, so the drift guard and
>   `test_smoke.py::test_version_matches_pyproject` are unaffected. Green.
> - **Commit 2 (`chore: release v0.1.0a4`)** — group 3: `pyproject.toml` → `0.1.0a4`, `uv sync`, the
>   re-locked **`uv.lock`** (mandatory — it pins the project's own version), **both** regenerated
>   schemas (`$id` → `v0.1.0a4`), CHANGELOG, and the `ci.yml` lockfile check. These five files are
>   genuinely coupled: bumping the version without regenerating **both** schemas turns PR CI red via
>   the drift guard, and (once 3.5 lands) a stale `uv.lock` turns it red too.
> - **Commit 3 (`docs:`)** — group 4: `openspec/project.md`, `README.md`, and the two frozen-doc
>   banners. Docs-only; `ci.yml` has no `paths:` filter, so CI still runs and must pass. May fold
>   into Commit 2.
>
> The branch is **squash-merged** (this repo's history is fully linear; `git log --merges` is empty),
> so this split buys pre-merge reviewability and bisectability, not `main` history.
>
> Never commit a bare RED step. Tests are pure functions over dicts — **no mocks, no I/O**.
>
> **Porting discipline:** this is a behavior-preserving port. The resolved `values` feed
> `param_hash` → `idempotency_key`, so any drift silently breaks cross-producer idempotency with no
> error raised. Do **not** clean up, rename, re-order, or "improve" the ported logic. The single
> permitted edit is the `ResolvedParams` import (task 1.2).

## 1. Port the oracle (test-first)

- [x] 1.1 RED: create `tests/test_params.py` by porting `sleap-roots-predict/tests/test_param_resolution.py`
      at HEAD — **32 of its 34** test functions, verbatim. Adaptations, and only these:
      - imports become, mirroring upstream (which imports the oracle from the **module**, not the
        package root — this keeps the 32 ported tests independent of the export step in 2.2, so 1.3
        is reachable):
        ```python
        from sleap_roots_contracts import ModelCard, ResolvedParams   # models, from the root
        from sleap_roots_contracts import params                      # module, for the _ALIASES monkeypatch
        from sleap_roots_contracts.params import (
            PLANT_AGE_DAYS_FIELD, SPECIES_NAME_FIELD, resolve_params,
            _coerce_age, _mode_for_scan, _normalize_mode, _normalize_species,
        )
        ```
        The package-root import is the sole responsibility of the added test in 2.1.
      - **Drop the 2 round-trip tests** (`test_round_trip_selects_expected_models`,
        `test_round_trip_unknown_species_selects_nothing`) — they call `choose_models`, which does not
        exist in this repo (issue #13). They stay in predict. Do **not** write a stub predicate.
      - **Keep** `test_mode_matches_seeded_card_vocabulary` (needs only `ModelCard`) and the `_card`
        helper it uses; drop the `choose_models` import.
      Confirm RED: `uv run pytest tests/test_params.py` fails at collection
      (`sleap_roots_contracts.params` does not exist).
- [x] 1.2 GREEN: create `src/sleap_roots_contracts/params.py` by porting
      `sleap_roots_predict/param_resolution.py` at HEAD. The **only** logic edit:
      `from sleap_roots_contracts import ResolvedParams` → `from .models import ResolvedParams`
      (a self-import would be circular; `params.py` is imported by `__init__.py` after `models.py`).
      Re-voice the module + function docstrings for contracts (predict's reference "predict's
      `choose_models`"; contracts' should say the params select a `ModelCard`), and document the soft
      Bloom column-name coupling and the `_mode_for_scan` growth seam. Preserve **every** branch,
      message string, and coercion rule. Ports: `SPECIES_NAME_FIELD`, `PLANT_AGE_DAYS_FIELD`,
      `_PARAM_KEYS`, `_ALIASES` (empty), `_is_blank`, `_normalize_text`, `_normalize_species`,
      `_normalize_mode`, `_mode_for_scan`, `_coerce_age`, `_canonicalize_text`, `resolve_params`.
      Docstrings are google-convention (ruff pydocstyle applies to `src/`).
- [x] 1.3 Verify GREEN: `uv run pytest tests/test_params.py -v` — all 32 test **functions** pass
      (≈48 test *items*, since 5 are parametrized). No package-root export is needed yet.

## 2. Public API export + the added tests (test-first)

- [x] 2.1 RED: add `test_resolve_params_is_exported` to `tests/test_params.py` — `from
      sleap_roots_contracts import resolve_params` succeeds and `"resolve_params" in
      sleap_roots_contracts.__all__`. Also assert `SPECIES_NAME_FIELD`/`PLANT_AGE_DAYS_FIELD` are
      **absent** from `__all__` (module-public, not package API — mirrors predict).
      Note: `tests/test_envelope.py::test_all_lists_exported_symbols` only checks the
      `__all__ → hasattr` direction (no dangling names); it does **not** assert membership, so this
      test is complementary, not redundant.
- [x] 2.2 GREEN: export `resolve_params` from `src/sleap_roots_contracts/__init__.py` (import +
      `__all__`, grouped with a short comment like the existing sections).
      `tests/test_envelope.py::test_all_lists_exported_symbols` must stay green.
- [x] 2.3 RED→GREEN: add `test_canonical_row_hashes_to_known_answer` — resolving a row to
      `{"species": "pennycress", "mode": "cylinder", "age": 14}` yields the `param_hash` literal
      pinned in the `param-resolution` spec's **Resolved Params Known-Answer Anchor** requirement
      (the single normative source for the digest; copy it from there, do not re-derive it).
      That digest was captured from the **pre-change** installed package (`0.1.0a3`), so it proves
      cross-release stability rather than post-change self-consistency. It passes as soon as 1.2
      lands. **If it ever goes red, a normalization or `compute_param_hash` canonicalization bug has
      been introduced — investigate, do NOT re-baseline.**
- [x] 2.4 Verify: `uv run pytest -v` (full suite) green; `uv run black --check src tests` and
      `uv run ruff check src tests` clean.

## 3. Release `v0.1.0a4` (bump, re-lock, regenerate both schemas)

- [x] 3.1 Bump `pyproject.toml` → `version = "0.1.0a4"` via `uv version 0.1.0a4` (single source of
      truth; `__init__.__version__` resolves from installed metadata, so no code edit).
- [x] 3.2 `uv sync && uv run python -m sleap_roots_contracts.schema` (writes all `MODELS`).
      **The `uv sync` is load-bearing and must precede the regen:** `__version__` resolves from
      *installed* metadata, not from `pyproject.toml`, so regenerating without reinstalling re-emits
      the OLD `$id`, leaving the drift guard green-but-wrong locally. Both
      `result_envelope.schema.json` and `analysis_input.schema.json` advance their `$id` version
      segment to `v0.1.0a4`. Verify `git diff schema/` changes **exactly one line per file — the
      `$id` — and nothing else** (a `$id`-only structural no-op). Re-run the drift guard.
- [x] 3.3 **Stage the bumped `uv.lock` (MANDATORY).** `uv.lock` pins this project's own version
      (`sleap-roots-contracts == 0.1.0a3`), so the bump stales it. `uv sync` in 3.2 re-locks it to
      `0.1.0a4`; commit that `uv.lock`. Required, not conditional: **today** PR `ci.yml` runs plain
      `uv sync` (non-frozen) and stays **green with a stale lock**, while the release `build.yml`
      runs `uv lock --check` + `uv sync --frozen` and **hard-fails** — so a forgotten lock bump first
      surfaces at release, after merge, while bloom#411 waits. Task 3.5 closes that gap permanently.
      Confirm with `uv lock --check` locally regardless (see 5.1).
- [x] 3.4 Update `docs/CHANGELOG.md` (use the **actual release date**, not a placeholder):
      - Add `## [0.1.0a4] - <release date> (Pre-release)` under `[Unreleased]`, opening with a
        one-line intro in house style (a3 does this), e.g. "Promotes the param-resolution oracle from
        `sleap-roots-predict` so predict and `bloomctl` share one implementation."
        - `### Added` — `resolve_params`, the pure param-resolution oracle mapping a Bloom
          `cyl_scans_extended` scan-metadata row to `ResolvedParams{species, mode, age}`; exported
          from the package root. Promoted from `sleap-roots-predict` so predict and `bloomctl` share
          one implementation (drift in the normalization would silently break
          `param_hash` → `idempotency_key`). Mention the module-public Bloom column-name constants.
          Do **not** mention `_ALIASES` — a private implementation detail has no place in a
          user-facing changelog.
        - `### Changed` — state a real change, not "none". The emitted schemas are regenerated and
          their `$id` advances to `v0.1.0a4`: a **bytes-only restamp**, no properties added, removed,
          or altered (`resolve_params` is a producer-side function, never emitted to JSON Schema).
          Consumers do the **standard full re-pin** (`pin.json` + vendored schema + regenerated TS),
          accepting the `$id`-only diff — **not** a pip-floor bump.
      - Footer links: repoint `[Unreleased]` → `compare/v0.1.0a4...HEAD`; add
        `[0.1.0a4]: .../compare/v0.1.0a3...v0.1.0a4`.
- [x] 3.5 **Close the stale-lock gap in PR CI** (approved scope addition; two reviewers flagged it,
      and `MEMORY.md/release-uv-lock-bump` records it already broke a release). In
      `.github/workflows/ci.yml`, immediately after the `- run: uv sync` step, add:
      ```yaml
      - name: Verify lockfile is current
        run: uv lock --check
      ```
      This makes a forgotten `uv.lock` bump fail at PR time instead of at the bloom-blocking release,
      and makes this change's own "Commit 2 is green only if `uv.lock` is bumped" claim actually true
      of PR CI. Verify it passes with the re-locked lock from 3.3 (and would fail without it).

## 4. Docs — only what this change falsifies (docs-only, CI-green)

> **Scope rule:** fix exactly the statements this change makes **false**. Pre-existing doc drift
> (the `__init__.py` module docstring's stale one-line inventory; `docs/02`'s old `#v{version}`
> `$id` fragment format at ~L1017) is **out of scope** — file follow-up issues, do not smuggle
> cleanup into a release-blocking PR.

- [x] 4.1 `openspec/project.md`: the Purpose currently reads "dependency-light, **Bloom-agnostic**
      leaf library that defines three contracts." Edit that adjective **in place** — appending a
      qualifier later in the section would leave the file contradicting itself. Replace with wording
      that keeps the honest distinction: the library remains **code-agnostic** toward Bloom (no Bloom
      import, no DB/network/filesystem I/O) but is no longer **vocabulary**-agnostic, because
      `resolve_params` reads Bloom's `cyl_scans_extended` column names (`species_name`,
      `plant_age_days`) as dict keys, hoisted into module constants. Name the param-resolution oracle
      alongside the three contracts, and add `bloomctl` (bloom repo) to the consumer list as an
      importer of `resolve_params`. The Important-Constraints line "does not touch Bloom, the DB,
      Argo, or model code" stays **true** and unedited.
- [x] 4.2 `README.md`: line 5 carries the same unqualified "Bloom-agnostic" adjective — apply the
      same in-place softening, or the two files disagree. Also name `resolve_params` alongside the
      result + provenance, analysis-input, and model-selection contracts, noting it is a pure
      producer-side function (not part of the emitted JSON Schema).
- [x] 4.3 `docs/01-contract-library-design.md`: this change **reverses an explicit scope boundary**
      written in the body — §1 "Explicitly NOT in scope" says *"No Bloom-metadata → params resolution
      logic → #3 (producer / Bloom client)"*, and §5 says the resolution *"lives in the producer /
      Bloom client (#3), keeping the contract Bloom-agnostic and light."* Per the repo's established
      convention (see the `2026-07-04-add-model-card-predict-inference-config` precedent), the **body
      stays frozen**; extend the existing point-in-time banner with the reversal so a standalone
      reader is not misled, e.g.: "§1 and §5 are now **reversed** on one point: the Bloom-metadata →
      params resolver (`resolve_params`) was promoted **into** this library in v0.1.0a4 (#15) as a
      soft, code-agnostic coupling (dict keys only); resolution no longer lives only in #3."
- [x] 4.4 `docs/02-contract-library-plan.md`: its banner says the library "has since evolved
      (v0.1.0a1–a3)" — bump to `a1–a4`. Banner line only; the body stays frozen.

## 5. Verify

- [ ] 5.1 Run `/pre-merge-check`: `black --check`, `ruff check`, full `pytest` + coverage, schema
      drift guard green (over **both** schemas). Reinstall (`uv sync`) first so
      `test_smoke.py::test_version_matches_pyproject` sees `0.1.0a4`. **Also run `uv lock --check`**
      (mirrors the release `build.yml`) so a stale `uv.lock` fails here rather than at release.
- [ ] 5.2 `openspec validate add-param-resolution --strict` passes.
- [ ] 5.3 Confirm the acceptance criteria from issue #15: the ported suite passes with identical
      `values` **and** identical `param_hash` vs predict's implementation, and
      `from sleap_roots_contracts import resolve_params` works at version `0.1.0a4`.
- [ ] 5.4 Open the PR (single bundled PR: feature + release — matches this repo's precedent, where
      `v0.1.0a2` (#8) and `v0.1.0a3` (#10) each shipped feature + bump in one squashed PR, and matches
      #15's explicit "cut the release"). Squash-merge title should carry the version like its
      predecessors: `feat: promote resolve_params param-resolution oracle into contracts (v0.1.0a4)`.

## 6. Cut the release (after merge to `main`)

- [ ] 6.1 Tag and publish the GitHub Release `v0.1.0a4` on `main`. This is the step that triggers
      `build.yml` → PyPI trusted publishing; without it nothing ships and bloom#411 stays blocked.
      `build.yml` validates the tag against `pyproject.toml` (stripping the leading `v`) and greps
      `docs/CHANGELOG.md` for `[0.1.0a4]`, so 3.1 and 3.4 must already be merged.
- [ ] 6.2 Verify the published artifact: in a clean env,
      `uv run --isolated --with sleap-roots-contracts==0.1.0a4 python -c "from sleap_roots_contracts import resolve_params; print(resolve_params({'species_name':'Rice','plant_age_days':3}))"`.

## 7. Post-merge / post-release (NOT part of this PR)

- [ ] 7.1 After merge: `/openspec:archive add-param-resolution` (a separate `chore:` PR — matches the
      standalone `chore: archive …` commits from #9 / #11; do not fold the archive into the feature PR).
- [ ] 7.2 After the `v0.1.0a4` release is published:
      - bloom#411 — re-pin `sleap-roots-contracts>=0.1.0a4` (full re-pin: `pin.json` + vendored schema
        `$id`-only diff + regenerated TS); import `resolve_params` for
        `bloomctl cyl download-for-predict`.
      - predict#28 — re-pin, import from contracts, delete local `param_resolution.py` and its
        `param-resolution` capability spec. **Re-point, do NOT delete, the two `choose_models`
        round-trip tests** (`test_round_trip_selects_expected_models`,
        `test_round_trip_unknown_species_selects_nothing`): they are the only remaining assertion of
        the metadata → params → model wiring, and deleting `test_param_resolution.py` wholesale would
        silently drop that coverage from **both** repos. Re-point TS-parity predict#20 at the
        contracts oracle.
      - `talmolab/sleap-roots-pipeline` `docs/bloom-integration/roadmap.md` — the "param oracle"
        reference now points at a shared contracts home (A3-params umbrella).
      **Do not modify the predict, bloom, or pipeline repos from this session.**
- [ ] 7.3 File follow-up issues for pre-existing debt surfaced by review but **out of scope** here:
      - `.claude/commands/review-openspec.md` states facts from a different repo (claims ~1939 tests
        across 77 files — actually 193 across 11; a `tests/fixtures.py`, `docs/testing.md`, matplotlib
        config, and an "MIT License at line 224" that do not exist here; the repo is GPL-3.0). It
        directs reviewers to hunt for defects that cannot exist, degrading every review that runs it.
      - `src/sleap_roots_contracts/__init__.py`'s module docstring has under-described the package
        since `0.1.0a1` (omits the analysis-input contract, `ModelCard`, the registry).
      - `docs/02-contract-library-plan.md` (~L1017) shows the superseded `#v{version}` `$id` fragment
        format.
      - `build.yml`'s `uv publish` lacks `--skip-existing`, so a retried publish hard-fails.
