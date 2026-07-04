"""Pydantic contract models — the canonical source of truth."""

import math
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    # Effective predict inference config. `predict_inference_config` is the FULL
    # config recorded for audit (including hardware/throughput knobs like device and
    # batch_size) and is NEVER hashed. `predict_output_params` is the output-defining
    # subset (e.g. peak_threshold) that participates in `idempotency_key`. Both are
    # optional; when `predict_output_params` is absent/empty the key is byte-identical
    # to the pre-existing derivation. Producers keep hardware knobs out of
    # `predict_output_params` (the library records it as given and does not enforce
    # the partition).
    predict_inference_config: dict[str, Any] | None = None
    predict_output_params: dict[str, Any] | None = None

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
            predict_output_params=self.predict_output_params,
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


# Defined after RootType on purpose: this module has no `from __future__ import
# annotations`, so the `root_type: RootType` field and the `-> ModelRef` return
# annotation are evaluated at class-definition time and both names must already exist
# (RootType is the binding constraint; ModelRef at line ~18 is never at risk). So
# ModelCard must come *after* RootType; it is placed here, adjacent to it. Conceptually
# it is a model-registry sibling of ModelRef.
class ModelCard(BaseModel):
    """Model-selection metadata + identity for one production model.

    Written by ``sleap-roots-training`` at promotion (the selection fields, as flat
    wandb artifact metadata) and read by ``sleap-roots-predict`` to choose a model
    per root type. The fields come from two sources:

    * **Selection fields** — written by training as flat wandb metadata keys:
      ``species``, ``mode``, ``age_min``, ``age_max``, ``root_type`` (and optionally
      the trained-with ``sleap_nn_version``).
    * **Identity fields** — intrinsic to the wandb artifact object, *not* metadata:
      ``registry_id``, ``version``, ``weights_checksum``. Predict's registry lister
      composes these from the artifact and merges them with the metadata before
      validating, so a bare ``model_validate(training_metadata)`` cannot build a full
      card (it lacks the identity fields).

    ``age_min``/``age_max`` is the *approved selection window*, curated at promotion
    (it MAY be set wider than the raw training ages to cover the data people actually
    scan). It is inclusive and assumed **contiguous** (``[age_min, age_max]``;
    non-contiguous approved sets are not expressible). The card never observes a
    scan's age — running a model outside its window is handled by predict's explicit
    override, not by this contract.

    Extra keys are ignored, so a card validates straight from a raw wandb metadata
    blob (boolean tag flags, the spread training config, eval metrics) merged with the
    artifact identity. ``extra="ignore"`` is set explicitly (not merely relied on as
    pydantic's default) because tolerating that blob is a load-bearing contract here —
    a future ``extra="forbid"`` would silently break predict's registry lister.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    # selection dimensions (training-written metadata)
    species: str
    mode: str
    age_min: int = Field(ge=0)
    age_max: int = Field(ge=0)
    root_type: RootType

    # identity of the concrete production artifact (artifact-intrinsic)
    registry_id: str
    version: str
    weights_checksum: str | None = None

    # trained-with sleap-nn version; optional — used only for predict's mismatch
    # warning (present -> predict can warn; absent -> predict skips the warning).
    sleap_nn_version: str | None = None

    @model_validator(mode="after")
    def _check_age_range(self) -> "ModelCard":
        if self.age_min > self.age_max:
            raise ValueError(
                f"age_min ({self.age_min}) must be <= age_max ({self.age_max})"
            )
        return self

    def to_model_ref(self, runtime_sleap_nn_version: str) -> ModelRef:
        """Build a fully-pinned ``ModelRef``, stamping the RUNTIME sleap-nn version.

        The runtime version (what actually runs inference) is pinned into
        ``ModelRef.sleap_nn_version``, so that required field is always satisfied
        regardless of whether the card carried a trained-with value. Predict compares
        the card's trained-with value against the runtime version and warns on
        mismatch; this method is pure and does not warn.

        Args:
            runtime_sleap_nn_version: The sleap-nn version actually running inference.

        Returns:
            A ``ModelRef`` carrying the card's ``registry_id``, ``version``,
            ``root_type``, and ``weights_checksum``, with the runtime version stamped.
        """
        return ModelRef(
            registry_id=self.registry_id,
            version=self.version,
            sleap_nn_version=runtime_sleap_nn_version,
            root_type=self.root_type,
            weights_checksum=self.weights_checksum,
        )


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
