"""Prediction manifest contract: predict's per-scan output shape.

Promoted from `sleap-roots-predict`'s `output_contract.py` (predict PR #16, `a252cdc`).
Predict's filesystem-writing/hashing/naming helpers stay in predict; only the pure
model shapes are promoted here, matching this library's no-I/O constraint.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import BlobKind, ModelRef, RootType

# `model_id`/`model` are protected-namespace-shaped fields; `protected_namespaces=()`
# disables pydantic's guard for them (predict's own output_contract.py does the same).
_FROZEN = ConfigDict(frozen=True, protected_namespaces=())


class PredictionArtifact(BaseModel):
    """One predicted root type's `.slp` file plus its identity + integrity.

    Attributes:
        kind: The blob kind this artifact carries once uploaded as a `BlobRef`.
        root_type: The root type this artifact carries.
        model_id: Filename-safe slug of the model (a discovery label; the full
            identity is `model`).
        model: The resolved `ModelRef` that produced this `.slp`.
        slp_path: Basename of the `.slp` (POSIX-style), relative to the manifest's
            directory.
        checksum: sha256 hex digest of the `.slp` file.
        file_size: Size of the `.slp` file in bytes.
    """

    model_config = _FROZEN

    kind: BlobKind = "predictions_slp"
    root_type: RootType
    model_id: str
    model: ModelRef
    slp_path: str
    checksum: str
    file_size: int


class PredictionManifest(BaseModel):
    """Per-scan output contract: manifest + predict-side provenance.

    Attributes:
        schema_version: Version of this manifest shape.
        scan_key: Producer-side scan identifier (also the `.slp` filename stem).
        plant_qr_code: Cross-scan plant key; defaults to `scan_key` when unset.
        artifacts: One `PredictionArtifact` per predicted root type (may be empty
            when no root type resolved to a model).
        predict_inference_config: Full effective inference config (audit).
        predict_output_params: Output-defining subset of the inference config.
        predict_code_sha: Git sha of the predict code (`""` when unknown).
        predict_container_digest: Image digest of the predict container (`""` when
            unknown).
    """

    model_config = _FROZEN

    schema_version: str = "1"
    scan_key: str
    plant_qr_code: str = ""
    artifacts: list[PredictionArtifact] = Field(default_factory=list)
    predict_inference_config: dict[str, Any] = Field(default_factory=dict)
    predict_output_params: dict[str, Any] = Field(default_factory=dict)
    predict_code_sha: str = ""
    predict_container_digest: str = ""

    @model_validator(mode="after")
    def _default_plant_qr_code(self) -> "PredictionManifest":
        """Default `plant_qr_code` to `scan_key` when not provided."""
        if not self.plant_qr_code:
            object.__setattr__(self, "plant_qr_code", self.scan_key)
        return self
