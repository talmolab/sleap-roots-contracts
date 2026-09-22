"""Run-manifest contract: the run-scoping shape written by bloomctl.

Written by `bloomctl` (`salk-bloom`, staging branch) during `batch-download-for-predict`,
alongside the per-scan `{scan_key}.scan_metadata.json` sidecars it already writes into the
same shared staging directory. Read by `sleap-roots-predict` and `sleap-roots`-traits to scope
processing to exactly the `scan_keys` a run was given, instead of directory-wide-scanning
whatever sidecars happen to be present (see talmolab/sleap-roots-pipeline#37).

Since 0.1.0a9 the manifest may also be named per run — ``run_manifest.<pipeline_run_id>.json``,
built by :func:`run_manifest_filename` — so runs sharing an output directory no longer share a
manifest. ``RUN_MANIFEST_FILENAME`` remains the name used when a stage has no run identity (no
``ARGO_WORKFLOW_NAME``), which keeps local and ``local-WSL2-*`` runs on their previous
behavior. :func:`read_run_manifest` is the single definition of how a reader chooses between
the two, what a missing manifest means, and when the legacy name is still acceptable; see
talmolab/sleap-roots-pipeline#71.
"""

import errno
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

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


class RunManifestError(Exception):
    """Base for this module's *resolution and identity* failures.

    Exactly two: :class:`RunManifestMissingError` and :class:`RunManifestIdentityError`.
    It is **not** the base of every failure this module raises — an unusable
    ``pipeline_run_id`` raises a bare ``ValueError`` and a missing directory raises
    ``FileNotFoundError``, and neither derives from this class. A consumer that must catch
    everything therefore catches ``RunManifestError``, ``ValueError`` and ``OSError``.

    Deliberately not a ``ValueError``. Pydantic's ``ValidationError`` is one, and consumers
    already wrap manifest parsing in ``except ValueError`` — inheriting from it would let a
    generic parse handler swallow "this tree is not the one you think it is".
    """


class RunManifestMissingError(RunManifestError, LookupError):
    """No run manifest was found for a caller that knows which run it is.

    Also a ``LookupError`` so a consumer can catch it alongside its own not-found handling
    while still re-raising it as that repo's own error type (``click.ClickException`` in
    bloomctl, for instance).
    """


class RunManifestIdentityError(RunManifestError):
    """A manifest read under a per-run filename names a different run.

    Deliberately **not** a ``ValueError``, unlike a parse failure. A malformed manifest and a
    manifest belonging to someone else are different problems with different responses, and
    consumers wrap parsing in handlers that catch ``ValueError`` (pydantic's
    ``ValidationError`` is one). Sharing that base would let a generic parse handler swallow
    the stronger signal.
    """


class RunManifestRead(NamedTuple):
    """One manifest read: where it came from, its bytes, its mode, and which convention.

    Consumers SHOULD use attribute access rather than tuple unpacking, so that fields can be
    appended without breaking them.

    Attributes:
        filename: The name actually read, so a forwarding stage can republish under it.
        data: The raw bytes, returned rather than a path so there is no window in which the
            file changes between being found and being read.
        mode: The source file's permission bits, taken by ``fstat`` on the descriptor already
            open — so it describes the bytes returned, not whatever is at that path later. A
            forwarding stage needs it: ``mkstemp`` creates at ``0600``, and the next container
            runs as a different uid on the same shared mount.
        is_per_run: Whether ``filename`` is the per-run form. Consumers use it to decide
            whether the identity cross-check applies, instead of each comparing against
            ``RUN_MANIFEST_FILENAME`` themselves.
    """

    filename: str
    data: bytes
    mode: int
    is_per_run: bool


def read_run_manifest(
    directory: str | Path,
    pipeline_run_id: str | None,
    *,
    allow_legacy: bool,
) -> RunManifestRead | None:
    """Read the run manifest this caller should use, if there is one.

    Candidate order depends on whether a run identity exists:

    * With one — the per-run filename, then ``RUN_MANIFEST_FILENAME`` if ``allow_legacy``.
    * Without one — ``RUN_MANIFEST_FILENAME`` alone, **regardless of** ``allow_legacy``,
      because with no identity that name is not a legacy fallback but the correct name
      (design §2.3). Gating it would silently unscope every local run when the fleet flips.

    Each candidate is *opened*, not probed: only a candidate that is *genuinely absent*
    advances to the next one, and that is a condition on the path rather than the exception
    type. ``open()`` raises ``FileNotFoundError`` both for a candidate that does not exist
    and for one that exists as a **dangling symlink** — the link is present, its target is
    not — so the exception alone cannot tell the two apart. A candidate that exists as a
    symlink therefore raises ``FileNotFoundError`` naming that path rather than advancing: a
    dangling link is a broken tree, not an absent candidate, and advancing past it would hand
    this run an older run's scope through the legacy name.

    Args:
        directory: Directory to look in. Not searched recursively. Its own absence raises
            ``FileNotFoundError`` naming the directory, rather than being reported as a
            missing manifest — under Argo a mis-mounted stage-in is the likelier cause.
        pipeline_run_id: This run's identity, or ``None`` (see
            :func:`pipeline_run_id_from_env`). A blank string is **not** ``None``: it is an
            invalid id and raises ``ValueError``.
        allow_legacy: Whether a caller that *knows its own identity* may accept a manifest
            written under the identity-less name. Required and keyword-only, with no default,
            so every call site states its position and the fleet's migration state is
            greppable. Pass ``True`` while any stage may still be writing the legacy name;
            pass ``False`` once the fleet is migrated and the stale files are deleted, which
            is what makes the missing-manifest error reachable at all. Ignored when
            ``pipeline_run_id`` is ``None``.

    Returns:
        A :class:`RunManifestRead`, or ``None`` when nothing was found and
        ``pipeline_run_id`` is ``None``.

    Raises:
        RunManifestMissingError: If ``pipeline_run_id`` is not ``None`` and no candidate was
            found. Deliberately not ``None``: every consumer treats an absent manifest as
            "discover everything here", which under a shared output tree means processing and
            ingesting other runs' scans. A stage that knows its run id is running under
            orchestration, where a manifest is always written, so its absence is a fault.
        ValueError: If ``pipeline_run_id`` is not usable as a filename component.
        OSError: Any failure other than the candidate being genuinely absent — notably
            ``PermissionError`` and a dangling-symlink candidate.
    """
    base = Path(directory)

    candidates: list[tuple[str, bool]] = []
    if pipeline_run_id is None:
        # No identity: the legacy name is the right name, not a fallback, so `allow_legacy`
        # has no say. Gating it here would unscope every non-Argo run at design §4 step 6.
        candidates.append((RUN_MANIFEST_FILENAME, False))
    else:
        candidates.append((run_manifest_filename(pipeline_run_id), True))
        if allow_legacy:
            candidates.append((RUN_MANIFEST_FILENAME, False))

    for name, is_per_run in candidates:
        try:
            with (base / name).open("rb") as handle:
                data = handle.read()
                mode = os.fstat(handle.fileno()).st_mode & 0o777
        except FileNotFoundError as exc:
            # Distinguish "this candidate is absent" from "the directory is not there" —
            # both are FileNotFoundError, and only the first should advance.
            if not base.is_dir():
                raise FileNotFoundError(
                    errno.ENOENT,
                    "run manifest directory does not exist",
                    # `as_posix()` here and in the missing-manifest message below, so the two
                    # render the same path the same way. It is a plain `str`, which is what
                    # the three-arg form's filename slot wants, and on the POSIX filesystems
                    # this runs on it is identical to `str(base)`.
                    base.as_posix(),
                ) from exc
            if (base / name).is_symlink():
                # `is_symlink()` uses `lstat`, so it is True for a DANGLING link — the link
                # itself exists, only its target does not. `open()` raises the same
                # `FileNotFoundError` for that as for a genuinely absent candidate, so the
                # exception type alone cannot tell them apart. A dangling link is a broken
                # tree, not an absent candidate, and advancing past it would hand this run
                # an older run's scope through the legacy name — exactly the silent foreign
                # scope that opening rather than probing exists to prevent.
                raise FileNotFoundError(
                    errno.ENOENT,
                    "run manifest is a symlink with a missing target",
                    (base / name).as_posix(),
                ) from exc
            continue
        return RunManifestRead(
            filename=name, data=data, mode=mode, is_per_run=is_per_run
        )

    if pipeline_run_id is not None:
        looked_for = ", ".join(repr(name) for name, _ in candidates)
        raise RunManifestMissingError(
            f"no run manifest for run {pipeline_run_id!r} in {base.as_posix()}: "
            f"looked for {looked_for}"
        )
    return None


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


def check_run_manifest_identity(
    manifest: RunManifest,
    pipeline_run_id: str | None,
    read: RunManifestRead,
) -> None:
    """Verify a per-run-named manifest names the run that is reading it.

    A no-op unless ``read.is_per_run``: the legacy name carries no run identity, and before
    per-run naming the producer overwrote ``pipeline_run_id`` on every merge, so a legacy
    file routinely names some earlier run. Callers may therefore pass whatever
    :func:`read_run_manifest` returned without testing the name themselves.

    The decision is taken from ``read.is_per_run`` rather than re-derived by comparing
    ``read.filename`` — :func:`read_run_manifest` already knows which candidate it opened,
    and a second derivation would be a second source of truth that disagrees the moment a
    caller holds anything but a bare filename.

    ``pipeline_run_id=None`` with a non-per-run read needs no branch of its own. A caller with
    no identity only ever gets ``is_per_run=False`` from :func:`read_run_manifest` — without an
    identity the per-run filename is never a candidate — so the check no-ops, letting the
    natural read → parse → check call chain pass its ``str | None`` id straight through.
    ``pipeline_run_id=None`` with ``read.is_per_run`` true is a different case: that
    combination can never come from :func:`read_run_manifest`, so it indicates a caller bug —
    a hand-built or mismatched :class:`RunManifestRead` — rather than a foreign manifest, and
    raises ``ValueError`` rather than :class:`RunManifestIdentityError`; the latter would tell
    a consumer to escalate a tree problem that is actually a bug in the calling code.

    For a per-run-named file this is the cross-check bloom#703 asked for, possible for the
    first time.

    Args:
        manifest: The parsed manifest.
        pipeline_run_id: The reader's own run identity, or ``None`` when it has none (see
            :func:`pipeline_run_id_from_env`).
        read: The :class:`RunManifestRead` the manifest was parsed from. ``is_per_run``
            decides whether the check applies; ``filename`` is used only in the error
            message.

    Returns:
        None.

    Raises:
        ValueError: If ``pipeline_run_id`` is ``None`` and ``read.is_per_run`` is true — a
            combination :func:`read_run_manifest` never produces, so it is a caller bug.
        RunManifestIdentityError: If a per-run-named manifest names a different run.
    """
    if not read.is_per_run:
        return
    if pipeline_run_id is None:
        raise ValueError(
            "a caller with no run identity cannot have read a per-run manifest; "
            f"{read.filename!r} was reported as per-run"
        )
    if manifest.pipeline_run_id != pipeline_run_id:
        raise RunManifestIdentityError(
            f"{read.filename} was read as run {pipeline_run_id!r}'s manifest but names run "
            f"{manifest.pipeline_run_id!r}"
        )
