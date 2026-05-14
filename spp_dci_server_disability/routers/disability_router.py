"""DCI Disability Registry FastAPI router.

Replaces spp_dci_server's 501 stub at ``/disability/registry/sync/search``
with a real handler backed by ``DisabilitySearchService``. The router
mounts under the existing ``/disability/registry`` prefix so SP-side
clients (e.g., the bridge dispatcher) reach it at the canonical path.

Authentication / signature verification reuses spp_dci_server's
middleware — no security delta from the stub.
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
    SearchRequest,
    SearchResponse,
    SearchResponseItem,
)
from odoo.addons.spp_dci.schemas.constants import (
    MsgHeaderStatusReasonCode,
    SearchStatusReasonCode,
)
from odoo.addons.spp_dci.services import get_sender_id, truncate_message
from odoo.addons.spp_dci_server.middleware.signature import (
    verify_bearer_token,
    verify_dci_signature,
)

from fastapi import APIRouter, Depends, HTTPException, status

from ..services.disability_search_service import DisabilitySearchService

_logger = logging.getLogger(__name__)

# Same prefix as spp_dci_server's stub router so the canonical
# /disability/registry/sync/search path is honoured.
disability_search_router = APIRouter(
    tags=["Disability Registry"],
    prefix="/disability/registry",
)


@disability_search_router.post(
    "/sync/search",
    response_model=DCIEnvelope,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def disability_sync_search(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    verified_sender_id: Annotated[str, Depends(verify_dci_signature)],
):
    """SPDCI-compliant Disability Registry synchronous search endpoint.

    Mirrors the shape of spp_dci_server's main ``/sync/search`` handler:
    parse the envelope, dispatch to a search service, build a signed
    callback envelope back. The disability-specific logic lives in
    ``DisabilitySearchService``.
    """
    envelope = request_envelope

    try:
        search_request = SearchRequest.model_validate(envelope.message)
    except Exception as e:
        _logger.error("Invalid SearchRequest message: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search request message: {str(e)}",
        ) from e

    _logger.info(
        "DR search request received — transaction_id: %s, sender: %s, items: %d",
        search_request.transaction_id,
        envelope.header.sender_id,
        len(search_request.search_request),
    )

    try:
        search_service = DisabilitySearchService(env)
        search_response = search_service.execute_search(search_request)
    except Exception as e:
        _logger.error("Error executing DR search: %s", str(e), exc_info=True)
        # Build a rejection response item per request item, then continue
        # building the envelope. This mirrors spp_dci_server's pattern of
        # surfacing service-level failures through DCI status codes
        # rather than HTTP 500s — the SP side has already parsed our
        # envelope; let it parse the rejection too.
        response_items = [
            SearchResponseItem(
                reference_id=req_item.reference_id,
                timestamp=datetime.now(UTC),
                status="rjct",
                status_reason_code=SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
                status_reason_message=truncate_message(str(e)),
            )
            for req_item in search_request.search_request
        ]
        search_response = SearchResponse(
            transaction_id=search_request.transaction_id,
            correlation_id=str(uuid.uuid4()),
            search_response=response_items,
        )

    response_items = search_response.search_response
    total_count = len(response_items)
    completed_count = sum(1 for item in response_items if item.status == "succ")
    rejected_count = sum(1 for item in response_items if item.status == "rjct")

    if completed_count == total_count:
        overall_status = "succ"
        status_reason_code = None
        status_reason_message = None
    elif rejected_count == total_count:
        overall_status = "rjct"
        status_reason_code = MsgHeaderStatusReasonCode.ERRORS_TOO_MANY.value
        status_reason_message = "All DR search requests failed"
    else:
        overall_status = "part"
        status_reason_code = None
        status_reason_message = f"{completed_count}/{total_count} DR search requests completed"

    our_sender_id = get_sender_id(env)

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

    response_signature = ""
    try:
        # sudo() for API access — authentication is via signature verification.
        signing_key_model = env["spp.dci.signing.key"].sudo()  # nosemgrep: odoo-sudo-without-context
        active_key = signing_key_model.get_active_key()
        if active_key:
            signer = active_key.get_signer()
            header_dict = callback_header.model_dump(mode="json", exclude_none=True)
            message_dict = search_response.model_dump(mode="json", exclude_none=True)
            response_signature = signer.sign(header_dict, message_dict)
            _logger.debug("DR response signed with key: %s", active_key.key_id)
        else:
            _logger.warning("No active signing key — DR response will be unsigned")
    except Exception as e:
        _logger.warning(
            "Failed to sign DR response: %s — continuing unsigned", str(e)
        )
        response_signature = ""

    return DCIEnvelope(
        signature=response_signature,
        header=callback_header,
        message=search_response.model_dump(mode="json", exclude_none=True),
    )
