"""Trait definitions registry: name/dtype/range validation for trait values."""

import warnings
from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel


class TraitDefinition(BaseModel):
    """Definition of a known trait."""

    unit: str
    dtype: Literal["float", "int"]
    description: str
    min: float | None = None
    max: float | None = None


def load_registry() -> dict[str, TraitDefinition]:
    """Load the packaged trait-definitions registry."""
    text = (
        resources.files("sleap_roots_contracts")
        .joinpath("trait_definitions.yaml")
        .read_text()
    )
    raw = yaml.safe_load(text) or {}
    return {name: TraitDefinition(**spec) for name, spec in raw.items()}


def validate_trait(
    name: str,
    value: float | None,
    registry: dict[str, TraitDefinition],
    on_unknown: Literal["warn", "error"] = "warn",
) -> None:
    """Validate a trait name + value against the registry.

    Args:
        name: Trait name to look up.
        value: Trait value (None skips range checks).
        registry: The loaded trait-definitions registry.
        on_unknown: Behavior for names absent from the registry ("warn" or "error").

    Raises:
        ValueError: unknown name (when on_unknown="error") or out-of-range value.
    """
    definition = registry.get(name)
    if definition is None:
        if on_unknown == "error":
            raise ValueError(f"Unknown trait: {name!r}")
        warnings.warn(
            f"Unknown trait not in registry: {name!r}", UserWarning, stacklevel=2
        )
        return
    if value is None:
        return
    if definition.min is not None and value < definition.min:
        raise ValueError(f"{name}={value} below min {definition.min}")
    if definition.max is not None and value > definition.max:
        raise ValueError(f"{name}={value} above max {definition.max}")
