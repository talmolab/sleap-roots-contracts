"""Packaged canonical analysis-input example tables.

Small real subsets of the wheat EDPIE post-QC tables in **canonical** form (role
columns + opaque numeric trait columns, no non-trait metadata). They ship inside the
wheel so downstream consumers (e.g. ``sleap-roots-analyze``, ``bloom-mcp``) can load
them from the released package rather than the test tree.

:func:`load_analysis_input_example` reads the role columns as strings, so the returned
frame passes :func:`sleap_roots_contracts.validate_analysis_input` directly — a bare
``pd.read_csv`` of the same file would infer a numeric ``replicate`` and fail the
role-dtype check (the canonicalization a consumer must otherwise perform).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

from ..analysis_input import canonicalize_role_dtypes

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

# Canonical analysis-input example tables (CSV stems shipped alongside this module).
# Coverage: replicate-present sample-level (cylinder/field/turface); replicate-absent
# sample-level (cylinder_no_replicate — the Bloom cylinder shape, analyze#142); and a
# genotype-aggregated table with no sample_id (genotype_means).
ANALYSIS_INPUT_EXAMPLES = (
    "cylinder",
    "cylinder_no_replicate",
    "field",
    "turface",
    "genotype_means",
)

__all__ = [
    "ANALYSIS_INPUT_EXAMPLES",
    "analysis_input_example_names",
    "analysis_input_example_path",
    "load_analysis_input_example",
]


def analysis_input_example_names() -> tuple[str, ...]:
    """Return the names of the packaged analysis-input example tables."""
    return ANALYSIS_INPUT_EXAMPLES


def _check_name(name: str) -> None:
    if name not in ANALYSIS_INPUT_EXAMPLES:
        raise KeyError(
            f"unknown example {name!r}; choose from {ANALYSIS_INPUT_EXAMPLES}"
        )


def analysis_input_example_path(name: str) -> Path:
    """Return the filesystem path to a packaged example CSV.

    For consumers that read the file with their own loader. Note that a bare
    ``pd.read_csv`` infers a numeric ``replicate``; cast the role columns to ``str``
    before validating, or use :func:`load_analysis_input_example`, which does so.

    The returned path is valid for filesystem-backed installs (the normal wheel /
    pip / uv case). Under a zip-imported install the resource is not a real file on
    disk; use :func:`load_analysis_input_example` (which extracts via
    ``importlib.resources.as_file``) instead.
    """
    _check_name(name)
    return Path(str(resources.files(__name__).joinpath(f"{name}.csv")))


def load_analysis_input_example(name: str) -> "pd.DataFrame":
    """Load a packaged analysis-input example as a frame that validates as-is.

    Role columns are read as strings so the returned frame passes
    ``validate_analysis_input`` without any further canonicalization by the caller.

    Args:
        name: One of :data:`ANALYSIS_INPUT_EXAMPLES`.

    Returns:
        A pandas DataFrame with string-typed role columns and the example's trait
        columns.

    Raises:
        ImportError: if pandas is not installed (install the ``[pandas]`` extra).
        KeyError: if ``name`` is not a known example.
    """
    _check_name(name)  # validate the name first, independent of the optional extra
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "loading example tables requires pandas. Install the optional extra: "
            "pip install 'sleap-roots-contracts[pandas]'"
        ) from exc
    source = resources.files(__name__).joinpath(f"{name}.csv")
    with resources.as_file(source) as path:
        df = pd.read_csv(path)
    # Reuse the contract's single role-dtype canonicalization (and its ROLE_COLUMNS).
    return canonicalize_role_dtypes(df)
