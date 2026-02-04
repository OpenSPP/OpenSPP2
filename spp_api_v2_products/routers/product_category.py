# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Product Category resource endpoints"""

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

from ..schemas.product_category import ProductCategory
from ..services.product_category_service import ProductCategoryService

_logger = logging.getLogger(__name__)

product_category_router = APIRouter(tags=["ProductCategory"], prefix="/ProductCategory")


@product_category_router.get(
    "/{identifier}",
    response_model=ProductCategory,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_product_category(
    identifier: Annotated[str, Path(description="Category identifier (name, URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read Product Category by identifier.
    """
    if not api_client.has_scope("product", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read product categories",
        )

    decoded_identifier = unquote(identifier)

    service = ProductCategoryService(env)
    category = service.find_by_identifier(decoded_identifier)

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product category not found",
        )

    data = service.to_api_schema(category)

    if "meta" in data and "versionId" in data["meta"]:
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@product_category_router.get(
    "",
    response_model=Bundle,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_product_categories(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    name: Annotated[str | None, Query()] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for product categories.
    """
    if not api_client.has_scope("product", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to search product categories",
        )

    params = {
        "name": name,
        "_count": count,
        "_offset": offset,
    }
    params = {k: v for k, v in params.items() if v is not None}

    service = ProductCategoryService(env)
    records, total = service.search(params)

    entries = []
    for category in records:
        data = service.to_api_schema(category)
        entries.append(
            BundleEntry(
                resource=data,
                search=BundleSearch(mode="match", score=1.0),
            )
        )

    base_url = "/api/v2/spp/ProductCategory"
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
