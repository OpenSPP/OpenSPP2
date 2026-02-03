# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for filter endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class FilterMetadata(BaseModel):
    """Metadata about a single filter."""

    name: str = Field(..., description="Filter name used in API parameters")
    field_path: str = Field(..., description="Odoo field path")
    filter_type: str = Field(..., description="Filter type (exact, contains, range, etc.)")
    label: str = Field(..., description="Human-readable label")
    description: str = Field(default="", description="Detailed description")
    allowed_operators: list[str] = Field(
        default_factory=list,
        description="List of valid operators",
    )
    required: bool = Field(default=False, description="Whether filter is required")
    is_indexed: bool = Field(default=False, description="Whether field is indexed")
    max_values: int | None = Field(
        default=None,
        description="Max values for in/nin filters",
    )


class PresetMetadata(BaseModel):
    """Metadata about a filter preset."""

    name: str = Field(..., description="Preset name")
    description: str = Field(default="", description="Preset description")


class FilterMetadataResponse(BaseModel):
    """Response for filter metadata endpoint."""

    resource: str = Field(..., description="API resource name")
    allow_custom_filters: bool = Field(
        default=False,
        description="Whether custom filters are allowed",
    )
    max_filter_complexity: int = Field(
        default=10,
        description="Maximum filter conditions per request",
    )
    filters: list[FilterMetadata] = Field(
        default_factory=list,
        description="Available filters",
    )
    presets: list[PresetMetadata] = Field(
        default_factory=list,
        description="Available presets",
    )


class FilterCondition(BaseModel):
    """A single filter condition."""

    field: str = Field(..., description="Field name to filter on")
    operator: str = Field(
        default="eq",
        description="Filter operator (eq, ne, gt, gte, lt, lte, in, nin, like, ilike, null)",
    )
    value: Any = Field(..., description="Filter value")


class CompoundFilterCondition(BaseModel):
    """A compound filter condition with AND/OR logic."""

    logic: str = Field(..., description="Logic operator: AND or OR")
    conditions: list["FilterCondition | CompoundFilterCondition"] = Field(
        ...,
        description="Nested conditions",
    )


class SortField(BaseModel):
    """Sort specification for a field."""

    field: str = Field(..., description="Field name to sort by")
    direction: str = Field(
        default="asc",
        description="Sort direction: asc or desc",
    )


class PaginationSpec(BaseModel):
    """Pagination specification."""

    count: int = Field(default=20, ge=1, le=100, description="Page size")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class SearchRequest(BaseModel):
    """Request body for advanced search endpoint."""

    filters: list[FilterCondition | CompoundFilterCondition] | None = Field(
        default=None,
        description="Filter conditions",
    )
    filter_logic: str = Field(
        default="AND",
        description="Top-level filter logic: AND or OR",
    )
    preset: str | None = Field(
        default=None,
        description="Named preset to apply",
    )
    additional_filters: list[FilterCondition | CompoundFilterCondition] | None = Field(
        default=None,
        description="Additional filters to apply on top of preset",
    )
    sort: list[SortField] | None = Field(
        default=None,
        description="Sort specification",
    )
    pagination: PaginationSpec | None = Field(
        default=None,
        description="Pagination specification",
    )


# Allow recursive types
CompoundFilterCondition.model_rebuild()
