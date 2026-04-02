# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for OGC API - Processes endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..schemas.ogc import OGCLink


class ProcessSummary(BaseModel):
    """Summary of a single process, used in process list responses."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Process identifier (e.g. 'spatial-statistics')")
    title: str = Field(..., description="Human-readable process title")
    description: str | None = Field(default=None, description="Process description")
    version: str = Field(default="1.0.0", description="Process version")
    jobControlOptions: list[str] = Field(  # noqa: N815
        ...,
        alias="jobControlOptions",
        description="Supported job control options (e.g. sync-execute, async-execute, dismiss)",
    )
    links: list[OGCLink] = Field(default_factory=list, description="Related links")


class ProcessDescription(BaseModel):
    """Full process description including input and output schemas."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Process identifier (e.g. 'spatial-statistics')")
    title: str = Field(..., description="Human-readable process title")
    description: str | None = Field(default=None, description="Process description")
    version: str = Field(default="1.0.0", description="Process version")
    jobControlOptions: list[str] = Field(  # noqa: N815
        ...,
        alias="jobControlOptions",
        description="Supported job control options (e.g. sync-execute, async-execute, dismiss)",
    )
    inputs: dict = Field(..., description="Input parameter definitions")
    outputs: dict = Field(..., description="Output schema definitions")
    links: list[OGCLink] = Field(default_factory=list, description="Related links")


class ProcessList(BaseModel):
    """List of available processes."""

    processes: list[ProcessSummary] = Field(..., description="Available processes")
    links: list[OGCLink] = Field(default_factory=list, description="Navigation links")


class ExecuteRequest(BaseModel):
    """Request body for POST /processes/{id}/execution."""

    inputs: dict = Field(..., description="Process input values")
    outputs: dict | None = Field(default=None, description="Requested output values")
    response: Literal["raw", "document"] | None = Field(
        default=None,
        description="Response type: raw or document",
    )


class StatusInfo(BaseModel):
    """OGC API job status information."""

    model_config = ConfigDict(populate_by_name=True)

    jobID: str = Field(..., alias="jobID", description="Unique job identifier")  # noqa: N815
    type: str = Field(default="process", description="Resource type")
    processID: str | None = Field(  # noqa: N815
        default=None,
        alias="processID",
        description="Identifier of the process that created this job",
    )
    status: str = Field(
        ...,
        description="Job status: accepted, running, successful, failed, or dismissed",
    )
    message: str | None = Field(default=None, description="Status message or error detail")
    created: str | None = Field(default=None, description="ISO 8601 creation datetime")
    started: str | None = Field(default=None, description="ISO 8601 start datetime")
    finished: str | None = Field(default=None, description="ISO 8601 finish datetime")
    updated: str | None = Field(default=None, description="ISO 8601 last updated datetime")
    progress: int | None = Field(default=None, description="Completion percentage (0-100)")
    links: list[OGCLink] = Field(default_factory=list, description="Related links")


class JobList(BaseModel):
    """List of jobs."""

    jobs: list[StatusInfo] = Field(..., description="Jobs")


class SingleStatisticsResult(BaseModel):
    """Result of a spatial statistics query for a single geometry."""

    total_count: int = Field(..., description="Total number of matched records")
    query_method: str = Field(..., description="Method used for the spatial query")
    areas_matched: int = Field(..., description="Number of geographic areas matched")
    statistics: dict = Field(..., description="Computed statistics by indicator")
    breakdown: dict | None = Field(default=None, description="Demographic breakdown by dimension")
    access_level: str | None = Field(default=None, description="Data access level applied")
    from_cache: bool = Field(default=False, description="Whether the result was served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")


class BatchResultItem(BaseModel):
    """Statistics result for a single geometry within a batch request."""

    id: str = Field(..., description="Geometry identifier from the request")
    total_count: int = Field(..., description="Total number of matched records")
    query_method: str = Field(..., description="Method used for the spatial query")
    areas_matched: int = Field(..., description="Number of geographic areas matched")
    statistics: dict = Field(..., description="Computed statistics by indicator")
    breakdown: dict | None = Field(default=None, description="Demographic breakdown by dimension")
    access_level: str | None = Field(default=None, description="Data access level applied")
    from_cache: bool = Field(default=False, description="Whether the result was served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")
    error: str | None = Field(default=None, description="Error message if this item failed")


class BatchSummary(BaseModel):
    """Aggregate summary across all geometries in a batch request."""

    total_count: int = Field(..., description="Total number of matched records across all geometries")
    geometries_queried: int = Field(..., description="Number of geometries successfully queried")
    geometries_failed: int = Field(default=0, description="Number of geometries that failed")
    statistics: dict = Field(..., description="Aggregated statistics across all geometries")
    breakdown: dict | None = Field(default=None, description="Demographic breakdown by dimension")
    access_level: str | None = Field(default=None, description="Data access level applied")
    from_cache: bool = Field(default=False, description="Whether all results were served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")


class BatchStatisticsResult(BaseModel):
    """Result of a spatial statistics query for multiple geometries."""

    results: list[BatchResultItem] = Field(..., description="Per-geometry results")
    summary: BatchSummary = Field(..., description="Aggregate summary across all geometries")


class ProximityResult(BaseModel):
    """Result of a proximity-based spatial statistics query."""

    total_count: int = Field(..., description="Total number of matched records")
    query_method: str = Field(..., description="Method used for the spatial query")
    areas_matched: int = Field(..., description="Number of geographic areas matched")
    reference_points_count: int = Field(..., description="Number of reference points used")
    radius_km: float = Field(..., description="Search radius in kilometres")
    relation: str = Field(..., description="Spatial relation used (e.g. within, intersects)")
    statistics: dict = Field(..., description="Computed statistics by indicator")
    breakdown: dict | None = Field(default=None, description="Demographic breakdown by dimension")
    access_level: str | None = Field(default=None, description="Data access level applied")
    from_cache: bool = Field(default=False, description="Whether the result was served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")
