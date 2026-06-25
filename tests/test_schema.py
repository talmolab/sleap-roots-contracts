"""Drift-guard and meta-validation tests for the emitted JSON Schema artifact."""

import json

import jsonschema
import pytest

from sleap_roots_contracts.schema import MODELS, SCHEMA_DIR, emit_schema, render


def test_committed_schema_matches_models():
    """The drift guard: regenerating must equal what's committed."""
    for name in MODELS:
        committed = (SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8")
        assert committed == render(name), (
            f"{name}.schema.json is stale; run "
            "`python -m sleap_roots_contracts.schema`"
        )


def test_emitted_schema_is_valid_jsonschema():
    """Each emitted schema is a valid Draft 2020-12 JSON Schema."""
    for name in MODELS:
        schema = json.loads(render(name))
        jsonschema.Draft202012Validator.check_schema(schema)


def test_emitted_schema_declares_draft_2020_12():
    """Each schema is self-describing as Draft 2020-12 via $schema."""
    for name in MODELS:
        schema = json.loads(render(name))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_id_carries_package_version():
    """Each emitted schema's $id embeds the live package __version__.

    The whole point of resolving __version__ from package metadata is that the
    schema $id tracks the released version. The drift guard alone cannot prove
    this (committed and rendered both derive from the same __version__), so
    assert the linkage directly.
    """
    import sleap_roots_contracts

    expected = f"/schema/v{sleap_roots_contracts.__version__}/"
    for name in MODELS:
        schema = json.loads(render(name))
        assert expected in schema["$id"]
        assert schema["$id"].endswith(f"/{name}.schema.json")


def test_render_refuses_unresolved_version(monkeypatch):
    """render() refuses to emit a 'vunknown' $id when the version is unresolved."""
    import sleap_roots_contracts.schema as schema_mod

    monkeypatch.setattr(schema_mod, "__version__", "unknown")
    with pytest.raises(RuntimeError, match="unresolved"):
        render("result_envelope")


def test_example_envelope_validates_against_schema():
    """A representative envelope validates against the emitted schema."""
    from tests.fixtures.examples import example_envelope

    schema = json.loads(render("result_envelope"))
    instance = json.loads(example_envelope().model_dump_json())
    jsonschema.Draft202012Validator(schema).validate(instance)


def test_emit_schema_accepts_explicit_dir(tmp_path):
    """emit_schema writes to a given directory, matching render() output."""
    emit_schema(tmp_path)
    for name in MODELS:
        written = (tmp_path / f"{name}.schema.json").read_text(encoding="utf-8")
        assert written == render(name)


def test_schema_rejects_blobref_without_location():
    """The emitted schema encodes BlobRef's at-least-one-location constraint."""
    from tests.fixtures.examples import example_envelope

    schema = json.loads(render("result_envelope"))
    instance = json.loads(example_envelope().model_dump_json())
    # Null out both blob locations -> Pydantic would reject; the schema must too.
    instance["blobs"][0]["s3_location"] = None
    instance["blobs"][0]["box_link"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(instance)
