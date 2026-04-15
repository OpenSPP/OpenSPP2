# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Bulk operation endpoints for OpenSPP API V2"""

import asyncio
import logging
import random
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.auth import get_authenticated_client
from ..schemas.bulk import BulkExportItem, BulkExportRequest, BulkExportResponse
from ..services.consent_service import ConsentService
from ..services.field_filter import filter_fields
from ..services.group_service import GroupService
from ..services.individual_service import IndividualService

_logger = logging.getLogger(__name__)

bulk_router = APIRouter(tags=["Bulk Operations"], prefix="/$bulk")


@bulk_router.post(
    "/export",
    response_model=BulkExportResponse,
    response_model_exclude_none=True,
)
async def bulk_export(
    request: BulkExportRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
):
    """
    Bulk export multiple resources by identifier.

    Efficiently retrieve multiple resources in a single request.
    Up to 100 identifiers can be requested per call.

    Returns results for each identifier with status indicating success or failure.
    Access is controlled by the same consent rules as individual reads.
    """
    resource_type = request.type

    # Check appropriate scope
    scope_name = resource_type.lower()
    if not api_client.has_scope(scope_name, "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope '{scope_name}:read'. Request access from your administrator.",
        )

    # Get services
    consent_service = ConsentService(env)

    if resource_type == "Individual":
        service = IndividualService(env)
    else:
        service = GroupService(env)

    # Parse identifiers and separate valid from invalid
    parsed = []  # List of (identifier_str, system, value)
    items = []
    failed = 0

    for identifier in request.identifiers:
        if "|" not in identifier:
            items.append(
                BulkExportItem(
                    identifier=identifier,
                    status="error",
                    error="Invalid identifier format. Expected: {system}|{value}",
                )
            )
            failed += 1
        else:
            system, value = identifier.split("|", 1)
            parsed.append((identifier, system, value))

    # Batch lookup all valid identifiers in a single query
    if parsed:
        lookup_keys = [(system, value) for _, system, value in parsed]
        records_map = service.find_by_identifiers(lookup_keys)
    else:
        records_map = {}

    # Process results
    successful = 0
    extension_list = request.extensions.split(",") if request.extensions else None

    for identifier, _system, _value in parsed:
        record = records_map.get(identifier)

        if not record:
            if api_client.is_require_consent:
                # SECURITY: Add timing jitter to prevent enumeration via timing
                await asyncio.sleep(0.05 + random.uniform(0, 0.02))  # 50-70ms delay
                # Don't reveal if resource exists for consent-required clients
                items.append(
                    BulkExportItem(
                        identifier=identifier,
                        status="access_denied",
                        error="Access denied",
                    )
                )
            else:
                items.append(
                    BulkExportItem(
                        identifier=identifier,
                        status="not_found",
                        error=f"{resource_type} not found",
                    )
                )
            failed += 1
            continue

        # Convert to API schema
        data = service.to_api_schema(record, extensions=extension_list)
        if data is None:  # pragma: no cover — record has no valid identifiers
            continue

        # Apply consent filtering
        filtered_data = consent_service.filter_response(
            record.id,
            api_client,
            scope_name,
            data,
        )

        # Check if consent was denied
        if api_client.is_require_consent:
            consent_info = filtered_data.get("_consent", {})
            if consent_info.get("status") in ("no_consent", "scope_mismatch"):
                items.append(
                    BulkExportItem(
                        identifier=identifier,
                        status="access_denied",
                        error="Access denied",
                    )
                )
                failed += 1
                continue

        # Remove consent metadata
        filtered_data.pop("_consent", None)

        # Apply _elements filter
        if request.elements:
            filtered_data = filter_fields(filtered_data, request.elements)

        items.append(
            BulkExportItem(
                identifier=identifier,
                status="success",
                resource=filtered_data,
            )
        )
        successful += 1

    return BulkExportResponse(
        total=len(request.identifiers),
        successful=successful,
        failed=failed,
        items=items,
    )
