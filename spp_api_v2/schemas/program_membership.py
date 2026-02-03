# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""ProgramMembership resource schema for OpenSPP API V2"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import CodeableConcept, Identifier, Reference, ResourceMeta


class ProgramMembership(BaseModel):
    """Enrollment of a beneficiary in a program"""

    type: Literal["ProgramMembership"] = Field(
        "ProgramMembership",
        description="Resource type discriminator",
    )

    # Identifiers (optional for membership)
    identifier: list[Identifier] | None = Field(
        None,
        description="External identifiers for this enrollment",
    )

    # Program reference (required)
    program: Reference = Field(
        ...,
        description="Reference to the Program",
    )

    # Beneficiary reference (required) - can be Individual or Group
    beneficiary: Reference = Field(
        ...,
        description="Reference to the beneficiary (Individual or Group)",
    )

    # Status (required)
    status: str = Field(
        ...,
        pattern="^(draft|enrolled|paused|exited|not_eligible|duplicated)$",
        description="Enrollment status",
    )

    # Enrollment date
    enrollment_date: date | None = Field(
        None,
        alias="enrollmentDate",
        description="Date of enrollment",
    )

    # Exit information
    exit_date: date | None = Field(
        None,
        alias="exitDate",
        description="Date of exit from program",
    )

    exit_reason: CodeableConcept | None = Field(
        None,
        alias="exitReason",
        description="Reason for exit",
    )

    # Metadata
    meta: ResourceMeta | None = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "ProgramMembership",
                "identifier": [
                    {
                        "system": "urn:openspp:program-membership",
                        "value": "4Ps-2024-HH001",
                    }
                ],
                "program": {
                    "reference": "Program/urn:openspp:program|4Ps-2024",
                    "display": "Pantawid Pamilyang Pilipino Program",
                },
                "beneficiary": {
                    "reference": "Group/urn:openspp:group|HH-2024-001",
                    "display": "Santos Household",
                },
                "status": "enrolled",
                "enrollmentDate": "2024-01-15",
                "exitDate": None,
                "exitReason": None,
            }
        },
    )
