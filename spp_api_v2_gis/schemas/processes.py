# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for OGC API - Processes endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .geojson import GeoJSONGeometry
from .ogc import OGCLink


class ProcessSummary(BaseModel):
    """Summary of a single process, used in process list responses."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "spatial-statistics",
                    "title": "Spatial Statistics",
                    "description": "Compute aggregate registrant statistics within arbitrary polygons.",
                    "version": "1.0.0",
                    "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
                    "links": [],
                },
            ],
        },
    )

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

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "proximity-statistics",
                    "title": "Proximity Statistics",
                    "description": "Compute statistics within a radius from reference points.",
                    "version": "1.0.0",
                    "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
                    "inputs": {
                        "reference_points": {
                            "title": "Reference Points",
                            "description": "Locations to measure proximity from.",
                            "minOccurs": 1,
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "longitude": {"type": "number"},
                                    "latitude": {"type": "number"},
                                },
                                "required": ["longitude", "latitude"],
                            },
                        },
                        "radius_km": {
                            "title": "Search Radius",
                            "schema": {"type": "number", "maximum": 500},
                        },
                    },
                    "outputs": {
                        "result": {
                            "title": "Proximity Statistics Result",
                            "schema": {"type": "object"},
                        },
                    },
                    "links": [],
                },
            ],
        },
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "processes": [
                        {
                            "id": "spatial-statistics",
                            "title": "Spatial Statistics",
                            "version": "1.0.0",
                            "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
                        },
                        {
                            "id": "proximity-statistics",
                            "title": "Proximity Statistics",
                            "version": "1.0.0",
                            "jobControlOptions": ["sync-execute", "async-execute", "dismiss"],
                        },
                    ],
                    "links": [],
                },
            ],
        },
    )

    processes: list[ProcessSummary] = Field(..., description="Available processes")
    links: list[OGCLink] = Field(default_factory=list, description="Navigation links")


class BatchGeometryItem(BaseModel):
    """A single geometry with an identifier for batch spatial-statistics queries."""

    id: str = Field(..., description="Unique identifier for this geometry (e.g., feature ID)")
    value: GeoJSONGeometry = Field(..., description="GeoJSON geometry (Polygon or MultiPolygon)")


class SpatialStatisticsInputs(BaseModel):
    """Inputs for the spatial-statistics process."""

    geometry: GeoJSONGeometry | list[BatchGeometryItem] = Field(
        ...,
        description=(
            "Query geometry as a single GeoJSON object or a list of "
            "{id, value} objects for batch processing."
        ),
    )
    filters: dict | None = Field(
        default=None,
        description="Additional filters for registrants (e.g. {'is_group': true})",
    )
    variables: list[str] | None = Field(
        default=None,
        description="List of statistic names to compute (defaults to GIS-published statistics)",
    )
    group_by: list[str] | None = Field(
        default=None,
        description="List of dimension names for demographic breakdown (e.g. ['gender'])",
    )
    population_filter: dict | None = Field(
        default=None,
        description=(
            "Filter registrants by program membership or CEL expression. "
            "Example: {'program': 'HCP', 'mode': 'and'}"
        ),
    )


class ProximityStatisticsInputs(BaseModel):
    """Inputs for the proximity-statistics process."""

    reference_points: list[dict] = Field(
        ...,
        description="Reference locations as lon/lat points: [{'longitude': 100.5, 'latitude': 0.5}]",
    )
    radius_km: float = Field(
        ...,
        gt=0,
        le=500,
        description="Search radius in kilometres",
    )
    relation: Literal["within", "beyond"] = Field(
        default="within",
        description="'within' returns registrants inside the radius; 'beyond' returns those outside",
    )
    filters: dict | None = Field(default=None, description="Additional filters for registrants")
    variables: list[str] | None = Field(default=None, description="List of statistic names to compute")
    group_by: list[str] | None = Field(default=None, description="Demographic breakdown dimensions")
    population_filter: dict | None = Field(default=None, description="Population program/CEL filter")


class ExecuteRequest(BaseModel):
    """Request body for POST /processes/{id}/execution."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "inputs": {
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[100.0, 0.0], [101.0, 0.0], [101.0, 1.0], [100.0, 1.0], [100.0, 0.0]]],
                        },
                        "variables": ["total_households", "total_individuals"],
                    },
                },
                {
                    "inputs": {
                        "geometry": [
                            {
                                "id": "zone_1",
                                "value": {
                                    "type": "Polygon",
                                    "coordinates": [
                                        [[100.0, 0.0], [101.0, 0.0], [101.0, 1.0], [100.0, 1.0], [100.0, 0.0]]
                                    ],
                                },
                            },
                        ],
                    },
                },
                {
                    "inputs": {
                        "reference_points": [{"longitude": 100.5, "latitude": 0.5}],
                        "radius_km": 10.0,
                    },
                },
            ],
        },
    )

    inputs: dict = Field(
        ...,
        description="Process input values. Structure depends on the process being executed.",
    )
    outputs: dict | None = Field(default=None, description="Requested output values")
    response: Literal["raw", "document"] | None = Field(
        default=None,
        description="Response type: raw or document",
    )


class StatusInfo(BaseModel):
    """OGC API job status information."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "jobID": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "type": "process",
                    "processID": "spatial-statistics",
                    "status": "successful",
                    "created": "2024-06-15T10:30:00Z",
                    "started": "2024-06-15T10:30:01Z",
                    "finished": "2024-06-15T10:30:05Z",
                    "progress": 100,
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc/jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "rel": "self",
                            "type": "application/json",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/results",
                            "rel": "results",
                            "type": "application/json",
                        },
                    ],
                },
            ],
        },
    )

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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total_count": 1250,
                    "query_method": "coordinates",
                    "areas_matched": 3,
                    "statistics": {
                        "total_households": {"value": 312, "suppressed": False},
                        "total_individuals": {"value": 1250, "suppressed": False},
                    },
                    "breakdown": {
                        "1": {"count": 620, "labels": {"gender": {"value": "1", "display": "Male"}}},
                        "2": {"count": 630, "labels": {"gender": {"value": "2", "display": "Female"}}},
                    },
                    "access_level": "aggregate",
                    "from_cache": False,
                    "computed_at": "2024-06-15T10:30:05Z",
                },
            ],
        },
    )

    total_count: int = Field(..., description="Total number of matched records")
    query_method: str = Field(..., description="Method used for the spatial query (coordinates or area_fallback)")
    areas_matched: int = Field(..., description="Number of geographic areas matched (0 if using coordinates)")
    statistics: dict = Field(
        ...,
        description=(
            "Computed statistics by indicator name. Each value is an object "
            "with 'value' and 'suppressed' boolean."
        ),
    )
    breakdown: dict | None = Field(
        default=None,
        description=(
            "Demographic breakdown by dimension combinations (e.g. gender, age). "
            "Map from cell ID to object with 'count' and 'labels'."
        ),
    )
    access_level: str | None = Field(default=None, description="Data access level applied (aggregate/individual)")
    from_cache: bool = Field(default=False, description="Whether the result was served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")


class BatchResultItem(BaseModel):
    """Statistics result for a single geometry within a batch request."""

    id: str = Field(..., description="Geometry identifier from the request")
    total_count: int = Field(..., description="Total number of matched records")
    query_method: str = Field(..., description="Method used for the spatial query (coordinates or area_fallback)")
    areas_matched: int = Field(..., description="Number of geographic areas matched (0 if using coordinates)")
    statistics: dict = Field(
        ...,
        description=(
            "Computed statistics for this geometry. Map of indicator name to "
            "object with 'value' and 'suppressed' boolean."
        ),
    )
    breakdown: dict | None = Field(default=None, description="Demographic breakdown by dimension")
    access_level: str | None = Field(default=None, description="Data access level applied (aggregate/individual)")
    from_cache: bool = Field(default=False, description="Whether this result was served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")
    error: str | None = Field(default=None, description="Error message if this item failed")


class BatchSummary(BaseModel):
    """Aggregate summary across all geometries in a batch request."""

    total_count: int = Field(..., description="Total number of unique matched records across all geometries")
    geometries_queried: int = Field(..., description="Number of geometries successfully queried")
    geometries_failed: int = Field(default=0, description="Number of geometries that failed")
    statistics: dict = Field(
        ...,
        description="Aggregated statistics (deduplicated) across all geometries.",
    )
    breakdown: dict | None = Field(default=None, description="Aggregated demographic breakdown")
    access_level: str | None = Field(default=None, description="Data access level applied")
    from_cache: bool = Field(default=False, description="Whether all results were served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")


class BatchStatisticsResult(BaseModel):
    """Result of a spatial statistics query for multiple geometries."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "results": [
                        {
                            "id": "zone_1",
                            "total_count": 800,
                            "query_method": "coordinates",
                            "areas_matched": 2,
                            "statistics": {"total_individuals": {"value": 800, "suppressed": False}},
                            "access_level": "aggregate",
                            "from_cache": False,
                            "computed_at": "2024-06-15T10:30:05Z",
                        },
                        {
                            "id": "zone_2",
                            "total_count": 450,
                            "query_method": "area_fallback",
                            "areas_matched": 1,
                            "statistics": {"total_individuals": {"value": 450, "suppressed": False}},
                            "access_level": "aggregate",
                            "from_cache": False,
                            "computed_at": "2024-06-15T10:30:06Z",
                        },
                    ],
                    "summary": {
                        "total_count": 1250,
                        "geometries_queried": 2,
                        "geometries_failed": 0,
                        "statistics": {"total_individuals": {"value": 1250, "suppressed": False}},
                        "access_level": "aggregate",
                        "from_cache": False,
                        "computed_at": "2024-06-15T10:30:06Z",
                    },
                },
            ],
        },
    )

    results: list[BatchResultItem] = Field(..., description="Per-geometry results")
    summary: BatchSummary = Field(..., description="Aggregate summary across all geometries")


class ProximityResult(BaseModel):
    """Result of a proximity-based spatial statistics query."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "total_count": 340,
                    "query_method": "coordinates",
                    "areas_matched": 0,
                    "reference_points_count": 5,
                    "radius_km": 50.0,
                    "relation": "within",
                    "statistics": {
                        "total_households": {"value": 85, "suppressed": False},
                        "total_individuals": {"value": 340, "suppressed": False},
                    },
                    "access_level": "aggregate",
                    "from_cache": False,
                    "computed_at": "2024-06-15T10:30:05Z",
                },
            ],
        },
    )

    total_count: int = Field(..., description="Total number of matched records")
    query_method: str = Field(..., description="Method used for the spatial query (coordinates or area_fallback)")
    areas_matched: int = Field(..., description="Number of geographic areas matched (0 if using coordinates)")
    reference_points_count: int = Field(..., description="Number of reference points used")
    radius_km: float = Field(..., description="Search radius in kilometres")
    relation: str = Field(..., description="Spatial relation used (within, beyond)")
    statistics: dict = Field(
        ...,
        description="Computed statistics by indicator. Map of indicator name to object with 'value' and 'suppressed' flag.",
    )
    breakdown: dict | None = Field(default=None, description="Demographic breakdown by dimension")
    access_level: str | None = Field(default=None, description="Data access level applied")
    from_cache: bool = Field(default=False, description="Whether the result was served from cache")
    computed_at: str | None = Field(default=None, description="ISO 8601 datetime of computation")


BatchGeometryItem.model_rebuild()
SpatialStatisticsInputs.model_rebuild()
ProximityStatisticsInputs.model_rebuild()
ExecuteRequest.model_rebuild()
StatusInfo.model_rebuild()
BatchResultItem.model_rebuild()
BatchSummary.model_rebuild()
BatchStatisticsResult.model_rebuild()
ProximityResult.model_rebuild()

