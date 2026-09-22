"""Tests for the run-manifest contract (RunManifest)."""

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.run_manifest import (
    PIPELINE_RUN_ID_ENV_VAR,
    RUN_MANIFEST_FILENAME,
    RunManifest,
    pipeline_run_id_from_env,
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
