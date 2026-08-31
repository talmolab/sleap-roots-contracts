# Design: root-type alias table

## Context

Issue #34 asks whether this library should own a nickname mapping. It was filed as a low-priority
question and contains one chronological slip worth correcting: it states that
`sleap-roots-training#49`'s resolution is "to store it as `crown` per team decision." That is the
right outcome, but it was not #49's decision at the time — #49's `D3` proposes adding a
`LabelRootType` superset carrying `seminal` to this contract, which was a reasonable reading of the
evidence then available. Elizabeth's 2026-08-27 decision settles it afterwards. `tasks.md` §1 posts
that correction to both places, with the chronology stated so #49 is not made to look careless.

## Decisions

- **D1. `RootType` is untouched, and no parallel `LabelRootType` is added.** The harm from a
  distinct seminal root type is not that selection stops working — `LabelCard` is not a selection
  input, so a seminal LabelCard never reaches `choose_models` — it is that the **label-to-model
  lineage join breaks**, which is #49's entire stated purpose. A wheat collection stamped `seminal`
  cannot be joined to the crown model trained on it. Verified: `RootType` at HEAD (`0.1.0a8`) is
  `Literal["primary", "lateral", "crown"]` and `seminal` appears nowhere in `src/`.
- **D2. The table lives here.** This is the one dependency training, predict and (in spirit) analyze
  share, and the equivalence has been reinvented three times. A frozen mapping and one pure function
  add no dependency and no I/O — the same argument that put `resolve_params` here.
- **D3. It is a routing record, not a similarity claim.** The pooled model establishes detector
  transferability under a shared appearance regime: the classes are not separable enough, at those
  ages, in that modality, to be worth separating. It does **not** establish that the structures are
  the same (embryonic vs post-embryonic nodal), nor that traits computed on them are comparable.
  Deriving an ontological equivalence from a training-set merge inverts the evidence. The table
  therefore states routing, which is exactly what is supported, and which is also what makes the
  record defensible to someone who knows plants — a similarity claim would be one they should
  correct.
- **D4. Entries carry an age window as structured data, in DAG.** The governing decision is age-scoped, and
  the evidence filename carries a *different* window per species (`wheat_5-14DAG`, `rice_3-10DAG`),
  which is itself evidence that the scope is per-species *and* per-window. Wheat seminal roots are
  embryonic; wheat crown roots emerge from basal shoot nodes around tillering, at or past the top
  of that window. Outside it the terms name two co-present populations, and pooling them would
  silently merge distinct root systems. Age is available at the ingestion boundary — `LabelCard`
  already carries `age_min`/`age_max` — so omitting it would be a choice, not a limitation. The
  **epoch** is stated normatively because it is recorded nowhere else in this library and the two
  sides disagree by default: the seeded window is read off a `DAG`-labelled dataset while the
  consumer takes its age from Bloom's `plant_age_days`, whose epoch neither repo asserts. The
  window's two bounds also guard different things — above `age_max` the terms name co-present
  populations, while below `age_min` a wheat plant has only its embryonic system, whose radicle the
  `primary` bucket also claims.
- **D5. The display direction is dropped from this change.** Not merely for want of a consumer, but
  for want of a safe signature. Its `species` argument comes from an analysis config, not from the
  data, so a pooled wheat+rice result rendered under a wheat config labels rice-derived rows
  "seminal". That failure reaches publications and is invisible to the reader — it looks correct.
  The per-config `custom_replacements` mechanism it would replace is scoped to one analysis whose
  species and age the author knows; hoisting it into a contract strips that binding and adds library
  authority to it. If it returns it must take age, must be named for reporting rather than botany,
  and must document that the caller is asserting scope rather than querying a fact.
- **D6. Unknowns raise, and that is what makes sparsity safe.** The nearest precedent in this library
  is `params._ALIASES` — a spec'd alias table that chose *passthrough* and is deliberately shipped
  empty. This table chooses the opposite, and the reason is the coupling: a sparse table plus
  raise-on-unknown means the first collection using an unrecorded term hard-fails ingestion, forcing
  a human judgment rather than letting a default swallow it. Sparsity and strictness are one
  decision, not two.
- **D7. The prohibition goes in `model-selection-contract`, as ADDED.** The earlier draft filed it in
  the new capability and justified that by the stale-base problem. The stale-base fact is true and is
  a real argument against a **MODIFIED** block — but ADDED requires no re-paste, and this repo's own
  `No Tolerant Read Of The Legacy Flat Card` did exactly this for exactly this kind of prohibition.
  Filing it away from the matching rule would put it where a predict developer never looks.

## The central asymmetry

Ingestion is many-to-one and keyed on (term, species, age). Display is one-to-one only *given a
species*, and undefined without one — `crown` displays as "seminal" in wheat and as "crown" in rice.
They are not inverses. D5 removes the display half; this section stays because the asymmetry is why
a future display change must be designed separately rather than bolted on as a reverse lookup.

## Follow-ups, deliberately not bundled

- **`LabelCard.source_root_type`.** Normalization is lossy and nothing retains the arriving term, so
  after backfill a wheat collection is indistinguishable from a genuine crown collection and the
  methods sentence "wheat roots were labeled as seminal roots" can no longer be produced from the
  contract. The fix is an optional field on `LabelCard`, which means MODIFYING
  `label-selection-contract` — a different shape of change from this one, and one that should not be
  smuggled in behind an alias table. The loss is stated normatively here in the meantime.
- **A species-scoped reporting label**, per D5.

## Risks

- **Thin consumer story, stated honestly.** #49's backfill mapping is a hand-written static table, so
  calling the function there replaces a literal — real but marginal. The genuine ingestion consumers
  are the `publish-labels` path for *new* packages (#10/#26), which is explicitly out of #49's scope.
  This change is worth making because it records a decision, not because it removes much code.
- **The two species normalizers can drift.** `params._normalize_species` applies a species alias map
  after strip+lower. If that map is ever populated, a Latin binomial would resolve there and miss
  here. Mitigated by sharing the helper rather than reimplementing it, and by a test that pins them
  together.
- **Import direction.** `params.py` imports `models.py`, so a helper shared by both cannot live in
  `models.py`. The table gets its own module.
