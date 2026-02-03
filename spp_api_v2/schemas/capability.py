# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Capability statement schema for metadata endpoint"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CapabilitySoftware(BaseModel):
    """Software information"""

    name: str
    version: str


class CapabilityInteraction(BaseModel):
    """Supported interaction on a resource"""

    code: str  # read, search-type, create, update, delete


class CapabilitySearchParam(BaseModel):
    """Supported search parameter"""

    name: str
    type: str  # string, token, date, reference, etc.
    documentation: str | None = None


class CapabilityResource(BaseModel):
    """Resource capability"""

    type: str  # Individual, Group, etc.
    profile: str | None = None
    interaction: list[CapabilityInteraction]
    search_param: list[CapabilitySearchParam] | None = Field(
        None,
        alias="searchParam",
    )

    model_config = ConfigDict(populate_by_name=True)


class CapabilityOperation(BaseModel):
    """Supported operation"""

    name: str
    definition: str


class CapabilityRest(BaseModel):
    """REST capabilities"""

    mode: str = "server"
    resource: list[CapabilityResource]
    operation: list[CapabilityOperation] | None = None


class CapabilityExtension(BaseModel):
    """Available extension"""

    url: str
    module: str
    applies_to: list[str] = Field(..., alias="appliesTo")
    fields: list[str]

    model_config = ConfigDict(populate_by_name=True)


class CapabilityStatement(BaseModel):
    """Capability statement for the API"""

    resource_type: Literal["CapabilityStatement"] = Field(
        "CapabilityStatement",
        alias="resourceType",
    )

    status: str = "active"
    date: str  # ISO date
    kind: str = "instance"

    software: CapabilitySoftware

    fhir_version: str = Field("inspired", alias="fhirVersion")
    format: list[str] = Field(default_factory=lambda: ["json"])

    rest: list[CapabilityRest]
    extension: list[CapabilityExtension] | None = None

    model_config = ConfigDict(populate_by_name=True)
