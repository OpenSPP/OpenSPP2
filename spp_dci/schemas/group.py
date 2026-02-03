"""DCI Group schema types."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .common import AdditionalAttribute, Address, Identifier, Place
from .constants import (
    AssistanceUnitEnum,
    EducationCodeEnum,
    EmploymentStatusEnum,
    IncomeLevelEnum,
    LanguageCodeEnum,
    MaritalStatus,
    OccupationEnum,
)
from .person import DisabilityInfo, Person, RelatedPerson


class Member(BaseModel):
    """DCI Member schema - individual within a group/household."""

    model_config = ConfigDict(populate_by_name=True)

    member_identifier: list[Identifier] | None = Field(
        None,
        description="Unique identifier(s) assigned to each member",
    )
    demographic_info: Person | None = Field(
        None,
        description="Personal/demographic details of the member",
    )
    related_person: list[RelatedPerson] | None = Field(
        None,
        description="Array of persons related to this member and relationship types",
    )
    is_disabled: bool | None = Field(
        None,
        description="Whether the member has a disability",
    )
    disability_info: list[DisabilityInfo] | None = Field(
        None,
        description="Additional attributes for people with disabilities",
    )
    marital_status: MaritalStatus | str | None = Field(
        None,
        description=(
            "Marital status (S=Single, M=Married, W=Widowed, A=Annulled, " "D=Divorced, L=Legally Separated, U=Unknown)"
        ),
    )
    employment_status: EmploymentStatusEnum | str | None = Field(
        None,
        description="Employment status of the member",
    )
    occupation: OccupationEnum | str | None = Field(
        None,
        description="Occupation of the member",
    )
    income_level: IncomeLevelEnum | str | None = Field(
        None,
        description="Income level of the member",
    )
    language_code: LanguageCodeEnum | str | None = Field(
        None,
        description="Languages spoken by the member",
    )
    education_level: EducationCodeEnum | str | None = Field(
        None,
        description="Education level of the member",
    )
    additional_attributes: list[AdditionalAttribute] | None = Field(
        None,
        description="Additional attributes as key-value pairs",
    )
    registration_date: datetime | None = Field(
        None,
        description="Date the member was registered",
    )
    last_updated: datetime | None = Field(
        None,
        description="Date the member details were last updated",
    )


class Group(BaseModel):
    """DCI Group schema - household/family unit."""

    model_config = ConfigDict(populate_by_name=True)

    context_: str | None = Field(
        None,
        alias="@context",
        description="JSON-LD context",
    )
    type_: str = Field(
        "Group",
        alias="@type",
        description="Entity type",
    )
    group_identifier: list[Identifier] | None = Field(
        None,
        description="Unique identifier(s) assigned to the group",
    )
    group_type: AssistanceUnitEnum | str | None = Field(
        None,
        description="Type of group (Member, Household, Family)",
    )
    geographical_location: Place | None = Field(
        None,
        description="Physical location where the group is living",
    )
    address: list[Address] | None = Field(
        None,
        description="Current residential address(es) of the group",
    )
    place_address: bool | None = Field(
        None,
        description="Whether place or address is used (True=place, False=address)",
    )
    poverty_score: float | None = Field(
        None,
        description="Metric based on assessment of group characteristics",
    )
    poverty_score_type: str | None = Field(
        None,
        description="Type of poverty score used to measure poverty level",
    )
    group_head_info: Member | None = Field(
        None,
        description="Personal details of the head of the group",
    )
    group_size: int | None = Field(
        None,
        ge=0,
        description="Total number of members in the group",
    )
    member_list: list[Member] | None = Field(
        None,
        description="List of related individuals in the group",
    )
    additional_attributes: list[AdditionalAttribute] | None = Field(
        None,
        description="Additional attributes as key-value pairs",
    )
    registration_date: datetime | None = Field(
        None,
        description="Date the group was registered",
    )
    last_updated: datetime | None = Field(
        None,
        description="Date the group details were last updated",
    )
