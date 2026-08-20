# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for incident input validation (OGC Features Part 4)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .geojson import GeoJSONGeometry


class IncidentProperties(BaseModel):
    """CAP-aligned properties for incident creation/update."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "event": "Flood",
                    "headline": "Major Flooding in Region A",
                    "severity": "extreme",
                    "urgency": "immediate",
                    "certainty": "observed",
                    "effective": "2026-04-01T00:00:00Z",
                    "expires": "2026-04-15T00:00:00Z",
                    "source": "INAM Mozambique",
                    "source_alert_id": "MOZ-FLOOD-2026-042",
                    "cap_msg_type": "alert",
                },
            ],
        },
    )

    event: str = Field(..., description="Event type (e.g., 'Flood', 'Typhoon')")
    headline: str = Field(..., description="Alert headline (maps to incident name)")
    severity: str | None = Field(default=None, description="CAP severity vocabulary code")
    urgency: str | None = Field(default=None, description="CAP urgency vocabulary code")
    certainty: str | None = Field(default=None, description="CAP certainty vocabulary code")
    effective: str | None = Field(default=None, description="ISO 8601 datetime when alert becomes active")
    expires: str | None = Field(default=None, description="ISO 8601 datetime when alert expires")
    source: str | None = Field(default=None, description="Organization that issued the alert")
    source_alert_id: str | None = Field(default=None, description="External alert reference ID from the EWS")
    cap_msg_type: str | None = Field(default="alert", description="CAP message type: alert, update, cancel")


class CreateIncidentInput(BaseModel):
    """Request body for POST /collections/incidents/items."""

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
                                [34.0, -15.0],
                                [36.0, -15.0],
                                [36.0, -13.0],
                                [34.0, -13.0],
                                [34.0, -15.0],
                            ]
                        ],
                    },
                    "properties": {
                        "event": "Flood",
                        "headline": "Severe Flooding in Zambezi Basin",
                        "severity": "extreme",
                        "urgency": "immediate",
                        "certainty": "observed",
                        "effective": "2026-04-01T00:00:00Z",
                        "source": "INAM Mozambique",
                        "source_alert_id": "MOZ-FLOOD-2026-042",
                    },
                },
            ],
        },
    )

    type: Literal["Feature"] = Field(default="Feature", description="Must be 'Feature'")
    geometry: GeoJSONGeometry = Field(..., description="Alert geometry (required, creates hazard_zone geofence)")
    properties: IncidentProperties = Field(..., description="CAP-aligned alert properties")


class ReplaceIncidentInput(BaseModel):
    """Request body for PUT /collections/incidents/items/{fid}."""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "examples": [
                {
                    "type": "Feature",
                    "geometry": None,
                    "properties": {
                        "event": "Flood",
                        "headline": "Severe Flooding - Update 2",
                        "severity": "extreme",
                        "cap_msg_type": "update",
                    },
                },
            ],
        },
    )

    type: Literal["Feature"] = Field(default="Feature", description="Must be 'Feature'")
    geometry: GeoJSONGeometry | None = Field(
        default=None, description="Alert geometry (optional on update, updates hazard_zone geofence if provided)"
    )
    properties: IncidentProperties = Field(..., description="CAP-aligned alert properties")
