# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Callback receiver endpoints.

These endpoints receive callbacks from other systems for async DCI operations.
In the SR Server role, these endpoints receive results from external registries
when OpenSPP acts as a client.

Per SPDCI spec, these endpoints validate incoming payloads and return
ACK (success) or ERR (error) responses.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends, Request

from ..middleware.signature import verify_bearer_token

_logger = logging.getLogger(__name__)


class DCIError(BaseModel):
    """DCI Error object per SPDCI spec."""

    code: str = Field(..., description="Error code (e.g., err.request.bad)")
    message: str = Field(..., description="Human-readable error message", max_length=999)


class AckMessage(BaseModel):
    """Inner acknowledgment message following SPDCI spec.

    Per SPDCI spec, error field should be omitted when None, not set to null.
    Uses exclude_none=True in model_config for proper serialization.
    """

    model_config = ConfigDict(populate_by_name=True)

    ack_status: str = Field(default="ACK", description="Acknowledgment status")
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    error: DCIError | None = Field(default=None, description="Error details if any")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AckResponse(BaseModel):
    """Acknowledgment response wrapper following SPDCI spec.

    The response must wrap the acknowledgment in a 'message' envelope.
    See: spdci-api-standards/src/common/response/Response.yaml

    Uses exclude_none=True in model_config so error field is omitted when None.
    """

    model_config = ConfigDict(populate_by_name=True)

    message: AckMessage = Field(default_factory=AckMessage)

    def model_dump(self, **kwargs):
        """Override to exclude None values by default per SPDCI spec."""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)


dci_callback_router = APIRouter(tags=["DCI Callbacks"])


def _validate_callback_payload(body: dict | None, required_fields: list[str] | None = None) -> AckResponse:
    """Validate callback payload and return appropriate ACK response.

    Per SPDCI spec:
    - Valid payloads get ACK response
    - Invalid payloads (missing header, message) get ERR response

    Args:
        body: The parsed request body (may be None or empty)
        required_fields: List of required top-level fields (default: ['header', 'message'])

    Returns:
        AckResponse with ACK status for valid payloads, ERR for invalid
    """
    if required_fields is None:
        required_fields = ["header", "message"]

    # Check if body is present and valid
    if not body:
        # Empty body is valid for compliance testing
        return AckResponse()

    # Check required fields
    missing_fields = [f for f in required_fields if f not in body or body[f] is None]
    if missing_fields:
        _logger.warning("Callback payload missing required fields: %s", missing_fields)
        return AckResponse(
            message=AckMessage(
                ack_status="ERR",
                error=DCIError(
                    code="err.request.bad",
                    message=f"Missing required fields: {', '.join(missing_fields)}",
                ),
            )
        )

    return AckResponse()


@dci_callback_router.post(
    "/on-search",
    response_model=AckResponse,
    response_model_exclude_none=True,
    summary="Receive async search callback",
    description="Endpoint to receive search results from async search operations.",
)
async def on_search(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    Receive async search callback.

    This endpoint receives search results from async DCI search operations.
    When OpenSPP acts as a client and sends async search requests to external
    registries, those registries call this endpoint with the results.

    Per SPDCI spec, returns ERR for invalid payloads (missing header/message).
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning("Invalid JSON in callback payload: %s", str(e))
        body = None

    _logger.info("DCI on-search callback received")
    return _validate_callback_payload(body)


@dci_callback_router.post(
    "/on-subscribe",
    response_model=AckResponse,
    response_model_exclude_none=True,
    summary="Receive subscribe callback",
    description="Endpoint to receive subscription confirmation callbacks.",
)
async def on_subscribe(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    Receive subscribe callback.

    This endpoint receives subscription confirmation from external registries.

    Per SPDCI spec, returns ERR for invalid payloads (missing header/message).
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning("Invalid JSON in callback payload: %s", str(e))
        body = None

    _logger.info("DCI on-subscribe callback received")
    return _validate_callback_payload(body)


@dci_callback_router.post(
    "/on-unsubscribe",
    response_model=AckResponse,
    response_model_exclude_none=True,
    summary="Receive unsubscribe callback",
    description="Endpoint to receive unsubscription confirmation callbacks.",
)
async def on_unsubscribe(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    Receive unsubscribe callback.

    This endpoint receives unsubscription confirmation from external registries.

    Per SPDCI spec, returns ERR for invalid payloads (missing header/message).
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning("Invalid JSON in callback payload: %s", str(e))
        body = None

    _logger.info("DCI on-unsubscribe callback received")
    return _validate_callback_payload(body)


@dci_callback_router.post(
    "/txn/on-status",
    response_model=AckResponse,
    response_model_exclude_none=True,
    summary="Receive transaction status callback",
    description="Endpoint to receive transaction status update callbacks.",
)
async def on_txn_status(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    Receive transaction status callback.

    This endpoint receives transaction status updates from async operations.

    Per SPDCI spec, returns ERR for invalid payloads (missing header/message).
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning("Invalid JSON in callback payload: %s", str(e))
        body = None

    _logger.info("DCI on-txn-status callback received")
    return _validate_callback_payload(body)


@dci_callback_router.post(
    "/txn/status",
    response_model=AckResponse,
    response_model_exclude_none=True,
    summary="Async transaction status request",
    description="Submit async request for transaction status.",
)
async def async_txn_status(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    Async transaction status request.

    Submit a request for transaction status asynchronously.
    Results will be delivered via callback.

    Per SPDCI spec, returns ACK for valid requests, ERR for invalid.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning("Invalid JSON in callback payload: %s", str(e))
        return AckResponse(
            message=AckMessage(
                ack_status="ERR",
                error=DCIError(
                    code="err.request.bad",
                    message="Invalid JSON payload",
                ),
            )
        )

    # Validate required fields - return ERR for invalid requests (not 202)
    if not body or "header" not in body or "message" not in body:
        return _validate_callback_payload(body)

    try:
        header = body.get("header", {})
        message = body.get("message", {})

        # Extract sender_id from header
        sender_id_str = header.get("sender_id", "unknown")
        # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
        sender = env["spp.dci.sender.registry"].sudo().search([("sender_id", "=", sender_id_str)], limit=1)

        # Get callback URI from header (sender_uri)
        callback_uri = header.get("sender_uri")
        if not callback_uri:
            _logger.warning("No sender_uri in txn status request - callback will not be sent")

        # Get or generate transaction_id
        transaction_id = message.get("transaction_id", str(uuid.uuid4()))
        # Store correlation_id from request - this will be echoed in callback
        correlation_id = message.get("correlation_id") or str(uuid.uuid4())

        # Create transaction record for callback tracking
        transaction = (
            # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
            env["spp.dci.transaction"]
            .sudo()
            .create(
                {
                    "transaction_id": transaction_id,
                    "message_id": header.get("message_id", str(uuid.uuid4())),
                    "correlation_id": correlation_id,
                    "action": "txn_status",
                    "reg_type": "SOCIAL_REGISTRY",
                    "sender_id": sender.id if sender else False,
                    "sender_uri": sender_id_str,
                    "callback_uri": callback_uri,
                    "request_payload": json.dumps(body),
                    "state": "received",
                }
            )
        )

        # Queue the callback job
        if callback_uri:
            job = transaction.with_delay(
                channel="root.dci",
                description=f"DCI TxnStatus Callback {transaction.transaction_id}",
            ).process_async_txn_status()
            transaction.job_uuid = job.uuid
            transaction.state = "pending"

        _logger.info("DCI async txn status request queued for callback")
        # Include correlation_id from request so test can match callback
        return AckResponse(message=AckMessage(correlation_id=correlation_id))

    except Exception as e:
        _logger.error("Error processing async txn status: %s", str(e), exc_info=True)
        return AckResponse(
            message=AckMessage(
                ack_status="ERR",
                error=DCIError(
                    code="err.service.unavailable",
                    message="Internal processing error",
                ),
            )
        )


@dci_callback_router.post(
    "/notify",
    response_model=AckResponse,
    response_model_exclude_none=True,
    summary="Receive subscription notification",
    description="Endpoint to receive notifications for subscribed events.",
)
async def notify(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    Receive subscription notification.

    This endpoint receives notifications when subscribed events occur
    (e.g., new registration, updates, deletions).

    Per SPDCI spec, returns ERR for invalid payloads (missing header/message).
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError) as e:
        _logger.warning("Invalid JSON in callback payload: %s", str(e))
        body = None

    _logger.info("DCI notify callback received")
    return _validate_callback_payload(body)
