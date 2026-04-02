# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OGC API - Processes job management endpoints.

Endpoints:
    GET    /gis/ogc/jobs                List jobs (filtered by client)
    GET    /gis/ogc/jobs/{jobId}        Job status
    GET    /gis/ogc/jobs/{jobId}/results Job results
    DELETE /gis/ogc/jobs/{jobId}        Dismiss or delete a job
"""

import logging
from typing import Annotated

from odoo.api import Environment
from odoo.exceptions import UserError

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from ..schemas.processes import (
    BatchStatisticsResult,
    JobList,
    ProximityResult,
    SingleStatisticsResult,
    StatusInfo,
)
from ._helpers import RETRY_AFTER_SECONDS, build_status_info, build_status_response, check_gis_scope, get_base_url

_logger = logging.getLogger(__name__)

jobs_router = APIRouter(tags=["GIS - OGC API Processes"], prefix="/gis/ogc")


def _get_job_or_404(env, job_id, api_client):
    """Look up a job record scoped to the authenticated client."""
    # nosemgrep: odoo-sudo-without-context
    job = (
        env["spp.gis.process.job"]
        .sudo()
        .search(
            [
                ("job_id", "=", job_id),
                ("client_id", "=", api_client.id),
            ],
            limit=1,
        )
    )
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    return job


@jobs_router.get(
    "/jobs",
    response_model=JobList,
    summary="List jobs",
    description="List process jobs for the authenticated client.",
)
async def list_jobs(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    status_filter: Annotated[
        str | None,
        Query(alias="status", description="Filter by job status"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=1000, description="Maximum jobs to return")] = 100,
):
    """List jobs scoped to the authenticated client."""
    check_gis_scope(api_client)

    domain = [("client_id", "=", api_client.id)]
    if status_filter:
        valid_statuses = {"accepted", "running", "successful", "failed", "dismissed"}
        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(sorted(valid_statuses))}",
            )
        domain.append(("status", "=", status_filter))

    # nosemgrep: odoo-sudo-without-context
    jobs = env["spp.gis.process.job"].sudo().search(domain, limit=limit, order="create_date desc")

    base_url = get_base_url(request)
    return JobList(jobs=[build_status_info(j, base_url) for j in jobs])


@jobs_router.get(
    "/jobs/{job_id}",
    response_model=StatusInfo,
    response_model_exclude_none=True,
    summary="Job status",
    description="Get the status of a process job.",
)
async def get_job_status(
    job_id: Annotated[str, Path(description="Job identifier")],
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Get job status, scoped to authenticated client."""
    check_gis_scope(api_client)

    job = _get_job_or_404(env, job_id, api_client)
    base_url = get_base_url(request)
    status_info = build_status_info(job, base_url)

    # Add Retry-After header for in-progress jobs to guide client polling
    if job.status in ("accepted", "running"):
        return build_status_response(status_info, extra_headers={"Retry-After": RETRY_AFTER_SECONDS})

    return status_info


@jobs_router.get(
    "/jobs/{job_id}/results",
    summary="Job results",
    description="Get the results of a completed process job.",
    responses={
        200: {
            "description": "Process results (schema varies by process type)",
            "content": {
                "application/json": {
                    "schema": {
                        "oneOf": [
                            SingleStatisticsResult.model_json_schema(),
                            BatchStatisticsResult.model_json_schema(),
                            ProximityResult.model_json_schema(),
                        ],
                    },
                },
            },
        },
    },
)
async def get_job_results(
    job_id: Annotated[str, Path(description="Job identifier")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Get results from a completed job.

    Only available when job status is 'successful'.
    """
    check_gis_scope(api_client)

    job = _get_job_or_404(env, job_id, api_client)

    if job.status != "successful":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Results not available. Job status is '{job.status}'",
        )

    return job.results


@jobs_router.delete(
    "/jobs/{job_id}",
    status_code=200,
    summary="Dismiss or delete a job",
    description="Dismiss a queued job or delete a completed job.",
)
async def dismiss_job(
    job_id: Annotated[str, Path(description="Job identifier")],
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Dismiss or delete a job.

    For accepted jobs: sets status to dismissed.
    For running jobs: returns 409 Conflict.
    For terminal jobs: deletes the record.
    """
    check_gis_scope(api_client)

    job = _get_job_or_404(env, job_id, api_client)

    try:
        was_accepted = job.status == "accepted"
        job.dismiss()

        if was_accepted:
            # Job was dismissed, return updated status
            base_url = get_base_url(request)
            return build_status_info(job, base_url)

        # Job was deleted (terminal status)
        return {"message": "Job deleted"}

    except UserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot dismiss a running job",
        ) from None
