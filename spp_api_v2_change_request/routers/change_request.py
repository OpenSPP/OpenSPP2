# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Change Request API endpoints."""

import logging
from typing import Annotated

from odoo.api import Environment
from odoo.exceptions import UserError, ValidationError

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client
from odoo.addons.spp_api_v2.schemas.search_result import (
    SearchResult,
    create_search_result,
)

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)

from ..schemas.change_request import (
    ApproveActionData,
    ChangeRequestCreate,
    ChangeRequestResponse,
    ChangeRequestUpdate,
    RejectActionData,
    RequestRevisionActionData,
)
from ..services.change_request_service import ChangeRequestService

_logger = logging.getLogger(__name__)

change_request_router = APIRouter(tags=["ChangeRequest"], prefix="/ChangeRequest")


@change_request_router.post(
    "",
    response_model=ChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_change_request(
    cr_data: ChangeRequestCreate,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Create a new change request.

    The change request will be created in draft status.
    Use the $submit action to submit for approval.
    """
    # Check permission
    if not api_client.has_scope("change_request", "create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to create change requests",
        )

    service = ChangeRequestService(env)
    source = f"urn:openspp:api-client:{api_client.client_id}"

    try:
        cr = service.create(cr_data, source=source)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except Exception as e:
        _logger.exception("Error creating change request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create change request: {str(e)}",
        ) from e

    # Set Location header
    response.headers["Location"] = f"/api/v2/spp/ChangeRequest/{cr.name}"

    return service.to_api_schema(cr)


@change_request_router.get("/{reference}", response_model=ChangeRequestResponse)
async def read_change_request(
    reference: Annotated[str, Path(description="CR reference (e.g., CR/2024/00001)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    response: Response,
):
    """
    Read a change request by reference.

    The reference is the CR number (e.g., CR/2024/00001), NOT a database ID.
    """
    # Check permission
    if not api_client.has_scope("change_request", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read change requests",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    data = service.to_api_schema(cr)

    # Add ETag header
    if data.get("meta", {}).get("versionId"):
        response.headers["ETag"] = f'"{data["meta"]["versionId"]}"'

    return data


@change_request_router.get("", response_model=SearchResult)
async def search_change_requests(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    registrant: Annotated[str | None, Query(description="Registrant identifier (system|value)")] = None,
    request_type: Annotated[str | None, Query(alias="requestType")] = None,
    cr_status: Annotated[str | None, Query(alias="status")] = None,
    created_after: Annotated[str | None, Query(alias="createdAfter")] = None,
    created_before: Annotated[str | None, Query(alias="createdBefore")] = None,
    count: Annotated[int, Query(alias="_count", ge=1, le=100)] = 20,
    offset: Annotated[int, Query(alias="_offset", ge=0)] = 0,
):
    """
    Search for change requests.

    Supports filtering by:
    - registrant: system|value identifier
    - requestType: CR type code
    - status: draft, pending, revision, approved, rejected, applied
    - createdAfter/createdBefore: date filters

    Returns a SearchResult with paginated data.
    """
    # Check permission
    if not api_client.has_scope("change_request", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to search change requests",
        )

    # Build params
    params = {
        "registrant": registrant,
        "request_type": request_type,
        "status": cr_status,
        "created_after": created_after,
        "created_before": created_before,
        "_count": count,
        "_offset": offset,
    }
    params = {k: v for k, v in params.items() if v is not None}

    service = ChangeRequestService(env)
    records, total = service.search(params)

    # Build data array
    data = [service.to_api_schema(cr) for cr in records]

    # Build pagination URLs
    base_url = "/api/v2/spp/ChangeRequest"
    query_parts = []
    if registrant:
        query_parts.append(f"registrant={registrant}")
    if request_type:
        query_parts.append(f"requestType={request_type}")
    if cr_status:
        query_parts.append(f"status={cr_status}")
    if created_after:
        query_parts.append(f"createdAfter={created_after}")
    if created_before:
        query_parts.append(f"createdBefore={created_before}")
    query_params = "&".join(query_parts)

    # Build self URL
    self_url = (
        f"{base_url}?{query_params}&_count={count}&_offset={offset}"
        if query_params
        else f"{base_url}?_count={count}&_offset={offset}"
    )

    # Build next URL
    next_url = None
    if offset + count < total:
        next_offset = offset + count
        next_url = (
            f"{base_url}?{query_params}&_count={count}&_offset={next_offset}"
            if query_params
            else f"{base_url}?_count={count}&_offset={next_offset}"
        )

    # Build prev URL
    prev_url = None
    if offset > 0:
        prev_offset = max(0, offset - count)
        prev_url = (
            f"{base_url}?{query_params}&_count={count}&_offset={prev_offset}"
            if query_params
            else f"{base_url}?_count={count}&_offset={prev_offset}"
        )

    return create_search_result(
        data=data,
        total=total,
        offset=offset,
        self_url=self_url,
        next_url=next_url,
        prev_url=prev_url,
    )


@change_request_router.put("/{reference}", response_model=ChangeRequestResponse)
async def update_change_request(
    reference: Annotated[str, Path()],
    update_data: ChangeRequestUpdate,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    if_match: Annotated[str | None, Header()] = None,
):
    """
    Update change request detail data.

    Only draft change requests can be updated.
    Use If-Match header with version ID for optimistic locking.
    """
    # Check permission
    if not api_client.has_scope("change_request", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to update change requests",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    # Check version for optimistic locking
    if if_match:
        current_version = str(int(cr.write_date.timestamp() * 1000000)) if cr.write_date else "1"
        if_match_clean = if_match.strip('"')
        if if_match_clean != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Version conflict. Resource was modified by another request.",
            )

    if cr.approval_state != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft change requests can be updated",
        )

    try:
        service.update_detail(cr, update_data.detail)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


# === Actions ===


@change_request_router.post("/{reference}/$submit", response_model=ChangeRequestResponse)
async def submit_change_request(
    reference: Annotated[str, Path()],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Submit change request for approval.

    Only draft change requests can be submitted.
    """
    if not api_client.has_scope("change_request", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to submit change requests",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        service.submit(cr)
    except UserError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{reference}/$approve", response_model=ChangeRequestResponse)
async def approve_change_request(
    reference: Annotated[str, Path()],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    action_data: ApproveActionData | None = None,
):
    """
    Approve a pending change request.

    Requires approval permission for the CR type.
    """
    if not api_client.has_scope("change_request", "approve"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to approve change requests",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        comment = action_data.comment if action_data else None
        service.approve(cr, comment=comment)
    except UserError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{reference}/$reject", response_model=ChangeRequestResponse)
async def reject_change_request(
    reference: Annotated[str, Path()],
    action_data: RejectActionData,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Reject a pending change request.

    Requires rejection reason.
    """
    if not api_client.has_scope("change_request", "approve"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to reject change requests",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        service.reject(cr, reason=action_data.reason)
    except (UserError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{reference}/$request-revision", response_model=ChangeRequestResponse)
async def request_revision_change_request(
    reference: Annotated[str, Path()],
    action_data: RequestRevisionActionData,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Request revision on a pending change request.

    Requires revision notes.
    """
    if not api_client.has_scope("change_request", "approve"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to request revision",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        service.request_revision(cr, notes=action_data.notes)
    except (UserError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{reference}/$apply", response_model=ChangeRequestResponse)
async def apply_change_request(
    reference: Annotated[str, Path()],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Apply an approved change request.

    This executes the changes to the registrant.
    """
    if not api_client.has_scope("change_request", "apply"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to apply change requests",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        service.apply(cr)
    except UserError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{reference}/$reset", response_model=ChangeRequestResponse)
async def reset_change_request(
    reference: Annotated[str, Path()],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Reset a rejected/revision CR to draft.

    Allows resubmission after making changes.
    """
    if not api_client.has_scope("change_request", "update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to reset change requests",
        )

    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        service.reset_to_draft(cr)
    except UserError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)
