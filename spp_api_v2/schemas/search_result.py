# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Search result envelope schema for OpenSPP API V2"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SearchResultMeta(BaseModel):
    """Pagination metadata for search results"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 100,
                "count": 20,
                "offset": 0,
            }
        }
    )

    total: int = Field(
        ...,
        ge=0,
        description="Total number of resources matching the search criteria",
    )

    count: int = Field(
        ...,
        ge=0,
        description="Number of resources in this response",
    )

    offset: int = Field(
        ...,
        ge=0,
        description="Zero-based offset of the first resource in this response",
    )


class SearchResultLinks(BaseModel):
    """Pagination links for search results"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "self": "/api/v2/spp/Individual?name=Santos&_count=20",
                "next": "/api/v2/spp/Individual?name=Santos&_count=20&_offset=20",
                "prev": None,
            }
        }
    )

    self: str = Field(
        ...,
        description="URL for the current page of results",
    )

    next: str | None = Field(
        None,
        description="URL for the next page of results, null if on last page",
    )

    prev: str | None = Field(
        None,
        description="URL for the previous page of results, null if on first page",
    )


class SearchResult(BaseModel):
    """Envelope for paginated search results"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
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
                            "text": "SANTOS, Maria",
                        },
                        "birthDate": "1985-03-15",
                    },
                    {
                        "type": "Individual",
                        "identifier": [
                            {
                                "system": "urn:gov:ph:psa:national-id",
                                "value": "PH-987654321",
                            }
                        ],
                        "active": True,
                        "name": {
                            "family": "SANTOS",
                            "given": "Juan",
                            "text": "SANTOS, Juan",
                        },
                        "birthDate": "1980-07-22",
                    },
                ],
                "meta": {
                    "total": 100,
                    "count": 2,
                    "offset": 0,
                },
                "links": {
                    "self": "/api/v2/spp/Individual?name=Santos&_count=2",
                    "next": "/api/v2/spp/Individual?name=Santos&_count=2&_offset=2",
                    "prev": None,
                },
            }
        }
    )

    data: list[dict[str, Any]] = Field(
        ...,
        description="Array of resources matching the search criteria",
    )

    meta: SearchResultMeta = Field(
        ...,
        description="Pagination metadata",
    )

    links: SearchResultLinks = Field(
        ...,
        description="Pagination links",
    )


def create_search_result(
    data: list[dict[str, Any]],
    total: int,
    offset: int,
    self_url: str,
    next_url: str | None = None,
    prev_url: str | None = None,
) -> SearchResult:
    """Helper function to construct a SearchResult response.

    Args:
        data: List of resource dictionaries to include in the response
        total: Total number of resources matching the search criteria
        offset: Zero-based offset of the first resource in this response
        self_url: URL for the current page of results
        next_url: URL for the next page of results (None if on last page)
        prev_url: URL for the previous page of results (None if on first page)

    Returns:
        SearchResult instance ready for JSON serialization

    Example:
        >>> resources = [{"type": "Individual", "identifier": [...], ...}]
        >>> result = create_search_result(
        ...     data=resources,
        ...     total=100,
        ...     offset=0,
        ...     self_url="/api/v2/spp/Individual?name=Santos&_count=20",
        ...     next_url="/api/v2/spp/Individual?name=Santos&_count=20&_offset=20",
        ...     prev_url=None,
        ... )
    """
    return SearchResult(
        data=data,
        meta=SearchResultMeta(
            total=total,
            count=len(data),
            offset=offset,
        ),
        links=SearchResultLinks(
            self=self_url,
            next=next_url,
            prev=prev_url,
        ),
    )
