# Design — tighten-model-card-validation

## Context

- **Goal:** close the two loose field types `ModelCard` shipped with in `0.1.0a3`, using guards this
  library already owns (`Mode`, `NonBoolInt`) and already applies to `LabelCard`.
- **Constraints:** `ModelCard` is a *released* contract with two live consumers
  (`sleap-roots-training` writes cards, `sleap-roots-predict` reads them). This library takes no
  filesystem, network, or DB I/O, so every guard here is a pure field-level validator.
- **Non-Goals:** validating the scan-parameter side (`resolve_params`); exporting `NonBoolInt`;
  renaming or backfilling registry collections; touching `LabelCard`.

## Decisions

**Decision: both tightenings ship as one change.**
`ModelCard.mode` → `Mode` (#21) and `NonBoolInt` on the age bounds (#25) were deferred from
`add-label-selection-contract` in the same breath, for the same reason, and land in the same field
block of the same model. They produce one `MODIFIED` requirement between them, and — because
`0.1.0a6` is merged but unreleased — one release and one downstream pin bump. Splitting them would
mean two changes racing for the same unreleased version, or a second validation-tightening release
for consumers to absorb weeks later.
*Alternative considered:* ship #21 alone as scoped by its issue and leave #25 for later — rejected
because "later" means `0.1.0a7` and a second round of predict/training pin bumps for a one-annotation
change, and because a proposal that tightens one half of the same field block invites the reviewer to
ask why the other half was left.

**Decision: the card is strict; the scan-parameter side stays tolerant.**
`resolve_params` normalizes a mode with strip+lower (`params.py:131`, whose docstring already calls
the `ModelCard` mode vocabulary authoritative) but does **not** check membership, and
`ResolvedParams.values` is a `dict[str, Any]`. That tolerance is deliberate and load-bearing: an
unmodelled species or mode is specified to degrade to a **selection zero-match, not an error**
(`params.py:121`), so a scan the program has no model for is skipped rather than crashing the run.
This change does not touch it. The resulting asymmetry is the correct one — the *registry card* is a
curated artifact written once at promotion and must be exactly right; the *scan parameters* are read
from live Bloom metadata the pipeline does not control.
*Alternative considered:* type the `mode` entry of `ResolvedParams.values` too — rejected: it would
convert a designed zero-match into a hard failure on the ingest path, and `values` is an open dict by
contract (it feeds `param_hash`).

**Decision: no normalization on the card side — exact-match `Literal`, mirroring `RootType`.**
`Mode` rejects `Cylinder` and `cylinder ` as surely as it rejects `cyl`. Adding a normalizing
`BeforeValidator` to `ModelCard.mode` would make the card quietly repair a producer's typo and
diverge from `RootType`'s five-year-old plain-`Literal` precedent on the same model. A card is
written once, by a script, at promotion; a loud failure there is cheap and a silent repair is not.

**Decision: `NonBoolInt` stays module-internal.**
It is not in `__init__.py`'s `__all__` today and this change does not add it. It is an implementation
detail of how these contracts defend against boolean-key metadata soup, not a shape consumers
construct. Consumers that need the behavior get it by validating a card.

**Decision: ride `0.1.0a6` rather than cut `0.1.0a7`.**
`pyproject.toml` already reads `0.1.0a6`; PyPI's newest is `0.1.0a5`; `add-label-selection-contract`
task 6.5 (cut the release) is still open. Folding in here means `sleap-roots-training` bumps its pin
`a3 → a6` exactly once and gets `LabelCard`, `Mode`, and a strict `ModelCard` together. **This makes
merge order load-bearing:** this change must merge before that release is cut. If it slips, the
correct response is to renumber to `0.1.0a7` — not to hold the release, because training #10 is
blocked on a6 shipping.

## Risks / Trade-offs

- **Predict's registry lister now raises where it used to shrug.** `WandbRegistrySource.list_cards()`
  does `ModelCard.model_validate(meta)` per artifact (`model_registry.py`), so one off-vocabulary
  `mode` in the live `wandb-registry-sleap-roots-models` metadata would fail the whole *listing*,
  not just that card's match. Training's seeded matrix is clean (`cylinder`, `multiplant cylinder`),
  but the seeded matrix is the source *snapshot*, not proof of what the live registry holds —
  nothing here can query wandb. → **Mitigated by Task 4.1:** the live registry's `mode` values must be
  enumerated against `get_args(Mode)` before predict bumps its pin. This is a verification obligation
  on the consumer's bump, not a blocker for this change. Whether `list_cards()` should degrade to
  skip-with-warning instead of raising is a real question, but it belongs to predict's spec, not this
  contract's — flagged for that repo, not resolved here.
- **`plate` is in the vocabulary but has no seeded models yet** (training #3 defers them). So the
  vocabulary is currently wider than the registry — the safe direction. The reverse (a live mode the
  vocabulary lacks, e.g. an unanticipated GraviScan/multiscanner mode, which `params.py:148` notes is
  a future slot-in) would be a hard failure, and would need a contract release to admit the new
  spelling. That is the intended cost of a controlled vocabulary and matches how `RootType` already
  behaves.
- **The bool guard is a `BeforeValidator`, so it changes the error type, not just the outcome.** A
  producer passing `age_min=True` previously got a valid card; it now gets a `ValidationError` whose
  message names the bool explicitly. No producer is known to do this — the guard is prophylactic
  against #11's backfill and any future card built from legacy metadata.
- **Test-fixture churn is a signal, not just chores.** `tests/test_model_card.py`'s shared fixture
  uses `mode="proximal"` — a value that was never in any vocabulary and that no producer writes.
  That it survived in the test suite for three releases is a small demonstration of what an untyped
  `mode` permits.
