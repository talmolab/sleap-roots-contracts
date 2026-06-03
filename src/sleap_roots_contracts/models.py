"""Pydantic contract models — the canonical source of truth."""

from datetime import datetime
from typing import Any

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
        object.__setattr__(self, "param_hash", compute_param_hash(self.values))
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
        object.__setattr__(self, "idempotency_key", key)
        return self
