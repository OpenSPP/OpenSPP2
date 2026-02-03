# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Product Category resource schema for OpenSPP API V2"""

from typing import Literal

from pydantic import BaseModel, Field

from odoo.addons.spp_api_v2.schemas.base import Reference, ResourceMeta


class ProductCategory(BaseModel):
    """A category for organizing products"""

    resource_type: Literal["ProductCategory"] = Field(
        "ProductCategory",
        alias="resourceType",
    )

    # Identifier (name)
    identifier: str = Field(
        ...,
        description="Unique identifier for this category (name)",
    )

    # Basic info
    name: str = Field(..., description="Category name")

    # Hierarchy
    parent: Reference | None = Field(None, description="Reference to parent category")

    # Metadata
    meta: ResourceMeta | None = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "resourceType": "ProductCategory",
                "identifier": "Food",
                "name": "Food",
                "parent": {
                    "reference": "ProductCategory/All",
                    "display": "All",
                },
            }
        }
