## 1. Implementation

- [ ] 1.1 `run_manifest_filename` with path-component validation — validate with
      `uv run pytest tests/test_run_manifest.py -k run_manifest_filename -v`
- [ ] 1.2 `pipeline_run_id_from_env` — validate with
      `uv run pytest tests/test_run_manifest.py -k pipeline_run_id_from_env -v`
- [ ] 1.3 `resolve_run_manifest_name` + `RunManifestMissingError` — validate with
      `uv run pytest tests/test_run_manifest.py -k resolve -v`
- [ ] 1.4 `check_run_manifest_identity` + `RunManifestIdentityError` + package-root exports —
      validate with `uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
- [ ] 1.5 Module docstring, `docs/CHANGELOG.md` entry, tick these tasks — validate with
      `openspec validate add-per-run-manifest-filename --strict`
