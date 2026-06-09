# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""ProgramMembership resource endpoints"""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)

from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client
from ..schemas.program_membership import ProgramMembership
from odoo.addons.spp_api_v2.schemas.search_result import SearchResult, create_search_result
from odoo.addons.spp_api_v2.services.consent_service import ConsentService
from ..services.program_membership_service import ProgramMembershipService
from odoo.addons.spp_api_v2.utils.pagination import fetch_with_consent

_logger = logging.getLogger(__name__)

program_membership_router = APIRouter(tags=["ProgramMembership"], prefix="/ProgramMembership")


@program_membership_router.get("/{identifier}", response_model=ProgramMembership)
async def read_program_membership(
    identifier: Annotated[str, Path(description="Format: {system}|{value} (URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read ProgramMembership by external identifier.

    Applies consent filtering for beneficiary data.
    """
    # Check scope
    if not api_client.has_scope("program_membership", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Missing required scope 'program_membership:read'. Request access from your administrator."),
        )

    # Parse identifier (format: system|value)
    if "|" not in identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format. Expected: {system}|{value}",
        )

    system, value = identifier.split("|", 1)

    # Find program membership by namespace_uri + value
    service = ProgramMembershipService(env)
    membership = service.find_by_identifier(system, value)

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ProgramMembership not found",
        )

    # Convert to API schema
    data = service.to_api_schema(membership)

    # Apply consent filtering for the beneficiary
    consent_service = ConsentService(env)
    filtered_data = consent_service.filter_response(
        membership.partner_id.id,
        api_client,
        "program_membership",
        data,
    )

    # Check if consent was denied (same pattern as individual endpoint)
    consent_info = filtered_data.get("_consent", {})
    if consent_info.get("status") in ("no_consent", "scope_mismatch"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Add ETag header (version for optimistic locking)
    if "meta" in filtered_data and "versionId" in filtered_data["meta"]:
        response.headers["ETag"] = f'"{filtered_data["meta"]["versionId"]}"'

    # Add consent status headers
    if "_consent" in filtered_data:
        consent_info = filtered_data.pop("_consent")
        # Map "given" to "active" for header (API convention)
        consent_status = consent_info.get("status", "unknown")
        header_status = "active" if consent_status == "given" else consent_status
        response.headers["X-Consent-Status"] = header_status
        if "scope" in consent_info:
            response.headers["X-Consent-Scope"] = consent_info["scope"]

    return filtered_data


@program_membership_router.get("", response_model=SearchResult)
async def search_program_memberships(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    beneficiary: Annotated[str | None, Query()] = None,
    program: Annotated[str | None, Query()] = None,
    status_: Annotated[str | None, Query(alias="status")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for program memberships.

    Search parameters:
    - beneficiary: Reference to Individual or Group (format: Individual/{system}|{value} or Group/{system}|{value})
    - program: Reference to Program (format: Program/{system}|{value})
    - status: enrollment status (draft|enrolled|paused|exited|not_eligible|duplicated)
    - _count: page size
    - _offset: skip records
    """
    # Check scope
    if not api_client.has_scope("program_membership", "search") and not api_client.has_scope(
        "program_membership", "read"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=("Missing required scope 'program_membership:search'. Request access from your administrator."),
        )

    # Build search parameters
    params = {}
    if beneficiary:
        params["beneficiary"] = beneficiary
    if program:
        params["program"] = program
    if status_:
        params["status"] = status_

    # Execute search with consent-aware pagination
    service = ProgramMembershipService(env)
    consent_service = ConsentService(env)

    def search_function(offset, limit):
        search_params = {**params, "_count": limit, "_offset": offset}
        try:
            return service.search(search_params)
        except Exception as e:
            _logger.warning("Error in program membership search: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid search parameters: {e}",
            ) from e

    def consent_filter_function(membership):
        try:
            data = service.to_api_schema(membership)
            filtered_data = consent_service.filter_response(
                membership.partner_id.id, api_client, "program_membership", data
            )
            consent_info = filtered_data.pop("_consent", None)
            if consent_info and consent_info.get("status") in (
                "no_consent",
                "scope_mismatch",
            ):
                return None
            return filtered_data
        except Exception as e:
            _logger.warning(
                "Error converting program membership id=%s to API schema: %s",
                membership.id,
                str(e),
            )
            return None

    resources, db_offset_consumed, raw_total, consent_was_applied = fetch_with_consent(
        search_function, consent_filter_function, count, offset
    )

    # Suppress total when consent filtering is active
    if consent_was_applied:
        total = len(resources)
    else:
        total = raw_total

    # Build pagination links
    url_params = {}
    if beneficiary:
        url_params["beneficiary"] = beneficiary
    if program:
        url_params["program"] = program
    if status_:
        url_params["status"] = status_
    url_params["_count"] = str(count)
    url_params["_offset"] = str(offset)

    query_string = "&".join(f"{k}={v}" for k, v in url_params.items())
    self_url = f"{request.url.path}?{query_string}"

    next_offset = db_offset_consumed if consent_was_applied else offset + count
    has_more = len(resources) >= count

    next_url = None
    if has_more:
        next_params = url_params.copy()
        next_params["_offset"] = str(next_offset)
        next_query_string = "&".join(f"{k}={v}" for k, v in next_params.items())
        next_url = f"{request.url.path}?{next_query_string}"

    prev_url = None
    if offset > 0:
        prev_offset = max(0, offset - count)
        prev_params = url_params.copy()
        prev_params["_offset"] = str(prev_offset)
        prev_query_string = "&".join(f"{k}={v}" for k, v in prev_params.items())
        prev_url = f"{request.url.path}?{prev_query_string}"

    return create_search_result(
        data=resources,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )


@program_membership_router.post("", response_model=ProgramMembership, status_code=status.HTTP_201_CREATED)
async def create_program_membership(
    program_membership: ProgramMembership,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Create new ProgramMembership (enrollment).

    CRITICAL:
    - Sets source_system to urn:openspp:api-client:{client_id}
    - Finds program and beneficiary by namespace_uri
    - Checks client scopes for create permission
    """
    # Check client has create scope
    if not api_client.has_scope("program_membership", "create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'program_membership:create'. Request access from your administrator.",
        )

    # Create program membership with source tracking
    service = ProgramMembershipService(env)
    source_system = f"urn:openspp:api-client:{api_client.client_id}"

    try:
        membership = service.create(program_membership, source=source_system)
    except Exception as e:
        _logger.exception("Error creating program membership")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to create program membership: {str(e)}",
        ) from e

    # Return created resource
    data = service.to_api_schema(membership)

    # Set Location header
    if data.get("identifier"):
        primary_id = data["identifier"][0]
        location = f"/api/v2/spp/ProgramMembership/{primary_id['system']}|{primary_id['value']}"
        response.headers["Location"] = location

    return data


@program_membership_router.put("/{identifier}", response_model=ProgramMembership)
async def update_program_membership(
    identifier: Annotated[str, Path()],
    program_membership: ProgramMembership,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    if_match: Annotated[str | None, Header()] = None,
):
    """
    Update ProgramMembership (full replacement).

    CRITICAL:
    - Requires If-Match header with version ID for optimistic locking
    - Updates with source tracking
    - Checks client scopes for update permission
    """
    # Check client has update scope
    if not api_client.has_scope("program_membership", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'program_membership:update'. Request access from your administrator.",
        )

    # Parse identifier
    if "|" not in identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format",
        )

    system, value = identifier.split("|", 1)

    # Find program membership
    service = ProgramMembershipService(env)
    membership = service.find_by_identifier(system, value)

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ProgramMembership not found",
        )

    # Check version for optimistic locking
    if if_match:
        current_version = str(membership.write_date.timestamp() if membership.write_date else 1)
        if_match_clean = if_match.strip('"')
        if if_match_clean != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Version conflict. Resource was modified by another request.",
            )

    # Update program membership
    source_system = f"urn:openspp:api-client:{api_client.client_id}"

    try:
        membership = service.update(membership, program_membership, source=source_system)
    except Exception as e:
        _logger.exception("Error updating program membership")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to update program membership: {str(e)}",
        ) from e

    # Return updated resource
    return service.to_api_schema(membership)
