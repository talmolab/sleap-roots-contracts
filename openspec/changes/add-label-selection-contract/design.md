## Context

`ModelCard` is the template. It lives in `models.py:158`, is `frozen=True, extra="ignore"`, carries
selection fields (`species`, `mode`, `age_min`, `age_max`, `root_type`) plus artifact identity
(`registry_id`, `version`, `weights_checksum`), and validates `age_min <= age_max` in a model
validator. `RootType = Literal["primary", "lateral", "crown"]` (`models.py:149`) is consumed directly
as a field type by `ModelRef`, `ModelCard`, and `BlobRef`; there is no exported frozenset beside it —
callers needing the value set use `typing.get_args(RootType)`.

`LabelCard` mirrors that shape for label artifacts. The evidence for each field is issue #10's audit
of all eight `wandb-registry-sleap-roots-labels` collections and the `/build-labeling-package`
scripts that already compute this metadata.

## Goals / Non-Goals

- **Goals:** a queryable, typed label provenance card symmetric with `ModelCard`; one owner for the
  mode vocabulary; structural invariants enforced at construction, before any network call.
- **Non-Goals:** retyping `ModelCard.mode`; backfilling/renaming the eight existing collections
  (#11); changing `embed=False` in `build_slp_project.py`; any filesystem or wandb I/O in this
  library.

## Decisions

**Decision: contracts owns the mode vocabulary; training imports it.**
Today the same three strings exist twice — `ModelCard.mode` is untyped `str` in the contract, while
training's `chooser.py:23` keeps an independent `MODE_VOCAB` frozenset. That duplication is precisely
the split issue #10 is about (`cylinder` vs `cyl`, the two registries cannot be joined). Contracts is
already the selection target and already owns `RootType`, so it takes `Mode` too, expressed the same
way — a `Literal`, not a frozenset, for consistency with `RootType`.
*Alternative considered:* leave the vocab in training and have contracts stay vocabulary-agnostic —
rejected, because the card that must reject `cyl` lives here, and a per-consumer copy is what broke
joinability in the first place. (Note `project.md` already records that this library is deliberately
no longer vocabulary-agnostic as of `0.1.0a4`.)

**Decision: `label-selection-contract` as a new sibling capability, not an extension of
`model-selection-contract`.**
The repo's convention is one capability per card family — `model-selection-contract` is scoped
entirely to `ModelCard`/`ModelRef`, and `analysis-input-contract` sits beside it. Folding `LabelCard`
into `model-selection-contract` would mix two unrelated card types under a name that doesn't mention
labels. *(Signed off by Elizabeth on #10.)*

**Decision: `ModelCard.mode` stays plain `str` in this change.**
Retyping it to `Mode` is a strict tightening of an existing shipped requirement and would drag
`model-selection-contract` deltas plus a predict-side compatibility question into a change that is
otherwise purely additive. Tracked as a follow-up. *(Signed off by Elizabeth on #10.)*

**Decision: `node_names` is a `tuple[str, ...]`, not a `list`.**
The model is `frozen`; a tuple keeps the field immutable in substance rather than only by assignment
guard. Same reasoning for `accessions`.

**Decision: the `n_frames == manifest rows` check lives in training's publish path, not here.**
This is the one validator of the three that cannot be a `LabelCard` model validator: it compares a
card field against the row count of `sample_manifest.csv`, and this library takes **no filesystem
I/O** (`project.md`, "Important Constraints"). The card cannot see the manifest. Placing it at the
publish boundary — which already holds the labeling-package directory — keeps contracts I/O-free and
still fails before any upload. The two invariants that *are* intrinsic to the card
(`age_min <= age_max`, `node_count == len(node_names)`) are enforced here.
*Alternative considered:* a pure `validate_label_package(card, manifest_df)` here under the optional
`[pandas]` extra, mirroring `validate_analysis_input` — viable and consistent with precedent; deferred
because the publish path is the only caller and pandas is not otherwise needed. **Flagged for review.**

**Decision: `source_sha256` is Optional on the contract but always computed in the publish path.**
It's computed over the `.slp` file bytes and passed at publish time. The contract can't read
files, so the hash is computed where the file is — same reason the manifest row-count validator
lives here.

**Decision: `extra="ignore"`, set explicitly.**
Mirrors `ModelCard` (`models.py:188`) so a card can be built from a raw wandb metadata blob — the
existing boolean tag flags (`{"v007": true, "4nodes": true}`) merged with artifact identity — without
the legacy extras causing failure. This is what makes #11's backfill tractable.

## Field table

Grouping is issue #10's; types and optionality are proposed here and are the primary reviewable
surface.

| group | field | type | req? | notes |
|---|---|---|---|---|
| selection | `species` | `str` | yes | `str`, not a Literal — `SPECIES_VOCAB` lives in training's chooser and is out of scope |
| selection | `mode` | `Mode` | yes | rejects `cyl` |
| selection | `root_type` | `RootType` | yes | existing vocabulary |
| selection | `age_min` | `int` (`ge=0`) | yes | inclusive |
| selection | `age_max` | `int` (`ge=0`) | yes | inclusive; `>= age_min` |
| skeleton | `skeleton_name` | `str` | yes | |
| skeleton | `node_count` | `int` (`ge=1`) | yes | `== len(node_names)` |
| skeleton | `node_names` | `tuple[str, ...]` | yes | `r1`…`rN` |
| content | `n_frames` | `int` (`ge=0`) | yes | cross-checked against manifest rows at publish |
| content | `n_instances` | `int` (`ge=0`) | yes | |
| content | `n_plants` | `int` (`ge=0`) | yes | |
| content | `n_scans` | `int` (`ge=0`) | yes | |
| content | `images_embedded` | `bool` | yes | records the ~10x storage state, does not change it |
| provenance | `source_experiment` | `str` | no | Optional — may not exist for legacy collections; new labels should populate it, but it can't block #11's backfill |
| provenance | `bloom_experiment_id` | `str` | no | Optional — trace-to-Bloom is best-effort, not a publish gate (Elizabeth, Slack 2026-07-21) |
| provenance | `accessions` | `tuple[str, ...]` | no | names, not ids; Optional — same recoverability risk as the other Bloom-trace fields, best-effort populate |
| provenance | `labeler` | `str` | no | Optional — not computed by `build_slp_project.py`; lives in human/Notion memory. Difficult-to-impossible to recover for previous collections (Elizabeth) |
| provenance | `box_link` | `str \| None` | no | may not exist for a given package |
| provenance | `source_sha256` | `str` | no (contract) / always (publish) | Computed from file bytes, so never actually missing — #11 has the files it republishes. Optional in the model so nothing blocks backfill; publish path always computes and passes it. Replaces the broken `data_path` |
| provenance | `sleap_io_version` | `str \| None` | yes if captured, else no | Required if the build script captures `sleap_io.__version__`, else Optional. No legacy LabelCards exist to tolerate, so `ModelCard`'s back-compat optionality doesn't transfer — require it once the build script is confirmed to grab it. Mirrors `ModelCard.sleap_nn_version` |
| registry | `registry_id` | `str` | yes | artifact identity |
| registry | `version` | `str` | yes | artifact identity |

## Risks / Trade-offs

- **Required-vs-optional is a one-way door for #11.** Every field marked required above is a field
  the backfill must produce for all eight legacy collections — and several (`labeler`,
  `bloom_experiment_id`, `n_instances`) are not recoverable from the current metadata without
  re-deriving from source. → If #11 is expected to reconstruct cards for legacy artifacts rather than
  republish them, `bloom_experiment_id`, `labeler`, and `source_sha256` should relax to optional.
  → **Resolved 2026-07-21 (Elizabeth, Slack):** backfill republishes as-is, does not re-derive.
  `bloom_experiment_id` / `source_experiment` / `accessions` / `labeler` → optional, best-effort
  populate. `source_sha256` stays computed in the publish path. One-way-door risk closed.
- **`Mode` as a `Literal` is a closed set**; a new capture mode requires a contracts release. Accepted
  — same trade-off `RootType` already makes, and the closedness is the point.
- Cross-repo sequencing: training cannot pin `0.1.0a5` until this ships. → Release contracts first;
  the training change declares the dependency.

## Open Questions

- ~~Optionality of `bloom_experiment_id` / `labeler` / `source_sha256` (see Risks) — depends on #11's
  intended shape.~~ **Resolved 2026-07-21 (Elizabeth, Slack):** #11 republishes as-is; these relax to
  optional, `source_sha256` stays computed in the publish path (see Risks).
- Should `species` become a contract-owned `Literal` too, for symmetry with `Mode`? Out of scope
  here; would move `SPECIES_VOCAB` out of training's chooser.
