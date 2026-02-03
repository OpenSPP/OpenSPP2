# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Operation outcome schema for error responses"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import CodeableConcept


class OperationOutcomeIssue(BaseModel):
    """Individual issue in an operation outcome"""

    severity: str = Field(..., pattern="^(fatal|error|warning|information)$")
    code: str
    details: CodeableConcept | None = None
    diagnostics: str | None = None
    location: list[str] | None = None


class OperationOutcome(BaseModel):
    """Error or warning response"""

    resource_type: Literal["OperationOutcome"] = Field(
        "OperationOutcome",
        alias="resourceType",
    )

    issue: list[OperationOutcomeIssue] = Field(..., min_length=1)

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "invalid",
                        "details": {
                            "coding": [
                                {
                                    "system": "urn:openspp:error",
                                    "code": "INVALID_IDENTIFIER",
                                    "display": "Invalid identifier format",
                                }
                            ],
                            "text": "Identifier value contains invalid characters",
                        },
                        "diagnostics": "identifier[0].value: expected pattern ^[A-Z0-9-]+$",
                        "location": ["Individual.identifier[0].value"],
                    }
                ],
            }
        },
    )
