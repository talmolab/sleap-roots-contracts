"""Run-manifest contract: the run-scoping shape written by bloomctl.

Written by `bloomctl` (`salk-bloom`, staging branch) during `batch-download-for-predict`,
alongside the per-scan `{scan_key}.scan_metadata.json` sidecars it already writes into the
same shared staging directory. Read by `sleap-roots-predict` and `sleap-roots`-traits to scope
processing to exactly the `scan_keys` a run was given, instead of directory-wide-scanning
whatever sidecars happen to be present (see talmolab/sleap-roots-pipeline#37).
"""

import os
import re
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, model_validator

_FROZEN = ConfigDict(frozen=True)

# Single source of truth for the manifest's on-disk filename, so bloomctl/predict/traits agree
# on it via import rather than each hardcoding the string.
RUN_MANIFEST_FILENAME = "run_manifest.json"

# The per-run filename's fixed parts. `RUN_MANIFEST_FILENAME` stays the legacy/local name; the
# two forms can never collide, because a valid run id is non-empty and may not begin with a dot.
_FILENAME_PREFIX = "run_manifest."
_FILENAME_SUFFIX = ".json"

# A run id becomes a path component and arrives from an environment variable, so it is validated
# against an allowlist rather than by blocking known-bad characters. An Argo workflow name is an
# RFC-1123 label (lowercase alphanumerics and '-'); bloomctl's non-Argo placeholder is
# `local-<hex8>`. Requiring an alphanumeric first character is what rejects "." and ".." and a
# leading dash without special-casing any of them.
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

# 255 is NAME_MAX on the Linux filesystems this runs on; the wrapper costs 18 characters. This is
# below Kubernetes' own 253-character object-name limit, so a maximally long workflow name is
# rejected rather than silently truncated — Argo's generateName emits about 26, so the gap is
# theoretical, and a loud ValueError beats an unwritable filename.
_RUN_ID_MAX_LENGTH = 255 - len(_FILENAME_PREFIX) - len(_FILENAME_SUFFIX)


def run_manifest_filename(pipeline_run_id: str) -> str:
    """Return the per-run manifest filename for ``pipeline_run_id``.

    Args:
        pipeline_run_id: The run identity, e.g. an Argo ``{{workflow.name}}``.

    Returns:
        ``"run_manifest.<pipeline_run_id>.json"``.

    Raises:
        ValueError: If ``pipeline_run_id`` is not usable as a single path component — not a
            string, empty, over ``_RUN_ID_MAX_LENGTH`` characters, or not matching the
            module's run-id pattern (it must start with a letter or digit and contain only
            letters, digits, ``.``, ``_`` and ``-``). Raised rather than sanitized: a silently
            rewritten id would name a file no other stage in the run would look for.
    """
    if not isinstance(pipeline_run_id, str):
        raise ValueError(
            f"pipeline_run_id must be a str, got {type(pipeline_run_id).__name__}"
        )
    if len(pipeline_run_id) > _RUN_ID_MAX_LENGTH:
        raise ValueError(
            f"pipeline_run_id is {len(pipeline_run_id)} characters, over the "
            f"{_RUN_ID_MAX_LENGTH} limit that keeps the filename within NAME_MAX"
        )
    if not _RUN_ID_PATTERN.fullmatch(pipeline_run_id):
        raise ValueError(
            f"pipeline_run_id {pipeline_run_id!r} is not usable as a filename component: "
            "it must start with a letter or digit and contain only letters, digits, "
            "'.', '_' and '-'"
        )
    return f"{_FILENAME_PREFIX}{pipeline_run_id}{_FILENAME_SUFFIX}"


#: The environment variable every pipeline stage reads its run identity from. Set to Argo's
#: `{{workflow.name}}` on the four stage templates that touch the manifest — images-downloader,
#: predictor, trait-extractor and write-back — and deliberately absent from the `local-WSL2-*`
#: templates, which is what keeps local runs on the legacy filename. The fifth cluster template,
#: exit-gate, does not set it and does not read the manifest. Exported so consumers import it
#: rather than hardcoding the string.
PIPELINE_RUN_ID_ENV_VAR = "ARGO_WORKFLOW_NAME"


def pipeline_run_id_from_env(env: Mapping[str, str] | None = None) -> str | None:
    """Return this process's run identity, or ``None`` when it has none.

    The single definition of "which run am I". Both writers and readers must use it: a writer
    that reads the variable itself can disagree with a reader about whitespace or blankness,
    and :func:`check_run_manifest_identity` would then fail on every stage.

    Args:
        env: Environment mapping to read. Defaults to ``os.environ``. Injectable so callers and
            tests need no monkeypatching.

    Returns:
        The stripped value of ``ARGO_WORKFLOW_NAME``, or ``None`` when unset or blank. ``None``
        means "not running under orchestration"; it is not an error.
    """
    source = os.environ if env is None else env
    value = source.get(PIPELINE_RUN_ID_ENV_VAR)
    if value is None:
        return None
    return value.strip() or None


def run_manifest_name_for_writing(pipeline_run_id: str | None) -> str:
    """Return the filename a writer should publish its manifest under.

    Args:
        pipeline_run_id: This run's identity, from :func:`pipeline_run_id_from_env`.

    Returns:
        The per-run filename when an identity is known, else ``RUN_MANIFEST_FILENAME``. Keying
        per-run naming to the presence of an identity is what leaves local and ``local-WSL2-*``
        runs on exactly their previous behavior, with no template changes.

    Raises:
        ValueError: If ``pipeline_run_id`` is not usable as a filename component.
    """
    if pipeline_run_id is None:
        return RUN_MANIFEST_FILENAME
    return run_manifest_filename(pipeline_run_id)


class RunManifest(BaseModel):
    """Run-scoping manifest: the run identity plus the exact scan_keys it covers.

    Attributes:
        schema_version: Version of this manifest shape.
        pipeline_run_id: Identifier of the run/workflow this manifest scopes (e.g. an Argo
            `{{workflow.name}}`-style string). Required — a manifest with no run identity
            would defeat the point of scoping.
        scan_keys: The producer-side scan identifiers (e.g. `"scan_1009"`) this run is scoped
            to process. Deliberately `str`, matching every other scan identifier in this
            library and what `sleap-roots-predict`'s `discover_scans` actually keys off — not
            Bloom's internal integer `scan_id` (see design.md; this is the bloom#555 boundary).
    """

    model_config = _FROZEN

    schema_version: str = "1"
    pipeline_run_id: str
    scan_keys: list[str]

    @model_validator(mode="after")
    def _check_scan_keys(self) -> "RunManifest":
        """Reject an empty list, duplicate entries, or a blank/whitespace-only element.

        Duplicate detection is exact-match, not whitespace-normalized: the sole documented
        producer (`bloomctl`'s `scan_key_for()`, `f"scan_{scan_id}"`) can never emit a
        `scan_key` with incidental whitespace, so two entries differing only by whitespace
        are treated as distinct rather than silently deduplicated.
        """
        value = self.scan_keys
        if not value:
            raise ValueError("scan_keys must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("scan_keys must not contain duplicates")
        if any(not key.strip() for key in value):
            raise ValueError(
                "scan_keys must not contain a blank or whitespace-only entry"
            )
        return self
