# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Product resource endpoints"""

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

from ..schemas.product import Product
from ..services.product_service import ProductService

_logger = logging.getLogger(__name__)

product_router = APIRouter(tags=["Product"], prefix="/Product")


@product_router.get(
    "/{identifier}",
    response_model=Product,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_product(
    identifier: Annotated[str, Path(description="Product identifier (default_code or name, URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read Product by identifier.

    The identifier is the product's default_code (SKU) or name.
    """
    # Check client has read scope
    if not api_client.has_scope("product", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read products",
        )

    # URL-decode the identifier
    decoded_identifier = unquote(identifier)

    service = ProductService(env)
    product = service.find_by_identifier(decoded_identifier)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Convert to API schema
    data = service.to_api_schema(product)

    # Add ETag header
    if "meta" in data and "versionId" in data["meta"]:
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@product_router.get(
    "",
    response_model=Bundle,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_products(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    name: Annotated[str | None, Query()] = None,
    code: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
    last_updated: Annotated[str | None, Query(alias="_lastUpdated")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for products.

    Supports search parameters:
    - name: string (contains)
    - code: default_code/SKU
    - category: category name
    - _lastUpdated: date with prefix
    - _count: page size (max 100)
    - _offset: skip records
    """
    # Check client has search scope
    if not api_client.has_scope("product", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to search products",
        )

    # Build search parameters
    params = {
        "name": name,
        "code": code,
        "category": category,
        "_lastUpdated": last_updated,
        "_count": count,
        "_offset": offset,
    }

    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    # Execute search
    service = ProductService(env)
    records, total = service.search(params)

    # Convert to API schema
    entries = []
    for product in records:
        data = service.to_api_schema(product)
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
    base_url = "/api/v2/spp/Product"
    query_params = "&".join(f"{k}={v}" for k, v in params.items() if k not in ("_count", "_offset"))

    links = [
        BundleLink(
            relation="self",
            url=f"{base_url}?{query_params}&_count={count}&_offset={offset}",
        )
    ]

    if offset + count < total:
        next_offset = offset + count
        links.append(
            BundleLink(
                relation="next",
                url=f"{base_url}?{query_params}&_count={count}&_offset={next_offset}",
            )
        )

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
