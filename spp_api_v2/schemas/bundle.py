# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Bundle schema for search results and batch operations"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..utils.openapi_polymorphic import polymorphic_body
from .group import Group
from .individual import Individual


class BundleLink(BaseModel):
    """Link in a bundle (for pagination)"""

    relation: str = Field(
        ...,
        pattern="^(self|next|previous|first|last)$",
    )
    url: str


class BundleRequest(BaseModel):
    """Request in a bundle entry"""

    method: str = Field(..., pattern="^(GET|POST|PUT|PATCH|DELETE)$")
    url: str


class BundleResponse(BaseModel):
    """Response in a bundle entry"""

    status: str  # e.g., "201 Created"
    location: str | None = None
    etag: str | None = None


class BundleSearch(BaseModel):
    """Search metadata in a bundle entry"""

    mode: str = Field(..., pattern="^(match|include)$")
    score: float | None = None


class BundleEntry(BaseModel):
    """Entry in a bundle"""

    model_config = ConfigDict(populate_by_name=True)

    full_url: str | None = Field(
        None,
        alias="fullUrl",
        description="Placeholder UUID (urn:uuid:xxx) or resource URL",
    )
    request: BundleRequest | None = None
    response: BundleResponse | None = None
    resource: dict[str, Any] | None = Field(
        None,
        description="FHIR-style resource. Must match the type indicated by request.url.",
    )
    search: BundleSearch | None = None


class Bundle(BaseModel):
    """Bundle for search results or batch operations"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "searchset",
                "total": 1,
                "link": [
                    {
                        "relation": "self",
                        "url": "/api/v2/spp/Individual?name=Santos",
                    }
                ],
                "entry": [
                    {
                        "resource": {
                            "type": "Individual",
                            "identifier": [
                                {
                                    "system": "urn:gov:ph:psa:national-id",
                                    "value": "PH-123456789",
                                }
                            ],
                            "name": {
                                "family": "SANTOS",
                                "given": "Maria",
                            },
                        },
                        "search": {
                            "mode": "match",
                            "score": 0.95,
                        },
                    }
                ],
            }
        },
    )

    resource_type: Literal["Bundle"] = Field(
        "Bundle",
        alias="resourceType",
    )

    type: str = Field(
        ...,
        pattern="^(transaction|transaction-response|batch|batch-response|searchset|history)$",
    )

    total: int | None = Field(None, description="Total number of matches")

    link: list[BundleLink] | None = None

    entry: list[BundleEntry] | None = None


class RegistrantBundleEntry(BundleEntry):
    """Bundle entry whose resource is a registrant (Individual or Group).

    The base BundleEntry stays generic because other modules (e.g. Products)
    reuse it for non-registrant resources; only registrant-serving endpoints
    document the Individual/Group restriction.
    """

    resource: dict[str, Any] | None = polymorphic_body(
        Individual,
        Group,
        default=None,
        description="FHIR-style registrant resource (Individual or Group). "
        "Must match the type indicated by request.url.",
    )


class RegistrantBundle(Bundle):
    """Bundle whose entries carry registrant resources (Individual or Group)."""

    entry: list[RegistrantBundleEntry] | None = None


# ============================================================================
# New simplified batch schemas (ADR-019)
# ============================================================================


class BatchEntryRequest(BaseModel):
    """
    Single operation in a batch request.

    Example:
        {
            "id": "temp-1",
            "method": "POST",
            "path": "Individual",
            "body": {
                "type": "Individual",
                "identifier": [{
                    "system": "urn:gov:ph:psa:national-id",
                    "value": "PH-987654321"
                }],
                "name": {
                    "family": "DELA CRUZ",
                    "given": "Juan"
                }
            }
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "temp-1",
                    "method": "POST",
                    "path": "Individual",
                    "body": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:gov:ph:psa:national-id",
                                "value": "PH-987654321",
                            }
                        ],
                        "name": {
                            "family": "DELA CRUZ",
                            "given": "Juan",
                        },
                    },
                },
                {
                    "id": "temp-2",
                    "method": "PUT",
                    "path": "Individual/national-id|PH-123456789",
                    "body": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:gov:ph:psa:national-id",
                                "value": "PH-123456789",
                            }
                        ],
                        "name": {
                            "family": "SANTOS",
                            "given": "Maria Clara",
                        },
                    },
                },
                {
                    "id": "temp-3",
                    "method": "GET",
                    "path": "Individual/national-id|PH-111222333",
                },
            ]
        }
    )

    id: str | None = Field(
        None,
        description="Placeholder ID for cross-references (e.g., 'temp-1')",
    )

    method: str = Field(
        ...,
        pattern="^(GET|POST|PUT|PATCH|DELETE)$",
        description="HTTP method for the operation",
    )

    path: str = Field(
        ...,
        description="Resource path (e.g., 'Individual', 'Group/national-id|123')",
    )

    body: dict[str, Any] | None = Field(
        None,
        description="Request body for POST/PUT/PATCH operations",
    )


class BatchRequest(BaseModel):
    """
    Batch or transaction request.

    A batch executes operations independently (some may fail).
    A transaction executes all-or-nothing (atomic).

    Example:
        {
            "type": "batch",
            "entries": [
                {
                    "id": "temp-1",
                    "method": "POST",
                    "path": "Individual",
                    "body": {...}
                },
                {
                    "id": "temp-2",
                    "method": "PUT",
                    "path": "Individual/national-id|PH-123",
                    "body": {...}
                }
            ]
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "batch",
                "entries": [
                    {
                        "id": "temp-1",
                        "method": "POST",
                        "path": "Individual",
                        "body": {
                            "type": "Individual",
                            "identifier": [
                                {
                                    "system": "urn:gov:ph:psa:national-id",
                                    "value": "PH-987654321",
                                }
                            ],
                            "name": {
                                "family": "DELA CRUZ",
                                "given": "Juan",
                            },
                        },
                    },
                    {
                        "id": "temp-2",
                        "method": "PUT",
                        "path": "Individual/national-id|PH-123456789",
                        "body": {
                            "type": "Individual",
                            "identifier": [
                                {
                                    "system": "urn:gov:ph:psa:national-id",
                                    "value": "PH-123456789",
                                }
                            ],
                            "name": {
                                "family": "SANTOS",
                                "given": "Maria Clara",
                            },
                        },
                    },
                ],
            }
        }
    )

    type: Literal["batch", "transaction"] = Field(
        ...,
        description="'batch' for independent operations, 'transaction' for atomic all-or-nothing",
    )

    entries: list[BatchEntryRequest] = Field(
        ...,
        description="List of operations to execute",
    )


class BatchEntryResponse(BaseModel):
    """
    Response for single operation in a batch.

    Example:
        {
            "id": "temp-1",
            "status": 201,
            "location": "/api/v2/spp/Individual/national-id|PH-987654321",
            "body": {
                "type": "Individual",
                "identifier": [{
                    "system": "urn:gov:ph:psa:national-id",
                    "value": "PH-987654321"
                }],
                "name": {
                    "family": "DELA CRUZ",
                    "given": "Juan"
                }
            }
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "temp-1",
                    "status": 201,
                    "location": "/api/v2/spp/Individual/national-id|PH-987654321",
                    "body": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:gov:ph:psa:national-id",
                                "value": "PH-987654321",
                            }
                        ],
                        "name": {
                            "family": "DELA CRUZ",
                            "given": "Juan",
                        },
                    },
                },
                {
                    "id": "temp-2",
                    "status": 200,
                    "body": {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:gov:ph:psa:national-id",
                                "value": "PH-123456789",
                            }
                        ],
                        "name": {
                            "family": "SANTOS",
                            "given": "Maria Clara",
                        },
                    },
                },
                {
                    "id": "temp-3",
                    "status": 404,
                    "body": {
                        "error": "Resource not found",
                    },
                },
            ]
        }
    )

    id: str | None = Field(
        None,
        description="Echoes the request ID",
    )

    status: int = Field(
        ...,
        description="HTTP status code (200, 201, 400, 404, 500, etc.)",
    )

    location: str | None = Field(
        None,
        description="Location header for created resources (status 201)",
    )

    body: dict[str, Any] | None = Field(
        None,
        description="Response body (resource data or error details)",
    )


class BatchResponse(BaseModel):
    """
    Batch or transaction response.

    Example:
        {
            "type": "batch-response",
            "entries": [
                {
                    "id": "temp-1",
                    "status": 201,
                    "location": "/api/v2/spp/Individual/national-id|PH-987654321",
                    "body": {...}
                },
                {
                    "id": "temp-2",
                    "status": 200,
                    "body": {...}
                }
            ]
        }
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "batch-response",
                "entries": [
                    {
                        "id": "temp-1",
                        "status": 201,
                        "location": "/api/v2/spp/Individual/national-id|PH-987654321",
                        "body": {
                            "type": "Individual",
                            "identifier": [
                                {
                                    "system": "urn:gov:ph:psa:national-id",
                                    "value": "PH-987654321",
                                }
                            ],
                            "name": {
                                "family": "DELA CRUZ",
                                "given": "Juan",
                            },
                        },
                    },
                    {
                        "id": "temp-2",
                        "status": 200,
                        "body": {
                            "type": "Individual",
                            "identifier": [
                                {
                                    "system": "urn:gov:ph:psa:national-id",
                                    "value": "PH-123456789",
                                }
                            ],
                            "name": {
                                "family": "SANTOS",
                                "given": "Maria Clara",
                            },
                        },
                    },
                ],
            }
        }
    )

    type: Literal["batch-response", "transaction-response"] = Field(
        ...,
        description="Response type matching the request type",
    )

    entries: list[BatchEntryResponse] = Field(
        ...,
        description="List of operation responses (same order as request)",
    )
