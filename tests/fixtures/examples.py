"""Shared example instances for tests."""

from sleap_roots_contracts import (
    BlobRef,
    InputRef,
    ModelRef,
    Provenance,
    ResolvedParams,
    ResultEnvelope,
    TraitValue,
)


def example_envelope() -> ResultEnvelope:
    """A representative, valid ResultEnvelope."""
    return ResultEnvelope(
        provenance=Provenance(
            contract_version="0.1.0a0",
            scan_key="scan-1",
            inputs=InputRef(image_ids=["i1", "i2"], images_checksum="img-abc"),
            predict_models=[
                ModelRef(
                    registry_id="r",
                    version="v1",
                    sleap_nn_version="0.1",
                    root_type="primary",
                )
            ],
            predict_container_digest="sha256:p",
            predict_code_sha="p",
            traits_sleap_roots_version="1.0",
            traits_container_digest="sha256:t",
            traits_code_sha="t",
            params=ResolvedParams(values={"species": "rice"}),
        ),
        traits=[TraitValue(name="primary_length", value=12.5, scan_key="scan-1")],
        blobs=[
            BlobRef(kind="predictions_slp", scan_key="scan-1", s3_location="s3://b/k")
        ],
    )
