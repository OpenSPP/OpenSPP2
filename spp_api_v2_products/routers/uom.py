# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unit of Measure resource endpoints"""

import logging
from typing import Annotated
from urllib.parse import unquote

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client
from odoo.addons.spp_api_v2.schemas.bundle import Bundle, BundleEntry, BundleLink, BundleSearch

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from ..schemas.uom import UnitOfMeasure
from ..services.uom_service import UomService

_logger = logging.getLogger(__name__)

uom_router = APIRouter(tags=["UnitOfMeasure"], prefix="/UnitOfMeasure")


@uom_router.get(
    "/{identifier}",
    response_model=UnitOfMeasure,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_uom(
    identifier: Annotated[str, Path(description="UoM identifier (name, URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read Unit of Measure by identifier.
    """
    if not api_client.has_scope("product", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read units of measure",
        )

    decoded_identifier = unquote(identifier)

    service = UomService(env)
    uom = service.find_by_identifier(decoded_identifier)

    if not uom:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unit of measure not found",
        )

    data = service.to_api_schema(uom)

    if "meta" in data and "versionId" in data["meta"]:
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@uom_router.get(
    "",
    response_model=Bundle,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_uoms(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    name: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for units of measure.
    """
    if not api_client.has_scope("product", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to search units of measure",
        )

    params = {
        "name": name,
        "category": category,
        "_count": count,
        "_offset": offset,
    }
    params = {k: v for k, v in params.items() if v is not None}

    service = UomService(env)
    records, total = service.search(params)

    entries = []
    for uom in records:
        data = service.to_api_schema(uom)
        entries.append(
            BundleEntry(
                resource=data,
                search=BundleSearch(mode="match", score=1.0),
            )
        )

    base_url = "/api/v2/spp/UnitOfMeasure"
    query_params = "&".join(f"{k}={v}" for k, v in params.items() if k not in ("_count", "_offset"))

    links = [
        BundleLink(
            relation="self",
            url=f"{base_url}?{query_params}&_count={count}&_offset={offset}",
        )
    ]

    if offset + count < total:
        links.append(
            BundleLink(
                relation="next",
                url=f"{base_url}?{query_params}&_count={count}&_offset={offset + count}",
            )
        )

    if offset > 0:
        links.append(
            BundleLink(
                relation="previous",
                url=f"{base_url}?{query_params}&_count={count}&_offset={max(0, offset - count)}",
            )
        )

    return Bundle(
        resourceType="Bundle",
        type="searchset",
        total=total,
        link=links,
        entry=entries,
    )
