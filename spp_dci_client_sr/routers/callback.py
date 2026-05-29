# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""SR Callback endpoint for receiving async search responses and updates."""

import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..middleware.signature import verify_sr_signature

_logger = logging.getLogger(__name__)

sr_callback_router = APIRouter(tags=["DCI SR Callback"])


@sr_callback_router.post(
    "/sr/on-search",
    response_model=None,
)
async def receive_sr_search_response(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_sr_signature)],
):
    """
    Receive SR async search response callback.

    This endpoint receives callbacks from Social Registry systems
    with the results of async search requests.

    **Request Structure**:
    DCI envelope with search_response in message.

    **Response**: Acknowledgment
    """
    try:
        _logger.info(
            "Received SR on-search callback from %s (verified sender: %s)",
            request.client.host if request.client else "unknown",
            verified_sender_id,
        )

        header = envelope.header.model_dump()
        message = envelope.message

        # Extract search response data
        search_response = message.get("search_response", [])
        transaction_id = message.get("transaction_id")
        correlation_id = message.get("correlation_id")

        _logger.info(
            "Processing SR search response - txn: %s, correlation: %s, results: %d",
            transaction_id,
            correlation_id,
            len(search_response),
        )

        # Process each search response item
        for item in search_response:
            _process_sr_search_result(env, item, verified_sender_id)

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
        _logger.error("Failed to process SR callback: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process SR callback",
        ) from None


@sr_callback_router.post(
    "/sr/on-subscribe",
    response_model=None,
)
async def receive_sr_subscribe_response(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_sr_signature)],
):
    """
    Receive SR subscription confirmation callback.

    **Response**: Acknowledgment
    """
    try:
        _logger.info(
            "Received SR on-subscribe callback from %s",
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
        _logger.error("Failed to process SR subscribe callback: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process SR callback",
        ) from None


@sr_callback_router.post(
    "/sr/on-notify",
    response_model=None,
)
async def receive_sr_notification(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_sr_signature)],
):
    """
    Receive SR event notification (enrollment, disenrollment, update).

    This endpoint receives real-time notifications from the Social Registry
    about changes to beneficiary data.

    **Response**: Acknowledgment
    """
    try:
        _logger.info(
            "Received SR notification from %s",
            verified_sender_id,
        )

        message = envelope.message
        event_type = message.get("event_type")
        correlation_id = message.get("correlation_id", "")
        notify_data = message.get("notify_data", {})

        _logger.info(
            "Processing SR notification - event: %s, correlation: %s",
            event_type,
            correlation_id,
        )

        # Process the notification based on event type
        if event_type == "ENROLLMENT":
            _process_enrollment_notification(env, notify_data, verified_sender_id)
        elif event_type == "DISENROLLMENT":
            _process_disenrollment_notification(env, notify_data, verified_sender_id)
        elif event_type == "UPDATE":
            _process_update_notification(env, notify_data, verified_sender_id)
        else:
            _logger.warning("Unknown SR event type: %s", event_type)

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
        _logger.error("Failed to process SR notification: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process SR notification",
        ) from None


def _process_sr_search_result(env: Environment, result: dict, source_registry: str):
    """Process a single SR search result and update local records.

    Args:
        env: Odoo environment
        result: Search result item from SR response
        source_registry: ID of the source registry
    """
    try:
        status_field = result.get("status")
        if status_field != "succ":
            _logger.warning(
                "SR search result has non-success status: %s - %s",
                status_field,
                result.get("status_reason_message"),
            )
            return

        data = result.get("data", {})
        reg_records = data.get("reg_records", [])

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
                        "No partner found for SR result identifier %s:%s",
                        id_type,
                        id_value,
                    )
                    continue

                # Update or create SR record
                _update_sr_record(env, partner, record, source_registry)
                break  # Found a match, move to next record

    except Exception as e:
        _logger.error("Error processing SR search result: %s", str(e), exc_info=True)


def _find_partner_by_identifier(env: Environment, id_type: str, id_value: str):
    """Find partner by identifier.

    Args:
        env: Odoo environment
        id_type: Identifier type (UIN, NIN, etc.)
        id_value: Identifier value

    Returns:
        res.partner record or None
    """
    # Search in spp.id records
    id_record = (
        env["spp.id"]
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
            env["spp.id"]
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


def _update_sr_record(
    env: Environment,
    partner,
    record: dict,
    source_registry: str,
):
    """Update or create SR record from search result.

    Args:
        env: Odoo environment
        partner: res.partner record
        record: SR person record
        source_registry: Source registry ID
    """
    SRRecord = env["spp.dci.sr.record"].sudo()

    # Find existing record
    existing = SRRecord.search(
        [("partner_id", "=", partner.id), ("source_registry", "=", source_registry), ("active", "=", True)],
        limit=1,
    )

    vals = {
        "partner_id": partner.id,
        "source_registry": source_registry,
        "external_id": record.get("id"),
        "sr_name": record.get("name"),
        "sr_birth_date": record.get("birth_date"),
        "sr_gender": record.get("gender"),
        "enrolled_programs": json.dumps(record.get("enrolled_programs", [])),
        "household_id": record.get("household_id"),
        "household_size": record.get("household_size"),
        "is_head_of_household": record.get("is_head_of_household"),
        "raw_data": json.dumps(record),
        "state": "synced",
        "last_sync_date": datetime.now(UTC),
        "synced_by": env.user.id,
    }

    if existing:
        existing.write(vals)
        _logger.info("Updated SR record for partner %s from callback", partner.id)
    else:
        SRRecord.create(vals)
        _logger.info("Created SR record for partner %s from callback", partner.id)


def _process_enrollment_notification(env: Environment, data: dict, source_registry: str):
    """Process enrollment notification from SR."""
    _logger.info("Processing enrollment notification from %s", source_registry)
    # Find partner and update enrollment data
    identifiers = data.get("identifier", [])
    for id_info in identifiers:
        partner = _find_partner_by_identifier(
            env,
            id_info.get("identifier_type", ""),
            id_info.get("identifier_value", ""),
        )
        if partner:
            _update_sr_record(env, partner, data, source_registry)
            break


def _process_disenrollment_notification(env: Environment, data: dict, source_registry: str):
    """Process disenrollment notification from SR."""
    _logger.info("Processing disenrollment notification from %s", source_registry)
    # Similar to enrollment, update the record
    identifiers = data.get("identifier", [])
    for id_info in identifiers:
        partner = _find_partner_by_identifier(
            env,
            id_info.get("identifier_type", ""),
            id_info.get("identifier_value", ""),
        )
        if partner:
            _update_sr_record(env, partner, data, source_registry)
            break


def _process_update_notification(env: Environment, data: dict, source_registry: str):
    """Process update notification from SR."""
    _logger.info("Processing update notification from %s", source_registry)
    identifiers = data.get("identifier", [])
    for id_info in identifiers:
        partner = _find_partner_by_identifier(
            env,
            id_info.get("identifier_type", ""),
            id_info.get("identifier_value", ""),
        )
        if partner:
            _update_sr_record(env, partner, data, source_registry)
            break
