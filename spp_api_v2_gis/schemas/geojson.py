# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for GeoJSON responses."""

from pydantic import BaseModel, Field


class GeoJSONGeometry(BaseModel):
    """GeoJSON geometry."""

    type: str = Field(..., description="Geometry type")
    coordinates: list = Field(..., description="Coordinates array")


class GeoJSONFeatureProperties(BaseModel):
    """Properties for a GeoJSON feature."""

    # Flexible properties - subclass for specific feature types
    pass


class GeoJSONFeature(BaseModel):
    """GeoJSON Feature."""

    type: str = Field(default="Feature", description="GeoJSON type")
    properties: dict = Field(..., description="Feature properties")
    geometry: dict | None = Field(default=None, description="GeoJSON geometry")


class GeoJSONFeatureCollection(BaseModel):
    """GeoJSON FeatureCollection."""

    type: str = Field(default="FeatureCollection", description="GeoJSON type")
    features: list[GeoJSONFeature] = Field(..., description="List of features")
    metadata: dict | None = Field(default=None, description="Collection metadata")
    styling: dict | None = Field(default=None, description="Styling hints for QGIS")
