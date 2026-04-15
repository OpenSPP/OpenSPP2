# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Group resource endpoints"""

import asyncio
import logging
import random
from datetime import datetime
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
from ..schemas.group import Group
from ..schemas.membership import (
    AddMemberRequest,
    MembershipResponse,
    MergeGroupRequest,
    RemoveMemberRequest,
    SplitGroupRequest,
    UpdateMemberRequest,
)
from ..schemas.patch import GroupPatch
from ..schemas.search_result import SearchResult, create_search_result
from ..services.api_audit_service import ApiAuditService
from ..services.consent_service import ConsentService
from ..services.field_filter import filter_fields, filter_list
from ..services.group_service import GroupService
from ..services.search_service import SearchService
from ..utils.pagination import fetch_with_consent
from .dependencies import check_group_access, parse_identifier, parse_resource_reference

_logger = logging.getLogger(__name__)

group_router = APIRouter(tags=["Group"], prefix="/Group")


@group_router.get(
    "/{identifier}",
    response_model=Group,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def read_group(
    identifier: Annotated[str, Path(description="Format: {system}|{value}")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
    elements: Annotated[str | None, Query(alias="_elements")] = None,
    extensions: Annotated[str | None, Query(alias="_extensions")] = None,
):
    """Read Group by external identifier"""
    # Check scope
    if not api_client.has_scope("group", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:read'. Request access from your administrator.",
        )

    if "|" not in identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format. Expected: {system}|{value}",
        )

    system, value = identifier.split("|", 1)

    # Find group
    service = GroupService(env)
    group = service.find_by_identifier(system, value)

    # SECURITY: Prevent user enumeration
    # For clients requiring consent, return same error for "not found" and "no consent"
    if not group:
        if api_client.is_require_consent:
            # SECURITY: Add timing jitter to prevent timing-based enumeration
            await asyncio.sleep(0.05 + random.uniform(0, 0.02))  # 50-70ms delay
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    # Convert to API schema
    extension_list = extensions.split(",") if extensions else None
    data = service.to_api_schema(group, extensions=extension_list)

    # Apply consent filtering
    consent_service = ConsentService(env)
    filtered_data = consent_service.filter_response(
        group.id,
        api_client,
        "group",
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

    # Add ETag header
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


@group_router.get(
    "",
    response_model=SearchResult,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def search_groups(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    identifier: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    type_: Annotated[str | None, Query(alias="type")] = None,
    member: Annotated[str | None, Query()] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
    elements: Annotated[str | None, Query(alias="_elements")] = None,
    extensions: Annotated[str | None, Query(alias="_extensions")] = None,
):
    """
    Search for groups.

    Search parameters:
    - identifier: system|value
    - name: string (contains)
    - type: household/family/organization/other
    - member: Individual reference
    - _count: page size
    - _offset: skip records
    - _extensions: comma-separated list of extensions to include
    """
    # Check scope
    if not api_client.has_scope("group", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:read'. Request access from your administrator.",
        )

    # Build search parameters
    params = {
        "identifier": identifier,
        "name": name,
        "type": type_,
        "member": member,
        "_count": count,
        "_offset": offset,
    }
    params = {k: v for k, v in params.items() if v is not None}

    # Execute search with consent-aware pagination
    search_service = SearchService(env)
    group_service = GroupService(env)
    consent_service = ConsentService(env)
    extension_list = extensions.split(",") if extensions else None

    def search_function(offset, limit):
        search_params = {**params, "_count": limit, "_offset": offset}
        return search_service.search_groups(search_params)

    def consent_filter_function(group):
        group_data = group_service.to_api_schema(group, extensions=extension_list)
        if group_data is None:
            return None
        filtered_data = consent_service.filter_response(group.id, api_client, "group", group_data)
        consent_info = filtered_data.pop("_consent", None)
        if consent_info and consent_info.get("status") in (
            "no_consent",
            "scope_mismatch",
        ):
            return None
        return filtered_data

    data, db_offset_consumed, raw_total, consent_was_applied = fetch_with_consent(
        search_function, consent_filter_function, count, offset
    )

    # Apply _elements filter for sparse fieldsets
    if elements:
        data = filter_list(data, elements)

    # Suppress total when consent filtering is active
    if consent_was_applied:
        total = len(data)
    else:
        total = raw_total

    # Build pagination links with proper URL encoding
    base_url = "/api/v2/spp/Group"
    base_params = {k: v for k, v in params.items() if k not in ("_count", "_offset")}

    def build_url(offset_val: int) -> str:
        """Build properly URL-encoded pagination URL."""
        url_params = {**base_params, "_count": count, "_offset": offset_val}
        return f"{base_url}?{urlencode(url_params)}"

    next_offset = db_offset_consumed if consent_was_applied else offset + count
    has_more = len(data) >= count

    self_url = build_url(offset)
    next_url = build_url(next_offset) if has_more else None
    prev_url = build_url(max(0, offset - count)) if offset > 0 else None

    return create_search_result(
        data=data,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )


@group_router.post("", response_model=Group, status_code=status.HTTP_201_CREATED)
async def create_group(
    group: Group,
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """Create new Group"""
    if not api_client.has_scope("group", "create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:create'. Request access from your administrator.",
        )

    service = GroupService(env)
    source_system = f"urn:openspp:api-client:{api_client.client_id}"

    # Initialize audit service
    audit_service = ApiAuditService(
        env,
        api_client,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    try:
        # api_authorized=True tells service to skip user group check since
        # API client scope (verified above) is the authorization for API calls
        group_record = service.create(group, source=source_system, api_authorized=True)
    except ValidationError as ve:
        _logger.warning("Validation error creating group: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        ) from ve
    except Exception as e:
        _logger.exception("Error creating group")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to create group",
        ) from e

    # Return created resource
    data = service.to_api_schema(group_record)

    # Set Location header and log audit
    if data.get("identifier"):
        primary_id = data["identifier"][0]
        location = f"/api/v2/spp/Group/{primary_id['system']}|{primary_id['value']}"
        response.headers["Location"] = location

        # Log successful creation
        audit_service.log_create(
            resource_type="group",
            resource_identifier=f"{primary_id['system']}|{primary_id['value']}",
            record=group_record,
        )

    return data


@group_router.put("/{identifier}", response_model=Group)
async def update_group(
    identifier: Annotated[str, Path()],
    group: Group,
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    if_match: Annotated[str | None, Header()] = None,
):
    """Update Group (full replacement)"""
    if not api_client.has_scope("group", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:update'. Request access from your administrator.",
        )

    if "|" not in identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format",
        )

    system, value = identifier.split("|", 1)

    # Find group
    service = GroupService(env)
    group_record = service.find_by_identifier(system, value)

    # SECURITY: Prevent user enumeration
    if not group_record:
        if api_client.is_require_consent:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found",
        )

    # SECURITY: Check consent before allowing update (for clients requiring consent)
    if api_client.is_require_consent:
        consent_service = ConsentService(env)
        if not consent_service.check_access(group_record.id, api_client, "group", "update"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

    # Check version for optimistic locking
    # Use integer microseconds to match versionId generation in services
    if if_match:
        current_version = str(int(group_record.write_date.timestamp() * 1000000)) if group_record.write_date else "1"
        if_match_clean = if_match.strip('"')
        if if_match_clean != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Version conflict. Resource was modified by another request.",
            )

    # Update group
    source_system = f"urn:openspp:api-client:{api_client.client_id}"

    try:
        group_record = service.update(group_record, group, source=source_system)
    except ValidationError as ve:
        _logger.warning("Validation error updating group: %s", ve)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        ) from ve
    except Exception as e:
        _logger.exception("Error updating group")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to update group",
        ) from e

    # Log successful update
    audit_service = ApiAuditService(
        env,
        api_client,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    audit_service.log_update(
        resource_type="group",
        resource_identifier=identifier,
        record=group_record,
    )

    return service.to_api_schema(group_record)


@group_router.patch("/{identifier}", response_model=Group)
async def patch_group(
    identifier: Annotated[str, Path()],
    patch: GroupPatch,
    request: Request,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    if_match: Annotated[str | None, Header()] = None,
):
    """
    Partially update Group (JSON Merge Patch - RFC 7396).

    Only specified fields are updated. Omitted fields remain unchanged.
    Use null to clear a field's value.

    Supports optimistic locking via If-Match header with version ID.
    """
    # Check client has update scope
    if not api_client.has_scope("group", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:update'. Request access from your administrator.",
        )

    # Parse identifier and find group
    system, value = parse_identifier(identifier)
    service = GroupService(env)
    group_record = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_group_access(group_record, api_client, env, "update")

    # Check version for optimistic locking
    if if_match:
        current_version = str(int(group_record.write_date.timestamp() * 1000000)) if group_record.write_date else "1"
        if_match_clean = if_match.strip('"')
        if if_match_clean != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Version conflict. Resource was modified by another request.",
            )

    # Perform partial update
    source_system = f"urn:openspp:api-client:{api_client.client_id}"
    audit_service = ApiAuditService(
        env,
        api_client,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    try:
        group_record = service.partial_update(group_record, patch, source=source_system)
    except ValidationError as ve:
        _logger.warning("Validation error patching group: %s", ve)
        audit_service.log_patch("group", identifier, group_record, status="validation_error")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        ) from ve
    except Exception as e:
        _logger.exception("Error patching group")
        audit_service.log_patch("group", identifier, group_record, status="error")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to patch group",
        ) from e

    # Log successful patch
    audit_service.log_patch("group", identifier, group_record)

    # Return updated resource
    return service.to_api_schema(group_record)


@group_router.post(
    "/{identifier}/$add-member",
    response_model=MembershipResponse,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    identifier: Annotated[str, Path(description="Format: {system}|{value}")],
    request: AddMemberRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Add a member to a group"""
    if not api_client.has_scope("group", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:update'. Request access from your administrator.",
        )

    # Parse identifier and find group
    system, value = parse_identifier(identifier)
    service = GroupService(env)
    group = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_group_access(group, api_client, env, "update")

    # Parse individual reference
    ind_system, ind_value = parse_resource_reference(request.entity.reference, "Individual")

    # Find individual
    individual = service._find_individual(ind_system, ind_value)
    if not individual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Individual not found",
        )

    # Extract role coding if provided
    role_coding = None
    if request.role and request.role.coding:
        role_coding = {
            "system": request.role.coding[0].system,
            "code": request.role.coding[0].code,
            "display": request.role.coding[0].display if hasattr(request.role.coding[0], "display") else None,
        }

    # Add member
    try:
        result = service.add_member(
            group,
            individual,
            role_coding=role_coding,
            start_date=request.start_date,
        )
    except Exception as e:
        _logger.exception("Error adding member to group")
        # Check for specific errors
        if "already a member" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to add member",
        ) from e

    return result


@group_router.post(
    "/{identifier}/$remove-member",
    response_model=MembershipResponse,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def remove_member(
    identifier: Annotated[str, Path(description="Format: {system}|{value}")],
    request: RemoveMemberRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Remove a member from a group"""
    if not api_client.has_scope("group", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:update'. Request access from your administrator.",
        )

    # Parse identifier and find group
    system, value = parse_identifier(identifier)
    service = GroupService(env)
    group = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_group_access(group, api_client, env, "update")

    # Parse individual reference
    ind_system, ind_value = parse_resource_reference(request.entity.reference, "Individual")

    # Find individual
    individual = service._find_individual(ind_system, ind_value)
    if not individual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Individual not found",
        )

    # Remove member
    try:
        result = service.remove_member(
            group,
            individual,
            ended_date=request.ended_date,
            reason=request.reason,
        )
    except Exception as e:
        _logger.exception("Error removing member from group")
        # Check for specific errors
        if "not a member" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to remove member",
        ) from e

    return result


@group_router.patch(
    "/{identifier}/member/{individual_identifier}",
    response_model=MembershipResponse,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def update_member(
    identifier: Annotated[str, Path(description="Group identifier. Format: {system}|{value}")],
    individual_identifier: Annotated[str, Path(description="Individual identifier. Format: {system}|{value}")],
    request: UpdateMemberRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """Update a member's role or dates in a group"""
    if not api_client.has_scope("group", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:update'. Request access from your administrator.",
        )

    # Parse identifiers
    system, value = parse_identifier(identifier)
    ind_system, ind_value = parse_identifier(individual_identifier)

    # Find group
    service = GroupService(env)
    group = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_group_access(group, api_client, env, "update")

    # Find individual
    individual = service._find_individual(ind_system, ind_value)
    if not individual:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Individual not found",
        )

    # Extract role coding if provided
    role_coding = None
    if request.role and request.role.coding:
        role_coding = {
            "system": request.role.coding[0].system,
            "code": request.role.coding[0].code,
            "display": request.role.coding[0].display if hasattr(request.role.coding[0], "display") else None,
        }

    # Update member
    try:
        result = service.update_member(
            group,
            individual,
            role_coding=role_coding,
            start_date=request.start_date,
            ended_date=request.ended_date,
        )
    except Exception as e:
        _logger.exception("Error updating member in group")
        # Check for specific errors
        if "not a member" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to update member",
        ) from e

    return result


@group_router.post(
    "/$merge",
    response_model=Group,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def merge_groups(
    request: MergeGroupRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Merge two groups into one.

    All members from source group are moved to target group.
    Source group is then deactivated.
    """
    if not api_client.has_scope("group", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:update'. Request access from your administrator.",
        )

    # Parse group references
    source_system, source_value = parse_resource_reference(request.source_group.reference, "Group")
    target_system, target_value = parse_resource_reference(request.target_group.reference, "Group")

    # Find groups
    service = GroupService(env)
    source_group = service.find_by_identifier(source_system, source_value)
    target_group = service.find_by_identifier(target_system, target_value)

    # Security checks for both groups (with specific error messages)
    if not source_group:
        if api_client.is_require_consent:
            await asyncio.sleep(0.05 + random.uniform(0, 0.02))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source group not found")

    if not target_group:
        if api_client.is_require_consent:
            await asyncio.sleep(0.05 + random.uniform(0, 0.02))
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target group not found")

    # SECURITY: Check consent for both groups (for clients requiring consent)
    if api_client.is_require_consent:
        consent_service = ConsentService(env)
        if not consent_service.check_access(source_group.id, api_client, "group", "update"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        if not consent_service.check_access(target_group.id, api_client, "group", "update"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Validate groups are different
    if source_group.id == target_group.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target groups must be different",
        )

    # Validate source group is active
    if not source_group.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Source group is already inactive and cannot be merged",
        )

    # Perform merge
    try:
        result = service.merge_groups(
            source_group,
            target_group,
            role_mapping=request.role_mapping,
        )
    except Exception as e:
        _logger.exception("Error merging groups")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to merge groups",
        ) from e

    return result


@group_router.post(
    "/{identifier}/$split",
    response_model=Group,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    status_code=status.HTTP_201_CREATED,
)
async def split_group(
    identifier: Annotated[str, Path(description="Format: {system}|{value}")],
    request: SplitGroupRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Split a group by moving some members to a new group.

    The source group (specified in path) keeps remaining members.
    A new group is created with the moved members.
    """
    # Requires both create (new group) and update (source group) permissions
    if not api_client.has_scope("group", "create") or not api_client.has_scope("group", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scopes 'group:create' and 'group:update'. Request access from your administrator.",
        )

    # Parse identifier and find source group
    system, value = parse_identifier(identifier)
    service = GroupService(env)
    source_group = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_group_access(source_group, api_client, env, "update")

    # Validate request has members to move
    if not request.members_to_move:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="membersToMove must not be empty",
        )

    # Parse and find all individuals to move
    members_to_move = []
    for member_ref in request.members_to_move:
        ind_system, ind_value = parse_resource_reference(member_ref.reference, "Individual")

        # Find individual
        individual = service._find_individual(ind_system, ind_value)
        if not individual:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Individual not found: {ind_system}|{ind_value}",
            )

        members_to_move.append(individual)

    # Parse new head if provided
    new_head = None
    if request.new_head:
        if not request.new_head.reference or not request.new_head.reference.startswith("Individual/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid newHead reference. Expected: Individual/{system}|{value}",
            )

        head_ident_str = request.new_head.reference.replace("Individual/", "")
        if "|" not in head_ident_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid identifier format in newHead reference",
            )

        head_system, head_value = head_ident_str.split("|", 1)

        # Find new head individual
        new_head = service._find_individual(head_system, head_value)
        if not new_head:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"New head individual not found: {head_ident_str}",
            )

    # Convert identifiers to dict format for service
    new_identifiers = [{"system": ident.system, "value": ident.value} for ident in request.new_group_identifier]

    # Perform split
    source_system = f"urn:openspp:api-client:{api_client.client_id}"
    try:
        result = service.split_group(
            source_group,
            new_identifiers,
            members_to_move,
            new_head=new_head,
            source=source_system,
        )
    except Exception as e:
        _logger.exception("Error splitting group")
        # Check for specific validation errors
        error_msg = str(e).lower()
        if "not a member" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        if "no members specified" in error_msg or "must be in the list" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e
        if "must have at least one member" in error_msg or "head" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Failed to split group",
        ) from e

    # Set Location header for newly created group
    if result.get("identifier"):
        primary_id = result["identifier"][0]
        location = f"/api/v2/spp/Group/{primary_id['system']}|{primary_id['value']}"
        response.headers["Location"] = location

    return result


@group_router.get(
    "/{identifier}/membership-history",
    response_model=SearchResult,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
)
async def get_membership_history(
    identifier: Annotated[str, Path(description="Format: {system}|{value}")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    count: Annotated[int, Query(alias="_count", ge=1, le=500)] = 100,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
    since: Annotated[str | None, Query(alias="_since")] = None,
):
    """
    Get membership change history for a group.

    Returns a timeline of all membership additions and removals.

    Query parameters:
    - _count: Maximum results (default: 100, max: 500)
    - _offset: Skip records (default: 0)
    - _since: Only show events after this datetime (ISO 8601 format)
    """
    if not api_client.has_scope("group", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'group:read'. Request access from your administrator.",
        )

    # Parse identifier and find group
    system, value = parse_identifier(identifier)
    service = GroupService(env)
    group = service.find_by_identifier(system, value)

    # Security checks (enumeration prevention + consent)
    await check_group_access(group, api_client, env, "read")

    # Parse since parameter if provided
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid _since parameter. Expected ISO 8601 datetime format.",
            ) from err

    # Get total count at the database level (no need to load all records)
    total = service.get_membership_history_count(group, since=since_dt)

    # Get paginated history entries and serialize to dicts
    history_entries = service.get_membership_history(group, limit=count, offset=offset, since=since_dt)
    data = [entry.model_dump(mode="json", by_alias=True, exclude_none=True) for entry in history_entries]

    # Build pagination URLs
    base_url = f"/api/v2/spp/Group/{identifier}/membership-history"

    def build_url(offset_val: int) -> str:
        """Build properly URL-encoded pagination URL."""
        url_params = {"_count": count, "_offset": offset_val}
        if since:
            url_params["_since"] = since
        return f"{base_url}?{urlencode(url_params)}"

    self_url = build_url(offset)
    next_url = build_url(offset + count) if offset + count < total else None
    prev_url = build_url(max(0, offset - count)) if offset > 0 else None

    return create_search_result(
        data=data,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )
