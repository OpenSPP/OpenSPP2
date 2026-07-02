# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unit of Measure resource schema for OpenSPP API V2"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from odoo.addons.spp_api_v2.schemas.base import Reference, ResourceMeta


class UnitOfMeasure(BaseModel):
    """A unit of measure for products"""

    resource_type: Literal["UnitOfMeasure"] = Field(
        "UnitOfMeasure",
        alias="resourceType",
    )

    # Identifier (name)
    identifier: str = Field(
        ...,
        description="Unique identifier for this UoM (name)",
    )

    # Basic info
    name: str = Field(..., description="UoM name")
    symbol: str | None = Field(None, description="Short symbol (e.g., 'kg', 'L')")

    # Category
    category: Reference | None = Field(None, description="Reference to UoM category")

    # Conversion
    factor: float | None = Field(None, description="Factor to convert to reference UoM")
    rounding: float | None = Field(None, description="Rounding precision")

    # Metadata
    meta: ResourceMeta | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "resourceType": "UnitOfMeasure",
                "identifier": "kg",
                "name": "Kilogram",
                "symbol": "kg",
                "category": {
                    "reference": "UnitOfMeasure/Weight",
                    "display": "Weight",
                },
                "factor": 1.0,
            }
        },
    )
