"""Emit versioned JSON Schema artifacts from the Pydantic models."""

import json
from pathlib import Path

from . import __version__
from .models import ResultEnvelope


def _default_schema_dir() -> Path:
    """Locate the repo's ``schema/`` dir for the producer-side emitter.

    Walks up from this file for the directory containing ``pyproject.toml`` (the
    repo root in a source checkout / CI); falls back to the current working
    directory when none is found (e.g. when the package is pip-installed, where a
    ``parents[2]`` guess would land on an unwritable site-packages path).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent / "schema"
    return Path.cwd() / "schema"


SCHEMA_DIR = _default_schema_dir()
MODELS = {"result_envelope": ResultEnvelope}


def render(name: str) -> str:
    """Render one schema as a deterministic JSON string."""
    schema = MODELS[name].model_json_schema()
    # Make the artifact self-describing so consumers (and jsonschema.validate)
    # select the intended dialect instead of defaulting to Draft 7.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    # Carry the package version as a path segment (not a URI fragment): JSON Schema
    # Draft 2020-12 forbids a non-empty fragment in "$id".
    schema["$id"] = (
        "https://github.com/talmolab/sleap-roots-contracts/schema/"
        f"v{__version__}/{name}.schema.json"
    )
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def emit_schema(schema_dir: Path | None = None) -> None:
    """Write all schemas to ``schema_dir`` (defaults to the repo's ``schema/``)."""
    target = schema_dir if schema_dir is not None else SCHEMA_DIR
    target.mkdir(parents=True, exist_ok=True)
    for name in MODELS:
        (target / f"{name}.schema.json").write_text(render(name), encoding="utf-8")


if __name__ == "__main__":
    emit_schema()
