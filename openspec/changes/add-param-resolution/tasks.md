> **Note:** the sub-steps below are the TDD *working-tree* order (RED→GREEN), **not** a commit
> sequence. Commits split along the code/release/docs seam (see `design.md` "Commit grouping"), each
> green on its own:
> - **Commit 1 (`feat:`)** — groups 1–2: `params.py`, the package export, and `tests/test_params.py`.
>   Pure Python; touches **no schema**, so the drift guard is untouched. Green.
> - **Commit 2 (`chore(release):`)** — group 3: `pyproject.toml` → `0.1.0a4`, `uv sync`, the re-locked
>   **`uv.lock`** (mandatory — it pins the project's own version), **both** regenerated schemas
>   (`$id` → `v0.1.0a4`), CHANGELOG. Green only if both schemas move together and `uv.lock` is bumped.
> - **Commit 3 (`docs:`)** — group 4: `openspec/project.md`, `README.md`. Docs-only; may fold into
>   Commit 2.
>
> Never commit a bare RED step. Tests are pure functions over dicts — **no mocks, no I/O**.
>
> **Porting discipline:** this is a behavior-preserving port. The resolved `values` feed
> `param_hash` → `idempotency_key`, so any drift silently breaks cross-producer idempotency with no
> error raised. Do **not** clean up, rename, re-order, or "improve" the ported logic. The single
> permitted edit is the `ResolvedParams` import (task 1.2).

## 1. Port the oracle (test-first)

- [ ] 1.1 RED: create `tests/test_params.py` by porting `sleap-roots-predict/tests/test_param_resolution.py`
      at HEAD — **32 of its 34** test functions, verbatim. Adaptations, and only these:
      - imports become `from sleap_roots_contracts import ModelCard, ResolvedParams, resolve_params`
        and `from sleap_roots_contracts import params` (the module, for the `_ALIASES` monkeypatch);
        private helpers import from `sleap_roots_contracts.params`.
      - **Drop the 2 round-trip tests** (`test_round_trip_selects_expected_models`,
        `test_round_trip_unknown_species_selects_nothing`) — they call `choose_models`, which does not
        exist in this repo (issue #13). They stay in predict. Do **not** write a stub predicate.
      - **Keep** `test_mode_matches_seeded_card_vocabulary` (needs only `ModelCard`) and the `_card`
        helper it uses; drop the `choose_models` import.
      Confirm RED: `uv run pytest tests/test_params.py` fails at import (`params` does not exist).
- [ ] 1.2 GREEN: create `src/sleap_roots_contracts/params.py` by porting
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
- [ ] 1.3 Verify GREEN: `uv run pytest tests/test_params.py -v` — all 32 pass.

## 2. Public API export + the added tests (test-first)

- [ ] 2.1 RED: add `test_resolve_params_is_exported` to `tests/test_params.py` — `from
      sleap_roots_contracts import resolve_params` succeeds and `"resolve_params" in
      sleap_roots_contracts.__all__`. Also assert `SPECIES_NAME_FIELD`/`PLANT_AGE_DAYS_FIELD` are
      **absent** from `__all__` (module-public, not package API — mirrors predict).
- [ ] 2.2 GREEN: export `resolve_params` from `src/sleap_roots_contracts/__init__.py` (import +
      `__all__`, grouped with a short comment like the existing sections).
      `tests/test_envelope.py::test_all_lists_exported_symbols` already guards `__all__ ↔ attr`
      consistency and must stay green.
- [ ] 2.3 RED→GREEN: add `test_canonical_row_hashes_to_known_answer` — resolving a row to
      `{"species": "pennycress", "mode": "cylinder", "age": 14}` yields `param_hash ==
      "d7562d09b93a57ba6c1a128f27c6c8022c023365a3243e7508423b45756faecb"`.
      This digest was captured from the **pre-change** installed package (`0.1.0a3`), so it proves
      cross-release stability rather than post-change self-consistency. It passes as soon as 1.2
      lands. **If it ever goes red, a normalization or `compute_param_hash` canonicalization bug has
      been introduced — investigate, do NOT re-baseline.**
- [ ] 2.4 Verify: `uv run pytest -v` (full suite) green; `uv run black --check src tests` and
      `uv run ruff check src tests` clean.

## 3. Release `v0.1.0a4` (bump, re-lock, regenerate both schemas)

- [ ] 3.1 Bump `pyproject.toml` → `version = "0.1.0a4"` via `uv version 0.1.0a4` (single source of
      truth; `__init__.__version__` resolves from installed metadata, so no code edit).
- [ ] 3.2 `uv sync && uv run python -m sleap_roots_contracts.schema` (writes all `MODELS`). Both
      `result_envelope.schema.json` and `analysis_input.schema.json` advance their `$id` version
      segment to `v0.1.0a4`. Verify `git diff schema/` shows **exactly two changed lines — the two
      `$id`s — and nothing else** (a `$id`-only structural no-op). Re-run the drift guard.
- [ ] 3.3 **Stage the bumped `uv.lock` (MANDATORY).** `uv.lock` pins this project's own version
      (`sleap-roots-contracts == 0.1.0a3`), so the bump stales it. `uv sync` in 3.2 re-locks it to
      `0.1.0a4`; commit that `uv.lock`. Required, not conditional: PR `ci.yml` runs plain `uv sync`
      (non-frozen) and stays **green with a stale lock**, but the release `build.yml` runs
      `uv lock --check` + `uv sync --frozen` and **hard-fails** — so a forgotten lock bump first
      surfaces at release, not in PR CI. Confirm with `uv lock --check` locally (see 5.1).
- [ ] 3.4 Update `docs/CHANGELOG.md` (use the **actual release date**, not a placeholder):
      - Add `## [0.1.0a4] - <release date> (Pre-release)` under `[Unreleased]`, with:
        - `### Added` — `resolve_params`, the pure param-resolution oracle mapping a Bloom
          `cyl_scans_extended` scan-metadata row to `ResolvedParams{species, mode, age}`; exported
          from the package root. Promoted from `sleap-roots-predict` so predict and `bloomctl` share
          one implementation (drift in the normalization would silently break
          `param_hash` → `idempotency_key`). Note the module-public Bloom column-name constants and
          the empty `_ALIASES` seam.
        - `### Changed` — none functionally; note the emitted schemas' `$id` advances to `v0.1.0a4`
          (a **structural no-op**; no properties added or removed). Say so plainly so a consumer
          reading the diff is not surprised, and state that consumers should do the standard full
          re-pin rather than a pip-floor bump.
      - Footer links: repoint `[Unreleased]` → `compare/v0.1.0a4...HEAD`; add
        `[0.1.0a4]: .../compare/v0.1.0a3...v0.1.0a4`.

## 4. Docs — capability inventory + the documented coupling (docs-only, CI-green)

- [ ] 4.1 `openspec/project.md`: name the param-resolution oracle in the Purpose alongside the three
      existing contracts, and record that this library knowingly owns a **soft, documented** coupling
      to Bloom's `cyl_scans_extended` column names (`species_name`, `plant_age_days`) — dict keys
      only, hoisted into module constants; no Bloom import and no DB/network/filesystem dependency, so
      the "dependency-light leaf" and "no DB/network" constraints still hold. Add `bloomctl` (bloom
      repo) to the consumer list as an importer of `resolve_params`. Do not overstate: the library is
      no longer *vocabulary*-agnostic toward Bloom, though it remains *code*-agnostic.
- [ ] 4.2 `README.md`: name `resolve_params` alongside the result + provenance, analysis-input, and
      model-selection contracts, noting it is a pure producer-side function (not part of the emitted
      JSON Schema).

## 5. Verify

- [ ] 5.1 Run `/pre-merge-check`: `black --check`, `ruff check`, full `pytest` + coverage, schema
      drift guard green (over **both** schemas). Reinstall (`uv sync`) first so
      `test_smoke.py::test_version_matches_pyproject` sees `0.1.0a4`. **Also run `uv lock --check`**
      (mirrors the release `build.yml`, which PR `ci.yml` does not) so a stale `uv.lock` fails here
      instead of at release.
- [ ] 5.2 `openspec validate add-param-resolution --strict` passes.
- [ ] 5.3 Confirm the acceptance criteria from issue #15: the ported suite passes with identical
      `values` **and** identical `param_hash` vs predict's implementation, and
      `from sleap_roots_contracts import resolve_params` works at version `0.1.0a4`.

## 6. Post-merge / post-release (NOT part of this PR)

- [ ] 6.1 After merge: `/openspec:archive add-param-resolution`.
- [ ] 6.2 After the `v0.1.0a4` release is published:
      - bloom#411 — re-pin `sleap-roots-contracts>=0.1.0a4` (full re-pin: `pin.json` + vendored schema
        `$id`-only diff + regenerated TS); import `resolve_params` for
        `bloomctl cyl download-for-predict`.
      - predict#28 — re-pin, import from contracts, delete local `param_resolution.py` and its
        `param-resolution` capability spec; re-point TS-parity predict#20 at the contracts oracle.
      - `talmolab/sleap-roots-pipeline` `docs/bloom-integration/roadmap.md` — the "param oracle"
        reference now points at a shared contracts home (A3-params umbrella).
      **Do not modify the predict, bloom, or pipeline repos from this session.**
