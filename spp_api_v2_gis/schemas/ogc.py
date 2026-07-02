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

    title: str = Field(..., description="API title")
    description: str = Field(..., description="API description")
    links: list[OGCLink] = Field(..., description="Navigation links")


class Conformance(BaseModel):
    """OGC API conformance declaration."""

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

    model_config = ConfigDict(populate_by_name=True)

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
    links: list[OGCLink] = Field(default_factory=list, description="Navigation links")


class Collections(BaseModel):
    """OGC API collections list."""

    links: list[OGCLink] = Field(default_factory=list, description="Navigation links")
    collections: list[CollectionInfo] = Field(..., description="Available collections")
