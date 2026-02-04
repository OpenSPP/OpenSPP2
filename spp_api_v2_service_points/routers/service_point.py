# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service Point resource endpoints"""

import logging
from typing import Annotated
from urllib.parse import unquote

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client
from odoo.addons.spp_api_v2.schemas.bundle import (
    Bundle,
    BundleEntry,
    BundleLink,
    BundleSearch,
)

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from ..schemas.service_point import ServicePoint
from ..services.service_point_service import ServicePointService

_logger = logging.getLogger(__name__)

service_point_router = APIRouter(tags=["ServicePoint"], prefix="/ServicePoint")


@service_point_router.get(
    "/{identifier}",
    response_model=ServicePoint,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_service_point(
    identifier: Annotated[str, Path(description="Service point identifier (URL-encoded name)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read Service Point by identifier.

    The identifier is the service point name (URL-encoded).
    """
    # Check client has read scope
    if not api_client.has_scope("service_point", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read service points",
        )

    # URL-decode the identifier
    decoded_identifier = unquote(identifier)

    service = ServicePointService(env)
    sp = service.find_by_identifier(decoded_identifier)

    if not sp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service point not found",
        )

    # Convert to API schema
    data = service.to_api_schema(sp)

    # Add ETag header (version for optimistic locking)
    if "meta" in data and "versionId" in data["meta"]:
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@service_point_router.get(
    "",
    response_model=Bundle,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_service_points(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    name: Annotated[str | None, Query()] = None,
    area: Annotated[str | None, Query()] = None,
    country: Annotated[str | None, Query()] = None,
    active: Annotated[bool | None, Query(alias="contractActive")] = None,
    last_updated: Annotated[str | None, Query(alias="_lastUpdated")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for service points.

    Supports search parameters:
    - name: string (contains)
    - area: area name
    - country: country code
    - contractActive: boolean
    - _lastUpdated: date with prefix
    - _count: page size (max 100)
    - _offset: skip records
    """
    # Check client has search scope
    if not api_client.has_scope("service_point", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to search service points",
        )

    # Build search parameters
    params = {
        "name": name,
        "area": area,
        "country": country,
        "contractActive": active,
        "_lastUpdated": last_updated,
        "_count": count,
        "_offset": offset,
    }

    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    # Execute search
    service = ServicePointService(env)
    records, total = service.search(params)

    # Convert to API schema
    entries = []
    for sp in records:
        data = service.to_api_schema(sp)
        entries.append(
            BundleEntry(
                resource=data,
                search=BundleSearch(
                    mode="match",
                    score=1.0,
                ),
            )
        )

    # Build pagination links
    base_url = "/api/v2/spp/ServicePoint"
    query_params = "&".join(f"{k}={v}" for k, v in params.items() if k not in ("_count", "_offset"))

    links = [
        BundleLink(
            relation="self",
            url=f"{base_url}?{query_params}&_count={count}&_offset={offset}",
        )
    ]

    # Next link
    if offset + count < total:
        next_offset = offset + count
        links.append(
            BundleLink(
                relation="next",
                url=f"{base_url}?{query_params}&_count={count}&_offset={next_offset}",
            )
        )

    # Previous link
    if offset > 0:
        prev_offset = max(0, offset - count)
        links.append(
            BundleLink(
                relation="previous",
                url=f"{base_url}?{query_params}&_count={count}&_offset={prev_offset}",
            )
        )

    return Bundle(
        resourceType="Bundle",
        type="searchset",
        total=total,
        link=links,
        entry=entries,
    )
