"""Pure param-resolution oracle: Bloom scan metadata -> ``ResolvedParams``.

Maps a single Bloom ``cyl_scans_extended`` row (the dict bloomcli's download
writes to ``scans.csv``) to a ``ResolvedParams`` carrying ``species``, ``mode``,
and ``age`` -- the params that select a ``ModelCard`` (metadata -> params ->
model). The mapper is pure: no network access and no filesystem I/O, and it does
not mutate its input.

This module is the **single source of truth** for that mapping. Its resolved
values feed ``ResolvedParams.param_hash`` -> ``Provenance.idempotency_key``
(first-writer-wins), so two producers computing params differently would both
"win" the dedup race for the same logical scan, with no error raised anywhere.
Consumers (``sleap-roots-predict``, ``bloomctl``) import it rather than
reimplementing it.

Note the library's single **soft** coupling to Bloom's column vocabulary: the
load-bearing field names below are dict keys, hoisted into module constants so
the cross-repo coupling is explicit and greppable. There is no Bloom import and
no DB, network, or filesystem dependency -- this stays a dependency-light leaf.

The documented input is a *pandas-parsed* CSV row, so the guards here are written
against pandas/numpy scalars as well as Python builtins: a ``pandas.NA`` species
or a ``numpy.bool_`` age must fail loud rather than be coerced into a plausible
param and hashed. Sentinel detection is duck-typed rather than importing pandas,
which is an optional extra of this library.
"""

import math
import numbers
from typing import Any, Callable, Dict, Optional

from .models import ResolvedParams

# Bloom ``cyl_scans_extended`` column names (bloomcli's ``scans.csv``). Module
# constants so the cross-repo coupling to bloomcli's schema is explicit/greppable.
SPECIES_NAME_FIELD = "species_name"
PLANT_AGE_DAYS_FIELD = "plant_age_days"

# The types an age may arrive as. An allowlist, not a denylist: ``numpy.bool_`` is
# NOT a ``bool``/``int``/``numbers.Integral``, so a denylist of ``bool`` lets it
# through and ``int(np.bool_(True))`` silently yields age 1. ``numbers.Integral``
# admits ``numpy.int64`` (a pandas int column) and ``numbers.Real`` admits
# ``numpy.float64``; ``decimal.Decimal`` is deliberately excluded (it is neither,
# never arrives from CSV/pandas, and would bypass the whole-number float guard).
_AGE_TYPES = (int, float, str, numbers.Integral, numbers.Real)

# The resolvable param space; overrides are restricted to these keys.
_PARAM_KEYS = ("species", "mode", "age")

# Extension seam: Bloom ``species_name`` (lowercased) -> ``ModelCard`` species
# vocabulary, for names that do NOT lowercase cleanly to the card string (e.g. a
# Latin binomial). The seeded common names lowercase cleanly, so this ships
# empty; add lowercase-keyed entries only for genuine non-identity aliases.
_ALIASES: Dict[str, str] = {}


def _is_na_sentinel(value: Any) -> bool:
    """Return True for a missing-data sentinel, without importing pandas.

    Every such sentinel compares unequal to itself: ``float("nan")``,
    ``numpy.float64("nan")``, ``decimal.Decimal("NaN")``, and ``pandas.NaT`` all
    return ``True`` from ``value != value``. ``pandas.NA`` is the exception — its
    self-inequality is itself ``NA``, whose truth value is ambiguous and raises
    ``TypeError``. That raise is therefore *positive* evidence of an NA sentinel,
    not an error.

    Duck-typed on purpose: pandas is an optional extra of this library, so the
    check must not import it, yet a ``pandas`` row is the documented input shape.
    """
    try:
        return bool(value != value)
    except TypeError:
        return True


def _is_blank(value: Any) -> bool:
    """Return True for absent-like values: ``None``, a missing sentinel, or a blank string.

    Bloom metadata read from ``scans.csv`` may present a missing cell as an empty
    string (``csv``), a ``NaN`` (``pandas`` coerces a numeric column with any gap
    to ``float``), or — with nullable/arrow dtypes reached through a ``Series`` —
    a ``pandas.NA``/``pandas.NaT``. All of these, plus whitespace-only strings,
    are treated the same as an absent key.

    Note ``inf`` is NOT blank: an infinite age is a *bad* value, not a missing
    one, and is rejected by ``_coerce_age`` rather than silently dropped.
    """
    if value is None or _is_na_sentinel(value):
        return True
    return isinstance(value, str) and value.strip() == ""


def _normalize_text(value: Any, field: str) -> str:
    """Strip and lowercase a text value; blank/``None``/missing sentinel -> ``""``.

    A present but non-string value raises rather than being stringified. Every
    legitimate species and mode is text, so ``str(value)`` on a stray sentinel or
    number would mint a plausible-looking param (``pandas.NA`` -> ``"<na>"``,
    ``123`` -> ``"123"``) and hash it into ``idempotency_key`` with no error —
    silent corruption. ``numpy.str_`` subclasses ``str``, so pandas string columns
    pass through normally.

    Raises:
        ValueError: If ``value`` is present, non-blank, and not a string.
    """
    if _is_blank(value):
        return ""
    if not isinstance(value, str):
        raise ValueError(f"Scan param {field!r} must be a string, got {value!r}")
    return value.strip().lower()


def _normalize_species(name: Any) -> str:
    """Normalize a Bloom species_name to the ModelCard species vocabulary.

    Strips and lowercases the name, then applies the (lowercase-keyed) alias
    map with a lowercase passthrough fallback. Blank, ``None``, or missing-sentinel
    (``NaN``, ``pandas.NA``/``NaT``) inputs normalize to ``""`` so callers can
    treat them as not provided. Unknown species pass through rather than being
    rejected: the ``ModelCard`` registry is the single authority on which species
    have models, so an unmodelled species degrades to a selection zero-match, not
    an error.

    Raises:
        ValueError: If ``name`` is present, non-blank, and not a string.
    """
    key = _normalize_text(name, "species")
    return _ALIASES.get(key, key)


def _normalize_mode(mode: Any) -> str:
    """Normalize a mode string to the ModelCard mode vocabulary (strip+lower).

    Mirrors ``_normalize_species`` so a derived mode and an override mode
    canonicalize identically (representation-independent ``param_hash``). The
    seeded modes (``cylinder``, ``multiplant cylinder``) are already lowercase.

    Raises:
        ValueError: If ``mode`` is present, non-blank, and not a string.
    """
    return _normalize_text(mode, "mode")


def _mode_for_scan(metadata: Dict[str, Any]) -> str:
    """Return the imaging modality for a scan (the single mode-decision point).

    The cylinder pipeline yields cylinder scans only, so this returns
    ``"cylinder"``. GraviScan/multiscanner modes slot in here once their
    scanners and models exist; the returned string MUST match the exact seeded
    ``ModelCard`` mode vocabulary.
    """
    return "cylinder"


def _coerce_age(raw_age: Any) -> int:
    """Coerce a plant_age_days value to a whole number of days (int).

    Accepts an int (including ``numpy.int64``), a finite whole float (including
    ``numpy.float64``), or an int-coercible whole-number string. Everything else
    raises a ``ValueError`` naming ``age`` — so the resolved ``age`` (and
    therefore ``param_hash``) is never derived from a lossy or nonsensical
    conversion. Blank and missing-sentinel inputs are handled upstream (treated as
    absent), not here.

    Rejected explicitly, each of which would otherwise resolve silently or crash:

    * ``bool`` and ``numpy.bool_`` — ``int(True)`` is ``1``, a plausible age.
      ``numpy.bool_`` is not a ``bool`` subclass, so the allowlist, not an
      ``isinstance(..., bool)`` check alone, is what excludes it.
    * ``inf`` / ``-inf`` — ``int(float("inf"))`` raises ``OverflowError``, which is
      not the exception this contract promises.
    * ``decimal.Decimal`` — outside the allowlist; a fractional ``Decimal`` slips
      past the whole-number float guard and truncates.
    """
    if isinstance(raw_age, bool) or not isinstance(raw_age, _AGE_TYPES):
        raise ValueError(f"Scan param 'age' must be a whole number, got {raw_age!r}")
    # Gate finiteness on ``float`` (which ``numpy.float64`` subclasses), NOT on
    # ``numbers.Real``: ints are always finite, and ``math.isfinite`` on a very
    # large int raises OverflowError converting it to float.
    if isinstance(raw_age, float) and not math.isfinite(raw_age):
        raise ValueError(f"Scan param 'age' must be a whole number, got {raw_age!r}")
    try:
        age = int(raw_age)
    except (TypeError, ValueError, OverflowError) as e:
        raise ValueError(
            f"Scan param 'age' must be a whole number, got {raw_age!r}"
        ) from e
    if isinstance(raw_age, float) and float(age) != raw_age:
        raise ValueError(f"Scan param 'age' must be a whole number, got {raw_age!r}")
    return age


def _canonicalize_text(values: Dict[str, Any], key: str, normalizer: Callable) -> None:
    """Normalize ``values[key]`` in place; drop the key if it normalizes to blank."""
    if key not in values:
        return
    normalized = normalizer(values[key])
    if normalized:
        values[key] = normalized
    else:
        del values[key]


def resolve_params(
    metadata: Dict[str, Any],
    overrides: Optional[Dict[str, Any]] = None,
) -> ResolvedParams:
    """Resolve a Bloom scan-metadata row to ``ResolvedParams`` (species/mode/age).

    Args:
        metadata: A single Bloom ``cyl_scans_extended`` row — the shape
            bloomcli's download writes to ``scans.csv``. Load-bearing fields:
            ``species_name`` (-> ``species``), ``plant_age_days`` (-> ``age``,
            days); the scanner determines ``mode``. Other columns are ignored.
            A blank or absent load-bearing field (missing key, ``None``, ``NaN``,
            or an empty/whitespace-only string) is treated as not provided.
        overrides: Optional param-space dict whose keys are a subset of
            ``{"species", "mode", "age"}``. Each key wins its field over the
            derived value; override values are normalized/coerced by the same
            rules as derived values so ``param_hash`` is representation-
            independent.

    Returns:
        A ``ResolvedParams`` whose ``values`` contain ``species``, ``mode``, and
        ``age``; the contract computes ``param_hash``.

    Raises:
        ValueError: If an override key is not in ``{"species", "mode", "age"}``;
            if a present ``plant_age_days`` (or ``age`` override) is not a whole
            number; or if ``species``, ``mode``, or ``age`` is still missing
            after merging overrides.
    """
    overrides = overrides or {}
    unknown = set(overrides) - set(_PARAM_KEYS)
    if unknown:
        raise ValueError(
            f"Unknown override key(s): {sorted(unknown)}; "
            f"allowed keys are {list(_PARAM_KEYS)}"
        )

    # Tolerant read: mode always; species/age only when present and non-blank.
    # Absent/blank fields are omitted, deferring to overrides then validation.
    values: Dict[str, Any] = {"mode": _mode_for_scan(metadata)}
    if not _is_blank(metadata.get(SPECIES_NAME_FIELD)):
        values["species"] = metadata[SPECIES_NAME_FIELD]
    if not _is_blank(metadata.get(PLANT_AGE_DAYS_FIELD)):
        values["age"] = metadata[PLANT_AGE_DAYS_FIELD]

    values = {**values, **overrides}  # override wins, per field

    # Canonicalize derived OR override values identically so param_hash is
    # representation-independent; a blank value is treated as absent (dropped ->
    # named by the validation below).
    _canonicalize_text(values, "species", _normalize_species)
    _canonicalize_text(values, "mode", _normalize_mode)
    if "age" in values:
        if _is_blank(values["age"]):
            del values["age"]
        else:
            values["age"] = _coerce_age(values["age"])

    missing = [key for key in _PARAM_KEYS if key not in values]
    if missing:
        raise ValueError(f"Missing required scan param(s): {missing}")

    return ResolvedParams(values=values)
