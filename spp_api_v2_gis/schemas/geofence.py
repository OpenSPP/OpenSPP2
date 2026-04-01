# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for Geofence API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .query import _validate_geojson_geometry


class GeofenceCreateRequest(BaseModel):
    """Request to create a geofence."""

    name: str = Field(..., description="Name of the geofence")
    description: str | None = Field(default=None, description="Description of the geofence")
    geometry: dict = Field(..., description="Geometry as GeoJSON (Polygon or MultiPolygon)")
    geofence_type: Literal["hazard_zone", "service_area", "targeting_area", "custom"] = Field(
        default="custom", description="Type of geofence"
    )

    @field_validator("geometry")
    @classmethod
    def check_geometry(cls, v):
        return _validate_geojson_geometry(v)

    incident_code: str | None = Field(default=None, description="Related incident code")


class GeofenceResponse(BaseModel):
    """Response from geofence operations."""

    id: int = Field(..., description="Geofence database identifier")
    name: str = Field(..., description="Geofence name")
    description: str | None = Field(default=None, description="Geofence description")
    geofence_type: str = Field(..., description="Type of geofence")
    area_sqkm: float = Field(..., description="Area in square kilometers")
    active: bool = Field(..., description="Whether the geofence is active")
    created_from: str = Field(..., description="Source of creation")


class GeofenceListItem(BaseModel):
    """Geofence item in list response."""

    id: int = Field(..., description="Geofence database identifier")
    name: str = Field(..., description="Geofence name")
    geofence_type: str = Field(..., description="Type of geofence")
    area_sqkm: float = Field(..., description="Area in square kilometers")
    active: bool = Field(..., description="Whether the geofence is active")


class GeofenceListResponse(BaseModel):
    """Response from geofence list endpoint."""

    geofences: list[GeofenceListItem] = Field(..., description="List of geofences")
    total: int = Field(..., description="Total count of geofences")
    offset: int = Field(..., description="Offset used for pagination")
    count: int = Field(..., description="Number of items returned")
