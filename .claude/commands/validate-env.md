# Validate Development Environment

Check that the dev environment is correctly set up. Run after cloning, after dependency
changes, when imports/tests fail unexpectedly, or after switching machines.

## Checks

```bash
# 1. uv installed
uv --version

# 2. Python matches the project (uv manages it from requires-python / .python-version)
uv run python --version

# 3. Dependencies synced from the lockfile (creates/uses .venv)
uv sync
uv tree            # all deps resolve from uv.lock

# 4. Import smoke test
uv run python -c "import sleap_roots_contracts as c; print('OK', c.__version__)"

# 5. Tests run
uv run pytest -q
```

## Common fixes
- **uv not found** → `curl -LsSf https://astral.sh/uv/install.sh | sh` (Windows:
  `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`).
- **Deps not synced / import errors** → `uv sync` (or rebuild: `Remove-Item -Recurse -Force .venv; uv sync`).
- **`VIRTUAL_ENV` mismatch warning** → harmless; another venv is active but `uv run` uses the
  project `.venv`.

## Notes
This is a pure library — no Git LFS, no test-data fixtures to download (unlike `sleap-roots`).
If those are ever added, extend this command with LFS pointer + data-presence checks.
