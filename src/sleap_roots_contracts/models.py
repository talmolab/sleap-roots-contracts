"""Pydantic contract models — the canonical source of truth."""

from typing import Any

from pydantic import BaseModel, model_validator

from .hashing import compute_param_hash


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
