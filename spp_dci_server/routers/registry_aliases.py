# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""SPDCI-compliant registry type endpoints.

Provides paths for different registry types:
- /disability/registry/* - Disability Registry
- /crvs/registry/* - Civil Registration and Vital Statistics
- /farmer/registry/* - Farmer Registry

These endpoints will be implemented as corresponding modules are added.
For now, they return appropriate "not implemented" responses for SPDCI compliance testing.
"""

import logging
from datetime import datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas.constants import MsgHeaderStatusReasonCode
from odoo.addons.spp_dci.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResponseItem,
)

from fastapi import APIRouter, Depends, status

from ..middleware.signature import verify_bearer_token

_logger = logging.getLogger(__name__)

# Disability Registry router
disability_router = APIRouter(tags=["Disability Registry"], prefix="/disability/registry")


@disability_router.post(
    "/sync/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def disability_sync_search(
    request: SearchRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    SPDCI-compliant Disability Registry synchronous search endpoint.

    Path: /disability/registry/sync/search

    This endpoint will be implemented when the Disability Registry module is added.
    For now, returns "not implemented" response for SPDCI compliance testing.
    """
    _logger.warning("Disability Registry search endpoint called but not yet implemented")

    # Build response items with "not implemented" status
    response_items = []
    for req_item in request.search_request:
        response_items.append(
            SearchResponseItem(
                reference_id=req_item.reference_id,
                timestamp=datetime.utcnow(),
                status="rjct",
                status_reason_code=MsgHeaderStatusReasonCode.ACTION_NOT_SUPPORTED.value,
                status_reason_message="Disability Registry not yet implemented. Will be available in spp_dci_server_disability module.",
                data=None,
                pagination=None,
                locale=req_item.locale,
            )
        )

    return SearchResponse(
        transaction_id=request.transaction_id,
        correlation_id=None,
        search_response=response_items,
    )


@disability_router.post(
    "/sync/notify",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def disability_sync_notify(
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    SPDCI-compliant Disability Registry notification endpoint.

    Path: /disability/registry/sync/notify

    This endpoint will be implemented when the Disability Registry module is added.
    """
    _logger.warning("Disability Registry notify endpoint called but not yet implemented")
    return {
        "status": "rjct",
        "message": "Disability Registry not yet implemented",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Civil Registry router
crvs_router = APIRouter(tags=["Civil Registry"], prefix="/crvs/registry")


@crvs_router.post(
    "/sync/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def crvs_sync_search(
    request: SearchRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    SPDCI-compliant Civil Registry synchronous search endpoint.

    Path: /crvs/registry/sync/search

    This endpoint will be implemented when the Civil Registry module is added.
    For now, returns "not implemented" response for SPDCI compliance testing.
    """
    _logger.warning("Civil Registry search endpoint called but not yet implemented")

    # Build response items with "not implemented" status
    response_items = []
    for req_item in request.search_request:
        response_items.append(
            SearchResponseItem(
                reference_id=req_item.reference_id,
                timestamp=datetime.utcnow(),
                status="rjct",
                status_reason_code=MsgHeaderStatusReasonCode.ACTION_NOT_SUPPORTED.value,
                status_reason_message="Civil Registry not yet implemented. Will be available in spp_dci_server_crvs module.",
                data=None,
                pagination=None,
                locale=req_item.locale,
            )
        )

    return SearchResponse(
        transaction_id=request.transaction_id,
        correlation_id=None,
        search_response=response_items,
    )


@crvs_router.post(
    "/sync/notify",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def crvs_sync_notify(
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    SPDCI-compliant Civil Registry notification endpoint.

    Path: /crvs/registry/sync/notify

    This endpoint will be implemented when the Civil Registry module is added.
    """
    _logger.warning("Civil Registry notify endpoint called but not yet implemented")
    return {
        "status": "rjct",
        "message": "Civil Registry not yet implemented",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Farmer Registry router
farmer_router = APIRouter(tags=["Farmer Registry"], prefix="/farmer/registry")


@farmer_router.post(
    "/sync/search",
    response_model=SearchResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def farmer_sync_search(
    request: SearchRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    SPDCI-compliant Farmer Registry synchronous search endpoint.

    Path: /farmer/registry/sync/search

    This endpoint will be implemented when the Farmer Registry module is added.
    For now, returns "not implemented" response for SPDCI compliance testing.
    """
    _logger.warning("Farmer Registry search endpoint called but not yet implemented")

    # Build response items with "not implemented" status
    response_items = []
    for req_item in request.search_request:
        response_items.append(
            SearchResponseItem(
                reference_id=req_item.reference_id,
                timestamp=datetime.utcnow(),
                status="rjct",
                status_reason_code=MsgHeaderStatusReasonCode.ACTION_NOT_SUPPORTED.value,
                status_reason_message="Farmer Registry not yet implemented. Will be available in spp_dci_server_farmer module.",
                data=None,
                pagination=None,
                locale=req_item.locale,
            )
        )

    return SearchResponse(
        transaction_id=request.transaction_id,
        correlation_id=None,
        search_response=response_items,
    )


@farmer_router.post(
    "/sync/notify",
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def farmer_sync_notify(
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
):
    """
    SPDCI-compliant Farmer Registry notification endpoint.

    Path: /farmer/registry/sync/notify

    This endpoint will be implemented when the Farmer Registry module is added.
    """
    _logger.warning("Farmer Registry notify endpoint called but not yet implemented")
    return {
        "status": "rjct",
        "message": "Farmer Registry not yet implemented",
        "timestamp": datetime.utcnow().isoformat(),
    }
