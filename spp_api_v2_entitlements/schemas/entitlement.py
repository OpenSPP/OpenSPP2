# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Entitlement resource schema for OpenSPP API V2"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from odoo.addons.spp_api_v2.schemas.base import Period, Reference, ResourceMeta


class MoneyValue(BaseModel):
    """Monetary value with currency"""

    value: float = Field(..., description="Amount")
    currency: str = Field(..., description="ISO 4217 currency code")


class Quantity(BaseModel):
    """Quantity with unit of measure"""

    value: float = Field(..., description="Quantity value")
    unit: str = Field(..., description="Unit of measure name")


class ProductQuantity(BaseModel):
    """Product with quantity"""

    product: Reference = Field(..., description="Reference to product")
    quantity: Quantity = Field(..., description="Amount of product")
    unit_price: MoneyValue | None = Field(None, alias="unitPrice", description="Price per unit")


class Entitlement(BaseModel):
    """An entitlement to receive benefits (cash or in-kind)"""

    type: Literal["Entitlement"] = Field(
        "Entitlement",
        description="Resource type discriminator",
    )

    # Identifier (entitlement code, required)
    identifier: str = Field(
        ...,
        description="Unique identifier for this entitlement (code)",
    )

    # Entitlement type
    entitlement_type: Literal["cash", "inkind"] = Field(
        ...,
        alias="entitlementType",
        description="Type of entitlement",
    )

    # Status
    state: str = Field(..., description="Current state of entitlement")

    # References (optional - may not be set in all cases)
    beneficiary: Reference | None = Field(None, description="Reference to beneficiary (Individual or Group)")
    program: Reference | None = Field(None, description="Reference to program")
    cycle: Reference | None = Field(None, description="Reference to cycle")

    # Validity period
    valid_period: Period | None = Field(None, alias="validPeriod", description="Validity period")

    # Cash entitlement fields
    initial_amount: MoneyValue | None = Field(None, alias="initialAmount", description="Initial cash amount")
    balance: MoneyValue | None = Field(None, description="Remaining balance")

    # In-kind entitlement fields
    items: list[ProductQuantity] | None = Field(None, description="Products for in-kind entitlement")

    # Service point (for in-kind)
    service_point: Reference | None = Field(None, alias="servicePoint", description="Redemption service point")

    # Approval info
    approved_date: date | None = Field(None, alias="approvedDate")

    # ERN (Entitlement Reference Number)
    ern: str | None = Field(None, description="Entitlement Reference Number")

    # Extensions
    extension: dict[str, Any] | None = None

    # Metadata
    meta: ResourceMeta | None = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "type": "Entitlement",
                "identifier": "abc123-def456",
                "entitlementType": "cash",
                "state": "approved",
                "beneficiary": {
                    "reference": "Individual/urn:gov:ph:psa:national-id|PH-123",
                    "display": "Maria Santos",
                },
                "program": {
                    "reference": "Program/4Ps",
                    "display": "Pantawid Pamilyang Pilipino Program",
                },
                "cycle": {
                    "reference": "Cycle/4Ps-2024-Q1",
                    "display": "4Ps 2024 Q1",
                },
                "validPeriod": {
                    "start": "2024-01-01",
                    "end": "2024-03-31",
                },
                "initialAmount": {
                    "value": 3000.00,
                    "currency": "PHP",
                },
            }
        }
