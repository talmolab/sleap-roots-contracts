"""Drift-guard and meta-validation tests for the emitted JSON Schema artifact."""

import json

import jsonschema

from sleap_roots_contracts.schema import MODELS, SCHEMA_DIR, render


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


def test_example_envelope_validates_against_schema():
    """A representative envelope validates against the emitted schema."""
    from tests.fixtures.examples import example_envelope

    schema = json.loads(render("result_envelope"))
    instance = json.loads(example_envelope().model_dump_json())
    jsonschema.validate(instance=instance, schema=schema)
