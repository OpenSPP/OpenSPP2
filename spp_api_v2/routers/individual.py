# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Individual resource endpoints"""

import asyncio
import logging
import random
from typing import Annotated
from urllib.parse import urlencode

from odoo.api import Environment
from odoo.exceptions import ValidationError

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

from ..middleware.auth import get_authenticated_client
from ..schemas.individual import Individual
from ..schemas.membership import GroupMembershipBundle
from ..schemas.patch import IndividualPatch
from ..schemas.search_result import SearchResult, create_search_result
from ..services.api_audit_service import ApiAuditService
from ..services.consent_service import ConsentService
from ..services.field_filter import filter_fields, filter_list
from ..services.individual_service import IndividualService
from ..services.search_service import SearchService
from ..utils.pagination import fetch_with_consent
from .dependencies import check_individual_access, parse_identifier

_logger = logging.getLogger(__name__)

individual_router = APIRouter(tags=["Individual"], prefix="/Individual")


@individual_router.get(
    "/{identifier}",
    response_model=Individual,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_individual(
    identifier: Annotated[str, Path(description="Format: {system}|{value} (URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
    elements: Annotated[str | None, Query(alias="_elements")] = None,
    extensions: Annotated[str | None, Query(alias="_extensions")] = None,
):
    """
    Read Individual by external identifier.

    CRITICAL:
    - Uses namespace_uri to lookup, NOT database ID
    - Applies consent filtering
    - Returns filtered fields based on consent and client scope
    """
    # Check scope
    if not api_client.has_scope("individual", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'individual:read'. Request access from your administrator.",
        )

    # Parse identifier (format: system|value)
    system, value = parse_identifier(identifier)

    # Find individual by namespace_uri + value
    service = IndividualService(env)
    partner = service.find_by_identifier(system, value)

    # SECURITY: Prevent user enumeration
    # For clients requiring consent, return same error for "not found" and "no consent"
    # to prevent attackers from determining which individuals exist in the system.
    if not partner:
        if api_client.is_require_consent:
            # SECURITY: Add timing jitter to prevent timing-based enumeration
            # Simulate the time it would take to process a found record
            await asyncio.sleep(0.05 + random.uniform(0, 0.02))  # 50-70ms delay
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Individual not found",
        )

    # Convert to API schema
    extension_list = extensions.split(",") if extensions else None
    data = service.to_api_schema(partner, extensions=extension_list)

    # Apply consent filtering
    consent_service = ConsentService(env)
    filtered_data = consent_service.filter_response(
        partner.id,
        api_client,
        "individual",
        data,
    )

    # SECURITY: Check if consent was denied and return same error as "not found"
    if api_client.is_require_consent:
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
        # Add consent scope header to show what fields/resources are accessible
        if "scope" in consent_info:
            response.headers["X-Consent-Scope"] = consent_info["scope"]

    # Apply _elements filter for sparse fieldsets
    if elements:
        filtered_data = filter_fields(filtered_data, elements)

    return filtered_data


@individual_router.get(
    "",
    response_model=SearchResult,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_individuals(
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    identifier: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    birthdate: Annotated[str | None, Query()] = None,
    gender: Annotated[str | None, Query()] = None,
    address: Annotated[str | None, Query()] = None,
    group: Annotated[str | None, Query()] = None,
    membership_role: Annotated[str | None, Query(alias="membership-role")] = None,
    last_updated: Annotated[str | None, Query(alias="_lastUpdated")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
    sort: Annotated[str | None, Query(alias="_sort")] = None,
    elements: Annotated[str | None, Query(alias="_elements")] = None,
    extensions: Annotated[str | None, Query(alias="_extensions")] = None,
):
    """
    Search for individuals.

    Supports search parameters:
    - identifier: system|value
    - name: string (contains)
    - birthdate: date with prefix (ge, le, eq)
    - gender: system|code
    - address: string search
    - group: Group identifier (system|value) or "none" for orphans
    - membership-role: Membership role code (e.g., "head", "spouse", "child")
    - _lastUpdated: date with prefix
    - _count: page size (max 100)
    - _offset: skip records
    - _sort: field name (prefix with - for descending)

    Returns SearchResult with paginated results.
    """
    # Check scope
    if not api_client.has_scope("individual", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'individual:read'. Request access from your administrator.",
        )

    # Build search parameters
    params = {
        "identifier": identifier,
        "name": name,
        "birthdate": birthdate,
        "gender": gender,
        "address": address,
        "group": group,
        "membership-role": membership_role,
        "_lastUpdated": last_updated,
        "_count": count,
        "_offset": offset,
        "_sort": sort,
    }

    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    # Execute search with consent-aware pagination
    search_service = SearchService(env)
    individual_service = IndividualService(env)
    consent_service = ConsentService(env)
    extension_list = extensions.split(",") if extensions else None

    def search_function(offset, limit):
        search_params = {**params, "_count": limit, "_offset": offset}
        return search_service.search_individuals(search_params)

    def consent_filter_function(partner):
        data = individual_service.to_api_schema(partner, extensions=extension_list)
        if data is None:
            return None
        filtered_data = consent_service.filter_response(partner.id, api_client, "individual", data)
        consent_info = filtered_data.pop("_consent", None)
        if consent_info and consent_info.get("status") in (
            "no_consent",
            "scope_mismatch",
        ):
            return None
        return filtered_data

    individuals_data, db_offset_consumed, raw_total, consent_was_applied = fetch_with_consent(
        search_function, consent_filter_function, count, offset
    )

    # Apply _elements filter for sparse fieldsets
    if elements:
        individuals_data = filter_list(individuals_data, elements)

    # When consent filtering is active, suppress the exact total to
    # avoid leaking the count of denied records. Clients detect
    # end-of-results when they receive fewer than `count` records.
    if consent_was_applied:
        total = len(individuals_data)
    else:
        total = raw_total

    # Build pagination links with proper URL encoding
    base_url = "/api/v2/spp/Individual"
    base_params = {k: v for k, v in params.items() if k not in ("_count", "_offset")}

    def build_url(offset_val: int) -> str:
        """Build properly URL-encoded pagination URL."""
        url_params = {**base_params, "_count": count, "_offset": offset_val}
        return f"{base_url}?{urlencode(url_params)}"

    # Use the consumed DB offset for next page link when consent filtering
    next_offset = db_offset_consumed if consent_was_applied else offset + count
    has_more = len(individuals_data) >= count

    self_url = build_url(offset)
    next_url = build_url(next_offset) if has_more else None
    prev_url = build_url(max(0, offset - count)) if offset > 0 else None

    return create_search_result(
        data=individuals_data,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )


@individual_router.post("", response_model=Individual, status_code=status.HTTP_201_CREATED)
async def create_individual(
    individual: Individual,
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Create new Individual.

    CRITICAL:
    - Sets source_system to urn:openspp:api-client:{client_id}
    - Finds ID types by namespace_uri
    - Finds gender by namespace_uri + code
    """
    # Check client has create scope
    if not api_client.has_scope("individual", "create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'individual:create'. Request access from your administrator.",
        )

    service = IndividualService(env)
    audit_service = ApiAuditService(
        env,
        api_client,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    source_system = f"urn:openspp:api-client:{api_client.client_id}"

    try:
        # api_authorized=True tells service to skip user group check since
        # API client scope (verified above) is the authorization for API calls
        partner = service.create(individual, source=source_system, api_authorized=True)
    except ValidationError as ve:
        _logger.warning("Validation error creating individual: %s", ve)
        # Log failed create attempt
        audit_service.log_create(
            "individual",
            individual.identifier[0].system + "|" + individual.identifier[0].value
            if individual.identifier
            else "unknown",
            None,
            status="validation_error",
            error_detail="Validation error",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        ) from ve
    except Exception as e:
        _logger.exception("Error creating individual")
        audit_service.log_create(
            "individual",
            "unknown",
            None,
            status="error",
            error_detail="Failed to create",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to create individual",
        ) from e

    # Return created resource
    data = service.to_api_schema(partner)

    # Get resource identifier for audit log
    resource_identifier = "unknown"
    if data.get("identifier"):
        primary_id = data["identifier"][0]
        resource_identifier = f"{primary_id['system']}|{primary_id['value']}"
        location = f"/api/v2/spp/Individual/{resource_identifier}"
        response.headers["Location"] = location

    # Log successful create
    audit_service.log_create("individual", resource_identifier, partner)

    return data


@individual_router.put("/{identifier}", response_model=Individual)
async def update_individual(
    identifier: Annotated[str, Path()],
    individual: Individual,
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    if_match: Annotated[str | None, Header()] = None,
):
    """
    Update Individual (full replacement).

    CRITICAL:
    - Requires If-Match header with version ID for optimistic locking
    - Updates with source tracking
    """
    # Check client has update scope
    if not api_client.has_scope("individual", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'individual:update'. Request access from your administrator.",
        )

    # Parse identifier and find individual
    system, value = parse_identifier(identifier)
    service = IndividualService(env)
    audit_service = ApiAuditService(
        env,
        api_client,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    partner = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_individual_access(partner, api_client, env, "update")

    # Check version for optimistic locking
    # Use integer microseconds to match versionId generation in services
    if if_match:
        current_version = str(int(partner.write_date.timestamp() * 1000000)) if partner.write_date else "1"
        if_match_clean = if_match.strip('"')
        if if_match_clean != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Version conflict. Resource was modified by another request.",
            )

    # Update individual
    source_system = f"urn:openspp:api-client:{api_client.client_id}"

    try:
        partner = service.update(partner, individual, source=source_system)
    except ValidationError as ve:
        _logger.warning("Validation error updating individual: %s", ve)
        audit_service.log_update("individual", identifier, partner, status="validation_error")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        ) from ve
    except Exception as e:
        _logger.exception("Error updating individual")
        audit_service.log_update("individual", identifier, partner, status="error")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to update individual",
        ) from e

    # Log successful update
    audit_service.log_update("individual", identifier, partner)

    # Return updated resource
    return service.to_api_schema(partner)


@individual_router.patch("/{identifier}", response_model=Individual)
async def patch_individual(
    identifier: Annotated[str, Path()],
    patch: IndividualPatch,
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    if_match: Annotated[str | None, Header()] = None,
):
    """
    Partially update Individual (JSON Merge Patch - RFC 7396).

    Only specified fields are updated. Omitted fields remain unchanged.
    Use null to clear a field's value.

    Supports optimistic locking via If-Match header with version ID.
    """
    # Check client has update scope
    if not api_client.has_scope("individual", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'individual:update'. Request access from your administrator.",
        )

    # Parse identifier and find individual
    system, value = parse_identifier(identifier)
    service = IndividualService(env)
    audit_service = ApiAuditService(
        env,
        api_client,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    partner = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_individual_access(partner, api_client, env, "update")

    # Check version for optimistic locking
    if if_match:
        current_version = str(int(partner.write_date.timestamp() * 1000000)) if partner.write_date else "1"
        if_match_clean = if_match.strip('"')
        if if_match_clean != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Version conflict. Resource was modified by another request.",
            )

    # Perform partial update
    source_system = f"urn:openspp:api-client:{api_client.client_id}"

    try:
        partner = service.partial_update(partner, patch, source=source_system)
    except ValidationError as ve:
        _logger.warning("Validation error patching individual: %s", ve)
        audit_service.log_patch("individual", identifier, partner, status="validation_error")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        ) from ve
    except Exception as e:
        _logger.exception("Error patching individual")
        audit_service.log_patch("individual", identifier, partner, status="error")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to patch individual",
        ) from e

    # Log successful patch
    audit_service.log_patch("individual", identifier, partner)

    # Return updated resource
    return service.to_api_schema(partner)


@individual_router.get(
    "/{identifier}/groups",
    response_model=GroupMembershipBundle,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def get_individual_groups(
    identifier: Annotated[str, Path(description="Format: {system}|{value} (URL-encoded)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    membership_status: Annotated[str | None, Query(alias="status", pattern="^(active|inactive)$")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 100,
):
    """
    Get all groups an individual belongs to (reverse lookup).

    Returns a Bundle of group memberships with the following information:
    - Group reference (Group/{system}|{value})
    - Individual reference (Individual/{system}|{value})
    - Membership role (head, spouse, child, etc.)
    - Start and end dates
    - Membership status (active/inactive)

    Query parameters:
    - status: Filter by "active" or "inactive" (default: all)
    - _count: Maximum results (default: 100)

    Security:
    - Requires scope: individual:read
    - Applies consent filtering if applicable
    """
    # Check client has read scope
    if not api_client.has_scope("individual", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'individual:read'. Request access from your administrator.",
        )

    # Parse identifier and find individual
    system, value = parse_identifier(identifier)
    service = IndividualService(env)
    partner = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_individual_access(partner, api_client, env, "read")

    # Get group memberships
    memberships = service.get_groups(partner, status=membership_status, limit=count)

    # Build bundle entries
    entries = []
    for membership_data in memberships:
        entries.append({"resource": membership_data})

    # Return bundle
    return GroupMembershipBundle(
        type="GroupMembershipList",
        total=len(memberships),
        entry=entries,
    )
