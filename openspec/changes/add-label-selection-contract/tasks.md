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
- [x] 6.3 Run `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`
      (293 passed; black + ruff clean)
- [ ] 6.4 `openspec validate add-label-selection-contract --strict` — **BLOCKED:** `openspec` CLI is
      not installed in this environment; run locally/CI
- [ ] 6.5 Release **`0.1.0a5`** (not `0.1.0a4` — already taken by `resolve_params`), then unblock
      `sleap-roots-training`'s `add-label-registry` — **version bumped in `pyproject.toml` + schema
      `$id` regenerated (a4→a5, no structural diff); the actual tag + PyPI publish is a user action**
