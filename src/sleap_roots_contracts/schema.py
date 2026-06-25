"""Emit versioned JSON Schema artifacts from the Pydantic models."""

import json
from pathlib import Path

from . import __version__
from .analysis_input import AnalysisInputRow
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
MODELS = {
    "result_envelope": ResultEnvelope,
    "analysis_input": AnalysisInputRow,
}


def _normalize_single_value_enums(node: object) -> object:
    """Rewrite single-value ``const`` to a one-element ``enum`` in place.

    Pydantic renders a single-value ``Literal`` (e.g. ``BlobKind =
    Literal["predictions_slp"]``) as JSON Schema ``const``, but a multi-value
    ``Literal`` renders as ``enum``. Consumers treat a contract's controlled
    vocabulary as an ``enum`` set regardless of cardinality (Bloom keys on
    ``BlobRef.kind``'s enum), so normalize ``const`` -> one-element ``enum`` for a
    uniform "allowed set" shape that does not change when a vocabulary narrows to
    one value.
    """
    if isinstance(node, dict):
        if "const" in node:
            node["enum"] = [node.pop("const")]
        for value in node.values():
            _normalize_single_value_enums(value)
    elif isinstance(node, list):
        for item in node:
            _normalize_single_value_enums(item)
    return node


def render(name: str) -> str:
    """Render one schema as a deterministic JSON string."""
    schema = _normalize_single_value_enums(MODELS[name].model_json_schema())
    # Make the artifact self-describing so consumers (and jsonschema.validate)
    # select the intended dialect instead of defaulting to Draft 7.
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    # The $id embeds the package version. If the package isn't installed,
    # __version__ falls back to "unknown" (see __init__.py) — refuse rather than
    # emit a poisoned ".../vunknown/..." $id (the byte Bloom keys on). CI always
    # installs first; this turns a confusing downstream drift-guard failure into
    # a clear, local error.
    if __version__ == "unknown":
        raise RuntimeError(
            "refusing to emit a schema with an unresolved package version; "
            "install the package (e.g. `uv sync`) before regenerating"
        )
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
