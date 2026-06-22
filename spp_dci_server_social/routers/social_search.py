# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Social Registry search endpoints"""

import logging
from datetime import datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas.search import SearchRequest, SearchResponse

from fastapi import APIRouter, Depends, HTTPException, status

_logger = logging.getLogger(__name__)

social_search_router = APIRouter(tags=["DCI Social Registry"], prefix="/registry/social")


@social_search_router.post(
    "/sync/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
)
async def sync_search(
    request: SearchRequest,
    env: Annotated[Environment, Depends(odoo_env)],
):
    """
    Synchronous search for Social Registry persons/groups.

    Implements DCI sync search pattern - returns immediate results.

    Request body contains:
    - transaction_id: Unique transaction identifier
    - search_request: List of search request items with criteria

    Each search criteria supports:
    - query_type: "idtype-value" or "expression"
    - reg_type: Should be "SOCIAL_REGISTRY"
    - pagination: page_size, page_number
    - sort: Optional sort specifications

    Returns SearchResponse with matching Person/Group records.
    """
    from ..services.search_service import DCISocialSearchService

    service = DCISocialSearchService(env)

    try:
        response = service.execute_search(request)
        return response
    except Exception as e:
        _logger.exception("Error executing DCI social registry search: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}",
        ) from e


@social_search_router.post(
    "/sync/notify",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def sync_notify(
    env: Annotated[Environment, Depends(odoo_env)],
):
    """
    Receive notification from external DCI client.

    This endpoint is not yet implemented. In a full implementation, this would:
    1. Validate the notification signature
    2. Parse the notification payload
    3. Process the event (create/update/delete records)
    4. Return acknowledgment

    Returns 501 Not Implemented with DCI rejection response.
    """
    _logger.info("DCI Social Registry notification endpoint called but not implemented")
    return {
        "status": "rjct",
        "status_reason_code": "rjct.search_criteria.invalid",
        "status_reason_message": "Notification endpoint is not yet implemented",
        "timestamp": datetime.utcnow().isoformat(),
    }
