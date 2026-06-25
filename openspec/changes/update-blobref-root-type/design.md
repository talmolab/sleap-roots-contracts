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
prediction blobs; `labels`/`h5`/`qc_image` were speculative and never produced. `viewer_html` is
deferred (add later if/when the pipeline produces it); `traits_csv` is rejected permanently — trait
numbers are `TraitValue` rows, not blobs.

**`const` → `enum` normalization (emitter decision).** Pydantic renders a single-value `Literal`
as JSON Schema `const`, but a multi-value `Literal` renders as `enum`. The previous 4-value `kind`
was an `enum`, and Bloom keys on `BlobRef.kind`'s **enum** (issue #5) for its `kind IN
('predictions_slp')` CHECK and byte-identity migration-match test. Emitting `const` would make
`kind` the sole exception to the "controlled vocabulary = enum" shape and risk breaking Bloom's
extraction. So `schema.py` normalizes any single-value `const` to a one-element `enum`
(`_normalize_single_value_enums`), keeping a uniform "allowed set" shape regardless of cardinality.
This is applied to all `MODELS`; today only `BlobRef.kind` is affected (no other single-value
`Literal` exists). Recorded here because the obvious assumption — "a single Literal just renders as
a one-element enum" — is false without this step.

## Schema regeneration

`schema/result_envelope.schema.json` is generated from the Pydantic models and CI drift-guards it
(regenerate must equal committed). It is **never hand-edited**. After the model change, regenerate
via `python -m sleap_roots_contracts.schema`. Expected diffs: `BlobRef.kind.enum` collapses to
`["predictions_slp"]`; a new required `root_type` property appears with
`enum: ["primary","lateral","crown"]`; `BlobRef.required` gains `root_type`.

## The version / `$id` coupling (the version bump restales BOTH schemas)

`schema.py` builds every schema's `$id` from `__version__` (`.../schema/v{__version__}/...`), and
the drift guard compares committed bytes against a fresh `render()` over **all** `MODELS`
(`result_envelope` *and* `analysis_input`). So advancing the version to `0.1.0a2` changes the `$id`
line of **both** committed schemas, even though only `BlobRef` changes shape. `python -m
sleap_roots_contracts.schema` regenerates both at once; a partial regen (only `result_envelope`)
passes locally on the model change but turns the drift guard RED on `analysis_input` after the bump.

**Versioning is now single-source (as of #6, merged).** `__version__` resolves from installed
package metadata, so `pyproject.toml:version` is the only place to bump; `__init__.py` needs no edit
and the schema `$id` tracks the bump after a reinstall (`uv sync`). `render()` also now refuses to
emit when the version is unresolved (`"unknown"`), and `test_schema_id_carries_package_version`
already asserts each `$id` carries `__version__` — so this change does **not** need to add a
`$id`/version test (it exists on main).

## Commit grouping (tasks.md is an implementation sequence, not a commit sequence)

The RED-first sub-steps in `tasks.md` are the TDD *working-tree* order; they must NOT each be a
commit (a committed RED step is red CI). The drift guard forces two atomic commit units, each
green on its own:

- **Unit A — the contract change, still at `v0.1.0a1`:** `models.py` (narrow `BlobKind`, add
  `RootType` + required `BlobRef.root_type`), `__init__.py` (export `RootType`/`BlobKind`),
  `tests/*` (new assertions + fixture/test updates), and the regenerated
  `result_envelope.schema.json` (`$id` still `v0.1.0a1`). `analysis_input.schema.json` is untouched
  and still matches. Green.
- **Unit B — the release bump:** `pyproject.toml:version` → `0.1.0a2` (single source; `__init__`
  needs no edit), `uv sync` to reinstall, **both** regenerated schemas (`$id` → `v0.1.0a2`), and the
  `docs/CHANGELOG.md` entry. Green only if both schemas are regenerated together.

Single PR, proposal/spec committed separately first; archive only after merge.
