"""Pydantic contract models — the canonical source of truth."""

import math
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from .hashing import compute_param_hash
from .identity import compute_idempotency_key

# Contract models are immutable: derived fields (param_hash, idempotency_key) and
# normalized values are guaranteed correct for the life of the instance, so the
# validators below use object.__setattr__ to set them past the frozen guard.
_FROZEN = ConfigDict(frozen=True)


def _reject_bool(v: Any) -> Any:
    """Reject a bool before it is coerced to an int.

    Catches ``numpy.bool_`` as well as the builtin. ``numpy.bool_`` is **not** a
    ``bool`` subclass, so an ``isinstance(v, bool)`` check alone lets it through and
    pydantic's lax mode then reads it as ``1``/``0`` — the same trap
    ``params._coerce_age`` documents and defends against with an allowlist. Numpy is
    not a dependency of this library, so the check is duck-typed on the ``.item()``
    scalar-unwrap protocol rather than importing numpy or matching a type name.

    The unwrap is gated on scalar-ness (``ndim == 0``, absent on non-array duck types)
    so a *container* of bools is not described as one: ``np.array([True])`` falls
    through to pydantic's accurate "not a valid integer", the same error a container
    of ints gets. Any ``.item()`` that raises falls through to the raw value rather
    than propagating, so this guard can only ever produce a ``ValidationError``.

    Args:
        v: The raw input value for an integer field.

    Returns:
        The *original* ``v``, unchanged, whenever it is not a bool — never the
        unwrapped scalar. The unwrap exists only to answer "is this a bool?"; handing
        pydantic the unwrapped value instead would make this guard a silent coercion
        step (``np.int64(7)`` would arrive as a Python ``int``) rather than a check.

    Raises:
        ValueError: If ``v`` is a builtin ``bool`` or unwraps to one.
    """
    unwrapped = v
    if not isinstance(v, bool) and hasattr(v, "item") and getattr(v, "ndim", 0) == 0:
        try:
            unwrapped = v.item()
        # Deliberately broad: this guard's only job is to decide "is this a bool?",
        # and any answer it cannot get must become a ValidationError downstream, not
        # an exception type no caller of model_validate is catching.
        except Exception:
            unwrapped = v
    if isinstance(unwrapped, bool):
        raise ValueError(
            f"expected an integer, got a bool ({v!r}); bools are rejected rather than "
            "coerced to 1/0 because a silently plausible count is worse than a failure"
        )
    return v


# An int field that will not swallow a bool. Python's `bool` is a subclass of `int`,
# so pydantic's lax mode coerces True/False to 1/0 — a card would then validate and
# read a plausible-but-wrong number (True as a node_count even satisfies the
# skeleton-coherence check against a single node name). LabelCard is unusually exposed:
# #11 backfills from legacy wandb metadata stored as boolean-key soup, and
# `extra="ignore"` makes field validation the only defense. BeforeValidator runs ahead
# of int parsing, so ordinary lax inputs ("7", 7.0) are untouched.
#
# Applied to every integer field on LabelCard and to ModelCard's age bounds. The
# ModelCard half landed in a follow-up change (still 0.1.0a6,
# tighten-model-card-validation): it tightens validation on a contract already shipped
# in 0.1.0a3, so it was kept out of the otherwise purely additive change that
# introduced this alias. Both ride the same unreleased 0.1.0a6.
NonBoolInt = Annotated[int, BeforeValidator(_reject_bool)]


class ModelRef(BaseModel):
    """Identity of one model used in a run (FK-able to a future Bloom models table)."""

    model_config = _FROZEN

    registry_id: str
    version: str
    sleap_nn_version: str
    root_type: str | None = None
    weights_checksum: str | None = None


class InputRef(BaseModel):
    """Pins the input data a run consumed, for reproducibility."""

    model_config = _FROZEN

    image_ids: list[str]
    images_checksum: str


class ResolvedParams(BaseModel):
    """Fully-resolved run params plus their canonical hash."""

    model_config = _FROZEN

    values: dict[str, Any]
    param_hash: str = ""

    @model_validator(mode="after")
    def _fill_hash(self) -> "ResolvedParams":
        computed = compute_param_hash(self.values)
        if self.param_hash and self.param_hash != computed:
            raise ValueError(
                f"param_hash {self.param_hash!r} does not match values "
                f"(computed {computed!r})"
            )
        object.__setattr__(self, "param_hash", computed)
        return self


class Provenance(BaseModel):
    """Run provenance; serializes to cyl_trait_sources.metadata jsonb (sub-project #2)."""

    model_config = _FROZEN

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

    # Effective predict inference config. `predict_inference_config` is the FULL
    # config recorded for audit (including hardware/throughput knobs like device and
    # batch_size) and is NEVER hashed. `predict_output_params` is the output-defining
    # subset (e.g. peak_threshold) that participates in `idempotency_key`. Both are
    # optional; when `predict_output_params` is absent/empty the key is byte-identical
    # to the pre-existing derivation. Producers keep hardware knobs out of
    # `predict_output_params` (the library records it as given and does not enforce
    # the partition).
    predict_inference_config: dict[str, Any] | None = None
    predict_output_params: dict[str, Any] | None = None

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
            models=[
                (m.registry_id, m.version, m.weights_checksum)
                for m in self.predict_models
            ],
            param_hash=self.params.param_hash,
            predict_code_sha=self.predict_code_sha,
            traits_code_sha=self.traits_code_sha,
            predict_output_params=self.predict_output_params,
        )
        if self.idempotency_key and self.idempotency_key != key:
            raise ValueError(
                f"idempotency_key {self.idempotency_key!r} does not match derived "
                f"value (computed {key!r})"
            )
        object.__setattr__(self, "idempotency_key", key)
        return self


class TraitValue(BaseModel):
    """One long-format trait row. NaN/inf normalize to None (-> SQL NULL)."""

    model_config = _FROZEN

    name: str
    value: float | None = None
    grain: Literal["scan", "image"] = "scan"
    scan_key: str

    @model_validator(mode="after")
    def _normalize_nonfinite(self) -> "TraitValue":
        if self.value is not None and (
            math.isnan(self.value) or math.isinf(self.value)
        ):
            object.__setattr__(self, "value", None)
        return self


# The pipeline produces exactly one SLEAP .slp prediction file per root type per
# scan; no other artifact kinds exist in this contract's world. (viewer_html is
# deferred; traits_csv is excluded — trait numbers are TraitValue rows, not blobs.)
BlobKind = Literal["predictions_slp"]

# Controlled vocabulary for a root type. Required on BlobRef (every predictions
# artifact names the root type it carries). ModelRef.root_type is deliberately
# left as a loose `str | None` registry pointer — see the change's design.md.
RootType = Literal["primary", "lateral", "crown"]

# Controlled vocabulary for a capture mode. Owned here (not in training's chooser)
# so the label registry and the model registry share one spelling — the `cylinder`
# vs `cyl` split across the two registries is exactly the defect issue #10 fixes.
# Expressed as a Literal, mirroring RootType, rather than a frozenset. Required on
# both cards: LabelCard since 0.1.0a6, ModelCard.mode as of the same release (it
# shipped as a loose `str` in 0.1.0a3). Matched exactly — neither card normalizes
# case or whitespace. Normalizing a *requested* mode is resolve_params' job
# (params.py:_normalize_mode), and an unmodelled value is specified to degrade to a
# selection zero-match there rather than an error; the cards are the authoritative
# side and fail loudly instead.
Mode = Literal["cylinder", "multiplant cylinder", "plate"]


# Defined after both vocabularies on purpose: this module has no `from __future__
# import annotations`, so the `mode: Mode` and `root_type: RootType` fields and the
# `-> ModelRef` return annotation are evaluated at class-definition time and every
# name must already exist (RootType and Mode are the binding constraints; ModelRef,
# defined far above, is never at risk). So ModelCard must come *after* both; it is placed as
# close to them as the vocabulary block allows. Conceptually ModelCard is a
# model-registry sibling of ModelRef.
class ModelCard(BaseModel):
    """Model-selection metadata + identity for one production model.

    Written by ``sleap-roots-training`` at promotion (the selection fields, as flat
    wandb artifact metadata) and read by ``sleap-roots-predict`` to choose a model
    per root type. The fields come from two sources:

    * **Selection fields** — written by training as flat wandb metadata keys:
      ``species``, ``mode``, ``age_min``, ``age_max``, ``root_type`` (and optionally
      the trained-with ``sleap_nn_version``). ``mode`` and ``root_type`` are the
      contract-owned :data:`Mode` and :data:`RootType` vocabularies, matched exactly:
      a card carrying the label registry's ``cyl`` shorthand — or a cased
      ``Cylinder`` — fails at construction rather than silently never matching a scan.
    * **Identity fields** — intrinsic to the wandb artifact object, *not* metadata:
      ``registry_id``, ``version``, ``weights_checksum``. Predict's registry lister
      composes these from the artifact and merges them with the metadata before
      validating, so a bare ``model_validate(training_metadata)`` cannot build a full
      card (it lacks the identity fields).

    ``age_min``/``age_max`` is the *approved selection window*, curated at promotion
    (it MAY be set wider than the raw training ages to cover the data people actually
    scan). It is inclusive and assumed **contiguous** (``[age_min, age_max]``;
    non-contiguous approved sets are not expressible). The card never observes a
    scan's age — running a model outside its window is handled by predict's explicit
    override, not by this contract.

    Extra keys are ignored, so a card validates straight from a raw wandb metadata
    blob (boolean tag flags, the spread training config, eval metrics) merged with the
    artifact identity. ``extra="ignore"`` is set explicitly (not merely relied on as
    pydantic's default) because tolerating that blob is a load-bearing contract here —
    a future ``extra="forbid"`` would silently break predict's registry lister.

    The counterweight to that tolerance: both age bounds are :data:`NonBoolInt`, so a
    ``True`` from the same boolean-key blob is rejected rather than coerced to a
    plausible-but-wrong window bound. Ordinary lax parsing (``"7"``, ``7.0``) is
    unaffected.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    # selection dimensions (training-written metadata)
    species: str
    mode: Mode
    age_min: NonBoolInt = Field(ge=0)
    age_max: NonBoolInt = Field(ge=0)
    root_type: RootType

    # identity of the concrete production artifact (artifact-intrinsic)
    registry_id: str
    version: str
    weights_checksum: str | None = None

    # trained-with sleap-nn version; optional — used only for predict's mismatch
    # warning (present -> predict can warn; absent -> predict skips the warning).
    sleap_nn_version: str | None = None

    @model_validator(mode="after")
    def _check_age_range(self) -> "ModelCard":
        if self.age_min > self.age_max:
            raise ValueError(
                f"age_min ({self.age_min}) must be <= age_max ({self.age_max})"
            )
        return self

    def to_model_ref(self, runtime_sleap_nn_version: str) -> ModelRef:
        """Build a fully-pinned ``ModelRef``, stamping the RUNTIME sleap-nn version.

        The runtime version (what actually runs inference) is pinned into
        ``ModelRef.sleap_nn_version``, so that required field is always satisfied
        regardless of whether the card carried a trained-with value. Predict compares
        the card's trained-with value against the runtime version and warns on
        mismatch; this method is pure and does not warn.

        Args:
            runtime_sleap_nn_version: The sleap-nn version actually running inference.

        Returns:
            A ``ModelRef`` carrying the card's ``registry_id``, ``version``,
            ``root_type``, and ``weights_checksum``, with the runtime version stamped.
        """
        return ModelRef(
            registry_id=self.registry_id,
            version=self.version,
            sleap_nn_version=runtime_sleap_nn_version,
            root_type=self.root_type,
            weights_checksum=self.weights_checksum,
        )


# Defined after Mode and RootType (same definition-order constraint as ModelCard:
# no `from __future__ import annotations` in this module, so the `mode: Mode` and
# `root_type: RootType` field annotations are evaluated at class-definition time and
# both names must already exist). LabelCard is the label-registry mirror of ModelCard.
class LabelCard(BaseModel):
    """Label-selection metadata + identity for one labeling package.

    The provenance mirror of ``ModelCard``: a queryable, typed card for the label
    artifacts in ``wandb-registry-sleap-roots-labels``. Written by the
    ``/build-labeling-package`` workflow (which already computes this metadata and
    currently discards it at publish) and read by training/lineage tooling to answer
    "where did these labels come from?" — the question the registry's boolean-key
    metadata soup cannot answer today (issue #10).

    Fields come in five groups (see the change's design.md field table):

    * **Selection** — ``species``, ``mode``, ``root_type``, ``age_min``, ``age_max``.
      ``mode`` is the contract-owned :data:`Mode` vocabulary, so a card rejects ``cyl``
      at construction; ``[age_min, age_max]`` is inclusive and contiguous, as on
      ``ModelCard``.
    * **Skeleton** — ``skeleton_name``, ``node_count``, ``node_names``. ``node_count``
      must equal ``len(node_names)`` (Task 3 validator); ``node_names`` is a tuple so it
      stays immutable in substance under ``frozen``.
    * **Content** — the per-package counts (``n_frames``, ``n_instances``, ``n_plants``,
      ``n_scans``) and ``images_embedded`` (records the ~10x storage state, does not
      change it). ``n_frames`` is cross-checked against ``sample_manifest.csv`` row
      count in training's publish path, not here — this library takes no filesystem I/O.
    * **Provenance** — best-effort trace fields. All optional: the Bloom-trace fields
      (``source_experiment``, ``bloom_experiment_id``, ``accessions``), ``labeler``, and
      ``box_link`` are not recoverable from the legacy collections' metadata, so requiring
      them would gate #11's as-is backfill (resolved with Elizabeth, Slack 2026-07-21).
      ``source_sha256`` replaces the broken ``data_path`` (unusable in all eight
      collections) — Optional on the contract, but always computed over the ``.slp``
      bytes and passed in the publish path. ``sleap_io_version`` mirrors
      ``ModelCard.sleap_nn_version``.
    * **Registry identity** — ``registry_id``, ``version``, intrinsic to the wandb
      artifact object (not metadata), merged in before validation.

    Extra keys are ignored, so a card validates straight from a raw wandb metadata blob
    (the legacy boolean tag flags like ``{"v007": true, "4nodes": true}`` merged with
    artifact identity, plus a stale ``data_path``). ``extra="ignore"`` is set explicitly
    (not merely relied on as pydantic's default) because tolerating that blob is what
    makes #11's backfill tractable — a future ``extra="forbid"`` would break it.

    The counterweight to that tolerance: every integer field is :data:`NonBoolInt`, so a
    bool from the same blob is rejected rather than coerced to ``1``/``0``. Ordinary lax
    parsing (``"7"``, ``7.0``) is unaffected.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    # selection dimensions
    species: str
    mode: Mode
    root_type: RootType
    age_min: NonBoolInt = Field(ge=0)
    age_max: NonBoolInt = Field(ge=0)

    # skeleton (node_count == len(node_names) enforced by a model validator)
    skeleton_name: str
    node_count: NonBoolInt = Field(ge=1)
    node_names: tuple[str, ...]

    # content counts
    n_frames: NonBoolInt = Field(ge=0)
    n_instances: NonBoolInt = Field(ge=0)
    n_plants: NonBoolInt = Field(ge=0)
    n_scans: NonBoolInt = Field(ge=0)
    images_embedded: bool

    # provenance — all best-effort, optional so #11's as-is backfill isn't gated on
    # metadata unrecoverable for the eight legacy collections (design.md, Risks).
    source_experiment: str | None = None
    bloom_experiment_id: str | None = None
    accessions: tuple[str, ...] | None = None
    labeler: str | None = None
    box_link: str | None = None
    # Optional on the contract, but the publish path always computes it over the .slp
    # bytes and passes it — the contract can't read files (design.md, publish-path
    # decisions). Replaces the broken data_path.
    #
    # Named for its algorithm, unlike the algorithm-agnostic ModelCard.weights_checksum.
    # Deliberate: weights_checksum is copied off the wandb artifact object, where the
    # digest algorithm is wandb's implementation detail and not ours to promise, while
    # this digest is computed by our own publish path with a pinned algorithm — so the
    # name is the promise a consumer can verify against.
    source_sha256: str | None = None
    sleap_io_version: str | None = None

    # identity of the concrete label artifact (artifact-intrinsic)
    registry_id: str
    version: str

    @model_validator(mode="after")
    def _check_age_range(self) -> "LabelCard":
        # Mirrors ModelCard._check_age_range; [age_min, age_max] is inclusive, so
        # age_min == age_max (a single-age window) is valid.
        if self.age_min > self.age_max:
            raise ValueError(
                f"age_min ({self.age_min}) must be <= age_max ({self.age_max})"
            )
        return self

    @model_validator(mode="after")
    def _check_skeleton_coherence(self) -> "LabelCard":
        # The declared node_count must match the actual node_names tuple; the error
        # names both so a mismatch is diagnosable from the message alone.
        if self.node_count != len(self.node_names):
            raise ValueError(
                f"node_count ({self.node_count}) must equal "
                f"len(node_names) ({len(self.node_names)})"
            )
        return self


# Single source of truth for BlobRef's "at least one location" rule: both the
# emitted JSON Schema constraint and the runtime validator derive from this, so a
# field rename can't leave the schema and the model out of sync.
_BLOB_LOCATION_FIELDS = ("s3_location", "box_link")


def _blob_location_anyof() -> dict:
    """Build the at-least-one-location ``anyOf`` from the location field names.

    Each branch requires one location field and constrains it to a (non-null)
    string, so an all-null object is rejected by the schema exactly as the model
    validator rejects it.
    """
    return {
        "anyOf": [
            {"required": [field], "properties": {field: {"type": "string"}}}
            for field in _BLOB_LOCATION_FIELDS
        ]
    }


class BlobRef(BaseModel):
    """Pointer to an intermediate artifact (rows in the #2 intermediates table)."""

    # Encode the "at least one location" rule in the emitted JSON Schema so
    # consumers (Bloom codegen) reject the same objects Pydantic does.
    model_config = ConfigDict(frozen=True, json_schema_extra=_blob_location_anyof())

    kind: BlobKind
    root_type: RootType
    scan_key: str
    s3_location: str | None = None
    box_link: str | None = None
    checksum: str | None = None
    file_size: int | None = None

    @model_validator(mode="after")
    def _require_location(self) -> "BlobRef":
        if all(getattr(self, field) is None for field in _BLOB_LOCATION_FIELDS):
            raise ValueError(
                "BlobRef requires at least one of " + " or ".join(_BLOB_LOCATION_FIELDS)
            )
        return self


class ResultEnvelope(BaseModel):
    """One per-scan result: 1 envelope : 1 source row : 1 scan."""

    model_config = _FROZEN

    provenance: Provenance
    traits: list[TraitValue]
    blobs: list[BlobRef] = []
