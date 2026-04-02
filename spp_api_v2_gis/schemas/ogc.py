# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for OGC API - Features responses.

Implements the OGC API - Features Core standard (Part 1: Core)
for GovStack GIS Building Block compliance.
"""

from pydantic import BaseModel, ConfigDict, Field


class OGCLink(BaseModel):
    """OGC API link object."""

    href: str = Field(..., description="URL of the link target")
    rel: str = Field(..., description="Relation type (e.g., self, items, conformance)")
    type: str | None = Field(default=None, description="Media type of the target")
    title: str | None = Field(default=None, description="Human-readable title")


class LandingPage(BaseModel):
    """OGC API - Features landing page."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "OpenSPP GIS API",
                    "description": "OGC API - Features endpoints for OpenSPP geospatial data.",
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc",
                            "rel": "self",
                            "type": "application/json",
                            "title": "This document",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/conformance",
                            "rel": "conformance",
                            "type": "application/json",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/collections",
                            "rel": "data",
                            "type": "application/json",
                        },
                    ],
                },
            ],
        },
    )

    title: str = Field(..., description="API title")
    description: str = Field(..., description="API description")
    links: list[OGCLink] = Field(..., description="Navigation links")


class Conformance(BaseModel):
    """OGC API conformance declaration."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "conformsTo": [
                        "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
                        "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
                        "http://www.opengis.net/spec/ogcapi-processes-1/1.0/conf/core",
                        "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete",
                    ],
                },
            ],
        },
    )

    conformsTo: list[str] = Field(  # noqa: N815
        ..., description="List of conformance class URIs"
    )


class SpatialExtent(BaseModel):
    """Spatial extent with bounding box."""

    bbox: list[list[float]] = Field(..., description="Bounding box coordinates [[west, south, east, north]]")
    crs: str = Field(
        default="http://www.opengis.net/def/crs/OGC/1.3/CRS84",
        description="Coordinate reference system",
    )


class TemporalExtent(BaseModel):
    """Temporal extent with time interval."""

    interval: list[list[str | None]] = Field(..., description="Time interval [[start, end]]")


class Extent(BaseModel):
    """Collection extent (spatial and temporal)."""

    spatial: SpatialExtent | None = Field(default=None, description="Spatial extent")
    temporal: TemporalExtent | None = Field(default=None, description="Temporal extent")


class CollectionInfo(BaseModel):
    """OGC API collection metadata."""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "pop_density_adm2",
                    "title": "Population Density (District)",
                    "description": "Population density statistics per district",
                    "itemType": "feature",
                    "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
                    "extent": {
                        "spatial": {
                            "bbox": [[95.0, -11.0, 141.0, 6.0]],
                            "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                        },
                    },
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/pop_density_adm2",
                            "rel": "self",
                            "type": "application/json",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/pop_density_adm2/items",
                            "rel": "items",
                            "type": "application/geo+json",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/pop_density_adm2/qml",
                            "rel": "describedby",
                            "type": "text/xml",
                        },
                    ],
                },
                {
                    "id": "geofences",
                    "title": "Geofences",
                    "description": "User-defined geographic areas of interest",
                    "itemType": "feature",
                    "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
                    "storageCrs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/geofences",
                            "rel": "self",
                            "type": "application/json",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/geofences/items",
                            "rel": "items",
                            "type": "application/geo+json",
                        },
                    ],
                },
                {
                    "id": "layer_42",
                    "title": "Health Facilities",
                    "description": "Data layer from spp.gis.data.layer",
                    "itemType": "feature",
                    "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/layer_42",
                            "rel": "self",
                            "type": "application/json",
                        },
                        {
                            "href": "/api/v2/spp/gis/ogc/collections/layer_42/items",
                            "rel": "items",
                            "type": "application/geo+json",
                        },
                    ],
                },
            ],
        },
    )

    id: str = Field(..., description="Collection identifier")
    title: str = Field(..., description="Human-readable title")
    description: str | None = Field(default=None, description="Collection description")
    extent: Extent | None = Field(default=None, description="Spatial/temporal extent")
    itemType: str = Field(  # noqa: N815
        default="feature",
        description="Type of items in collection",
    )
    crs: list[str] = Field(
        default=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
        description="Supported CRS list",
    )
    storageCrs: str | None = Field(  # noqa: N815
        default=None,
        description="CRS used to store features in this collection",
    )
    links: list[OGCLink] = Field(default_factory=list, description="Navigation links")


class Collections(BaseModel):
    """OGC API collections list."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "links": [
                        {
                            "href": "/api/v2/spp/gis/ogc/collections",
                            "rel": "self",
                            "type": "application/json",
                        },
                    ],
                    "collections": [
                        {
                            "id": "pop_density_adm2",
                            "title": "Population Density (District)",
                            "itemType": "feature",
                            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
                            "links": [],
                        },
                        {
                            "id": "geofences",
                            "title": "Geofences",
                            "itemType": "feature",
                            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
                            "storageCrs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
                            "links": [],
                        },
                        {
                            "id": "layer_42",
                            "title": "Health Facilities",
                            "itemType": "feature",
                            "crs": ["http://www.opengis.net/def/crs/OGC/1.3/CRS84"],
                            "links": [],
                        },
                    ],
                },
            ],
        },
    )

    links: list[OGCLink] = Field(default_factory=list, description="Navigation links")
    collections: list[CollectionInfo] = Field(..., description="Available collections")
