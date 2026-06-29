# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Async API endpoints with job_worker integration.

Implements asynchronous DCI operations (mounted under /social/registry):
- POST /search - Async search (202 Accepted, callback delivery)
- POST /subscribe - Create event subscription
- POST /unsubscribe - Cancel subscription
- POST /sync/txn/status - Check transaction status (sync)
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import (
    DCICallbackHeader,
    DCIEnvelope,
    DCIMessageHeader,
    SearchRequest,
    SubscribeRequest,
    TxnStatusRequest,
    TxnStatusResponse,
    TxnStatusResponseData,
    UnsubscribeRequest,
)
from odoo.addons.spp_dci.services import (
    get_response_action,
    get_sender_id,
    sign_dci_envelope,
)

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..middleware.rate_limit import check_dci_rate_limit
from ..middleware.signature import verify_bearer_token, verify_dci_signature
from .callbacks import AckMessage, AckResponse

_logger = logging.getLogger(__name__)

dci_async_router = APIRouter(tags=["DCI Async Operations"])


def _build_minimal_search_response(
    transaction_id: str,
    status: str,
    status_reason_code: str | None = None,
    status_reason_message: str | None = None,
) -> dict:
    """Build a minimal SearchResponse-like object for txn status.

    Per SPDCI spec, txn_status should be a SearchResponse, SubscribeResponse,
    or UnSubscribeResponse object.
    """
    response = {
        "transaction_id": transaction_id,
        "correlation_id": str(uuid.uuid4()),
        "search_response": [
            {
                "reference_id": f"ref-{transaction_id}",
                "timestamp": datetime.now(UTC).isoformat(),
                "status": status,
            }
        ],
    }
    if status_reason_code:
        response["search_response"][0]["status_reason_code"] = status_reason_code
    if status_reason_message:
        response["search_response"][0]["status_reason_message"] = status_reason_message
    return response


def _build_response_envelope(
    env: Environment,
    original_header: DCIMessageHeader,
    response_message: dict,
    status_code: str,
    status_reason_code: str | None = None,
    status_reason_message: str | None = None,
    completed_count: int = 0,
) -> DCIEnvelope:
    """Build a DCI response envelope."""
    our_sender_id = get_sender_id(env)

    callback_header = DCICallbackHeader(
        version=original_header.version,
        message_id=str(uuid.uuid4()),
        message_ts=datetime.now(UTC),
        action=get_response_action(original_header.action),
        sender_id=our_sender_id,
        receiver_id=original_header.sender_id,
        total_count=original_header.total_count,
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


@dci_async_router.post(
    "/search",
    response_model=AckResponse,
    status_code=status.HTTP_202_ACCEPTED,
    response_model_exclude_none=True,
)
async def async_search(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
    response: Response,
):
    """
    Async search - queue processing and return 202 Accepted.

    The search is executed in the background via job_worker.
    Results are delivered to the sender's callback_uri.

    **Response**: 202 Accepted with transaction tracking info
    """
    try:
        envelope = request_envelope

        # Parse search request
        try:
            search_request = SearchRequest.model_validate(envelope.message)
        except Exception as e:
            _logger.error("Invalid SearchRequest: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid search request: {str(e)}",
            ) from e

        # SECURITY: Use verified_sender_id from signature verification
        # instead of reading from envelope.header to prevent spoofing
        # Use sudo() for API access - authentication is handled by signature verification
        # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
        sender = env["spp.dci.sender.registry"].sudo().search([("sender_id", "=", verified_sender_id)], limit=1)

        # Get callback URI from header
        callback_uri = envelope.header.sender_uri
        if not callback_uri:
            _logger.warning("No sender_uri in request - callback will not be sent")

        # Create transaction record
        # Use sudo() for API access - authentication is handled by signature verification
        # Store correlation_id from request - this will be echoed in callback
        correlation_id = getattr(search_request, "correlation_id", None) or str(uuid.uuid4())
        transaction = (
            # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
            env["spp.dci.transaction"]
            .sudo()
            .create(
                {
                    "transaction_id": search_request.transaction_id,
                    "message_id": envelope.header.message_id,
                    "correlation_id": correlation_id,
                    "action": "search",
                    "reg_type": "SOCIAL_REGISTRY",  # Default, could be derived from request
                    "sender_id": sender.id if sender else False,
                    "sender_uri": verified_sender_id,
                    "callback_uri": callback_uri,
                    "request_payload": json.dumps(envelope.model_dump(mode="json")),
                    "state": "received",
                }
            )
        )

        _logger.info(
            "Created async search transaction %s for sender_id=%s",
            transaction.transaction_id,
            sender.id if sender else "unknown",
        )

        # Queue the search job with job_worker
        job = transaction.with_delay(
            channel="dci",
            timeout=60,
            description=f"DCI Search {transaction.transaction_id}",
        ).process_async_search()

        # Store job UUID for tracking
        transaction.job_uuid = job.uuid
        transaction.state = "pending"

        # Return SPDCI-compliant ACK response for async operations
        # Include correlation_id from request so test can match callback
        return AckResponse(message=AckMessage(correlation_id=correlation_id))

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Error processing async search: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@dci_async_router.post(
    "/subscribe",
    response_model=AckResponse,
    status_code=status.HTTP_202_ACCEPTED,
    response_model_exclude_none=True,
)
async def subscribe(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
):
    """
    Create event subscription for notifications.

    Subscribe to registry events (registration, update, delete).
    Notifications will be sent to the callback_url when events occur.

    **Response**: ACK with callback delivery of subscription codes
    """
    try:
        envelope = request_envelope

        # Parse subscribe request
        try:
            sub_request = SubscribeRequest.model_validate(envelope.message)
        except Exception as e:
            _logger.error("Invalid SubscribeRequest: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid subscribe request: {str(e)}",
            ) from e

        # SECURITY: Use verified_sender_id from signature verification
        # Use sudo() for API access - authentication is handled by signature verification
        # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
        sender = env["spp.dci.sender.registry"].sudo().search([("sender_id", "=", verified_sender_id)], limit=1)
        if not sender:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sender not registered",
            )

        success_count = 0

        # Get callback URI from header (SPDCI spec)
        callback_uri = envelope.header.sender_uri
        if not callback_uri:
            _logger.warning("No sender_uri in subscribe request - callback will not be sent")

        for req_item in sub_request.subscribe_request:
            try:
                # Map event type to internal format (from subscribe_criteria)
                # DCI spec uses both "REGISTER" and "REGISTRATION" for the same event
                event_type_map = {
                    "REGISTER": "registration",
                    "REGISTRATION": "registration",
                    "UPDATE": "update",
                    "DELETE": "delete",
                    "BIRTH": "birth",
                    "DEATH": "death",
                    "MARRIAGE": "marriage",
                    "DIVORCE": "divorce",
                    "ADOPTION": "adoption",
                    "CORRECTION": "correction",
                }
                raw_event_type = req_item.subscribe_criteria.reg_event_type
                event_type = event_type_map.get(raw_event_type, raw_event_type.lower())

                # Serialize filter to JSON string for storage
                filter_expression = None
                if req_item.subscribe_criteria.filter:
                    filter_expression = json.dumps(req_item.subscribe_criteria.filter)

                # Get reg_type from criteria or default
                reg_type = req_item.subscribe_criteria.reg_type or "SOCIAL_REGISTRY"

                # Create subscription (URL validation happens in model create)
                # Use sudo() for API access - authentication is handled by signature verification
                subscription = (
                    # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
                    env["spp.dci.subscription"]
                    .sudo()
                    .create(
                        {
                            "sender_id": sender.id,
                            "callback_uri": callback_uri,
                            "event_type": event_type,
                            "reg_type": reg_type,
                            "filter_expression": filter_expression,
                            "filter_type": req_item.subscribe_criteria.filter_type,
                            "original_message_id": envelope.header.message_id,
                            "original_transaction_id": sub_request.transaction_id,
                            "state": "pending",
                        }
                    )
                )

                # Auto-confirm if sender is trusted
                if sender.auto_approve:
                    subscription.action_confirm()

                success_count += 1

                # SECURITY: Use ID in logs, not name (PII consideration)
                _logger.info(
                    "Created subscription %s for sender_id=%s, event %s",
                    subscription.subscription_code,
                    sender.id,
                    event_type,
                )

            except Exception as e:
                # Log full error internally
                _logger.error("Failed to create subscription: %s", str(e), exc_info=True)

        # Create transaction record for callback tracking
        # Store correlation_id from request - this will be echoed in callback
        correlation_id = getattr(sub_request, "correlation_id", None) or str(uuid.uuid4())
        transaction = (
            # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
            env["spp.dci.transaction"]
            .sudo()
            .create(
                {
                    "transaction_id": sub_request.transaction_id,
                    "message_id": envelope.header.message_id,
                    "correlation_id": correlation_id,
                    "action": "subscribe",
                    "reg_type": "SOCIAL_REGISTRY",
                    "sender_id": sender.id if sender else False,
                    "sender_uri": verified_sender_id,
                    "callback_uri": callback_uri,
                    "request_payload": json.dumps(envelope.model_dump(mode="json")),
                    "state": "received",
                }
            )
        )

        # Queue the callback job
        if callback_uri:
            job = transaction.with_delay(
                channel="dci",
                timeout=60,
                description=f"DCI Subscribe Callback {transaction.transaction_id}",
            ).process_async_subscribe()
            transaction.job_uuid = job.uuid
            transaction.state = "pending"

        _logger.info(
            "Subscribe completed for %d/%d items, callback queued",
            success_count,
            len(sub_request.subscribe_request),
        )
        # Include correlation_id from request so test can match callback
        return AckResponse(message=AckMessage(correlation_id=correlation_id))

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Error processing subscribe: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@dci_async_router.post(
    "/unsubscribe",
    response_model=AckResponse,
    status_code=status.HTTP_202_ACCEPTED,
    response_model_exclude_none=True,
)
async def unsubscribe(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
):
    """
    Cancel event subscription.

    **Response**: ACK with callback delivery of unsubscribe confirmation
    """
    try:
        envelope = request_envelope

        # Parse unsubscribe request
        try:
            unsub_request = UnsubscribeRequest.model_validate(envelope.message)
        except Exception as e:
            _logger.error("Invalid UnsubscribeRequest: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid unsubscribe request: {str(e)}",
            ) from e

        # Get sender for transaction record
        # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
        sender = env["spp.dci.sender.registry"].sudo().search([("sender_id", "=", verified_sender_id)], limit=1)

        success_count = 0

        # SPDCI format: subscription_codes is a list of strings
        for subscription_code in unsub_request.subscription_codes:
            # SECURITY: Use verified_sender_id to ensure sender can only
            # cancel their own subscriptions
            # Use sudo() for API access - authentication is handled by signature verification
            subscription = (
                # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
                env["spp.dci.subscription"]
                .sudo()
                .search(
                    [
                        ("subscription_code", "=", subscription_code),
                        ("sender_id.sender_id", "=", verified_sender_id),
                    ],
                    limit=1,
                )
            )

            if subscription:
                subscription.action_cancel()
                success_count += 1
                _logger.info("Cancelled subscription %s", subscription_code)
            else:
                _logger.warning(
                    "Subscription %s not found or not owned by sender %s",
                    subscription_code,
                    verified_sender_id,
                )

        # Get callback URI from header
        callback_uri = envelope.header.sender_uri
        if not callback_uri:
            _logger.warning("No sender_uri in unsubscribe request - callback will not be sent")

        # Create transaction record for callback tracking
        # Store correlation_id from request - this will be echoed in callback
        correlation_id = getattr(unsub_request, "correlation_id", None) or str(uuid.uuid4())
        transaction = (
            # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
            env["spp.dci.transaction"]
            .sudo()
            .create(
                {
                    "transaction_id": unsub_request.transaction_id,
                    "message_id": envelope.header.message_id,
                    "correlation_id": correlation_id,
                    "action": "unsubscribe",
                    "reg_type": "SOCIAL_REGISTRY",
                    "sender_id": sender.id if sender else False,
                    "sender_uri": verified_sender_id,
                    "callback_uri": callback_uri,
                    "request_payload": json.dumps(envelope.model_dump(mode="json")),
                    "state": "received",
                }
            )
        )

        # Queue the callback job
        if callback_uri:
            job = transaction.with_delay(
                channel="dci",
                timeout=60,
                description=f"DCI Unsubscribe Callback {transaction.transaction_id}",
            ).process_async_unsubscribe()
            transaction.job_uuid = job.uuid
            transaction.state = "pending"

        _logger.info(
            "Unsubscribe completed for %d/%d items, callback queued",
            success_count,
            len(unsub_request.subscription_codes),
        )
        # Include correlation_id from request so test can match callback
        return AckResponse(message=AckMessage(correlation_id=correlation_id))

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Error processing unsubscribe: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e


@dci_async_router.post(
    "/sync/txn/status",
    response_model=DCIEnvelope,
    response_model_exclude_none=True,
)
async def txn_status(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
):
    """
    Check transaction status.

    Query the status of async transactions by transaction_id.

    **Response**: DCIEnvelope with transaction statuses
    """
    try:
        envelope = request_envelope

        # Parse status request
        try:
            status_request = TxnStatusRequest.model_validate(envelope.message)
        except Exception as e:
            _logger.error("Invalid TxnStatusRequest: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status request: {str(e)}",
            ) from e

        req_criteria = status_request.txnstatus_request

        # Build search domain based on attribute_type (SPDCI spec)
        domain = [("sender_uri", "=", verified_sender_id)]

        if req_criteria.attribute_type == "transaction_id":
            # Single transaction lookup
            txn_ids = (
                [req_criteria.attribute_value]
                if isinstance(req_criteria.attribute_value, str)
                else req_criteria.attribute_value
            )
            domain.append(("transaction_id", "in", txn_ids))
        elif req_criteria.attribute_type == "correlation_id":
            domain.append(("correlation_id", "=", req_criteria.attribute_value))
        elif req_criteria.attribute_type == "reference_id_list":
            # Not directly supported in our model, but we can try message_id
            ref_ids = (
                req_criteria.attribute_value
                if isinstance(req_criteria.attribute_value, list)
                else [req_criteria.attribute_value]
            )
            domain.append(("message_id", "in", ref_ids))

        # Use sudo() for API access - authentication is handled by signature verification
        # nosemgrep: odoo-sudo-without-context — DCI protocol handler with JWT/signature verification
        transactions = env["spp.dci.transaction"].sudo().search(domain, limit=1)

        # Per SPDCI spec, txnstatus_response contains:
        # - txn_type: search, subscribe, receipt (same as request)
        # - txn_status: The actual response object (SearchResponse, SubscribeResponse, etc.)
        #
        # Note: txn_type in response should match request (no mapping needed)
        response_txn_type = req_criteria.txn_type

        if transactions:
            txn = transactions[0]
            # Try to get the stored response payload, otherwise construct minimal response
            if txn.response_payload:
                try:
                    txn_status_obj = json.loads(txn.response_payload)
                except (json.JSONDecodeError, TypeError):
                    txn_status_obj = _build_minimal_search_response(
                        txn.transaction_id,
                        txn.dci_status,
                        txn.error_code,
                        txn.error_message,
                    )
            else:
                txn_status_obj = _build_minimal_search_response(
                    txn.transaction_id,
                    txn.dci_status,
                    txn.error_code,
                    txn.error_message,
                )

            txn_status_data = TxnStatusResponseData(
                txn_type=response_txn_type,
                txn_status=txn_status_obj,
            )
            overall_status = "succ" if txn.dci_status != "rjct" else "rjct"
        else:
            # Transaction not found - return minimal rejected response
            txn_status_data = TxnStatusResponseData(
                txn_type=response_txn_type,
                txn_status=_build_minimal_search_response(
                    str(req_criteria.attribute_value),
                    "rjct",
                    "rjct.reference_id.invalid",
                    "Transaction not found",
                ),
            )
            overall_status = "rjct"

        # Build response per SPDCI spec
        status_response = TxnStatusResponse(
            transaction_id=status_request.transaction_id,
            correlation_id=str(uuid.uuid4()),
            txnstatus_response=txn_status_data,
        )

        return _build_response_envelope(
            env,
            envelope.header,
            status_response.model_dump(mode="json", exclude_none=True),
            status_code=overall_status,
            completed_count=1 if overall_status == "succ" else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Error processing txn status: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from e
