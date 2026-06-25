# Design Notes

## Decision: do NOT tighten `ModelRef.root_type` to `RootType`

`root_type` appears on two models, labelling two different things:

- **`BlobRef.root_type`** labels *an artifact*: "this `.slp` file contains **primary** root
  predictions." Every predictions blob comes from one root-type-specific SLEAP model, so it is
  always exactly one of `{primary, lateral, crown}`, and Bloom enforces it `NOT NULL`. This field
  is **required** and **constrained to `RootType`** — the core of change C.

- **`ModelRef.root_type`** labels *a model*: "this SLEAP model detects **primary** roots." It is
  `str | None` today: **optional** (a model need not be root-type-specific) and a **free string**
  because `ModelRef` is documented as "FK-able to a future Bloom models table" — a pointer into a
  model registry that does not yet exist.

**Considered:** tighten `ModelRef.root_type` to `RootType | None` for one-vocabulary consistency.
The existing fixtures/tests use `root_type="primary"`, so nothing in-repo would break.

**Chosen:** leave `ModelRef.root_type` as `str | None`. Reasons:

1. **Scope.** Change C is the *artifact* contract (`BlobRef`). Tightening `ModelRef` is extra
   surface beyond what the change requires.
2. **No downstream pull.** The Bloom #357 parity gate asserts only on `BlobRef.kind`. Neither the
   gate nor the `root_type` column on Bloom's intermediates table reads `ModelRef.root_type`, so
   tightening it unblocks nothing.
3. **Forward flexibility.** `ModelRef` is a registry pointer. If the model registry ever needs a
   root-type label outside the three (e.g. a whole-plant or multi-class model), a free string
   absorbs it without another contract bump.

The `RootType` type is still **defined once and exported**, so the vocabulary has a single source of
truth — we simply do not *apply* it to the optional model field. The inconsistency (one `root_type`
enum-constrained, the other a free string) is accepted and documented here as the recorded decision
for `talmolab/sleap-roots-contracts#5`.

## Why narrow `BlobKind` to a single-value `Literal`

`Literal["predictions_slp"]` is intentional, not a placeholder. The pipeline emits only `.slp`
prediction blobs; `labels`/`h5`/`qc_image` were speculative and never produced. A single-value
`Literal` still renders as a one-element `enum` in the JSON Schema, which is exactly what Bloom's
`kind IN ('predictions_slp')` CHECK and its byte-identity migration-match test compare against.
`viewer_html` is deferred (add later if/when the pipeline produces it); `traits_csv` is rejected
permanently — trait numbers are `TraitValue` rows, not blobs.

## Schema regeneration

`schema/result_envelope.schema.json` is generated from the Pydantic models and CI drift-guards it
(regenerate must equal committed). It is **never hand-edited**. After the model change, regenerate
via `python -m sleap_roots_contracts.schema`. Expected diffs: `BlobRef.kind.enum` collapses to
`["predictions_slp"]`; a new required `root_type` property appears with
`enum: ["primary","lateral","crown"]`; `BlobRef.required` gains `root_type`.

## The version / `$id` coupling (two traps, both load-bearing here)

`schema.py` builds every schema's `$id` from `__version__` (`.../schema/v{__version__}/...`), and
the drift guard compares committed bytes against a fresh `render()` over **all** `MODELS`
(`result_envelope` *and* `analysis_input`). Two consequences this change must respect:

1. **The version bump restales BOTH schemas, not just `result_envelope`.** Even though only
   `BlobRef` changes shape, advancing `__version__` to `0.1.0a2` changes the `$id` line of
   `analysis_input.schema.json` too. `python -m sleap_roots_contracts.schema` regenerates both at
   once; a partial regen (only `result_envelope`) passes locally on the model change but turns the
   drift guard RED on `analysis_input` after the bump.

2. **The version lives in two independent static strings.** `pyproject.toml:version` (drives the
   built/published wheel) and `src/sleap_roots_contracts/__init__.py:__version__` (drives the schema
   `$id`) are **not** linked — `__init__` is a hardcoded literal, not `importlib.metadata`. For this
   release they must be bumped **in lockstep**. Nothing in CI cross-checks them, and
   `prepare-release.md` currently (wrongly) claims `__init__` is dynamically versioned and instructs
   bumping only `pyproject.toml`; following it verbatim would publish a `0.1.0a2` wheel whose schema
   `$id` still reads `v0.1.0a1`. **This is a release-infrastructure defect, tracked in #6 (align the
   release setup with `sleap-roots-analyze`: dynamic versioning + release validation), and is out of
   scope for this change.** Here we simply bump both strings by hand. Once #6 lands, `__init__`
   derives from package metadata and the lockstep disappears.

## Commit grouping (tasks.md is an implementation sequence, not a commit sequence)

The RED-first sub-steps in `tasks.md` are the TDD *working-tree* order; they must NOT each be a
commit (a committed RED step is red CI). The drift guard forces two atomic commit units, each
green on its own:

- **Unit A — the contract change, still at `v0.1.0a1`:** `models.py` (narrow `BlobKind`, add
  `RootType` + required `BlobRef.root_type`), `__init__.py` (export-only, no version bump),
  `tests/*` (new assertions + fixture/test updates), and the regenerated
  `result_envelope.schema.json` (`$id` still `v0.1.0a1`). `analysis_input.schema.json` is untouched
  and still matches. Green.
- **Unit B — the release bump:** `__init__.__version__` → `0.1.0a2`, `pyproject.toml:version` →
  `0.1.0a2`, **both** regenerated schemas (`$id` → `v0.1.0a2`), and the `docs/CHANGELOG.md` entry.
  Green only if both schemas are regenerated together.

Single PR, proposal/spec committed separately first; archive only after merge.
