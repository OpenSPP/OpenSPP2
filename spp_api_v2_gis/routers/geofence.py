# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Geofence API endpoints for saving areas of interest."""

import json
import logging
from typing import Annotated

from odoo.api import Environment
from odoo.exceptions import ValidationError

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from ..schemas.geofence import (
    GeofenceCreateRequest,
    GeofenceListItem,
    GeofenceListResponse,
    GeofenceResponse,
)

_logger = logging.getLogger(__name__)

geofence_router = APIRouter(tags=["GIS"], prefix="/gis")


@geofence_router.post(
    "/geofences",
    response_model=GeofenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create geofence",
    description="Save area of interest as a geofence from GeoJSON.",
)
async def create_geofence(
    request: GeofenceCreateRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """Create a new geofence from GeoJSON.

    Args:
        request: Geofence creation request with name, geometry, and optional fields
        env: Odoo environment
        api_client: Authenticated API client
        response: FastAPI response object for setting headers

    Returns:
        GeofenceResponse with created geofence details

    Raises:
        HTTPException: 403 if missing scope, 422 if validation fails
    """
    # Check geofence scope
    if not api_client.has_scope("gis", "geofence"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:geofence scope",
        )

    # Get the geofence model
    geofence_model = env["spp.gis.geofence"]

    # Prepare kwargs for optional fields
    kwargs = {}
    if request.description:
        kwargs["description"] = request.description

    # Handle incident_code if provided
    if request.incident_code:
        # Find incident by code (external ID)
        incident = env["spp.hazard.incident"].search([("code", "=", request.incident_code)], limit=1)
        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incident with code '{request.incident_code}' not found",
            )
        kwargs["incident_id"] = incident.id

    try:
        # Convert geometry dict to JSON string for create_from_geojson
        geometry_json = json.dumps(request.geometry)

        # Create geofence using model method
        geofence = geofence_model.create_from_geojson(
            geojson_str=geometry_json,
            name=request.name,
            geofence_type=request.geofence_type,
            created_from="api",
            **kwargs,
        )

        # Set Location header
        response.headers["Location"] = f"/api/v2/spp/gis/geofences/{geofence.id}"

        # Return response
        return GeofenceResponse(
            id=geofence.id,
            name=geofence.name,
            description=geofence.description,
            geofence_type=geofence.geofence_type,
            area_sqkm=geofence.area_sqkm,
            active=geofence.active,
            created_from=geofence.created_from,
        )

    except ValidationError as e:
        _logger.warning("Validation error creating geofence: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        _logger.exception("Error creating geofence")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create geofence: {str(e)}",
        ) from e


@geofence_router.get(
    "/geofences",
    response_model=GeofenceListResponse,
    summary="List geofences",
    description="List saved geofences with optional filtering and pagination.",
)
async def list_geofences(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    geofence_type: Annotated[str | None, Query()] = None,
    incident_id: Annotated[int | None, Query()] = None,
    active: Annotated[bool | None, Query()] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """List geofences with optional filters.

    Args:
        env: Odoo environment
        api_client: Authenticated API client
        geofence_type: Filter by geofence type (hazard_zone, service_area, targeting_area, custom)
        incident_id: Filter by related incident ID
        active: Filter by active status (default: True)
        count: Number of results per page (default: 20, max: 100)
        offset: Number of results to skip (default: 0)

    Returns:
        GeofenceListResponse with list of geofences and pagination info

    Raises:
        HTTPException: 403 if missing scope
    """
    # Check read scope
    if not api_client.has_scope("gis", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read scope",
        )

    # Build search domain
    domain = []
    if geofence_type:
        domain.append(("geofence_type", "=", geofence_type))
    if incident_id is not None:
        domain.append(("incident_id", "=", incident_id))
    if active is not None:
        domain.append(("active", "=", active))
    else:
        # Default to active geofences only
        domain.append(("active", "=", True))

    # Get geofence model
    geofence_model = env["spp.gis.geofence"]

    # Get total count
    total = geofence_model.search_count(domain)

    # Search with pagination
    geofences = geofence_model.search(domain, limit=count, offset=offset, order="name")

    # Convert to response schema
    items = [
        GeofenceListItem(
            id=geofence.id,
            name=geofence.name,
            geofence_type=geofence.geofence_type,
            area_sqkm=geofence.area_sqkm,
            active=geofence.active,
        )
        for geofence in geofences
    ]

    return GeofenceListResponse(
        geofences=items,
        total=total,
        offset=offset,
        count=len(items),
    )


@geofence_router.get(
    "/geofences/{geofence_id}",
    summary="Get geofence",
    description="Get a single geofence with full GeoJSON representation.",
)
async def get_geofence(
    geofence_id: Annotated[int, Path(description="Geofence ID")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Get a single geofence by ID.

    Returns the full GeoJSON Feature representation including geometry.

    Args:
        geofence_id: Database ID of the geofence
        env: Odoo environment
        api_client: Authenticated API client

    Returns:
        dict: GeoJSON Feature with geometry and properties

    Raises:
        HTTPException: 403 if missing scope, 404 if not found
    """
    # Check read scope
    if not api_client.has_scope("gis", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read scope",
        )

    # Get geofence model
    geofence_model = env["spp.gis.geofence"]

    # Search for geofence
    geofence = geofence_model.browse(geofence_id)

    if not geofence.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geofence with ID {geofence_id} not found",
        )

    # Return full GeoJSON representation
    try:
        return geofence.to_geojson()
    except Exception as e:
        _logger.exception("Error converting geofence to GeoJSON")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert geofence to GeoJSON: {str(e)}",
        ) from e


@geofence_router.delete(
    "/geofences/{geofence_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive geofence",
    description="Soft delete a geofence by setting active=False.",
)
async def delete_geofence(
    geofence_id: Annotated[int, Path(description="Geofence ID")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Archive a geofence (soft delete).

    Sets active=False rather than permanently deleting the record.

    Args:
        geofence_id: Database ID of the geofence
        env: Odoo environment
        api_client: Authenticated API client

    Raises:
        HTTPException: 403 if missing scope, 404 if not found
    """
    # Check geofence scope (same as create)
    if not api_client.has_scope("gis", "geofence"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:geofence scope",
        )

    # Get geofence model
    geofence_model = env["spp.gis.geofence"]

    # Search for geofence
    geofence = geofence_model.browse(geofence_id)

    if not geofence.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Geofence with ID {geofence_id} not found",
        )

    # Soft delete by setting active=False
    try:
        geofence.write({"active": False})
    except Exception as e:
        _logger.exception("Error archiving geofence")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive geofence: {str(e)}",
        ) from e
