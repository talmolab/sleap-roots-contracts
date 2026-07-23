## Why

The `sleap-roots-labels` registry cannot answer "where did these labels come from?". Its eight
collections store provenance as **boolean-key soup** (`{"soybean": true, "4nodes": true, "lateral":
true}` — keys with the value `true`, not key→value pairs), so nothing is queryable unless you already
know a key's name. The one field that nominally records origin, `data_path`, is unusable in **all
eight** cases: six point at a Windows temp directory from a one-off re-embed run
(`C:/Users/ELIZAB~1/AppData/Local/Temp/reembed_<random>/...`), the other two at a `Z:` drive letter
that resolves from neither a Linux training node nor CI. Frame count and source experiment survive
only as prose in the free-text `description`.

Meanwhile the `/build-labeling-package` workflow that *produces* the labels already computes exactly
the missing metadata — a per-frame sample manifest, the Bloom `experiment_id`, accession names, and
the canonical skeleton — and discards all of it at publish time.

`ModelCard` (`model-selection-contract`) already proves the shape this should take: real typed
fields, validated at construction. Labels need the mirror. Without it, Tier 2's `run→artifact`
lineage oracle cannot close (a model cannot be joined to the labels it trained on) and Tier 2.7's
skeleton unification cannot even *enumerate* node counts without parsing free text.

## What Changes

- Add a **`label-selection-contract`** capability defining `LabelCard` — an immutable (`frozen`)
  Pydantic model carrying a label set's selection, skeleton, content, provenance, and registry
  identity fields, importable from the package root and mirroring `ModelCard`'s conventions.
- Promote the **mode vocabulary** into the contract as `Mode = Literal["cylinder", "multiplant
  cylinder", "plate"]`, mirroring the existing `RootType` Literal (`models.py:149`). `LabelCard.mode`
  is typed `Mode`, so the `cyl` shorthand the current label collections use is rejected at
  construction.
- `LabelCard` enforces two structural invariants at construction: `age_min <= age_max` (mirroring
  `ModelCard`) and `node_count == len(node_names)`.
- `LabelCard` is **producer↔producer** — like `ModelCard`, it never crosses the Bloom boundary and is
  **not** emitted to JSON Schema.
- **No `data_path` field.** The broken locator is deliberately not carried forward; row-level origin
  travels in the sample manifest attached to the artifact (training's `label-registry`), and content
  identity is carried by `source_sha256`.

Not in scope: retyping `ModelCard.mode` from `str` to `Mode` (tracked separately — see Design);
renaming or backfilling the existing eight collections (#11).

## Impact

- Affected specs: `label-selection-contract` (new capability). **No** change to
  `model-selection-contract` — `ModelCard` is untouched.
- Affected code: `src/sleap_roots_contracts/models.py` (add `Mode`, `LabelCard`),
  `src/sleap_roots_contracts/__init__.py` (export both), `tests/`, `docs/`.
- Release: cuts the next contracts alpha (**`0.1.0a5`** — `0.1.0a4` is already taken by
  `resolve_params`; issue #10's "0.1.0a4" is stale). Consumed by `sleap-roots-training`'s
  `add-label-registry` change, which **must sequence after** this ships.
- Runtime deps unchanged (pydantic only; no filesystem/network — see Design on validator placement).
