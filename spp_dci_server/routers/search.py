# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Search API endpoint for registry synchronization."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import (
    DCICallbackHeader,
    DCIEnvelope,
    SearchRequest,
    SearchResponse,
    SearchResponseItem,
)
from odoo.addons.spp_dci.schemas.constants import (
    MsgHeaderStatusReasonCode,
    SearchStatusReasonCode,
)
from odoo.addons.spp_dci.services import (
    get_sender_id,
    truncate_message,
)

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.rate_limit import check_dci_rate_limit
from ..middleware.signature import verify_bearer_token, verify_dci_signature

_logger = logging.getLogger(__name__)

dci_search_router = APIRouter(tags=["DCI Search"])


@dci_search_router.post(
    "/sync/search",
    response_model=DCIEnvelope,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_registry(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
):
    """
    Search social registry records using DCI protocol.

    Accepts a DCI envelope containing SearchRequest message with query criteria.
    Returns DCI envelope with SearchResponse containing matching records.

    **Authentication**: HTTP Signature verification via DCI envelope

    **Request Structure**:
    ```json
    {
        "signature": "namespace=\"dci\", kidId=\"...\", ...",
        "header": {
            "version": "1.0.0",
            "message_id": "unique-msg-id",
            "message_ts": "2024-01-15T10:30:00Z",
            "action": "search",
            "sender_id": "external-registry",
            "receiver_id": "openspp",
            "total_count": 1
        },
        "message": {
            "transaction_id": "txn-123",
            "search_request": [...]
        }
    }
    ```

    **Response**: DCI envelope with SearchResponse containing matching Person/Group records
    """
    try:
        # Signature has been verified by dependency (verified_sender_id is set)
        envelope = request_envelope

        # Parse message as SearchRequest
        try:
            search_request = SearchRequest.model_validate(envelope.message)
        except Exception as e:
            _logger.error("Invalid SearchRequest message: %s", str(e))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid search request message: {str(e)}",
            ) from e

        _logger.info(
            "DCI search request received - transaction_id: %s, sender: %s, items: %d",
            search_request.transaction_id,
            envelope.header.sender_id,
            len(search_request.search_request),
        )

        # Execute search using DCISocialSearchService
        try:
            from odoo.addons.spp_dci_server_social.services.search_service import (
                DCISocialSearchService,
            )

            search_service = DCISocialSearchService(env)
            search_response = search_service.execute_search(search_request)
            _logger.info(
                "DCI search completed - transaction_id: %s, items: %d",
                search_request.transaction_id,
                len(search_response.search_response),
            )
        except ImportError as e:
            _logger.error("spp_dci_server_social module not available: %s", str(e))
            # Fallback to stub response if social module not installed
            response_items = []
            for req_item in search_request.search_request:
                item = SearchResponseItem(
                    reference_id=req_item.reference_id,
                    timestamp=datetime.now(UTC),
                    status="rjct",
                    status_reason_code=SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
                    status_reason_message="Social Registry search module not installed",
                )
                response_items.append(item)
            search_response = SearchResponse(
                transaction_id=search_request.transaction_id,
                correlation_id=str(uuid.uuid4()),
                search_response=response_items,
            )
        except Exception as e:
            _logger.error("Error executing search: %s", str(e), exc_info=True)
            # Return error response for all items
            response_items = []
            for req_item in search_request.search_request:
                item = SearchResponseItem(
                    reference_id=req_item.reference_id,
                    timestamp=datetime.now(UTC),
                    status="rjct",
                    status_reason_code=SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
                    status_reason_message=truncate_message(str(e)),
                )
                response_items.append(item)
            search_response = SearchResponse(
                transaction_id=search_request.transaction_id,
                correlation_id=str(uuid.uuid4()),
                search_response=response_items,
            )

        # Get our sender ID from config
        our_sender_id = get_sender_id(env)

        # Determine overall status from search response items
        response_items = search_response.search_response
        total_count = len(response_items)
        completed_count = sum(1 for item in response_items if item.status == "succ")
        rejected_count = sum(1 for item in response_items if item.status == "rjct")

        # Set overall status based on results
        # Note: For success, omit status_reason_code/message per SPDCI spec
        if completed_count == total_count:
            overall_status = "succ"
            status_reason_code = None
            status_reason_message = None
        elif rejected_count == total_count:
            overall_status = "rjct"
            # Use SPDCI-compliant header reason codes (MsgHeaderStatusReasonCode enum)
            status_reason_code = MsgHeaderStatusReasonCode.ERRORS_TOO_MANY.value
            status_reason_message = "All search requests failed"
        else:
            overall_status = "part"
            # For partial success, omit reason code per SPDCI spec
            status_reason_code = None
            status_reason_message = f"{completed_count}/{total_count} search requests completed"

        # Build callback header
        callback_header = DCICallbackHeader(
            version=envelope.header.version,
            message_id=str(uuid.uuid4()),
            message_ts=datetime.now(UTC),
            action=f"on-{envelope.header.action}",
            sender_id=our_sender_id,
            receiver_id=envelope.header.sender_id,
            total_count=total_count,
            status=overall_status,
            status_reason_code=status_reason_code,
            status_reason_message=status_reason_message,
            completed_count=completed_count,
        )

        # Sign response with server's private key
        response_signature = ""
        try:
            # Get active signing key
            # Use sudo() for API access - authentication is handled by signature verification
            signing_key_model = env["spp.dci.signing.key"].sudo()  # nosemgrep: odoo-sudo-without-context
            active_key = signing_key_model.get_active_key()

            if not active_key:
                _logger.warning("No active signing key found - response will be unsigned")
            else:
                # Get signer and sign the response
                signer = active_key.get_signer()
                header_dict = callback_header.model_dump(mode="json", exclude_none=True)
                message_dict = search_response.model_dump(mode="json", exclude_none=True)
                response_signature = signer.sign(header_dict, message_dict)
                _logger.debug("Response signed with key: %s", active_key.key_id)
        except Exception as e:
            _logger.warning(
                "Failed to sign response: %s - continuing with unsigned response",
                str(e),
            )
            response_signature = ""

        response_envelope = DCIEnvelope(
            signature=response_signature,
            header=callback_header,
            message=search_response.model_dump(mode="json", exclude_none=True),
        )

        _logger.info(
            "DCI search response sent - transaction_id: %s, items: %d",
            search_request.transaction_id,
            len(response_items),
        )

        return response_envelope

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Error processing DCI search request: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing search request",
        ) from e
