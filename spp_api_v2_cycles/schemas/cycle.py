# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Cycle resource schema for OpenSPP API V2"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from odoo.addons.spp_api_v2.schemas.base import Period, Reference, ResourceMeta


class CycleStatistics(BaseModel):
    """Statistics about a cycle"""

    members_count: int | None = Field(None, alias="membersCount", description="Number of beneficiaries")
    entitlements_count: int | None = Field(None, alias="entitlementsCount", description="Number of entitlements")
    payments_count: int | None = Field(None, alias="paymentsCount", description="Number of payments")
    total_amount: float | None = Field(None, alias="totalAmount", description="Total amount allocated")
    currency: str | None = Field(None, description="Currency code")

    model_config = ConfigDict(populate_by_name=True)


class Cycle(BaseModel):
    """A program cycle for distributing benefits"""

    type: Literal["Cycle"] = Field("Cycle")

    # Identifier (cycle name, required)
    identifier: str = Field(
        ...,
        description="Unique identifier for this cycle (name)",
    )

    # Basic info
    name: str = Field(..., description="Cycle name")
    sequence: int | None = Field(None, description="Cycle sequence number")

    # References
    program: Reference = Field(..., description="Reference to program")

    # Period
    period: Period | None = Field(None, description="Start and end dates")

    # Status
    state: str = Field(..., description="Current state")

    # Approval info
    approved_date: datetime | None = Field(None, alias="approvedDate")
    approved_by: str | None = Field(None, alias="approvedBy", description="Approver's name")

    # Statistics
    statistics: CycleStatistics | None = None

    # Navigation
    previous_cycle: Reference | None = Field(None, alias="previousCycle")
    next_cycle: Reference | None = Field(None, alias="nextCycle")

    # Extensions
    extension: dict[str, Any] | None = None

    # Metadata
    meta: ResourceMeta | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "Cycle",
                "identifier": "4Ps-2024-Q1",
                "name": "4Ps 2024 Q1",
                "sequence": 1,
                "program": {
                    "reference": "Program/4Ps",
                    "display": "Pantawid Pamilyang Pilipino Program",
                },
                "period": {
                    "start": "2024-01-01",
                    "end": "2024-03-31",
                },
                "state": "approved",
                "statistics": {
                    "membersCount": 1500,
                    "entitlementsCount": 1500,
                    "totalAmount": 4500000.00,
                    "currency": "PHP",
                },
            }
        },
    )
