"""DCI message envelope schemas.

Implements the three-part DCI message structure:
1. Signature - HTTP Signature for message authentication
2. Header - Message metadata (request or callback)
3. Message - The actual payload (Any type, validated by specific endpoints)
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .constants import RequestStatus


class DCIMessageHeader(BaseModel):
    """DCI Message Header for requests.

    Contains routing, identification, and protocol metadata for DCI messages.
    Used in all request messages (search, subscribe, notify, etc.).
    """

    model_config = ConfigDict(populate_by_name=True)

    version: str = Field(
        default="1.0.0",
        description="Messaging protocol specification version being used",
    )
    message_id: str = Field(
        ...,
        description="Unique message ID for reliable delivery across transport layers",
    )
    message_ts: datetime = Field(
        ...,
        description="Message timestamp",
    )
    action: str = Field(
        ...,
        description="DCI Connect action (search, subscribe, notify, unsubscribe, etc.)",
    )
    sender_id: str = Field(
        ...,
        description="Sender ID registered with receiving system (for auth, encryption, signature verification)",
    )
    sender_uri: str | None = Field(
        None,
        description="Sender URL for async callbacks (e.g., https://spp.example.org/callback/on-search)",
    )
    receiver_id: str = Field(
        ...,
        description="Receiver ID registered with calling system (for auth, encryption, signature verification)",
    )
    total_count: int = Field(
        default=0,
        description="Total number of requests present in the message",
    )
    is_msg_encrypted: bool = Field(
        default=False,
        description="Whether the message payload is encrypted",
    )
    meta: dict | None = Field(
        None,
        description="Additional metadata as key-value pairs",
    )


class DCICallbackHeader(DCIMessageHeader):
    """DCI Callback Header for responses.

    Extends DCIMessageHeader with status tracking for async callbacks.
    Used in all response/callback messages (on-search, on-subscribe, etc.).
    """

    status: RequestStatus = Field(
        ...,
        description="Request processing status (rcvd, pdng, succ, rjct)",
    )
    status_reason_code: str | None = Field(
        None,
        description="Machine-readable status reason code for errors",
    )
    status_reason_message: str | None = Field(
        None,
        max_length=999,
        description="Human-readable status message for actionable feedback",
    )
    completed_count: int = Field(
        default=0,
        description="Number of requests in completed state (includes success and functional errors)",
    )


class DCIEnvelope(BaseModel):
    """DCI three-part message envelope.

    Wraps all DCI messages with:
    1. Signature - HTTP Signature for authentication/integrity
    2. Header - Routing and status metadata
    3. Message - The actual payload (type varies by action)
    """

    model_config = ConfigDict(populate_by_name=True)

    signature: str = Field(
        ...,
        description="HTTP Signature of {header}+{message} verified using sender's public key",
    )
    header: DCIMessageHeader | DCICallbackHeader = Field(
        ...,
        description="Message metadata (DCIMessageHeader for requests, DCICallbackHeader for responses)",
    )
    message: Any = Field(
        ...,
        description="Message payload (type depends on action: SearchRequest, SubscribeRequest, etc.)",
    )
