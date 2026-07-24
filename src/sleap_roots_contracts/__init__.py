"""Shared result + provenance contract for the sleap-roots <-> Bloom pipeline."""

from importlib.metadata import PackageNotFoundError, version

from .analysis_input import (
    AnalysisInputRow,
    ValidationIssue,
    ValidationResult,
    canonicalize_role_dtypes,
    validate_analysis_input,
)
from .hashing import NonCanonicalizableError, compute_param_hash
from .models import (
    BlobKind,
    BlobRef,
    InputRef,
    LabelCard,
    Mode,
    ModelCard,
    ModelRef,
    Provenance,
    ResolvedParams,
    ResultEnvelope,
    RootType,
    TraitValue,
)
from .params import resolve_params
from .prediction_manifest import PredictionArtifact, PredictionManifest
from .registry import TraitDefinition, load_registry, validate_trait

# Single source of version truth is pyproject.toml; resolve it from installed
# package metadata so the version (and the schema $id derived from it in
# schema.py) can never drift from what was built/published.
try:
    __version__ = version("sleap-roots-contracts")
except PackageNotFoundError:  # not installed (e.g. running from a bare source tree)
    __version__ = "unknown"

__all__ = [
    "BlobRef",
    "InputRef",
    "LabelCard",
    "ModelCard",
    "ModelRef",
    "Provenance",
    "ResolvedParams",
    "ResultEnvelope",
    "TraitValue",
    "BlobKind",
    "RootType",
    "Mode",
    # Prediction-manifest contract (predict's per-scan output shape; producer<->producer,
    # not emitted to JSON Schema).
    "PredictionArtifact",
    "PredictionManifest",
    "TraitDefinition",
    "load_registry",
    "validate_trait",
    # Analysis-input contract (structural validator + canonical row model).
    "AnalysisInputRow",
    "ValidationIssue",
    "ValidationResult",
    "validate_analysis_input",
    "canonicalize_role_dtypes",
    # Producer-side hashing surface (Python consumers of this package are the
    # producers; Bloom consumes only the emitted JSON Schema).
    "compute_param_hash",
    "NonCanonicalizableError",
    # Param-resolution oracle (Bloom scan metadata -> ResolvedParams). The
    # module's Bloom column-name constants stay module-public, not package API.
    "resolve_params",
    "__version__",
]
