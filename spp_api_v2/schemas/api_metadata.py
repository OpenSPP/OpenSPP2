# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Simplified API metadata schema for OpenSPP API V2.

This replaces the FHIR CapabilityStatement with a simpler, more intuitive
metadata structure that describes available resources, operations, extensions,
and authentication methods.
"""

from pydantic import BaseModel, ConfigDict, Field


class ResourceMetadata(BaseModel):
    """Metadata describing supported operations and search parameters for a resource.

    This provides information about what operations can be performed on a resource
    (read, search, create, update, delete) and what search parameters are available.
    """

    operations: list[str] = Field(
        ...,
        description="Supported operations on this resource",
        examples=[["read", "search", "create", "update"]],
    )
    search_params: list[str] = Field(
        default_factory=list,
        alias="searchParams",
        description="Available search parameters for this resource",
        examples=[["identifier", "name", "birthdate", "gender", "address"]],
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "operations": ["read", "search", "create", "update"],
                "searchParams": ["identifier", "name", "birthdate", "gender"],
            }
        },
    )


class ExtensionMetadata(BaseModel):
    """Metadata describing an API extension provided by an optional module.

    Extensions allow domain-specific modules to add fields and functionality
    to core resources. For example, the farmer registry module adds farm-related
    fields to Individual and Group resources.
    """

    url: str = Field(
        ...,
        description="Unique URI identifying this extension",
        examples=["urn:openspp:extension:farmer"],
    )
    module: str = Field(
        ...,
        description="Odoo module providing this extension",
        examples=["spp_farmer_registry"],
    )
    applies_to: list[str] = Field(
        ...,
        alias="appliesTo",
        description="Resource types this extension can be applied to",
        examples=[["Individual", "Group"]],
    )
    fields: list[str] = Field(
        ...,
        description="Additional fields provided by this extension",
        examples=[["farm_size", "crops", "livestock_count"]],
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "url": "urn:openspp:extension:farmer",
                "module": "spp_farmer_registry",
                "appliesTo": ["Individual", "Group"],
                "fields": ["farm_size", "crops", "livestock_count"],
            }
        },
    )


class AuthenticationMetadata(BaseModel):
    """Metadata describing authentication configuration for the API.

    Currently supports OAuth2 client credentials flow for API authentication.
    """

    type: str = Field(
        ...,
        description="Authentication type",
        examples=["oauth2"],
    )
    token_endpoint: str = Field(
        ...,
        alias="tokenEndpoint",
        description="URL endpoint for obtaining access tokens",
        examples=["/api/v2/spp/oauth/token"],
    )
    grant_types: list[str] = Field(
        ...,
        alias="grantTypes",
        description="Supported OAuth2 grant types",
        examples=[["client_credentials"]],
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "oauth2",
                "tokenEndpoint": "/api/v2/spp/oauth/token",
                "grantTypes": ["client_credentials"],
            }
        },
    )


class ApiMetadata(BaseModel):
    """Complete API metadata response.

    This provides a comprehensive overview of the API including version,
    available resources, extensions, authentication methods, and documentation.
    """

    name: str = Field(
        ...,
        description="API name",
        examples=["OpenSPP API"],
    )
    version: str = Field(
        ...,
        description="API version following semantic versioning",
        examples=["2.0.0"],
    )
    resources: dict[str, ResourceMetadata] = Field(
        ...,
        description="Map of resource types to their metadata",
    )
    extensions: list[ExtensionMetadata] = Field(
        default_factory=list,
        description="Available API extensions from optional modules",
    )
    authentication: AuthenticationMetadata = Field(
        ...,
        description="Authentication configuration",
    )
    docs: str = Field(
        ...,
        description="URL to interactive API documentation",
        examples=["/api/v2/spp/docs"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "OpenSPP API",
                "version": "2.0.0",
                "resources": {
                    "Individual": {
                        "operations": ["read", "search", "create", "update"],
                        "searchParams": [
                            "identifier",
                            "name",
                            "birthdate",
                            "gender",
                            "address",
                        ],
                    },
                    "Group": {
                        "operations": ["read", "search", "create", "update"],
                        "searchParams": ["identifier", "name", "type", "member"],
                    },
                    "Program": {
                        "operations": ["read", "search"],
                        "searchParams": ["identifier", "name", "status", "type"],
                    },
                    "ProgramMembership": {
                        "operations": ["read", "search"],
                        "searchParams": ["beneficiary", "program", "status"],
                    },
                },
                "extensions": [
                    {
                        "url": "urn:openspp:extension:farmer",
                        "module": "spp_farmer_registry",
                        "appliesTo": ["Individual", "Group"],
                        "fields": ["farm_size", "crops"],
                    }
                ],
                "authentication": {
                    "type": "oauth2",
                    "tokenEndpoint": "/api/v2/spp/oauth/token",
                    "grantTypes": ["client_credentials"],
                },
                "docs": "/api/v2/spp/docs",
            }
        }
    )
