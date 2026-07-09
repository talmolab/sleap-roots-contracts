## Why

The pure param-resolution oracle `resolve_params(metadata, overrides=None) -> ResolvedParams` maps a
single Bloom `cyl_scans_extended` scan-metadata row to the `{species, mode, age}` params that select
a `ModelCard`. It lives today **only** in `sleap-roots-predict`
(`sleap_roots_predict/param_resolution.py`, predict#18, merged). Two consumers now need it:

- **`sleap-roots-predict`** — the origin; migration to consume-from-contracts and delete the local
  copy is tracked in predict#28.
- **`bloomctl`** (Salk-Harnessing-Plants-Initiative/bloom#411) — the A4 "images-downloader" stage-in
  will import it to author the per-scan `{scan_key}.scan_metadata.json` sidecar's `params`. That work
  is **blocked on this release** (decision: contracts-first, then bloom re-pins).

Without a shared home each would reimplement the normalization, and that normalization is
**load-bearing**: the resolved `values` feed `ResolvedParams.param_hash` →
`Provenance.idempotency_key` (first-writer-wins). Drift between producers silently breaks
idempotency — two writers compute different keys for the same logical scan, both "win," and dedup is
lost with no error raised anywhere.

Contracts is the right home: it already owns `ResolvedParams` (with `param_hash`/`values`) **and**
`ModelCard` (`0.1.0a3`), so the oracle's inputs and its selection target both already live here.
Full rationale and decisions: `docs/superpowers/specs/2026-07-08-param-resolution-in-contracts-design.md`
and this change's `design.md`. Tracked as sleap-roots-contracts#15 (roadmap tier A3-params;
program tracker talmolab/sleap-roots-pipeline#14).

## What Changes

- Add a new **`param-resolution` capability** implemented in a new pure module
  `src/sleap_roots_contracts/params.py`, ported from predict's implementation at HEAD with
  **behavior identical byte-for-byte**:
  - `resolve_params(metadata, overrides=None) -> ResolvedParams` — exported from the package root
    (`__all__`), giving drop-in parity with `ResolvedParams` so predict and `bloomctl` swap the
    import with **no call-site changes**.
  - Module-public Bloom column-name constants `SPECIES_NAME_FIELD` (`"species_name"`) and
    `PLANT_AGE_DAYS_FIELD` (`"plant_age_days"`) — **not** added to `__all__` (mirrors predict).
  - Private helpers `_PARAM_KEYS`, `_ALIASES` (ships **empty**), `_is_blank`, `_normalize_text`,
    `_normalize_species`, `_normalize_mode`, `_mode_for_scan`, `_coerce_age`, `_canonicalize_text`.
  - The **only** logic edit vs. predict: `from sleap_roots_contracts import ResolvedParams` becomes
    `from .models import ResolvedParams` (a self-import would be circular). Docstrings are re-voiced
    for contracts; every branch, message string, and coercion rule is preserved.
- Port predict's `tests/test_param_resolution.py` as the acceptance oracle into
  `tests/test_params.py` — **32 of its 34** tests verbatim (the `_ALIASES` monkeypatch test
  re-points to `sleap_roots_contracts.params`).
- Add two tests predict's suite lacks: `resolve_params` is importable from the package root and in
  `__all__` (while the two column-name constants are **not**); and a **known-answer `param_hash`
  anchor** over the canonical resolved row. The digest literal lives in one normative place — the
  spec's *Resolved Params Known-Answer Anchor* requirement — and is copied from there into the test.
- Release **`v0.1.0a4`**: bump `pyproject.toml` (single source of truth), re-lock `uv.lock`,
  regenerate **both** schemas (each `$id` embeds the version), update `docs/CHANGELOG.md`.
- Record in `openspec/project.md` (and, identically, `README.md`) that contracts knowingly owns a
  **soft, documented** coupling to Bloom's column names: dict keys only — no Bloom import, no
  DB/network/filesystem I/O. The library stays **code-agnostic** toward Bloom but is no longer
  **vocabulary**-agnostic, so the bare adjective "Bloom-agnostic" is corrected **in place** in both
  files rather than merely qualified further down.
- Add a `uv lock --check` step to PR `ci.yml` (approved scope addition). Today a stale `uv.lock`
  passes PR CI (non-frozen `uv sync`) and only hard-fails at release in `build.yml` — after merge,
  while bloom#411 waits. This change bumps the version, so it is precisely the change that trips that
  trap; the guard lands with it.

## Impact

- **Affected specs:**
  - `param-resolution` (NEW capability) — ADDED: scan-metadata → params resolution; species
    normalization; the imaging-mode seam; age resolution in days; override merge semantics; strict
    post-override validation; public API export; resolved-params known-answer anchor.
  - No other capability is touched. The hashing algorithm and its version-independence stay owned by
    `result-contract`'s producer-side hashing requirement; this capability pins only the composition
    of `resolve_params` with that hash.
- **Affected code:**
  - `src/sleap_roots_contracts/params.py` — **NEW**; the ported oracle. Imports only `math`,
    `typing`, and `.models.ResolvedParams`.
  - `src/sleap_roots_contracts/__init__.py` — export `resolve_params` (import + `__all__`).
  - `tests/test_params.py` — **NEW**; the ported acceptance oracle + 2 added tests.
  - `pyproject.toml` — `version` → `0.1.0a4` (single source; `__version__` resolves from metadata).
  - `uv.lock` — re-locked (it pins this project's own version).
  - `schema/result_envelope.schema.json` **and** `schema/analysis_input.schema.json` — both
    regenerated. **`$id`-only diff**: `schema.py` stamps `$id` from `__version__`, so the bytes change
    while the structure does not — the version string occurs exactly once per file, so exactly one
    line per file moves. `resolve_params` is a function and `ModelCard` was never emitted, so this
    change adds **no schema surface at all**. This is *not* "schema unchanged."
  - `.github/workflows/ci.yml` — add `uv lock --check` after `uv sync`.
  - `docs/CHANGELOG.md` — `0.1.0a4` entry + footer compare-link refresh.
  - `openspec/project.md` — correct "Bloom-agnostic" in place; name the param-resolution oracle;
    record the documented soft coupling to Bloom column names; add `bloomctl` as a consumer.
  - `README.md` — same in-place correction of "Bloom-agnostic"; name `resolve_params` alongside the
    existing contracts.
  - `docs/01-contract-library-design.md`, `docs/02-contract-library-plan.md` — **banner lines only;
    bodies left frozen**, per the `2026-07-04-add-model-card-predict-inference-config` precedent.
    `docs/01` §1 and §5 currently state that Bloom-metadata → params resolution is out of scope and
    belongs to the producer/#3 — this change **reverses** that boundary, so the existing point-in-time
    banner is extended to say so. `docs/02`'s banner advances `v0.1.0a1–a3` → `a1–a4`.
  - **Out of scope, follow-up issues:** the `__init__.py` module docstring's stale one-line inventory
    (under-describing since `0.1.0a1`), `docs/02`'s superseded `#v{version}` `$id` fragment format,
    `uv publish` lacking `--skip-existing`, and `.claude/commands/review-openspec.md` asserting facts
    from a different repo. None are made newly wrong by this change; fixing them here would be scope
    creep on a release-blocking PR.
- **Scope decision — ship #15 alone.** The sibling issues #13 (shared `card_matches` selection
  predicate) and #14 (`PipelineCard` selection type + matcher) stay **open siblings**, not folded in.
  `resolve_params` is self-contained; both siblings carry unsettled design questions of their own
  (#13: ambiguous-/zero-match semantics; #14: the `contract_version` byte format, still open in its
  title). Coupling a release that **blocks bloom#411** to two undesigned changes trades a known
  unblock for unknown delay.
- **Consequence of that decision:** predict's two `choose_models(resolve_params(row), cards)`
  round-trip tests are **not** ported — `choose_models` does not exist here until #13 lands. They stay
  in predict, where the predicate lives and where an integration test belongs. A stub predicate in
  this repo's tests would assert against a fiction and create a second untracked copy of exactly the
  logic #13 exists to de-duplicate. When #13 lands, those tests can migrate here.
- **No TypeScript port.** The TS resolver lives Bloom-side; the Python (now contracts) oracle stays
  the reference it is tested *against* (predict#20). No TS artifact is a deliverable of this change.
- **Downstream consumers do the standard FULL re-pin** — `pin.json` + vendored schema (accept the
  `$id`-only diff) + regenerated TS — **not** merely a pip-floor bump.
- **Consumers to keep in sync (not edited here — this session does not modify the predict, bloom, or
  pipeline repos):**
  - bloom#411 — re-pin `sleap-roots-contracts>=0.1.0a4`; import `resolve_params` for
    `bloomctl cyl download-for-predict`.
  - predict#28 — re-pin, import from contracts, delete local `param_resolution.py` and its
    `param-resolution` capability spec; re-point TS-parity predict#20 at the contracts oracle.
  - `talmolab/sleap-roots-pipeline` `docs/bloom-integration/roadmap.md` — the "param oracle"
    reference now points at a shared contracts home (A3-params umbrella).
- **`contract_version`** is a producer-set field value, not a package constant. This change adds no
  envelope fields, so no forced bump.
