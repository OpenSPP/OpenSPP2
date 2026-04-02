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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [100.0, 0.0],
                            [101.0, 0.0],
                            [101.0, 1.0],
                            [100.0, 1.0],
                            [100.0, 0.0],
                        ]
                    ],
                },
            ],
        },
    )

    type: GeometryType = Field(..., description="Geometry type")
    coordinates: list = Field(..., description="Coordinates array")


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature (RFC 7946)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "Feature",
                    "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [100.0, 0.0],
                                [101.0, 0.0],
                                [101.0, 1.0],
                                [100.0, 1.0],
                                [100.0, 0.0],
                            ]
                        ],
                    },
                    "properties": {
                        "uuid": "d290f1ee-6c54-4b01-90e6-d701748f0851",
                        "name": "Flood Response Zone A",
                        "description": "Northern flood-affected area",
                        "geofence_type": "hazard_zone",
                        "geofence_type_label": "Hazard Zone",
                        "area_sqkm": 12345.67,
                        "tags": ["flood", "response-2024"],
                        "created_from": "api",
                        "created_by": "Admin User",
                        "create_date": "2024-06-15T10:30:00Z",
                    },
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/geofences/items/d290f1ee",
                            "rel": "self",
                            "type": "application/geo+json",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/geofences",
                            "rel": "collection",
                            "type": "application/json",
                        },
                    ],
                },
            ],
        },
    )

    type: Literal["Feature"] = Field(default="Feature", description="GeoJSON type")
    id: str | int | None = Field(default=None, description="Feature identifier")
    properties: dict = Field(..., description="Feature properties")
    geometry: GeoJSONGeometry | None = Field(default=None, description="GeoJSON geometry")
    links: list[OGCLink] | None = Field(default=None, description="OGC navigation links")


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection (OGC API - Features Part 1)."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "type": "FeatureCollection",
                    "numberMatched": 42,
                    "numberReturned": 10,
                    "features": [
                        {
                            "type": "Feature",
                            "id": "d290f1ee-6c54-4b01-90e6-d701748f0851",
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [
                                    [
                                        [100.0, 0.0],
                                        [101.0, 0.0],
                                        [101.0, 1.0],
                                        [100.0, 1.0],
                                        [100.0, 0.0],
                                    ]
                                ],
                            },
                            "properties": {
                                "name": "Flood Response Zone A",
                                "geofence_type": "hazard_zone",
                                "area_sqkm": 12345.67,
                            },
                        },
                    ],
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/geofences/items?limit=10&offset=0",
                            "rel": "self",
                            "type": "application/geo+json",
                            "title": "This page",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/geofences/items?limit=10&offset=10",
                            "rel": "next",
                            "type": "application/geo+json",
                            "title": "Next page",
                        },
                    ],
                },
            ],
        },
    )

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

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [100.0, 0.0],
                                [101.0, 0.0],
                                [101.0, 1.0],
                                [100.0, 1.0],
                                [100.0, 0.0],
                            ]
                        ],
                    },
                    "properties": {
                        "name": "Flood Response Zone A",
                        "geofence_type": "hazard_zone",
                        "description": "Northern flood-affected area",
                        "tags": ["flood", "response-2024"],
                    },
                },
            ],
        },
    )

    type: Literal["Feature"] = Field(default="Feature", description="Must be 'Feature'")
    geometry: GeoJSONGeometry = Field(..., description="Geofence geometry (required)")
    properties: GeofenceProperties = Field(..., description="Geofence properties")


class ReplaceGeofenceInput(BaseModel):
    """Request body for PUT /collections/geofences/items/{fid} (OGC Part 4)."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [102.0, 2.0],
                                [103.0, 2.0],
                                [103.0, 3.0],
                                [102.0, 3.0],
                                [102.0, 2.0],
                            ]
                        ],
                    },
                    "properties": {
                        "name": "Updated Response Zone",
                        "geofence_type": "service_area",
                        "description": "Expanded service coverage area",
                    },
                },
            ],
        },
    )

    type: Literal["Feature"] = Field(default="Feature", description="Must be 'Feature'")
    geometry: GeoJSONGeometry = Field(..., description="Geofence geometry (required)")
    properties: GeofenceProperties = Field(..., description="Geofence properties")
