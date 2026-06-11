"""Shared pytest fixtures for the test suite.

Provides a loader for the shipped analysis-input example tables. The loader is a
pytest fixture (not a plain helper) so the example CSVs are read once per use and the
"each example validates" test can parametrize over the three shapes.
"""

from pathlib import Path

import pytest

ANALYSIS_INPUT_DIR = Path(__file__).parent / "fixtures" / "analysis_input"
ANALYSIS_INPUT_SHAPES = ("cylinder", "field", "turface")

# Canonical role columns are string-typed. A consumer canonicalizes its own data to
# the contract before validating; mirror that here so an all-numeric label (e.g. a
# replicate of "1") keeps its string role dtype after pandas' CSV type inference.
_ROLE_COLUMNS = ("genotype", "sample_id", "replicate", "image_path")


def _load_analysis_input(name: str):
    """Read one example analysis-input CSV with canonical role dtypes."""
    import pandas as pd

    df = pd.read_csv(ANALYSIS_INPUT_DIR / f"{name}.csv")
    role_cols = {col: "string" for col in _ROLE_COLUMNS if col in df.columns}
    return df.astype(role_cols)


@pytest.fixture
def analysis_input_dir() -> Path:
    """Directory holding the shipped analysis-input example CSVs."""
    return ANALYSIS_INPUT_DIR


@pytest.fixture(params=ANALYSIS_INPUT_SHAPES)
def example_analysis_input(request):
    """Each shipped example analysis-input table, one per shape (parametrized)."""
    return _load_analysis_input(request.param)
