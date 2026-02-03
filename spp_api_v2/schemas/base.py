# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Base schema types for OpenSPP API V2"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class Period(BaseModel):
    """Time period with start and end dates"""

    start: date | None = None
    end: date | None = None


class Identifier(BaseModel):
    """External identifier for a resource"""

    system: str = Field(
        ...,
        description="Namespace URI for the identifier type",
        examples=["urn:gov:ph:psa:national-id"],
    )
    value: str = Field(
        ...,
        description="The identifier value",
        examples=["PH-123456789"],
    )
    period: Period | None = Field(
        None,
        description="Time period when identifier is/was valid",
    )


class HumanName(BaseModel):
    """Human name with components"""

    family: str | None = Field(None, description="Family name (surname)")
    given: str | None = Field(None, description="Given name (first name)")
    middle: str | None = Field(None, description="Middle name")
    prefix: str | None = Field(None, description="Name prefix (Mr., Dr.)")
    suffix: str | None = Field(None, description="Name suffix (Jr., III)")
    text: str | None = Field(
        None,
        description="Full text representation of name",
    )


class Coding(BaseModel):
    """Reference to a code in a vocabulary"""

    system: str = Field(..., description="Vocabulary namespace URI")
    code: str = Field(..., description="Code value")
    display: str | None = Field(None, description="Human-readable display")


class CodeableConcept(BaseModel):
    """Coded value with optional text"""

    coding: list[Coding] = Field(default_factory=list)
    text: str | None = Field(None, description="Plain text representation")


class Address(BaseModel):
    """Physical or postal address"""

    model_config = ConfigDict(populate_by_name=True)

    type: str | None = Field(None, pattern="^(physical|postal|both)$")
    text: str | None = Field(None, description="Full address as text")
    line: list[str] | None = Field(None, description="Street address lines")
    city: str | None = None
    district: str | None = None
    state: str | None = None
    postal_code: str | None = Field(None, alias="postalCode")
    country: str | None = Field(None, description="ISO 3166-1 alpha-2 code")


class ContactPoint(BaseModel):
    """Contact information (phone, email, etc.)"""

    system: str = Field(..., pattern="^(phone|email|fax|url|sms)$")
    value: str
    use: str | None = Field(None, pattern="^(home|work|mobile)$")
    rank: int | None = Field(None, ge=1, description="Preferred order")


class Reference(BaseModel):
    """Reference to another resource"""

    reference: str = Field(
        ...,
        description="Resource type and identifier",
        examples=["Individual/urn:gov:ph:psa:national-id|PH-123"],
    )
    display: str | None = Field(None, description="Text alternative")


class ResourceMeta(BaseModel):
    """Resource metadata"""

    model_config = ConfigDict(populate_by_name=True)

    version_id: str | None = Field(None, alias="versionId")
    last_updated: datetime | None = Field(None, alias="lastUpdated")
    source: str | None = Field(
        None,
        description="Source system URI",
    )


class GroupMembershipRef(BaseModel):
    """Reference to group membership"""

    group: Reference
    role: CodeableConcept | None = None
    period: Period | None = None
