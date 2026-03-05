# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Aggregation API endpoints for population analytics."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.aggregation import (
    AggregationResponse,
    ComputeAggregationRequest,
    DimensionsListResponse,
)
from ..services.aggregation_api_service import AggregationApiService

_logger = logging.getLogger(__name__)

aggregation_router = APIRouter(tags=["Aggregation"], prefix="/aggregation")


@aggregation_router.post(
    "/compute",
    response_model=AggregationResponse,
    summary="Compute population aggregation",
    description="Compute population counts and statistics with optional demographic breakdowns.",
)
async def compute_aggregation(
    request: ComputeAggregationRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Compute aggregation for a scope with optional breakdown.

    Requires:
        aggregation:read scope

    Response:
        AggregationResponse with total_count, statistics, and optional breakdown
    """
    if not api_client.has_scope("aggregation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have aggregation:read scope",
        )

    try:
        service = AggregationApiService(env)
        result = service.compute_aggregation(
            scope_dict=request.scope.model_dump(),
            statistics=request.statistics,
            group_by=request.group_by,
        )
        return result

    except ValueError as e:
        _logger.warning("Invalid aggregation request: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        _logger.error("Aggregation computation failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute aggregation",
        ) from e


@aggregation_router.get(
    "/dimensions",
    response_model=DimensionsListResponse,
    summary="List available dimensions",
    description="Returns active demographic dimensions available for group_by.",
)
async def list_dimensions(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    applies_to: Annotated[
        str | None,
        Query(description="Filter: 'individuals', 'groups', or None for all"),
    ] = None,
):
    """List active demographic dimensions.

    Requires:
        aggregation:read scope

    Response:
        DimensionsListResponse with available dimensions
    """
    if not api_client.has_scope("aggregation", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have aggregation:read scope",
        )

    try:
        service = AggregationApiService(env)
        dimensions = service.list_dimensions(applies_to=applies_to)
        return {"dimensions": dimensions}

    except Exception as e:
        _logger.error("Failed to list dimensions: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list dimensions",
        ) from e
