"""DCI envelope schemas for the DR-side register endpoint.

The register endpoint complements the existing read-only search endpoint
with a write path: the SP issues a signed DCI envelope to create or
update partner records on the DR, keyed by UIN reg_id.

Why a custom action vs. reusing search semantics:

    DCI's standard MessageAction enum doesn't define a generic
    "create-individual" operation. ENROLLMENT exists but means program
    enrollment, not registrant onboarding. We use the action name
    ``register-individual`` and shape the message around the same
    transaction_id + per-item reference_id pattern the search side
    uses, so the response can carry per-item status under partial
    success.
"""

from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterIndividualItem(BaseModel):
    """One person to register on the DR."""

    model_config = ConfigDict(extra="forbid")

    reference_id: str
    uin: str
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    sex: str | None = None
    birth_date: date_type | None = None
    # SR-sourced self-report: when true, the DR's register service
    # creates a DRAFT spp.disability.assessment for assessor review
    # (only if no assessment exists yet for this registrant). WG fields
    # are left blank — the assessor populates them during interview.
    is_disabled: bool = False


class RegisterRequest(BaseModel):
    """Payload of a DCI register envelope (message body)."""

    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    register_request: list[RegisterIndividualItem] = Field(default_factory=list)
    refresh_existing: bool = False


class RegisterResponseItem(BaseModel):
    """One register result, paired by reference_id with the request item."""

    model_config = ConfigDict(extra="allow")

    reference_id: str
    timestamp: datetime
    status: str  # 'succ' | 'rjct'
    status_reason_code: str | None = None
    status_reason_message: str | None = None
    operation: str | None = None  # 'created' | 'updated' | 'skipped'
    local_partner_id: int | None = None
    uin: str | None = None
    # True when the register service created a new draft disability
    # assessment for this registrant (only happens when is_disabled=true
    # was set AND no prior assessment exists). Useful for the SP-side
    # summary so operators see assessor-backlog counts at a glance.
    draft_assessment_created: bool | None = None


class RegisterResponse(BaseModel):
    """Response payload (under DCI envelope.message)."""

    model_config = ConfigDict(extra="allow")

    transaction_id: str
    correlation_id: str
    register_response: list[RegisterResponseItem] = Field(default_factory=list)
