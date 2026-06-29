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


def test_blobref_schema_narrows_kind_and_requires_root_type():
    """The emitted BlobRef reflects the narrowed kind and the root_type vocabulary."""
    defs = json.loads(render("result_envelope"))["$defs"]["BlobRef"]
    assert defs["properties"]["kind"]["enum"] == ["predictions_slp"]
    # Bloom keys on `properties.kind.enum`; a raw single-value Literal would emit
    # `const` and KeyError their extraction. Assert the normalization held.
    assert "const" not in defs["properties"]["kind"]
    assert "root_type" in defs["required"]
    assert set(defs["properties"]["root_type"]["enum"]) == {
        "primary",
        "lateral",
        "crown",
    }


def test_normalize_rewrites_scalar_const_to_one_element_enum():
    """A scalar const becomes a one-element enum (the single-value Literal case)."""
    from sleap_roots_contracts.schema import _normalize_single_value_enums

    assert _normalize_single_value_enums({"const": "x", "type": "string"}) == {
        "enum": ["x"],
        "type": "string",
    }


def test_normalize_preserves_falsy_scalar_consts():
    """Key presence, not truthiness: False / None / 0 are still rewritten."""
    from sleap_roots_contracts.schema import _normalize_single_value_enums

    assert _normalize_single_value_enums({"const": False}) == {"enum": [False]}
    assert _normalize_single_value_enums({"const": None}) == {"enum": [None]}
    assert _normalize_single_value_enums({"const": 0}) == {"enum": [0]}


def test_normalize_leaves_multivalue_enum_untouched():
    """An existing multi-value enum is not disturbed."""
    from sleap_roots_contracts.schema import _normalize_single_value_enums

    node = {"enum": ["a", "b", "c"], "type": "string"}
    assert _normalize_single_value_enums(dict(node)) == node


def test_normalize_does_not_clobber_coexisting_enum():
    """A node carrying both const and enum keeps its enum (no silent clobber)."""
    from sleap_roots_contracts.schema import _normalize_single_value_enums

    out = _normalize_single_value_enums({"const": "x", "enum": ["y"]})
    assert out["enum"] == ["y"]


def test_normalize_ignores_non_scalar_const_and_const_named_keys():
    """A non-scalar const (or a node whose child is named 'const') is left alone."""
    from sleap_roots_contracts.schema import _normalize_single_value_enums

    # const with a dict value is not a single-value Literal node.
    assert _normalize_single_value_enums({"const": {"a": 1}}) == {"const": {"a": 1}}
    # A property literally named "const" must not be renamed/corrupted; only the
    # inner scalar-const leaf is normalized.
    out = _normalize_single_value_enums(
        {"properties": {"const": {"const": "x", "type": "string"}}}
    )
    assert out == {"properties": {"const": {"enum": ["x"], "type": "string"}}}


def test_normalize_recurses_into_nested_const():
    """Scalar consts nested under dicts/lists are rewritten (recursion works)."""
    from sleap_roots_contracts.schema import _normalize_single_value_enums

    out = _normalize_single_value_enums({"anyOf": [{"const": "x"}, {"type": "null"}]})
    assert out == {"anyOf": [{"enum": ["x"]}, {"type": "null"}]}


def test_normalize_is_idempotent():
    """Normalizing an already-normalized schema is a no-op."""
    from sleap_roots_contracts.schema import _normalize_single_value_enums

    once = json.loads(render("result_envelope"))
    twice = _normalize_single_value_enums(json.loads(json.dumps(once)))
    assert twice == once


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
