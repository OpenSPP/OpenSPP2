# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Data API endpoints for variable value management."""

import logging
from typing import Annotated

from odoo.api import Environment
from odoo.osv import expression

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..schemas.data import (
    DataInvalidateRequest,
    DataInvalidateResponse,
    DataPullResponse,
    DataPushError,
    DataPushRequest,
    DataPushResponse,
    DataValueOutput,
    VariableInfo,
    VariablesListResponse,
)

_logger = logging.getLogger(__name__)

data_router = APIRouter(tags=["Data"], prefix="/Data")


def _resolve_subject_id(env: Environment, external_id: str, provider=None) -> int | None:
    """
    Resolve external identifier to subject_id.

    Supports two formats:
    - Namespace URI format: "namespace_uri|value" (e.g., "urn:gov:edu:student|12345")
    - Simple ID: matched against provider's id_mapping_fields

    Args:
        env: Odoo environment
        external_id: External identifier
        provider: Optional provider record for ID mapping configuration

    Returns:
        Subject ID (res.partner.id) or None if not found
    """
    if not external_id:
        return None

    # Try namespace URI format first (standard spp_api_v2 format)
    # Format: {vocabulary_uri}#{code}|{value}
    # Example: urn:openspp:vocab:id-type#national_id|12345
    if "|" in external_id:
        parts = external_id.split("|", 1)
        if len(parts) == 2:
            system_uri, value = parts
            # Search by id_type_id.uri (full code URI) for consistency with spp_api_v2
            reg_id = (
                env["spp.registry.id"]
                .sudo()
                .search(
                    [
                        ("id_type_id.uri", "=", system_uri),
                        ("value", "=", value),
                    ],
                    limit=1,
                )
            )
            if reg_id and reg_id.partner_id:
                return reg_id.partner_id.id

    # Try provider's ID mapping fields
    if provider and provider.id_mapping_fields:
        mapping_fields = provider.get_id_mapping_field_list()
        Partner = env["res.partner"].sudo()

        for field_name in mapping_fields:
            if field_name in Partner._fields:
                partner = Partner.search([(field_name, "=", external_id)], limit=1)
                if partner:
                    return partner.id

    # Try common identifier fields as fallback
    Partner = env["res.partner"].sudo()
    for field_name in ["external_id", "ref"]:
        if field_name in Partner._fields:
            partner = Partner.search([(field_name, "=", external_id)], limit=1)
            if partner:
                return partner.id

    return None


def _get_external_id(env: Environment, partner_id: int) -> str | None:
    """Get primary external identifier for a partner."""
    Partner = env["res.partner"].sudo()
    partner = Partner.browse(partner_id)
    if not partner.exists():
        return None

    # Try registry IDs first
    # Use id_type_id.uri for full code URI (e.g., urn:openspp:vocab:id-type#national_id)
    if hasattr(partner, "reg_ids") and partner.reg_ids:
        reg_id = partner.reg_ids[0]
        if reg_id.id_type_id and reg_id.id_type_id.uri:
            return f"{reg_id.id_type_id.uri}|{reg_id.value}"

    # Fall back to external_id or ref
    if hasattr(partner, "external_id") and partner.external_id:
        return partner.external_id
    if partner.ref:
        return partner.ref

    return str(partner_id)


def _validate_provider_access(env: Environment, api_client, provider_code: str, variable_name: str = None):
    """
    Validate provider access for the API client.

    Args:
        env: Odoo environment
        api_client: Authenticated API client
        provider_code: Provider code to validate
        variable_name: Optional variable name to check

    Returns:
        Provider record

    Raises:
        HTTPException: If access is denied
    """
    # Check data scope
    if not api_client.has_scope("data", "write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have data:write scope",
        )

    # Find provider
    Provider = env["spp.data.provider"].sudo()
    provider = Provider.search([("code", "=", provider_code), ("active", "=", True)], limit=1)

    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider not found: {provider_code}",
        )

    # If variable specified, check it belongs to this provider
    if variable_name:
        Variable = env["spp.cel.variable"].sudo()
        variable = Variable.search(
            [
                ("cel_accessor", "=", variable_name),
                ("external_provider_id", "=", provider.id),
            ],
            limit=1,
        )
        if not variable:
            # Check if variable exists but belongs to different provider
            any_var = Variable.search([("cel_accessor", "=", variable_name)], limit=1)
            if any_var:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Variable '{variable_name}' does not belong to provider '{provider_code}'",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Variable not found: {variable_name}",
            )

    return provider


# ═══════════════════════════════════════════════════════════════════════════════
# PUSH ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@data_router.post(
    "/push",
    response_model=DataPushResponse,
    summary="Push variable values",
    description="Push variable values from an external system into the cache.",
)
async def push_values(
    request: DataPushRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Push variable values from external systems.

    External systems (e.g., education ministry, health ministry) use this
    endpoint to push computed or collected values into the OpenSPP cache.
    """
    provider = _validate_provider_access(env, api_client, request.provider_code)

    DataValue = env["spp.data.value"].sudo()
    errors: list[DataPushError] = []
    values_to_upsert = []

    for idx, val in enumerate(request.values):
        # Resolve subject
        subject_id = _resolve_subject_id(env, val.subject_external_id, provider)
        if not subject_id:
            errors.append(
                DataPushError(
                    index=idx,
                    subject_external_id=val.subject_external_id,
                    variable=val.variable,
                    error=f"Subject not found: {val.subject_external_id}",
                )
            )
            continue

        # Validate variable belongs to provider
        Variable = env["spp.cel.variable"].sudo()
        variable = Variable.search(
            [
                ("cel_accessor", "=", val.variable),
                ("external_provider_id", "=", provider.id),
            ],
            limit=1,
        )
        if not variable:
            errors.append(
                DataPushError(
                    index=idx,
                    subject_external_id=val.subject_external_id,
                    variable=val.variable,
                    error=f"Variable not found or not owned by provider: {val.variable}",
                )
            )
            continue

        values_to_upsert.append(
            {
                "variable_name": variable.cel_accessor,
                "subject_model": "res.partner",
                "subject_id": subject_id,
                "period_key": val.period_key or "current",
                "value_json": {"value": val.value},
                "value_type": variable.value_type or "number",
                "source_type": "external",
                "provider": provider.code,
                "as_of": val.as_of,
                "ttl_seconds": provider.default_ttl_seconds,
            }
        )

    # Bulk upsert
    result = {"inserted": 0, "updated": 0}
    if values_to_upsert:
        result = DataValue.upsert_values(values_to_upsert)

    return DataPushResponse(
        success=len(errors) == 0,
        processed=len(values_to_upsert),
        inserted=result.get("inserted", 0),
        updated=result.get("updated", 0),
        errors=errors,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PULL ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@data_router.get(
    "/pull",
    response_model=DataPullResponse,
    summary="Pull variable values",
    description="Pull cached variable values for subjects.",
)
async def pull_values(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    variable: Annotated[str, Query(description="Variable name to pull")],
    subject_external_ids: Annotated[str, Query(description="Comma-separated external IDs")],
    period_key: Annotated[str | None, Query(description="Period filter (default: current)")] = "current",
    _count: Annotated[int, Query(ge=1, le=1000, alias="_count")] = 100,
):
    """
    Pull cached variable values.

    Returns cached values for the specified variable and subjects.
    """
    # Check read scope
    if not api_client.has_scope("data", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have data:read scope",
        )

    # Parse subject IDs
    external_ids = [s.strip() for s in subject_external_ids.split(",") if s.strip()]
    if not external_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one subject_external_id is required",
        )

    # Resolve to internal IDs
    subject_id_map = {}  # internal_id -> external_id
    for ext_id in external_ids:
        internal_id = _resolve_subject_id(env, ext_id)
        if internal_id:
            subject_id_map[internal_id] = ext_id

    if not subject_id_map:
        return DataPullResponse(total=0, items=[])

    # Query cached values
    DataValue = env["spp.data.value"].sudo()
    domain = [
        ("variable_name", "=", variable),
        ("subject_id", "in", list(subject_id_map.keys())),
        ("period_key", "=", period_key or "current"),
    ]

    records = DataValue.search(domain, limit=_count)

    items = []
    for rec in records:
        ext_id = subject_id_map.get(rec.subject_id) or _get_external_id(env, rec.subject_id)
        value = rec.value_json.get("value") if isinstance(rec.value_json, dict) else rec.value_json
        items.append(
            DataValueOutput(
                variable=rec.variable_name,
                subject_external_id=ext_id,
                value=value,
                period_key=rec.period_key,
                recorded_at=rec.recorded_at,
                expires_at=rec.expires_at,
                is_stale=rec.is_stale,
                source_type=rec.source_type,
            )
        )

    return DataPullResponse(total=len(items), items=items)


# ═══════════════════════════════════════════════════════════════════════════════
# INVALIDATE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@data_router.post(
    "/invalidate",
    response_model=DataInvalidateResponse,
    summary="Invalidate cached values",
    description="Invalidate cached variable values.",
)
async def invalidate_values(
    request: DataInvalidateRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Invalidate cached variable values.

    Marks cached values as stale so they will be refreshed on next access.
    """
    provider = _validate_provider_access(env, api_client, request.provider_code, request.variable)

    # Resolve subject IDs if provided
    subject_ids = None
    if request.subject_external_ids:
        subject_ids = []
        for ext_id in request.subject_external_ids:
            internal_id = _resolve_subject_id(env, ext_id, provider)
            if internal_id:
                subject_ids.append(internal_id)

    # Invalidate
    DataValue = env["spp.data.value"].sudo()
    count = DataValue.invalidate(
        variable_name=request.variable,
        subject_ids=subject_ids,
        period_key=request.period_key,
    )

    return DataInvalidateResponse(success=True, invalidated=count)


# ═══════════════════════════════════════════════════════════════════════════════
# VARIABLES ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@data_router.get(
    "/variables",
    response_model=VariablesListResponse,
    summary="List available variables",
    description="List variables that can receive external data.",
)
async def list_variables(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
    provider_code: Annotated[str | None, Query(description="Filter by provider code")] = None,
    source_type: Annotated[str | None, Query(description="Filter by source type (external, computed, etc.)")] = None,
    _count: Annotated[int, Query(ge=1, le=500, alias="_count")] = 100,
    _last_id: Annotated[int | None, Query(alias="_lastId", description="ID of last record from previous page")] = None,
):
    """
    List variables available for data push/pull.

    Returns variables configured for external data sources.
    """
    # Check read scope
    if not api_client.has_scope("data", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Client does not have data:read scope",
        )

    Variable = env["spp.cel.variable"].sudo()
    domain = [("active", "=", True)]

    if provider_code:
        Provider = env["spp.data.provider"].sudo()
        provider = Provider.search([("code", "=", provider_code)], limit=1)
        if provider:
            domain.append(("external_provider_id", "=", provider.id))
        else:
            return VariablesListResponse(total=0, items=[])

    if source_type:
        domain.append(("source_type", "=", source_type))

    # Apply cursor-based pagination
    if _last_id is not None:
        domain = expression.AND([domain, [("id", ">", _last_id)]])

    total = Variable.search_count(domain)
    variables = Variable.search(domain, limit=_count, order="id")

    items = [
        VariableInfo(
            name=v.name,
            cel_accessor=v.cel_accessor,
            description=v.description or None,
            value_type=v.value_type or "number",
            source_type=v.source_type or "computed",
            cache_strategy=v.cache_strategy or "none",
            period_granularity=v.period_granularity or None,
            provider_code=v.external_provider_id.code if v.external_provider_id else None,
        )
        for v in variables
    ]

    return VariablesListResponse(total=total, items=items)
