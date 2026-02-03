# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for Consent API endpoints."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ConsentScopeSchema(BaseModel):
    """Schema for consent scope details."""

    resource_type: str = Field(..., description="Type of resource covered")
    field_access: str = Field(..., description="Level of field access")
    purpose: str = Field(..., description="Purpose of data processing")
    include_extensions: bool = Field(default=False)


class ConsentStatusResponse(BaseModel):
    """Schema for consent status check response.

    Status values align with W3C Data Privacy Vocabulary (DPV) ConsentStatus.
    """

    consent_id: str = Field(..., description="External consent identifier")
    # DPV-aligned status values
    status: Literal[
        "requested",  # dpv:ConsentRequested
        "given",  # dpv:ConsentGiven
        "renewed",  # dpv:RenewedConsentGiven
        "refused",  # dpv:ConsentRefused
        "withdrawn",  # dpv:ConsentWithdrawn
        "expired",  # dpv:ConsentExpired
        "invalidated",  # dpv:ConsentInvalidated
        "not_found",  # Not a DPV status - indicates consent doesn't exist
    ]
    grantee: str | None = Field(None, description="Organization granted access")
    effective_date: date | None = None
    expiry_date: date | None = None
    scopes: list[ConsentScopeSchema] = Field(default_factory=list)
    legal_basis: str | None = None


class ConsentRevokeRequest(BaseModel):
    """Schema for consent revocation request."""

    reason: str | None = Field(
        None,
        description="Reason for revoking consent",
        max_length=1000,
    )


class ConsentRevokeResponse(BaseModel):
    """Schema for consent withdrawal response.

    Uses DPV terminology: 'withdrawn' instead of 'revoked'.
    """

    consent_id: str
    status: Literal["withdrawn"] = "withdrawn"  # dpv:ConsentWithdrawn
    revoked_at: datetime = Field(..., description="When consent was withdrawn")
    message: str = "Consent has been successfully withdrawn"


class ConsentReceiptSchema(BaseModel):
    """
    Consent receipt per ISO/IEC 29184 and Kantara Initiative.

    Provides proof of consent to the data subject.
    """

    receipt_id: str = Field(..., description="Unique receipt identifier")
    version: str = Field(default="1.0", description="Receipt format version")
    timestamp: datetime = Field(..., description="When receipt was generated")

    # Data Subject
    data_subject: dict = Field(
        ...,
        description="Identifier for the data subject (no PII)",
    )

    # Data Controller
    data_controller: dict = Field(
        ...,
        description="Organization responsible for data processing",
    )

    # Consent Details
    consent_id: str = Field(..., description="Consent record identifier")
    consent_date: date = Field(..., description="When consent was given")
    collection_method: str | None = Field(
        None,
        description="How consent was collected",
    )

    # What was consented to
    purposes: list[dict] = Field(
        ...,
        description="Purposes for which data processing was consented",
    )
    data_categories: list[str] = Field(
        default_factory=list,
        description="Categories of personal data covered",
    )

    # Validity
    effective_date: date | None = None
    expiry_date: date | None = None

    # Rights
    withdrawal_uri: str = Field(
        ...,
        description="URI to revoke consent",
    )
    data_subject_rights: list[str] = Field(
        default_factory=lambda: [
            "Right to access your data",
            "Right to rectification",
            "Right to erasure",
            "Right to data portability",
            "Right to withdraw consent at any time",
        ],
    )


class ConsentAccessSummarySchema(BaseModel):
    """Schema for consent access summary (for data subject requests)."""

    consent_id: str
    total_accesses: int
    by_action: dict[str, int]
    by_resource_type: dict[str, int]
    by_client: dict[str, int]
    date_range: dict[str, str | None]


class ConsentHistoryEntrySchema(BaseModel):
    """Schema for a single consent history entry."""

    version: int
    action: str
    changed_date: datetime
    changed_by: str | None
    changed_fields: list[str] | None
    reason: str | None


class ConsentHistoryResponse(BaseModel):
    """Schema for consent history response."""

    consent_id: str
    current_version: int
    history: list[ConsentHistoryEntrySchema]
