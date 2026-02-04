# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Entitlement resource endpoints"""

import logging
from typing import Annotated
from urllib.parse import unquote

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client
from odoo.addons.spp_api_v2.schemas.search_result import (
    SearchResult,
    create_search_result,
)

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from ..schemas.entitlement import Entitlement
from ..services.entitlement_service import EntitlementService

_logger = logging.getLogger(__name__)

entitlement_router = APIRouter(tags=["Entitlement"], prefix="/Entitlement")


@entitlement_router.get(
    "/{identifier}",
    response_model=Entitlement,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_entitlement(
    identifier: Annotated[str, Path(description="Entitlement code (UUID)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read Entitlement by identifier (code).

    The identifier is the entitlement's unique code (UUID-based).
    """
    # Check client has read scope
    if not api_client.has_scope("entitlement", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read entitlements",
        )

    # URL-decode the identifier
    decoded_identifier = unquote(identifier)

    service = EntitlementService(env)
    entitlement = service.find_by_identifier(decoded_identifier)

    if not entitlement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entitlement not found",
        )

    # Convert to API schema
    data = service.to_api_schema(entitlement)

    # Add ETag header
    if "meta" in data and "versionId" in data["meta"]:
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@entitlement_router.get(
    "",
    response_model=SearchResult,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_entitlements(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    beneficiary: Annotated[str | None, Query(description="Beneficiary identifier (system|value)")] = None,
    program: Annotated[str | None, Query()] = None,
    cycle: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    entitlement_type: Annotated[str | None, Query(alias="entitlementType", description="cash or inkind")] = None,
    valid_from: Annotated[str | None, Query(alias="validFrom")] = None,
    valid_until: Annotated[str | None, Query(alias="validUntil")] = None,
    last_updated: Annotated[str | None, Query(alias="_lastUpdated")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for entitlements.

    Supports search parameters:
    - beneficiary: system|value identifier
    - program: program name
    - cycle: cycle name
    - state: entitlement state
    - entitlementType: cash or inkind
    - validFrom: date
    - validUntil: date
    - _lastUpdated: date with prefix
    - _count: page size (max 100)
    - _offset: skip records
    """
    # Check client has search scope
    if not api_client.has_scope("entitlement", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to search entitlements",
        )

    # Build search parameters
    params = {
        "beneficiary": beneficiary,
        "program": program,
        "cycle": cycle,
        "state": state,
        "type": entitlement_type,
        "validFrom": valid_from,
        "validUntil": valid_until,
        "_lastUpdated": last_updated,
        "_count": count,
        "_offset": offset,
    }

    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    # Execute search
    service = EntitlementService(env)
    records, total = service.search(params)

    # Convert to API schema
    entitlements_data = []
    for entitlement in records:
        data = service.to_api_schema(entitlement)
        entitlements_data.append(data)

    # Build pagination links
    base_url = "/api/v2/spp/Entitlement"
    # Filter out pagination params and map internal param names to query param names
    base_params = {}
    for k, v in params.items():
        if k not in ("_count", "_offset"):
            # Map internal "type" to query param "entitlementType"
            param_name = "entitlementType" if k == "type" else k
            base_params[param_name] = v

    def build_url(offset_val: int) -> str:
        """Build pagination URL."""
        url_params = "&".join(f"{k}={v}" for k, v in base_params.items())
        if url_params:
            return f"{base_url}?{url_params}&_count={count}&_offset={offset_val}"
        return f"{base_url}?_count={count}&_offset={offset_val}"

    # Determine if there are more results
    has_more = offset + count < total

    # Build pagination URLs
    self_url = build_url(offset)
    next_url = build_url(offset + count) if has_more else None
    prev_url = build_url(max(0, offset - count)) if offset > 0 else None

    return create_search_result(
        data=entitlements_data,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )
