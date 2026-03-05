# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Proximity query API endpoint for finding registrants within/beyond radius of reference points."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ..schemas.query import ProximityQueryRequest, ProximityQueryResponse
from ..services.spatial_query_service import SpatialQueryService

_logger = logging.getLogger(__name__)

proximity_router = APIRouter(tags=["GIS"], prefix="/gis")


@proximity_router.post(
    "/query/proximity",
    summary="Query statistics by proximity to reference points",
    description="Find registrants within or beyond a given radius from a set of "
    "reference points (e.g., health centers). Supports thousands of reference points "
    "using pre-buffered spatial indexes.",
    response_model=ProximityQueryResponse,
)
async def query_proximity(
    request: Annotated[ProximityQueryRequest, Body(...)],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
) -> ProximityQueryResponse:
    """Query registrant statistics by proximity to reference points.

    Accepts a list of reference point coordinates and a radius. Returns
    aggregated statistics for registrants that are within or beyond the
    specified distance from any of the reference points.

    The server pre-buffers reference points and uses ST_Intersects against
    indexed registrant coordinates for efficient queries.
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
        reference_points = [{"longitude": pt.longitude, "latitude": pt.latitude} for pt in request.reference_points]

        result = service.query_proximity(
            reference_points=reference_points,
            radius_km=request.radius_km,
            relation=request.relation,
            filters=request.filters,
            variables=request.variables,
        )

        # Remove internal registrant_ids from response
        result.pop("registrant_ids", None)

        return ProximityQueryResponse(**result)

    except ValueError as e:
        _logger.warning("Invalid proximity query parameters: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None
    except Exception as e:
        _logger.exception("Proximity query failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Proximity query failed: {str(e)}",
        ) from None
