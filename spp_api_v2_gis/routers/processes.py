# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OGC API - Processes endpoints.

Implements process discovery and execution per OGC API - Processes Part 1: Core.

Endpoints:
    GET  /gis/ogc/processes                        List available processes
    GET  /gis/ogc/processes/{processId}            Process description
    POST /gis/ogc/processes/{processId}/execution  Execute a process
"""

import logging
import uuid
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Request, Response, status

from ..schemas.processes import (
    ExecuteRequest,
    ProcessDescription,
    ProcessList,
    ProcessSummary,
    StatusInfo,
)
from ..services.process_registry import VALID_PROCESS_IDS, ProcessRegistry
from ..services.spatial_query_service import SpatialQueryService

_logger = logging.getLogger(__name__)

processes_router = APIRouter(tags=["GIS - OGC API Processes"], prefix="/gis/ogc")

# Maximum geometries allowed in a sync request before forcing async
_DEFAULT_FORCED_ASYNC_THRESHOLD = 10
_MAX_GEOMETRIES = 100


def _check_gis_scope(api_client):
    """Verify client has gis:read or statistics:read scope."""
    if not (api_client.has_scope("gis", "read") or api_client.has_scope("statistics", "read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read or statistics:read scope",
        )


def _get_base_url(request: Request) -> str:
    """Extract base URL for self-referencing links."""
    url = str(request.base_url).rstrip("/")
    return f"{url}/api/v2/spp"


def _build_status_info(job, base_url=""):
    """Build a StatusInfo dict from a spp.gis.process.job record."""
    links = []
    ogc_base = f"{base_url}/gis/ogc" if base_url else ""

    if ogc_base:
        links.append({"href": f"{ogc_base}/jobs/{job.job_id}", "rel": "self", "type": "application/json"})
        if job.status == "successful":
            links.append(
                {"href": f"{ogc_base}/jobs/{job.job_id}/results", "rel": "results", "type": "application/json"}
            )

    return StatusInfo(
        jobID=job.job_id,
        processID=job.process_id,
        status=job.status,
        message=job.message,
        created=job.create_date.isoformat() if job.create_date else None,
        started=job.started_at.isoformat() if job.started_at else None,
        finished=job.finished_at.isoformat() if job.finished_at else None,
        updated=job.write_date.isoformat() if job.write_date else None,
        progress=job.progress,
        links=links,
    )


@processes_router.get(
    "/processes",
    response_model=ProcessList,
    summary="List available processes",
    description="Returns a list of all available OGC processes.",
)
async def list_processes(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """List all available OGC processes."""
    _check_gis_scope(api_client)

    registry = ProcessRegistry(env)
    process_dicts = registry.list_processes()

    processes = [ProcessSummary(**p) for p in process_dicts]
    return ProcessList(processes=processes)


@processes_router.get(
    "/processes/{process_id}",
    response_model=ProcessDescription,
    summary="Process description",
    description="Returns the full description of a process, including input/output schemas.",
)
async def get_process_description(
    process_id: Annotated[str, Path(description="Process identifier")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Get full process description with input/output schemas."""
    _check_gis_scope(api_client)

    registry = ProcessRegistry(env)
    description = registry.get_process(process_id)

    if description is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Process '{process_id}' not found",
        )

    return ProcessDescription(**description)


@processes_router.post(
    "/processes/{process_id}/execution",
    summary="Execute a process",
    description="Execute an OGC process synchronously or asynchronously.",
    status_code=200,
)
async def execute_process(
    process_id: Annotated[str, Path(description="Process identifier")],
    execute_request: Annotated[ExecuteRequest, Body(...)],
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    prefer: Annotated[str | None, Header()] = None,
):
    """Execute a process.

    Supports both synchronous and asynchronous execution.
    Use the Prefer: respond-async header to request async execution.
    Batch requests with more than the configured threshold of geometries
    are automatically forced to async.
    """
    _check_gis_scope(api_client)

    # Validate process ID
    if process_id not in VALID_PROCESS_IDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Process '{process_id}' not found",
        )

    inputs = execute_request.inputs

    # Validate and determine sync vs async
    wants_async = prefer and "respond-async" in prefer
    forced_async = False

    if process_id == "spatial-statistics":
        _validate_spatial_statistics_inputs(inputs)
        geometry = inputs.get("geometry")
        if isinstance(geometry, list):
            # Get forced async threshold
            # nosemgrep: odoo-sudo-without-context
            threshold = int(
                env["ir.config_parameter"]
                .sudo()
                .get_param("spp_gis.forced_async_threshold", _DEFAULT_FORCED_ASYNC_THRESHOLD)
            )
            if len(geometry) > threshold:
                forced_async = True
    elif process_id == "proximity-statistics":
        _validate_proximity_statistics_inputs(inputs)

    use_async = wants_async or forced_async

    if use_async:
        return _execute_async(env, api_client, process_id, inputs, request)

    return _execute_sync(env, process_id, inputs)


def _validate_spatial_statistics_inputs(inputs):
    """Validate inputs for spatial-statistics process."""
    geometry = inputs.get("geometry")
    if geometry is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'geometry' input is required",
        )

    if isinstance(geometry, list):
        if len(geometry) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="'geometry' array must not be empty",
            )
        if len(geometry) > _MAX_GEOMETRIES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum {_MAX_GEOMETRIES} geometries allowed per request",
            )
        # Validate each item has {id, value} wrapper
        for i, item in enumerate(geometry):
            if not isinstance(item, dict) or "id" not in item or "value" not in item:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Geometry array item {i} must be an object with 'id' and 'value' keys. "
                    "Bare GeoJSON arrays are not supported; wrap each geometry in {{id, value}}.",
                )
    elif not isinstance(geometry, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'geometry' must be a GeoJSON object or an array of {id, value} objects",
        )


def _validate_proximity_statistics_inputs(inputs):
    """Validate inputs for proximity-statistics process."""
    reference_points = inputs.get("reference_points")
    if not reference_points:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'reference_points' input is required",
        )
    if not isinstance(reference_points, list) or len(reference_points) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'reference_points' must be a non-empty array",
        )
    if len(reference_points) > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10,000 reference points allowed",
        )

    radius_km = inputs.get("radius_km")
    if radius_km is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'radius_km' input is required",
        )
    if not isinstance(radius_km, (int, float)) or radius_km <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'radius_km' must be a positive number",
        )
    if radius_km > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'radius_km' must not exceed 500",
        )

    relation = inputs.get("relation", "within")
    if relation not in ("within", "beyond"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'relation' must be 'within' or 'beyond'",
        )


def _execute_sync(env, process_id, inputs):
    """Execute a process synchronously and return results directly."""
    service = SpatialQueryService(env)

    try:
        if process_id == "spatial-statistics":
            result = _run_spatial_statistics(service, inputs)
        else:
            result = _run_proximity_statistics(service, inputs)

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception:
        _logger.exception("Process execution failed for %s", process_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Process execution failed",
        ) from None


def _execute_async(env, api_client, process_id, inputs, request):
    """Execute a process asynchronously via job_worker."""
    job_id = str(uuid.uuid4())

    # Create job record
    # nosemgrep: odoo-sudo-without-context
    job = (
        env["spp.gis.process.job"]
        .sudo()
        .create(
            {
                "job_id": job_id,
                "process_id": process_id,
                "client_id": api_client.id,
                "inputs": inputs,
            }
        )
    )

    # Enqueue via job_worker
    delayed = job.with_delay(
        channel="gis",
        timeout=300,
        description=f"OGC Process: {process_id} ({job_id})",
    ).execute_process()
    job.job_uuid = delayed.uuid

    base_url = _get_base_url(request)
    status_info = _build_status_info(job, base_url)

    return Response(
        content=status_info.model_dump_json(by_alias=True, exclude_none=True),
        status_code=201,
        media_type="application/json",
        headers={
            "Location": f"{base_url}/gis/ogc/jobs/{job_id}",
        },
    )


def _run_spatial_statistics(service, inputs):
    """Run spatial-statistics process and return results."""
    geometry = inputs.get("geometry")
    filters = inputs.get("filters")
    variables = inputs.get("variables")

    if isinstance(geometry, list):
        # Batch mode
        geometries = [{"id": g["id"], "geometry": g["value"]} for g in geometry]
        result = service.query_statistics_batch(
            geometries=geometries,
            filters=filters,
            variables=variables,
        )
        # Remove registrant_ids from per-geometry results
        for item in result.get("results", []):
            item.pop("registrant_ids", None)
        return result

    # Single geometry mode
    result = service.query_statistics(
        geometry=geometry,
        filters=filters,
        variables=variables,
    )
    result.pop("registrant_ids", None)
    return result


def _run_proximity_statistics(service, inputs):
    """Run proximity-statistics process and return results."""
    reference_points = inputs["reference_points"]
    result = service.query_proximity(
        reference_points=reference_points,
        radius_km=inputs["radius_km"],
        relation=inputs.get("relation", "within"),
        filters=inputs.get("filters"),
        variables=inputs.get("variables"),
    )
    result.pop("registrant_ids", None)
    return result
