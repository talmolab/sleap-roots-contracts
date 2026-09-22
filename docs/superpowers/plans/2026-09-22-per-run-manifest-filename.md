# Per-Run Manifest Filename (contracts 0.1.0a9) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-09-22)** — revision 2 rewrote the API after `/review-openspec`; revision 3
closes what the re-review then found in it. Revision 1's `exists`-predicate API is gone. See
"What changed". Do not implement from a cached copy of any earlier revision.

**Goal:** Add the naming and resolution contract that lets each pipeline run read its own
`run_manifest.<pipeline_run_id>.json` instead of a shared `run_manifest.json` that accumulates
every run's `scan_keys`.

**Architecture:** Five functions, a result type and three exceptions in `run_manifest.py`. One reader
(`read_run_manifest`) owns the candidate order, the open, and the fail-loud decision for all four
consumer call sites, so none of them re-invents it. It returns the bytes it read, not a path, so
there is no probe/read window.

**Tech Stack:** Python ≥3.11, Pydantic v2, pytest, ruff (pydocstyle/google), black (line-length 88), uv.

**Spec:** `sleap-roots-pipeline/docs/superpowers/specs/2026-09-21-per-run-run-manifest-identity-design.md`
(at commit `ab90185` or later — earlier revisions carry the withdrawn purity premise).

## Global Constraints

- **No ambient, caller-supplied-directory reads in the contract-model surface.** This is the real
  invariant, and it is narrower than `openspec/project.md` currently claims. `emit_schema()`
  (`schema.py:93-98`) writes files, `_default_schema_dir()` falls back to `Path.cwd()`, and
  `registry.py`/`examples/` read packaged resources. `read_run_manifest` is a deliberate,
  documented exception for one named file; `project.md`'s wording gets corrected in Task 7.
- **Purely additive to existing names.** `RUN_MANIFEST_FILENAME` and `RunManifest` keep their
  current values and behavior. 0.1.0a8 consumers must keep working untouched.
- **Target version `0.1.0a9`.** Current `origin/main` is `0.1.0a8` (tagged). Do **not** hand-edit
  `pyproject.toml`'s version — the Version Bump workflow (`.github/workflows/version.yml`,
  `workflow_dispatch`) owns it and opens its own PR.
- **No JSON Schema emission.** `schema.MODELS` must stay `{result_envelope, analysis_input}`.
- **The run-id cap is 237, not 253.** The filename adds 18 characters (`run_manifest.` +
  `.json`) and 237 + 18 = 255 = `NAME_MAX`. Kubernetes allows 253-character names, which this
  deliberately cannot support; Argo's `generateName` emits ~26.
- Docstrings required in `src/` (google convention); tests exempt.
- Checks: `uv run pytest -v`, `uv run black --check src tests`, `uv run ruff check src tests`.

## What changed

| before | after | why |
|---|---|---|
| `resolve_run_manifest_name(id, exists)` | `read_run_manifest(directory, id, *, allow_legacy)` returning `(filename, data, mode, is_per_run)` | the `exists` boolean collapsed `EACCES` into "absent" (falling through to the stale legacy file, which `ingest.py:115-127` deliberately guards against) and reopened a probe/read window `run_batch` works to avoid |
| justified by "the library does no filesystem I/O" | justified by "no caller-directory reads in the model surface" | the original premise was false — see Global Constraints |
| legacy fallback unconditional | `allow_legacy` keyword-only and **required** | unconditional fallback always succeeds in the shared trees, so `RunManifestMissingError` could never fire and the fail-loud guarantee was decorative (design §2.9) |
| — | added `run_manifest_name_for_writing`, exported `PIPELINE_RUN_ID_ENV_VAR` | otherwise the writer-side rule and the env-var name live only in prose, and bloomctl keeps a hardcoded string |
| cross-check always applies | no-op on the legacy filename | otherwise all four sites write the same `if filename != RUN_MANIFEST_FILENAME` guard |
| cap 200 | cap 237 | 200 could reject a legal name and then crash every stage |
| delta purely ADDED | one **MODIFIED** requirement | "single source of truth for the manifest's on-disk filename" becomes false once a second convention exists |
| *(rev 3)* `allow_legacy` gated the legacy name always | it is ignored when there is no run identity | `RUN_MANIFEST_FILENAME` is the *correct* name without an identity, not a fallback; gating it built an empty candidate list and silently unscoped every local run at design §4 step 6 |
| *(rev 3)* returned `(filename, data, is_per_run)` | adds `mode` | predict must reproduce the source's permissions without a second stat; the fd is already open, so `fstat` is free |
| *(rev 3)* `RunManifestIdentityError(ValueError)` | `RunManifestError` base; identity error is not a `ValueError` | pydantic's `ValidationError` is a `ValueError`, so a generic parse handler would have swallowed "this tree is not yours" |
| *(rev 3)* `-k read_run_manifest` | `-k test_read` | no test name contained that substring, so the gate collected zero tests |

## File Structure

| File | Responsibility |
|---|---|
| `src/sleap_roots_contracts/run_manifest.py` | modify — five functions, `RunManifestRead`, three exceptions |
| `src/sleap_roots_contracts/__init__.py` | modify — re-export, extend `__all__` |
| `tests/test_run_manifest.py` | modify — tests per task |
| `openspec/changes/add-per-run-manifest-filename/` | modify — proposal, tasks, delta (Task 1 revision) |
| `docs/CHANGELOG.md` | modify — Unreleased entry |
| `README.md` | modify — the run-manifest paragraph (lines ~53-57) |
| `openspec/project.md` | modify — two false claims, plus the new API |

---

### Task 1R: Revise the OpenSpec proposal

**Files:** all three under `openspec/changes/add-per-run-manifest-filename/`.

Task 1 already landed (`1113874`). This revises it against the review. The full replacement text
for `proposal.md` and the spec delta is in the dispatch brief for this task — use it verbatim.

Key deltas from the committed version:
- The `## ADDED Requirements` section replaces `resolve_run_manifest_name` with
  `read_run_manifest`, adds `run_manifest_name_for_writing`, adds `PIPELINE_RUN_ID_ENV_VAR` to
  the export requirement, and raises the cap to 237.
- A new `## MODIFIED Requirements` section restates **Well-Known Filename Constant** in full
  (OpenSpec requires the complete text, not a diff), adding one sentence that it is the name used
  when no run identity is available, and cross-referencing the per-run convention.
- New scenarios: the 237-char positive boundary; a non-`str` id; a blank-but-not-`None` id;
  `EACCES` propagating rather than advancing to the next candidate; `allow_legacy=False`
  refusing the legacy file.
- `## Impact` gains `README.md` and `openspec/project.md`.

- [ ] Steps are in the dispatch brief. Validate with
      `openspec validate add-per-run-manifest-filename --strict`, then commit.

---

### Task 2: `run_manifest_filename`

**Files:** modify `src/sleap_roots_contracts/run_manifest.py`; test `tests/test_run_manifest.py`.

**Interfaces:**
- Consumes: `RUN_MANIFEST_FILENAME` (existing).
- Produces: `run_manifest_filename(pipeline_run_id: str) -> str`, raising `ValueError` on an
  unsafe id. Tasks 4 and 5 call it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_run_manifest.py`, extending the existing import line:

```python
def test_run_manifest_filename_is_built_from_the_run_id():
    """The per-run filename interpolates the run id between prefix and suffix."""
    assert (
        run_manifest_filename("sleap-roots-pipeline-9s92h")
        == "run_manifest.sleap-roots-pipeline-9s92h.json"
    )


def test_run_manifest_filename_accepts_an_id_of_the_local_placeholder_shape():
    """An id of this shape is filename-safe.

    This asserts only that the shape passes validation. It is NOT sanction for naming a file
    after bloomctl's `local-<uuid8>` placeholder: design §2.3 forbids that, because no other
    process can reproduce another's placeholder, so a writer must pass `None` here and use
    `run_manifest_name_for_writing`, which selects the legacy name when there is no identity.
    """
    assert run_manifest_filename("local-ab12cd34") == "run_manifest.local-ab12cd34.json"


def test_run_manifest_filename_accepts_the_maximum_length_id():
    """237 is the positive boundary: 237 + len("run_manifest.") + len(".json") == 255."""
    longest = "a" * 237
    assert len(run_manifest_filename(longest)) == 255


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
        "-leading-dash",
        "has space",
        "has\x00null",
        "a" * 238,
    ],
)
def test_run_manifest_filename_rejects_an_unsafe_id(bad):
    """The id becomes a path component, so anything unsafe raises rather than escaping."""
    with pytest.raises(ValueError):
        run_manifest_filename(bad)


def test_run_manifest_filename_rejects_a_non_string_id():
    """A non-str id is a programming error, surfaced as ValueError not TypeError."""
    with pytest.raises(ValueError):
        run_manifest_filename(12345)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k run_manifest_filename -v`
Expected: FAIL — `ImportError: cannot import name 'run_manifest_filename'`

- [ ] **Step 3: Write the implementation**

Add `import re` to the module imports, then after `RUN_MANIFEST_FILENAME`:

```python
# The per-run filename's fixed parts. `RUN_MANIFEST_FILENAME` stays the legacy/local name; the
# two forms can never collide, because a valid run id is non-empty and may not begin with a dot.
_FILENAME_PREFIX = "run_manifest."
_FILENAME_SUFFIX = ".json"

# A run id becomes a path component and arrives from an environment variable, so it is validated
# against an allowlist rather than by blocking known-bad characters. An Argo workflow name is an
# RFC-1123 label (lowercase alphanumerics and '-'); bloomctl's non-Argo placeholder is
# `local-<hex8>`. Requiring an alphanumeric first character is what rejects "." and ".." and a
# leading dash without special-casing any of them.
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# 255 is NAME_MAX on the Linux filesystems this runs on; the wrapper costs 18 characters. This is
# below Kubernetes' own 253-character object-name limit, so a maximally long workflow name is
# rejected rather than silently truncated — Argo's generateName emits about 26, so the gap is
# theoretical, and a loud ValueError beats an unwritable filename.
_RUN_ID_MAX_LENGTH = 255 - len(_FILENAME_PREFIX) - len(_FILENAME_SUFFIX)


def run_manifest_filename(pipeline_run_id: str) -> str:
    """Return the per-run manifest filename for ``pipeline_run_id``.

    Args:
        pipeline_run_id: The run identity, e.g. an Argo ``{{workflow.name}}``.

    Returns:
        ``"run_manifest.<pipeline_run_id>.json"``.

    Raises:
        ValueError: If ``pipeline_run_id`` is not usable as a single path component — not a
            string, empty, over ``_RUN_ID_MAX_LENGTH`` characters, or not matching the
            module's run-id pattern (it must start with a letter or digit and contain only
            letters, digits, ``.``, ``_`` and ``-``). Raised rather than sanitized: a silently
            rewritten id would name a file no other stage in the run would look for.
    """
    if not isinstance(pipeline_run_id, str):
        raise ValueError(
            f"pipeline_run_id must be a str, got {type(pipeline_run_id).__name__}"
        )
    if len(pipeline_run_id) > _RUN_ID_MAX_LENGTH:
        raise ValueError(
            f"pipeline_run_id is {len(pipeline_run_id)} characters, over the "
            f"{_RUN_ID_MAX_LENGTH} limit that keeps the filename within NAME_MAX"
        )
    if not _RUN_ID_PATTERN.fullmatch(pipeline_run_id):
        raise ValueError(
            f"pipeline_run_id {pipeline_run_id!r} is not usable as a filename component: "
            "it must start with a letter or digit and contain only letters, digits, "
            "'.', '_' and '-'"
        )
    return f"{_FILENAME_PREFIX}{pipeline_run_id}{_FILENAME_SUFFIX}"
```

Note the docstring describes the rule in words and does **not** re-quote the character class —
the spec and `_RUN_ID_PATTERN` are the two places the literal lives.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_manifest.py -k run_manifest_filename -v`
Expected: PASS (17 tests — 4 explicit + 12 parametrized, plus the pre-existing
`test_run_manifest_filename_literal_value`, which this selector also matches)

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add run_manifest_filename with path-component validation"
```

---

### Task 3: `pipeline_run_id_from_env` and `run_manifest_name_for_writing`

**Files:** modify `src/sleap_roots_contracts/run_manifest.py`; test `tests/test_run_manifest.py`.

**Interfaces:**
- Consumes: `run_manifest_filename` (Task 2), `RUN_MANIFEST_FILENAME`.
- Produces: `PIPELINE_RUN_ID_ENV_VAR`, `pipeline_run_id_from_env(env=None) -> str | None`, and
  `run_manifest_name_for_writing(pipeline_run_id: str | None) -> str`.

These ship together because the writer rule is meaningless without the env reader, and pairing
them is what stops bloomctl keeping a parallel env read (design §3.2).

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


def test_env_var_name_is_exported():
    """Consumers must not hardcode the variable name (bloomctl currently does)."""
    assert PIPELINE_RUN_ID_ENV_VAR == "ARGO_WORKFLOW_NAME"


def test_name_for_writing_is_per_run_when_the_id_is_known():
    """A writer under orchestration names the file for its own run."""
    assert run_manifest_name_for_writing("wf1") == "run_manifest.wf1.json"


def test_name_for_writing_is_the_legacy_name_without_an_id():
    """No run identity means the legacy name, which keeps local runs behaving as before."""
    assert run_manifest_name_for_writing(None) == RUN_MANIFEST_FILENAME


def test_name_for_writing_rejects_an_invalid_id():
    """An unsafe id fails at the writer too, not only at the reader."""
    with pytest.raises(ValueError):
        run_manifest_name_for_writing("../escape")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k "from_env or name_for_writing or env_var_name" -v`
Expected: FAIL — `ImportError: cannot import name 'pipeline_run_id_from_env'`

- [ ] **Step 3: Write the implementation**

Add `import os` and `from collections.abc import Mapping` to the module imports.

```python
#: The environment variable every pipeline stage reads its run identity from. Set to Argo's
#: `{{workflow.name}}` on the four stage templates that touch the manifest — images-downloader,
#: predictor, trait-extractor and write-back — and deliberately absent from the `local-WSL2-*`
#: templates, which is what keeps local runs on the legacy filename. The fifth cluster template,
#: exit-gate, does not set it and does not read the manifest. Exported so consumers import it
#: rather than hardcoding the string.
PIPELINE_RUN_ID_ENV_VAR = "ARGO_WORKFLOW_NAME"


def pipeline_run_id_from_env(env: Mapping[str, str] | None = None) -> str | None:
    """Return this process's run identity, or ``None`` when it has none.

    The single definition of "which run am I". Both writers and readers must use it: a writer
    that reads the variable itself can disagree with a reader about whitespace or blankness,
    and :func:`check_run_manifest_identity` would then fail on every stage.

    Args:
        env: Environment mapping to read. Defaults to ``os.environ``. Injectable so callers and
            tests need no monkeypatching.

    Returns:
        The stripped value of ``ARGO_WORKFLOW_NAME``, or ``None`` when unset or blank. ``None``
        means "not running under orchestration"; it is not an error.
    """
    source = os.environ if env is None else env
    value = source.get(PIPELINE_RUN_ID_ENV_VAR)
    if value is None:
        return None
    return value.strip() or None


def run_manifest_name_for_writing(pipeline_run_id: str | None) -> str:
    """Return the filename a writer should publish its manifest under.

    Args:
        pipeline_run_id: This run's identity, from :func:`pipeline_run_id_from_env`.

    Returns:
        The per-run filename when an identity is known, else ``RUN_MANIFEST_FILENAME``. Keying
        per-run naming to the presence of an identity is what leaves local and ``local-WSL2-*``
        runs on exactly their previous behavior, with no template changes.

    Raises:
        ValueError: If ``pipeline_run_id`` is not usable as a filename component.
    """
    if pipeline_run_id is None:
        return RUN_MANIFEST_FILENAME
    return run_manifest_filename(pipeline_run_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_manifest.py -k "from_env or name_for_writing or env_var_name" -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add the env reader and the writer-side naming rule"
```

---

### Task 4: `read_run_manifest` and `RunManifestMissingError`

**Files:** modify `src/sleap_roots_contracts/run_manifest.py`; test `tests/test_run_manifest.py`.

**Interfaces:**
- Consumes: `run_manifest_filename` (Task 2), `RUN_MANIFEST_FILENAME`.
- Produces: `RunManifestError(Exception)`, `RunManifestMissingError(RunManifestError, LookupError)`,
  `RunManifestRead(NamedTuple)` with fields `filename: str`, `data: bytes`, `mode: int`,
  `is_per_run: bool`; and
  `read_run_manifest(directory, pipeline_run_id, *, allow_legacy) -> RunManifestRead | None`.
  This is the function all four consumer call sites use.

This is the task that carries the change's safety property. Read design §2.2 and §2.9 first —
especially §2.9's asymmetry, which is the single easiest thing to get wrong here.

- [ ] **Step 1: Write the failing tests**

```python
def test_read_prefers_the_per_run_manifest(tmp_path):
    """With both present, the run's own manifest wins."""
    (tmp_path / "run_manifest.wf1.json").write_bytes(b'{"per_run": true}')
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')
    result = read_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert result.filename == "run_manifest.wf1.json"
    assert result.data == b'{"per_run": true}'
    assert result.is_per_run is True


def test_read_falls_back_to_the_legacy_manifest(tmp_path):
    """Mid-rollout, a new reader still finds an old writer's file."""
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')
    result = read_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert result.filename == RUN_MANIFEST_FILENAME
    assert result.is_per_run is False


def test_read_refuses_the_legacy_manifest_when_the_fallback_is_off(tmp_path):
    """Post-migration, a stale legacy file must not silently re-scope an identified run."""
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')
    with pytest.raises(RunManifestMissingError):
        read_run_manifest(tmp_path, "wf1", allow_legacy=False)


def test_read_still_uses_the_legacy_name_without_an_identity_when_the_fallback_is_off(tmp_path):
    """allow_legacy governs identified runs only — it must not unscope local ones.

    With no run identity, RUN_MANIFEST_FILENAME is not a fallback: per design §2.3 it is the
    correct and only name. Gating it on allow_legacy would make the fleet-wide flip in design
    §4 step 6 silently regress every local-WSL2 run from scoped to unscoped.
    """
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')
    result = read_run_manifest(tmp_path, None, allow_legacy=False)
    assert result.filename == RUN_MANIFEST_FILENAME
    assert result.is_per_run is False


def test_read_returns_none_without_an_identity_when_nothing_is_present_and_fallback_is_off(
    tmp_path,
):
    """The degenerate call still has one candidate, and its absence is not an error."""
    assert read_run_manifest(tmp_path, None, allow_legacy=False) is None


def test_read_rejects_a_blank_run_id(tmp_path):
    """A blank-but-not-None id is invalid, not 'no identity' — it must not silently
    become the legacy path."""
    with pytest.raises(ValueError):
        read_run_manifest(tmp_path, "", allow_legacy=True)


def test_read_reports_a_missing_directory_as_such(tmp_path):
    """ENOENT on the directory is also FileNotFoundError, so say which is missing.

    Without this, a mis-mounted stage-in — the likelier cause under Argo — reports as a
    missing manifest and sends the reader hunting the wrong problem.
    """
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError) as excinfo:
        read_run_manifest(missing, "wf1", allow_legacy=True)
    assert "nope" in str(excinfo.value)


def test_read_returns_the_source_file_mode(tmp_path):
    """predict forwards the manifest and must reproduce its mode without a second stat."""
    target = tmp_path / RUN_MANIFEST_FILENAME
    target.write_bytes(b"{}")
    result = read_run_manifest(tmp_path, None, allow_legacy=True)
    assert result.mode == (target.stat().st_mode & 0o777)


def test_read_raises_when_the_run_id_is_known_and_nothing_is_present(tmp_path):
    """Under orchestration a missing manifest is a fault, never 'scope to everything'."""
    with pytest.raises(RunManifestMissingError) as excinfo:
        read_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert "run_manifest.wf1.json" in str(excinfo.value)


def test_read_returns_none_when_there_is_no_run_id_and_nothing_is_present(tmp_path):
    """Locally, an absent manifest keeps today's unscoped behavior."""
    assert read_run_manifest(tmp_path, None, allow_legacy=True) is None


def test_read_ignores_a_per_run_manifest_when_the_run_id_is_unknown(tmp_path):
    """A caller with no identity must not adopt some other run's scope."""
    (tmp_path / "run_manifest.wf1.json").write_bytes(b'{"per_run": true}')
    assert read_run_manifest(tmp_path, None, allow_legacy=True) is None


def test_read_propagates_an_invalid_run_id(tmp_path):
    """An unsafe id is a programming error, surfaced as ValueError not 'missing'."""
    with pytest.raises(ValueError):
        read_run_manifest(tmp_path, "../escape", allow_legacy=True)


def test_read_propagates_a_permission_error_rather_than_advancing(tmp_path, monkeypatch):
    """An unreadable manifest must never be mistaken for an absent one.

    This is the reason the function opens rather than probing: a boolean predicate collapses
    EACCES into "absent", which would fall through to a stale legacy manifest. bloomctl's
    ingest.py avoids .is_file() for exactly this reason.
    """
    target = tmp_path / "run_manifest.wf1.json"
    target.write_bytes(b"{}")
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')

    real_open = Path.open

    def deny(self, *args, **kwargs):
        if self.name == "run_manifest.wf1.json":
            raise PermissionError(13, "Permission denied")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny)
    with pytest.raises(PermissionError):
        read_run_manifest(tmp_path, "wf1", allow_legacy=True)


def test_read_accepts_a_string_directory(tmp_path):
    """Consumers pass str paths in places; accept them like the rest of the library."""
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b"{}")
    assert read_run_manifest(str(tmp_path), None, allow_legacy=True).data == b"{}"
```

Add `from pathlib import Path` to the test imports.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k test_read -v`
Expected: FAIL — `ImportError: cannot import name 'read_run_manifest'`

- [ ] **Step 3: Write the implementation**

Add `from pathlib import Path` and `from typing import NamedTuple` to the module imports.

```python
class RunManifestError(Exception):
    """Base for every run-manifest failure this module raises.

    Deliberately not a ``ValueError``. Pydantic's ``ValidationError`` is one, and consumers
    already wrap manifest parsing in ``except ValueError`` — inheriting from it would let a
    generic parse handler swallow "this tree is not the one you think it is".
    """


class RunManifestMissingError(RunManifestError, LookupError):
    """No run manifest was found for a caller that knows which run it is.

    Also a ``LookupError`` so a consumer can catch it alongside its own not-found handling
    while still re-raising it as that repo's own error type (``click.ClickException`` in
    bloomctl, for instance).
    """


class RunManifestRead(NamedTuple):
    """One manifest read: where it came from, its bytes, its mode, and which convention.

    Consumers SHOULD use attribute access rather than tuple unpacking, so that fields can be
    appended without breaking them.

    Attributes:
        filename: The name actually read, so a forwarding stage can republish under it.
        data: The raw bytes, returned rather than a path so there is no window in which the
            file changes between being found and being read.
        mode: The source file's permission bits, taken by ``fstat`` on the descriptor already
            open — so it describes the bytes returned, not whatever is at that path later. A
            forwarding stage needs it: ``mkstemp`` creates at ``0600``, and the next container
            runs as a different uid on the same shared mount.
        is_per_run: Whether ``filename`` is the per-run form. Consumers use it to decide
            whether the identity cross-check applies, instead of each comparing against
            ``RUN_MANIFEST_FILENAME`` themselves.
    """

    filename: str
    data: bytes
    mode: int
    is_per_run: bool


def read_run_manifest(
    directory: str | Path,
    pipeline_run_id: str | None,
    *,
    allow_legacy: bool,
) -> RunManifestRead | None:
    """Read the run manifest this caller should use, if there is one.

    Candidate order depends on whether a run identity exists:

    * With one — the per-run filename, then ``RUN_MANIFEST_FILENAME`` if ``allow_legacy``.
    * Without one — ``RUN_MANIFEST_FILENAME`` alone, **regardless of** ``allow_legacy``,
      because with no identity that name is not a legacy fallback but the correct name
      (design §2.3). Gating it would silently unscope every local run when the fleet flips.

    Each candidate is *opened*, not probed: only ``FileNotFoundError`` advances to the next
    one, so an unreadable manifest raises instead of being mistaken for an absent one and
    falling through to an older run's scope.

    Args:
        directory: Directory to look in. Not searched recursively. Its own absence raises
            ``FileNotFoundError`` naming the directory, rather than being reported as a
            missing manifest — under Argo a mis-mounted stage-in is the likelier cause.
        pipeline_run_id: This run's identity, or ``None`` (see
            :func:`pipeline_run_id_from_env`). A blank string is **not** ``None``: it is an
            invalid id and raises ``ValueError``.
        allow_legacy: Whether a caller that *knows its own identity* may accept a manifest
            written under the identity-less name. Required and keyword-only, with no default,
            so every call site states its position and the fleet's migration state is
            greppable. Pass ``True`` while any stage may still be writing the legacy name;
            pass ``False`` once the fleet is migrated and the stale files are deleted, which
            is what makes the missing-manifest error reachable at all. Ignored when
            ``pipeline_run_id`` is ``None``.

    Returns:
        A :class:`RunManifestRead`, or ``None`` when nothing was found and
        ``pipeline_run_id`` is ``None``.

    Raises:
        RunManifestMissingError: If ``pipeline_run_id`` is not ``None`` and no candidate was
            found. Deliberately not ``None``: every consumer treats an absent manifest as
            "discover everything here", which under a shared output tree means processing and
            ingesting other runs' scans. A stage that knows its run id is running under
            orchestration, where a manifest is always written, so its absence is a fault.
        ValueError: If ``pipeline_run_id`` is not usable as a filename component.
        OSError: Any failure other than the candidate being absent — notably
            ``PermissionError``.
    """
    base = Path(directory)

    candidates: list[tuple[str, bool]] = []
    if pipeline_run_id is None:
        # No identity: the legacy name is the right name, not a fallback, so `allow_legacy`
        # has no say. Gating it here would unscope every non-Argo run at design §4 step 6.
        candidates.append((RUN_MANIFEST_FILENAME, False))
    else:
        candidates.append((run_manifest_filename(pipeline_run_id), True))
        if allow_legacy:
            candidates.append((RUN_MANIFEST_FILENAME, False))

    for name, is_per_run in candidates:
        try:
            with (base / name).open("rb") as handle:
                data = handle.read()
                mode = os.fstat(handle.fileno()).st_mode & 0o777
        except FileNotFoundError:
            # Distinguish "this candidate is absent" from "the directory is not there" —
            # both are FileNotFoundError, and only the first should advance.
            if not base.is_dir():
                raise FileNotFoundError(
                    f"run manifest directory does not exist: {base.as_posix()}"
                ) from None
            continue
        return RunManifestRead(
            filename=name, data=data, mode=mode, is_per_run=is_per_run
        )

    if pipeline_run_id is not None:
        looked_for = ", ".join(repr(name) for name, _ in candidates)
        raise RunManifestMissingError(
            f"no run manifest for run {pipeline_run_id!r} in {base.as_posix()}: "
            f"looked for {looked_for}"
        )
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_manifest.py -k test_read -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add read_run_manifest with an explicit legacy fallback"
```

---

### Task 5: `check_run_manifest_identity` and package exports

**Files:** modify `src/sleap_roots_contracts/run_manifest.py` and
`src/sleap_roots_contracts/__init__.py`; test `tests/test_run_manifest.py`.

**Interfaces:**
- Consumes: `RunManifest` (existing), `RUN_MANIFEST_FILENAME`.
- Produces: `RunManifestError(Exception)` (Task 4), `RunManifestIdentityError(RunManifestError)` and
  `check_run_manifest_identity(manifest, pipeline_run_id, filename) -> None`. Plus all nine new
  names re-exported from the package root.

- [ ] **Step 1: Write the failing tests**

```python
def test_identity_check_passes_for_the_owning_run():
    """The ordinary case: the file this run wrote names this run."""
    manifest = make_manifest(pipeline_run_id="wf1")
    assert check_run_manifest_identity(manifest, "wf1", "run_manifest.wf1.json") is None


def test_identity_check_rejects_a_foreign_manifest():
    """A per-run-named file naming a different run means the tree is not what we think."""
    manifest = make_manifest(pipeline_run_id="wf2")
    with pytest.raises(RunManifestIdentityError) as excinfo:
        check_run_manifest_identity(manifest, "wf1", "run_manifest.wf1.json")
    message = str(excinfo.value)
    assert "wf1" in message
    assert "wf2" in message
    assert "run_manifest.wf1.json" in message


def test_identity_check_is_a_noop_for_the_legacy_filename():
    """The legacy name carries no identity, so a mismatch there is expected, not an error.

    Without this, all four call sites would write the same
    `if filename != RUN_MANIFEST_FILENAME` guard themselves.
    """
    manifest = make_manifest(pipeline_run_id="some-older-run")
    assert check_run_manifest_identity(manifest, "wf1", RUN_MANIFEST_FILENAME) is None


def test_identity_error_is_not_swallowed_by_a_generic_parse_handler():
    """An identity mismatch must survive `except ValueError` around manifest parsing.

    pydantic's ValidationError IS a ValueError, and consumers wrap parsing in handlers that
    catch it. If RunManifestIdentityError were also a ValueError, "this tree is not the one
    you think it is" would be swallowed as though it were a malformed file.
    """
    assert not issubclass(RunManifestIdentityError, ValueError)


def test_both_errors_share_one_catchable_base():
    """Consumers can catch RunManifestError alone and re-raise as their own type."""
    assert issubclass(RunManifestIdentityError, RunManifestError)
    assert issubclass(RunManifestMissingError, RunManifestError)
    assert issubclass(RunManifestMissingError, LookupError)


def test_new_names_are_exported_from_the_package_root():
    """Every new name is importable from the package root and listed in __all__."""
    import sleap_roots_contracts as pkg

    for name in (
        "PIPELINE_RUN_ID_ENV_VAR",
        "RunManifestError",
        "RunManifestIdentityError",
        "RunManifestMissingError",
        "RunManifestRead",
        "check_run_manifest_identity",
        "pipeline_run_id_from_env",
        "read_run_manifest",
        "run_manifest_filename",
        "run_manifest_name_for_writing",
    ):
        assert hasattr(pkg, name), name
        assert name in pkg.__all__, name


def test_legacy_filename_constant_is_unchanged():
    """This release is additive — the existing constant keeps its exact value."""
    assert RUN_MANIFEST_FILENAME == "run_manifest.json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_manifest.py -k "identity or exported or legacy_filename or catchable_base" -v`
Expected: FAIL — `ImportError: cannot import name 'check_run_manifest_identity'`

- [ ] **Step 3: Write the implementation**

In `run_manifest.py`:

```python
class RunManifestIdentityError(RunManifestError):
    """A manifest read under a per-run filename names a different run.

    Deliberately **not** a ``ValueError``, unlike a parse failure. A malformed manifest and a
    manifest belonging to someone else are different problems with different responses, and
    consumers wrap parsing in handlers that catch ``ValueError`` (pydantic's
    ``ValidationError`` is one). Sharing that base would let a generic parse handler swallow
    the stronger signal.
    """


def check_run_manifest_identity(
    manifest: RunManifest,
    pipeline_run_id: str,
    filename: str,
) -> None:
    """Verify a per-run-named manifest names the run that is reading it.

    A no-op when ``filename`` is ``RUN_MANIFEST_FILENAME``: the legacy name carries no run
    identity, and before per-run naming the producer overwrote ``pipeline_run_id`` on every
    merge, so a legacy file routinely names some earlier run. Callers may therefore pass
    whatever :func:`read_run_manifest` returned without testing the name themselves.

    For a per-run-named file this is the cross-check bloom#703 asked for, possible for the
    first time.

    Args:
        manifest: The parsed manifest.
        pipeline_run_id: The reader's own run identity.
        filename: The name it was read from.

    Returns:
        None.

    Raises:
        RunManifestIdentityError: If a per-run-named manifest names a different run.
    """
    if filename == RUN_MANIFEST_FILENAME:
        return
    if manifest.pipeline_run_id != pipeline_run_id:
        raise RunManifestIdentityError(
            f"{filename} was read as run {pipeline_run_id!r}'s manifest but names run "
            f"{manifest.pipeline_run_id!r}"
        )
```

In `__init__.py`, extend the run_manifest import and `__all__` with all **ten** names:
`PIPELINE_RUN_ID_ENV_VAR`, `RunManifestError`, `RunManifestIdentityError`,
`RunManifestMissingError`, `RunManifestRead`, `check_run_manifest_identity`,
`pipeline_run_id_from_env`, `read_run_manifest`, `run_manifest_filename`,
`run_manifest_name_for_writing`. Missing `RunManifestError` here leaves this task's own
export test red.

- [ ] **Step 4: Run the full suite plus linters**

Run: `uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
Expected: all pass. Baseline was 460; expect 506 — 46 new (16 + 9 + 14 + 7), since the 17th
in Task 2's gate is a pre-existing test that selector also matches.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py src/sleap_roots_contracts/__init__.py tests/test_run_manifest.py
git commit -m "feat(run-manifest): add the identity cross-check and export the new names"
```

---

### Task 6: Module docstring and CHANGELOG

**Files:** modify `src/sleap_roots_contracts/run_manifest.py` (module docstring only);
`docs/CHANGELOG.md`.

- [ ] **Step 1: Extend the module docstring**

Append to the existing module docstring:

```
Since 0.1.0a9 the manifest may also be named per run — ``run_manifest.<pipeline_run_id>.json``,
built by :func:`run_manifest_filename` — so runs sharing an output directory no longer share a
manifest. ``RUN_MANIFEST_FILENAME`` remains the name used when a stage has no run identity (no
``ARGO_WORKFLOW_NAME``), which keeps local and ``local-WSL2-*`` runs on their previous
behavior. :func:`read_run_manifest` is the single definition of how a reader chooses between
the two, what a missing manifest means, and when the legacy name is still acceptable; see
talmolab/sleap-roots-pipeline#71.
```

- [ ] **Step 2: Add the CHANGELOG entry**

Under `## [Unreleased]` in `docs/CHANGELOG.md`:

```markdown
### Added
- Per-run run-manifest naming and resolution: `run_manifest_filename`,
  `pipeline_run_id_from_env`, `run_manifest_name_for_writing`, `read_run_manifest`,
  `check_run_manifest_identity`, `RunManifestRead`, `PIPELINE_RUN_ID_ENV_VAR`, and the
  `RunManifestError` / `RunManifestMissingError` / `RunManifestIdentityError` exceptions
  (talmolab/sleap-roots-pipeline#71). Additive — `RunManifest` and `RUN_MANIFEST_FILENAME` are
  unchanged, so 0.1.0a8 consumers are unaffected until they adopt the new names.
```

- [ ] **Step 3: Run the checks**

Run: `uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add src/sleap_roots_contracts/run_manifest.py docs/CHANGELOG.md
git commit -m "docs(run-manifest): document per-run naming in the module and CHANGELOG"
```

---

### Task 7: Correct two false claims in `project.md`, and update `README.md`

**Files:** modify `openspec/project.md`, `README.md`,
`openspec/changes/add-per-run-manifest-filename/tasks.md`.

Both `project.md` claims below were verified false during review. They are independent of this
change but sit in the paragraphs it edits, so leaving them would be the worst option.

- [ ] **Step 1: Fix the I/O claim in `openspec/project.md`**

It currently says the library is "code-agnostic toward Bloom (no Bloom import, no DB/network/
filesystem I/O)". That is false: `schema.py:93-98`'s `emit_schema()` writes files,
`_default_schema_dir()` (`schema.py:19-23`) falls back to `Path.cwd()`, `registry.py:25-27` reads
the packaged YAML, and `examples/__init__.py:70` returns filesystem paths. Replace the
parenthetical with:

```
(no Bloom import; no DB or network I/O, and no ambient filesystem reads in the contract-model
surface — the exceptions are deliberate and named: `emit_schema` writes the JSON Schema
artifacts, `registry`/`examples` read packaged resources, and `read_run_manifest` reads one
named file from a caller-supplied directory)
```

- [ ] **Step 2: Fix the stale consumer claim in `openspec/project.md`**

Around lines 99-101 it says predict/traits "will read it to scope processing to exactly the
`scan_key`s a run was given, once their consuming PRs land (not yet, as of this release — see
talmolab/sleap-roots-pipeline#37)". They have read it since 0.1.0a7:
`sleap-roots/trait_extractor/extractor.py:194` calls `load_run_manifest`, and
`sleap-roots-predict/sleap_roots_predict/batch.py:131-139` parses `RunManifest`. Replace with:

```
`sleap-roots-predict`/`sleap-roots-traits` read it to scope processing to exactly the
`scan_key`s a run was given (landed; see talmolab/sleap-roots-pipeline#37)
```

- [ ] **Step 3: Describe the new API in `project.md` and `README.md`**

Append one sentence to the run-manifest paragraph in both (`README.md` ~lines 53-57,
`project.md` ~lines 17-19):

```
Since `0.1.0a9` it also defines the per-run filename convention and the shared resolution
policy — `run_manifest_filename`, `pipeline_run_id_from_env`, `run_manifest_name_for_writing`,
`read_run_manifest`, `check_run_manifest_identity` — so the four consumer call sites agree on
one definition rather than three (talmolab/sleap-roots-pipeline#71).
```

- [ ] **Step 4: Tick the OpenSpec tasks**

Mark Tasks 2-7 `- [x]` in `openspec/changes/add-per-run-manifest-filename/tasks.md`.

- [ ] **Step 5: Run every check**

Run: `openspec validate add-per-run-manifest-filename --strict && uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add openspec/project.md README.md openspec/changes/add-per-run-manifest-filename/tasks.md
git commit -m "docs: correct two false claims in project.md and describe the new API"
```

---

### Task 8: PR, then the version bump

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin add-per-run-manifest-filename
```

Use `/pr-description`. Reference change-id `add-per-run-manifest-filename` and
talmolab/sleap-roots-pipeline#71. The body must state:

- This is **additive**; no consumer is affected until it bumps its pin. The claim rests on the
  pre-existing suite staying green plus `test_legacy_filename_constant_is_unchanged` — there is
  no dedicated cross-version regression test, and the PR should say so rather than imply one.
- **Rollback:** if 0.1.0a9 is broken, consumers stay pinned to `==0.1.0a8`; nothing in a9 is
  required until a consumer opts in. A PyPI yank is available if the release must be withdrawn.
- The two `project.md` corrections are pre-existing defects fixed in passing, not caused here.

- [ ] **Step 2: Run `/review-pr` before merging**

- [ ] **Step 3: After merge, trigger the version bump to `0.1.0a9`**

`.github/workflows/version.yml` is `workflow_dispatch`: use `bump_type: alpha`, or
`custom_version: 0.1.0a9`. It bumps `pyproject.toml` via `uv version` and opens its own PR where
CHANGELOG finalization lands.

- [ ] **Step 4: Confirm the release is installable before any consumer work starts**

Run: `uv run --with "sleap-roots-contracts==0.1.0a9" --no-project python -c "from sleap_roots_contracts import read_run_manifest, run_manifest_name_for_writing; print('ok')"`
Expected: prints `ok`.

This is the gate for plan 3 — no consumer pin moves until this succeeds against the published
package, not a local checkout.

---

## Self-Review

**Review coverage.** B1 → Task 4's required `allow_legacy` + its two dedicated tests. B2 → design
doc §2.5, corrected at `ab90185`; no code change needed. B3 → Task 7 Step 5 restores the full
gate. B4 → Task 7 Steps 1-3. I1 → Task 4's open-don't-probe implementation and
`test_read_propagates_a_permission_error_rather_than_advancing`. I2 → Task 3 ships the env reader
and writer rule together, and design §3.2 records the bloomctl obligation. I3a → `is_per_run` plus
the legacy no-op. I3b → `run_manifest_name_for_writing`. I3c → `PIPELINE_RUN_ID_ENV_VAR` exported
and asserted. I4 → cap is now 237, derived rather than literal. Lens 1's MODIFIED-requirement
point → Task 1R. Lens 2's boundary and non-str gaps → Task 2. Lens 5's rollback point → Task 8.

**Placeholders.** None — every code step carries real code, every test step real assertions.

**Type consistency.** `run_manifest_filename(str) -> str` is called by
`run_manifest_name_for_writing` (Task 3) and `read_run_manifest` (Task 4) exactly as defined in
Task 2. `pipeline_run_id_from_env() -> str | None` feeds both of those, whose parameter is
`str | None`. `read_run_manifest` returns `RunManifestRead | None`; `check_run_manifest_identity`
takes that read's `.filename`. Exception names match across Tasks 4, 5 and the delta.

**Re-review coverage (revision 3).** N1 (`allow_legacy` unscoping identity-less readers) → Task 4's
asymmetric candidate list plus the "still uses the legacy name without an identity" test. N2
(missing mode) → `RunManifestRead.mode` via `fstat` on the already-open descriptor. N3 ("all five
cluster templates" — false; exit-gate does not set it) → the `PIPELINE_RUN_ID_ENV_VAR` docstring in
Task 3. N4 (a missing directory reported as a missing manifest) → the `base.is_dir()` branch and its
test. N5 (a test docstring that read as sanction for keying on the local placeholder) → reworded in
Task 2. N6 (exception taxonomy) → `RunManifestError` base; the identity error is no longer a
`ValueError`. N7 (dead `IsADirectoryError` branch) → removed. The broken `-k read_run_manifest`
selector, which collected zero tests → `-k test_read`. Lens 1's IMPORTANT-1 (blank id through the
reader) and SUGGESTION-1 (the zero-candidate call) → two new Task 4 tests.

**Known residuals, recorded rather than fixed.**
- A per-run file created between the two candidate opens still leaves the reader on the legacy
  file. That window shuts for good at design §4 step 6, when `allow_legacy` goes to `False`.
- The new "New Names Are Exported From The Package Root" requirement and the existing untouched
  "Package Export" requirement now both govern package-root exports. Not a contradiction; fold
  them together the next time this capability is modified.
- The MODIFIED requirement's second scenario duplicates one in "The Writer's Filename Rule". That
  is deliberate — it anchors the cross-reference and satisfies the one-scenario minimum — and is
  noted here so a later scenario-count audit does not read it as an accident.
- `bloomctl` still owns the two-value rule (filename identity `None` locally, body value
  `local-<hex8>`); the API has no helper for the body value, so that rule lives in design §3.2
  prose and must be carried into plan 3's bloomctl task.

---

# Revision 4 — `/review-pr` findings (PR #38)

Five adversarial lenses on the open PR found two correctness bugs and three structural gaps. No
consumer has adopted the API, so these are fixed here rather than filed. **OpenSpec order applies:
Task 9 amends the spec delta first; Tasks 10-11 are TDD against it; Task 12 is docs.**

## Designs (decided — do not re-derive)

**D1 — a dangling symlink must not advance.** `open()` on a dangling symlink raises
`FileNotFoundError(ENOENT)` (verified on Linux), so the current loop treats it as "absent" and
falls through to the legacy manifest — a silent foreign scope, exactly what open-don't-probe
exists to prevent. The rule must test the *condition*, not the exception type:

```python
        except FileNotFoundError as exc:
            if not base.is_dir():
                raise FileNotFoundError(
                    errno.ENOENT, "run manifest directory does not exist", str(base)
                ) from exc
            if (base / name).is_symlink():
                # is_symlink() uses lstat, so it is True for a DANGLING link. The link exists;
                # its target does not. That is a broken tree, not an absent candidate, and
                # advancing would hand this run an older run's scope.
                raise FileNotFoundError(
                    errno.ENOENT,
                    "run manifest is a symlink with a missing target",
                    str(base / name),
                ) from exc
            continue
```

**D2 — `None` identity with a per-run read is a caller error, not a foreign manifest.**
`check_run_manifest_identity` currently raises `RunManifestIdentityError` ("read as run None's
manifest"), which tells consumers to escalate a tree problem. The combination is impossible from
`read_run_manifest`, so it is a programming error:

```python
    if pipeline_run_id is None:
        if read.is_per_run:
            raise ValueError(
                "a caller with no run identity cannot have read a per-run manifest; "
                f"{read.filename!r} was reported as per-run"
            )
        return
    if not read.is_per_run:
        return
    if manifest.pipeline_run_id != pipeline_run_id:
        raise RunManifestIdentityError(...)   # unchanged message
```

**D3 — a composed entry point, so the safe sequence is the short one.** Three primitives that
four repos must compose in order, where omitting the third is silent, is the divergence this
module exists to prevent.

```python
class LoadedRunManifest(NamedTuple):
    manifest: RunManifest
    read: RunManifestRead


def load_run_manifest(directory, pipeline_run_id, *, allow_legacy) -> LoadedRunManifest | None:
    """read -> parse -> cross-check, in that order. Returns None only when there is no
    manifest and no run identity. Forwarding stages get `.read.data`/`.read.mode`/
    `.read.filename`; scope-only readers use `.manifest`."""
```

The primitives stay exported as the escape hatch. Export count goes 12 -> 14.

**D4 — `RunManifestRead.filename` is pinned as a bare filename.** Documented as such, and the
test that blesses an absolute path is changed to assert that shape is *rejected* rather than
supported.

## Task 9 — amend the spec delta (docs only, no code)

- [ ] **Manifest Resolution And Reading**: state that only a candidate that is genuinely absent
      advances; a path that exists as a dangling symlink SHALL raise. Add a scenario.
- [ ] **Run Identity Cross-Check**: state the `None`-identity rule — no-op for a non-per-run
      read, `ValueError` for a per-run read. Add two scenarios.
- [ ] **NEW requirement: Composed Load** — `load_run_manifest` and `LoadedRunManifest`, the
      order it performs, and that it is the recommended entry point. At least three scenarios.
- [ ] **MODIFIED Package Export**: fourteen names.
- [ ] Note in **Manifest Resolution And Reading** that `RunManifestRead.filename` is always a
      bare filename.
- [ ] Update `proposal.md`'s What Changes and Impact.
- [ ] `openspec validate add-per-run-manifest-filename --strict`, commit.

## Task 10 — TDD: resolution hardening (D1, D2)

- [ ] Failing tests first: a dangling symlink at the per-run name with a readable legacy file
      present raises rather than returning the legacy one (**skip on Windows** —
      `os.symlink` needs privilege there; CI is ubuntu); `None` + a per-run read raises
      `ValueError`, not `RunManifestIdentityError`; `None` + a non-per-run read is still a no-op.
- [ ] Confirm red, implement D1 and D2, confirm green.
- [ ] Full suite + black + ruff. Commit.

## Task 11 — TDD: the composed entry point (D3)

- [ ] Failing tests first: happy path returns manifest and read; a foreign per-run manifest
      raises `RunManifestIdentityError` *through* the composed call; no manifest and no identity
      returns `None`; no manifest with an identity raises `RunManifestMissingError`; a malformed
      manifest raises pydantic's `ValidationError`; the legacy path skips the cross-check.
- [ ] Confirm red, implement, confirm green. Export both new names.
- [ ] Full suite + black + ruff. Commit.

## Task 12 — docs and test-quality (no behavior change)

- [ ] `run_manifest.py:29-30` — the comment calling `RUN_MANIFEST_FILENAME` the "Single source of
      truth for the manifest's on-disk filename" is false by this change's own spec delta.
      Reword as the delta's requirement was reworded.
- [ ] `run_manifest.py:33` — drop the "may not begin with a dot" half of the collision argument;
      only non-emptiness matters.
- [ ] **Reader-before-writer ordering is normative and currently lives only in another repo's
      design doc.** Add it to the module docstring and `README.md`: adopting the writer first
      makes un-adopted readers find no legacy manifest and fall back to whole-tree discovery,
      which is worse than the defect being fixed.
- [ ] Document that a maximum-length run id leaves no headroom for a forwarder's temp filename
      (`mkstemp(prefix=name + ".")` would exceed `NAME_MAX`), so writers must size their own.
- [ ] `test_read_returns_the_source_file_mode` — `chmod` the source to `0o600` first so it can
      distinguish `fstat(fd)` from `stat(path)`; **skip on Windows**.
- [ ] `test_read_propagates_a_permission_error_rather_than_advancing` — record opened paths and
      assert the legacy file was not read, matching its sibling.
- [ ] Both `Path.open` monkeypatches — match on the full path, not the basename.
- [ ] Fix this plan's own Task 5 sample, which still shows the superseded
      `check_run_manifest_identity(..., filename: str)`.
- [ ] Full suite + black + ruff + `openspec validate --strict`. Commit.

## Deliberately NOT fixed here

- The `base.is_dir()` race (`os.open(..., O_DIRECTORY)` + `dir_fd=`) — a real improvement and a
  real refactor of the read loop, days after the rest is verified. File it.
- Narrowing `_RUN_ID_PATTERN` to lowercase-only — would reject ids the spec currently accepts,
  so it is a breaking narrowing, not a fix.
- `is_run_manifest_name` / cleanup-glob helper — no caller yet; add it with the cleanup work.
- A frozen dataclass instead of `NamedTuple` — churn without a caller to protect.
