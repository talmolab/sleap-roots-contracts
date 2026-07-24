## 1. Mode vocabulary

- [x] 1.1 (RED) Test that `Mode` imports from the package root and `get_args(Mode)` yields exactly
      `("cylinder", "multiplant cylinder", "plate")`, and that `cyl` is absent
- [x] 1.2 (GREEN) Add `Mode = Literal["cylinder", "multiplant cylinder", "plate"]` to `models.py`,
      adjacent to `RootType` and subject to the same definition-order constraint documented at
      `models.py:152` (no `from __future__ import annotations` in this module)
- [x] 1.3 Export `Mode` from `__init__.py`

## 2. LabelCard model

- [x] 2.1 (RED) Test valid construction, immutability, and that the best-effort provenance fields
      (`source_experiment`, `bloom_experiment_id`, `accessions`, `labeler`, `box_link`,
      `source_sha256`, `sleap_io_version`) default to `None` — set optional per the resolved design
      (Elizabeth, Slack 2026-07-21), broader than this task's original `box_link`/`sleap_io_version`
- [x] 2.1a Test that all seven provenance fields, when **populated**, survive
      `model_validate` and a JSON round-trip. Closes the gap 2.1 leaves: every other test
      leaves them `None`, so a renamed/aliased field would be dropped by `extra="ignore"`,
      still read `None`, and pass. Verified by mutation (an `alias="boxLink"` on `box_link`
      is invisible to all 48 pre-existing tests, caught by this one). Not TDD — the
      implementation was already correct; this is a guard added in review
- [x] 2.2 (RED) Test that no `data_path` field exists
- [x] 2.3 (GREEN) Add `LabelCard` to `models.py` with `model_config = ConfigDict(frozen=True,
      extra="ignore")`, mirroring `ModelCard` (`models.py:188`) — including the comment explaining why
      `extra="ignore"` is set explicitly rather than relied upon
- [x] 2.4 Export `LabelCard` from `__init__.py`

## 3. Validators

- [x] 3.1 (RED) Test `age_min <= age_max`, negative-bound rejection, and the inclusive single-age
      window (`age_min == age_max`, including `0`)
- [x] 3.2 (GREEN) Implement the age-window model validator, mirroring `ModelCard` (`models.py:208`)
- [x] 3.3 (RED) Test `node_count == len(node_names)`, that the error names both the declared count and
      the actual number of names, and that `node_count = 0` is rejected
- [x] 3.4 (GREEN) Implement the skeleton-coherence model validator
- [x] 3.5 (RED) Test that `mode="cyl"` raises and `mode="cylinder"` succeeds; that a `root_type`
      outside the vocabulary raises
- [x] 3.6 (RED) Test that a `bool` is rejected by every integer field, including the case that
      slips past 3.3 (`node_count=True` coerces to 1 and *satisfies* the coherence check against a
      single node name), and that lax int parsing (`"7"`, `7.0`) still works
- [x] 3.7 (GREEN) Add `NonBoolInt = Annotated[int, BeforeValidator(_reject_bool)]` and apply it to
      all seven integer fields. Reusable by design; **not** applied to `ModelCard` — same exposure,
      but retyping a contract released in `0.1.0a3` is a behavior change tracked as a follow-up
      (see design.md, Risks)
- [x] 3.8 Test the skeleton mismatch in **both** directions — 3.3 covered only declared > actual,
      which a one-sided `<` comparison would also pass; added the spec's own worked example
      (declared 4, five names)
- [x] 3.9 Pin how far one `ValidationError` goes, and document it in design.md for #11's backfill:
      field-level errors aggregate, but any field error suppresses the `mode="after"` validators,
      and those are sequential (the age check short-circuits the skeleton check). Not a bug — how
      pydantic is specified to behave — but the backfill should loop `model_validate` until clean
      rather than treat one error as the full defect list. Not TDD; a guard added in review
- [x] 3.10 Record in design.md + a `models.py` comment why `source_sha256` keeps its
      algorithm-specific name against `ModelCard.weights_checksum`: `weights_checksum` is copied off
      the wandb artifact where the digest algorithm is wandb's detail, while our publish path
      computes `source_sha256` with a pinned algorithm, so the name is a promise. Not renamed

## 4. Tolerant construction

- [x] 4.1 (RED) Test `LabelCard.model_validate` over a mapping merging label metadata with artifact
      identity
- [x] 4.2 (RED) Test that legacy boolean tag flags (`v007: True`, `4nodes: True`) and a stale
      `data_path` are ignored rather than fatal
- [x] 4.3 (GREEN) Confirm `extra="ignore"` covers both; no code change expected beyond 2.3 (confirmed —
      both RED tests passed with no source change)

## 5. Schema boundary

- [x] 5.1 (RED) Test that `LabelCard` is absent from the generated `result_envelope` JSON Schema
      `$defs`, mirroring the existing `ModelCard` guard
- [x] 5.2 Regenerate `schema/*.json` and confirm the CI drift guard stays green (expect **no** diff —
      `LabelCard` is producer↔producer and must not reach the emitted schema; confirmed: zero diff,
      drift-guard tests pass)

## 6. Docs and release

- [x] 6.1 Update `openspec/project.md` — the Purpose paragraph enumerates the contracts ("It defines
      three contracts" → "four contracts"); add the label-selection contract and note it is not
      emitted to JSON Schema
- [x] 6.2 Note in `project.md`'s vocabulary paragraph that contracts now owns `Mode` as well as
      `RootType`, and that training imports it
- [x] 6.2a Add a `[0.1.0a6] - <release date> (Pre-release)` entry to `docs/CHANGELOG.md` (matching
      the `[0.1.0a5]` header format), plus the compare-links footer
      (`[0.1.0a6]: .../compare/v0.1.0a5...v0.1.0a6`) and retarget `[Unreleased]` to
      `.../compare/v0.1.0a6...HEAD` — the `0.1.0a5` doc-sync precedent (archived change, task 2.4)
- [x] 6.2b Add a README.md paragraph introducing `LabelCard`/`Mode`, matching the existing
      one-paragraph-per-contract pattern (archived change, task 2.6)
- [x] 6.2c Append `label-selection-contract` to the capability list in
      `docs/01-contract-library-design.md` (~line 11) and note the `LabelCard`/`Mode` addition in
      the staleness paragraph (archived change, task 2.7)
- [x] 6.3 Run `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`
      (353 passed; black + ruff clean)
- [ ] 6.4 `openspec validate add-label-selection-contract --strict` — **BLOCKED:** `openspec` CLI is
      not installed in this environment; run locally/CI
- [ ] 6.5 Release **`0.1.0a6`** (not `0.1.0a4` — already taken by `resolve_params`), then unblock
      `sleap-roots-training`'s `add-label-registry` — **version bumped in `pyproject.toml` + schema
      `$id` regenerated (a5→a6, no structural diff); the actual tag + PyPI publish is a user action**
