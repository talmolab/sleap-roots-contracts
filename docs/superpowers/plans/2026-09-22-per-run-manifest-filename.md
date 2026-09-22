# Per-Run Manifest Filename (contracts 0.1.0a9) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the naming and resolution contract that lets each pipeline run read its own
`run_manifest.<pipeline_run_id>.json` instead of a shared `run_manifest.json` that accumulates
every run's `scan_keys`.

**Architecture:** Four additions to `run_manifest.py`, all **pure** — no filesystem access. A
filename builder, an env reader, a resolution-policy function that takes an `exists` predicate
supplied by the caller, and an identity cross-check. The policy lives here so `bloomctl`,
`sleap-roots-predict` and `sleap-roots` share one definition instead of three; the I/O stays in
those consumers, which preserves this library's no-filesystem-I/O invariant.

**Tech Stack:** Python ≥3.11, Pydantic v2, pytest, ruff (pydocstyle/google), black (line-length 88), uv.

**Spec:** `sleap-roots-pipeline/docs/superpowers/specs/2026-09-21-per-run-run-manifest-identity-design.md`

## Global Constraints

- **No filesystem, network, or DB I/O in `src/`.** Stated in `openspec/project.md` as a defining
  property of this library. This is why the resolver takes an `exists` callable (see Deviation).
- **Purely additive.** `RUN_MANIFEST_FILENAME` and `RunManifest` keep their current behavior and
  values; nothing existing changes shape. Consumers on 0.1.0a8 must keep working untouched.
- **Target version `0.1.0a9`.** Current `origin/main` is `0.1.0a8` (tagged). Do **not** hand-edit
  `pyproject.toml`'s version — the Version Bump workflow (`.github/workflows/version.yml`,
  `workflow_dispatch`) owns it and opens its own PR, where CHANGELOG and schema regeneration land.
- **No JSON Schema emission.** `RunManifest` is a producer↔producer shape; `schema.MODELS` must
  stay `{result_envelope, analysis_input}`. There is an existing test asserting this — keep it green.
- Docstrings required in `src/` (google convention); tests exempt.
- Run checks with: `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`.

## Deviation from the approved design — read before Task 2

The design's §3.1 proposed `resolve_run_manifest_path(directory, pipeline_run_id) -> Path | None`,
which stats the filesystem. That contradicts `openspec/project.md`, which states this library does
**no filesystem I/O** — a property Bloom-side consumers rely on and that the whole "dependency-light
leaf library" framing rests on.

This plan therefore ships `resolve_run_manifest_name(pipeline_run_id, exists)` instead: identical
policy (per-run name → legacy name → raise-or-None), but the caller supplies the existence
predicate. Single definition of the policy is preserved — which was the actual goal — and the
policy becomes unit-testable with a dict-backed fake instead of `tmp_path`. Consumers gain three
lines each (`lambda name: (directory / name).is_file()`).

**This is a refinement, not a reversal.** Flag it if you disagree before starting Task 2.

## File Structure

| File | Responsibility |
|---|---|
| `src/sleap_roots_contracts/run_manifest.py` | modify — add the four functions + two exceptions alongside `RunManifest` and `RUN_MANIFEST_FILENAME` |
| `src/sleap_roots_contracts/__init__.py` | modify — re-export the new names, extend `__all__` |
| `tests/test_run_manifest.py` | modify — add tests for each new behavior |
| `openspec/changes/add-per-run-manifest-filename/` | create — proposal, tasks, spec delta on `run-manifest-contract` |
| `docs/CHANGELOG.md` | modify — Unreleased entry |
| `.gitignore` | modify — add `.worktrees/` (currently only in `.git/info/exclude`, untracked) |

Everything lives in `run_manifest.py` rather than a new module: it is currently ~60 lines, the
additions are ~70, and the filename convention and the model that lives in the file are one
concept. Splitting would separate `RUN_MANIFEST_FILENAME` from the function that generalizes it.

---

### Task 1: OpenSpec proposal for the contract change

**Files:**
- Create: `openspec/changes/add-per-run-manifest-filename/proposal.md`
- Create: `openspec/changes/add-per-run-manifest-filename/tasks.md`
- Create: `openspec/changes/add-per-run-manifest-filename/specs/run-manifest-contract/spec.md`

**Interfaces:**
- Consumes: nothing.
- Produces: the requirement text Tasks 2–5 implement. No code.

- [ ] **Step 1: Read the existing capability spec so the delta matches its voice**

Run: `cat openspec/specs/run-manifest-contract/spec.md`

Note its five existing requirements. You are **adding** requirements, not modifying them —
`RUN_MANIFEST_FILENAME` keeps its literal value, so "Well-Known Filename Constant" is untouched.

- [ ] **Step 2: Write `proposal.md`**

```markdown
# Add a per-run run-manifest filename and its resolution policy

## Why

`bloomctl`'s `write_run_manifest` unions `scan_keys` into a single shared `run_manifest.json`
and never prunes, and `sleap-roots-pipeline#37` established that `out_dir` is permanently shared
across all runs by design (isolating it breaks the skip-if-done the batch oracle depends on). So
every run operates on the union of all runs. Measured four times on 2026-09-21 on current pins: a
1-scan request carried a 12-key manifest and write-back delivered all 12, creating
`cyl_trait_sources` rows for eleven unrequested scans.

Fix shape (a) from talmolab/sleap-roots-pipeline#71: give the manifest a per-run *identity*
while artifacts stay shared, so dedup keeps working. That needs a filename convention, and it
needs one shared definition of how a reader resolves and falls back — three consumers
(`bloomctl`, `sleap-roots-predict`, `sleap-roots`) must agree exactly or the rollout skews.

## What Changes

- **ADDED** `run_manifest_filename(pipeline_run_id)` — the per-run filename, with validation that
  the id is safe to use as a path component.
- **ADDED** `pipeline_run_id_from_env()` — one definition of "which run am I", read from
  `ARGO_WORKFLOW_NAME`.
- **ADDED** `resolve_run_manifest_name(pipeline_run_id, exists)` — the resolution policy: per-run
  name, then the legacy name, then raise if the run id is known and neither is present, else
  `None`. Pure: the caller supplies `exists`, so the library keeps doing no filesystem I/O.
- **ADDED** `check_run_manifest_identity(...)` — the cross-check that a per-run-named manifest
  names the run reading it. This is bloom#703's cross-check, possible for the first time.
- **ADDED** `RunManifestMissingError`, `RunManifestIdentityError`.

`RUN_MANIFEST_FILENAME` and `RunManifest` are unchanged. This release is additive; 0.1.0a8
consumers are unaffected until they adopt the new names.

## Impact

- Affected specs: `run-manifest-contract`
- Affected code: `src/sleap_roots_contracts/run_manifest.py`, `__init__.py`
- Downstream (separate changes, not this one): `salk-bloom` bloomctl writer + ingest reader,
  `sleap-roots-predict`, `sleap-roots` traits, then template pin bumps in `sleap-roots-pipeline`.
```

- [ ] **Step 3: Write the spec delta**

Create `openspec/changes/add-per-run-manifest-filename/specs/run-manifest-contract/spec.md`:

```markdown
## ADDED Requirements

### Requirement: Per-Run Manifest Filename

The library SHALL export `run_manifest_filename(pipeline_run_id: str) -> str`, returning
`"run_manifest.<pipeline_run_id>.json"`. Because the returned value is used as a path component
and `pipeline_run_id` originates in an environment variable, the function SHALL reject any id
that is not a safe single path component: it SHALL accept only ids matching
`[A-Za-z0-9][A-Za-z0-9._-]*` with length at most 200, and SHALL raise `ValueError` otherwise.

#### Scenario: Filename is built from the run id
- **WHEN** `run_manifest_filename("sleap-roots-pipeline-9s92h")` is called
- **THEN** it returns `"run_manifest.sleap-roots-pipeline-9s92h.json"`

#### Scenario: A path separator is rejected
- **WHEN** `run_manifest_filename("../etc/passwd")` is called
- **THEN** `ValueError` is raised

#### Scenario: An empty or blank id is rejected
- **WHEN** `run_manifest_filename("")` or `run_manifest_filename("   ")` is called
- **THEN** `ValueError` is raised

#### Scenario: An over-long id is rejected
- **WHEN** `run_manifest_filename("a" * 201)` is called
- **THEN** `ValueError` is raised

### Requirement: Run Identity Is Read From One Place

The library SHALL export `pipeline_run_id_from_env(env=None) -> str | None`, returning the value
of `ARGO_WORKFLOW_NAME` when it is set and not blank, and `None` otherwise. Leading and trailing
whitespace SHALL be stripped. When `env` is omitted, `os.environ` is read.

#### Scenario: The run id is returned when set
- **WHEN** `ARGO_WORKFLOW_NAME` is `"sleap-roots-pipeline-9s92h"`
- **THEN** `pipeline_run_id_from_env()` returns `"sleap-roots-pipeline-9s92h"`

#### Scenario: An unset variable reads as no run identity
- **WHEN** `ARGO_WORKFLOW_NAME` is not present in the environment
- **THEN** `pipeline_run_id_from_env()` returns `None`

#### Scenario: A blank variable reads as no run identity
- **WHEN** `ARGO_WORKFLOW_NAME` is `"   "`
- **THEN** `pipeline_run_id_from_env()` returns `None`

### Requirement: Manifest Resolution Policy

The library SHALL export `resolve_run_manifest_name(pipeline_run_id, exists) -> str | None`,
where `exists` is a callable taking a filename and returning whether it is present. The library
SHALL perform no filesystem access itself. Resolution order SHALL be: the per-run filename when
`pipeline_run_id` is not `None`; then `RUN_MANIFEST_FILENAME`. When neither is present, the
function SHALL raise `RunManifestMissingError` if `pipeline_run_id` is not `None`, and SHALL
return `None` otherwise.

The asymmetry is deliberate. A caller that knows its run id is running under orchestration, where
a missing manifest is a fault; a caller with no run id is running locally, where unscoped
discovery is the established behavior.

#### Scenario: The per-run manifest is preferred
- **GIVEN** both `run_manifest.wf1.json` and `run_manifest.json` exist
- **WHEN** `resolve_run_manifest_name("wf1", exists)` is called
- **THEN** it returns `"run_manifest.wf1.json"`

#### Scenario: Falls back to the legacy name
- **GIVEN** only `run_manifest.json` exists
- **WHEN** `resolve_run_manifest_name("wf1", exists)` is called
- **THEN** it returns `"run_manifest.json"`

#### Scenario: A known run id with no manifest is an error
- **GIVEN** neither file exists
- **WHEN** `resolve_run_manifest_name("wf1", exists)` is called
- **THEN** `RunManifestMissingError` is raised

#### Scenario: An unknown run id with no manifest is not an error
- **GIVEN** neither file exists
- **WHEN** `resolve_run_manifest_name(None, exists)` is called
- **THEN** it returns `None`

#### Scenario: An unknown run id never looks for a per-run name
- **GIVEN** only `run_manifest.wf1.json` exists
- **WHEN** `resolve_run_manifest_name(None, exists)` is called
- **THEN** it returns `None`

### Requirement: Run Identity Cross-Check

The library SHALL export `check_run_manifest_identity(manifest, pipeline_run_id, filename)`,
raising `RunManifestIdentityError` when `manifest.pipeline_run_id` differs from `pipeline_run_id`,
and returning `None` otherwise. Consumers call it only for a manifest read under a per-run
filename, where the two are required to agree.

#### Scenario: A matching identity passes
- **WHEN** a manifest with `pipeline_run_id="wf1"` is checked against `"wf1"`
- **THEN** no exception is raised

#### Scenario: A foreign manifest is rejected
- **WHEN** a manifest with `pipeline_run_id="wf2"` is checked against `"wf1"`
- **THEN** `RunManifestIdentityError` is raised, and its message names both ids and the filename

### Requirement: New Names Are Exported From The Package Root

The library SHALL export `run_manifest_filename`, `pipeline_run_id_from_env`,
`resolve_run_manifest_name`, `check_run_manifest_identity`, `RunManifestMissingError` and
`RunManifestIdentityError` from the package root, and list them in `__all__`.

#### Scenario: Names importable from the package root
- **WHEN** a consumer imports all six names from `sleap_roots_contracts`
- **THEN** the import succeeds and each name appears in `sleap_roots_contracts.__all__`
```

- [ ] **Step 4: Write `tasks.md` mirroring Tasks 2–6 of this plan**

One `- [ ]` per task below, each naming its validation command. Keep it short; this plan is the
detailed version.

- [ ] **Step 5: Validate strictly**

Run: `openspec validate add-per-run-manifest-filename --strict`
Expected: passes with 0 failures. Fix every issue before continuing.

- [ ] **Step 6: Commit**

```bash
git add openspec/changes/add-per-run-manifest-filename .gitignore
git commit -m "docs(openspec): propose the per-run run-manifest filename (#71)"
```

Add `.worktrees/` to `.gitignore` in this same commit — it is currently only in
`.git/info/exclude`, so it is protected locally but not for anyone else.

- [ ] **Step 7: STOP — user approval gate**

Present the change-id, the affected capability (`run-manifest-contract`, all ADDED), and the
Deviation note above. Do not start Task 2 until the user approves.

---

### Task 2: `run_manifest_filename`

**Files:**
- Modify: `src/sleap_roots_contracts/run_manifest.py`
- Test: `tests/test_run_manifest.py`

**Interfaces:**
- Consumes: `RUN_MANIFEST_FILENAME` (existing).
- Produces: `run_manifest_filename(pipeline_run_id: str) -> str`, raising `ValueError` on an
  unsafe id. Tasks 3 and 5 call it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_run_manifest.py`:

```python
def test_run_manifest_filename_is_built_from_the_run_id():
    """The per-run filename interpolates the run id between prefix and suffix."""
    assert (
        run_manifest_filename("sleap-roots-pipeline-9s92h")
        == "run_manifest.sleap-roots-pipeline-9s92h.json"
    )


def test_run_manifest_filename_accepts_the_local_placeholder():
    """bloomctl's non-Argo placeholder shape is a valid id."""
    assert run_manifest_filename("local-ab12cd34") == "run_manifest.local-ab12cd34.json"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "..",
        ".",
        "../etc/passwd",
        "a/b",
        "a\\b",
        ".hidden",
        "has space",
        "has\x00null",
        "a" * 201,
    ],
)
def test_run_manifest_filename_rejects_an_unsafe_id(bad):
    """The id becomes a path component, so anything unsafe raises rather than escaping."""
    with pytest.raises(ValueError):
        run_manifest_filename(bad)


def test_run_manifest_filename_never_collides_with_the_legacy_name():
    """No id can produce the legacy filename, so the two namespaces stay distinct."""
    assert run_manifest_filename("x") != RUN_MANIFEST_FILENAME
```

Add `run_manifest_filename` to the existing import at the top of the file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k run_manifest_filename -v`
Expected: FAIL — `ImportError: cannot import name 'run_manifest_filename'`

- [ ] **Step 3: Write the implementation**

Add to `src/sleap_roots_contracts/run_manifest.py`, after `RUN_MANIFEST_FILENAME`:

```python
# The per-run filename's fixed parts. `RUN_MANIFEST_FILENAME` stays the legacy/local name, so
# the two forms never collide: a valid run id can never be empty, and the pattern below forbids
# a leading dot, so "run_manifest." + id + ".json" is always longer and differently shaped.
_FILENAME_PREFIX = "run_manifest."
_FILENAME_SUFFIX = ".json"

# A run id becomes a path component, and it arrives from an environment variable, so it is
# validated as an allowlist rather than by blocking known-bad characters. An Argo workflow name
# is an RFC-1123 label (lowercase alphanumerics and '-'), and bloomctl's non-Argo placeholder is
# `local-<hex8>`; both match. Requiring the first character to be alphanumeric is what rejects
# "." and ".." without special-casing them.
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_RUN_ID_MAX_LENGTH = 200


def run_manifest_filename(pipeline_run_id: str) -> str:
    """Return the per-run manifest filename for ``pipeline_run_id``.

    Args:
        pipeline_run_id: The run identity, e.g. an Argo ``{{workflow.name}}``.

    Returns:
        ``"run_manifest.<pipeline_run_id>.json"``.

    Raises:
        ValueError: If ``pipeline_run_id`` is not usable as a single path component —
            empty, over-long, or containing anything outside
            ``[A-Za-z0-9][A-Za-z0-9._-]*``. Raised rather than sanitized: a silently
            rewritten id would name a file no other stage in the run would look for.
    """
    if not isinstance(pipeline_run_id, str):
        raise ValueError(f"pipeline_run_id must be a str, got {type(pipeline_run_id)!r}")
    if len(pipeline_run_id) > _RUN_ID_MAX_LENGTH:
        raise ValueError(
            f"pipeline_run_id is {len(pipeline_run_id)} characters, "
            f"over the {_RUN_ID_MAX_LENGTH} limit"
        )
    if not _RUN_ID_PATTERN.fullmatch(pipeline_run_id):
        raise ValueError(
            f"pipeline_run_id {pipeline_run_id!r} is not usable as a filename component: "
            "it must start with a letter or digit and contain only letters, digits, "
            "'.', '_' and '-'"
        )
    return f"{_FILENAME_PREFIX}{pipeline_run_id}{_FILENAME_SUFFIX}"
```

Add `import re` to the module's imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_manifest.py -k run_manifest_filename -v`
Expected: PASS (15 tests — 2 explicit + 11 parametrized + 1 collision)

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add run_manifest_filename with path-component validation"
```

---

### Task 3: `pipeline_run_id_from_env`

**Files:**
- Modify: `src/sleap_roots_contracts/run_manifest.py`
- Test: `tests/test_run_manifest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `pipeline_run_id_from_env(env: Mapping[str, str] | None = None) -> str | None`.
  Consumers in other repos call it to decide whether they know their run identity.

- [ ] **Step 1: Write the failing tests**

```python
def test_pipeline_run_id_from_env_returns_the_workflow_name():
    """ARGO_WORKFLOW_NAME is the run identity."""
    assert (
        pipeline_run_id_from_env({"ARGO_WORKFLOW_NAME": "sleap-roots-pipeline-9s92h"})
        == "sleap-roots-pipeline-9s92h"
    )


def test_pipeline_run_id_from_env_is_none_when_unset():
    """No variable means no run identity — the local/dev case."""
    assert pipeline_run_id_from_env({}) is None


def test_pipeline_run_id_from_env_is_none_when_blank():
    """A set-but-empty variable is common in k8s manifests and means the same as unset."""
    assert pipeline_run_id_from_env({"ARGO_WORKFLOW_NAME": "   "}) is None


def test_pipeline_run_id_from_env_strips_surrounding_whitespace():
    """A stray newline from a shell-substituted value must not change the filename."""
    assert pipeline_run_id_from_env({"ARGO_WORKFLOW_NAME": " wf1\n"}) == "wf1"


def test_pipeline_run_id_from_env_reads_os_environ_by_default(monkeypatch):
    """Omitting env reads the real process environment."""
    monkeypatch.setenv("ARGO_WORKFLOW_NAME", "wf-from-os")
    assert pipeline_run_id_from_env() == "wf-from-os"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k pipeline_run_id_from_env -v`
Expected: FAIL — `ImportError: cannot import name 'pipeline_run_id_from_env'`

- [ ] **Step 3: Write the implementation**

```python
#: The environment variable every pipeline stage reads its run identity from. Set to Argo's
#: `{{workflow.name}}` on all five cluster templates; deliberately absent from the local-WSL2
#: templates, which is what keeps local runs on the legacy filename and legacy semantics.
PIPELINE_RUN_ID_ENV_VAR = "ARGO_WORKFLOW_NAME"


def pipeline_run_id_from_env(
    env: Mapping[str, str] | None = None,
) -> str | None:
    """Return this process's run identity, or ``None`` when it has none.

    Args:
        env: Environment mapping to read. Defaults to ``os.environ``. Injectable so callers
            and tests need no monkeypatching.

    Returns:
        The stripped value of ``ARGO_WORKFLOW_NAME``, or ``None`` when it is unset or blank.
        ``None`` means "not running under orchestration" and is what selects the legacy
        filename and today's unscoped-discovery behavior; it is not an error.
    """
    source = os.environ if env is None else env
    value = source.get(PIPELINE_RUN_ID_ENV_VAR)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
```

Add `import os` and `from collections.abc import Mapping` to the module's imports.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_manifest.py -k pipeline_run_id_from_env -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add pipeline_run_id_from_env"
```

---

### Task 4: `resolve_run_manifest_name` and `RunManifestMissingError`

**Files:**
- Modify: `src/sleap_roots_contracts/run_manifest.py`
- Test: `tests/test_run_manifest.py`

**Interfaces:**
- Consumes: `run_manifest_filename` (Task 2), `RUN_MANIFEST_FILENAME`.
- Produces: `RunManifestMissingError(LookupError)` and
  `resolve_run_manifest_name(pipeline_run_id: str | None, exists: Callable[[str], bool]) -> str | None`.
  This is the function all three consumer repos call.

- [ ] **Step 1: Write the failing tests**

```python
def _exists_among(*names):
    """Build an `exists` predicate over a fixed set of present filenames."""
    present = set(names)
    return lambda name: name in present


def test_resolve_prefers_the_per_run_manifest():
    """With both present, the run's own manifest wins."""
    exists = _exists_among("run_manifest.wf1.json", RUN_MANIFEST_FILENAME)
    assert resolve_run_manifest_name("wf1", exists) == "run_manifest.wf1.json"


def test_resolve_falls_back_to_the_legacy_manifest():
    """Mid-rollout, a new reader still finds an old writer's file."""
    exists = _exists_among(RUN_MANIFEST_FILENAME)
    assert resolve_run_manifest_name("wf1", exists) == RUN_MANIFEST_FILENAME


def test_resolve_raises_when_the_run_id_is_known_and_nothing_is_present():
    """Under orchestration a missing manifest is a fault, never 'scope to everything'."""
    exists = _exists_among()
    with pytest.raises(RunManifestMissingError) as excinfo:
        resolve_run_manifest_name("wf1", exists)
    assert "run_manifest.wf1.json" in str(excinfo.value)
    assert RUN_MANIFEST_FILENAME in str(excinfo.value)


def test_resolve_returns_none_when_there_is_no_run_id_and_nothing_is_present():
    """Locally, an absent manifest keeps today's unscoped behavior."""
    assert resolve_run_manifest_name(None, _exists_among()) is None


def test_resolve_ignores_a_per_run_manifest_when_the_run_id_is_unknown():
    """A caller with no identity must not adopt some other run's scope."""
    exists = _exists_among("run_manifest.wf1.json")
    assert resolve_run_manifest_name(None, exists) is None


def test_resolve_does_not_call_exists_for_the_per_run_name_when_the_run_id_is_unknown():
    """The per-run candidate is not merely skipped in the result — it is never probed."""
    probed = []

    def exists(name):
        probed.append(name)
        return False

    resolve_run_manifest_name(None, exists)
    assert probed == [RUN_MANIFEST_FILENAME]


def test_resolve_propagates_an_invalid_run_id():
    """An unsafe id is a programming error, surfaced as ValueError, not swallowed as 'missing'."""
    with pytest.raises(ValueError):
        resolve_run_manifest_name("../escape", _exists_among())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k resolve -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_run_manifest_name'`

- [ ] **Step 3: Write the implementation**

```python
class RunManifestMissingError(LookupError):
    """No run manifest was found for a caller that knows which run it is.

    A subclass of ``LookupError`` so a consumer can catch it alongside its own
    not-found handling, but distinct enough to re-raise as that repo's own error type
    (``click.ClickException`` in bloomctl, for instance).
    """


def resolve_run_manifest_name(
    pipeline_run_id: str | None,
    exists: Callable[[str], bool],
) -> str | None:
    """Return the manifest filename this caller should read, if any.

    The library performs no filesystem access; ``exists`` is the caller's probe, typically
    ``lambda name: (directory / name).is_file()``. Keeping the policy here and the I/O in the
    caller is what lets bloomctl, predict and traits share one definition of the fallback order
    without this library growing a filesystem dependency.

    Args:
        pipeline_run_id: This run's identity, or ``None`` when the caller has none (see
            :func:`pipeline_run_id_from_env`).
        exists: Predicate answering whether a filename is present where the caller is looking.

    Returns:
        The per-run filename when it is present; else ``RUN_MANIFEST_FILENAME`` when that is
        present; else ``None``, but only when ``pipeline_run_id`` is ``None``.

    Raises:
        RunManifestMissingError: If ``pipeline_run_id`` is not ``None`` and neither candidate is
            present. Deliberately not ``None``: every consumer treats an absent manifest as
            "discover everything in this directory", which under a shared output tree means
            processing and ingesting other runs' scans. A stage that knows its run id is running
            under orchestration, where a manifest is always written, so its absence is a fault.
        ValueError: If ``pipeline_run_id`` is not usable as a filename component.
    """
    candidates: list[str] = []
    if pipeline_run_id is not None:
        candidates.append(run_manifest_filename(pipeline_run_id))
    candidates.append(RUN_MANIFEST_FILENAME)

    for name in candidates:
        if exists(name):
            return name

    if pipeline_run_id is not None:
        raise RunManifestMissingError(
            f"no run manifest for run {pipeline_run_id!r}: looked for "
            f"{' then '.join(repr(c) for c in candidates)}"
        )
    return None
```

Add `Callable` to the `collections.abc` import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_manifest.py -k resolve -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add resolve_run_manifest_name with fail-loud policy"
```

---

### Task 5: `check_run_manifest_identity` and package exports

**Files:**
- Modify: `src/sleap_roots_contracts/run_manifest.py`
- Modify: `src/sleap_roots_contracts/__init__.py`
- Test: `tests/test_run_manifest.py`

**Interfaces:**
- Consumes: `RunManifest` (existing).
- Produces: `RunManifestIdentityError(ValueError)` and
  `check_run_manifest_identity(manifest: RunManifest, pipeline_run_id: str, filename: str) -> None`.
  Plus all six new names re-exported from the package root.

- [ ] **Step 1: Write the failing tests**

```python
def test_identity_check_passes_for_the_owning_run():
    """The ordinary case: the file this run wrote names this run."""
    manifest = make_manifest(pipeline_run_id="wf1")
    assert (
        check_run_manifest_identity(manifest, "wf1", "run_manifest.wf1.json") is None
    )


def test_identity_check_rejects_a_foreign_manifest():
    """A per-run-named file naming a different run means the tree is not what we think."""
    manifest = make_manifest(pipeline_run_id="wf2")
    with pytest.raises(RunManifestIdentityError) as excinfo:
        check_run_manifest_identity(manifest, "wf1", "run_manifest.wf1.json")
    message = str(excinfo.value)
    assert "wf1" in message
    assert "wf2" in message
    assert "run_manifest.wf1.json" in message


def test_identity_error_is_a_value_error():
    """Consumers already catching ValueError around manifest parsing keep working."""
    assert issubclass(RunManifestIdentityError, ValueError)


def test_new_names_are_exported_from_the_package_root():
    """The six new names are importable from the package root and listed in __all__."""
    import sleap_roots_contracts as src_pkg

    for name in (
        "run_manifest_filename",
        "pipeline_run_id_from_env",
        "resolve_run_manifest_name",
        "check_run_manifest_identity",
        "RunManifestMissingError",
        "RunManifestIdentityError",
    ):
        assert hasattr(src_pkg, name), name
        assert name in src_pkg.__all__, name


def test_legacy_filename_constant_is_unchanged():
    """This release is additive — the existing constant keeps its exact value."""
    assert RUN_MANIFEST_FILENAME == "run_manifest.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k "identity or exported or legacy_filename" -v`
Expected: FAIL — `ImportError: cannot import name 'check_run_manifest_identity'`

- [ ] **Step 3: Write the implementation**

In `run_manifest.py`:

```python
class RunManifestIdentityError(ValueError):
    """A manifest read under a per-run filename names a different run.

    A ``ValueError`` because it is the same class of problem as a manifest that fails
    validation: the file is not what its name claims.
    """


def check_run_manifest_identity(
    manifest: RunManifest,
    pipeline_run_id: str,
    filename: str,
) -> None:
    """Verify a per-run-named manifest names the run that is reading it.

    Only meaningful for a manifest resolved under :func:`run_manifest_filename`; the legacy
    filename carries no run identity in its name, and before per-run naming existed the
    producer overwrote ``pipeline_run_id`` on every merge, so the field could never disagree.
    This is the cross-check bloom#703 asked for, possible for the first time.

    Args:
        manifest: The parsed manifest.
        pipeline_run_id: The reader's own run identity.
        filename: The name it was read from, used in the error message.

    Returns:
        None.

    Raises:
        RunManifestIdentityError: If the manifest names a different run.
    """
    if manifest.pipeline_run_id != pipeline_run_id:
        raise RunManifestIdentityError(
            f"{filename} was read as run {pipeline_run_id!r}'s manifest but names run "
            f"{manifest.pipeline_run_id!r}"
        )
```

In `__init__.py`, extend the existing run_manifest import and `__all__`:

```python
from .run_manifest import (
    RUN_MANIFEST_FILENAME,
    RunManifest,
    RunManifestIdentityError,
    RunManifestMissingError,
    check_run_manifest_identity,
    pipeline_run_id_from_env,
    resolve_run_manifest_name,
    run_manifest_filename,
)
```

and add the six new names to `__all__` alongside `"RunManifest"` and `"RUN_MANIFEST_FILENAME"`.

- [ ] **Step 4: Run the full suite plus linters**

Run: `uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
Expected: all pass. The baseline was 460 tests; expect 460 + the ~32 added here.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py src/sleap_roots_contracts/__init__.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add the identity cross-check and export the new names"
```

---

### Task 6: Module docstring, CHANGELOG, and OpenSpec task sync

**Files:**
- Modify: `src/sleap_roots_contracts/run_manifest.py` (module docstring)
- Modify: `docs/CHANGELOG.md`
- Modify: `openspec/changes/add-per-run-manifest-filename/tasks.md`

**Interfaces:**
- Consumes: everything from Tasks 2–5.
- Produces: no code.

- [ ] **Step 1: Extend the module docstring**

The current docstring describes only the shared-file model. Append:

```
Since 0.1.0a9 the manifest may also be named per run — ``run_manifest.<pipeline_run_id>.json``,
built by :func:`run_manifest_filename` — so that runs sharing an output directory no longer
share a manifest. ``RUN_MANIFEST_FILENAME`` remains the name used when a stage has no run
identity (no ``ARGO_WORKFLOW_NAME``), which keeps local and ``local-WSL2-*`` runs on the
previous behavior. :func:`resolve_run_manifest_name` is the single definition of how a reader
chooses between the two and what a missing manifest means; see
talmolab/sleap-roots-pipeline#71.
```

- [ ] **Step 2: Add the CHANGELOG entry**

Under `## [Unreleased]` in `docs/CHANGELOG.md`, matching the file's existing style:

```markdown
### Added
- Per-run run-manifest naming: `run_manifest_filename`, `pipeline_run_id_from_env`,
  `resolve_run_manifest_name`, `check_run_manifest_identity`, and the
  `RunManifestMissingError` / `RunManifestIdentityError` exceptions
  (talmolab/sleap-roots-pipeline#71). Additive — `RunManifest` and `RUN_MANIFEST_FILENAME`
  are unchanged, so 0.1.0a8 consumers are unaffected until they adopt the new names.
```

- [ ] **Step 3: Tick the OpenSpec tasks**

Mark Tasks 2–6 `- [x]` in `openspec/changes/add-per-run-manifest-filename/tasks.md`.

- [ ] **Step 4: Re-validate and run everything**

Run: `openspec validate add-per-run-manifest-filename --strict && uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py docs/CHANGELOG.md openspec/changes/add-per-run-manifest-filename/tasks.md
git commit -m "docs(run-manifest): document per-run naming and close the change's tasks"
```

---

### Task 7: PR, then the version bump

**Files:** none in this repo's source.

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin add-per-run-manifest-filename
```

Use `/pr-description`. Reference change-id `add-per-run-manifest-filename` and
talmolab/sleap-roots-pipeline#71. State plainly that this is additive and that **no consumer is
affected until it bumps its pin** — reviewers should not expect downstream changes here.

- [ ] **Step 2: Run `/review-pr` before merging**

- [ ] **Step 3: After merge, trigger the version bump to `0.1.0a9`**

`.github/workflows/version.yml` is `workflow_dispatch` with a `bump_type` choice — use `alpha`,
or `custom_version` `0.1.0a9`. It bumps `pyproject.toml` via `uv version` and opens its own PR;
CHANGELOG finalization and schema regeneration happen on that PR. Do **not** hand-edit the
version in this branch.

- [ ] **Step 4: Confirm the release is installable before any consumer work starts**

Run: `uv run --with "sleap-roots-contracts==0.1.0a9" --no-project python -c "from sleap_roots_contracts import run_manifest_filename; print(run_manifest_filename('wf1'))"`
Expected: prints `run_manifest.wf1.json`.

This is the gate for plan 3 — do not bump any consumer pin until this command succeeds against
the published package, not a local checkout.

---

## Self-Review

**Spec coverage.** Design §3.1's three functions → Tasks 2, 3, 4; its id validation → Task 2;
§3.2's cross-check → Task 5; §2.2's resolution order and fail-loud asymmetry → Task 4; §2.3's
"no run id means legacy name" → Tasks 3 and 4. Design §3.3 (call sites), §4 (rollout), §5 (live
E2E) are **out of scope here by design** — they are plans 2 and 3. §2.1's predict#40 comment and
§7's roadmap entry belong to plan 3.

**Deviation recorded.** §3.1's `resolve_run_manifest_path` became
`resolve_run_manifest_name(pipeline_run_id, exists)` to preserve the library's no-filesystem-I/O
invariant. Flagged at the top; gated on user agreement at Task 1 Step 7.

**Placeholders.** None — every code step carries real code, every test step real assertions.

**Type consistency.** `run_manifest_filename(str) -> str` is called by
`resolve_run_manifest_name` in Task 4 exactly as defined in Task 2.
`pipeline_run_id_from_env() -> str | None` feeds `resolve_run_manifest_name`'s first parameter,
also `str | None`. `check_run_manifest_identity` takes `RunManifest`, matching the existing model.
Exception names are identical across Tasks 4, 5 and the spec delta.
