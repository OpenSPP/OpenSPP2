# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""IBR Callback endpoint for receiving async search responses."""

import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..middleware.signature import verify_ibr_signature

_logger = logging.getLogger(__name__)

ibr_callback_router = APIRouter(tags=["DCI IBR Callback"])


@ibr_callback_router.post(
    "/ibr/on-search",
    response_model=None,
)
async def receive_ibr_search_response(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_ibr_signature)],
):
    """
    Receive IBR async search response callback.

    This endpoint receives callbacks from Integrated Beneficiary Registry systems
    with the results of async search requests (e.g., duplication checks).

    **Request Structure**:
    DCI envelope with search_response in message.

    **Response**: Acknowledgment
    """
    try:
        _logger.info(
            "Received IBR on-search callback from %s (verified sender: %s)",
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
            "Processing IBR search response - txn: %s, correlation: %s, results: %d",
            transaction_id,
            correlation_id,
            len(search_response),
        )

        # Process each search response item
        for item in search_response:
            _process_ibr_search_result(env, item, verified_sender_id, correlation_id)

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
        _logger.error("Failed to process IBR callback: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process IBR callback",
        ) from None


@ibr_callback_router.post(
    "/ibr/on-subscribe",
    response_model=None,
)
async def receive_ibr_subscribe_response(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_ibr_signature)],
):
    """
    Receive IBR subscription confirmation callback.

    **Response**: Acknowledgment
    """
    try:
        _logger.info(
            "Received IBR on-subscribe callback from %s",
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
        _logger.error("Failed to process IBR subscribe callback: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process IBR callback",
        ) from None


def _process_ibr_search_result(
    env: Environment,
    result: dict,
    source_registry: str,
    correlation_id: str | None,
):
    """Process a single IBR search result and update duplication check.

    Args:
        env: Odoo environment
        result: Search result item from IBR response
        source_registry: ID of the source registry
        correlation_id: Correlation ID to match pending checks
    """
    try:
        status_field = result.get("status")
        if status_field != "succ":
            _logger.warning(
                "IBR search result has non-success status: %s - %s",
                status_field,
                result.get("status_reason_message"),
            )
            return

        data = result.get("data", {})
        reg_records = data.get("reg_records", [])

        # Find pending duplication check by correlation_id
        # Use sudo() for API access - authentication is handled by signature verification
        if correlation_id:
            pending_check = (
                # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
                env["spp.dci.duplication.check"]
                .sudo()
                .search(
                    [
                        ("state", "=", "checking"),
                        ("notes", "ilike", correlation_id),
                    ],
                    limit=1,
                )
            )
        else:
            pending_check = None

        # Determine if there are duplicates
        is_duplicate = len(reg_records) > 0
        matched_programs = []

        for record in reg_records:
            # Extract program information
            programs = record.get("programs", [])
            for prog in programs:
                prog_name = prog.get("name") or prog.get("program_name")
                if prog_name:
                    matched_programs.append(prog_name)

        # Update duplication check if found
        if pending_check:
            pending_check.write(
                {
                    "result": "confirmed_match" if is_duplicate else "no_match",
                    "matched_programs": "\n".join(matched_programs) if matched_programs else "",
                    "raw_response": json.dumps(result),
                    "state": "completed",
                }
            )
            _logger.info(
                "Updated duplication check %s from IBR callback: %s",
                pending_check.id,
                "match found" if is_duplicate else "no match",
            )
        else:
            _logger.info(
                "IBR callback processed but no pending check found for correlation_id: %s",
                correlation_id,
            )

    except Exception as e:
        _logger.error("Error processing IBR search result: %s", str(e), exc_info=True)
