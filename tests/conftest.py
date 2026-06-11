"""Shared pytest fixtures for the test suite.

Loads the analysis-input example tables from the **packaged** accessor
(``sleap_roots_contracts.examples``) — the same path a downstream consumer uses — so
the tests exercise the shipped examples, not a copy in the test tree.
"""

import pytest

from sleap_roots_contracts.examples import (
    ANALYSIS_INPUT_EXAMPLES,
    analysis_input_example_path,
    load_analysis_input_example,
)

# All shipped examples (parametrized over for "each example validates").
EXAMPLE_TABLES = ANALYSIS_INPUT_EXAMPLES
# Sample-level tables carry a sample_id; the genotype-aggregated one does not.
SAMPLE_LEVEL_TABLES = ("cylinder", "cylinder_no_replicate", "field", "turface")
GENOTYPE_AGGREGATED_TABLE = "genotype_means"


@pytest.fixture(params=EXAMPLE_TABLES)
def example_analysis_input(request):
    """Each shipped example analysis-input table (parametrized over all examples)."""
    return load_analysis_input_example(request.param)


@pytest.fixture
def load_analysis_input():
    """Return the packaged loader to read a named example by shape."""
    return load_analysis_input_example


@pytest.fixture
def example_path():
    """Return the accessor for a packaged example's filesystem path."""
    return analysis_input_example_path
