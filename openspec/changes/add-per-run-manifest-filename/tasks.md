## 1. Implementation

- [ ] 1.1 `run_manifest_filename` with path-component validation —
      `uv run pytest tests/test_run_manifest.py -k run_manifest_filename -v`
- [ ] 1.2 `pipeline_run_id_from_env`, `PIPELINE_RUN_ID_ENV_VAR`, `run_manifest_name_for_writing` —
      `uv run pytest tests/test_run_manifest.py -k "from_env or name_for_writing or env_var_name" -v`
- [ ] 1.3 `read_run_manifest` + `RunManifestRead` + `RunManifestMissingError` —
      `uv run pytest tests/test_run_manifest.py -k read_run_manifest -v`
- [ ] 1.4 `check_run_manifest_identity` + `RunManifestIdentityError` + package-root exports —
      `uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
- [ ] 1.5 Module docstring + `docs/CHANGELOG.md` entry —
      `uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
- [ ] 1.6 Correct two false claims in `openspec/project.md`; describe the new API there and in
      `README.md`; tick these tasks —
      `openspec validate add-per-run-manifest-filename --strict && uv run pytest -q && uv run black --check src tests && uv run ruff check src tests`
