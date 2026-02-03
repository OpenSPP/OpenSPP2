# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Individual resource schema for OpenSPP API V2"""

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import (
    Address,
    CodeableConcept,
    ContactPoint,
    GroupMembershipRef,
    HumanName,
    Identifier,
    ResourceMeta,
)


class Individual(BaseModel):
    """A person registered in OpenSPP"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "Individual",
                "identifier": [
                    {
                        "system": "urn:gov:ph:psa:national-id",
                        "value": "PH-123456789",
                    }
                ],
                "active": True,
                "name": {
                    "family": "SANTOS",
                    "given": "Maria",
                    "middle": "Dela Cruz",
                    "text": "SANTOS, Maria Dela Cruz",
                },
                "birthDate": "1985-03-15",
                "gender": {
                    "coding": [
                        {
                            "system": "urn:iso:std:iso:5218",
                            "code": "2",
                            "display": "Female",
                        }
                    ]
                },
                "telecom": [
                    {
                        "system": "phone",
                        "value": "+639171234567",
                        "use": "mobile",
                        "rank": 1,
                    }
                ],
            }
        },
    )

    type: Literal["Individual"] = Field(
        "Individual",
        description="Resource type discriminator",
    )

    # Identifiers (required, at least one)
    identifier: list[Identifier] = Field(
        ...,
        min_length=1,
        description="External identifiers for this individual",
    )

    # Status
    active: bool = Field(True, description="Whether record is active")

    # Name (optional - may be omitted when consent restricts access)
    name: HumanName | None = None

    # Demographics
    birth_date: date | None = Field(None, alias="birthDate")
    birth_date_estimated: bool | None = Field(False, alias="birthDateEstimated")
    gender: CodeableConcept | None = None

    # Contact
    telecom: list[ContactPoint] | None = None
    address: list[Address] | None = None

    # Photo
    photo: str | None = Field(None, description="Base64-encoded photo")

    # Relationships
    group_membership: list[GroupMembershipRef] | None = Field(
        None,
        alias="groupMembership",
    )

    # Extensions (module-specific fields)
    extension: dict[str, Any] | None = None

    # Metadata
    meta: ResourceMeta | None = None
