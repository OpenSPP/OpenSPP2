# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Export API endpoints for GeoPackage and offline data."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from ..services.export_service import ExportService

_logger = logging.getLogger(__name__)

export_router = APIRouter(tags=["GIS"], prefix="/gis")


@export_router.get(
    "/export/geopackage",
    summary="Export layers as GeoPackage",
    description="Export layers and geofences as GeoPackage (.gpkg) or ZIP of GeoJSON files for offline use in QGIS.",
    response_class=Response,
)
async def export_geopackage(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    layer_ids: Annotated[
        str | None,
        Query(description="Comma-separated list of report codes to include (exports all if omitted)"),
    ] = None,
    include_geofences: Annotated[
        bool,
        Query(description="Include user's geofences in export"),
    ] = True,
    admin_level: Annotated[
        int | None,
        Query(description="Filter layers by admin level"),
    ] = None,
):
    """Export GIS data as GeoPackage for offline use.

    This endpoint exports selected layers and geofences in a format suitable for
    offline use in QGIS or other GIS applications.

    **Export Format:**
    - Attempts to create a GeoPackage (.gpkg) file if fiona is available
    - Falls back to ZIP of GeoJSON files (.geojson) if GeoPackage creation fails
    - Both formats are compatible with QGIS 3.28+

    **What's Included:**
    - Each requested layer as a separate table/file
    - User's active geofences (if include_geofences=true)
    - Proper geometry columns and CRS (EPSG:4326)

    **Usage in QGIS:**
    - GeoPackage: Drag and drop .gpkg file into QGIS
    - ZIP: Extract and drag .geojson files into QGIS
    - Load corresponding .qml style files for proper visualization

    Args:
        env: Odoo environment
        api_client: Authenticated API client
        layer_ids: Comma-separated report codes (e.g., "pop_density,poverty_rate")
        include_geofences: Whether to include user's saved geofences
        admin_level: Filter layers to specific admin level (e.g., 2 for districts)

    Returns:
        Response: Binary file download (GeoPackage or ZIP)

    Raises:
        HTTPException: 403 if missing scope, 400 if no data available
    """
    # Check read scope
    if not api_client.has_scope("gis", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read scope",
        )

    try:
        # Parse layer_ids
        layer_ids_list = None
        if layer_ids:
            layer_ids_list = [code.strip() for code in layer_ids.split(",") if code.strip()]

        # Get export service
        export_service = ExportService(env)

        # Generate export
        file_bytes, filename, content_type = export_service.export_geopackage(
            layer_ids=layer_ids_list,
            include_geofences=include_geofences,
            admin_level=admin_level,
        )

        # Log export operation
        layer_count = len(layer_ids_list) if layer_ids_list else "all"
        _logger.info(
            "GIS export completed: %d bytes, format=%s, layers=%s, geofences=%s, admin_level=%s",
            len(file_bytes),
            content_type,
            layer_count,
            include_geofences,
            admin_level,
        )

        # Return file download
        return Response(
            content=file_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(file_bytes)),
            },
        )

    except ValueError as e:
        _logger.warning("Invalid export request: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        _logger.error("Error exporting GIS data: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export GIS data",
        ) from e
