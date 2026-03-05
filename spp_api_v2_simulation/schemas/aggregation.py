# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for Aggregation API."""

from pydantic import BaseModel, Field


class AggregationScopeRequest(BaseModel):
    """Inline scope definition for aggregation queries."""

    target_type: str = Field(
        default="group",
        description="Target type: 'group' or 'individual'",
    )
    cel_expression: str | None = Field(
        default=None,
        description="CEL expression to filter the target population",
    )
    area_id: int | None = Field(
        default=None,
        description="Area ID to restrict scope geographically",
    )


class ComputeAggregationRequest(BaseModel):
    """Request body for POST /aggregation/compute."""

    scope: AggregationScopeRequest = Field(
        ...,
        description="Scope definition for the aggregation query",
    )
    statistics: list[str] | None = Field(
        default=None,
        description="List of statistic names to compute (None for defaults)",
    )
    group_by: list[str] | None = Field(
        default=None,
        description="List of dimension names for breakdown (max 3)",
    )


class AggregationResponse(BaseModel):
    """Response from POST /aggregation/compute."""

    total_count: int = Field(..., description="Total registrants matching the scope")
    statistics: dict = Field(
        default_factory=dict,
        description="Computed statistics keyed by name",
    )
    breakdown: dict | None = Field(
        default=None,
        description="Breakdown by group_by dimensions (if requested)",
    )
    from_cache: bool = Field(..., description="Whether result was served from cache")
    computed_at: str = Field(..., description="ISO 8601 timestamp of computation")
    access_level: str = Field(..., description="Access level: 'aggregate' or 'individual'")


class DimensionInfo(BaseModel):
    """Information about a demographic dimension."""

    name: str = Field(..., description="Technical name of the dimension")
    label: str = Field(..., description="Human-readable label")
    description: str | None = Field(default=None, description="Dimension description")
    dimension_type: str = Field(..., description="Type: 'field' or 'expression'")
    applies_to: str = Field(..., description="Applies to: 'all', 'individuals', or 'groups'")
    value_labels: dict | None = Field(
        default=None,
        description="Mapping of raw values to display labels",
    )


class DimensionsListResponse(BaseModel):
    """Response from GET /aggregation/dimensions."""

    dimensions: list[DimensionInfo] = Field(
        ...,
        description="Active demographic dimensions available for group_by",
    )
