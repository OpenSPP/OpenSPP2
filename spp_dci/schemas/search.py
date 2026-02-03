"""DCI Search schema types."""

from datetime import datetime
from typing import Any

from pydantic import AnyUrl, BaseModel, ConfigDict, Field


class Purpose(BaseModel):
    """Purpose details for consent or authorization."""

    model_config = ConfigDict(populate_by_name=True)

    code: str = Field(
        ...,
        description="Code indicating the purpose",
    )
    text: str | None = Field(
        None,
        description="Human-readable description of the purpose",
    )
    ref_uri: AnyUrl | str | None = Field(
        None,
        description="Reference URI for additional information",
    )


class Consent(BaseModel):
    """Consent information for data use."""

    model_config = ConfigDict(populate_by_name=True)

    ts: datetime = Field(
        ...,
        description="Timestamp when consent was provided",
    )
    purpose: Purpose = Field(
        ...,
        description="Details about the purpose of consent",
    )


class Authorize(BaseModel):
    """Authorization information for data access or processing."""

    model_config = ConfigDict(populate_by_name=True)

    ts: datetime = Field(
        ...,
        description="Timestamp when authorization was granted",
    )
    purpose: Purpose = Field(
        ...,
        description="Details about the purpose of authorization",
    )


class PaginationRequest(BaseModel):
    """Pagination parameters for search requests."""

    model_config = ConfigDict(populate_by_name=True)

    page_size: int = Field(
        ...,
        description="Number of records per page",
        gt=0,
    )
    page_number: int = Field(
        1,
        description="Page number (1-indexed)",
        gt=0,
    )
    # OpenSPP extension: cursor-based pagination
    cursor: str | None = Field(
        None,
        description="Cursor for efficient pagination (OpenSPP extension). When provided, page_number is ignored.",
    )


class Pagination(BaseModel):
    """Pagination information for search responses."""

    model_config = ConfigDict(populate_by_name=True)

    page_size: int = Field(
        ...,
        description="Number of records per page",
        gt=0,
    )
    page_number: int = Field(
        ...,
        description="Current page number (1-indexed)",
        gt=0,
    )
    total_count: int = Field(
        ...,
        description="Total number of records matching the search criteria",
        ge=0,
    )
    # OpenSPP extension: cursor-based pagination
    next_cursor: str | None = Field(
        None,
        description="Cursor to fetch next page (OpenSPP extension). None if no more records.",
    )


class SearchSort(BaseModel):
    """Sorting parameters for search results."""

    model_config = ConfigDict(populate_by_name=True)

    attribute_name: str = Field(
        ...,
        description="Name of the attribute to sort by",
    )
    sort_order: str = Field(
        ...,
        description="Sort order: 'asc' for ascending, 'desc' for descending",
        pattern="^(asc|desc)$",
    )


class IdTypeValueQuery(BaseModel):
    """Simple identifier lookup query by type and value."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(
        ...,
        description="Identifier type (UIN, BRN, MRN, DRN, etc.)",
    )
    value: str = Field(
        ...,
        description="Identifier value",
    )


class ExpressionCondition(BaseModel):
    """Single condition in a query expression."""

    model_config = ConfigDict(populate_by_name=True)

    attribute: str = Field(
        ...,
        description="Attribute name to query",
    )
    operator: str = Field(
        ...,
        description="Comparison operator: =, >, <, >=, <=, in, contains",
    )
    value: Any = Field(
        ...,
        description="Value to compare against",
    )


class Expression(BaseModel):
    """Query expression with AND/OR logic.

    - seq: list of conditions combined with AND logic
    - or_: list of expressions combined with OR logic
    """

    model_config = ConfigDict(populate_by_name=True)

    seq: list[ExpressionCondition] | None = Field(
        None,
        description="Sequential conditions (AND logic)",
    )
    or_: list["Expression"] | None = Field(
        None,
        alias="or",
        description="Alternative expressions (OR logic)",
    )


class SearchCriteria(BaseModel):
    """Search criteria specification."""

    model_config = ConfigDict(populate_by_name=True)

    version: str = Field(
        "1.0.0",
        description="API version",
    )
    reg_type: str | None = Field(
        None,
        description="Registry type: SOCIAL_REGISTRY, IBR, CRVS, DR, FR (optional per SPDCI spec)",
    )
    reg_event_type: str | None = Field(
        None,
        description="Registry event type (BIRTH, DEATH, REGISTRATION, etc.)",
    )
    query_type: str = Field(
        ...,
        description="Query type: idtype-value, expression, predicate, graphql",
    )
    query: Any = Field(
        ...,
        description="Query object (IdTypeValueQuery, Expression, or other query types)",
    )
    sort: list[SearchSort] | None = Field(
        None,
        description="Sort specifications",
    )
    pagination: PaginationRequest | None = Field(
        None,
        description="Pagination parameters",
    )
    consent: Consent | None = Field(
        None,
        description="Consent information for data use",
    )
    authorize: Authorize | None = Field(
        None,
        description="Authorization information for data access or processing",
    )


class SearchRequestItem(BaseModel):
    """Individual search request item."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(
        ...,
        description="Unique reference ID for this search request",
    )
    timestamp: datetime = Field(
        ...,
        description="Request timestamp",
    )
    search_criteria: SearchCriteria = Field(
        ...,
        description="Search criteria specification",
    )
    locale: str | None = Field(
        None,
        description="Language/locale code (e.g., 'en', 'es', 'fr')",
    )


class SearchRequest(BaseModel):
    """DCI Search Request message payload."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Unique transaction identifier",
    )
    correlation_id: str | None = Field(
        None,
        description="Correlation identifier for tracking related messages",
    )
    search_request: list[SearchRequestItem] = Field(
        ...,
        description="List of search request items (batch support)",
    )


class SearchResponseData(BaseModel):
    """Search response data containing registry records."""

    model_config = ConfigDict(populate_by_name=True)

    version: str = Field(
        "1.0.0",
        description="API version",
    )
    reg_type: str = Field(
        ...,
        description="Registry type: SOCIAL_REGISTRY, IBR, CRVS, DR, FR",
    )
    reg_event_type: str | None = Field(
        None,
        description="Registry event type",
    )
    reg_record_type: str = Field(
        ...,
        description="Record type: PERSON, GROUP, BENEFICIARY, FARMER, PWD_PERSON",
    )
    reg_records: list[Any] = Field(
        ...,
        description="List of registry records (Person, Group, etc.)",
    )


class SearchResponseItem(BaseModel):
    """Individual search response item."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(
        ...,
        description="Reference ID matching the request",
    )
    timestamp: datetime = Field(
        ...,
        description="Response timestamp",
    )
    status: str = Field(
        ...,
        description="Request status: rcvd, pdng, succ, rjct",
    )
    status_reason_code: str | None = Field(
        None,
        description="Status reason code for rejected/failed requests",
    )
    status_reason_message: str | None = Field(
        None,
        description="Human-readable status reason message",
        max_length=999,
    )
    data: SearchResponseData | None = Field(
        None,
        description="Search result data (only present for successful searches)",
    )
    pagination: Pagination | None = Field(
        None,
        description="Pagination information for the response",
    )
    locale: str | None = Field(
        None,
        description="Language/locale code",
    )


class SearchResponse(BaseModel):
    """DCI Search Response message payload."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Transaction identifier matching the request",
    )
    correlation_id: str | None = Field(
        None,
        description="Correlation identifier for tracking related messages",
    )
    search_response: list[SearchResponseItem] = Field(
        ...,
        description="List of search response items",
    )


# Update forward references for recursive Expression model
Expression.model_rebuild()
