"""Pydantic contract models — the canonical source of truth."""

import math
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from .hashing import compute_param_hash
from .identity import compute_idempotency_key

# Contract models are immutable: derived fields (param_hash, idempotency_key) and
# normalized values are guaranteed correct for the life of the instance, so the
# validators below use object.__setattr__ to set them past the frozen guard.
_FROZEN = ConfigDict(frozen=True)


class ModelRef(BaseModel):
    """Identity of one model used in a run (FK-able to a future Bloom models table)."""

    model_config = _FROZEN

    registry_id: str
    version: str
    sleap_nn_version: str
    root_type: str | None = None
    weights_checksum: str | None = None


class InputRef(BaseModel):
    """Pins the input data a run consumed, for reproducibility."""

    model_config = _FROZEN

    image_ids: list[str]
    images_checksum: str


class ResolvedParams(BaseModel):
    """Fully-resolved run params plus their canonical hash."""

    model_config = _FROZEN

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

    model_config = _FROZEN

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

    model_config = _FROZEN

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


# The pipeline produces exactly one SLEAP .slp prediction file per root type per
# scan; no other artifact kinds exist in this contract's world. (viewer_html is
# deferred; traits_csv is excluded — trait numbers are TraitValue rows, not blobs.)
BlobKind = Literal["predictions_slp"]

# Controlled vocabulary for a root type. Required on BlobRef (every predictions
# artifact names the root type it carries). ModelRef.root_type is deliberately
# left as a loose `str | None` registry pointer — see the change's design.md.
RootType = Literal["primary", "lateral", "crown"]

# Single source of truth for BlobRef's "at least one location" rule: both the
# emitted JSON Schema constraint and the runtime validator derive from this, so a
# field rename can't leave the schema and the model out of sync.
_BLOB_LOCATION_FIELDS = ("s3_location", "box_link")


def _blob_location_anyof() -> dict:
    """Build the at-least-one-location ``anyOf`` from the location field names.

    Each branch requires one location field and constrains it to a (non-null)
    string, so an all-null object is rejected by the schema exactly as the model
    validator rejects it.
    """
    return {
        "anyOf": [
            {"required": [field], "properties": {field: {"type": "string"}}}
            for field in _BLOB_LOCATION_FIELDS
        ]
    }


class BlobRef(BaseModel):
    """Pointer to an intermediate artifact (rows in the #2 intermediates table)."""

    # Encode the "at least one location" rule in the emitted JSON Schema so
    # consumers (Bloom codegen) reject the same objects Pydantic does.
    model_config = ConfigDict(frozen=True, json_schema_extra=_blob_location_anyof())

    kind: BlobKind
    root_type: RootType
    scan_key: str
    s3_location: str | None = None
    box_link: str | None = None
    checksum: str | None = None
    file_size: int | None = None

    @model_validator(mode="after")
    def _require_location(self) -> "BlobRef":
        if all(getattr(self, field) is None for field in _BLOB_LOCATION_FIELDS):
            raise ValueError(
                "BlobRef requires at least one of " + " or ".join(_BLOB_LOCATION_FIELDS)
            )
        return self


class ResultEnvelope(BaseModel):
    """One per-scan result: 1 envelope : 1 source row : 1 scan."""

    model_config = _FROZEN

    provenance: Provenance
    traits: list[TraitValue]
    blobs: list[BlobRef] = []
