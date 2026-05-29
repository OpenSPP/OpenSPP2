# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DR Callback endpoint for receiving async search responses."""

import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from odoo import fields
from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..middleware.signature import verify_dr_signature
from ..services.dr_parsing import extract_disability_data, unwrap_search_data

_logger = logging.getLogger(__name__)

dr_callback_router = APIRouter(tags=["DCI DR Callback"])


@dr_callback_router.post(
    "/dr/on-search",
    response_model=None,
)
async def receive_dr_search_response(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_dr_signature)],
):
    """
    Receive DR async search response callback.

    This endpoint receives callbacks from Disability Registry systems
    with the results of async search requests.

    **Request Structure**:
    DCI envelope with search_response in message.

    **Response**: Acknowledgment
    """
    try:
        _logger.info(
            "Received DR on-search callback from %s (verified sender: %s)",
            request.client.host if request.client else "unknown",
            verified_sender_id,
        )

        envelope.header.model_dump()
        message = envelope.message

        # Extract search response data
        search_response = message.get("search_response", [])
        transaction_id = message.get("transaction_id")
        correlation_id = message.get("correlation_id")

        _logger.info(
            "Processing DR search response - txn: %s, correlation: %s, results: %d",
            transaction_id,
            correlation_id,
            len(search_response),
        )

        # Process each search response item
        for item in search_response:
            _process_dr_search_result(env, item, verified_sender_id)

        # Return SPDCI-compliant response with message wrapper
        return {
            "message": {
                "ack_status": "rcvd",
                "timestamp": datetime.now(UTC).isoformat(),
                "error": None,
                "correlation_id": correlation_id or "",
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Failed to process DR callback: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process DR callback",
        ) from None


@dr_callback_router.post(
    "/dr/on-subscribe",
    response_model=None,
)
async def receive_dr_subscribe_response(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_dr_signature)],
):
    """
    Receive DR subscription confirmation callback.

    **Response**: Acknowledgment
    """
    try:
        _logger.info(
            "Received DR on-subscribe callback from %s",
            verified_sender_id,
        )

        message = envelope.message
        correlation_id = message.get("correlation_id", "")

        # Return SPDCI-compliant response with message wrapper
        return {
            "message": {
                "ack_status": "rcvd",
                "timestamp": datetime.now(UTC).isoformat(),
                "error": None,
                "correlation_id": correlation_id,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Failed to process DR subscribe callback: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process DR callback",
        ) from None


def _process_dr_search_result(env: Environment, result: dict, source_registry: str):
    """Process a single DR search result and update disability status.

    Args:
        env: Odoo environment
        result: Search result item from DR response
        source_registry: ID of the source registry
    """
    try:
        status_field = result.get("status")
        if status_field != "succ":
            _logger.warning(
                "DR search result has non-success status: %s - %s",
                status_field,
                result.get("status_reason_message"),
            )
            return

        reg_records = unwrap_search_data(result.get("data"))

        for record in reg_records:
            # Extract identifiers to find matching partner
            identifiers = record.get("identifier", [])

            for id_info in identifiers:
                id_type = id_info.get("identifier_type", "")
                id_value = id_info.get("identifier_value", "")

                if not id_type or not id_value:
                    continue

                # Find partner by identifier
                partner = _find_partner_by_identifier(env, id_type, id_value)
                if not partner:
                    _logger.debug(
                        "No partner found for DR result identifier %s:%s",
                        id_type,
                        id_value,
                    )
                    continue

                # Update or create disability status
                _update_disability_status(env, partner, record, source_registry)
                break  # Found a match, move to next record

    except Exception as e:
        _logger.error("Error processing DR search result: %s", str(e), exc_info=True)


def _find_partner_by_identifier(env: Environment, id_type: str, id_value: str):
    """Find partner by identifier.

    Args:
        env: Odoo environment
        id_type: Identifier type (UIN, DRN, etc.)
        id_value: Identifier value

    Returns:
        res.partner record or None
    """
    # Search in spp.id records
    # Use sudo() for API access - authentication is handled by signature verification
    id_record = (
        env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
        .sudo()
        .search(
            [
                ("id_type_id.code", "=", id_type),
                ("value", "=", id_value),
            ],
            limit=1,
        )
    )

    if id_record:
        return id_record.partner_id

    # Also check with namespace URIs
    if not id_type.startswith("urn:"):
        id_record = (
            env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("id_type_id.namespace_uri", "ilike", id_type),
                    ("value", "=", id_value),
                ],
                limit=1,
            )
        )
        if id_record:
            return id_record.partner_id

    return None


def _update_disability_status(
    env: Environment,
    partner,
    record: dict,
    source_registry: str,
):
    """Update or create disability status from DR record.

    Args:
        env: Odoo environment
        partner: res.partner record
        record: DR person record
        source_registry: Source registry ID
    """
    # Use sudo() for API access - authentication is handled by signature verification
    DisabilityStatus = env["spp.dci.disability.status"].sudo()  # nosemgrep: odoo-sudo-without-context

    # Extract disability data using spec-aware parsing
    extracted = extract_disability_data(record)

    # Find existing status
    existing = DisabilityStatus.search(
        [("partner_id", "=", partner.id), ("active", "=", True)],
        limit=1,
    )

    vals = {
        "partner_id": partner.id,
        "has_disability": extracted["has_disability"],
        "disability_types": json.dumps(extracted["disability_types"]),
        "functional_scores": json.dumps(extracted["functional_scores"]),
        "assessment_date": extracted["assessment_date"],
        "source_registry": source_registry,
        "raw_data": json.dumps(record),
        "state": "synced",
        "last_sync_date": fields.Datetime.now(),
        "synced_by": env.user.id,
    }

    if existing:
        existing.write(vals)
        _logger.info("Updated disability status for partner %s from DR callback", partner.id)
    else:
        DisabilityStatus.create(vals)
        _logger.info("Created disability status for partner %s from DR callback", partner.id)
