"""Tests for the prediction-manifest contract (PredictionArtifact/PredictionManifest)."""

import pytest
from pydantic import ValidationError

from sleap_roots_contracts.models import ModelRef
from sleap_roots_contracts.prediction_manifest import (
    PredictionArtifact,
    PredictionManifest,
)
from sleap_roots_contracts.schema import MODELS


def _ref(root_type="primary", registry_id="reg/rice-primary", version="v1"):
    """Build a valid ModelRef, overridable per-test (mirrors predict's own helper)."""
    return ModelRef(
        registry_id=registry_id,
        version=version,
        sleap_nn_version="0.3.0",
        root_type=root_type,
    )


def make_artifact(**overrides):
    """Build a valid PredictionArtifact with sensible defaults, overridable per-test."""
    base = dict(
        root_type="primary",
        model_id="reg-rice-primary-v1",
        model=_ref(),
        slp_path="s1.modelreg-rice-primary-v1.rootprimary.slp",
        checksum="abc123",
        file_size=42,
    )
    base.update(overrides)
    return PredictionArtifact(**base)


def make_manifest(**overrides):
    """Build a valid PredictionManifest with sensible defaults, overridable per-test."""
    base = dict(scan_key="s1")
    base.update(overrides)
    return PredictionManifest(**base)


def test_artifact_kind_defaults_to_predictions_slp():
    """kind defaults to "predictions_slp" when not given."""
    assert make_artifact().kind == "predictions_slp"


def test_artifact_rejects_unknown_kind():
    """An out-of-vocabulary kind is rejected."""
    with pytest.raises(ValidationError):
        make_artifact(kind="labels")


def test_artifact_rejects_unknown_root_type():
    """An out-of-vocabulary root_type is rejected."""
    with pytest.raises(ValidationError):
        make_artifact(root_type="seedling")


def test_artifact_is_frozen():
    """A PredictionArtifact cannot be mutated after construction."""
    a = make_artifact()
    with pytest.raises(ValidationError):
        a.checksum = "def456"


def test_artifact_missing_required_field_raises():
    """A PredictionArtifact missing a required field (file_size) raises."""
    with pytest.raises(ValidationError):
        PredictionArtifact(
            root_type="primary",
            model_id="m",
            model=_ref(),
            slp_path="p.slp",
            checksum="abc",
        )


def test_manifest_plant_qr_code_defaults_to_scan_key():
    """An unset plant_qr_code defaults to scan_key."""
    assert make_manifest(scan_key="scan0731").plant_qr_code == "scan0731"


def test_manifest_schema_version_defaults_to_one():
    """schema_version defaults to "1"."""
    assert make_manifest().schema_version == "1"


def test_manifest_empty_defaults_for_scan_with_no_resolved_roots():
    """A manifest built with only scan_key has empty artifacts/config defaults."""
    m = make_manifest()
    assert m.artifacts == []
    assert m.predict_inference_config == {}
    assert m.predict_output_params == {}


def test_manifest_is_frozen():
    """A PredictionManifest cannot be mutated after construction."""
    m = make_manifest()
    with pytest.raises(ValidationError):
        m.scan_key = "other"


def test_manifest_missing_required_field_raises():
    """A PredictionManifest missing scan_key raises."""
    with pytest.raises(ValidationError):
        PredictionManifest()


def test_manifest_round_trips_through_json():
    """A manifest with a real nested ModelRef dumps to JSON and reloads equal."""
    artifact = make_artifact()
    manifest = make_manifest(
        scan_key="s1",
        plant_qr_code="s1",
        artifacts=[artifact],
        predict_inference_config={"device": "cpu", "peak_threshold": 0.2},
        predict_output_params={"peak_threshold": 0.2},
    )
    reloaded = PredictionManifest.model_validate_json(manifest.model_dump_json())
    assert reloaded == manifest
    assert reloaded.artifacts[0].model == _ref()


def test_manifest_with_explicit_empty_artifacts_round_trips():
    """A manifest with artifacts explicitly set to [] round-trips through JSON."""
    manifest = make_manifest(scan_key="s1", artifacts=[])
    reloaded = PredictionManifest.model_validate_json(manifest.model_dump_json())
    assert reloaded == manifest
    assert reloaded.artifacts == []


def test_manifest_schema_version_override_round_trips():
    """A non-default schema_version is retained and survives a JSON round-trip."""
    manifest = make_manifest(scan_key="s1", schema_version="2")
    reloaded = PredictionManifest.model_validate_json(manifest.model_dump_json())
    assert reloaded.schema_version == "2"


def test_manifest_round_trips_through_dict():
    """A manifest survives a model_dump()/model_validate() round-trip (not just JSON)."""
    manifest = make_manifest(scan_key="s1", artifacts=[make_artifact()])
    reloaded = PredictionManifest.model_validate(manifest.model_dump())
    assert reloaded == manifest


def test_manifest_with_all_root_types_round_trips():
    """A manifest with three artifacts spanning all RootTypes preserves each."""
    artifacts = [
        make_artifact(root_type=rt, model=_ref(root_type=rt))
        for rt in ("primary", "lateral", "crown")
    ]
    manifest = make_manifest(scan_key="s1", artifacts=artifacts)
    reloaded = PredictionManifest.model_validate_json(manifest.model_dump_json())
    assert reloaded == manifest
    assert {a.root_type for a in reloaded.artifacts} == {"primary", "lateral", "crown"}


def test_prediction_models_importable_from_package_root():
    """PredictionArtifact/PredictionManifest are exported from the package root."""
    import sleap_roots_contracts

    assert sleap_roots_contracts.PredictionArtifact is PredictionArtifact
    assert sleap_roots_contracts.PredictionManifest is PredictionManifest


def test_prediction_manifest_absent_from_schema_models():
    """PredictionManifest/PredictionArtifact are producer<->producer; not schema-emitted.

    Like ModelCard, this contract never crosses the Bloom boundary, so it must not
    appear in schema.py's emitted MODELS set.
    """
    assert set(MODELS) == {"result_envelope", "analysis_input"}
    assert PredictionManifest not in MODELS.values()
    assert PredictionArtifact not in MODELS.values()
