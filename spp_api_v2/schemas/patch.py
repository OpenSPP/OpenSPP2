# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Patch schemas for partial updates (JSON Merge Patch - RFC 7396)"""

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .base import Address, CodeableConcept, ContactPoint, HumanName


class IndividualPatch(BaseModel):
    """
    Partial update schema for Individual resources.

    Uses JSON Merge Patch semantics (RFC 7396):
    - Only specified fields are updated
    - null values remove the field
    - Omitted fields are unchanged
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": {
                    "family": "SANTOS",
                    "given": "Maria Elena",
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

    # All fields are optional for PATCH
    active: bool | None = None

    name: HumanName | None = None

    birth_date: date | None = Field(None, alias="birthDate")
    birth_date_estimated: bool | None = Field(None, alias="birthDateEstimated")
    gender: CodeableConcept | None = None

    telecom: list[ContactPoint] | None = None
    address: list[Address] | None = None

    photo: str | None = Field(None, description="Base64-encoded photo")

    extension: dict[str, Any] | None = None


class GroupPatch(BaseModel):
    """
    Partial update schema for Group resources.

    Uses JSON Merge Patch semantics (RFC 7396):
    - Only specified fields are updated
    - null values remove the field
    - Omitted fields are unchanged
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Santos Household (Updated)",
                "address": [
                    {
                        "type": "physical",
                        "line": ["456 New Street"],
                        "city": "Manila",
                    }
                ],
            }
        },
    )

    # All fields are optional for PATCH
    active: bool | None = None

    name: str | None = None

    address: list[Address] | None = None

    extension: dict[str, Any] | None = None
