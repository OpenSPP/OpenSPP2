# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Bulk operation schemas for OpenSPP API V2"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BulkExportRequest(BaseModel):
    """Request for bulk export of resources by identifiers"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "Individual",
                "identifiers": [
                    "urn:gov:ph:psa:national-id|PH-123456789",
                    "urn:gov:ph:psa:national-id|PH-987654321",
                ],
                "_elements": "name,birthDate,gender",
            }
        },
    )

    type: Literal["Individual", "Group"] = Field(
        ...,
        description="Type of resources to export",
    )

    identifiers: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of identifiers in format system|value",
    )

    elements: str | None = Field(
        None,
        alias="_elements",
        description="Comma-separated list of fields to include in response",
    )

    extensions: str | None = Field(
        None,
        alias="_extensions",
        description="Comma-separated list of extensions to include",
    )


class BulkExportItem(BaseModel):
    """Single item in bulk export response"""

    model_config = ConfigDict(populate_by_name=True)

    identifier: str = Field(
        ...,
        description="The requested identifier",
    )

    status: Literal["success", "not_found", "access_denied", "error"] = Field(
        ...,
        description="Result status for this identifier",
    )

    resource: dict[str, Any] | None = Field(
        None,
        description="The exported resource (if successful)",
    )

    error: str | None = Field(
        None,
        description="Error message (if not successful)",
    )


class BulkExportResponse(BaseModel):
    """Response for bulk export operation"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "total": 2,
                "successful": 2,
                "failed": 0,
                "items": [
                    {
                        "identifier": "urn:gov:ph:psa:national-id|PH-123456789",
                        "status": "success",
                        "resource": {
                            "type": "Individual",
                            "identifier": [
                                {
                                    "system": "urn:gov:ph:psa:national-id",
                                    "value": "PH-123456789",
                                }
                            ],
                            "name": {"family": "SANTOS", "given": "Maria"},
                        },
                    },
                    {
                        "identifier": "urn:gov:ph:psa:national-id|PH-987654321",
                        "status": "success",
                        "resource": {
                            "type": "Individual",
                            "identifier": [
                                {
                                    "system": "urn:gov:ph:psa:national-id",
                                    "value": "PH-987654321",
                                }
                            ],
                            "name": {"family": "REYES", "given": "Juan"},
                        },
                    },
                ],
            }
        },
    )

    total: int = Field(
        ...,
        ge=0,
        description="Total number of identifiers requested",
    )

    successful: int = Field(
        ...,
        ge=0,
        description="Number of successful exports",
    )

    failed: int = Field(
        ...,
        ge=0,
        description="Number of failed exports",
    )

    items: list[BulkExportItem] = Field(
        ...,
        description="Export results for each identifier",
    )
