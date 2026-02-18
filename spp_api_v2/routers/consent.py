# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Consent API Router - GDPR-compliant consent management.

Provides endpoints for:
- Checking consent status
- Revoking consent (as easy as giving it per GDPR Art 7.3)
- Generating consent receipts
- Viewing consent history and access logs
"""

import logging
import uuid
from datetime import datetime
from typing import Annotated

from odoo import fields as odoo_fields

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from ..middleware.auth import get_current_client
from ..schemas.consent import (
    ConsentAccessSummarySchema,
    ConsentHistoryEntrySchema,
    ConsentHistoryResponse,
    ConsentReceiptSchema,
    ConsentRevokeRequest,
    ConsentRevokeResponse,
    ConsentScopeSchema,
    ConsentStatusResponse,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/Consent", tags=["Consent"])


def _find_consent_for_client(env, external_id: str, client, require_active: bool = False):
    """
    Find a consent record that the client has access to.

    Supports both specific recipient matching (recipient_ids) and
    category-based matching (allowed_recipient_types).

    Args:
        env: Odoo environment
        external_id: External consent identifier (UUID)
        client: API client record
        require_active: If True, only return active (given/renewed) consents

    Returns:
        spp.consent record or empty recordset
    """
    # Build domain for recipient matching
    # Client can access consent if:
    # 1. They are in recipient_ids (specific mode), OR
    # 2. Their org_type is in allowed_recipient_types (category mode)
    domain = [
        ("external_id", "=", external_id),
        "|",
        # Specific recipient matching
        "&",
        "|",
        ("recipient_mode", "=", False),  # Legacy consents
        ("recipient_mode", "=", "specific"),
        ("recipient_ids", "in", [client.partner_id.id]),
        # Category-based matching
        "&",
        ("recipient_mode", "=", "category"),
        ("allowed_recipient_types.code", "=", client.organization_type),
    ]

    if require_active:
        domain.append(("status", "in", ("given", "renewed")))

    return env["spp.consent"].search(domain, limit=1)


@router.get(
    "/{consent_id}",
    response_model=ConsentStatusResponse,
    summary="Get consent status",
    description="Check the current status of a consent record.",
)
async def get_consent_status(
    consent_id: Annotated[str, Path(description="Consent external identifier (UUID)")],
    api_client: Annotated[dict, Depends(get_current_client)],
):
    """
    Get the current status of a consent record.

    Only returns consents where the API client's organization is a recipient
    (either specific or via organization category).
    """
    env = api_client["env"]
    client = api_client["client"]

    # Find consent by external_id where client has recipient access
    consent = _find_consent_for_client(env, consent_id, client)

    if not consent:
        return ConsentStatusResponse(
            consent_id=consent_id,
            status="not_found",
        )

    # Build scope list
    scopes = [
        ConsentScopeSchema(
            resource_type=scope.resource_type,
            field_access=scope.field_access,
            purpose=scope.purpose,
            include_extensions=scope.include_extensions,
        )
        for scope in consent.api_scope_ids
    ]

    return ConsentStatusResponse(
        consent_id=consent_id,
        status=consent.status,  # Use DPV-aligned status from base model
        grantee=client.partner_id.name,
        effective_date=consent.effective_date,
        expiry_date=consent.expiry,
        scopes=scopes,
        legal_basis=client.legal_basis,
    )


@router.post(
    "/{consent_id}/$revoke",
    response_model=ConsentRevokeResponse,
    summary="Revoke consent",
    description="Revoke a consent. Per GDPR Article 7(3), withdrawal must be as easy as giving consent.",
)
async def revoke_consent(
    consent_id: Annotated[str, Path(description="Consent external identifier (UUID)")],
    api_client: Annotated[dict, Depends(get_current_client)],
    request: ConsentRevokeRequest | None = None,
):
    """
    Revoke a consent record.

    GDPR Article 7(3) requires that withdrawing consent must be as easy
    as giving it. This endpoint provides a simple way to revoke consent.

    The revocation is:
    - Immediate: Takes effect right away
    - Audited: Recorded in consent history
    - Permanent: Cannot be undone (must create new consent)
    """
    env = api_client["env"]
    client = api_client["client"]

    # Find active consent where client has recipient access
    consent = _find_consent_for_client(env, consent_id, client, require_active=True)

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active consent not found or not accessible",
        )

    reason = request.reason if request else None

    # Withdraw the consent using base model action
    # This automatically records history via the base model
    consent.action_withdraw(reason=reason, channel="api")

    _logger.info(
        "Consent %s withdrawn via API by client %s",
        consent_id,
        client.client_id,
    )

    return ConsentRevokeResponse(
        consent_id=consent_id,
        status="withdrawn",  # DPV-aligned status
        revoked_at=datetime.utcnow(),
        message="Consent has been successfully withdrawn. Data access under this consent is no longer permitted.",
    )


@router.delete(
    "/{consent_id}",
    response_model=ConsentRevokeResponse,
    summary="Revoke consent (DELETE method)",
    description="Alternative method to revoke consent using HTTP DELETE.",
)
async def delete_consent(
    consent_id: Annotated[str, Path(description="Consent external identifier (UUID)")],
    api_client: Annotated[dict, Depends(get_current_client)],
    reason: Annotated[str | None, Query(description="Reason for revocation")] = None,
):
    """
    Revoke consent using DELETE method.

    Provides RESTful alternative to POST /$revoke.
    """
    request = ConsentRevokeRequest(reason=reason) if reason else None
    return await revoke_consent(consent_id, api_client, request)


@router.get(
    "/{consent_id}/$receipt",
    response_model=ConsentReceiptSchema,
    summary="Get consent receipt",
    description="Generate a consent receipt per ISO/IEC 29184 for the data subject.",
)
async def get_consent_receipt(
    consent_id: Annotated[str, Path(description="Consent external identifier (UUID)")],
    api_client: Annotated[dict, Depends(get_current_client)],
):
    """
    Generate a consent receipt.

    The receipt provides proof of consent to the data subject, including:
    - What they consented to
    - When consent was given
    - How to withdraw consent
    - Their data subject rights
    """
    env = api_client["env"]
    client = api_client["client"]

    # Find consent where client has recipient access
    consent = _find_consent_for_client(env, consent_id, client)

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent not found or not accessible",
        )

    # Get data subject identifier (external, not DB ID)
    if consent.signatory_id:
        data_subject_id = consent.signatory_id.spp_id or f"individual:{consent.signatory_id.id}"
    elif consent.group_id:
        data_subject_id = consent.group_id.spp_id or f"group:{consent.group_id.id}"
    else:
        data_subject_id = "unknown"

    # Build purposes from scopes
    purposes = []
    data_categories = set()
    for scope in consent.api_scope_ids:
        purposes.append(
            {
                "id": scope.purpose,
                "description": dict(scope._fields["purpose"].selection).get(scope.purpose, scope.purpose),
                "resource_type": scope.resource_type,
                "field_access": scope.field_access,
            }
        )
        # Add data categories based on resource type
        if scope.resource_type in ("individual", "all"):
            data_categories.add("Personal identification data")
            data_categories.add("Demographic data")
        if scope.resource_type in ("group", "all"):
            data_categories.add("Household composition data")
        if scope.resource_type in ("program_membership", "all"):
            data_categories.add("Program enrollment data")
            data_categories.add("Benefit eligibility data")

    # Get base URL for withdrawal URI
    base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "")  # nosemgrep: odoo-sudo-without-context

    return ConsentReceiptSchema(
        receipt_id=str(uuid.uuid4()),
        version="1.0",
        timestamp=datetime.utcnow(),
        data_subject={"identifier": data_subject_id},
        data_controller={
            "name": "OpenSPP",
            # nosemgrep: odoo-sudo-without-context
            "contact": env["ir.config_parameter"].sudo().get_param("spp_api_v2.data_controller_contact", ""),
        },
        consent_id=consent_id,
        consent_date=consent.create_date.date() if consent.create_date else None,
        collection_method=consent.collection_method,
        purposes=purposes,
        data_categories=sorted(data_categories),
        effective_date=consent.effective_date,
        expiry_date=consent.expiry,
        withdrawal_uri=f"{base_url}/api/v2/Consent/{consent_id}/$revoke",
    )


@router.get(
    "/{consent_id}/$history",
    response_model=ConsentHistoryResponse,
    summary="Get consent history",
    description="Get the version history of a consent record.",
)
async def get_consent_history(
    consent_id: Annotated[str, Path(description="Consent external identifier (UUID)")],
    api_client: Annotated[dict, Depends(get_current_client)],
):
    """
    Get consent version history.

    Returns all changes made to the consent record for accountability.
    """
    env = api_client["env"]
    client = api_client["client"]

    # Verify access
    consent = _find_consent_for_client(env, consent_id, client)

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent not found or not accessible",
        )

    # Get history
    history_records = env["spp.consent.history"].search(
        [("consent_id", "=", consent.id)],
        order="version desc",
    )

    history = [
        ConsentHistoryEntrySchema(
            version=h.version,
            action=h.action,
            changed_date=h.changed_date,
            changed_by=h.changed_by_id.name if h.changed_by_id else None,
            changed_fields=h.changed_fields.split(",") if h.changed_fields else None,
            reason=h.reason,
        )
        for h in history_records
    ]

    current_version = history[0].version if history else 0

    return ConsentHistoryResponse(
        consent_id=consent_id,
        current_version=current_version,
        history=history,
    )


@router.get(
    "/{consent_id}/$access-summary",
    response_model=ConsentAccessSummarySchema,
    summary="Get access summary",
    description="Get a summary of all data accesses made under this consent.",
)
async def get_access_summary(
    consent_id: Annotated[str, Path(description="Consent external identifier (UUID)")],
    api_client: Annotated[dict, Depends(get_current_client)],
    date_from: Annotated[str | None, Query(description="Filter from date (YYYY-MM-DD)")] = None,
    date_to: Annotated[str | None, Query(description="Filter to date (YYYY-MM-DD)")] = None,
):
    """
    Get summary of data accesses under this consent.

    Useful for responding to data subject access requests (GDPR Article 15).
    """
    env = api_client["env"]
    client = api_client["client"]

    # Verify access
    consent = _find_consent_for_client(env, consent_id, client)

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consent not found or not accessible",
        )

    # Parse dates if provided
    from_dt = None
    to_dt = None
    if date_from:
        from_dt = odoo_fields.Datetime.from_string(f"{date_from} 00:00:00")
    if date_to:
        to_dt = odoo_fields.Datetime.from_string(f"{date_to} 23:59:59")

    # Get summary from unified API audit log
    summary = env["spp.api.audit.log"].get_consent_access_summary(
        consent_id=consent.id,
        date_from=from_dt,
        date_to=to_dt,
    )

    return ConsentAccessSummarySchema(
        consent_id=consent_id,
        **summary,
    )
