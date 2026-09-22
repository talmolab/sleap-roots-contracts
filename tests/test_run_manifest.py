"""Tests for the run-manifest contract (RunManifest)."""

import os
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.run_manifest import (
    PIPELINE_RUN_ID_ENV_VAR,
    RUN_MANIFEST_FILENAME,
    LoadedRunManifest,
    RunManifest,
    RunManifestError,
    RunManifestIdentityError,
    RunManifestMissingError,
    RunManifestRead,
    check_run_manifest_identity,
    load_run_manifest,
    pipeline_run_id_from_env,
    read_run_manifest,
    run_manifest_filename,
    run_manifest_name_for_writing,
)
from sleap_roots_contracts.schema import MODELS


def make_manifest(**overrides):
    """Build a valid RunManifest with sensible defaults, overridable per-test."""
    base = dict(
        pipeline_run_id="sleap-roots-pipeline-abc123xy",
        scan_keys=["scan_1009", "scan_577", "scan_289"],
    )
    base.update(overrides)
    return RunManifest(**base)


def test_pipeline_run_id_is_required():
    """A RunManifest missing pipeline_run_id raises."""
    with pytest.raises(ValidationError):
        RunManifest(scan_keys=["scan_1"])


def test_scan_keys_is_required():
    """A RunManifest missing scan_keys raises."""
    with pytest.raises(ValidationError):
        RunManifest(pipeline_run_id="sleap-roots-pipeline-abc123xy")


def test_schema_version_defaults_to_one():
    """schema_version defaults to "1"."""
    assert make_manifest().schema_version == "1"


def test_manifest_is_frozen():
    """A RunManifest cannot be mutated after construction."""
    m = make_manifest()
    with pytest.raises(ValidationError):
        m.pipeline_run_id = "other"


def test_manifest_round_trips_through_json():
    """A manifest with realistic fixture values dumps to JSON and reloads equal."""
    manifest = make_manifest()
    reloaded = RunManifest.model_validate_json(manifest.model_dump_json())
    assert reloaded == manifest


def test_manifest_round_trips_through_dict():
    """A manifest survives a model_dump()/model_validate() round-trip (not just JSON)."""
    manifest = make_manifest()
    reloaded = RunManifest.model_validate(manifest.model_dump())
    assert reloaded == manifest


def test_empty_scan_keys_is_rejected():
    """scan_keys=[] raises with a message naming the empty-list failure specifically."""
    with pytest.raises(ValidationError, match="scan_keys must not be empty"):
        make_manifest(scan_keys=[])


def test_duplicate_scan_keys_is_rejected():
    """A repeated scan_key entry raises with a message naming the duplicate failure."""
    with pytest.raises(ValidationError, match="scan_keys must not contain duplicates"):
        make_manifest(scan_keys=["scan_1", "scan_1"])


def test_blank_scan_key_element_is_rejected():
    """An empty-string scan_key entry raises with a message naming the blank failure."""
    with pytest.raises(ValidationError, match="blank or whitespace-only"):
        make_manifest(scan_keys=["scan_1", ""])


def test_whitespace_only_scan_key_element_is_rejected():
    """A whitespace-only scan_key entry raises with a message naming the blank failure."""
    with pytest.raises(ValidationError, match="blank or whitespace-only"):
        make_manifest(scan_keys=["scan_1", "  "])


def test_non_string_scan_key_element_is_rejected():
    """An int scan_key entry raises rather than being coerced (bloom#555 boundary)."""
    with pytest.raises(ValidationError):
        make_manifest(scan_keys=[1009, 577])


def test_none_scan_key_element_is_rejected():
    """A None scan_key entry raises."""
    with pytest.raises(ValidationError):
        make_manifest(scan_keys=["scan_1", None])


def test_scan_keys_order_is_preserved():
    """scan_keys retains construction order through a JSON round-trip."""
    manifest = make_manifest(scan_keys=["scan_3", "scan_1", "scan_2"])
    assert manifest.scan_keys == ["scan_3", "scan_1", "scan_2"]
    reloaded = RunManifest.model_validate_json(manifest.model_dump_json())
    assert reloaded.scan_keys == ["scan_3", "scan_1", "scan_2"]


def test_run_manifest_filename_literal_value():
    """RUN_MANIFEST_FILENAME is pinned to the literal "run_manifest.json"."""
    assert RUN_MANIFEST_FILENAME == "run_manifest.json"


def test_run_manifest_importable_from_package_root():
    """RunManifest/RUN_MANIFEST_FILENAME are exported from the package root."""
    import sleap_roots_contracts

    assert sleap_roots_contracts.RunManifest is RunManifest
    assert sleap_roots_contracts.RUN_MANIFEST_FILENAME is RUN_MANIFEST_FILENAME
    assert "RunManifest" in sleap_roots_contracts.__all__
    assert "RUN_MANIFEST_FILENAME" in sleap_roots_contracts.__all__


def test_run_manifest_absent_from_schema_models():
    """RunManifest is producer<->producer; not schema-emitted.

    Like PredictionManifest/ModelCard, this contract never crosses the Bloom boundary, so it
    must not appear in schema.py's emitted MODELS set.
    """
    assert set(MODELS) == {"result_envelope", "analysis_input"}
    assert RunManifest not in MODELS.values()


def test_manifest_round_trips_through_a_real_file(tmp_path):
    """A manifest written to RUN_MANIFEST_FILENAME on disk reloads equal (bloom#555 boundary).

    Exercises the literal write/read boundary the filesystem contract actually crosses
    (encoding, whitespace), not just an in-memory round-trip.
    """
    manifest = make_manifest()
    path = tmp_path / RUN_MANIFEST_FILENAME
    path.write_text(manifest.model_dump_json(), encoding="utf-8")

    reloaded = RunManifest.model_validate_json(path.read_text(encoding="utf-8"))

    assert reloaded == manifest


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


def test_read_still_uses_the_legacy_name_without_an_identity_when_the_fallback_is_off(
    tmp_path,
):
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


def test_read_rejects_a_blank_run_id(tmp_path, monkeypatch):
    """A blank-but-not-None id is invalid, not 'no identity' — it must not silently
    become the legacy path.

    A readable legacy manifest is present, so were the blank id treated as "no identity"
    the call would return it instead of raising. The recorded `Path.open` pins the rest of
    the spec clause — "and the legacy name is not read": the id is validated while the
    candidate list is built, before any file is opened.
    """
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')

    opened: list[Path] = []
    real_open = Path.open

    def recording_open(self, *args, **kwargs):
        opened.append(self)
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", recording_open)

    with pytest.raises(ValueError):
        read_run_manifest(tmp_path, "", allow_legacy=True)
    assert opened == []


def test_read_reports_a_missing_directory_as_such(tmp_path):
    """ENOENT on the directory is also FileNotFoundError, so say which is missing.

    Without this, a mis-mounted stage-in — the likelier cause under Argo — reports as a
    missing manifest and sends the reader hunting the wrong problem.
    """
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError) as excinfo:
        read_run_manifest(missing, "wf1", allow_legacy=True)
    assert "nope" in str(excinfo.value)


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows ignores POSIX permission bits"
)
def test_read_returns_the_source_file_mode(tmp_path):
    """predict forwards the manifest and must reproduce its mode without a second stat.

    Chmod the source to a mode nothing else in this test would produce, so the assertion can
    distinguish `fstat(fd)` from a naive `base.stat()` rather than passing for either.
    """
    target = tmp_path / RUN_MANIFEST_FILENAME
    target.write_bytes(b"{}")
    os.chmod(target, 0o600)
    result = read_run_manifest(tmp_path, None, allow_legacy=True)
    assert result.mode == 0o600


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


def test_read_propagates_a_permission_error_rather_than_advancing(
    tmp_path, monkeypatch
):
    """An unreadable manifest must never be mistaken for an absent one.

    This is the reason the function opens rather than probing: a boolean predicate collapses
    EACCES into "absent", which would fall through to a stale legacy manifest. bloomctl's
    ingest.py avoids .is_file() for exactly this reason. The recorded `Path.open` calls pin
    the "and the legacy file is not read" half of the scenario, which otherwise holds only
    because the raise happens to escape the loop before a second candidate is tried.
    """
    target = tmp_path / "run_manifest.wf1.json"
    target.write_bytes(b"{}")
    legacy = tmp_path / RUN_MANIFEST_FILENAME
    legacy.write_bytes(b'{"legacy": true}')

    opened: list[Path] = []
    real_open = Path.open

    def deny(self, *args, **kwargs):
        opened.append(self)
        if self == target:
            raise PermissionError(13, "Permission denied")
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny)
    with pytest.raises(PermissionError):
        read_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert legacy not in opened


def test_read_accepts_a_string_directory(tmp_path):
    """Consumers pass str paths in places; accept them like the rest of the library."""
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b"{}")
    assert read_run_manifest(str(tmp_path), None, allow_legacy=True).data == b"{}"


def test_read_requires_allow_legacy_to_be_passed(tmp_path):
    """No default: a caller must state its position on the legacy fallback.

    A default would let the fleet-wide migration state go unstated at a call site, which is
    the hazard the required parameter exists to prevent.
    """
    with pytest.raises(TypeError):
        read_run_manifest(tmp_path, "wf1")


def test_read_rejects_allow_legacy_positionally(tmp_path):
    """Keyword-only: `read_run_manifest(dir, id, True)` must not silently mean allow_legacy."""
    with pytest.raises(TypeError):
        read_run_manifest(tmp_path, "wf1", True)


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlink creation needs privilege on Windows"
)
def test_read_raises_for_a_dangling_symlink_at_the_per_run_name(tmp_path):
    """A dangling per-run symlink must not be mistaken for an absent candidate.

    This is the regression test for the bug: `open()` raises `FileNotFoundError` both for a
    candidate that is genuinely absent and for one that exists as a symlink whose target is
    gone, so a loop that only checks the exception type advances to the legacy manifest in
    both cases — silently handing this run an older run's scope. A readable legacy manifest
    is present, so a wrong implementation would return its content instead of raising.
    """
    per_run = tmp_path / "run_manifest.wf1.json"
    per_run.symlink_to(tmp_path / "does-not-exist.json")
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')

    with pytest.raises(FileNotFoundError) as excinfo:
        read_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert "run_manifest.wf1.json" in str(excinfo.value)


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlink creation needs privilege on Windows"
)
def test_read_raises_for_a_dangling_symlink_at_the_legacy_name(tmp_path):
    """A dangling legacy symlink with no other candidate also raises rather than returning None."""
    legacy = tmp_path / RUN_MANIFEST_FILENAME
    legacy.symlink_to(tmp_path / "does-not-exist.json")

    with pytest.raises(FileNotFoundError) as excinfo:
        read_run_manifest(tmp_path, None, allow_legacy=True)
    assert RUN_MANIFEST_FILENAME in str(excinfo.value)


def test_read_still_advances_past_a_genuinely_absent_per_run_candidate(tmp_path):
    """Non-regression: an absent (not dangling) per-run candidate still falls through.

    The dangling-symlink fix must discriminate the two FileNotFoundError causes, not turn
    every miss on the per-run candidate into a raise.
    """
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(b'{"legacy": true}')
    result = read_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert result.filename == RUN_MANIFEST_FILENAME
    assert result.is_per_run is False
    assert result.data == b'{"legacy": true}'


def make_read(filename, *, is_per_run):
    """Build a RunManifestRead standing in for what read_run_manifest returned."""
    return RunManifestRead(
        filename=filename, data=b"{}", mode=0o644, is_per_run=is_per_run
    )


def test_identity_check_passes_for_the_owning_run():
    """The ordinary case: the file this run wrote names this run."""
    manifest = make_manifest(pipeline_run_id="wf1")
    read = make_read("run_manifest.wf1.json", is_per_run=True)
    assert check_run_manifest_identity(manifest, "wf1", read) is None


def test_identity_check_rejects_a_foreign_manifest():
    """A per-run-named file naming a different run means the tree is not what we think."""
    manifest = make_manifest(pipeline_run_id="wf2")
    read = make_read("run_manifest.wf1.json", is_per_run=True)
    with pytest.raises(RunManifestIdentityError) as excinfo:
        check_run_manifest_identity(manifest, "wf1", read)
    message = str(excinfo.value)
    assert "wf1" in message
    assert "wf2" in message
    assert "run_manifest.wf1.json" in message


def test_identity_check_is_a_noop_for_a_read_that_is_not_per_run():
    """`is_per_run` false carries no identity, so a mismatch there is expected, not an error.

    Named for the predicate rather than the filename because that is what the function now
    reads: `read_run_manifest` already recorded which candidate it opened, and the check
    trusts that flag instead of re-deriving it from the name. Without this, all four call
    sites would write the same `if filename != RUN_MANIFEST_FILENAME` guard themselves —
    and would get it wrong for any read whose filename is not bare.
    """
    manifest = make_manifest(pipeline_run_id="some-older-run")
    read = make_read(RUN_MANIFEST_FILENAME, is_per_run=False)
    assert check_run_manifest_identity(manifest, "wf1", read) is None


def test_identity_check_is_a_noop_for_a_caller_with_no_run_identity():
    """`pipeline_run_id=None` needs no branch: such a caller only ever gets is_per_run false.

    This is what lets the natural read -> parse -> check chain pass its `str | None` id
    straight through without a guard at the call site.
    """
    manifest = make_manifest(pipeline_run_id="some-older-run")
    read = make_read(RUN_MANIFEST_FILENAME, is_per_run=False)
    assert check_run_manifest_identity(manifest, None, read) is None


def test_identity_check_uses_the_flag_not_the_filename():
    """``is_per_run`` governs the decision; ``filename`` (always a bare filename) is used
    only to compose the error message, never parsed or compared to decide anything.

    The filename here deliberately does not name either run, to show the check's outcome
    turns on ``is_per_run`` and the two manifests' ``pipeline_run_id`` values alone.
    """
    manifest = make_manifest(pipeline_run_id="wf1")
    read = make_read("run_manifest.some-other-run.json", is_per_run=True)
    assert check_run_manifest_identity(manifest, "wf1", read) is None

    foreign = make_manifest(pipeline_run_id="wf2")
    with pytest.raises(RunManifestIdentityError) as excinfo:
        check_run_manifest_identity(foreign, "wf1", read)
    assert "run_manifest.some-other-run.json" in str(excinfo.value)


def test_identity_check_raises_value_error_for_no_identity_with_a_per_run_read():
    """`None` identity with a per-run read is a caller bug, not a foreign manifest.

    `read_run_manifest` never hands a caller with no identity a per-run read — without an
    identity the per-run filename is never a candidate — so this combination can only arise
    from a hand-built or mismatched `RunManifestRead`. The error type must say "caller bug",
    not "escalate this tree": `RunManifestIdentityError` is not a `ValueError`, so a bare
    `pytest.raises(ValueError)` genuinely discriminates between the two.
    """
    manifest = make_manifest(pipeline_run_id="wf1")
    read = make_read("run_manifest.wf1.json", is_per_run=True)
    with pytest.raises(ValueError) as excinfo:
        check_run_manifest_identity(manifest, None, read)
    assert not isinstance(excinfo.value, RunManifestIdentityError)
    assert "run_manifest.wf1.json" in str(excinfo.value)


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


def test_an_invalid_run_id_is_not_a_run_manifest_error():
    """RunManifestError is the base of resolution/identity failures only, not of every one.

    An unusable id is a plain ValueError, so a consumer catching RunManifestError alone
    does not catch it. Pinned so the class's stated scope stays true.
    """
    with pytest.raises(ValueError) as excinfo:
        run_manifest_filename("../escape")
    assert not isinstance(excinfo.value, RunManifestError)


def test_a_missing_directory_is_not_a_run_manifest_error(tmp_path):
    """The other failure outside the base class: a mis-mounted directory is an OSError."""
    with pytest.raises(FileNotFoundError) as excinfo:
        read_run_manifest(tmp_path / "nope", "wf1", allow_legacy=True)
    assert not isinstance(excinfo.value, RunManifestError)


def test_new_names_are_exported_from_the_package_root():
    """Every new name is importable from the package root and listed in __all__."""
    import sleap_roots_contracts as pkg

    for name in (
        "PIPELINE_RUN_ID_ENV_VAR",
        "LoadedRunManifest",
        "RunManifestError",
        "RunManifestIdentityError",
        "RunManifestMissingError",
        "RunManifestRead",
        "check_run_manifest_identity",
        "load_run_manifest",
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


def test_load_run_manifest_happy_path_returns_manifest_and_read(tmp_path):
    """The composed call reads, parses and cross-checks in one step."""
    (tmp_path / "run_manifest.wf1.json").write_bytes(
        b'{"pipeline_run_id": "wf1", "scan_keys": ["scan_1"]}'
    )
    loaded = load_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert isinstance(loaded, LoadedRunManifest)
    assert loaded.manifest.pipeline_run_id == "wf1"
    assert loaded.read.is_per_run is True
    assert loaded.read.filename == "run_manifest.wf1.json"


def test_load_run_manifest_raises_identity_error_for_a_foreign_manifest(tmp_path):
    """A per-run manifest naming a different run raises through the composed call."""
    (tmp_path / "run_manifest.wf1.json").write_bytes(
        b'{"pipeline_run_id": "wf2", "scan_keys": ["scan_1"]}'
    )
    with pytest.raises(RunManifestIdentityError):
        load_run_manifest(tmp_path, "wf1", allow_legacy=True)


def test_load_run_manifest_skips_cross_check_for_the_legacy_manifest(tmp_path):
    """A legacy manifest naming an earlier run loads without a cross-check."""
    (tmp_path / RUN_MANIFEST_FILENAME).write_bytes(
        b'{"pipeline_run_id": "some-older-run", "scan_keys": ["scan_1"]}'
    )
    loaded = load_run_manifest(tmp_path, "wf1", allow_legacy=True)
    assert loaded.read.is_per_run is False
    assert loaded.manifest.pipeline_run_id == "some-older-run"


def test_load_run_manifest_returns_none_when_nothing_present_and_no_identity(tmp_path):
    """Nothing found and no run identity returns None, matching read_run_manifest."""
    assert load_run_manifest(tmp_path, None, allow_legacy=False) is None


def test_load_run_manifest_raises_missing_when_nothing_present_with_an_identity(
    tmp_path,
):
    """Nothing found with a run identity is RunManifestMissingError."""
    with pytest.raises(RunManifestMissingError):
        load_run_manifest(tmp_path, "wf1", allow_legacy=True)


def test_load_run_manifest_raises_validation_error_for_a_malformed_manifest(tmp_path):
    """A malformed manifest raises pydantic's ValidationError, unwrapped."""
    (tmp_path / "run_manifest.wf1.json").write_bytes(b"not json")
    with pytest.raises(ValidationError):
        load_run_manifest(tmp_path, "wf1", allow_legacy=True)
