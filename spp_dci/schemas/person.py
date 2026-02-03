"""DCI Person schema types."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .common import Address, Identifier, Name
from .constants import SexCategory


class DisabilityInfo(BaseModel):
    """DCI DisabilityInfo schema - disability information."""

    model_config = ConfigDict(populate_by_name=True)

    disability_limitation_type: str = Field(
        ...,
        description="Type of functional limitation (Vision, Hearing, Mobility, etc.)",
    )
    functional_severity: int = Field(
        ...,
        ge=1,
        le=4,
        description="Severity level of functional limitation (1-4 scale)",
    )


class RelatedPerson(BaseModel):
    """DCI RelatedPerson schema - family relationship information."""

    model_config = ConfigDict(populate_by_name=True)

    relationship_type: str = Field(
        ...,
        description="Type of relationship (spouse, child, parent, etc.)",
    )
    related_member: Optional["Person"] = Field(
        None,
        description="The related person object",
    )


class Person(BaseModel):
    """DCI Person schema - core person entity."""

    model_config = ConfigDict(populate_by_name=True)

    context_: str | None = Field(
        None,
        alias="@context",
        description="JSON-LD context",
    )
    type_: str = Field(
        "Person",
        alias="@type",
        description="Entity type",
    )
    identifier: list[Identifier] = Field(
        ...,
        description="Person's identification numbers (UIN, BRN, MRN, DRN, etc.)",
    )
    name: Name | None = Field(
        None,
        description="Person's structured name",
    )
    sex: SexCategory | str | None = Field(
        None,
        description="Sex of the person (male, female, other, unknown)",
    )
    birth_date: date | None = Field(
        None,
        description="Date of birth",
    )
    death_date: date | None = Field(
        None,
        description="Date of death",
    )
    address: list[Address] | None = Field(
        None,
        description="Current residential addresses",
    )
    phone_number: list[str] | None = Field(
        None,
        description="Phone numbers (E.164 format recommended)",
    )
    email: list[str] | None = Field(
        None,
        description="Email addresses (RFC 5322 addr-spec format)",
    )
    registration_date: datetime | None = Field(
        None,
        description="Date of registration",
    )
    last_updated: datetime | None = Field(
        None,
        description="Date when person details were last updated",
    )


# Update forward references
RelatedPerson.model_rebuild()
