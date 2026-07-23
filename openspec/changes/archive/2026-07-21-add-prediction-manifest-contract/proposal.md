## Why

`bloomctl` (bloom issue #407) needs to construct and upload `cyl_scan_intermediates` blob bytes
from predict's per-scan output. That requires reading `PredictionArtifact`/`PredictionManifest`,
which today are defined only in `sleap-roots-predict` — a package not published to PyPI, and one
a sibling bloom change already rejected taking as a direct `bloomctl` dependency for exactly that
reason. `sleap-roots-contracts` is already a real `bloomctl` dependency and already hosts the
model this data feeds (`BlobRef`), so promoting the shapes here unblocks `bloomctl` without a new
cross-repo dependency. Full rationale, alternatives, and decisions are in
`docs/superpowers/specs/2026-07-21-prediction-manifest-in-contracts-design.md`.

## What Changes

- Add `PredictionArtifact`/`PredictionManifest` (straight lift of all fields from predict's
  `output_contract.py`, plus one new field: `PredictionArtifact.kind: BlobKind =
  "predictions_slp"`) in a new module `src/sleap_roots_contracts/prediction_manifest.py`, reusing
  the existing `BlobKind`/`RootType`/`ModelRef` vocabulary.
- Export both from the package root (`__init__.py`).
- New capability `prediction-manifest-contract` (producer↔producer, like `model-selection-contract`
  — no JSON Schema emission).
- Bump `pyproject.toml` to `0.1.0a5` and re-lock `uv.lock` in this same change.
- **No changes to `sleap-roots-predict`** — that repo keeps its local definitions until a separate
  follow-on session (predict#30) swaps the import and deletes them.
- **No writer/I-O helpers move** — `write_prediction_outputs`, `predict_and_write_batch`,
  `slugify_model_id`, `_validate_scan_key`, `_resolve_identity`, `ScanRequest` all stay in predict.

## Impact

- Affected specs: `prediction-manifest-contract` (new capability)
- Affected code:
  - `src/sleap_roots_contracts/prediction_manifest.py` (new)
  - `src/sleap_roots_contracts/__init__.py` (new imports + `__all__` entries)
  - `pyproject.toml` (version bump)
  - `uv.lock` (re-lock)
  - `tests/test_prediction_manifest.py` (new)
  - `schema/*.json` (`$id`-only restamp to `v0.1.0a5`, forced by the version bump — no field or
    `MODELS` dict changes; see design.md)
  - `docs/CHANGELOG.md`, `openspec/project.md`, `README.md`, `docs/01-contract-library-design.md`
    (doc-sync, matching the `param-resolution` promotion's precedent)
- Not affected: `schema.py`'s `MODELS` dict (gains no entries), `sleap-roots-predict`,
  Bloom/bloomctl (those are tracked follow-ups, not part of this change).
