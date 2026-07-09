# `resolve_params` in contracts — design

**Date:** 2026-07-08
**Repo:** `sleap-roots-contracts`
**Branch:** `add-param-resolution`
**Target release:** `0.1.0a4`
**Issue:** talmolab/sleap-roots-contracts#15
**Roadmap tier:** A3-params (program tracker: talmolab/sleap-roots-pipeline#14)
**Status:** design approved in brainstorming; pending OpenSpec proposal

## Context

The pure param-resolution oracle `resolve_params(metadata, overrides=None) -> ResolvedParams`
maps a single Bloom `cyl_scans_extended` scan-metadata row to the `{species, mode, age}` params
that select a `ModelCard`. It lives today only in `sleap-roots-predict`
(`sleap_roots_predict/param_resolution.py`, added in predict#18, merged).

Two consumers now need it:

- **`sleap-roots-predict`** — the origin. Migration to consume-from-contracts and delete the
  local copy is tracked in predict#28.
- **`bloomctl`** (Salk-Harnessing-Plants-Initiative/bloom#411) — the A4 "images-downloader"
  stage-in will import it to author the per-scan `{scan_key}.scan_metadata.json` sidecar's
  `params`. That work is **blocked on this release** (decision: contracts-first, then bloom
  re-pins).

Without a shared home, both would reimplement the normalization. That normalization is
**load-bearing**: the resolved `values` feed `ResolvedParams.param_hash` →
`Provenance.idempotency_key` (first-writer-wins). Any drift between producers silently breaks
idempotency — two writers computing different keys for the same logical scan both "win," and the
dedup guarantee is gone with no error anywhere.

Contracts is the right home: it already owns `ResolvedParams` (with `param_hash`/`values`) **and**
`ModelCard` (`0.1.0a3`). The oracle's inputs and its selection target both already live here.

## Goals / Non-Goals

**Goals**

- Port `resolve_params` into contracts with **behavior identical** to predict's implementation at
  HEAD — same resolved `values`, therefore the same `param_hash`.
- Expose it as `from sleap_roots_contracts import resolve_params`, drop-in parity with
  `ResolvedParams`, so predict and `bloomctl` swap the import with **no call-site changes**.
- Port predict's test suite as the acceptance oracle, and add a known-answer hash anchor.
- Cut `0.1.0a4` so bloom#411 can re-pin.

**Non-Goals**

- **No TypeScript port.** The TS resolver lives Bloom-side; the Python oracle stays the reference
  it is tested against (predict#20).
- **No `card_matches` / `choose_models`** (#13) and **no `PipelineCard`** (#14). See Decision 1.
- No scanner→mode lookup table for deferred modalities (GraviScan, multiscanner). The seam is
  documented; the table is out of scope, exactly as in predict's spec.
- No behavior changes, "improvements," or refactors while porting. See Decision 3.

## Decisions

### 1. Ship #15 alone; #13 and #14 remain siblings

`resolve_params` is self-contained — it imports only `math`, `typing`, and `ResolvedParams` — so it
can land without the selection predicate. Both siblings carry unsettled design questions of their
own (#13: ambiguous-match and zero-match semantics; #14: the `contract_version` byte format,
still open in its title). Coupling a release that **blocks bloom#411** to two undesigned changes
trades a known unblock for unknown delay.

Consequence: the two round-trip tests at the end of predict's suite call `choose_models`, which
does not exist here. Handled in Decision 4.

### 2. Module `params.py`; new `param-resolution` capability

**Module.** `src/sleap_roots_contracts/params.py`. Pydantic models live in `models.py`; pure
functions get their own module (`hashing.py`, `registry.py`, `analysis_input.py`). `params.py`
follows this repo's noun-naming rather than predict's action-naming (`param_resolution.py`); the
public import path is `from sleap_roots_contracts import resolve_params` regardless, so no consumer
observes the filename.

**Capability.** A new `openspec/specs/param-resolution/` capability, not folded into
`model-selection-contract`. That capability's requirements describe the `ModelCard` *shape*;
`resolve_params` never touches a `ModelCard` — it produces the params that later select one. A
separate capability also mirrors predict's own `param-resolution` capability 1:1, making predict#28's
eventual spec removal a clean subtraction instead of a merge.

### 3. Port behavior byte-for-byte; exactly one import line changes

The only edit to the logic is:

```python
from sleap_roots_contracts import ResolvedParams   # predict
from .models import ResolvedParams                  # contracts (self-import would be circular)
```

Module and function docstrings are re-voiced for contracts (predict's say "so predict's
`choose_models` can select…"), but every branch, message string, and coercion rule is preserved.

The full ported surface — larger than the issue summary states:

| Name | Visibility | Role |
| --- | --- | --- |
| `resolve_params` | package `__all__` | the oracle |
| `SPECIES_NAME_FIELD`, `PLANT_AGE_DAYS_FIELD` | module-public, **not** in `__all__` | Bloom column names |
| `_PARAM_KEYS` | private | `("species", "mode", "age")` |
| `_ALIASES` | private | species alias seam; ships **empty** |
| `_is_blank` | private | `None` / `NaN` / blank-string → absent |
| `_normalize_text` | private | shared strip+lower |
| `_normalize_species`, `_normalize_mode` | private | delegate to `_normalize_text` |
| `_mode_for_scan` | private | the single mode-decision point |
| `_coerce_age` | private | whole-number `int` coercion |
| `_canonicalize_text` | private | in-place normalize-or-drop |

`_normalize_text`, `_mode_for_scan`, `_PARAM_KEYS`, and the two field constants are absent from the
issue's summary but present in the live file; the constants are asserted by a ported test.

The module-public/not-in-`__all__` split for the field constants mirrors predict exactly:
`bloomctl` can reference them, but they are not part of the advertised package API.

### 4. Test port: 32 verbatim, 2 dropped, 2 added

`tests/test_params.py`. Predict's suite has **34** test functions (several parametrized); contracts
ends with 34 as well — 32 ported, 2 dropped, 2 added.

- **Ported verbatim** (32 of 34), including every normalization, coercion, override-precedence,
  blank/`NaN`, and `ValueError` case. The `_ALIASES` monkeypatch test re-points its module
  reference to `sleap_roots_contracts.params`.
- **Kept:** `test_mode_matches_seeded_card_vocabulary` — it needs only `ModelCard`, which contracts
  already has, so the mode↔card vocabulary coupling stays asserted here.
- **Dropped (2):** the `choose_models(resolve_params(row), cards)` round-trips. They stay in
  predict, where the predicate lives and where an integration test belongs. Reimplementing a stub
  predicate here would assert against a fiction and create a second untracked copy of exactly the
  logic #13 exists to de-duplicate.
- **Added (2):**
  1. `resolve_params` is importable from the package root and present in `__all__`.
  2. A **known-answer hash test** pinning the canonical row:

     ```
     {"species": "pennycress", "mode": "cylinder", "age": 14}
       → d7562d09b93a57ba6c1a128f27c6c8022c023365a3243e7508423b45756faecb
     ```

Predict's suite only ever compares hashes to *each other*. Because both repos construct
`ResolvedParams` from this same package, identical `values` already imply an identical
`param_hash` — so those relative assertions cannot detect a change to `compute_param_hash`'s
canonicalization, which would rotate every `idempotency_key` in the fleet at once. The literal is
the anchor that does. `compute_param_hash` does not ingest `__version__`, so it survives the
version bump.

### 5. The Bloom coupling is real, soft, and documented here

`openspec/project.md` calls this a "Bloom-agnostic leaf library," and this oracle reads Bloom
column names. The coupling is **soft** — dict keys only; no Bloom import, no DB, no network, no
filesystem I/O — but it is a genuine narrowing of "Bloom-agnostic" and is recorded rather than
glossed.

Mitigations: the two column names are hoisted into module constants (greppable across repos, as in
predict), and `project.md` gains a sentence stating that contracts knowingly owns this documented
coupling, because both the oracle's input vocabulary and its selection target (`ModelCard`) already
live here. The alternative — a Bloom-side resolver — is precisely the drift this change exists to
prevent.

### 6. `mode` growth seam

`_mode_for_scan(metadata)` returns the constant `"cylinder"` (the cylinder pipeline yields cylinder
scans only). It is the one place `mode` is decided, so GraviScan/multiscanner modalities slot in
here without changing `resolve_params`'s body, its callers, or its output shape. Any string it
returns **MUST** equal the exact seeded `ModelCard` mode vocabulary.

### 7. Release: a `$id`-only structural no-op

This is **not** "schema unchanged." `schema.py` stamps each artifact's `$id` from `__version__`:

```
https://github.com/talmolab/sleap-roots-contracts/schema/v{__version__}/{name}.schema.json
```

Bumping to `0.1.0a4` therefore restamps both `schema/analysis_input.schema.json` and
`schema/result_envelope.schema.json` — **bytes change, structure does not** (one `$id` line each).
`resolve_params` is a function, and `ModelCard` was never emitted, so this change adds no schema
surface at all.

Release steps: bump `pyproject.toml` to `0.1.0a4`; **re-lock `uv.lock` in the same commit** (a
version bump without it hard-fails the release build, and PR CI does not catch it); regenerate
`schema/*.json` and confirm the drift guard is green; add the CHANGELOG entry; `/prepare-release` →
tag → PyPI trusted publishing.

Downstream consumers do the **standard full re-pin** — `pin.json`, vendored schema (accept the
`$id`-only diff), regenerated TS — **not** merely a pip-floor bump.

## Error Handling

Unchanged from predict, and asserted by the ported tests:

- Unknown override key → `ValueError` naming the offending key.
- Present-but-non-whole or non-coercible `age` (incl. `bool`) → `ValueError` naming `age`.
- Any of `species` / `mode` / `age` still absent after the override merge → `ValueError` naming
  every missing param.
- Blank (`""`, whitespace, `None`, `NaN`) load-bearing fields are treated as **not provided**, so
  they defer to overrides and then to the missing-param error — never to a blank param and never to
  a "not a whole number" error.

No half-resolved `ResolvedParams` is ever returned.

## Testing

`uv run pytest -v` (full suite), `uv run black --check src tests`, `uv run ruff check src tests`,
coverage, and the schema drift guard — via `/pre-merge-check`.

## Follow-ups (not this change)

- **bloom#411** — re-pin `sleap-roots-contracts>=0.1.0a4` (full re-pin: `pin.json` + vendored
  schema `$id`-only diff + regenerated TS); import `resolve_params` for
  `bloomctl cyl download-for-predict`.
- **predict#28** — re-pin, import from contracts, delete local `param_resolution.py` (and its
  `param-resolution` capability spec); re-point TS-parity predict#20 at the contracts oracle.
- **talmolab/sleap-roots-pipeline** — `docs/bloom-integration/roadmap.md`: the "param oracle"
  reference now points at a shared contracts home (#14, A3-params umbrella).
- **#13 / #14** — shared `card_matches` predicate and `PipelineCard` selection type remain open
  siblings; when #13 lands, predict's two round-trip tests could migrate here.
