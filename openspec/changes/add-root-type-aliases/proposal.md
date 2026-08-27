# Proposal: A contract-owned root-type alias table

## Why

`RootType` is deliberately three buckets, but field terminology is not — wheat's "seminal" roots are
the crown bucket at the ages this pipeline studies. That routing equivalence is real, decided, and
written down nowhere, so it has now been independently reinvented three times, most recently as a
proposed contract fork in `sleap-roots-training#49`. Tracking issue:
talmolab/sleap-roots-contracts#34.

## Background

`RootType` (`primary` / `lateral` / `crown`) is small and strict because pipeline correctness depends
on it: `sleap-roots-predict`'s `choose_models` matches on exact `RootType` equality, and `ModelCard`,
`LabelCard`, `BlobRef` and `PredictionArtifact` all validate against it. Real terminology is richer —
seminal, adventitious, nodal, brace and tertiary roots are structurally and developmentally distinct.

Where the equivalence has already been reinvented:

1. **A trained model pools the two.** The "Crown/Seminal Roots" model
   (`250328_095645.multi_instance.n=1658`) was trained on a combined wheat + rice dataset
   (`labels_seminal_wheat_5-14DAG_rice_3-10DAG.v005.slp`). **Unverified from either local checkout** —
   this string appears in no repo on this machine, and it is the change's primary evidence, so
   `tasks.md` §1.4 pins it to a wandb artifact before implementation.
2. **`sleap-roots-analyze` hand-rolls the reverse direction per config**, as `custom_replacements`
   `{"crown": "seminal"}` in a wheat cylinder QC pipeline. **Also unverified here** — that repo is not
   checked out on this machine; §1.4 pins it to a commit SHA.
3. **It was rediscovered a third time.** `sleap-roots-training#49` hit the wheat collection
   `wheat_5-14DAG_seminal_6nodes_labels`, correctly found that `LabelCard(root_type="seminal", ...)`
   raises today, and proposed adding a `LabelRootType` superset to *this* contract. That was a
   reasonable reading of the evidence available when it was written; Elizabeth's decision came after.

**The governing decision (Elizabeth, 2026-08-27): use `crown`, not `seminal`, throughout.** "In wheat
at the age we study the roots are seminal but they look the same as crown roots." **The age clause is
load-bearing** and is treated as such below.

## What Changes

**Non-breaking and additive.** `RootType` membership is **unchanged**.

Add a **root-type-aliases** capability: a contract-owned, evidence-gated table recording which
botanical terms route to which canonical bucket, **for which species and over which developmental
window**, plus one accessor.

```python
canonical_root_type("seminal", species="wheat", age_days=9)  -> "crown"
canonical_root_type("seminal", species="wheat", age_days=30) -> ValueError  # outside the window
```

The table is a **routing** record: it asserts that these terms resolve to the same model weights. It
asserts nothing about developmental identity or trait comparability, and the spec says so normatively
— wheat seminal roots are embryonic while crown roots are post-embryonic nodal roots, and outside the
recorded window they are two co-present populations rather than one.

**The display direction is deliberately not in this change.** `root_type_display_name` was scoped
here and removed: it lacks a consumer (`sleap-roots-analyze` is not in this program's dependency
graph), and more importantly it lacks a safe signature — its `species` argument comes from an
analysis config rather than from the data, so a pooled wheat+rice result rendered under a wheat
config would label rice-derived rows "seminal", invisibly and in print. It is tracked as a follow-up
in `design.md`, gated on a real request and an age-aware signature.

## Non-goals

- **Widening `RootType`,** or adding a parallel `LabelRootType`. See `design.md` D1.
- **Applying aliases at the selection seam.** Prohibited normatively — see the
  `Alias Normalization Is An Ingestion Boundary Only` requirement, which this change adds to
  `model-selection-contract`, where the matching rule lives and where a predict developer will
  actually encounter it.
- **Being a botanical authority.** The table records routing, not synonymy.
- **Owning trait-name sanitization.** `sleap-roots-analyze` keeps `custom_replacements`.

## Impact

- **Affected specs:** new `root-type-aliases` capability (ADDED). Plus **one ADDED requirement** on
  `model-selection-contract` carrying the match-seam prohibition. ADDED rather than MODIFIED
  deliberately: `main`'s copy of that spec still describes the **pre-selectors** flat card because the
  `update-model-card-selectors` archive (contracts#33) has not merged, so a MODIFIED block would
  re-paste and permanently bake a stale requirement. An ADDED requirement re-pastes nothing and trips
  no scenario-preservation check. Precedent: `update-model-card-selectors` added
  `No Tolerant Read Of The Legacy Flat Card` to this same spec the same way.
- **Affected code:** a new `src/sleap_roots_contracts/root_type_aliases.py` (**not** `models.py` —
  `params.py` already imports `models`, so a species-normalization helper shared between them cannot
  live in `models.py` without a cycle), and `__init__.py` exports.
- **Affected tests:** a new `tests/test_root_type_aliases.py`, plus card-rejection guards in
  `tests/test_model_card.py` and `tests/test_label_card.py`.
- **Affected docs:** `docs/CHANGELOG.md` (entry **and** footer compare links), `README.md`,
  `openspec/project.md` (the vocabularies paragraph, **not** the six-contracts list — an alias table
  is not a data contract), and `docs/01-contract-library-design.md`'s staleness banner, which
  enumerates capability names verbatim.
- **Affected release artifacts:** `pyproject.toml`, `uv.lock`, and both `schema/*.json` — every
  schema `$id` embeds `__version__`, so the version bump restamps them even though no emitted
  contract changes shape. The changelog SHALL record that the schema delta is `$id`-only, since Bloom
  consumes those artifacts for codegen and migration-match.
- **Release: `0.1.0a9`.** `0.1.0a8` is already published, so this cannot ride an unreleased version.
- **Priority: low.** Issue #34 says so explicitly.
