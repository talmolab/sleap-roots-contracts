"""Shared pytest fixtures for the test suite.

Provides a loader for the shipped analysis-input example tables. The loader is a
pytest fixture (not a plain helper) so the example CSVs are read once per use and the
"each example validates" test can parametrize over them.

The examples are small real subsets of the wheat EDPIE post-QC tables (see
``tests/fixtures/analysis_input/README.md``): three sample-level platform tables plus
one genotype-aggregated table (no ``sample_id``) for the grain/warn case.
"""

from pathlib import Path

import pytest

ANALYSIS_INPUT_DIR = Path(__file__).parent / "fixtures" / "analysis_input"

# All shipped examples (parametrized over for "each example validates").
EXAMPLE_TABLES = ("cylinder", "field", "turface", "genotype_means")
# Sample-level tables carry a sample_id; the genotype-aggregated one does not.
SAMPLE_LEVEL_TABLES = ("cylinder", "field", "turface")
GENOTYPE_AGGREGATED_TABLE = "genotype_means"

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


@pytest.fixture(params=EXAMPLE_TABLES)
def example_analysis_input(request):
    """Each shipped example analysis-input table (parametrized over all examples)."""
    return _load_analysis_input(request.param)


@pytest.fixture
def load_analysis_input():
    """Return a loader to read a named example table (for per-table assertions)."""
    return _load_analysis_input
