# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Subscription schemas for event notifications.

SPDCI compliant subscription schema per:
spdci-api-standards/release/yaml/social_api_v1.0.0.yaml
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SubscribeCriteria(BaseModel):
    """Subscribe criteria specification per SPDCI spec.

    Required fields:
    - reg_event_type: Type of event to subscribe to
    - filter: Filter criteria for matching events
    - notify_record_type: Type of records to notify about
    """

    model_config = ConfigDict(populate_by_name=True)

    version: str = Field(
        default="1.0.0",
        description="API version",
    )
    reg_type: str | None = Field(
        None,
        description="Registry type (optional)",
    )
    reg_event_type: str = Field(
        ...,
        description="Registry event type (BIRTH, DEATH, REGISTRATION, UPDATE, etc.)",
    )
    frequency: str | None = Field(
        None,
        description="Notification frequency (immediate, daily, weekly, etc.)",
    )
    filter_type: str | None = Field(
        None,
        description="Filter type (idtype-value, expression, predicate, graphql)",
    )
    filter: Any = Field(
        ...,
        description="Filter criteria for matching events",
    )
    notify_record_type: str = Field(
        ...,
        description="Type of records to notify about (e.g., 'spdci-extensions-dci:Member')",
    )
    response_entity: str | None = Field(
        None,
        description="Entity type for response data",
    )
    response_fields: list[str] | None = Field(
        None,
        description="Specific fields to include in response",
    )
    authorize: Any | None = Field(
        None,
        description="Authorization information",
    )


class SubscribeRequestItem(BaseModel):
    """Individual subscription request per SPDCI spec."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(
        ...,
        description="Unique reference for this subscription request",
    )
    timestamp: datetime = Field(
        ...,
        description="Request timestamp",
    )
    subscribe_criteria: SubscribeCriteria = Field(
        ...,
        description="Subscription criteria specification",
    )
    locale: str | None = Field(
        None,
        description="ISO 639-3 language code for responses",
    )


class SubscribeRequest(BaseModel):
    """DCI subscribe request message."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Unique transaction identifier",
    )
    subscribe_request: list[SubscribeRequestItem] = Field(
        ...,
        description="List of subscription requests",
    )


class SubscribeResponseItem(BaseModel):
    """Individual subscription response."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(
        ...,
        description="Reference ID from original request",
    )
    subscription_code: str | None = Field(
        None,
        description="Assigned subscription code if successful",
    )
    timestamp: datetime = Field(
        ...,
        description="Processing timestamp",
    )
    status: str = Field(
        ...,
        description="Status code (succ, rjct)",
    )
    status_reason_code: str | None = Field(
        None,
        description="Machine-readable error code",
    )
    status_reason_message: str | None = Field(
        None,
        description="Human-readable error message",
    )


class SubscribeResponse(BaseModel):
    """DCI subscribe response message."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Original transaction ID",
    )
    correlation_id: str | None = Field(
        None,
        description="Correlation ID for tracking",
    )
    subscribe_response: list[SubscribeResponseItem] = Field(
        ...,
        description="List of subscription responses",
    )


class UnsubscribeRequest(BaseModel):
    """DCI unsubscribe request message per SPDCI spec."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Unique transaction identifier",
    )
    timestamp: datetime = Field(
        ...,
        description="Request timestamp",
    )
    subscription_codes: list[str] = Field(
        ...,
        description="List of unsubscribe requests",
    )


class UnsubscribeResponseItem(BaseModel):
    """Individual unsubscribe response."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(
        ...,
        description="Reference ID from original request",
    )
    timestamp: datetime = Field(
        ...,
        description="Processing timestamp",
    )
    status: str = Field(
        ...,
        description="Status code (succ, rjct)",
    )
    status_reason_code: str | None = Field(
        None,
        description="Machine-readable error code",
    )
    status_reason_message: str | None = Field(
        None,
        description="Human-readable error message",
    )


class UnsubscribeResponse(BaseModel):
    """DCI unsubscribe response message."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Original transaction ID",
    )
    correlation_id: str | None = Field(
        None,
        description="Correlation ID for tracking",
    )
    unsubscribe_response: list[UnsubscribeResponseItem] = Field(
        ...,
        description="List of unsubscribe responses",
    )


class TxnStatusRequestCriteria(BaseModel):
    """Transaction status request criteria per SPDCI spec."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(
        ...,
        description="Unique reference_id for this status request",
    )
    txn_type: str = Field(
        ...,
        description="Transaction type to fetch status (search, subscribe, receipt)",
    )
    attribute_type: str = Field(
        ...,
        description="Attribute type (transaction_id, reference_id_list, correlation_id)",
    )
    attribute_value: str | list[str] = Field(
        ...,
        description="Attribute value - transaction ID, list of reference IDs, or correlation ID",
    )


class TxnStatusRequest(BaseModel):
    """DCI transaction status request per SPDCI spec."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Unique transaction identifier for this status request",
    )
    txnstatus_request: TxnStatusRequestCriteria = Field(
        ...,
        description="Transaction status request criteria",
    )


class TxnStatusResponseData(BaseModel):
    """Transaction status response data per SPDCI spec.

    This is a single object (not a list) containing the status of the queried transaction.
    The txn_status field contains the actual response object (SearchResponse,
    SubscribeResponse, or UnSubscribeResponse) from the original transaction.
    """

    model_config = ConfigDict(populate_by_name=True)

    txn_type: str = Field(
        ...,
        description="Transaction type: search, subscribe, receipt (matches request txn_type per SPDCI spec)",
    )
    txn_status: Any = Field(
        ...,
        description="The actual response object (SearchResponse, SubscribeResponse, or UnSubscribeResponse)",
    )


class TxnStatusResponse(BaseModel):
    """DCI transaction status response per SPDCI spec."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Original request transaction ID",
    )
    correlation_id: str = Field(
        ...,
        description="Correlation ID for tracking (required per SPDCI)",
    )
    txnstatus_response: TxnStatusResponseData = Field(
        ...,
        description="Transaction status response object",
    )
