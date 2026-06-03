"""Shared result + provenance contract for the sleap-roots <-> Bloom pipeline."""

from .models import (
    BlobRef,
    InputRef,
    ModelRef,
    Provenance,
    ResolvedParams,
    ResultEnvelope,
    TraitValue,
)
from .registry import TraitDefinition, load_registry, validate_trait

__version__ = "0.1.0a0"
__all__ = [
    "BlobRef",
    "InputRef",
    "ModelRef",
    "Provenance",
    "ResolvedParams",
    "ResultEnvelope",
    "TraitValue",
    "TraitDefinition",
    "load_registry",
    "validate_trait",
    "__version__",
]
