# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service Point resource schema for OpenSPP API V2"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from odoo.addons.spp_api_v2.schemas.base import (
    Address,
    ContactPoint,
    Reference,
    ResourceMeta,
)


class ServicePoint(BaseModel):
    """A service point where beneficiaries can redeem entitlements"""

    resource_type: Literal["ServicePoint"] = Field(
        "ServicePoint",
        alias="resourceType",
    )

    # Identifier (service point name, required)
    identifier: str = Field(
        ...,
        description="Unique identifier for this service point (name)",
    )

    # Name
    name: str = Field(..., description="Display name of the service point")

    # Status
    active: bool = Field(True, alias="contractActive", description="Whether contract is active")
    disabled: bool = Field(False, description="Whether service point is disabled")

    # Location
    area: Reference | None = Field(None, description="Reference to geographic area")
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 country code")
    address: Address | None = None

    # Contact
    telecom: list[ContactPoint] | None = None

    # Organization
    company: Reference | None = Field(None, description="Reference to company managing this service point")

    # Service types
    service_type: list[str] | None = Field(None, alias="serviceType", description="Types of services offered")

    # Extensions (module-specific fields)
    extension: dict[str, Any] | None = None

    # Metadata
    meta: ResourceMeta | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "resourceType": "ServicePoint",
                "identifier": "SP-MANILA-001",
                "name": "Manila Central Distribution Center",
                "contractActive": True,
                "disabled": False,
                "country": "PH",
                "telecom": [
                    {
                        "system": "phone",
                        "value": "+639171234567",
                        "use": "work",
                    }
                ],
            }
        },
    )
