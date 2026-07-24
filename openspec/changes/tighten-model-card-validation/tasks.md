## 1. Retype `ModelCard.mode` to the `Mode` vocabulary (#21)

- [ ] 1.1 (RED) Test that a `ModelCard` built with `mode="cyl"` raises, and that the error names the
      `mode` field — the label registry's shorthand is the concrete value this guard exists to stop
- [ ] 1.2 (RED) Test that a differently-cased `mode="Cylinder"` and a whitespace-padded
      `mode="cylinder "` both raise, pinning the "no normalization on the card side" decision so a
      future `BeforeValidator` cannot be added without failing a test
- [ ] 1.3 (RED) Parametrized test that every member of `get_args(Mode)` constructs and is retained
      unchanged, mirroring the existing `test_model_card_accepts_all_root_types`. Guards the
      inverse of 1.1 — a typo'd vocabulary that rejects a legitimate seeded mode
- [ ] 1.4 (GREEN) Change `ModelCard.mode` from `str` to `Mode` in `models.py`. `Mode` is defined
      above `ModelCard` already, so the definition-order constraint documented at `models.py:194`
      (no `from __future__ import annotations` in this module) is satisfied without moving anything
- [ ] 1.5 Update the shared fixture in `tests/test_model_card.py`, which uses the off-vocabulary
      `mode="proximal"`, to a real vocabulary member — and confirm the fixture change alone does not
      turn 1.1–1.3 green (they must fail for the annotation, not the fixture)

## 2. Adopt `NonBoolInt` on the age bounds (#25)

- [ ] 2.1 (RED) Parametrized test that `age_min=True` and `age_max=True` (and `False`) each raise
      rather than coercing to `1`/`0`
- [ ] 2.2 (RED) Test that lax integer parsing still works — `age_min="7"` and `age_max=7.0` both
      construct and read as the integer `7`. This is the regression guard that keeps the fix narrow:
      `NonBoolInt` must reject only `bool`
- [ ] 2.3 (GREEN) Annotate `ModelCard.age_min` and `ModelCard.age_max` as `NonBoolInt`, keeping the
      existing `Field(ge=0)` bounds
- [ ] 2.4 Confirm `age_min <= age_max`, negative-bound, and equal-bound behavior is unchanged (the
      existing tests must stay green — the `mode="after"` validator runs only once field validation
      passes, so a bool bound now fails *before* the range check)

## 3. Comments, exports, and docs

- [ ] 3.1 Update the `NonBoolInt` comment block (`models.py:46-48`) — it currently states "Applied to
      LabelCard only. ModelCard has the same exposure but shipped in 0.1.0a3; retyping its fields is
      a behavior change ... tracked as a follow-up". That deferral is now resolved
- [ ] 3.2 Update the `Mode` comment block (`models.py:188-190`) — "Required on LabelCard;
      `ModelCard.mode` stays a loose `str` in this change (retyping it is a tracked follow-up)" is
      now stale
- [ ] 3.3 Update `ModelCard`'s class docstring, which describes `mode` as a plain selection field, to
      name the vocabulary and the bool guard
- [ ] 3.4 Confirm `__init__.py` needs no change: `Mode` is already exported (`__init__.py:51`) and
      `NonBoolInt` stays module-internal per the design decision
- [ ] 3.5 Update `openspec/project.md`'s contract-library summary if it describes `ModelCard`'s field
      types, and check `docs/` for the same

## 4. Cross-repo verification and sequencing

- [ ] 4.1 Enumerate the live `wandb-registry-sleap-roots-models` collections' `mode` metadata values
      against `get_args(Mode)` and record the result. **Blocking for `sleap-roots-predict`'s pin
      bump, not for this merge** — predict's `WandbRegistrySource.list_cards()` validates every
      artifact, so one off-vocabulary value there fails the whole listing (see design.md, Risks).
      Cannot be done from this repo: it needs wandb credentials
- [ ] 4.2 File the follow-up on `sleap-roots-predict` for the `list_cards()` question surfaced by
      4.1 — should an unparseable card be skipped with a warning instead of failing the listing? —
      referencing this change. That is predict's spec decision, not this contract's
- [ ] 4.3 Note in `sleap-roots-training` #10 that `chooser.py`'s `MODE_VOCAB` frozenset is now fully
      redundant for both cards and should become `get_args(Mode)` when training bumps its pin

## 5. Validation and release

- [ ] 5.1 Run `openspec validate tighten-model-card-validation --strict`
- [ ] 5.2 Run `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`
- [ ] 5.3 Regenerate `schema/*.json` and confirm the drift guard is green — expected to be a no-op,
      since `ModelCard` is producer↔producer and not emitted; a diff here means something is wrong
- [ ] 5.4 Confirm `pyproject.toml` still reads `0.1.0a6` and that this change merges **before**
      `add-label-selection-contract`'s task 6.5 cuts that release. If a6 ships first, renumber to
      `0.1.0a7` rather than holding the release — training #10 is blocked on a6 (see design.md)
- [ ] 5.5 Run `/pre-merge-check`, then `/pr-description`, referencing both #21 and #25
