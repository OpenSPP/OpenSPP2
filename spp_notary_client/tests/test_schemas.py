# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for tolerant Notary Pydantic schemas."""

from spp_notary_client.services.schemas import (
    CatalogResponse,
    ClaimRef,
    EvaluateRequest,
    EvidenceEntity,
    EvidenceIdentifier,
)


def test_catalog_response_accepts_minimal_payload_and_extra_fields():
    """Exact upstream schema is not fixed yet, so responses tolerate extra data."""
    catalog = CatalogResponse.model_validate(
        {
            "claims": [
                {
                    "id": "disability-severity-code",
                    "title": "Disability severity",
                    "value": {"type": "string"},
                    "disclosure": {"default": "value", "allowed": ["value", "redacted"]},
                    "future_field": {"kept": True},
                }
            ],
            "future_top_level": "kept",
        }
    )

    assert catalog.claims[0].id == "disability-severity-code"
    assert catalog.claims[0].value_type == "string"
    assert catalog.claims[0].default_disclosure == "value"
    assert catalog.claims[0].allowed_disclosures == ["value", "redacted"]
    assert catalog.claims[0].model_extra["future_field"] == {"kept": True}
    assert catalog.model_extra["future_top_level"] == "kept"


def test_evaluate_request_serializes_bare_claim_ids_until_claim_versions_land():
    """Bare claim IDs stay bare, while ClaimRef objects keep version detail."""
    bare = EvaluateRequest(
        target=EvidenceEntity(type="Person", id="NATIONAL-ID-123"),
        claims=["disability-severity-code"],
        purpose="https://openspp.example/purpose",
    )
    versioned = EvaluateRequest(
        target=EvidenceEntity(
            type="Person",
            identifiers=[EvidenceIdentifier(scheme="national_id", value="NATIONAL-ID-123")],
        ),
        claims=[ClaimRef(id="disability-severity-code", version="2026-01")],
        purpose="https://openspp.example/purpose",
    )

    assert bare.model_dump(exclude_none=True)["target"]["id"] == "NATIONAL-ID-123"
    assert bare.model_dump(exclude_none=True)["claims"] == ["disability-severity-code"]
    assert versioned.model_dump(exclude_none=True)["target"]["identifiers"][0] == {
        "scheme": "national_id",
        "value": "NATIONAL-ID-123",
    }
    assert versioned.model_dump(exclude_none=True)["claims"] == [
        {"id": "disability-severity-code", "version": "2026-01"}
    ]
