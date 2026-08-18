# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Product resource schema for OpenSPP API V2"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from odoo.addons.spp_api_v2.schemas.base import Reference, ResourceMeta


class Product(BaseModel):
    """A product that can be distributed as in-kind entitlement"""

    resource_type: Literal["Product"] = Field(
        "Product",
        alias="resourceType",
    )

    # Identifier (default_code or name)
    identifier: str = Field(
        ...,
        description="Unique identifier for this product (default_code or name)",
    )

    # Basic info
    name: str = Field(..., description="Product name")
    code: str | None = Field(None, alias="defaultCode", description="Product SKU/code")

    # Category
    category: Reference | None = Field(None, description="Reference to product category")

    # Unit of measure
    uom: Reference | None = Field(None, alias="unitOfMeasure", description="Reference to unit of measure")

    # Pricing
    list_price: float | None = Field(None, alias="listPrice", description="List price")
    currency: str | None = Field(None, description="Currency code (ISO 4217)")

    # Status
    active: bool = Field(True, description="Whether product is active")

    # Image availability (URL not exposed to avoid database ID leakage)
    has_image: bool | None = Field(None, alias="hasImage", description="Whether product has an image")

    # Extensions
    extension: dict[str, Any] | None = None

    # Metadata
    meta: ResourceMeta | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "resourceType": "Product",
                "identifier": "RICE-25KG",
                "name": "Rice 25kg Bag",
                "defaultCode": "RICE-25KG",
                "category": {
                    "reference": "ProductCategory/Food",
                    "display": "Food",
                },
                "unitOfMeasure": {
                    "reference": "UnitOfMeasure/kg",
                    "display": "kg",
                },
                "listPrice": 25.00,
                "currency": "PHP",
                "active": True,
            }
        },
    )
