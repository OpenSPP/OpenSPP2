# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Spatial query API endpoints for querying statistics within arbitrary polygons."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ..schemas.query import (
    BatchSpatialQueryRequest,
    BatchSpatialQueryResponse,
    SpatialQueryRequest,
    SpatialQueryResponse,
)
from ..services.spatial_query_service import SpatialQueryService

_logger = logging.getLogger(__name__)

spatial_query_router = APIRouter(tags=["GIS"], prefix="/gis")


@spatial_query_router.post(
    "/query/statistics",
    summary="Query statistics for polygon",
    description="Query registrant statistics within arbitrary polygon using PostGIS.",
    response_model=SpatialQueryResponse,
)
async def query_statistics(
    request: Annotated[SpatialQueryRequest, Body(...)],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> SpatialQueryResponse:
    """Query statistics within polygon.

    This endpoint accepts a GeoJSON polygon and returns aggregated statistics
    for registrants within that area. It uses PostGIS spatial queries for
    efficient computation.

    Query methods:
    - coordinates: Direct spatial query when registrants have coordinates (preferred)
    - area_fallback: Match via area_id when coordinates not available

    Statistics are computed by the unified aggregation service.
    """
    # Check read scope - accept either gis:read or statistics:read
    if not (api_client.has_scope("gis", "read") or api_client.has_scope("statistics", "read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read or statistics:read scope",
        )

    try:
        # Initialize service
        service = SpatialQueryService(env)

        # Execute spatial query
        result = service.query_statistics(
            geometry=request.geometry,
            filters=request.filters,
            variables=request.variables,
        )

        # Remove internal registrant_ids from response
        result.pop("registrant_ids", None)

        return SpatialQueryResponse(**result)

    except ValueError as e:
        _logger.warning("Invalid query parameters: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        _logger.exception("Spatial query failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Spatial query failed",
        ) from e


@spatial_query_router.post(
    "/query/statistics/batch",
    summary="Batch query statistics for multiple polygons",
    description="Query registrant statistics for multiple polygons individually. "
    "Returns per-geometry results plus an aggregate summary.",
    response_model=BatchSpatialQueryResponse,
)
async def query_statistics_batch(
    request: Annotated[BatchSpatialQueryRequest, Body(...)],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> BatchSpatialQueryResponse:
    """Batch query statistics for multiple geometries.

    Each geometry is queried independently, returning per-shape statistics
    that can be used for thematic map visualization. A summary field provides
    the deduplicated aggregate across all shapes.
    """
    # Check read scope - accept either gis:read or statistics:read
    if not (api_client.has_scope("gis", "read") or api_client.has_scope("statistics", "read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read or statistics:read scope",
        )

    try:
        service = SpatialQueryService(env)

        # Convert pydantic models to dicts for the service
        geometries = [{"id": item.id, "geometry": item.geometry} for item in request.geometries]

        result = service.query_statistics_batch(
            geometries=geometries,
            filters=request.filters,
            variables=request.variables,
        )

        return BatchSpatialQueryResponse(**result)

    except ValueError as e:
        _logger.warning("Invalid batch query parameters: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None
    except Exception:
        _logger.exception("Batch spatial query failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch spatial query failed",
        ) from None
