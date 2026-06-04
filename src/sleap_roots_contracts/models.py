"""Pydantic contract models — the canonical source of truth."""

import math
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from .hashing import compute_param_hash
from .identity import compute_idempotency_key


class ModelRef(BaseModel):
    """Identity of one model used in a run (FK-able to a future Bloom models table)."""

    registry_id: str
    version: str
    sleap_nn_version: str
    root_type: str | None = None
    weights_checksum: str | None = None


class InputRef(BaseModel):
    """Pins the input data a run consumed, for reproducibility."""

    image_ids: list[str]
    images_checksum: str


class ResolvedParams(BaseModel):
    """Fully-resolved run params plus their canonical hash."""

    values: dict[str, Any]
    param_hash: str = ""

    @model_validator(mode="after")
    def _fill_hash(self) -> "ResolvedParams":
        computed = compute_param_hash(self.values)
        if self.param_hash and self.param_hash != computed:
            raise ValueError(
                f"param_hash {self.param_hash!r} does not match values "
                f"(computed {computed!r})"
            )
        object.__setattr__(self, "param_hash", computed)
        return self


class Provenance(BaseModel):
    """Run provenance; serializes to cyl_trait_sources.metadata jsonb (sub-project #2)."""

    contract_version: str
    scan_key: str
    inputs: InputRef
    idempotency_key: str = ""
    pipeline_run_id: str | None = None

    # predict stage
    predict_models: list[ModelRef]
    predict_container_digest: str
    predict_code_sha: str
    worker_request_id: str | None = None

    # traits stage
    traits_sleap_roots_version: str
    traits_container_digest: str
    traits_code_sha: str

    # orchestration (execution-model dependent)
    argo_workflow_uid: str | None = None
    argo_node_id: str | None = None

    params: ResolvedParams
    produced_at: datetime | None = None

    @model_validator(mode="after")
    def _fill_idempotency_key(self) -> "Provenance":
        key = compute_idempotency_key(
            scan_key=self.scan_key,
            images_checksum=self.inputs.images_checksum,
            models=[
                (m.registry_id, m.version, m.weights_checksum)
                for m in self.predict_models
            ],
            param_hash=self.params.param_hash,
            predict_code_sha=self.predict_code_sha,
            traits_code_sha=self.traits_code_sha,
        )
        if self.idempotency_key and self.idempotency_key != key:
            raise ValueError(
                f"idempotency_key {self.idempotency_key!r} does not match derived "
                f"value (computed {key!r})"
            )
        object.__setattr__(self, "idempotency_key", key)
        return self


class TraitValue(BaseModel):
    """One long-format trait row. NaN/inf normalize to None (-> SQL NULL)."""

    name: str
    value: float | None = None
    grain: Literal["scan", "image"] = "scan"
    scan_key: str

    @model_validator(mode="after")
    def _normalize_nonfinite(self) -> "TraitValue":
        if self.value is not None and (
            math.isnan(self.value) or math.isinf(self.value)
        ):
            object.__setattr__(self, "value", None)
        return self


BlobKind = Literal["predictions_slp", "labels", "h5", "qc_image"]


class BlobRef(BaseModel):
    """Pointer to an intermediate artifact (rows in the #2 intermediates table)."""

    kind: BlobKind
    scan_key: str
    s3_location: str | None = None
    box_link: str | None = None
    checksum: str | None = None
    file_size: int | None = None

    @model_validator(mode="after")
    def _require_location(self) -> "BlobRef":
        if self.s3_location is None and self.box_link is None:
            raise ValueError("BlobRef requires at least one of s3_location or box_link")
        return self


class ResultEnvelope(BaseModel):
    """One per-scan result: 1 envelope : 1 source row : 1 scan."""

    provenance: Provenance
    traits: list[TraitValue]
    blobs: list[BlobRef] = []
