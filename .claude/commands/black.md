# Black Code Formatting

Format Python code with [Black](https://black.readthedocs.io/), the uncompromising code formatter.

## Format Code

Format all Python files in `src` and `tests`:
```bash
uv run black src/sleap_roots_contracts tests
```

## Check Formatting (Dry Run)

Check if files would be reformatted without making changes:
```bash
uv run black --check src/sleap_roots_contracts tests
```

## Check and Show Diff

See what changes would be made:
```bash
uv run black --diff src/sleap_roots_contracts tests
```

## Configuration

Black is configured in `pyproject.toml`:
```toml
[tool.black]
line-length = 88
```

## VS Code Integration

To format on save in VS Code, add to `.vscode/settings.json`:
```json
{
    "python.formatting.provider": "black",
    "editor.formatOnSave": true
}
```

## Pre-commit Hook

To automatically format before commits, add to `.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        language_version: python3.11
```