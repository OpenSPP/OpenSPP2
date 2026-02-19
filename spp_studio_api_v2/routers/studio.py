# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Studio API endpoints for field and variable discovery."""

import logging
from typing import Annotated, Any

from pydantic import BaseModel, Field

from odoo.api import Environment
from odoo.osv import expression

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import get_authenticated_client

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

_logger = logging.getLogger(__name__)

studio_router = APIRouter(tags=["Studio"], prefix="/Studio")


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class StudioFieldInfo(BaseModel):
    """Information about a Studio custom field."""

    technicalName: str = Field(..., description="Odoo field name (x_*)")
    label: str = Field(..., description="Display label")
    fieldType: str = Field(..., description="Field type (text, integer, etc.)")
    targetType: str = Field(..., description="Target registry (individual/group)")
    helpText: str | None = Field(default=None, description="Help text")
    isRequired: bool = Field(default=False, description="Whether field is required")
    placementZone: str | None = Field(default=None, description="Form placement zone")
    apiExposed: bool = Field(default=True, description="Whether exposed via API")
    selectionOptions: list[dict] | None = Field(
        default=None,
        description="For selection/multi_select: [{'value': 'x', 'label': 'X'}]",
    )
    isReadonly: bool = Field(default=False, description="Whether field is read-only")
    isSearchable: bool = Field(default=False, description="Whether field is searchable")
    sequence: int = Field(default=10, description="Order within placement zone")
    visibilityField: str | None = Field(default=None, description="Field that controls visibility")
    visibilityOperator: str | None = Field(default=None, description="Comparison operator")
    visibilityValue: str | None = Field(default=None, description="Value to compare")
    linkModel: str | None = Field(default=None, description="For link fields: target model")
    linkDomain: str | None = Field(default=None, description="For link fields: domain filter")


class StudioFieldsResponse(BaseModel):
    """Response for Studio fields list endpoint."""

    total: int = Field(..., description="Total number of fields")
    items: list[StudioFieldInfo] = Field(..., description="List of fields")
    nextPageId: int | None = Field(default=None, description="ID of last item for cursor pagination")


class VariableInfo(BaseModel):
    """Information about a CEL variable."""

    name: str = Field(..., description="Variable accessor name")
    label: str | None = Field(default=None, description="Display label")
    description: str | None = Field(default=None, description="Variable description")
    valueType: str = Field(..., description="Value type (number, boolean, string, etc.)")
    sourceType: str = Field(..., description="Source type (field, computed, external, etc.)")
    appliesTo: str = Field(..., description="Context (individual, group, both)")
    periodGranularity: str | None = Field(default=None, description="Period granularity")
    supportsHistorical: bool = Field(default=False, description="Supports historical queries")
    unit: str | None = Field(default=None, description="Unit of measurement")
    category: str | None = Field(default=None, description="Variable category")


class VariablesResponse(BaseModel):
    """Response for variables list endpoint."""

    total: int = Field(..., description="Total number of variables")
    items: list[VariableInfo] = Field(..., description="List of variables")
    nextPageId: int | None = Field(default=None, description="ID of last item for cursor pagination")


class FieldSchema(BaseModel):
    """JSON Schema for a Studio field."""

    technicalName: str = Field(..., description="Technical field name")
    type: str = Field(..., description="JSON Schema type (string, number, boolean, object, array)")
    format: str | None = Field(default=None, description="JSON Schema format (date, date-time, reference)")
    minimum: float | None = Field(default=None, description="Minimum value for numeric fields")
    maximum: float | None = Field(default=None, description="Maximum value for numeric fields")
    maxLength: int | None = Field(default=None, description="Maximum length for string fields")
    enum: list[str] | None = Field(default=None, description="Allowed values for selection fields")
    enumDisplay: dict[str, str] | None = Field(
        default=None, description="Display labels for enum values {value: label}"
    )
    linkModel: str | None = Field(default=None, description="Target model for link fields")
    linkDomain: str | None = Field(default=None, description="Domain filter for link fields")
    description: str | None = Field(default=None, description="Field description")
    required: bool = Field(default=False, description="Whether field is required")
    # Visibility conditions for conditional display
    visibilityField: str | None = Field(default=None, description="Field that controls visibility")
    visibilityOperator: str | None = Field(default=None, description="Comparison operator (set, not_set, =, !=)")
    visibilityValue: str | None = Field(default=None, description="Value to compare")


class VariableValueDetail(BaseModel):
    """A single variable value with metadata."""

    value: Any = Field(..., description="The variable value")
    periodKey: str = Field(..., description="Period key")
    recordedAt: str | None = Field(default=None, description="When value was recorded")
    isStale: bool = Field(default=False, description="Whether value is stale")
    sourceType: str | None = Field(default=None, description="Source type")


class SubjectVariablesResponse(BaseModel):
    """Response for subject variables endpoint."""

    subjectId: str = Field(..., description="External identifier of subject")
    periodKey: str = Field(..., description="Period key queried")
    variables: dict[str, VariableValueDetail] = Field(..., description="Variable name to value mapping")


# ═══════════════════════════════════════════════════════════════════════════════
# FIELDS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@studio_router.get(
    "/fields",
    response_model=StudioFieldsResponse,
    summary="List Studio custom fields",
    description="List all active Studio custom fields with their configuration.",
)
async def list_studio_fields(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    target_type: Annotated[str | None, Query(description="Filter by target registry (individual/group)")] = None,
    api_exposed_only: Annotated[bool, Query(description="Only return API-exposed fields")] = True,
    _count: Annotated[int, Query(ge=1, le=500, alias="_count")] = 100,
    _last_id: Annotated[
        int | None,
        Query(alias="_lastId", description="ID of last record from previous page"),
    ] = None,
):
    """List Studio custom fields."""
    if not api_client.has_scope("studio", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'studio:read'. Request access from your administrator.",
        )

    # sudo() required: Studio field definitions are system config. Authorization
    # is done via API scope check above (studio:read), not Odoo ACLs.
    StudioField = env["spp.studio.field"].sudo()  # nosemgrep: odoo-sudo-without-context

    domain = [("state", "=", "active")]

    if target_type:
        domain.append(("target_type", "=", target_type))

    if api_exposed_only:
        domain.append(("api_exposed", "=", True))

    # Apply cursor-based pagination
    if _last_id is not None:
        domain = expression.AND([domain, [("id", ">", _last_id)]])

    total = StudioField.search_count(domain)
    fields = StudioField.search(domain, limit=_count, order="id")

    items = []
    for field in fields:
        # Parse selection options if present
        selection_opts = None
        if field.field_type in ("selection", "multi_select") and field.selection_options:
            selection_opts = []
            for line in field.selection_options.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "|" in line:
                    value, label = line.split("|", 1)
                    selection_opts.append({"value": value.strip(), "label": label.strip()})
                else:
                    # Use line as both value and label
                    selection_opts.append({"value": line, "label": line})

        # Get visibility field name if set
        visibility_field_name = None
        if field.visibility_condition == "conditional" and field.visibility_field_id:
            visibility_field_name = field.visibility_field_id.name

        # Get link model name if set
        link_model_name = None
        if field.field_type == "link" and field.link_model_id:
            link_model_name = field.link_model_id.model

        items.append(
            StudioFieldInfo(
                technicalName=field.technical_name,
                label=field.label,
                fieldType=field.field_type,
                targetType=field.target_type,
                helpText=field.help_text or None,
                isRequired=field.is_required,
                placementZone=field.placement_zone_id.code if field.placement_zone_id else None,
                apiExposed=field.api_exposed,
                selectionOptions=selection_opts,
                isReadonly=field.is_readonly,
                isSearchable=field.is_searchable,
                sequence=field.sequence,
                visibilityField=visibility_field_name,
                visibilityOperator=field.visibility_operator if field.visibility_condition == "conditional" else None,
                visibilityValue=field.visibility_value if field.visibility_condition == "conditional" else None,
                linkModel=link_model_name,
                linkDomain=field.link_domain if field.field_type == "link" else None,
            )
        )

    # Get the ID of the last item for cursor pagination
    next_page_id = fields[-1].id if fields else None
    return StudioFieldsResponse(total=total, items=items, nextPageId=next_page_id)


@studio_router.get(
    "/fields/{technical_name}/schema",
    response_model=FieldSchema,
    summary="Get JSON Schema for a Studio field",
    description="Get JSON Schema validation rules for a specific Studio field.",
)
async def get_field_schema(
    technical_name: Annotated[str, Path(description="Technical field name (e.g., x_farm_size)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
):
    """Get JSON Schema for a Studio field."""
    if not api_client.has_scope("studio", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'studio:read'. Request access from your administrator.",
        )

    # sudo() required: Studio field definitions are system config. Authorization
    # is done via API scope check above (studio:read), not Odoo ACLs.
    StudioField = env["spp.studio.field"].sudo()  # nosemgrep: odoo-sudo-without-context

    # Find the field by technical name
    field = StudioField.search(
        [("technical_name", "=", technical_name), ("state", "=", "active")],
        limit=1,
    )

    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Studio field '{technical_name}' not found or not active",
        )

    # Map field_type to JSON Schema type
    field_type_mapping = {
        "text": "string",
        "long_text": "string",
        "integer": "number",
        "decimal": "number",
        "date": "string",
        "datetime": "string",
        "boolean": "boolean",
        "selection": "string",
        "multi_select": "array",
        "link": "object",
    }

    json_type = field_type_mapping.get(field.field_type, "string")

    # Build the schema
    schema_data = {
        "technicalName": field.technical_name,
        "type": json_type,
        "description": field.help_text or field.label,
        "required": field.is_required,
    }

    # Add format for date/datetime/link fields
    if field.field_type == "date":
        schema_data["format"] = "date"
    elif field.field_type == "datetime":
        schema_data["format"] = "date-time"
    elif field.field_type == "link":
        schema_data["format"] = "reference"

    # Add constraints for numeric fields
    if field.field_type in ("integer", "decimal"):
        # Integer fields typically have minimum 0 unless otherwise specified
        # This is a reasonable default but could be configured in the future
        if field.field_type == "integer":
            schema_data["minimum"] = 0

    # Add maxLength for text fields
    if field.field_type == "text":
        # Standard char field max length in Odoo
        schema_data["maxLength"] = 255
    elif field.field_type == "long_text":
        # Text fields can be longer
        schema_data["maxLength"] = 65535

    # Add enum/enumDisplay for selection fields
    if field.field_type in ("selection", "multi_select") and field.selection_options:
        enum_values = []
        enum_display = {}

        for line in field.selection_options.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                value, label = line.split("|", 1)
                value = value.strip()
                label = label.strip()
                enum_values.append(value)
                enum_display[value] = label
            else:
                # Use line as both value and label
                enum_values.append(line)
                enum_display[line] = line

        schema_data["enum"] = enum_values
        schema_data["enumDisplay"] = enum_display

    # Add link model and domain for link fields
    if field.field_type == "link" and field.link_model_id:
        schema_data["linkModel"] = field.link_model_id.model
        schema_data["linkDomain"] = field.link_domain if field.link_domain else "[]"

    # Add visibility conditions
    if field.visibility_condition == "conditional" and field.visibility_field_id:
        schema_data["visibilityField"] = field.visibility_field_id.name
        schema_data["visibilityOperator"] = field.visibility_operator
        schema_data["visibilityValue"] = field.visibility_value

    return FieldSchema(**schema_data)


# ═══════════════════════════════════════════════════════════════════════════════
# VARIABLES ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@studio_router.get(
    "/variables",
    response_model=VariablesResponse,
    summary="List available variables",
    description="List all active CEL variables that can be used in expressions or queried.",
)
async def list_variables(
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    applies_to: Annotated[str | None, Query(description="Filter by context (individual/group/both)")] = None,
    source_type: Annotated[str | None, Query(description="Filter by source type")] = None,
    category: Annotated[str | None, Query(description="Filter by category name")] = None,
    _count: Annotated[int, Query(ge=1, le=500, alias="_count")] = 100,
    _last_id: Annotated[
        int | None,
        Query(alias="_lastId", description="ID of last record from previous page"),
    ] = None,
):
    """List available CEL variables."""
    if not api_client.has_scope("studio", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'studio:read'. Request access from your administrator.",
        )

    # sudo() required: Variable definitions are system config. Authorization
    # is done via API scope check above (studio:read), not Odoo ACLs.
    Variable = env["spp.cel.variable"].sudo()  # nosemgrep: odoo-sudo-without-context

    domain = [("state", "=", "active")]

    if applies_to and applies_to != "both":
        domain.append(("applies_to", "in", [applies_to, "both"]))

    if source_type:
        domain.append(("source_type", "=", source_type))

    if category:
        domain.append(("category_id.name", "ilike", category))

    # Apply cursor-based pagination
    if _last_id is not None:
        domain = expression.AND([domain, [("id", ">", _last_id)]])

    total = Variable.search_count(domain)
    variables = Variable.search(domain, limit=_count, order="id")

    items = []
    for var in variables:
        # Skip variables with missing required fields to avoid validation errors
        # All required fields must be non-empty strings
        cel_accessor = var.cel_accessor
        value_type = var.value_type
        source_type = var.source_type
        applies_to = var.applies_to

        if not cel_accessor or not value_type or not source_type or not applies_to:
            _logger.warning("Skipping variable ID %s with missing required fields", var.id)
            continue

        # Ensure string type for required fields (some may be False/None from Odoo)
        try:
            items.append(
                VariableInfo(
                    name=str(cel_accessor),
                    label=str(getattr(var, "label", None) or var.name or cel_accessor),
                    description=str(getattr(var, "description", None) or "")
                    if getattr(var, "description", None)
                    else None,
                    valueType=str(value_type),
                    sourceType=str(source_type),
                    appliesTo=str(applies_to),
                    periodGranularity=str(var.period_granularity) if var.period_granularity else "current",
                    supportsHistorical=bool(var.supports_historical),
                    unit=str(getattr(var, "unit", None)) if getattr(var, "unit", None) else None,
                    category=str(var.category_id.name) if var.category_id and var.category_id.name else None,
                )
            )
        except Exception as e:
            _logger.warning("Failed to serialize variable ID %s: %s", var.id, e)
            continue

    # Get the ID of the last item for cursor pagination
    next_page_id = variables[-1].id if variables else None
    return VariablesResponse(total=total, items=items, nextPageId=next_page_id)


@studio_router.get(
    "/variables/{resource_type}/{identifier}",
    response_model=SubjectVariablesResponse,
    summary="Get variable values for a subject",
    description="Get cached variable values for an Individual or Group.",
)
async def get_subject_variables(
    resource_type: Annotated[str, Path(description="Resource type (Individual/Group)")],
    identifier: Annotated[str, Path(description="External identifier (system|value)")],
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[object, Depends(get_authenticated_client)],
    variables: Annotated[str | None, Query(description="Comma-separated variable names, or * for all")] = "*",
    period_key: Annotated[str, Query(description="Period key (current, 2024-12, etc.)")] = "current",
):
    """Get variable values for a specific Individual or Group."""
    if not api_client.has_scope("studio", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing required scope 'studio:read'. Request access from your administrator.",
        )

    from ..services.variable_value_service import VariableValueService

    # Validate resource type
    if resource_type.lower() not in ("individual", "group"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="resource_type must be 'Individual' or 'Group'",
        )

    # Parse identifier
    if "|" not in identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid identifier format. Expected: {system}|{value}",
        )

    system, value = identifier.split("|", 1)

    # Find the subject
    # sudo() required: Registry ID lookup needs system access to resolve
    # the identifier to a partner. Authorization is via API scope checks.
    reg_id = (
        env["spp.registry.id"]  # nosemgrep: odoo-sudo-without-context
        .sudo()
        .search(
            [("namespace_uri", "=", system), ("value", "=", value)],
            limit=1,
        )
    )

    if not reg_id or not reg_id.partner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subject not found",
        )

    partner = reg_id.partner_id

    # Validate resource type matches
    is_group = partner.is_group
    if resource_type.lower() == "individual" and is_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifier refers to a Group, not an Individual",
        )
    if resource_type.lower() == "group" and not is_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identifier refers to an Individual, not a Group",
        )

    # Parse variable names
    var_names = None
    if variables and variables != "*":
        var_names = [v.strip() for v in variables.split(",") if v.strip()]

    # Get variable values
    service = VariableValueService(env)
    var_data = service.get_values_for_subject(partner.id, var_names, period_key)

    # Convert to response format
    variables_response = {}
    for var_name, var_info in var_data.items():
        variables_response[var_name] = VariableValueDetail(
            value=var_info["value"],
            periodKey=var_info["periodKey"],
            recordedAt=var_info.get("recordedAt"),
            isStale=var_info.get("isStale", False),
            sourceType=var_info.get("sourceType"),
        )

    return SubjectVariablesResponse(
        subjectId=identifier,
        periodKey=period_key,
        variables=variables_response,
    )
