import tomllib
from pathlib import Path

import pytest

import sleap_roots_contracts


def test_version_exposed():
    """__version__ is a resolved (non-sentinel) string from package metadata."""
    assert isinstance(sleap_roots_contracts.__version__, str)
    # "unknown" is the uninstalled-source fallback (see __init__.py); a real run
    # must resolve to the installed distribution's version.
    assert sleap_roots_contracts.__version__ != "unknown"


def test_version_matches_pyproject():
    """__version__ resolves to pyproject.toml's declared version (no drift).

    pyproject.toml is the single source of truth. This is the real drift guard
    (the old hardcoded ``__version__`` literal made the metadata comparison a
    tautology): it fails if the installed metadata drifts from the declared
    version, e.g. a stale editable install or a bump that didn't reinstall.
    """
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if not pyproject.is_file():  # running from an installed wheel without the repo
        pytest.skip("pyproject.toml not available (installed wheel)")
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert sleap_roots_contracts.__version__ == declared
