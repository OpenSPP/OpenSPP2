# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OGC API - Features endpoints.

Implements the OGC API - Features Core standard (Part 1: Core) for
GovStack GIS Building Block compliance. Maps existing GIS report data
and data layers to OGC-compliant feature collections.

Endpoints:
    GET /gis/ogc/                           Landing page
    GET /gis/ogc/conformance                Conformance classes
    GET /gis/ogc/collections                List all collections
    GET /gis/ogc/collections/{id}           Single collection metadata
    GET /gis/ogc/collections/{id}/items     Feature items (GeoJSON)
    GET /gis/ogc/collections/{id}/items/{fid} Single feature
    GET /gis/ogc/collections/{id}/qml       QGIS style file (extension)
"""

import json
import logging
import re
from typing import Annotated

from odoo.api import Environment
from odoo.exceptions import MissingError

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status

from ..schemas.ogc import (
    CollectionInfo,
    Collections,
    Conformance,
    LandingPage,
)
from ..services.ogc_service import OGCService
from ..services.qml_template_service import QMLTemplateService

_logger = logging.getLogger(__name__)

ogc_features_router = APIRouter(tags=["GIS - OGC API Features"], prefix="/gis/ogc")


def _get_base_url(request: Request) -> str:
    """Extract base URL from request for self-referencing links.

    Args:
        request: FastAPI request object

    Returns:
        Base URL string (scheme + host + API prefix)
    """
    # Build from request URL, stripping the OGC path suffix
    url = str(request.base_url).rstrip("/")
    return f"{url}/api/v2/spp"


def _check_gis_read_scope(api_client):
    """Verify client has gis:read scope.

    Args:
        api_client: Authenticated API client

    Raises:
        HTTPException: If scope check fails
    """
    if not api_client.has_scope("gis", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read scope",
        )


@ogc_features_router.get(
    "",
    response_model=LandingPage,
    summary="OGC API landing page",
    description="Provides links to the API definition, conformance, and collections.",
)
async def get_landing_page(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """OGC API - Features landing page."""
    _check_gis_read_scope(api_client)

    base_url = _get_base_url(request)
    service = OGCService(env, base_url)
    return service.get_landing_page()


@ogc_features_router.get(
    "/conformance",
    response_model=Conformance,
    summary="OGC conformance classes",
    description="Declares which OGC API conformance classes this server implements.",
)
async def get_conformance(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """OGC API conformance declaration."""
    _check_gis_read_scope(api_client)

    service = OGCService(env)
    return service.get_conformance()


@ogc_features_router.get(
    "/collections",
    response_model=Collections,
    response_model_exclude_none=True,
    summary="List feature collections",
    description=("Lists all available feature collections. Each GIS report and data layer becomes a collection."),
)
async def get_collections(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """List all OGC feature collections."""
    _check_gis_read_scope(api_client)

    base_url = _get_base_url(request)
    service = OGCService(env, base_url)
    return service.get_collections()


@ogc_features_router.get(
    "/collections/{collection_id}",
    response_model=CollectionInfo,
    response_model_exclude_none=True,
    summary="Collection metadata",
    description="Returns metadata for a single feature collection.",
)
async def get_collection(
    collection_id: Annotated[str, Path(description="Collection identifier")],
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Get single collection metadata."""
    _check_gis_read_scope(api_client)

    try:
        base_url = _get_base_url(request)
        service = OGCService(env, base_url)
        return service.get_collection(collection_id)
    except MissingError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@ogc_features_router.get(
    "/collections/{collection_id}/items",
    summary="Feature items",
    description=(
        "Returns features from a collection as a GeoJSON FeatureCollection. "
        "Supports pagination via limit/offset and spatial filtering via bbox."
    ),
)
async def get_collection_items(
    collection_id: Annotated[str, Path(description="Collection identifier")],
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    limit: Annotated[int, Query(description="Maximum number of features", ge=1, le=10000)] = 1000,
    offset: Annotated[int, Query(description="Pagination offset", ge=0)] = 0,
    bbox: Annotated[
        str | None,
        Query(
            description=("Bounding box filter: west,south,east,north (e.g., -180,-90,180,90)"),
        ),
    ] = None,
):
    """Get features from a collection.

    Returns GeoJSON FeatureCollection with OGC pagination links.
    """
    _check_gis_read_scope(api_client)

    # Parse bbox parameter
    bbox_list = None
    if bbox:
        try:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox must have exactly 4 values")
            bbox_list = parts
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bbox parameter: {e}",
            ) from e

    try:
        base_url = _get_base_url(request)
        service = OGCService(env, base_url)
        result = service.get_collection_items(
            collection_id,
            limit=limit,
            offset=offset,
            bbox=bbox_list,
        )
        return Response(
            content=_json_dumps(result),
            media_type="application/geo+json",
            headers={"Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"},
        )
    except MissingError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@ogc_features_router.options(
    "/collections/{collection_id}/items",
    summary="Advertise supported methods for items endpoint",
    include_in_schema=False,
)
async def options_collection_items(
    collection_id: Annotated[str, Path(description="Collection identifier")],
):
    """Handle OPTIONS requests from OAPIF clients (e.g. QGIS).

    QGIS sends OPTIONS to discover allowed methods before fetching features.
    """
    return Response(
        status_code=200,
        headers={
            "Allow": "GET, HEAD, OPTIONS",
            "Accept": "application/geo+json, application/json",
        },
    )


@ogc_features_router.get(
    "/collections/{collection_id}/items/{feature_id}",
    summary="Single feature",
    description="Returns a single feature from a collection.",
)
async def get_collection_item(
    collection_id: Annotated[str, Path(description="Collection identifier")],
    feature_id: Annotated[str, Path(description="Feature identifier")],
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Get a single feature by ID."""
    _check_gis_read_scope(api_client)

    try:
        base_url = _get_base_url(request)
        service = OGCService(env, base_url)
        result = service.get_collection_item(collection_id, feature_id)
        return Response(
            content=_json_dumps(result),
            media_type="application/geo+json",
            headers={"Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"},
        )
    except MissingError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@ogc_features_router.get(
    "/collections/{collection_id}/qml",
    summary="QGIS style file (OpenSPP extension)",
    description=(
        "Returns a QML style file for the collection. "
        "This is an OpenSPP extension to the OGC API standard, "
        "used by the QGIS plugin for automatic layer styling."
    ),
    response_class=Response,
)
async def get_collection_qml(
    collection_id: Annotated[str, Path(description="Collection identifier")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    field_name: Annotated[str | None, Query(description="Field to symbolize")] = None,
    opacity: Annotated[float, Query(description="Layer opacity (0.0-1.0)", ge=0.0, le=1.0)] = 0.7,
):
    """Get QGIS style file (QML) for collection.

    Returns a QML XML file that can be loaded in QGIS to style the layer
    according to the report's color scheme and thresholds. Only available
    for report-based collections.
    """
    _check_gis_read_scope(api_client)

    try:
        # Resolve collection to a report for QML generation
        admin_level = None
        if collection_id.startswith("layer_"):
            # Report-driven data layers can provide QML via their linked report
            try:
                layer_database_id = int(collection_id[6:])
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="QML styles only available for report-based collections",
                ) from e
            if layer_database_id <= 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="QML styles only available for report-based collections",
                )
            layer = env["spp.gis.data.layer"].sudo().browse(layer_database_id)
            if not layer.exists() or not (
                hasattr(layer, "source_type") and layer.source_type == "report" and layer.report_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="QML styles only available for report-based collections",
                )
            report = layer.report_id
        else:
            # Strip _admN suffix before report lookup
            report_code = collection_id
            admin_level = None
            match = re.match(r"^(.+)_adm(\d+)$", collection_id)
            if match:
                report_code = match.group(1)
                admin_level = int(match.group(2))
            report = env["spp.gis.report"].sudo().search([("code", "=", report_code)], limit=1)
            if not report:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Report with code '{report_code}' not found",
                )

        # Generate QML (use report.env which is already sudo from line above)
        # Pass admin_level so thresholds can be adapted to the level's data range
        qml_service = QMLTemplateService(report.env)
        qml_xml = qml_service.generate_qml(
            report_id=report.id,
            geometry_type=report.geometry_type,
            field_name=field_name,
            opacity=opacity,
            admin_level=admin_level,
        )

        return Response(
            content=qml_xml,
            media_type="text/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{collection_id}.qml"',
            },
        )

    except HTTPException:
        raise
    except ValueError as e:
        _logger.warning("Invalid QML request for %s: %s", collection_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        _logger.error("Error generating QML for %s: %s", collection_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate QML style file",
        ) from e


def _json_dumps(data):
    """Serialize data to JSON string.

    Args:
        data: Data to serialize

    Returns:
        JSON string
    """
    return json.dumps(data, default=str)
