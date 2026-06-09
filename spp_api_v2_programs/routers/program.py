# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Program resource endpoints"""

import logging
from typing import Annotated

from odoo.api import Environment
from odoo.osv import expression

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)

from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client
from ..schemas.program import Program
from odoo.addons.spp_api_v2.schemas.search_result import SearchResult, create_search_result
from ..services.program_service import ProgramService

_logger = logging.getLogger(__name__)

program_router = APIRouter(tags=["Program"], prefix="/Program")


@program_router.get("/{identifier}", response_model=Program)
async def read_program(
    identifier: Annotated[str, Path(description="Format: {system}|{value} (URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read Program by external identifier.

    Programs are read-only via API (created in admin UI).
    """
    # Check scope
    if not api_client.has_scope("program", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'program:read'. Request access from your administrator.",
        )

    # Parse identifier (format: system|value)
    if "|" not in identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format. Expected: {system}|{value}",
        )

    system, value = identifier.split("|", 1)

    # Find program by namespace_uri + value
    service = ProgramService(env)
    program = service.find_by_identifier(system, value)

    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )

    # Convert to API schema
    data = service.to_api_schema(program)

    # Add ETag header (version for optimistic locking)
    if "meta" in data and "versionId" in data["meta"]:
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@program_router.get("", response_model=SearchResult)
async def search_programs(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    identifier: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    type_: Annotated[str | None, Query(alias="type")] = None,
    target_type: Annotated[str | None, Query(alias="targetType")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    last_id: Annotated[
        int | None,
        Query(alias="_lastId", description="ID of last record from previous page"),
    ] = None,
):
    """
    Search for programs.

    Search parameters:
    - identifier: system|value
    - name: string (contains)
    - status: active/ended
    - type: program type code
    - targetType: individual/group
    - _count: page size
    - _lastId: cursor for pagination (ID of last record from previous page)
    """
    # Check scope
    if not api_client.has_scope("program", "search") and not api_client.has_scope("program", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'program:search'. Request access from your administrator.",
        )

    # Build search domain
    domain = []

    # Name search
    if name:
        domain.append(("name", "ilike", name))

    # Status search
    if status:
        if status == "active":
            domain.append(("state", "=", "active"))
        elif status == "ended":
            domain.append(("state", "=", "ended"))

    # Target type search
    if target_type:
        domain.append(("target_type", "=", target_type))

    # Identifier search - not easily supported without external ID system
    # We'll skip this for now as programs may not have standardized external IDs

    # Apply cursor-based pagination
    if last_id is not None:
        domain = expression.AND([domain, [("id", ">", last_id)]])

    # Execute search (include inactive programs for ended status)
    program_model = env["spp.program"].sudo().with_context(active_test=False)  # nosemgrep: odoo-sudo-without-context
    programs = program_model.search(domain, limit=count, order="id")
    total = program_model.search_count(domain)

    # Convert to API schema
    service = ProgramService(env)

    resources = []
    for program in programs:
        try:
            data = service.to_api_schema(program)
            resources.append(data)
        except Exception as e:
            _logger.warning("Error converting program id=%s to API schema: %s", program.id, e)
            continue

    # Build pagination links
    # Build query parameters
    params = {}
    if name:
        params["name"] = name
    if status:
        params["status"] = status
    if target_type:
        params["targetType"] = target_type
    params["_count"] = str(count)

    # Build self link with current cursor
    if last_id:
        params["_lastId"] = str(last_id)
    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    self_url = f"{request.url.path}?{query_string}"

    # Next link - use last record ID as cursor
    next_url = None
    if len(resources) >= count and resources:
        last_record_id = programs[-1].id
        next_params = params.copy()
        next_params["_lastId"] = str(last_record_id)
        next_query_string = "&".join(f"{k}={v}" for k, v in next_params.items())
        next_url = f"{request.url.path}?{next_query_string}"

    # For cursor-based pagination, we don't have a previous link
    # (would require reverse cursor)
    prev_url = None

    # Calculate offset for SearchResult metadata
    # With cursor-based pagination, we approximate offset based on last_id
    offset = last_id if last_id else 0

    return create_search_result(
        data=resources,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )
