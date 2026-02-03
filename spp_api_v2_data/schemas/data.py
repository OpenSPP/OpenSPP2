# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for Data API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════════
# PUSH ENDPOINT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class DataValueInput(BaseModel):
    """Single value to push into the cache."""

    variable: str = Field(
        ...,
        description="Variable name (cel_accessor)",
        examples=["school_attendance", "vaccination_status"],
    )
    subject_external_id: str = Field(
        ...,
        description="External identifier for the subject",
        examples=["EDU-2024-001", "urn:gov:edu:student:12345"],
    )
    value: Any = Field(
        ...,
        description="The value to store (number, string, boolean, or object)",
    )
    period_key: str | None = Field(
        default="current",
        description="Period identifier (current, 2024-12, 2024-Q4, etc.)",
    )
    as_of: datetime | None = Field(
        default=None,
        description="Point-in-time this value represents",
    )
    metadata: dict | None = Field(
        default=None,
        description="Optional metadata about the value",
    )


class DataPushRequest(BaseModel):
    """Request body for pushing variable values."""

    provider_code: str = Field(
        ...,
        description="Provider code for authentication and access control",
        examples=["education_ministry", "health_api"],
    )
    values: list[DataValueInput] = Field(
        ...,
        description="List of values to push",
        min_length=1,
        max_length=10000,
    )


class DataPushError(BaseModel):
    """Error detail for a single value."""

    index: int = Field(..., description="Index in the input values array")
    subject_external_id: str | None = Field(default=None, description="External ID that failed")
    variable: str | None = Field(default=None, description="Variable name")
    error: str = Field(..., description="Error message")


class DataPushResponse(BaseModel):
    """Response from push endpoint."""

    success: bool = Field(..., description="Whether the operation was successful")
    processed: int = Field(..., description="Number of values processed")
    inserted: int = Field(default=0, description="Number of new values inserted")
    updated: int = Field(default=0, description="Number of existing values updated")
    errors: list[DataPushError] = Field(default_factory=list, description="List of errors if any")


# ═══════════════════════════════════════════════════════════════════════════════
# PULL ENDPOINT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class DataValueOutput(BaseModel):
    """Single value from the cache."""

    variable: str = Field(..., description="Variable name")
    subject_external_id: str = Field(..., description="External identifier")
    value: Any = Field(..., description="The cached value")
    period_key: str = Field(..., description="Period identifier")
    recorded_at: datetime = Field(..., description="When the value was recorded")
    expires_at: datetime | None = Field(default=None, description="When the value expires")
    is_stale: bool = Field(default=False, description="Whether the value is stale")
    source_type: str | None = Field(default=None, description="Source type (computed, external, etc.)")


class DataPullResponse(BaseModel):
    """Response from pull endpoint."""

    total: int = Field(..., description="Total number of values found")
    items: list[DataValueOutput] = Field(..., description="List of cached values")


# ═══════════════════════════════════════════════════════════════════════════════
# INVALIDATE ENDPOINT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class DataInvalidateRequest(BaseModel):
    """Request body for invalidating cached values."""

    provider_code: str = Field(
        ...,
        description="Provider code for authentication",
    )
    variable: str = Field(
        ...,
        description="Variable name to invalidate",
    )
    subject_external_ids: list[str] | None = Field(
        default=None,
        description="External IDs to invalidate (None = all subjects)",
    )
    period_key: str | None = Field(
        default=None,
        description="Period to invalidate (None = all periods)",
    )


class DataInvalidateResponse(BaseModel):
    """Response from invalidate endpoint."""

    success: bool = Field(..., description="Whether the operation was successful")
    invalidated: int = Field(..., description="Number of values invalidated")


# ═══════════════════════════════════════════════════════════════════════════════
# VARIABLES ENDPOINT SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class VariableInfo(BaseModel):
    """Information about a variable."""

    name: str = Field(..., description="Variable name")
    cel_accessor: str = Field(..., description="CEL accessor name")
    description: str | None = Field(default=None, description="Variable description")
    value_type: str = Field(..., description="Value type (number, string, boolean)")
    source_type: str = Field(..., description="Source type (field, computed, external, etc.)")
    cache_strategy: str = Field(..., description="Cache strategy (none, session, ttl, manual)")
    period_granularity: str | None = Field(default=None, description="Period granularity")
    provider_code: str | None = Field(default=None, description="External provider code if applicable")


class VariablesListResponse(BaseModel):
    """Response from variables list endpoint."""

    total: int = Field(..., description="Total number of variables")
    items: list[VariableInfo] = Field(..., description="List of variables")
