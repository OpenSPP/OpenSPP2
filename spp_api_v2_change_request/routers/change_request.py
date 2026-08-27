# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Change Request API endpoints."""

import logging
from typing import Annotated
from urllib.parse import urlencode

from odoo.api import Environment
from odoo.exceptions import AccessDenied, AccessError, UserError, ValidationError

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
    ChangeRequestTypeInfo,
    ChangeRequestTypeSchema,
    ChangeRequestUpdate,
    RejectActionData,
    RequestRevisionActionData,
)
from ..services.change_request_service import ChangeRequestService

_logger = logging.getLogger(__name__)

change_request_router = APIRouter(tags=["ChangeRequest"], prefix="/ChangeRequest")


def _status_for_odoo_error(exc: Exception) -> int:
    """Map an Odoo exception raised by a state transition to an HTTP status.

    ``AccessError`` must be distinguished before ``UserError``: it subclasses
    ``UserError`` in Odoo, so a bare ``except UserError`` reports an
    authorization failure as ``409 Conflict``. That is wrong twice over -- a
    client is told to resolve a conflict it cannot see, and a client that
    retries on 409 (reasonable for a genuine conflict, which may clear) loops
    on a permission error that never will.

    ``AccessDenied`` is grouped with ``AccessError``: both report an
    authorization failure, and the platform's global handler
    (``fastapi.error_handlers``) maps the pair to 403 the same way.
    """
    if isinstance(exc, (AccessError, AccessDenied)):
        return status.HTTP_403_FORBIDDEN
    return status.HTTP_409_CONFLICT


def _build_reference(p1: str, p2: str, p3: str) -> str:
    """Reconstruct CR reference from path segments (e.g., CR/2026/00001)."""
    return f"{p1}/{p2}/{p3}"


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


# Type schema endpoints are registered before /{p1}/{p2}/{p3} so that FastAPI
# matches "$types" as a literal path segment rather than capturing it as
# path parameters.


@change_request_router.get(
    "/$types",
    response_model=list[ChangeRequestTypeInfo],
)
async def list_change_request_types(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    List all active Change Request types.

    Returns type code, name, target type, and whether an applicant is required.
    """
    if not api_client.has_scope("change_request", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read change request types",
        )

    service = ChangeRequestService(env)
    return service.get_type_list()


@change_request_router.get(
    "/$types/{code}",
    response_model=ChangeRequestTypeSchema,
)
async def get_change_request_type_schema(
    code: Annotated[str, Path(description="CR type code (e.g., edit_individual)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Get the full field schema for a Change Request type.

    Returns type info, field definitions, and document requirements.
    """
    if not api_client.has_scope("change_request", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have permission to read change request types",
        )

    service = ChangeRequestService(env)
    result = service.get_type_schema(code)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request type not found: {code}",
        )

    return result


@change_request_router.get("/{p1}/{p2}/{p3}", response_model=ChangeRequestResponse)
async def read_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
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
    base_params = {
        k: v
        for k, v in {
            "registrant": registrant,
            "requestType": request_type,
            "status": cr_status,
            "createdAfter": created_after,
            "createdBefore": created_before,
        }.items()
        if v is not None
    }

    def build_url(offset_val: int) -> str:
        """Build properly URL-encoded pagination URL."""
        url_params = {**base_params, "_count": count, "_offset": offset_val}
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


@change_request_router.put("/{p1}/{p2}/{p3}", response_model=ChangeRequestResponse)
async def update_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
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


@change_request_router.post("/{p1}/{p2}/{p3}/$submit", response_model=ChangeRequestResponse)
async def submit_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
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
            status_code=_status_for_odoo_error(e),
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{p1}/{p2}/{p3}/$approve", response_model=ChangeRequestResponse)
async def approve_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
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
            status_code=_status_for_odoo_error(e),
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{p1}/{p2}/{p3}/$reject", response_model=ChangeRequestResponse)
async def reject_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        service.reject(cr, reason=action_data.reason)
    except UserError as e:
        raise HTTPException(
            status_code=_status_for_odoo_error(e),
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{p1}/{p2}/{p3}/$request-revision", response_model=ChangeRequestResponse)
async def request_revision_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
    service = ChangeRequestService(env)
    cr = service.find_by_reference(reference)

    if not cr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Change request not found: {reference}",
        )

    try:
        service.request_revision(cr, notes=action_data.notes)
    except UserError as e:
        raise HTTPException(
            status_code=_status_for_odoo_error(e),
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{p1}/{p2}/{p3}/$apply", response_model=ChangeRequestResponse)
async def apply_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
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
            status_code=_status_for_odoo_error(e),
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)


@change_request_router.post("/{p1}/{p2}/{p3}/$reset", response_model=ChangeRequestResponse)
async def reset_change_request(
    p1: Annotated[str, Path(description="Reference part 1 (e.g., CR)")],
    p2: Annotated[str, Path(description="Reference part 2 (e.g., 2026)")],
    p3: Annotated[str, Path(description="Reference part 3 (e.g., 00001)")],
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

    reference = _build_reference(p1, p2, p3)
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
            status_code=_status_for_odoo_error(e),
            detail=str(e),
        ) from e

    return service.to_api_schema(cr)
