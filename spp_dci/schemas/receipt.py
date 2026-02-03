# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Receipt schemas for delivery confirmation.

SPDCI compliant receipt schema per:
spdci-api-standards/src/registry/social/ReceiptRequest.yaml
spdci-api-standards/src/extensions/social/ReceiptInformation.yaml

Receipt API enables external systems to confirm receipt of async notifications,
completing the reliable delivery pattern for DCI subscriptions.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ReceiptType(str, Enum):
    """Receipt types per SPDCI RegistryEventType.

    Indicates what kind of notification is being acknowledged.
    """

    REGISTER = "register"
    PAYMENT = "payment"
    DEREGISTER = "deregister"
    ENROLLMENT = "enrollment"
    ENROLLMENT_STATUS_CHANGE = "enrollment_status_change"
    UPDATE = "update"
    DELETE = "delete"
    NOTIFICATION = "notification"  # Generic notification receipt


class BeneficiaryRef(BaseModel):
    """Reference to a beneficiary in receipt confirmation.

    Minimal identifying information to match against notification records.
    """

    model_config = ConfigDict(populate_by_name=True)

    identifier_type: str | None = Field(
        None,
        description="Type of identifier (e.g., 'ns:org:id_type:national_id')",
    )
    identifier_value: str | None = Field(
        None,
        description="Identifier value",
    )
    reference_id: str | None = Field(
        None,
        description="Reference ID from original notification",
    )


class ReceiptInformation(BaseModel):
    """Receipt information per SPDCI spec.

    Contains the receipt type and optional list of confirmed beneficiaries.
    """

    model_config = ConfigDict(populate_by_name=True)

    receipt_type: ReceiptType = Field(
        ...,
        description="Type of receipt: register, payment, deregister, etc.",
    )
    subscription_code: str | None = Field(
        None,
        description="Subscription code the notification was sent for",
    )
    notification_id: str | None = Field(
        None,
        description="ID of the notification being acknowledged (from X-DCI-Notification-ID header)",
    )
    beneficiaries: list[BeneficiaryRef] | None = Field(
        None,
        description="List of beneficiaries confirmed in receipt (optional)",
    )
    received_at: datetime | None = Field(
        None,
        description="When the notification was received by the external system",
    )
    processed_at: datetime | None = Field(
        None,
        description="When the notification was processed by the external system",
    )
    error_message: str | None = Field(
        None,
        description="Error message if notification processing failed",
    )


class ReceiptRequest(BaseModel):
    """DCI receipt request message.

    Sent by external systems to confirm receipt of async notifications.
    """

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Unique transaction identifier for this receipt",
    )
    receipt_information: ReceiptInformation = Field(
        ...,
        description="Receipt details",
    )


class ReceiptResponseItem(BaseModel):
    """Individual receipt confirmation response."""

    model_config = ConfigDict(populate_by_name=True)

    reference_id: str = Field(
        ...,
        description="Reference ID for this receipt response",
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
        description="Human-readable status message",
    )


class ReceiptResponse(BaseModel):
    """DCI receipt response message."""

    model_config = ConfigDict(populate_by_name=True)

    transaction_id: str = Field(
        ...,
        description="Original transaction ID from request",
    )
    correlation_id: str | None = Field(
        None,
        description="Correlation ID for tracking",
    )
    receipt_response: list[ReceiptResponseItem] = Field(
        ...,
        description="List of receipt responses",
    )
