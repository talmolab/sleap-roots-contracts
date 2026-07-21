## 1. Prediction manifest models (TDD)

- [ ] 1.1 Write failing tests in `tests/test_prediction_manifest.py`: JSON round-trip (with a
      real nested `ModelRef`); `kind` defaults to `"predictions_slp"`; `kind` rejects an
      out-of-vocabulary value (`ValidationError`, mirrors `test_blobref_rejects_unknown_kind`);
      `root_type` rejects an out-of-vocabulary value (`ValidationError`, mirrors
      `test_blobref_rejects_unknown_root_type`); `plant_qr_code` defaults to `scan_key`;
      `schema_version` defaults to `"1"`; both `PredictionArtifact` and `PredictionManifest` are
      frozen (reassigning any field raises); empty `artifacts`/`predict_inference_config`/
      `predict_output_params` defaults when only `scan_key` is given; a manifest with three
      artifacts spanning all three `RootType`s round-trips with all three preserved; a
      `PredictionArtifact`/`PredictionManifest` missing a required field raises
      `ValidationError`; package-root import + `__all__` membership; `PredictionArtifact`/
      `PredictionManifest` absent from `sleap_roots_contracts.schema.MODELS` (mirrors
      `test_model_card_absent_from_result_schema`).
- [ ] 1.2 Implement `PredictionArtifact`/`PredictionManifest` in
      `src/sleap_roots_contracts/prediction_manifest.py`, reusing `BlobKind`/`RootType`/
      `ModelRef` from `.models`.
- [ ] 1.3 Export `PredictionArtifact`/`PredictionManifest` from `src/sleap_roots_contracts/__init__.py`
      (imports + `__all__`).
- [ ] 1.4 Run `uv run pytest tests/test_prediction_manifest.py -v` green.

## 2. Version, release prep, and doc sync

- [ ] 2.1 Bump `pyproject.toml` version to `0.1.0a5`.
- [ ] 2.2 Re-lock `uv.lock` (`uv lock`) in the same commit as the version bump.
- [ ] 2.3 Regenerate `schema/*.json` (`uv run python -m sleap_roots_contracts.schema`) — a
      bytes-only `$id` restamp to `v0.1.0a5` (no field/model changes; `MODELS` dict gains no
      entries), matching the `0.1.0a3`→`0.1.0a4` precedent. Commit the diff.
- [ ] 2.4 Add a `[0.1.0a5]` entry to `docs/CHANGELOG.md` (summary paragraph + `### Added` bullet
      naming the new symbols/rationale + `### Changed` bullet noting the `$id` restamp), plus
      the compare-links footer (`[0.1.0a5]: .../compare/v0.1.0a4...v0.1.0a5`) and retarget
      `[Unreleased]` to `.../compare/v0.1.0a5...HEAD`.
- [ ] 2.5 Update `openspec/project.md`'s `## Purpose` section: "three contracts" → "four
      contracts", adding the prediction-manifest contract description.
- [ ] 2.6 Add a README.md paragraph introducing `PredictionArtifact`/`PredictionManifest`,
      matching the existing one-paragraph-per-contract pattern.
- [ ] 2.7 Append `prediction-manifest-contract` to the capability list in
      `docs/01-contract-library-design.md` (~line 11).

## 3. Validation

- [ ] 3.1 `uv run black --check src tests`
- [ ] 3.2 `uv run ruff check src tests`
- [ ] 3.3 `uv lock --check` (verifies the re-lock in 2.2 is current; PR CI's plain `uv sync`
      won't catch a stale lock — only the release build's `--frozen` sync does)
- [ ] 3.4 `uv run python -m sleap_roots_contracts.schema && git diff --exit-code schema/`
      (schema drift guard, confirms 2.3 mechanically)
- [ ] 3.5 `uv run pytest -v --cov=src/sleap_roots_contracts --cov-report=term-missing` (full suite)
- [ ] 3.6 `openspec validate add-prediction-manifest-contract --strict`
