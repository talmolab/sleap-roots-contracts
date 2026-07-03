> **Note:** the sub-steps below are the TDD *working-tree* order (RED→GREEN), **not** a commit
> sequence. Commits split along the capability seam + the schema/version coupling (see `design.md`
> "Commit grouping"), each green on its own:
> - **Commit 1 (`feat:` ModelCard)** — group 1 only: `ModelCard` + exports + tests. Touches **no
>   schema** (ModelCard is not emitted), so the drift guard is untouched. Green.
> - **Commit 2 (`feat:` predict inference config)** — groups 2–4: the two `Provenance` fields, the
>   `identity.py` kwarg, tests, and the regenerated `result_envelope.schema.json` (`$id` still
>   `v0.1.0a2`). Green.
> - **Commit 3 (`chore(release):`)** — group 5: `pyproject.toml` → `0.1.0a3`, `uv sync`, **both**
>   regenerated schemas (`$id` → `v0.1.0a3`), CHANGELOG. Green only if both schemas move together.
> - **Commit 4 (`docs:`)** — group 6: capability-inventory doc updates (`project.md`, README).
>   Docs-only; may fold into Commit 3.
>
> Groups 1 and 2 are order-independent. Never commit a bare RED step. Tests are pure
> pydantic/schema/idempotency — **no mocks**.

## 1. `ModelCard` model-selection contract (test-first)

- [ ] 1.1 RED: in a new `tests/test_model_card.py`, assert a valid `ModelCard` constructs and retains
      its fields; `age_min > age_max` raises `ValidationError`; a negative `age_min`/`age_max` raises;
      a **single-age, zero-inclusive window** (`age_min == age_max`, incl. both `0` and both `7`)
      constructs successfully (inclusive window boundary); a `root_type` outside
      `{primary, lateral, crown}` raises; a card built without `sleap_nn_version` has
      `sleap_nn_version is None`; reassigning a field raises (frozen).
- [ ] 1.2 GREEN: add `ModelCard` to `models.py` next to `ModelRef` — `model_config = _FROZEN`; fields
      `species: str`, `mode: str`, `age_min: int = Field(ge=0)`, `age_max: int = Field(ge=0)`,
      `root_type: RootType`, `registry_id: str`, `version: str`, `weights_checksum: str | None = None`,
      `sleap_nn_version: str | None = None`; a `@model_validator(mode="after")` enforcing
      `age_min <= age_max`. Import `Field` from pydantic. Google-style docstring documenting the
      metadata-vs-artifact-intrinsic field split and the contiguous approved-window semantics.
- [ ] 1.3 RED: assert `card.to_model_ref("runtime-x")` returns a `ModelRef` with
      `sleap_nn_version == "runtime-x"` (the RUNTIME value, not the card's trained-with value) that
      carries the card's `registry_id`, `version`, `root_type`, and `weights_checksum`; that it works
      when the card's `sleap_nn_version is None`; and that a card with `weights_checksum is None`
      yields `ModelRef.weights_checksum is None` (the None-card path that could regress
      `ModelRef`'s required `sleap_nn_version`).
- [ ] 1.4 GREEN: implement `ModelCard.to_model_ref(runtime_sleap_nn_version)` — pure, no warning.
- [ ] 1.5 RED: assert `ModelCard.model_validate({**selection_metadata, **artifact_identity})`
      succeeds (merged-dict round-trip), where the **7 required** fields are the selection metadata
      (`species`, `mode`, `age_min`, `age_max`, `root_type`) merged with the artifact identity
      (`registry_id`, `version`); and that `model_validate({...those 7 fields..., "soybean": True,
      "oks_map": 0.8, "training_config": {...}})` succeeds and ignores the extras.
- [ ] 1.6 GREEN: confirm the model tolerates extras (pydantic v2 default `extra="ignore"`); do **not**
      set `extra="forbid"`. No code change expected beyond 1.2 if the default holds — the test pins it.
- [ ] 1.7 Export `ModelCard` from `src/sleap_roots_contracts/__init__.py` (`__all__` + import). Add an
      assertion to `tests/test_envelope.py::test_public_exports_importable` (or a new root-import test)
      that `ModelCard` imports from the package root. (`test_all_lists_exported_symbols` already guards
      `__all__ ↔ attr` consistency.)
- [ ] 1.8 RED→GREEN: in `tests/test_model_card.py` (or `test_schema.py`), assert `"ModelCard"` is
      **absent** from `json.loads(render("result_envelope"))["$defs"]` — pins that the selection
      contract does not leak into the Bloom-facing schema. Passes as soon as `ModelCard` is unreferenced
      by `ResultEnvelope` (no emitter change needed).

## 2. `Provenance` inference-config fields (test-first)

- [ ] 2.1 RED: in `tests/test_provenance.py`, assert a `Provenance` accepts `predict_inference_config`
      and `predict_output_params` mappings and retains them; and that a `Provenance` built without
      either field constructs fine with both defaulting to `None`.
- [ ] 2.2 GREEN: add `predict_inference_config: dict[str, Any] | None = None` and
      `predict_output_params: dict[str, Any] | None = None` to `Provenance` (in the predict-stage
      block). `Any` is already imported.
- [ ] 2.3 RED→GREEN: assert both new fields survive a JSON round-trip — build a `Provenance` with
      `predict_inference_config={"device": "cuda", "batch_size": 4}` and
      `predict_output_params={"peak_threshold": 0.2}`, re-parse via `Provenance.model_validate_json(
      p.model_dump_json())`, and assert the two mappings and the `idempotency_key` are preserved.
      (Passes once 2.2 + group 3 land; pins serialization.)

## 3. Idempotency contribution + byte-identical backward compat (test-first)

      > **Golden digests were captured from PRE-CHANGE `main` (this branch's `identity.py`/`models.py`
      > are still unmodified until 3.2/3.4), so they prove BYTE-IDENTITY with existing producers' keys
      > — not mere post-change self-consistency. Do NOT re-derive them from the green run.**
      > `compute_idempotency_key(**BASE)` (the `test_identity.py` `BASE`) =
      > `913e6492c459a4475231badb54c073243f98cfb0fed03db60b8bb507e2387e09`. The self-contained golden
      > `Provenance` (inlined literals below) = `42f67605ab4eac398f6c7c331cb4f267b6c5864a609bedc741b8dca8ea5f98d3`.

- [ ] 3.1 RED: in `tests/test_identity.py`, assert `compute_idempotency_key(**BASE,
      predict_output_params=None)` equals `compute_idempotency_key(**BASE)` (append-nothing); that an
      empty `{}` equals `None`; that a populated `{"peak_threshold": 0.2}` yields a **different** key;
      that two distinct output-param dicts yield distinct keys; that a **present-but-falsy** value
      `{"peak_threshold": 0.0}` still changes the key (guards the truthy-gate against a mistaken
      `if any(values)`); and a **golden**: `compute_idempotency_key(**BASE) == "913e64…387e09"`
      (pins byte-stability of the six-key payload itself).
- [ ] 3.2 GREEN: add `predict_output_params: dict | None = None` to `compute_idempotency_key`; add
      `payload["predict_output_params"] = predict_output_params` **only when truthy** so an
      absent/empty value keeps the canonical payload byte-identical to today. Extend the docstring.
- [ ] 3.3 RED: in `tests/test_provenance.py`, assert (a) a `Provenance` without the new fields has an
      `idempotency_key` equal to `compute_idempotency_key(...)` with no output-params arg; (b) a
      **golden byte-identity** test — a `Provenance` built from **inlined literal inputs local to the
      test** (NOT `make_provenance`, so a later fixture edit cannot silently re-baseline it) hashes to
      the exact pre-change digest `42f676…f98d3`; (c) populating
      `predict_output_params={"peak_threshold": 0.2}` changes the key; (d) two provenances differing
      **only** in `predict_inference_config` (e.g. `device`) with identical `predict_output_params`
      produce the **same** key; (e) two provenances differing **only** in `predict_output_params`
      (`peak_threshold`) produce different keys; (f) a `predict_output_params` with a non-finite value
      (`float("nan")`) raises `ValidationError` at construction (canonicalization runs in the
      validator, consistent with `param_hash`).
- [ ] 3.4 GREEN: in `Provenance._fill_idempotency_key`, pass
      `predict_output_params=self.predict_output_params` into `compute_idempotency_key`. The golden
      digests in 3.1/3.3 were already captured from pre-change code (see the note above) — they must
      stay green unchanged; if either moves, the byte-identity guarantee has been broken, so
      investigate rather than re-baseline.

## 4. Regenerate + drift-guard `result_envelope.schema.json` (test-first), still at v0.1.0a2

- [ ] 4.1 RED: in `tests/test_schema.py`, assert the rendered `result_envelope` `Provenance` `$def`
      exposes `predict_inference_config` and `predict_output_params` as properties **not** listed in
      its `required` array; and that an `example`-style envelope with both fields populated validates
      against the emitted schema. (The genuine RED signal for this group is the pre-existing
      `test_committed_schema_matches_models` drift guard going red against the stale committed file
      until 4.2 regenerates.)
- [ ] 4.2 GREEN: regenerate with `python -m sleap_roots_contracts.schema`; commit the updated
      `schema/result_envelope.schema.json` (`$id` still `v0.1.0a2` — version not yet bumped). Confirm
      the drift guard and JSON-Schema meta-validation pass; `analysis_input.schema.json` is untouched
      and still matches.

## 5. Release `v0.1.0a3` (Unit B — bump pyproject, reinstall, regenerate both schemas)

- [ ] 5.1 Bump `pyproject.toml` → `version = "0.1.0a3"` via `uv version 0.1.0a3` (single source of
      truth; `__init__.__version__` resolves from metadata, so no code edit).
- [ ] 5.2 `uv sync && python -m sleap_roots_contracts.schema` (writes all `MODELS`). Both
      `result_envelope.schema.json` and `analysis_input.schema.json` advance their `$id` version
      segment to `v0.1.0a3`. Verify `git diff schema/` shows the two `$id` lines changing (plus the
      `Provenance` shape already committed in 4.2). Re-run the drift guard.
- [ ] 5.3 Update `docs/CHANGELOG.md`:
      - Add a `## [0.1.0a3] - 2026-07-03 (Pre-release)` section under `[Unreleased]` with an `### Added`
        entry: the `ModelCard` model-selection contract (selection + identity fields, optional
        trained-with `sleap_nn_version`, `to_model_ref` runtime stamping, not emitted to JSON Schema);
        and `Provenance.predict_inference_config` + `predict_output_params`, the latter folded into
        `idempotency_key` (output-defining knobs hashed; hardware knobs recorded but not hashed;
        byte-identical when absent). Note `contract_version` is producer-set and needs no forced bump.
      - Footer links: repoint `[Unreleased]` → `compare/v0.1.0a3...HEAD`; add
        `[0.1.0a3]: .../compare/v0.1.0a2...v0.1.0a3`.
      - Split the body into `### Added` (the `ModelCard` model-selection contract; the two
        `Provenance` fields) **and** a short `### Changed` note that `compute_idempotency_key` gains an
        optional `predict_output_params` and folds it into the key, with existing keys unchanged when
        absent (byte-identical) — mirroring the MODIFIED spec requirement honestly.

## 6. Docs — capability inventory (Commit 4; docs-only, CI-green)

- [ ] 6.1 `openspec/project.md`: update the Purpose from "defines **two** contracts" to **three**,
      naming the new **model-selection contract** — the Python-side `ModelCard` shape shared by
      `sleap-roots-training` (writer) and `sleap-roots-predict` (reader), **not** emitted to JSON
      Schema. Add `sleap-roots-training` to the External Dependencies / consumers list as the ModelCard
      **writer** (it is currently absent), and note predict's new model-selection reader role.
- [ ] 6.2 `README.md`: name the model-selection contract / `ModelCard` alongside the result +
      provenance and analysis-input contracts, noting it is a producer↔producer contract not in the
      emitted schema. (README hardcodes no version and does not enumerate model classes, so only the
      contract-inventory framing needs updating.)

## 7. Verify

- [ ] 7.1 Run `/pre-merge-check`: `black --check`, `ruff check`, full `pytest` + coverage, schema
      drift guard green (over **both** schemas). Reinstall the package (`uv sync`) before running so
      `test_smoke.py::test_version_matches_pyproject` sees `0.1.0a3`.
- [ ] 7.2 `openspec validate add-model-card-predict-inference-config --strict` passes.

## 8. Post-merge / post-release (NOT part of this PR)

- [ ] 8.1 After merge: `/openspec:archive add-model-card-predict-inference-config`.
- [ ] 8.2 After the `v0.1.0a3` release is published: `sleap-roots-predict` (branch
      `add-warm-model-worker`) pins to `0.1.0a3` and resumes; coordinate the A3/A4 reproducibility
      roadmap update (owned by the predict slice). **Do not modify the predict/training/pipeline repos
      from this session.**
