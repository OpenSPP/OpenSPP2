# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tolerant Pydantic schemas for Registry Notary payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NotaryBaseModel(BaseModel):
    """Base schema that accepts extra fields while the upstream schema settles."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Subject(NotaryBaseModel):
    """Notary subject reference."""

    id: str
    id_type: str | None = None


class ClaimRef(NotaryBaseModel):
    """Claim reference, with optional version for future Notary schema support."""

    id: str
    version: str | None = None


class ClaimMetadata(NotaryBaseModel):
    """Catalog metadata for a Notary claim."""

    id: str
    title: str | None = None
    description: str | None = None
    version: str | None = None
    subject_type: str | None = None
    value_type: str | None = None
    default_disclosure: str | None = None
    allowed_disclosures: list[str] = Field(default_factory=list)
    supported_formats: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_current_aliases(cls, values):
        if not isinstance(values, dict):
            return values
        values = dict(values)
        if "title" not in values and "name" in values:
            values["title"] = values["name"]
        if "value_type" not in values and "type" in values:
            values["value_type"] = values["type"]
        if "supported_formats" not in values and "formats" in values:
            values["supported_formats"] = values["formats"]
        return values


class CatalogResponse(NotaryBaseModel):
    """Response from GET /claims."""

    claims: list[ClaimMetadata] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_data_wrapper(cls, values):
        if not isinstance(values, dict):
            return values
        values = dict(values)
        if "claims" not in values and "data" in values:
            values["claims"] = values["data"]
        return values


class EvidenceServiceMetadata(NotaryBaseModel):
    """Minimal .well-known/evidence-service metadata shape."""

    issuer: str | None = None
    claims_endpoint: str | None = None
    evaluate_endpoint: str | None = None
    batch_evaluate_endpoint: str | None = None
    jwks_uri: str | None = None


class EvaluateRequest(NotaryBaseModel):
    """Request body for POST /claims/evaluate."""

    subject: Subject
    claims: list[str | ClaimRef]
    purpose: str
    disclosure: str | None = None
    format: str | None = None


class ClaimResult(NotaryBaseModel):
    """A single evaluated Notary claim."""

    claim_id: str | None = None
    claim_version: str | None = None
    value_type: str | None = None
    value: Any = None
    satisfied: bool | None = None
    disclosure: str | None = None
    format: str | None = None
    expires_at: str | None = None
    provenance: dict[str, Any] | None = None


class EvaluateResponse(NotaryBaseModel):
    """Response from POST /claims/evaluate."""

    evaluation_id: str | None = None
    results: list[ClaimResult] = Field(default_factory=list)
    created_at: str | None = None
    expires_at: str | None = None


class BatchEvaluateRequest(NotaryBaseModel):
    """Request body for POST /claims/batch-evaluate."""

    subjects: list[Subject]
    claims: list[str | ClaimRef]
    purpose: str
    disclosure: str | None = None
    format: str | None = None


class BatchItem(NotaryBaseModel):
    """One subject's result in a batch evaluation response."""

    input_index: int | None = None
    subject: Subject | None = None
    subject_ref: dict[str, Any] | None = None
    status: Literal["succeeded", "failed"] | str
    results: list[ClaimResult] = Field(default_factory=list)
    claim_results: list[ClaimResult] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_result_aliases(cls, values):
        if not isinstance(values, dict):
            return values
        values = dict(values)
        if "results" not in values and "claim_results" in values:
            values["results"] = values["claim_results"]
        if "claim_results" not in values and "results" in values:
            values["claim_results"] = values["results"]
        return values


class BatchEvaluateResponse(NotaryBaseModel):
    """Response from POST /claims/batch-evaluate."""

    batch_id: str | None = None
    status: str | None = None
    claims: list[ClaimMetadata | str] = Field(default_factory=list)
    items: list[BatchItem] = Field(default_factory=list)
    summary: dict[str, Any] | None = None
