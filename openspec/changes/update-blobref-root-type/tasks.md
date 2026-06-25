> **Note:** the sub-steps below are the TDD *working-tree* order (RED→GREEN), **not** a commit
> sequence. The schema drift guard forces two atomic commit units (see `design.md` "Commit
> grouping"): **Unit A** = model + regenerated `result_envelope.schema.json` + fixture/test updates
> + exports, still at `v0.1.0a1` (groups 1–4); **Unit B** = the release bump — `pyproject.toml`
> version (single source as of #6), **both** regenerated schemas, and the CHANGELOG (group 5).
> Never commit a bare RED step.

## 1. Narrow `BlobKind` (test-first)

- [ ] 1.1 RED: in `tests/test_trait_blob.py`, assert `BlobKind`'s allowed set is exactly
      `{"predictions_slp"}` (via `typing.get_args(BlobKind)`), and that constructing a `BlobRef`
      with `kind="labels"` (a previously-valid kind, with a location + `root_type="primary"`) raises
      `ValidationError`.
- [ ] 1.2 GREEN: narrow `BlobKind` to `Literal["predictions_slp"]` in `models.py`.
- [ ] 1.3 Reconcile the existing `test_blobref_rejects_unknown_kind` (currently `kind="not_a_kind"`,
      no `root_type`): add `root_type="primary"` so it isolates the *kind* rule rather than also
      tripping the now-required `root_type`.

## 2. Add `RootType` + required `BlobRef.root_type` (test-first)

- [ ] 2.1 RED: assert a `RootType` vocabulary of exactly `{"primary","lateral","crown"}`
      (via `typing.get_args`); a `BlobRef` built without `root_type` raises `ValidationError`; a
      `BlobRef` with `root_type="seedling"` (out-of-vocab) raises; a `BlobRef` with
      `root_type="primary"` + a location succeeds and **`b.root_type == "primary"`**.
- [ ] 2.2 GREEN: add `RootType = Literal["primary","lateral","crown"]`; add required
      `root_type: RootType` to `BlobRef` (no default). Leave `ModelRef.root_type` as `str | None`
      (recorded decision — see `design.md`).
- [ ] 2.3 Export `RootType` and `BlobKind` from `src/sleap_roots_contracts/__init__.py`
      (`__all__` + import); add a RED-first test that both import from the package root.
      (`test_all_lists_exported_symbols` already guards `__all__↔attr` consistency.)

## 3. Fix existing `BlobRef` constructions broken by the now-required field

- [ ] 3.1 `tests/fixtures/examples.py` — `example_envelope`'s `BlobRef` passes `root_type="primary"`.
- [ ] 3.2 `tests/test_envelope.py` — the `BlobRef` in `test_envelope_round_trips` (line ~37) passes
      `root_type="primary"`. (Untracked by the original Impact; it round-trips a full envelope and
      would otherwise raise.)
- [ ] 3.3 `tests/test_trait_blob.py` — update the two location-rule tests that omit `root_type`:
      `test_blobref_s3_only_ok` (line ~40) gets `root_type="primary"`; `test_blobref_requires_a_location`
      (line ~35) gets `root_type="primary"` so it fails **only** on the missing location, not on the
      missing `root_type`.

## 4. Regenerate + drift-guard `result_envelope.schema.json` (test-first), still at v0.1.0a1

- [ ] 4.1 RED: in `tests/test_schema.py`, assert the rendered `result_envelope` schema's
      `BlobRef.kind` enum is exactly `["predictions_slp"]`; that `root_type` is in the `BlobRef`
      `$def`'s `required` array; and that its enum is exactly `{"primary","lateral","crown"}`.
      (These render-shape assertions pin the output; the genuine RED signal for this group is the
      pre-existing `test_committed_schema_matches_models` drift guard going red against the stale
      committed file until 4.2 regenerates.)
- [ ] 4.2 GREEN: regenerate with `python -m sleap_roots_contracts.schema`; commit the updated
      `schema/result_envelope.schema.json` (`$id` still `v0.1.0a1` — version not yet bumped).
      Confirm the drift guard and JSON-Schema meta-validation pass. `analysis_input.schema.json` is
      untouched at this point and still matches.

## 5. Release `v0.1.0a2` (Unit B — bump pyproject, reinstall, regenerate both schemas)

- [ ] 5.1 Bump `pyproject.toml` → `version = "0.1.0a2"` (single source of version truth as of #6;
      `__init__.__version__` resolves from metadata, so no code edit). Use `uv version 0.1.0a2`.
- [ ] 5.2 Reinstall so the new version is visible, then regenerate **both** schemas:
      `uv sync && python -m sleap_roots_contracts.schema` (writes all `MODELS`). Both
      `result_envelope.schema.json` and `analysis_input.schema.json` have their `$id` version
      segment advance to `v0.1.0a2`. Verify `git diff schema/` shows **only** the two `$id` lines
      changing (plus the BlobRef shape already committed in 4.2). Re-run the drift guard.
      (`test_schema_id_carries_package_version`, on main since #6, already asserts the `$id`/version
      linkage — no new test needed here.)
- [ ] 5.3 Update `docs/CHANGELOG.md`:
      - Add a `## [0.1.0a2] - 2026-06-25 (Pre-release)` section under `[Unreleased]` with:
        - `### Changed` — **BREAKING:** `BlobRef.kind` narrowed to `Literal["predictions_slp"]`;
          **BREAKING:** `BlobRef` now requires `root_type` (`RootType = Literal["primary","lateral","crown"]`,
          no default); exported `BlobKind` + `RootType` from the package root; `ModelRef.root_type`
          intentionally left `str | None` (recorded decision, talmolab/sleap-roots-contracts#5).
        - `### Removed` — **BREAKING:** dropped `labels`, `h5`, `qc_image` from `BlobKind`;
          `traits_csv` permanently excluded (trait numbers are `TraitValue` rows, not blobs).
      - Footer links: repoint `[Unreleased]` → `compare/v0.1.0a2...HEAD`; add
        `[0.1.0a2]: .../compare/v0.1.0a1...v0.1.0a2`.

## 6. Verify

- [ ] 6.1 Run `/pre-merge-check`: `black --check`, `ruff check`, full `pytest` + coverage, schema
      drift guard green (over **both** schemas). Reinstall the package (`uv sync`) before running so
      `test_smoke.py`'s `test_version_matches_pyproject` sees `0.1.0a2`.
- [ ] 6.2 `openspec validate update-blobref-root-type --strict` passes.

## 7. Post-merge / post-release (NOT part of this PR)

- [ ] 7.1 After merge: `/openspec:archive update-blobref-root-type`.
- [ ] 7.2 After the `v0.1.0a2` release is published: comment on Bloom PR
      `Salk-Harnessing-Plants-Initiative/bloom#357` with the new version + tag so the re-pin can
      land and the migration-match parity gate goes green. **Do not modify the Bloom repo from this
      session.**
