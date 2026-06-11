# Project Context

## Purpose
`sleap-roots-contracts` is the shared **data contract** library for the sleap-roots ↔ Bloom
pipeline. It is a small, dependency-light, **Bloom-agnostic** leaf library that defines two
contracts: (1) the **result + provenance contract** — the shape of a per-scan pipeline result
and its provenance (Pydantic v2 models) — and (2) the **analysis-input contract** — the
canonical wide trait table, with a structural `validate_analysis_input` validator. It emits
versioned JSON Schema artifacts and ships a trait-definitions registry.

Producers (`sleap-roots-predict`, `sleap-roots-traits`) import it; **Bloom consumes the emitted
JSON Schema** (codegen + migration-match). It is sub-project #1 of the sleap-roots ↔ Bloom
integration program (see `docs/01-contract-library-design.md` and `docs/02-contract-library-plan.md`).

## Tech Stack
- Python ≥3.11
- uv + `uv_build` (build backend)
- Pydantic v2 (canonical source of truth for the contracts)
- PyYAML (trait-definitions registry)
- pandas — **optional** `[pandas]` extra, required only by `validate_analysis_input`
  (runtime core stays pydantic + pyyaml)
- pytest + pytest-cov; ruff + black; jsonschema (schema meta-validation)
- GitHub Actions (CI + PyPI trusted publishing). **Distributed via PyPI — no Docker/GHCR**
  (the container rule applies to the pipeline services, not this library).

## Project Conventions

### Code Style
- src layout: `src/sleap_roots_contracts/`; tests in `tests/`.
- black line-length 88; ruff with pydocstyle (google convention); docstrings required in
  `src/` (tests exempt via per-file-ignore).
- Run: `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`.

### Architecture Patterns
- **Pydantic is canonical**; `schema/*.json` is *generated* from the models and **drift-guarded
  in CI** (regenerate must equal committed). Schema version = package semver, carried in `$id`.
- Trait **values** are long-format rows (no jsonb); provenance is a jsonb blob on the source row.
- Hashes (`param_hash`, `idempotency_key`) are **producer-side only**; Bloom treats them as
  **opaque strings** and never recomputes them.
- The library does **not** touch Bloom, the DB, Argo, or model code — those live in sibling repos.

### Testing Strategy
- **TDD** (red → green → commit) for every model/function; see `.claude/commands/tdd.md`.
- Known-answer + edge-case tests (NaN/inf → null, order-independence, range validation).
- Schema round-trip + snapshot drift guard + JSON-Schema meta-validation.

### Git Workflow
- Branch per change; PR into `main`; CI must pass.
- Work is **spec-driven via OpenSpec**: `/openspec:proposal` to start, `/openspec:apply` to keep
  tasks in sync, `/openspec:archive` after merge. Use `/new-feature` to kick off the whole loop.

## Domain Context
Plant root phenotyping. A "scan" is one cylinder scan (≈ one plant). The pipeline detects
multiple root types (primary / lateral / crown), each from a separate SLEAP model. Trait
values are stored in Bloom long-format (`cyl_scan_traits(scan_id, name, value)`); a "source"
(`cyl_trait_sources`) = one per-scan pipeline run, identified by an idempotency key.

## Important Constraints
- **Bloom DB safety:** the contract only *describes* data; write-back (sub-project #2) goes
  through sanctioned, idempotent service-role RPCs — never ad-hoc SQL. Keep this library free of
  any DB/network code.
- Keep dependencies minimal (pydantic + pyyaml are the only runtime-core deps; pandas is an
  optional `[pandas]` extra used solely by `validate_analysis_input`).

## External Dependencies
Runtime core is pydantic + pyyaml; pandas is an optional `[pandas]` extra (only
`validate_analysis_input` needs it). Downstream consumers: `sleap-roots-predict`,
`sleap-roots-traits` (import the result contract), `sleap-roots-analyze` + `bloom-mcp`
(call `validate_analysis_input`), and Bloom (consumes `schema/*.json`).
