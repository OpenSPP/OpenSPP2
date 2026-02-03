# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for Vocabulary API."""

from pydantic import BaseModel, Field


class VocabularyResponse(BaseModel):
    """Schema for a single vocabulary."""

    namespace_uri: str = Field(
        ...,
        description="Globally unique namespace URI",
        examples=["urn:iso:std:iso:5218", "urn:openspp:vocab:relationship"],
    )
    name: str = Field(
        ...,
        description="Human-readable name",
        examples=["Gender", "Relationship Type"],
    )
    version: str | None = Field(
        None,
        description="Version of the vocabulary",
        examples=["2024"],
    )
    description: str | None = Field(
        None,
        description="Detailed description",
    )
    reference_url: str | None = Field(
        None,
        description="Link to official documentation",
    )
    domain: str = Field(
        ...,
        description="Domain area (core, social_assistance, health, etc.)",
        examples=["core", "social_assistance"],
    )
    is_hierarchical: bool = Field(
        False,
        description="Whether codes have parent/child relationships",
    )
    code_count: int = Field(
        0,
        description="Number of codes in this vocabulary",
    )

    model_config = {"from_attributes": True}


class VocabularyListResponse(BaseModel):
    """Schema for list of vocabularies."""

    total: int = Field(..., description="Total number of vocabularies")
    items: list[VocabularyResponse] = Field(..., description="List of vocabularies")


class VocabularyCodeResponse(BaseModel):
    """Schema for a single vocabulary code."""

    code: str = Field(
        ...,
        description="Machine-readable code",
        examples=["M", "F", "head"],
    )
    display: str = Field(
        ...,
        description="Human-readable label",
        examples=["Male", "Female", "Head of Household"],
    )
    definition: str | None = Field(
        None,
        description="Formal definition of what this code means",
    )
    deprecated: bool = Field(
        False,
        description="Whether this code is deprecated",
    )
    parent_code: str | None = Field(
        None,
        description="Parent code for hierarchical vocabularies",
    )
    level: int = Field(
        0,
        description="Level in hierarchy (0 for root)",
    )

    model_config = {"from_attributes": True}


class VocabularyCodesResponse(BaseModel):
    """Schema for codes within a vocabulary."""

    namespace_uri: str = Field(
        ...,
        description="Namespace URI of the vocabulary",
    )
    vocabulary_name: str = Field(
        ...,
        description="Name of the vocabulary",
    )
    total: int = Field(
        ...,
        description="Total number of codes",
    )
    items: list[VocabularyCodeResponse] = Field(
        ...,
        description="List of codes",
    )
