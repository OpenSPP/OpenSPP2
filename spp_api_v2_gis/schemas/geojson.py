# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for GeoJSON responses and geofence input validation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .ogc import OGCLink

# RFC 7946 geometry types
GeometryType = Literal[
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
    "GeometryCollection",
]


class GeoJSONGeometry(BaseModel):
    """GeoJSON geometry (RFC 7946)."""

    type: GeometryType = Field(..., description="Geometry type")
    coordinates: list = Field(..., description="Coordinates array")


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature (RFC 7946)."""

    type: Literal["Feature"] = Field(default="Feature", description="GeoJSON type")
    id: str | int | None = Field(default=None, description="Feature identifier")
    properties: dict = Field(..., description="Feature properties")
    geometry: GeoJSONGeometry | None = Field(default=None, description="GeoJSON geometry")
    links: list[OGCLink] | None = Field(default=None, description="OGC navigation links")


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection (OGC API - Features Part 1)."""

    type: Literal["FeatureCollection"] = Field(default="FeatureCollection", description="GeoJSON type")
    features: list[GeoJSONFeature] = Field(..., description="List of features")
    timeStamp: str | None = Field(  # noqa: N815
        default=None, description="ISO 8601 timestamp of the response"
    )
    numberMatched: int | None = Field(  # noqa: N815
        default=None, description="Total number of features matching the query"
    )
    numberReturned: int | None = Field(  # noqa: N815
        default=None, description="Number of features in this response"
    )
    links: list[OGCLink] | None = Field(default=None, description="OGC navigation and pagination links")


# --- Geofence-specific models for POST/PUT input validation ---


class GeofenceProperties(BaseModel):
    """Typed properties for a geofence feature."""

    name: str = Field(..., description="Geofence name")
    description: str | None = Field(default=None, description="Geofence description")
    geofence_type: str | None = Field(default=None, description="Geofence type classification")
    tags: list[str] | None = Field(default=None, description="Tags for categorization")
    area_sqkm: float | None = Field(default=None, description="Area in square kilometres")


class CreateGeofenceInput(BaseModel):
    """Request body for POST /collections/geofences/items (OGC Part 4)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["Feature"] = Field(default="Feature", description="Must be 'Feature'")
    geometry: GeoJSONGeometry = Field(..., description="Geofence geometry (required)")
    properties: GeofenceProperties = Field(..., description="Geofence properties")


class ReplaceGeofenceInput(BaseModel):
    """Request body for PUT /collections/geofences/items/{fid} (OGC Part 4)."""

    model_config = ConfigDict(extra="ignore")

    type: Literal["Feature"] = Field(default="Feature", description="Must be 'Feature'")
    geometry: GeoJSONGeometry = Field(..., description="Geofence geometry (required)")
    properties: GeofenceProperties = Field(..., description="Geofence properties")
