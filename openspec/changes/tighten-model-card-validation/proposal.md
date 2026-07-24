## Why

`ModelCard` shipped in `0.1.0a3` with two loose field types that `LabelCard` deliberately did not
copy when it landed in `0.1.0a6`:

**1. `mode` is an untyped `str`.** The same three capture-mode strings existed in three places —
`ModelCard.mode: str` here (validating nothing), training's `chooser.py:23` `MODE_VOCAB` frozenset,
and the `cyl` shorthand baked into the label collection names. `add-label-selection-contract` fixed
two of the three: it promoted the vocabulary into this library as `Mode = Literal["cylinder",
"multiplant cylinder", "plate"]` and typed `LabelCard.mode` with it. `ModelCard.mode` was left
behind, so the *model* registry — the older and more load-bearing of the two — is now the only
selection surface in the program that will accept `cyl`, `Cylinder`, or `banana` without complaint.
That is backwards: `root_type: RootType` on the very same model has been a controlled vocabulary
since `0.1.0a3` (issue #21).

**2. `age_min`/`age_max` silently swallow a `bool`.** Python's `bool` subclasses `int`, so pydantic's
lax mode reads `True`/`False` as `1`/`0`. `ModelCard` sets `extra="ignore"` specifically so a card can
be built from a raw wandb metadata blob, and in this registry that blob is boolean-key soup
(`{"v007": true, "4nodes": true}`) — field validation is the only defense left. `age_min=True` yields
a card claiming an approved selection window that starts at day 1. `add-label-selection-contract`
built the reusable `NonBoolInt` guard for exactly this and applied it to all seven of `LabelCard`'s
integer fields, but deliberately left `ModelCard` alone (issue #25).

Both were deferred for the same stated reason — tightening a *released* contract is a behavior change
that deserves its own change and its own changelog line, rather than being smuggled into an otherwise
purely additive one (`add-label-selection-contract/design.md`, "Decision: `ModelCard.mode` stays plain
`str`" and the `NonBoolInt` asymmetry note). This is that change, and it is the last window to make it
cheaply: `0.1.0a6` is merged to `main` but **not yet released to PyPI**, so both tightenings can ride
one release and one downstream pin bump instead of two.

## What Changes

- **Retype `ModelCard.mode` from `str` to `Mode`** (#21), the vocabulary this library already owns.
  A card carrying `cyl` — or any other off-vocabulary spelling — now fails at construction instead of
  silently never matching a scan.
- **Adopt `NonBoolInt` on `ModelCard.age_min` and `ModelCard.age_max`** (#25). A `bool` bound is
  rejected rather than coerced; ordinary lax parsing (`"7"`, `7.0`) is unaffected.
- **Fix `NonBoolInt` to catch `numpy.bool_` as well as the builtin.** Added during pre-PR review:
  `numpy.bool_` is not a `bool` subclass, so `isinstance(v, bool)` let it through and pydantic read
  it as `1`/`0` — the exact trap `params._coerce_age` already documents and defends against for scan
  ages with an allowlist. The card side was therefore *looser* than the tolerant scan-param side for
  the same quantity, inverting the asymmetry this change argues for. Because `NonBoolInt` is shared,
  this also closes the hole on all seven of `LabelCard`'s integer fields — including `node_count`,
  where a coerced `1` satisfies the skeleton-coherence check against a single node name.
- Update `model-selection-contract`'s "Model Selection Card" requirement to state both, with
  scenarios covering vocabulary rejection, full-vocabulary acceptance, bool rejection, and the
  preserved lax-parsing behavior.

**This is a breaking change for a card producer that was writing an off-vocabulary `mode` or a bool
age bound.** No known producer does — training's seeded matrix carries only `cylinder` and
`multiplant cylinder` (`registry/data/model_selection.yaml`), both in the vocabulary, and the `plate`
models remain deferred (training #3). See Design for the verification task this obligates.

Not in scope: the tolerant scan-parameter side. `resolve_params` keeps accepting any normalized mode
string and degrading an unmodelled one to a selection zero-match rather than an error — see Design.

## Impact

- **Affected specs:** `model-selection-contract` (MODIFIED — one requirement). No new capability.
  Note `LabelCard`'s bool rejection turns out to have **no spec requirement at all** —
  `add-label-selection-contract` implemented `NonBoolInt` and discussed it in design.md, but never
  wrote a SHALL or a scenario for it. So the shared guard's strengthening has no
  `label-selection-contract` surface to modify. That gap belongs to that change, which is still open
  (2 tasks); flagged there rather than patched from here.
- **Affected code:** `src/sleap_roots_contracts/models.py` (two field annotations plus the `NonBoolInt` and
  `Mode` comment blocks that name this deferral),
  `tests/test_model_card.py` (the shared fixture uses `mode="proximal"`, an off-vocabulary value that
  the retype invalidates), `docs/`.
- **Release:** rides the **unreleased `0.1.0a6`**, alongside `add-label-selection-contract`. Must
  merge *before* that change's task 6.5 cuts the release; if a6 ships first, this becomes `0.1.0a7`
  and costs a second pin bump in every consumer.
- **Consumers:** `sleap-roots-predict` pins `==0.1.0a5` and validates raw wandb metadata straight into
  `ModelCard` (`model_registry.py`), so it is unaffected until it bumps — but its bump now carries a
  read-path behavior change. `sleap-roots-training` pins `==0.1.0a3` and is the card *writer*; its
  `chooser.py` `MODE_VOCAB` frozenset becomes redundant and should be replaced with
  `get_args(Mode)` when it bumps (training #10).
- Runtime deps unchanged; no JSON Schema impact (`ModelCard` is producer↔producer and is not emitted).
