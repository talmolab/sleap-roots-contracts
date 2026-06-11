"""Shared result + provenance contract for the sleap-roots <-> Bloom pipeline."""

from .analysis_input import (
    AnalysisInputRow,
    ValidationIssue,
    ValidationResult,
    validate_analysis_input,
)
from .hashing import NonCanonicalizableError, compute_param_hash
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

__version__ = "0.1.0a1"
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
    # Analysis-input contract (structural validator + canonical row model).
    "AnalysisInputRow",
    "ValidationIssue",
    "ValidationResult",
    "validate_analysis_input",
    # Producer-side hashing surface (Python consumers of this package are the
    # producers; Bloom consumes only the emitted JSON Schema).
    "compute_param_hash",
    "NonCanonicalizableError",
    "__version__",
]
