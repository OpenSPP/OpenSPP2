# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared helpers for GIS OGC API routers."""

from fastapi import HTTPException, Request, Response, status

from ..schemas.processes import StatusInfo

# Suggested polling interval for async job status (seconds)
RETRY_AFTER_SECONDS = "5"


def check_gis_scope(api_client):
    """Verify client has gis:read or statistics:read scope."""
    if not (api_client.has_scope("gis", "read") or api_client.has_scope("statistics", "read")):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have gis:read or statistics:read scope",
        )


def get_base_url(request: Request) -> str:
    """Extract base URL for self-referencing links."""
    url = str(request.base_url).rstrip("/")
    return f"{url}/api/v2/spp"


def build_status_info(job, base_url=""):
    """Build a StatusInfo from a spp.gis.process.job record.

    Handles Odoo's False-for-empty convention on Text fields by
    coercing falsy values to None for Pydantic compatibility.
    """
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


def build_status_response(status_info, status_code=200, extra_headers=None):
    """Build a JSON Response from a StatusInfo, with optional extra headers.

    Used when headers like Retry-After need to be set alongside the JSON body.
    """
    headers = {}
    if extra_headers:
        headers.update(extra_headers)
    return Response(
        content=status_info.model_dump_json(by_alias=True, exclude_none=True),
        status_code=status_code,
        media_type="application/json",
        headers=headers or None,
    )
