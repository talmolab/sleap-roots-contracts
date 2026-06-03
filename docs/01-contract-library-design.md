# Design — Sub-project #1: `sleap-roots-contracts`

**Date:** 2026-06-03
**Status:** Draft for review
**Program:** [README.md](./README.md) — sleap-roots ↔ Bloom pipeline integration
**Sub-project:** #1 of the decomposition (the result & provenance contract — the spine)

---

## 1. Purpose

A small, dependency-light, **Bloom-agnostic** Python library that defines the *shape*
of a per-scan pipeline result and its provenance, emits a language-neutral JSON Schema
artifact, and is imported by the Python producers (`predict`, `traits`) while Bloom (TS/
Postgres) consumes the emitted schema. It is the single source of truth that makes every
result traceable and prevents producer/consumer drift.

### In scope
- Pydantic models for results + provenance + blob refs + resolved params.
- A pure, deterministic param-hash function.
- Validation rules (numeric values, trait-name registry, deterministic idempotency key).
- CI that emits `schema/*.json` and a snapshot/drift guard.

### Explicitly NOT in scope (belongs to later sub-projects)
- No DB writes, no Bloom client, no SQL/migrations → **#2**.
- No Bloom-metadata → params *resolution* logic → **#3** (producer / Bloom client).
- No model/inference code, no Argo, no orchestration → **#3 / #4**.
- No Bloom `models` table → **fast-follow after #3** (see §7).

## 2. Why a standalone repo

The contract is a **leaf** dependency: everything imports it, it imports nothing.
- `sleap-roots-pipeline` is the **root** (orchestrator, depends on predict + traits) and is
  **YAML/shell only** — hosting a Python lib there inverts the dependency graph and changes
  the repo's character.
- Hosting in `predict` would force `traits` (and Bloom codegen) to depend on `predict`.

So: new standalone repo **`sleap-roots-contracts`**, independently semver'd. `predict`/`traits`
depend on `sleap-roots-contracts==X.Y`; Bloom pins `schema/*.json @ vX.Y`.
(Revisit only if predict+traits+pipeline are ever collapsed into one monorepo.)

## 3. Data model background (Bloom reality, verified 2026-06-03)

Bloom already stores cyl traits **relationally, long-format** (since 2023):
- `cyl_scan_traits (id, scan_id→cyl_scans, name TEXT, value REAL)` — per-scan
- `cyl_image_traits (id, image_id→cyl_images, name TEXT, value REAL)` — per-image
- `cyl_trait_sources (id, name TEXT)` — thin provenance dimension
- RPC `get_scan_traits`, view `cyl_scan_trait_names`

Variable trait sets are absorbed by long format — a new trait is a new `name` row, **no
migration, no jsonb for values**. Therefore the contract models **trait values as rows**,
and reserves jsonb (#2) for **provenance metadata on the source row**.

Gaps #2 will fill (informed by this design): jsonb `metadata` on `cyl_trait_sources`;
`source_id` FK on the trait tables (values are currently untraceable); a dedicated
intermediates/blob table; CLI + backfill. DB-safety: cyl trait tables ship **SELECT-only
RLS** → write-back must go through a sanctioned, idempotent **service-role RPC**, never
direct table writes.

## 4. Models (Pydantic, canonical)

> A **source = one per-scan pipeline run**. `idempotency_key` is its unique identity
> (unique constraint in #2). Reprocessing the same scan with a new model/params/inputs/code
> mints a **new** source row; the old one is retained = full history. **1 `ResultEnvelope`
> : 1 source row : 1 scan.**

### `Provenance` → serializes to `cyl_trait_sources.metadata` (jsonb, #2)
- `contract_version: str`
- `scan_key: str` — the scan this run processed (#2 resolves to `cyl_scans.id`)
- `idempotency_key: str` (deterministic — see §5)
- `inputs: InputRef` — pins what went in
- `pipeline_run_id: str | None`
- **predict stage**: `models: list[ModelRef]` (multiple: primary/lateral/crown),
  `container_digest: str`, `code_sha: str`, `worker_request_id: str | None` (warm-worker path)
- **traits stage**: `sleap_roots_version: str`, `container_digest: str`, `code_sha: str`
- **orchestration** (optional, execution-model dependent):
  `argo_workflow_uid: str | None`, `argo_node_id: str | None`
- `params: ResolvedParams`
- `produced_at: datetime`

### `InputRef` — input-data identity (reproducibility)
- `image_ids: list[str]` — the Bloom image ids consumed
- `images_checksum: str` — content checksum over the input image set (detects re-uploads/swaps)

### `ModelRef` (structured so it is FK-able to a future Bloom `models` table)
- `registry_id: str`, `version: str`, `sleap_nn_version: str`
- `root_type: str | None` (which model this is — primary/lateral/crown)
- `weights_checksum: str | None` (pins weights even if registry id/version mutate)

### `TraitValue` → long-format rows
- `name: str` (validated against the trait **definitions** registry)
- `value: float | None` (NaN/inf → `None` → SQL `NULL`; explicit-null = "tried, was missing"
  vs. omitted = "never ran")
- `grain: Literal["scan", "image"] = "scan"` (image allowed; when enabled needs an image key,
  not `scan_key`)
- `scan_key: str` (producer-side scan identity; #2's write path resolves to `cyl_scans.id`)

### `BlobRef` → intermediates/blob table rows (#2)
- `kind: Literal["predictions_slp", "labels", "h5", "qc_image", ...]` (controlled vocabulary)
- `scan_key: str`
- `s3_location: str | None`, `box_link: str | None` — **validator: at least one required**
- `checksum: str | None`, `file_size: int | None` (mirrors Bloom audit-field pattern)

### `ResolvedParams`
- `values: dict[str, Any]` (fully-resolved run params)
- `param_hash: str` (canonical-JSON hash — rules in §5)

### Trait definitions registry (shared artifact, shipped in this repo)
- `TraitDefinition(name, unit, dtype, description)` + a `trait_definitions.{yaml,json}` seeded
  from sleap-roots' known trait set; emitted alongside `schema/*.json`. Enables name + dtype +
  range validation and self-documenting outputs. Bloom can consume the same artifact.

### `ResultEnvelope` (the unit a write-back consumes) — 1 envelope : 1 source : 1 scan
- `provenance: Provenance`
- `traits: list[TraitValue]`
- `blobs: list[BlobRef]`

## 5. Param resolution, hashing, identity

- **Contract owns only**: `ResolvedParams` + `compute_param_hash(values) -> str`. The
  *resolution* of Bloom dataset metadata → defaults → user overrides → `ResolvedParams` lives
  in the **producer / Bloom client (#3)**, keeping the contract Bloom-agnostic and light.
- **Canonical-JSON hashing (pinned to avoid silent reproducibility breaks)**: recursively
  sorted keys; UTF-8; compact separators (no whitespace); a **fixed float repr**; **reject
  `NaN`/`inf`** in params; then `sha256` → hex. `compute_param_hash` and the idempotency key
  both use this canonicalization.
- **Idempotency key** is deterministic from
  `(scan_key, inputs.images_checksum, sorted models[(registry_id, version, weights_checksum)],
  param_hash, predict.code_sha, traits.code_sha)`. A re-delivered ingestion event → same key →
  no double-write; any change to inputs/model/params/code → new key → reprocess (new source
  row). Required by the warm-worker model.
- **Validation**: trait `value` is numeric or `None`; `name` checked against the trait
  **definitions** registry (unknown → configurable warn/error); dtype/range checks from the
  definition; `BlobRef` requires ≥1 location.
- **Hash scope**: hashes are computed **producer-side only**; Bloom stores + compares them as
  **opaque strings** and never recomputes. So canonicalization only needs to be deterministic
  within Python — no byte-identical Python↔TS spec required. `values` must be JSON-serializable
  scalars/containers (reject non-serializable types).

## 6. Cross-language flow & drift guard

**Repo boundary:** #1 *produces, versions, and publishes* the artifact + owns the internal
drift guard. #2 (Bloom) *consumes* it (codegen + migration-match check). Schema version =
package semver, carried in each schema's `$id`.

```
sleap-roots-contracts (Pydantic, canonical)        [owned by #1]
   | CI: pydantic -> schema/*.json  (committed interchange artifact, $id carries vX.Y)
   |                                  ^ snapshot test FAILS CI if models change
   |                                    without regenerating schema (the drift guard)
   | publish: PyPI (lib) + schema/*.json on the GitHub release
   +--> predict, traits   import sleap-roots-contracts==X.Y
   +--> bloom (#2)        pin schema/*.json @ vX.Y -> codegen TS,
                          match supabase migration against schema in CI   [owned by #2]
```

## 7. Models table — deferred seam

`ModelRef` is a **structured sub-object** (not a flat string) so a future Bloom `models` table
can be introduced **after #3** decides the canonical registry home (W&B + Bloom + sleap-nn).
Because a run uses **multiple** models, that future table is reached via a **join**
(`cyl_trait_source_models(source_id, model_id, root_type)`), not a single FK on
`cyl_trait_sources`. Building it earlier risks two sources of truth with W&B; until then model
identity lives structured-in-provenance and is join-ready.

## 8. Testing (TDD — tests written first)

- Round-trip: Pydantic ↔ JSON ↔ JSON-Schema-valid.
- `compute_param_hash`: determinism + key-order independence + value-change sensitivity +
  fixed float repr + `NaN`/`inf` rejection.
- Idempotency-key determinism + sensitivity to each component (scan_key, images_checksum,
  each model tuple, param_hash, both code_shas); model-list order-independence.
- `TraitValue.value`: NaN/inf → `None` mapping; `None` serializes to JSON null / SQL NULL.
- Trait **definitions** registry: known name passes; unknown warns or errors per config;
  dtype/range validation (e.g. count ≥ 0, angle 0–360).
- `BlobRef`: at-least-one-location validator (s3 or box); `kind` rejects out-of-vocab values.
- Golden JSON-Schema snapshot (the drift guard).
- Example fixtures (`ResultEnvelope` samples) validate against the emitted schema.

## 9. Repo bootstrap (tooling baseline, from `analyze` standard)

`uv` project; `pytest`; OpenSpec scaffold (`openspec/`); `CLAUDE.md`; `.claude/commands`
(incl. `tdd`, `review-openspec`); **PyPI publish workflow**.

**No Dockerfile / GHCR for this repo.** The blanket "each repo gets a Dockerfile + GHCR CI"
rule targets the **services** (predict/traits/pipeline); `sleap-roots-contracts` is a pure
library — producers `pip install sleap-roots-contracts==X.Y`, and GHCR is a container registry
(libs go to PyPI). Distributing a container here would be maintenance with no consumer.

## 10. Downstream implications (recorded, not built here)

- **#2 (Bloom):** add jsonb `metadata` to `cyl_trait_sources`; add `source_id` FK to
  `cyl_scan_traits`/`cyl_image_traits`; create intermediates/blob table; service-role
  idempotent write-back RPC; CLI update; backfill Box traits.
- **#3 (predict/traits):** params resolution from Bloom metadata; produce `ResultEnvelope`;
  warm predict worker carrying `worker_request_id`.
- **#4 (orchestration):** Argo Events ingest→per-scan trigger; populate `argo_*` ids;
  notifications; experiment-level `analyze` trigger.
