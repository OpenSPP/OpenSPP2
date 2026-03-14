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

from ..schemas.processes import JobList, StatusInfo

_logger = logging.getLogger(__name__)

jobs_router = APIRouter(tags=["GIS - OGC API Processes"], prefix="/gis/ogc")


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
    """Build a StatusInfo from a spp.gis.process.job record."""
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
        message=job.message or None,
        created=job.create_date.isoformat() if job.create_date else None,
        started=job.started_at.isoformat() if job.started_at else None,
        finished=job.finished_at.isoformat() if job.finished_at else None,
        updated=job.write_date.isoformat() if job.write_date else None,
        progress=job.progress,
        links=links,
    )


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
    _check_gis_scope(api_client)

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

    base_url = _get_base_url(request)
    return JobList(jobs=[_build_status_info(j, base_url) for j in jobs])


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
    _check_gis_scope(api_client)

    job = _get_job_or_404(env, job_id, api_client)
    base_url = _get_base_url(request)
    return _build_status_info(job, base_url)


@jobs_router.get(
    "/jobs/{job_id}/results",
    summary="Job results",
    description="Get the results of a completed process job.",
)
async def get_job_results(
    job_id: Annotated[str, Path(description="Job identifier")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Get results from a completed job.

    Only available when job status is 'successful'.
    """
    _check_gis_scope(api_client)

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
    _check_gis_scope(api_client)

    job = _get_job_or_404(env, job_id, api_client)

    try:
        was_accepted = job.status == "accepted"
        job.dismiss()

        if was_accepted:
            # Job was dismissed, return updated status
            base_url = _get_base_url(request)
            return _build_status_info(job, base_url)

        # Job was deleted (terminal status)
        return {"message": "Job deleted"}

    except UserError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot dismiss a running job",
        ) from None
