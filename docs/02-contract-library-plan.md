# sleap-roots-contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sleap-roots-contracts`, a small Python library that defines the per-scan result + provenance contract (Pydantic models), emits a versioned JSON Schema artifact, and ships a trait-definitions registry — the shared spine for the sleap-roots ↔ Bloom integration.

**Architecture:** Pydantic v2 models are the single source of truth. Pure helpers compute a canonical-JSON `param_hash` and a deterministic `idempotency_key` (producer-side only; Bloom treats them as opaque). A schema-emitter renders `schema/*.json` with a snapshot drift-guard test. A YAML-backed trait-definitions registry drives name/dtype/range validation. Library distributed via PyPI; **no Docker/GHCR** (that rule is for the services).

**Tech Stack:** Python ≥3.11, uv + `uv_build`, Pydantic v2, PyYAML, pytest + pytest-cov, ruff + black, jsonschema (meta-validation), GitHub Actions (CI + PyPI trusted publishing).

**Spec:** [01-contract-library-design.md](./01-contract-library-design.md). **Repo to create:** `C:\repos\sleap-roots-contracts` (new git repo, separate from the vault; GitHub `talmolab/sleap-roots-contracts`).

**Conventions (mirror `sleap-roots-analyze`):** src layout `src/sleap_roots_contracts/`; tests in `tests/`; `uv run pytest -v`; `uv run black --check` + `uv run ruff check`; google docstring convention; GPL-3.0.

---

## File Structure

- `src/sleap_roots_contracts/__init__.py` — version + public re-exports
- `src/sleap_roots_contracts/hashing.py` — canonical JSON + `compute_param_hash`
- `src/sleap_roots_contracts/identity.py` — `compute_idempotency_key`
- `src/sleap_roots_contracts/models.py` — `ModelRef`, `InputRef`, `ResolvedParams`, `Provenance`, `TraitValue`, `BlobRef`, `ResultEnvelope`
- `src/sleap_roots_contracts/registry.py` — `TraitDefinition` + registry loader + validation
- `src/sleap_roots_contracts/trait_definitions.yaml` — seed registry data (shipped in package)
- `src/sleap_roots_contracts/schema.py` — schema emitter (`emit_schema()` + `__main__`)
- `schema/*.json` — emitted, committed artifacts (the drift-guard target)
- `tests/` — one test module per source module + `tests/fixtures/`
- `.github/workflows/ci.yml`, `.github/workflows/publish.yml`
- `openspec/`, `CLAUDE.md`, `.claude/commands/` (from `analyze` standard)

---

## Task 0: Repo scaffold + tooling baseline

**Files:**
- Create: `C:\repos\sleap-roots-contracts\pyproject.toml`
- Create: `src/sleap_roots_contracts/__init__.py`, `tests/__init__.py`, `README.md`, `LICENSE`, `.gitignore`
- Create: `.github/workflows/ci.yml`
- Create: `CLAUDE.md`, `openspec/` (via `openspec init`), `.claude/commands/tdd.md`

- [ ] **Step 1: Create and init the repo**

```bash
mkdir C:\repos\sleap-roots-contracts
git -C C:\repos\sleap-roots-contracts init
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "sleap-roots-contracts"
version = "0.1.0a0"
description = "Shared result + provenance contract for the sleap-roots <-> Bloom pipeline."
readme = "README.md"
license = "GPL-3.0-or-later"
authors = [{ name = "eberrigan", email = "eberrigan@salk.edu" }]
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.7",
    "pyyaml>=6.0",
]

[project.urls]
Homepage = "https://github.com/talmolab/sleap-roots-contracts"
Repository = "https://github.com/talmolab/sleap-roots-contracts"

[build-system]
requires = ["uv_build>=0.8.11,<0.9.0"]
build-backend = "uv_build"

[dependency-groups]
dev = [
    "pytest>=8.4.1",
    "pytest-cov>=6.2.1",
    "ruff>=0.12.11",
    "black>=25.1.0",
    "jsonschema>=4.23",
    "build>=1.3.0",
]

[tool.black]
line-length = 88

[tool.ruff.lint]
select = ["D"]

[tool.ruff.lint.pydocstyle]
convention = "google"
```

- [ ] **Step 3: Create package + test skeleton**

`src/sleap_roots_contracts/__init__.py`:
```python
"""Shared result + provenance contract for the sleap-roots <-> Bloom pipeline."""

__version__ = "0.1.0a0"
```

`tests/__init__.py`: empty file. `.gitignore`: standard Python (`.venv/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `dist/`, `.coverage`). `LICENSE`: GPL-3.0 text. `README.md`: one-paragraph purpose + `uv sync` / `uv run pytest` usage.

- [ ] **Step 4: Sync and smoke-test the toolchain**

Run: `uv sync` then `uv run python -c "import sleap_roots_contracts as c; print(c.__version__)"`
Expected: prints `0.1.0a0`.

- [ ] **Step 5: Write CI workflow** `.github/workflows/ci.yml`

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: uv sync
      - run: uv run black --check src tests
      - run: uv run ruff check src tests
      - run: uv run pytest --cov=src/sleap_roots_contracts --cov-report=term-missing -v
```

- [ ] **Step 6: Initialize OpenSpec (best-practice setup)**

The `openspec` CLI is installed globally (v0.13.0). Initialize non-interactively, configuring
the Claude tooling — this creates `openspec/{AGENTS.md, project.md, specs/, changes/}`, the
`<!-- OPENSPEC -->` managed block in `CLAUDE.md`, and the workflow slash commands
`.claude/commands/openspec/{proposal,apply,archive}.md`:

```bash
cd C:\repos\sleap-roots-contracts && openspec init . --tools claude
```

Verify: `openspec list` runs without error; `.claude/commands/openspec/proposal.md` exists.

- [ ] **Step 7: Fill `openspec/project.md`**

Replace the generated stub with this repo's real context (so proposals are grounded):
- **Purpose:** shared result + provenance contract for the sleap-roots ↔ Bloom pipeline (leaf library; producers import it, Bloom consumes its JSON Schema).
- **Tech stack:** Python ≥3.11, uv + `uv_build`, Pydantic v2, PyYAML, pytest+pytest-cov, ruff+black, jsonschema; distributed via PyPI (no Docker/GHCR).
- **Conventions:** src layout `src/sleap_roots_contracts/`; google docstrings; black line-length 88; `uv run pytest`; TDD; schema is generated and drift-guarded in CI; hashes are producer-side only (Bloom treats them as opaque).
- **Context:** part of the program in `C:\vaults\sleap-roots\bloom-pipeline-integration\` (sub-project #1 of 5).

- [ ] **Step 8: Add the reusable dev Claude commands**

Copy the **repo-agnostic** dev commands from `C:\repos\sleap-roots-analyze\.claude\commands\`
into `.claude/commands/`, then in each replace `sleap_roots_analyze` → `sleap_roots_contracts`
and delete any pipeline-specific steps (these are a pure library):

```
tdd.md  lint.md  coverage.md  black.md  run-ci-locally.md  pre-merge-check.md
review-openspec.md  review-pr.md  generate-pr-review.md  pr-description.md
update-changelog.md  prepare-release.md  cleanup-merged.md
```

**Do NOT copy** the analyze-only commands (`configure-run-all`, `cross-platform-summary`,
`dry-run`, `run-pipelines`, `validate-config`, `verify-results`). Together with the
`openspec/{proposal,apply,archive}` commands from Step 6, this is the full dev command set.

Verify each copied command body references `sleap_roots_contracts` (no stray `analyze` paths):
`uv run python -c "import pathlib,re; bad=[p for p in pathlib.Path('.claude/commands').rglob('*.md') if 'sleap_roots_analyze' in p.read_text()]; print('STRAY:', bad)"`
Expected: `STRAY: []`.

- [ ] **Step 9: Capture the build as an OpenSpec change (spec-driven)**

Create the first change so the implementation is spec-driven, not ad-hoc. Use the
`/openspec:proposal` command (or scaffold by hand) to create
`openspec/changes/add-result-provenance-contract/` with `proposal.md` (why + what),
`tasks.md` (mirroring Tasks 1–9 of this plan), and `specs/result-contract/spec.md` (the
capability: models, hashing, identity, registry, schema artifact). Then:

```bash
openspec validate add-result-provenance-contract --strict
```
Expected: validation passes. Tasks 1–9 below implement this change; `/openspec:apply` keeps
`tasks.md` in sync; `/openspec:archive` runs after merge.

- [ ] **Step 10: Commit the scaffold**

```bash
git add -A
git commit -m "chore: scaffold sleap-roots-contracts (uv, pytest, ruff, CI, openspec, dev commands)"
```

---

## Task 1: Canonical JSON + `compute_param_hash`

**Files:**
- Create: `src/sleap_roots_contracts/hashing.py`
- Test: `tests/test_hashing.py`

- [ ] **Step 1: Write the failing tests**

```python
import math
import pytest
from sleap_roots_contracts.hashing import compute_param_hash, NonCanonicalizableError


def test_hash_is_deterministic():
    v = {"species": "rice", "scale": 1.5}
    assert compute_param_hash(v) == compute_param_hash(v)


def test_hash_is_key_order_independent():
    assert compute_param_hash({"a": 1, "b": 2}) == compute_param_hash({"b": 2, "a": 1})


def test_hash_changes_with_value():
    assert compute_param_hash({"a": 1}) != compute_param_hash({"a": 2})


def test_hash_nested_key_order_independent():
    a = {"outer": {"x": 1, "y": 2}}
    b = {"outer": {"y": 2, "x": 1}}
    assert compute_param_hash(a) == compute_param_hash(b)


def test_hash_rejects_nan():
    with pytest.raises(NonCanonicalizableError):
        compute_param_hash({"a": math.nan})


def test_hash_rejects_inf():
    with pytest.raises(NonCanonicalizableError):
        compute_param_hash({"a": math.inf})


def test_hash_is_hex_sha256():
    h = compute_param_hash({"a": 1})
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_hashing.py -v`
Expected: FAIL with `ModuleNotFoundError: sleap_roots_contracts.hashing`.

- [ ] **Step 3: Implement** `src/sleap_roots_contracts/hashing.py`

```python
"""Canonical-JSON hashing for params (producer-side only; Bloom treats output as opaque)."""

import hashlib
import json
import math
from typing import Any


class NonCanonicalizableError(ValueError):
    """Raised when a value cannot be canonicalized (e.g. NaN/inf)."""


def _check_finite(obj: Any) -> None:
    """Recursively reject NaN/inf floats."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise NonCanonicalizableError(f"NaN/inf not allowed in hashed values: {obj}")
    elif isinstance(obj, dict):
        for value in obj.values():
            _check_finite(value)
    elif isinstance(obj, (list, tuple)):
        for value in obj:
            _check_finite(value)


def canonical_json(values: dict[str, Any]) -> str:
    """Serialize to deterministic JSON: sorted keys, compact, no NaN/inf."""
    _check_finite(values)
    return json.dumps(
        values, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def sha256_hex(text: str) -> str:
    """Return the hex sha256 of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_param_hash(values: dict[str, Any]) -> str:
    """Compute the canonical, deterministic hash of a resolved-params dict."""
    return sha256_hex(canonical_json(values))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_hashing.py -v` → Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/hashing.py tests/test_hashing.py
git commit -m "feat: canonical-JSON param hashing with NaN/inf rejection"
```

---

## Task 2: `compute_idempotency_key`

**Files:**
- Create: `src/sleap_roots_contracts/identity.py`
- Test: `tests/test_identity.py`

- [ ] **Step 1: Write the failing tests**

```python
from sleap_roots_contracts.identity import compute_idempotency_key

BASE = dict(
    scan_key="scan-1",
    images_checksum="img-abc",
    models=[("reg-primary", "v1", "wc1"), ("reg-lateral", "v2", None)],
    param_hash="ph-1",
    predict_code_sha="p-sha",
    traits_code_sha="t-sha",
)


def test_idempotency_is_deterministic():
    assert compute_idempotency_key(**BASE) == compute_idempotency_key(**BASE)


def test_idempotency_model_order_independent():
    reordered = {**BASE, "models": list(reversed(BASE["models"]))}
    assert compute_idempotency_key(**reordered) == compute_idempotency_key(**BASE)


def test_idempotency_handles_none_weights_checksum():
    # Must not raise when sorting models with a None weights_checksum.
    compute_idempotency_key(**BASE)


import pytest


@pytest.mark.parametrize(
    "field,newval",
    [
        ("scan_key", "scan-2"),
        ("images_checksum", "img-xyz"),
        ("param_hash", "ph-2"),
        ("predict_code_sha", "p-sha2"),
        ("traits_code_sha", "t-sha2"),
        ("models", [("reg-primary", "v9", "wc1")]),
    ],
)
def test_idempotency_sensitive_to_each_component(field, newval):
    changed = {**BASE, field: newval}
    assert compute_idempotency_key(**changed) != compute_idempotency_key(**BASE)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_identity.py -v` → Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement** `src/sleap_roots_contracts/identity.py`

```python
"""Deterministic idempotency-key derivation (producer-side only)."""

from .hashing import canonical_json, sha256_hex


def compute_idempotency_key(
    *,
    scan_key: str,
    images_checksum: str,
    models: list[tuple[str, str, str | None]],
    param_hash: str,
    predict_code_sha: str,
    traits_code_sha: str,
) -> str:
    """Derive the run identity from inputs, models, params, and code versions.

    Args:
        scan_key: Producer-side scan identifier.
        images_checksum: Checksum over the input image set.
        models: (registry_id, version, weights_checksum) per model; order-independent.
        param_hash: Output of compute_param_hash.
        predict_code_sha: Git sha of the predict producer.
        traits_code_sha: Git sha of the traits producer.

    Returns:
        Hex sha256 identity string.
    """
    model_keys = sorted(
        f"{registry_id}::{version}::{weights_checksum or ''}"
        for registry_id, version, weights_checksum in models
    )
    payload = {
        "scan_key": scan_key,
        "images_checksum": images_checksum,
        "models": model_keys,
        "param_hash": param_hash,
        "predict_code_sha": predict_code_sha,
        "traits_code_sha": traits_code_sha,
    }
    return sha256_hex(canonical_json(payload))
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_identity.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/identity.py tests/test_identity.py
git commit -m "feat: deterministic, order-independent idempotency key"
```

---

## Task 3: `ModelRef`, `InputRef`, `ResolvedParams`

**Files:**
- Create: `src/sleap_roots_contracts/models.py`
- Test: `tests/test_models_basic.py`

- [ ] **Step 1: Write the failing tests**

```python
import pytest
from pydantic import ValidationError
from sleap_roots_contracts.models import ModelRef, InputRef, ResolvedParams


def test_modelref_minimal():
    m = ModelRef(registry_id="r", version="v1", sleap_nn_version="0.1")
    assert m.root_type is None and m.weights_checksum is None


def test_modelref_full():
    m = ModelRef(registry_id="r", version="v1", sleap_nn_version="0.1",
                 root_type="primary", weights_checksum="abc")
    assert m.root_type == "primary"


def test_inputref_requires_images_checksum():
    with pytest.raises(ValidationError):
        InputRef(image_ids=["i1"])  # missing images_checksum


def test_resolvedparams_computes_hash_when_absent():
    p = ResolvedParams(values={"species": "rice"})
    assert len(p.param_hash) == 64


def test_resolvedparams_hash_matches_values():
    from sleap_roots_contracts.hashing import compute_param_hash
    vals = {"species": "rice", "scale": 2}
    assert ResolvedParams(values=vals).param_hash == compute_param_hash(vals)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_models_basic.py -v` → Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement (start of `models.py`)**

```python
"""Pydantic contract models — the canonical source of truth."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .hashing import compute_param_hash
from .identity import compute_idempotency_key


class ModelRef(BaseModel):
    """Identity of one model used in a run (FK-able to a future Bloom models table)."""

    registry_id: str
    version: str
    sleap_nn_version: str
    root_type: str | None = None
    weights_checksum: str | None = None


class InputRef(BaseModel):
    """Pins the input data a run consumed, for reproducibility."""

    image_ids: list[str]
    images_checksum: str


class ResolvedParams(BaseModel):
    """Fully-resolved run params plus their canonical hash."""

    values: dict[str, Any]
    param_hash: str = ""

    @model_validator(mode="after")
    def _fill_hash(self) -> "ResolvedParams":
        object.__setattr__(self, "param_hash", compute_param_hash(self.values))
        return self
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_models_basic.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/models.py tests/test_models_basic.py
git commit -m "feat: ModelRef, InputRef, ResolvedParams (auto param_hash)"
```

---

## Task 4: `Provenance` (auto-computes idempotency_key)

**Files:**
- Modify: `src/sleap_roots_contracts/models.py`
- Test: `tests/test_provenance.py`

- [ ] **Step 1: Write the failing tests**

```python
from sleap_roots_contracts.models import Provenance, ModelRef, InputRef, ResolvedParams
from sleap_roots_contracts.identity import compute_idempotency_key


def make_provenance(**overrides):
    base = dict(
        contract_version="0.1.0a0",
        scan_key="scan-1",
        inputs=InputRef(image_ids=["i1", "i2"], images_checksum="img-abc"),
        predict_models=[ModelRef(registry_id="r", version="v1", sleap_nn_version="0.1",
                                 root_type="primary")],
        predict_container_digest="sha256:pred",
        predict_code_sha="p-sha",
        traits_sleap_roots_version="1.0",
        traits_container_digest="sha256:tr",
        traits_code_sha="t-sha",
        params=ResolvedParams(values={"species": "rice"}),
    )
    base.update(overrides)
    return Provenance(**base)


def test_provenance_autofills_idempotency_key():
    p = make_provenance()
    expected = compute_idempotency_key(
        scan_key="scan-1",
        images_checksum="img-abc",
        models=[("r", "v1", None)],
        param_hash=p.params.param_hash,
        predict_code_sha="p-sha",
        traits_code_sha="t-sha",
    )
    assert p.idempotency_key == expected


def test_same_inputs_same_key():
    assert make_provenance().idempotency_key == make_provenance().idempotency_key


def test_changed_model_changes_key():
    other = make_provenance(predict_models=[
        ModelRef(registry_id="r", version="v2", sleap_nn_version="0.1", root_type="primary")])
    assert other.idempotency_key != make_provenance().idempotency_key


def test_orchestration_fields_optional():
    p = make_provenance()
    assert p.argo_workflow_uid is None and p.worker_request_id is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_provenance.py -v` → Expected: FAIL with `ImportError: cannot import name 'Provenance'`.

- [ ] **Step 3: Implement (append to `models.py`)**

```python
class Provenance(BaseModel):
    """Run provenance; serializes to the cyl_trait_sources.metadata jsonb (sub-project #2)."""

    contract_version: str
    scan_key: str
    inputs: InputRef
    idempotency_key: str = ""
    pipeline_run_id: str | None = None

    # predict stage
    predict_models: list[ModelRef]
    predict_container_digest: str
    predict_code_sha: str
    worker_request_id: str | None = None

    # traits stage
    traits_sleap_roots_version: str
    traits_container_digest: str
    traits_code_sha: str

    # orchestration (execution-model dependent)
    argo_workflow_uid: str | None = None
    argo_node_id: str | None = None

    params: ResolvedParams
    produced_at: datetime | None = None

    @model_validator(mode="after")
    def _fill_idempotency_key(self) -> "Provenance":
        key = compute_idempotency_key(
            scan_key=self.scan_key,
            images_checksum=self.inputs.images_checksum,
            models=[(m.registry_id, m.version, m.weights_checksum) for m in self.predict_models],
            param_hash=self.params.param_hash,
            predict_code_sha=self.predict_code_sha,
            traits_code_sha=self.traits_code_sha,
        )
        object.__setattr__(self, "idempotency_key", key)
        return self
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_provenance.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/models.py tests/test_provenance.py
git commit -m "feat: Provenance model with auto-derived idempotency_key"
```

---

## Task 5: `TraitValue` (NaN/inf → None) + `BlobRef` validators

**Files:**
- Modify: `src/sleap_roots_contracts/models.py`
- Test: `tests/test_trait_blob.py`

- [ ] **Step 1: Write the failing tests**

```python
import math
import pytest
from pydantic import ValidationError
from sleap_roots_contracts.models import TraitValue, BlobRef


def test_traitvalue_defaults_grain_scan():
    t = TraitValue(name="primary_length", value=12.5, scan_key="s1")
    assert t.grain == "scan"


def test_traitvalue_nan_becomes_none():
    assert TraitValue(name="x", value=math.nan, scan_key="s1").value is None


def test_traitvalue_inf_becomes_none():
    assert TraitValue(name="x", value=math.inf, scan_key="s1").value is None


def test_traitvalue_explicit_none_allowed():
    assert TraitValue(name="x", value=None, scan_key="s1").value is None


def test_blobref_requires_a_location():
    with pytest.raises(ValidationError):
        BlobRef(kind="predictions_slp", scan_key="s1")


def test_blobref_s3_only_ok():
    b = BlobRef(kind="predictions_slp", scan_key="s1", s3_location="s3://b/k")
    assert b.box_link is None


def test_blobref_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        BlobRef(kind="not_a_kind", scan_key="s1", s3_location="s3://b/k")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_trait_blob.py -v` → Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement (append to `models.py`)**

```python
import math


class TraitValue(BaseModel):
    """One long-format trait row. NaN/inf normalize to None (-> SQL NULL)."""

    name: str
    value: float | None = None
    grain: Literal["scan", "image"] = "scan"
    scan_key: str

    @model_validator(mode="after")
    def _normalize_nonfinite(self) -> "TraitValue":
        if self.value is not None and (math.isnan(self.value) or math.isinf(self.value)):
            object.__setattr__(self, "value", None)
        return self


BlobKind = Literal["predictions_slp", "labels", "h5", "qc_image"]


class BlobRef(BaseModel):
    """Pointer to an intermediate artifact (rows in the #2 intermediates table)."""

    kind: BlobKind
    scan_key: str
    s3_location: str | None = None
    box_link: str | None = None
    checksum: str | None = None
    file_size: int | None = None

    @model_validator(mode="after")
    def _require_location(self) -> "BlobRef":
        if self.s3_location is None and self.box_link is None:
            raise ValueError("BlobRef requires at least one of s3_location or box_link")
        return self
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_trait_blob.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/models.py tests/test_trait_blob.py
git commit -m "feat: TraitValue (NaN->None) and BlobRef (vocab + location validators)"
```

---

## Task 6: Trait definitions registry + name/dtype/range validation

**Files:**
- Create: `src/sleap_roots_contracts/registry.py`
- Create: `src/sleap_roots_contracts/trait_definitions.yaml`
- Test: `tests/test_registry.py`

> The YAML is the **seed**; it is expanded by enumerating `sleap_roots`'s computed traits (the
> upstream source of truth) in a follow-up. Default unknown-name behavior is **warn**, so an
> incomplete registry never blocks producers.

- [ ] **Step 1: Write the failing tests**

```python
import warnings
import pytest
from sleap_roots_contracts.registry import (
    TraitDefinition, load_registry, validate_trait,
)


def test_load_registry_has_entries():
    reg = load_registry()
    assert "primary_length" in reg
    assert isinstance(reg["primary_length"], TraitDefinition)


def test_known_trait_passes():
    reg = load_registry()
    validate_trait("primary_length", 10.0, reg)  # no raise


def test_unknown_trait_warns_by_default():
    reg = load_registry()
    with pytest.warns(UserWarning):
        validate_trait("totally_made_up_trait", 1.0, reg)


def test_unknown_trait_errors_when_strict():
    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("totally_made_up_trait", 1.0, reg, on_unknown="error")


def test_range_violation_errors():
    reg = load_registry()
    with pytest.raises(ValueError):
        validate_trait("lateral_count", -1.0, reg)  # count must be >= 0


def test_none_value_skips_range_check():
    reg = load_registry()
    validate_trait("lateral_count", None, reg)  # no raise
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_registry.py -v` → Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Create seed** `src/sleap_roots_contracts/trait_definitions.yaml`

```yaml
# Seed trait definitions. Source of truth for full population: the traits computed by
# `sleap_roots` (expand by enumerating its trait outputs). on_unknown defaults to "warn".
primary_length:
  unit: px
  dtype: float
  min: 0.0
  description: Length of the primary root.
lateral_count:
  unit: count
  dtype: int
  min: 0.0
  description: Number of lateral roots detected.
crown_angle:
  unit: deg
  dtype: float
  min: 0.0
  max: 360.0
  description: Crown root angle.
```

- [ ] **Step 4: Implement** `src/sleap_roots_contracts/registry.py`

```python
"""Trait definitions registry: name/dtype/range validation for trait values."""

import warnings
from importlib import resources
from typing import Literal

import yaml
from pydantic import BaseModel


class TraitDefinition(BaseModel):
    """Definition of a known trait."""

    unit: str
    dtype: Literal["float", "int"]
    description: str
    min: float | None = None
    max: float | None = None


def load_registry() -> dict[str, TraitDefinition]:
    """Load the packaged trait-definitions registry."""
    text = resources.files("sleap_roots_contracts").joinpath("trait_definitions.yaml").read_text()
    raw = yaml.safe_load(text) or {}
    return {name: TraitDefinition(**spec) for name, spec in raw.items()}


def validate_trait(
    name: str,
    value: float | None,
    registry: dict[str, TraitDefinition],
    on_unknown: Literal["warn", "error"] = "warn",
) -> None:
    """Validate a trait name + value against the registry.

    Raises:
        ValueError: unknown name (when on_unknown="error") or out-of-range value.
    """
    definition = registry.get(name)
    if definition is None:
        if on_unknown == "error":
            raise ValueError(f"Unknown trait: {name!r}")
        warnings.warn(f"Unknown trait not in registry: {name!r}", UserWarning, stacklevel=2)
        return
    if value is None:
        return
    if definition.min is not None and value < definition.min:
        raise ValueError(f"{name}={value} below min {definition.min}")
    if definition.max is not None and value > definition.max:
        raise ValueError(f"{name}={value} above max {definition.max}")
```

Add `"pyyaml>=6.0"` is already a dependency (Task 0). Ensure the YAML ships in the wheel — `uv_build` includes package data under `src/sleap_roots_contracts/` by default; verify in Task 9 build check.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_registry.py -v` → Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/sleap_roots_contracts/registry.py src/sleap_roots_contracts/trait_definitions.yaml tests/test_registry.py
git commit -m "feat: trait definitions registry with dtype/range validation"
```

---

## Task 7: `ResultEnvelope` + public exports

**Files:**
- Modify: `src/sleap_roots_contracts/models.py`, `src/sleap_roots_contracts/__init__.py`
- Test: `tests/test_envelope.py`

- [ ] **Step 1: Write the failing tests**

```python
from sleap_roots_contracts import (
    ResultEnvelope, Provenance, TraitValue, BlobRef, ModelRef, InputRef, ResolvedParams,
)


def _provenance():
    return Provenance(
        contract_version="0.1.0a0", scan_key="scan-1",
        inputs=InputRef(image_ids=["i1"], images_checksum="img-abc"),
        predict_models=[ModelRef(registry_id="r", version="v1", sleap_nn_version="0.1")],
        predict_container_digest="sha256:p", predict_code_sha="p",
        traits_sleap_roots_version="1.0", traits_container_digest="sha256:t", traits_code_sha="t",
        params=ResolvedParams(values={"species": "rice"}),
    )


def test_envelope_round_trips():
    env = ResultEnvelope(
        provenance=_provenance(),
        traits=[TraitValue(name="primary_length", value=1.0, scan_key="scan-1")],
        blobs=[BlobRef(kind="predictions_slp", scan_key="scan-1", s3_location="s3://b/k")],
    )
    restored = ResultEnvelope.model_validate_json(env.model_dump_json())
    assert restored.provenance.idempotency_key == env.provenance.idempotency_key
    assert restored.traits[0].name == "primary_length"


def test_public_exports_importable():
    # All core symbols importable from the package root.
    assert ResultEnvelope and Provenance and TraitValue and BlobRef
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_envelope.py -v` → Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement**

Append to `models.py`:
```python
class ResultEnvelope(BaseModel):
    """One per-scan result: 1 envelope : 1 source row : 1 scan."""

    provenance: Provenance
    traits: list[TraitValue]
    blobs: list[BlobRef] = []
```

Update `__init__.py`:
```python
"""Shared result + provenance contract for the sleap-roots <-> Bloom pipeline."""

from .models import (
    BlobRef, InputRef, ModelRef, Provenance, ResolvedParams, ResultEnvelope, TraitValue,
)
from .registry import TraitDefinition, load_registry, validate_trait

__version__ = "0.1.0a0"
__all__ = [
    "BlobRef", "InputRef", "ModelRef", "Provenance", "ResolvedParams", "ResultEnvelope",
    "TraitValue", "TraitDefinition", "load_registry", "validate_trait", "__version__",
]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_envelope.py -v` → Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/sleap_roots_contracts/models.py src/sleap_roots_contracts/__init__.py tests/test_envelope.py
git commit -m "feat: ResultEnvelope + public package exports"
```

---

## Task 8: Schema emitter + drift guard + meta-validation

**Files:**
- Create: `src/sleap_roots_contracts/schema.py`
- Create: `schema/` (emitted, committed)
- Test: `tests/test_schema.py`

- [ ] **Step 1: Implement the emitter** `src/sleap_roots_contracts/schema.py`

```python
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
    schema["$id"] = (
        f"https://github.com/talmolab/sleap-roots-contracts/schema/{name}.schema.json#v{__version__}"
    )
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def emit_schema() -> None:
    """Write all schemas to the schema/ directory."""
    SCHEMA_DIR.mkdir(exist_ok=True)
    for name in MODELS:
        (SCHEMA_DIR / f"{name}.schema.json").write_text(render(name), encoding="utf-8")


if __name__ == "__main__":
    emit_schema()
```

- [ ] **Step 2: Generate the committed artifact**

Run: `uv run python -m sleap_roots_contracts.schema`
Expected: creates `schema/result_envelope.schema.json`.

- [ ] **Step 3: Write the drift-guard + meta-validation tests** `tests/test_schema.py`

```python
import json
from pathlib import Path

import jsonschema
from sleap_roots_contracts.schema import render, MODELS, SCHEMA_DIR


def test_committed_schema_matches_models():
    # The drift guard: regenerating must equal what's committed.
    for name in MODELS:
        committed = (SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8")
        assert committed == render(name), (
            f"{name}.schema.json is stale; run `python -m sleap_roots_contracts.schema`"
        )


def test_emitted_schema_is_valid_jsonschema():
    for name in MODELS:
        schema = json.loads(render(name))
        jsonschema.Draft202012Validator.check_schema(schema)


def test_example_envelope_validates_against_schema():
    from tests.fixtures.examples import example_envelope
    schema = json.loads(render("result_envelope"))
    instance = json.loads(example_envelope().model_dump_json())
    jsonschema.validate(instance=instance, schema=schema)
```

- [ ] **Step 4: Create fixture** `tests/fixtures/__init__.py` (empty) and `tests/fixtures/examples.py`

```python
"""Shared example instances for tests."""

from sleap_roots_contracts import (
    BlobRef, InputRef, ModelRef, Provenance, ResolvedParams, ResultEnvelope, TraitValue,
)


def example_envelope() -> ResultEnvelope:
    """A representative, valid ResultEnvelope."""
    return ResultEnvelope(
        provenance=Provenance(
            contract_version="0.1.0a0", scan_key="scan-1",
            inputs=InputRef(image_ids=["i1", "i2"], images_checksum="img-abc"),
            predict_models=[ModelRef(registry_id="r", version="v1", sleap_nn_version="0.1",
                                     root_type="primary")],
            predict_container_digest="sha256:p", predict_code_sha="p",
            traits_sleap_roots_version="1.0", traits_container_digest="sha256:t",
            traits_code_sha="t", params=ResolvedParams(values={"species": "rice"}),
        ),
        traits=[TraitValue(name="primary_length", value=12.5, scan_key="scan-1")],
        blobs=[BlobRef(kind="predictions_slp", scan_key="scan-1", s3_location="s3://b/k")],
    )
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_schema.py -v` → Expected: PASS (3 tests).

- [ ] **Step 6: Wire the drift guard into CI**

Add to `.github/workflows/ci.yml` before the pytest step:
```yaml
      - run: uv run python -m sleap_roots_contracts.schema
      - run: git diff --exit-code schema/
```

- [ ] **Step 7: Commit**

```bash
git add src/sleap_roots_contracts/schema.py schema/ tests/test_schema.py tests/fixtures/ .github/workflows/ci.yml
git commit -m "feat: JSON Schema emitter with snapshot drift guard + meta-validation"
```

---

## Task 9: PyPI publish workflow + build verification

**Files:**
- Create: `.github/workflows/publish.yml`
- Test: local build check (manual)

- [ ] **Step 1: Verify the package builds and ships the YAML**

Run: `uv build` then
`uv run python -c "import zipfile,glob; w=glob.glob('dist/*.whl')[0]; print('trait_definitions.yaml' in '\n'.join(zipfile.ZipFile(w).namelist()))"`
Expected: prints `True` (confirms package data is bundled).

- [ ] **Step 2: Write the publish workflow** `.github/workflows/publish.yml`

```yaml
name: Publish
on:
  release:
    types: [published]
jobs:
  pypi:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write   # OIDC trusted publishing
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: { python-version: "3.12" }
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 3: Run the full quality suite**

Run: `uv run black --check src tests && uv run ruff check src tests && uv run pytest --cov=src/sleap_roots_contracts --cov-report=term-missing -v`
Expected: all green; coverage on `models.py`, `hashing.py`, `identity.py`, `registry.py`, `schema.py`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: PyPI trusted-publishing workflow on release"
```

- [ ] **Step 5: Push + open the OpenSpec change (process)**

Create the GitHub repo `talmolab/sleap-roots-contracts`, push `main`, and record this work as an OpenSpec change in-repo per `openspec/AGENTS.md` (proposal → tasks mirror this plan). Configure PyPI trusted publishing for the `pypi` environment.

---

## Self-Review

**Spec coverage** (against [01-contract-library-design.md](./01-contract-library-design.md)):
- §1 purpose / leaf lib → Tasks 0–9. §2 standalone repo → Task 0.
- §4 models: `Provenance`(T4), `InputRef`(T3), `ModelRef`+plural(T3/T4), `TraitValue` null policy(T5), `BlobRef` vocab+location(T5), `ResolvedParams`(T3), definitions registry(T6), `ResultEnvelope`(T7).
- §5 hashing/identity/opaque/validation → T1, T2, T6.
- §6 drift guard + versioned `$id` + PyPI publish → T8, T9.
- §7 deferred models table → documented in spec; no code here (correct).
- §8 testing surface → every task is TDD; T8 covers round-trip/snapshot/meta-validate/fixtures.
- §9 bootstrap (uv/pytest/openspec/CLAUDE/commands, **no Docker/GHCR**, PyPI) → T0, T9.

**Placeholder scan:** trait YAML is a deliberate seed (mechanism complete, warn-on-unknown), not a placeholder — flagged explicitly in T6. No TBD/TODO steps; all code steps show code.

**Type consistency:** `Provenance` field names (`predict_models`, `predict_code_sha`, `traits_code_sha`, `inputs.images_checksum`) match the idempotency call in T4 and the fixture in T8. `BlobKind` vocab matches the spec's `kind` list. `compute_param_hash`/`compute_idempotency_key`/`load_registry`/`validate_trait`/`render`/`emit_schema` names are consistent across tasks.
