## Why

Bloom's pipeline produces exactly **one SLEAP `.slp` prediction file per root type per scan** —
there are no `labels`, `h5`, or `qc_image` artifacts in this contract's world. The current
`BlobRef` over-describes that reality: its `kind` admits four values, and it carries no root-type
label even though every predictions artifact is intrinsically tied to one root type
(`primary` / `lateral` / `crown`).

Bloom's **change C** (sub-project #2, draft PR
`Salk-Harnessing-Plants-Initiative/bloom#357`) narrows its intermediates table to
`kind IN ('predictions_slp')` and adds a `NOT NULL` `root_type` column constrained to those three
values. A **migration-match test in Bloom** asserts that the DB `kind` CHECK equals THIS repo's
`BlobRef.kind` enum byte-for-byte; it is skip-guarded today and flips on (becomes a hard parity
gate) the moment Bloom re-pins to the released contract. To unblock that re-pin, this contract must
narrow `BlobKind` and add the strict `root_type` vocabulary.

This is a deliberate, breaking semantic change to the result contract, released as `v0.1.0a2`.
Tracks `talmolab/sleap-roots-contracts#5`.

## What Changes

- **BREAKING:** Narrow `BlobKind` from `Literal["predictions_slp", "labels", "h5", "qc_image"]` to
  `Literal["predictions_slp"]`. `viewer_html` is deferred (not added now); `traits_csv` is dropped
  on purpose — trait numbers are `TraitValue` rows, not blobs.
- Add a shared controlled vocabulary `RootType = Literal["primary", "lateral", "crown"]`.
- **BREAKING:** Add a **required** `root_type: RootType` field to `BlobRef` (no default). Every
  predictions artifact names the root type it carries.
- Export `RootType` (and `BlobKind`) from the package root so producers and tests share one
  vocabulary definition.
- **Decision (recorded):** `ModelRef.root_type` stays `str | None` — it is **not** tightened to
  `RootType`. Rationale in `design.md`: change C is scoped to the *artifact* contract; the Bloom
  parity gate only asserts on `BlobRef.kind`; and `ModelRef` is a forward-looking pointer into a
  not-yet-existing Bloom models registry where a premature enum buys nothing and risks a future
  widening bump. The `RootType` type is defined once and simply not *applied* to that optional field.
- Update the shared test fixture (`example_envelope`) so its `BlobRef` supplies `root_type`.
- Regenerate `schema/result_envelope.schema.json` from the models (drift-guarded; never hand-edited):
  `BlobRef.kind` becomes a single-value enum, `root_type` becomes a required enum property.
- Release **`v0.1.0a2`**: bump `__version__`, update `docs/CHANGELOG.md`.

## Impact

- Affected specs: `result-contract` (MODIFIED: **Blob References** requirement).
- Affected code:
  - `src/sleap_roots_contracts/models.py` — narrow `BlobKind`; add `RootType`; add required
    `BlobRef.root_type`; leave `ModelRef.root_type` unchanged.
  - `src/sleap_roots_contracts/__init__.py` — export `RootType`, `BlobKind`; bump `__version__` to
    `0.1.0a2`.
  - `pyproject.toml` — bump `version` to `0.1.0a2`. **This repo currently carries the version in TWO
    independent static places** (`pyproject.toml` and `__init__.__version__`); for this release they
    must be bumped together (one-time manual lockstep), and nothing in CI cross-checks them. The
    underlying defect — hardcoded `__version__` instead of analyze-style dynamic versioning — is
    tracked separately in #6 and is **out of scope here** (see `design.md`).
  - `schema/result_envelope.schema.json` **and** `schema/analysis_input.schema.json` — both
    regenerated. The model change touches only `result_envelope`, but each schema's `$id` embeds
    `__version__`, so the version bump restales **both** committed schemas (generated artifacts, CI
    drift-guarded together over all `MODELS`).
  - `tests/fixtures/examples.py` — `BlobRef(..., root_type="primary")`.
  - `tests/test_trait_blob.py`, `tests/test_envelope.py` — existing `BlobRef(...)` constructions
    omit `root_type` and will raise once it is required; updated to supply it (and to keep each test
    isolating the one rule it names).
  - `tests/test_schema.py` — new RED-first assertions on the narrowed `kind` set, the
    required/constrained `root_type`, the regenerated schema, and that each schema `$id` carries the
    bumped version.
  - `docs/CHANGELOG.md` — `0.1.0a2` entry (`### Changed`/`### Removed`, breaking-marked) + footer
    compare-link refresh.
- Intentionally **not** modified: `docs/01-contract-library-design.md` and
  `docs/02-contract-library-plan.md` carry the original 4-value `BlobKind` and `root_type`-free
  `BlobRef` examples. Both are dated, status-marked point-in-time design/plan records (with build
  checkboxes), not living API references. The living contract surface — the Pydantic models, the
  emitted JSON Schema, and the `result-contract` spec — is updated by this change; the historical
  records are left as-is.
- Downstream (separate, not touched here): after release, Bloom #357 re-pins to `v0.1.0a2`; its
  byte-identity drift guard WILL fire on re-pin (intended for a real contract change) and its
  migration-match parity gate goes from skip-guarded to a hard gate. Comment on bloom#357 with the
  new version + tag so the re-pin can land. **This session does not modify the Bloom repo.**
