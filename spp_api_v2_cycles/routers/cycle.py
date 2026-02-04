# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Cycle resource endpoints"""

import logging
from typing import Annotated
from urllib.parse import unquote, urlencode

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client
from odoo.addons.spp_api_v2.schemas.search_result import (
    SearchResult,
    create_search_result,
)

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from ..schemas.cycle import Cycle
from ..services.cycle_service import CycleService

_logger = logging.getLogger(__name__)

cycle_router = APIRouter(tags=["Cycle"], prefix="/Cycle")


@cycle_router.get(
    "/{identifier}",
    response_model=Cycle,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_cycle(
    identifier: Annotated[str, Path(description="Cycle identifier (name, URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read Cycle by identifier.

    The identifier is the cycle's name.
    """
    # Check client has read scope
    if not api_client.has_scope("cycle", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read cycles",
        )

    # URL-decode the identifier
    decoded_identifier = unquote(identifier)

    service = CycleService(env)
    cycle = service.find_by_identifier(decoded_identifier)

    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cycle not found",
        )

    # Convert to API schema
    data = service.to_api_schema(cycle)

    # Add ETag header
    if "meta" in data and "versionId" in data["meta"]:
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@cycle_router.get(
    "",
    response_model=SearchResult,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_cycles(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    program: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    start_date: Annotated[str | None, Query(alias="startDate")] = None,
    end_date: Annotated[str | None, Query(alias="endDate")] = None,
    last_updated: Annotated[str | None, Query(alias="_lastUpdated")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for cycles.

    Supports search parameters:
    - program: program name
    - state: cycle state
    - startDate: filter by start date
    - endDate: filter by end date
    - _lastUpdated: date with prefix
    - _count: page size (max 100)
    - _offset: skip records

    Returns SearchResult with paginated results.
    """
    # Check client has search scope
    if not api_client.has_scope("cycle", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to search cycles",
        )

    # Build search parameters
    params = {
        "program": program,
        "state": state,
        "startDate": start_date,
        "endDate": end_date,
        "_lastUpdated": last_updated,
        "_count": count,
        "_offset": offset,
    }

    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    # Execute search
    service = CycleService(env)
    records, total = service.search(params)

    # Convert to API schema
    cycles_data = []
    for cycle in records:
        data = service.to_api_schema(cycle)
        cycles_data.append(data)

    # Build pagination links with proper URL encoding
    base_url = "/api/v2/spp/Cycle"
    # Filter out pagination params and properly encode remaining params
    base_params = {k: v for k, v in params.items() if k not in ("_count", "_offset")}

    def build_url(offset_val: int) -> str:
        """Build properly URL-encoded pagination URL."""
        url_params = {**base_params, "_count": count, "_offset": offset_val}
        return f"{base_url}?{urlencode(url_params)}"

    # Determine if there are more results
    has_more = offset + count < total

    # Build pagination URLs
    self_url = build_url(offset)
    next_url = build_url(offset + count) if has_more else None
    prev_url = build_url(max(0, offset - count)) if offset > 0 else None

    return create_search_result(
        data=cycles_data,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )
