"""Emit versioned JSON Schema artifacts from the Pydantic models."""

import json
from pathlib import Path

from . import __version__
from .models import ResultEnvelope

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
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


def emit_schema() -> None:
    """Write all schemas to the schema/ directory."""
    SCHEMA_DIR.mkdir(exist_ok=True)
    for name in MODELS:
        (SCHEMA_DIR / f"{name}.schema.json").write_text(render(name), encoding="utf-8")


if __name__ == "__main__":
    emit_schema()
