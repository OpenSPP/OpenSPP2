# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for spatial query API."""

from typing import Literal

from pydantic import BaseModel, Field


class SpatialQueryRequest(BaseModel):
    """Request for spatial query."""

    geometry: dict = Field(..., description="Query geometry as GeoJSON (Polygon or MultiPolygon)")
    filters: dict | None = Field(default=None, description="Additional filters for registrants")
    variables: list[str] | None = Field(
        default=None,
        description="List of statistic names to compute (defaults to GIS-published statistics)",
    )


class SpatialQueryResponse(BaseModel):
    """Response from spatial query."""

    total_count: int = Field(..., description="Total number of registrants in query area")
    query_method: str = Field(
        ...,
        description="Method used for query (coordinates, area_fallback)",
    )
    areas_matched: int = Field(..., description="Number of areas intersecting query polygon")
    statistics: dict = Field(..., description="Computed aggregate statistics")
    access_level: str | None = Field(
        default=None,
        description="Access level applied to statistics (aggregate or individual)",
    )
    from_cache: bool = Field(
        default=False,
        description="Whether statistics were served from cache",
    )
    computed_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when statistics were computed",
    )


# === Batch Query Schemas ===


class GeometryItem(BaseModel):
    """A single geometry with an identifier for batch queries."""

    id: str = Field(..., description="Unique identifier for this geometry (e.g., feature ID)")
    geometry: dict = Field(..., description="GeoJSON geometry (Polygon or MultiPolygon)")


class BatchSpatialQueryRequest(BaseModel):
    """Request for batch spatial query across multiple geometries."""

    geometries: list[GeometryItem] = Field(
        ...,
        min_length=1,
        description="List of geometries to query, each with a unique ID",
    )
    filters: dict | None = Field(default=None, description="Additional filters for registrants")
    variables: list[str] | None = Field(
        default=None,
        description="List of statistic names to compute (defaults to GIS-published statistics)",
    )


class BatchResultItem(BaseModel):
    """Result for a single geometry in a batch query."""

    id: str = Field(..., description="Geometry identifier matching the request")
    total_count: int = Field(..., description="Total number of registrants in this geometry")
    query_method: str = Field(
        ...,
        description="Method used for query (coordinates, area_fallback)",
    )
    areas_matched: int = Field(..., description="Number of areas intersecting this geometry")
    statistics: dict = Field(..., description="Statistics computed for this geometry")
    access_level: str | None = Field(
        default=None,
        description="Access level applied to statistics (aggregate or individual)",
    )
    from_cache: bool = Field(
        default=False,
        description="Whether statistics were served from cache",
    )
    computed_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when statistics were computed",
    )


class BatchSummary(BaseModel):
    """Aggregated summary across all geometries in a batch query."""

    total_count: int = Field(..., description="Combined total registrants across all geometries")
    geometries_queried: int = Field(..., description="Number of geometries in the batch")
    statistics: dict = Field(..., description="Combined statistics across all geometries")
    access_level: str | None = Field(
        default=None,
        description="Access level applied to statistics (aggregate or individual)",
    )
    from_cache: bool = Field(
        default=False,
        description="Whether statistics were served from cache",
    )
    computed_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when statistics were computed",
    )


class BatchSpatialQueryResponse(BaseModel):
    """Response from batch spatial query."""

    results: list[BatchResultItem] = Field(..., description="Per-geometry results")
    summary: BatchSummary = Field(..., description="Aggregated summary across all geometries")


# === Proximity Query Schemas ===


class ReferencePoint(BaseModel):
    """A geographic reference point for proximity queries."""

    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")


class ProximityQueryRequest(BaseModel):
    """Request for proximity-based spatial query.

    Finds registrants within or beyond a given radius from a set of
    reference points (e.g., health centers, schools). The server
    pre-buffers the reference points and uses ST_Intersects against
    indexed registrant coordinates for efficient queries even with
    thousands of reference points.
    """

    reference_points: list[ReferencePoint] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Reference locations (e.g., health centers) as lon/lat points",
    )
    radius_km: float = Field(
        ...,
        gt=0,
        le=500,
        description="Search radius in kilometers",
    )
    relation: Literal["within", "beyond"] = Field(
        default="within",
        description="'within' returns registrants inside the radius; "
        "'beyond' returns those outside the radius of all reference points",
    )
    filters: dict | None = Field(default=None, description="Additional filters for registrants")
    variables: list[str] | None = Field(
        default=None,
        description="List of statistic names to compute (defaults to GIS-published statistics)",
    )


class ProximityQueryResponse(BaseModel):
    """Response from proximity-based spatial query."""

    total_count: int = Field(..., description="Number of registrants matching the proximity criteria")
    query_method: str = Field(
        ...,
        description="Method used for query (coordinates, area_fallback)",
    )
    areas_matched: int = Field(
        ...,
        description="Number of areas matched (0 for coordinate-based queries)",
    )
    reference_points_count: int = Field(
        ...,
        description="Number of reference points used in the query",
    )
    radius_km: float = Field(..., description="Radius used for the query (km)")
    relation: str = Field(..., description="Relation used: 'within' or 'beyond'")
    statistics: dict = Field(..., description="Computed aggregate statistics")
    access_level: str | None = Field(
        default=None,
        description="Access level applied to statistics (aggregate or individual)",
    )
    from_cache: bool = Field(
        default=False,
        description="Whether statistics were served from cache",
    )
    computed_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when statistics were computed",
    )
