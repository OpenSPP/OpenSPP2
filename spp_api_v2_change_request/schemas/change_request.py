# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pydantic schemas for Change Request API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChangeRequestType(BaseModel):
    """Change request type reference."""

    code: str = Field(..., description="Type code (e.g., add_member, edit_individual)")
    name: str | None = Field(None, description="Human-readable type name")


class RegistrantRef(BaseModel):
    """Reference to a registrant."""

    system: str = Field(..., description="Identifier namespace URI")
    value: str = Field(..., description="Identifier value")
    display: str | None = Field(None, description="Display name")


class ChangeRequestMeta(BaseModel):
    """Metadata for change request."""

    version_id: str | None = Field(None, alias="versionId")
    last_updated: datetime | None = Field(None, alias="lastUpdated")
    source: str | None = Field(None, description="Source system URI")

    class Config:
        populate_by_name = True


class ChangeRequestCreate(BaseModel):
    """Schema for creating a new change request."""

    type: Literal["ChangeRequest"] = Field(
        "ChangeRequest",
    )

    # Request type (required)
    request_type: ChangeRequestType = Field(
        ...,
        alias="requestType",
        description="Type of change request",
    )

    # Target registrant (required)
    registrant: RegistrantRef = Field(
        ...,
        description="Registrant this change applies to",
    )

    # Applicant (optional - person submitting on behalf)
    applicant: RegistrantRef | None = Field(
        None,
        description="Person submitting the request",
    )
    applicant_phone: str | None = Field(None, alias="applicantPhone")

    # Detail data (type-specific fields)
    detail: dict[str, Any] | None = Field(
        None,
        description="Type-specific detail fields",
    )

    # Description and notes
    description: str | None = None
    notes: str | None = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "type": "ChangeRequest",
                "requestType": {"code": "edit_individual"},
                "registrant": {
                    "system": "urn:gov:ph:psa:national-id",
                    "value": "PH-123456789",
                },
                "detail": {
                    "given_name": "Maria",
                    "family_name": "Santos",
                    "phone": "+639171234567",
                },
            }
        }


class ChangeRequestResponse(BaseModel):
    """Schema for change request response."""

    type: Literal["ChangeRequest"] = Field(
        "ChangeRequest",
    )

    # Reference (e.g., CR/2024/00001)
    reference: str = Field(..., description="Change request reference number")

    # Type
    request_type: ChangeRequestType = Field(..., alias="requestType")

    # Status
    status: str = Field(
        ...,
        description="Current status",
        json_schema_extra={"enum": ["draft", "pending", "revision", "approved", "rejected", "applied"]},
    )

    # Target registrant
    registrant: RegistrantRef

    # Applicant
    applicant: RegistrantRef | None = None
    applicant_phone: str | None = Field(None, alias="applicantPhone")

    # Detail data
    detail: dict[str, Any] | None = None

    # Application tracking
    is_applied: bool = Field(False, alias="isApplied")
    applied_date: datetime | None = Field(None, alias="appliedDate")
    apply_error: str | None = Field(None, alias="applyError")

    # Approval tracking
    submitted_date: datetime | None = Field(None, alias="submittedDate")
    approved_date: datetime | None = Field(None, alias="approvedDate")
    rejected_date: datetime | None = Field(None, alias="rejectedDate")
    rejection_reason: str | None = Field(None, alias="rejectionReason")
    revision_notes: str | None = Field(None, alias="revisionNotes")

    # Description and notes
    description: str | None = None
    notes: str | None = None

    # Metadata
    meta: ChangeRequestMeta | None = None

    class Config:
        populate_by_name = True


class ChangeRequestUpdate(BaseModel):
    """Schema for updating change request detail data."""

    detail: dict[str, Any] = Field(
        ...,
        description="Type-specific detail fields to update",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "detail": {
                    "given_name": "Maria Elena",
                    "phone": "+639171234568",
                }
            }
        }


class ApproveActionData(BaseModel):
    """Data for approve action."""

    comment: str | None = Field(
        None,
        description="Optional comment for approval",
    )


class RejectActionData(BaseModel):
    """Data for reject action."""

    reason: str = Field(
        ...,
        description="Reason for rejection (required)",
        min_length=1,
    )


class RequestRevisionActionData(BaseModel):
    """Data for request-revision action."""

    notes: str = Field(
        ...,
        description="Notes explaining what needs revision (required)",
        min_length=1,
    )


class FieldChoice(BaseModel):
    """Value/label pair for selection choices, vocabulary codes, and documents."""

    value: str = Field(..., description="Machine-readable value or code")
    label: str = Field(..., description="Human-readable display label")


class VocabularyInfo(BaseModel):
    """Vocabulary namespace and available codes for a vocabulary field."""

    namespace_uri: str = Field(..., alias="namespaceUri", description="Vocabulary namespace URI")
    codes: list[FieldChoice] = Field(default_factory=list, description="Available codes")

    class Config:
        populate_by_name = True


class FieldDefinition(BaseModel):
    """Schema definition for a single field on a CR detail model."""

    name: str = Field(..., description="Field name")
    label: str = Field(..., description="Human-readable field label")
    type: str = Field(
        ...,
        description="Field type (string, text, integer, float, boolean, date, datetime, selection, code, reference)",
    )
    required: bool = Field(False, description="Whether the field is required")
    readonly: bool = Field(False, description="Whether the field is read-only or computed")
    help: str | None = Field(None, description="Help text for the field")
    choices: list[FieldChoice] | None = Field(None, description="Available choices for selection fields")
    vocabulary: VocabularyInfo | None = Field(None, description="Vocabulary info for code fields")


class ChangeRequestTypeInfo(BaseModel):
    """Summary info for a CR type."""

    code: str = Field(..., description="Type code (e.g., add_member)")
    name: str = Field(..., description="Human-readable type name")
    target_type: str = Field(..., alias="targetType", description="Target registrant type (individual, group, both)")
    requires_applicant: bool = Field(False, alias="requiresApplicant", description="Whether an applicant is required")

    class Config:
        populate_by_name = True


class ChangeRequestTypeSchema(BaseModel):
    """Full schema for a CR type including field definitions."""

    type_info: ChangeRequestTypeInfo = Field(..., alias="typeInfo", description="Type summary")
    fields: list[FieldDefinition] = Field(default_factory=list, description="Available detail fields")
    available_documents: list[FieldChoice] = Field(
        default_factory=list, alias="availableDocuments", description="Documents that can be attached"
    )
    required_documents: list[FieldChoice] = Field(
        default_factory=list, alias="requiredDocuments", description="Documents that must be attached"
    )

    class Config:
        populate_by_name = True
