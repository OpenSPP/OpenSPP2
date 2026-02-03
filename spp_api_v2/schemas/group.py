# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Group resource schema for OpenSPP API V2"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import Address, CodeableConcept, Identifier, Period, Reference, ResourceMeta


class GroupMember(BaseModel):
    """Member of a group"""

    entity: Reference = Field(..., description="Reference to Individual")
    role: CodeableConcept | None = None
    period: Period | None = None
    inactive: bool = False


class Group(BaseModel):
    """A household or other group of individuals"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "Group",
                "identifier": [
                    {
                        "system": "urn:openspp:group",
                        "value": "HH-2024-001",
                    }
                ],
                "active": True,
                "groupType": "household",
                "name": "Santos Household",
                "quantity": 4,
                "member": [
                    {
                        "entity": {
                            "reference": "Individual/urn:gov:ph:psa:national-id|PH-123",
                            "display": "Maria Santos",
                        },
                        "role": {
                            "coding": [
                                {
                                    "system": "urn:openspp:vocab:relationship",
                                    "code": "head",
                                    "display": "Head of Household",
                                }
                            ]
                        },
                    }
                ],
            }
        },
    )

    type: Literal["Group"] = Field(
        "Group",
        description="Resource type discriminator",
    )

    # Identifiers (required, at least one)
    identifier: list[Identifier] = Field(
        ...,
        min_length=1,
        description="External identifiers for this group",
    )

    # Status
    active: bool = True

    # Group Type (household, family, organization, other)
    group_type: str = Field(
        "household",
        alias="groupType",
        pattern="^(household|family|organization|other)$",
        description="Type of group",
    )

    # Name
    name: str | None = None

    # Members
    member: list[GroupMember] | None = None
    quantity: int | None = Field(None, description="Number of members")

    # Location
    address: list[Address] | None = None

    # Extensions (module-specific fields)
    extension: dict[str, Any] | None = None

    # Metadata
    meta: ResourceMeta | None = None
