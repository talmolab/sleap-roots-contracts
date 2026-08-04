"""Run-manifest contract: the run-scoping shape written by bloomctl.

Written by `bloomctl` (`salk-bloom`, staging branch) during `batch-download-for-predict`,
alongside the per-scan `{scan_key}.scan_metadata.json` sidecars it already writes into the
same shared staging directory. Read by `sleap-roots-predict` and `sleap-roots`-traits to scope
processing to exactly the `scan_keys` a run was given, instead of directory-wide-scanning
whatever sidecars happen to be present (see talmolab/sleap-roots-pipeline#37).
"""

from pydantic import BaseModel, ConfigDict, model_validator

_FROZEN = ConfigDict(frozen=True)

# Single source of truth for the manifest's on-disk filename, so bloomctl/predict/traits agree
# on it via import rather than each hardcoding the string.
RUN_MANIFEST_FILENAME = "run_manifest.json"


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
