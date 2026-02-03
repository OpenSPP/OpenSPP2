# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Program resource schema for OpenSPP API V2"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import CodeableConcept, Identifier, Period, ResourceMeta


class Program(BaseModel):
    """A social protection program"""

    type: Literal["Program"] = Field(
        "Program",
        description="Resource type discriminator",
    )

    # Identifiers (required, at least one)
    identifier: list[Identifier] = Field(
        ...,
        min_length=1,
        description="External identifiers for this program",
    )

    # Status
    active: bool = Field(True, description="Whether program is active")

    # Name and description
    name: str = Field(..., description="Program name")
    description: str | None = Field(None, description="Program description")

    # Program type (e.g., cash transfer, in-kind, etc.)
    program_type: CodeableConcept = Field(
        ...,
        alias="programType",
        description="Type of program (e.g., cash transfer, in-kind)",
    )

    # Target type
    target_type: str = Field(
        ...,
        pattern="^(individual|group)$",
        alias="targetType",
        description="Whether program targets individuals or groups",
    )

    # Eligibility criteria (human-readable)
    eligibility_criteria: str | None = Field(
        None,
        alias="eligibilityCriteria",
        description="Eligibility criteria description",
    )

    # Period when program is active
    period: Period | None = None

    # Metadata
    meta: ResourceMeta | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "Program",
                "identifier": [
                    {
                        "system": "urn:openspp:program",
                        "value": "4Ps-2024",
                    }
                ],
                "active": True,
                "name": "Pantawid Pamilyang Pilipino Program (4Ps)",
                "description": "Conditional cash transfer program for poor families",
                "programType": {
                    "coding": [
                        {
                            "system": "urn:openspp:vocab:program-type",
                            "code": "cash-transfer",
                            "display": "Cash Transfer",
                        }
                    ]
                },
                "targetType": "group",
                "eligibilityCriteria": "Households with children under 18 and pregnant/lactating mothers",
                "period": {
                    "start": "2024-01-01",
                    "end": None,
                },
            }
        },
    )
