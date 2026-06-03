# sleap-roots-contracts

Shared **result + provenance contract** for the sleap-roots ↔ Bloom pipeline.

This is a small, dependency-light, Bloom-agnostic library that defines the shape of a
per-scan pipeline result and its provenance (Pydantic v2 models), emits a versioned JSON
Schema artifact, and ships a trait-definitions registry. The Python producers
(`sleap-roots-predict`, `sleap-roots-traits`) import it; Bloom consumes the emitted schema.

It is sub-project #1 of the sleap-roots ↔ Bloom integration program. Design and plan:
`docs/01-contract-library-design.md` and `docs/02-contract-library-plan.md`.

## Develop

```bash
uv sync
uv run pytest -v
uv run black --check src tests && uv run ruff check src tests
```

## Key ideas

- **Pydantic is canonical**; `schema/*.json` is generated and drift-guarded in CI.
- Trait **values** are long-format rows (no jsonb); provenance is a jsonb blob on the source.
- Hashes (`param_hash`, `idempotency_key`) are **producer-side only**; Bloom treats them as
  opaque strings.
- Distributed via **PyPI** (no Docker image — this is a library).
