# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Receipt API endpoint.

Implements the receipt endpoint for delivery confirmation per SPDCI spec.
External systems call this endpoint to confirm they received async notifications,
enabling reliable message delivery tracking.

Per SPDCI spec (ReceiptRequest.yaml, ReceiptInformation.yaml):
- transaction_id: Unique identifier for this receipt request
- receipt_information: Contains receipt_type and optional beneficiaries list
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import (
    DCICallbackHeader,
    DCIEnvelope,
    ReceiptRequest,
    ReceiptResponse,
    ReceiptResponseItem,
)
from odoo.addons.spp_dci.services import (
    get_response_action,
    get_sender_id,
    sign_dci_envelope,
)

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.rate_limit import check_dci_rate_limit
from ..middleware.signature import verify_bearer_token, verify_dci_signature

_logger = logging.getLogger(__name__)

dci_receipt_router = APIRouter(tags=["DCI Receipt"])


def _build_receipt_response_envelope(
    env: Environment,
    original_header,
    response_message: dict,
    status_code: str,
    status_reason_code: str | None = None,
    status_reason_message: str | None = None,
    completed_count: int = 0,
) -> DCIEnvelope:
    """Build a DCI response envelope for receipt."""
    our_sender_id = get_sender_id(env)

    callback_header = DCICallbackHeader(
        version=original_header.version if hasattr(original_header, "version") else "1.0.0",
        message_id=str(uuid.uuid4()),
        message_ts=datetime.now(UTC),
        action=get_response_action("receipt"),
        sender_id=our_sender_id,
        receiver_id=original_header.sender_id if hasattr(original_header, "sender_id") else "unknown",
        total_count=1,
        status=status_code,
        status_reason_code=status_reason_code,
        status_reason_message=status_reason_message,
        completed_count=completed_count,
    )

    # Sign the response and build the envelope
    signature = sign_dci_envelope(env, callback_header, response_message)

    return DCIEnvelope(
        signature=signature,
        header=callback_header,
        message=response_message,
    )


@dci_receipt_router.post(
    "/receipt",
    response_model=DCIEnvelope,
    response_model_exclude_none=True,
    summary="Submit receipt confirmation",
    description="Confirm receipt of an async notification. Used by external systems to acknowledge delivery.",
)
async def submit_receipt(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
):
    """
    Submit receipt confirmation for a notification.

    This endpoint allows external systems to confirm they received
    async notifications sent via subscription callbacks.

    The receipt_information should include:
    - receipt_type: Type of receipt (register, payment, deregister, etc.)
    - notification_id: ID of the notification being acknowledged (from X-DCI-Notification-ID header)
    - subscription_code: Code of the subscription the notification was for

    **Response**: DCIEnvelope with receipt confirmation status
    """
    try:
        envelope = request_envelope

        # Parse receipt request
        try:
            receipt_request = ReceiptRequest.model_validate(envelope.message)
        except Exception as e:
            _logger.error("Invalid ReceiptRequest: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid receipt request: {str(e)}",
            ) from e

        receipt_info = receipt_request.receipt_information

        # Find the notification log entry by notification_id or subscription_code
        # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
        NotificationLog = env["spp.dci.notification.log"].sudo()
        notification_log = None

        if receipt_info.notification_id:
            notification_log = NotificationLog.search(
                [("notification_id", "=", receipt_info.notification_id)],
                limit=1,
            )

        # If not found by notification_id, try by subscription_code (less precise)
        if not notification_log and receipt_info.subscription_code:
            # Find the most recent unacknowledged notification for this subscription
            subscription = (
                # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
                env["spp.dci.subscription"]
                .sudo()
                .search(
                    [
                        ("subscription_code", "=", receipt_info.subscription_code),
                        ("sender_id.sender_id", "=", verified_sender_id),
                    ],
                    limit=1,
                )
            )
            if subscription:
                notification_log = NotificationLog.search(
                    [
                        ("subscription_id", "=", subscription.id),
                        ("receipt_received", "=", False),
                        ("status", "=", "sent"),
                    ],
                    order="sent_at desc",
                    limit=1,
                )

        response_status = "succ"
        status_reason_code = None
        status_reason_message = None

        if notification_log:
            # Update the notification log with receipt information
            update_vals = {
                "receipt_received": True,
                "receipt_timestamp": datetime.now(UTC),
                "receipt_transaction_id": receipt_request.transaction_id,
                "status": "received",
            }

            if receipt_info.processed_at:
                update_vals["receipt_processed_at"] = receipt_info.processed_at

            if receipt_info.error_message:
                update_vals["receipt_error"] = receipt_info.error_message

            notification_log.write(update_vals)

            _logger.info(
                "Receipt recorded for notification %s from sender %s",
                notification_log.notification_id,
                verified_sender_id,
            )
        else:
            # Notification not found - still acknowledge the receipt but with warning
            response_status = "succ"  # Receipt itself is successful even if we can't match
            status_reason_code = "warn.notification.not_found"
            status_reason_message = (
                "Receipt acknowledged but notification not found. "
                "Ensure notification_id or subscription_code is provided."
            )
            _logger.warning(
                "Receipt received but notification not found. notification_id=%s, subscription_code=%s, sender=%s",
                receipt_info.notification_id,
                receipt_info.subscription_code,
                verified_sender_id,
            )

        # Build response
        receipt_response = ReceiptResponse(
            transaction_id=receipt_request.transaction_id,
            correlation_id=str(uuid.uuid4()),
            receipt_response=[
                ReceiptResponseItem(
                    reference_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    status=response_status,
                    status_reason_code=status_reason_code,
                    status_reason_message=status_reason_message,
                )
            ],
        )

        return _build_receipt_response_envelope(
            env,
            envelope.header,
            receipt_response.model_dump(mode="json", exclude_none=True),
            status_code=response_status,
            status_reason_code=status_reason_code,
            status_reason_message=status_reason_message,
            completed_count=1,
        )

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Error processing receipt: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@dci_receipt_router.post(
    "/sync/receipt",
    response_model=DCIEnvelope,
    response_model_exclude_none=True,
    summary="Submit receipt confirmation (sync)",
    description="Synchronous version of receipt confirmation.",
)
async def sync_receipt(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
):
    """
    Synchronous receipt submission.

    Same functionality as /receipt but explicitly marked as synchronous.
    """
    # Delegate to the main receipt handler
    return await submit_receipt(request_envelope, env, _bearer_token, verified_sender_id, _rate_limit_check)
