**Commit granularity note** (from adversarial review, 2026-08-04): this repo's precedent for a
brand-new, from-scratch contract model (`add-label-selection-contract`, `add-prediction-manifest-contract`)
lands as a small number of commits at section boundaries — not one commit per RED/GREEN subtask
below. Implement sections 1-3 as RED/GREEN steps for TDD discipline, but commit once after section
3, once after sections 4-5, and once after section 6 (docs + release prep).

## 1. RunManifest model

- [ ] 1.1 (RED) Test that `RunManifest` requires `pipeline_run_id` and `scan_keys` (missing either
      raises `ValidationError`)
- [ ] 1.2 (RED) Test `schema_version` defaults to `"1"`
- [ ] 1.3 (GREEN) Add `src/sleap_roots_contracts/run_manifest.py` with `RunManifest`
      (`model_config = ConfigDict(frozen=True)`, `schema_version: str = "1"`,
      `pipeline_run_id: str`, `scan_keys: list[str]`)
- [ ] 1.4 Test the manifest is frozen (mutation raises) — not RED/GREEN, this behavior is free
      from `frozen=True` once 1.3 lands; the test is a guard, not a driver
- [ ] 1.5 Test round-trips through JSON (`model_dump_json`/`model_validate_json`) and through dict
      (`model_dump`/`model_validate`), using realistic fixture values
      (`scan_keys=["scan_1009", "scan_577", "scan_289"]`,
      `pipeline_run_id="sleap-roots-pipeline-abc123xy"`) rather than placeholders — also a guard,
      not RED/GREEN, for the same reason as 1.4

## 2. Validators

- [ ] 2.1 (RED) Test `scan_keys=[]` raises `ValidationError`
- [ ] 2.2 (GREEN) Add the non-empty-list validator
- [ ] 2.3 (RED) Test `scan_keys=["scan_1", "scan_1"]` raises `ValidationError`
- [ ] 2.4 (GREEN) Add the no-duplicates validator
- [ ] 2.5 (RED) Test `scan_keys=["scan_1", ""]` (and a whitespace-only entry, `"  "`) raises
      `ValidationError`
- [ ] 2.6 (GREEN) Add the blank-element validator (reject empty/whitespace-only strings in
      `scan_keys`)
- [ ] 2.7 Confirming tests (no code change expected — pydantic v2's default lax mode does not
      coerce `int`/`float`/`None` into a `str` field, unlike its `int` field lax-coercion of
      `bool`): `scan_keys=[1009, 577]` raises `ValidationError`; `scan_keys=["scan_1", None]`
      raises `ValidationError`; constructing with `["scan_3", "scan_1", "scan_2"]` and asserting
      `.scan_keys` preserves that exact order, including after a JSON round-trip. These pin
      today's correct default behavior against a future regression (e.g. a lenient custom
      validator or config change) — see design.md's bloom#555 discussion for why the
      int/str boundary specifically is load-bearing here

## 3. Filename constant + package export

- [ ] 3.1 (RED) Test `RUN_MANIFEST_FILENAME == "run_manifest.json"` (pinned literal — a future
      rename must be a visible, deliberate diff here)
- [ ] 3.2 (GREEN) Add `RUN_MANIFEST_FILENAME = "run_manifest.json"` to `run_manifest.py`
- [ ] 3.3 (RED) Test `from sleap_roots_contracts import RunManifest, RUN_MANIFEST_FILENAME`
      succeeds and both names are in `__all__`
- [ ] 3.4 (GREEN) Export both from `src/sleap_roots_contracts/__init__.py`

## 4. Schema boundary

Depends on section 3 (imports `RunManifest` via the package root, not the submodule, so the
export path itself is exercised).

- [ ] 4.1 (RED) Test `RunManifest` is absent from `schema.py`'s `MODELS` (extends the existing
      `test_prediction_manifest_absent_from_schema_models`-style assertion:
      `set(MODELS) == {"result_envelope", "analysis_input"}` and `RunManifest not in
      MODELS.values()`)
- [ ] 4.2 Regenerate `schema/*.json` and confirm the CI drift guard is green (expect zero diff at
      this point — no version bump has happened yet; re-verified again after 6.7's bump, see task
      6.8)

## 5. Real-file round-trip

Depends on section 3 (`RUN_MANIFEST_FILENAME`).

- [ ] 5.1 Add a `tmp_path`-based test that writes `model_dump_json()` to a file named
      `RUN_MANIFEST_FILENAME` (not an arbitrary name — exercises the real constant, not just the
      model) and reads it back with `Path.read_text(encoding="utf-8")` +
      `model_validate_json()` — exercises the literal write/read boundary the filesystem contract
      actually crosses (encoding, whitespace), not just an in-memory round-trip. Not TDD (no
      behavior change expected) — a guard against a future encoding regression, mirroring
      bloom#555's own lesson that only a real read/write path catches this class of bug

## 6. Docs and release

- [ ] 6.1 Update `openspec/project.md` — the Purpose paragraph enumerates the contracts ("five
      contracts" → "six contracts"); add the run-manifest contract and note it is not emitted to
      JSON Schema; update the **"External Dependencies"** section (not "Downstream consumers" —
      that section doesn't exist under that name) to note `bloomctl` writes it and
      `sleap-roots-predict`/`sleap-roots`-traits read it once their consuming PRs land (not yet)
- [ ] 6.2 Add a `[0.1.0a7] - <release date> (Pre-release)` entry to `docs/CHANGELOG.md`, matching
      the `[0.1.0a6]` header format, plus the compare-links footer and retargeted `[Unreleased]`
      link
- [ ] 6.3 Add a README.md paragraph introducing `RunManifest`/`RUN_MANIFEST_FILENAME`, matching the
      existing one-paragraph-per-contract pattern (writer/reader + "not emitted to JSON Schema" —
      no incident narrative; that detail stays in the design docs)
- [ ] 6.4 Append `run-manifest-contract` to the capability list in
      `docs/01-contract-library-design.md`'s staleness paragraph and add a sentence noting the
      `RunManifest`/`RUN_MANIFEST_FILENAME` addition in `0.1.0a7`, mirroring the
      `label-selection-contract` precedent (`add-label-selection-contract` task 6.2c)
- [ ] 6.5 Run `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`
- [ ] 6.6 `openspec validate add-run-manifest-contract --strict`
- [ ] 6.7 Bump `pyproject.toml` to `0.1.0a7` and re-lock `uv.lock` in the same commit (a version
      bump without a re-lock hard-fails the release build, and PR CI does not catch it — the
      `0.1.0a4` release history)
- [ ] 6.8 **After** 6.7 (order matters — `schema.py`'s `render()` embeds `__version__` in every
      schema's `$id`, so any version bump restamps `schema/*.json` even though this change touches
      neither `ResultEnvelope` nor `AnalysisInputRow`): regenerate `schema/*.json` and re-run the
      full verification suite — `uv run pytest -v`, `uv run black --check src tests`,
      `uv run ruff check src tests`, `uv lock --check`, and confirm the schema drift guard
      (`git diff --exit-code schema/`) is clean against the restamped `$id`
- [ ] 6.9 Release `0.1.0a7` via `/prepare-release` (tag + PyPI publish is a user action)

## 7. Archive gate — MUST be closed before `openspec archive`

Not a checkbox to tick off with the rest: archiving folds this change's deltas into
`openspec/specs/`, so anything missing here becomes permanently unspecified with no later prompt to
fix it.

- [ ] 7.1 **BLOCKING.** `0.1.0a7` must be tagged and published to PyPI before this change is
      archived (mirrors the `add-label-selection-contract` gate) — archiving a contract whose
      release never happened leaves `openspec/specs/` describing a version consumers cannot
      install.
- [ ] 7.2 Comment on and update talmolab/sleap-roots-pipeline#37 with what shipped (draft, get
      approval before posting). Include the three known limitations from design.md's "Known
      limitations" section — the fixed-filename concurrent-run race, `write-back`'s identical
      unscoped-glob gap (a 4th consumer needing the same fix, not previously tracked), and
      `bloomctl`'s missing `pipeline_run_id` source — so they're tracked cross-repo, not lost.
- [ ] 7.3 Update `docs/bloom-integration/roadmap.md`'s "Cross-repo correctness" subsection —
      flip the `sleap-roots-contracts` row from ⬜ to ✅, record the version, and note the
      file-based (not CLI-arg) decision (draft, get approval before committing).
