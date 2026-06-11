from importlib.metadata import version

import sleap_roots_contracts


def test_version_exposed():
    """__version__ is a string and agrees with the installed package metadata."""
    assert isinstance(sleap_roots_contracts.__version__, str)
    assert sleap_roots_contracts.__version__ == version("sleap-roots-contracts")
