# Design — `add-param-resolution`

Full brainstormed design: `docs/superpowers/specs/2026-07-08-param-resolution-in-contracts-design.md`.
This file records the decisions a reviewer needs while reading the spec deltas and tasks.

## Why this is a port, not a rewrite

The resolved `values` feed `ResolvedParams.param_hash` → `Provenance.idempotency_key`
(first-writer-wins). Any behavioral difference between this implementation and predict's — a
different strip order, a tolerated bool, a `NaN` treated as a value rather than as absent — silently
changes the hash for some inputs. Two producers would then compute different keys for the same
logical scan, both "win" the first-writer race, and dedup would be lost **with no error raised
anywhere**. The failure is invisible at the call site and only shows up as duplicate rows in Bloom.

Therefore: no cleanups, no "while I'm here" improvements, no signature changes during the port. The
one required edit is the import (below). Refactors, if any, come in a later change with the tests
already in place.

## Decisions

### 1. Ship #15 alone

#13 (shared `card_matches`) and #14 (`PipelineCard`) stay open siblings. `resolve_params` is
self-contained (imports only `math`, `typing`, `ResolvedParams`), while both siblings carry unsettled
design questions of their own. bloom#411 is **blocked on this release**; coupling it to two
undesigned changes trades a known unblock for unknown delay.

### 2. The one required code edit

```python
from sleap_roots_contracts import ResolvedParams   # predict
from .models import ResolvedParams                 # contracts — a self-import would be circular
```

`params.py` is imported by `__init__.py` **after** `models.py`, so the relative import resolves
cleanly. Docstrings are re-voiced (predict's reference "predict's `choose_models`"), but every
branch, message string, and coercion rule is preserved verbatim.

### 3. Module `params.py`, capability `param-resolution`

Pydantic models live in `models.py`; pure functions get their own module (`hashing.py`,
`registry.py`, `analysis_input.py`). `params.py` follows this repo's noun-naming rather than
predict's action-naming; the public import path is `from sleap_roots_contracts import resolve_params`
either way, so no consumer observes the filename.

The capability is **new**, not folded into `model-selection-contract`: that capability's requirements
describe the `ModelCard` *shape*, and `resolve_params` never touches a `ModelCard` — it produces the
params that later select one. A separate capability also mirrors predict's own `param-resolution`
capability 1:1, making predict#28's eventual spec removal a clean subtraction instead of a merge.

### 4. Exported surface

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

`_normalize_text`, `_mode_for_scan`, `_PARAM_KEYS`, and the two field constants are **absent from
issue #15's summary** but present in the live file; the constants are asserted by a ported test. The
module-public/not-in-`__all__` split mirrors predict exactly.

### 5. Test port: 32 verbatim, 2 dropped, 2 added

Predict's suite has **34** test functions (several parametrized). Contracts ends with 34 as well.

- **Dropped (2):** the `choose_models(resolve_params(row), cards)` round-trips. `choose_models` does
  not exist here (it is #13). They stay in predict, where the predicate lives and where an
  integration test belongs. A stub predicate here would assert against a fiction and create a second
  untracked copy of exactly the logic #13 exists to de-duplicate. When #13 lands, they can migrate.
- **Kept:** `test_mode_matches_seeded_card_vocabulary` — needs only `ModelCard`, which contracts has,
  so the mode↔card vocabulary coupling stays asserted here.
- **Added (2):** `resolve_params` in `__all__`; and a **known-answer `param_hash` anchor**.

On the anchor: predict's suite only ever compares hashes to *each other*. Because both repos
construct `ResolvedParams` from this same package, identical `values` already imply an identical
`param_hash` — so those relative assertions **cannot detect** a change to `compute_param_hash`'s
canonicalization, which would rotate every `idempotency_key` in the fleet at once. The literal
`d7562d09b93a57ba6c1a128f27c6c8022c023365a3243e7508423b45756faecb` (for
`{"species": "pennycress", "mode": "cylinder", "age": 14}`) is the anchor that does.

> **GOLDEN DIGEST — captured from the PRE-CHANGE installed package (`0.1.0a3`)**, so it proves
> cross-release stability, not post-change self-consistency. `compute_param_hash` does not ingest
> `__version__`, so the bump cannot move it. If a green run disagrees, a canonicalization bug has
> been introduced — investigate, do **not** re-baseline.

### 6. The Bloom coupling is real, soft, and documented

`openspec/project.md` calls this a "Bloom-agnostic leaf library," and this oracle reads Bloom column
names. The coupling is **soft** — dict keys only; no Bloom import, no DB, no network, no filesystem
I/O — but it is a genuine narrowing of "Bloom-agnostic" and is recorded rather than glossed. The two
column names are hoisted into module constants (greppable across repos, as in predict), and
`project.md` gains a sentence stating that contracts knowingly owns this documented coupling, because
both the oracle's input vocabulary and its selection target (`ModelCard`) already live here. The
alternative — a Bloom-side resolver — is precisely the drift this change exists to prevent.

### 7. Release is a `$id`-only structural no-op — not "schema unchanged"

`schema.py` stamps each artifact's `$id` from `__version__`:

```
https://github.com/talmolab/sleap-roots-contracts/schema/v{__version__}/{name}.schema.json
```

Bumping to `0.1.0a4` restamps **both** `schema/analysis_input.schema.json` and
`schema/result_envelope.schema.json` — bytes change, structure does not (one `$id` line each).
`resolve_params` is a function and `ModelCard` was never emitted, so this change adds no schema
surface at all. Downstream consumers do the **standard full re-pin** (`pin.json` + vendored schema +
regenerated TS), accepting the `$id`-only diff — not merely a pip-floor bump.

`uv.lock` pins this project's own version, so the bump stales it. PR `ci.yml` runs plain `uv sync`
(non-frozen) and stays **green with a stale lock**, but the release `build.yml` runs `uv lock --check`
+ `uv sync --frozen` and **hard-fails**. The lock bump is therefore mandatory, and `uv lock --check`
must be run locally.

## Commit grouping

Each commit is green on its own. Never commit a bare RED step.

- **Commit 1 (`feat:`)** — `params.py` + export + `tests/test_params.py`. Pure Python; touches **no
  schema**, so the drift guard is untouched.
- **Commit 2 (`chore(release):`)** — `pyproject.toml` → `0.1.0a4`, `uv sync`, the re-locked
  `uv.lock`, **both** regenerated schemas (`$id` → `v0.1.0a4`), CHANGELOG. Green only if both schemas
  move together and `uv.lock` is bumped.
- **Commit 3 (`docs:`)** — `openspec/project.md`, `README.md`. Docs-only; may fold into Commit 2.

## Risks

| Risk | Mitigation |
| --- | --- |
| Silent behavioral drift from predict breaks `idempotency_key` | Port verbatim; 32 ported tests + a golden `param_hash` anchor captured pre-change |
| Forgotten `uv.lock` bump passes PR CI, fails the release build | Task 4.1 runs `uv lock --check` locally, mirroring `build.yml` |
| Reviewer reads "no schema change" and skips regeneration | Spec, proposal, and design all state the `$id`-only restamp explicitly; drift guard enforces it |
| Two copies of the oracle coexist during the predict#28 window | Expected and bounded; contracts is declared the source of truth, predict deletes its copy on re-pin |
