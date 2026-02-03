# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""RFC 9457 Problem Details schema for standardized HTTP API error responses

This schema replaces FHIR OperationOutcome with a simpler, RFC-compliant error format
for OpenSPP API V2. See https://www.rfc-editor.org/rfc/rfc9457 for the specification.
(RFC 9457 obsoletes RFC 7807.)
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FieldError(BaseModel):
    """Individual field-level validation error"""

    field: str = Field(
        ...,
        description="The field path that contains the error (e.g., 'identifier[0].value')",
        examples=["identifier", "name.given", "birthDate"],
    )
    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["required", "invalid_format", "not_found", "duplicate"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["This field is required", "Invalid date format"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "field": "identifier",
                "code": "not_found",
                "message": "No individual exists with this identifier",
            }
        }
    )


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Details for HTTP API errors

    A standardized format for machine-readable details of errors in HTTP responses.
    This replaces the FHIR OperationOutcome with a simpler, standards-based approach.

    The 'type' field uses URN format: urn:openspp:error:{category}
    Common categories: not-found, validation, authentication, authorization, conflict, server-error
    """

    type: str = Field(
        ...,
        description=(
            "URN identifying the error type (e.g., 'urn:openspp:error:not-found'). "
            "This identifier should be stable across occurrences of the same error type."
        ),
        pattern=r"^urn:openspp:error:[a-z\-]+$",
        examples=[
            "urn:openspp:error:not-found",
            "urn:openspp:error:validation",
            "urn:openspp:error:authentication",
        ],
    )

    title: str = Field(
        ...,
        description="Short, human-readable summary of the error type",
        examples=["Not Found", "Validation Error", "Authentication Required"],
    )

    status: int = Field(
        ...,
        description="HTTP status code for this occurrence",
        ge=100,
        le=599,
        examples=[400, 401, 403, 404, 409, 422, 500],
    )

    detail: str = Field(
        ...,
        description="Human-readable explanation specific to this occurrence of the error",
        examples=[
            "Individual not found with identifier national-id|PH-123",
            "The birth date cannot be in the future",
        ],
    )

    instance: str | None = Field(
        None,
        description="The URI reference that identifies the specific occurrence of the problem",
        examples=[
            "/api/v2/spp/Individual/national-id|PH-123",
            "/api/v2/spp/Group/household|HH-456",
        ],
    )

    errors: list[FieldError] | None = Field(
        None,
        description="Optional list of field-level validation errors",
    )

    # Allow additional extension fields per RFC 9457
    extension: dict[str, Any] | None = Field(
        None,
        description="Additional problem-type-specific extension fields",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "type": "urn:openspp:error:not-found",
                    "title": "Not Found",
                    "status": 404,
                    "detail": "Individual not found with identifier national-id|PH-123",
                    "instance": "/api/v2/spp/Individual/national-id|PH-123",
                    "errors": [
                        {
                            "field": "identifier",
                            "code": "not_found",
                            "message": "No individual exists with this identifier",
                        }
                    ],
                },
                {
                    "type": "urn:openspp:error:validation",
                    "title": "Validation Error",
                    "status": 422,
                    "detail": "Request data contains validation errors",
                    "instance": "/api/v2/spp/Individual",
                    "errors": [
                        {
                            "field": "birthDate",
                            "code": "invalid_value",
                            "message": "Birth date cannot be in the future",
                        },
                        {
                            "field": "identifier",
                            "code": "required",
                            "message": "At least one identifier is required",
                        },
                    ],
                },
                {
                    "type": "urn:openspp:error:authentication",
                    "title": "Authentication Required",
                    "status": 401,
                    "detail": "Valid authentication credentials are required to access this resource",
                    "instance": "/api/v2/spp/Individual/national-id|PH-123",
                },
                {
                    "type": "urn:openspp:error:authorization",
                    "title": "Forbidden",
                    "status": 403,
                    "detail": "You do not have permission to access this individual's data",
                    "instance": "/api/v2/spp/Individual/national-id|PH-123",
                },
                {
                    "type": "urn:openspp:error:conflict",
                    "title": "Conflict",
                    "status": 409,
                    "detail": "Individual with identifier national-id|PH-123 already exists",
                    "instance": "/api/v2/spp/Individual",
                    "errors": [
                        {
                            "field": "identifier[0].value",
                            "code": "duplicate",
                            "message": "This identifier is already registered to another individual",
                        }
                    ],
                },
            ]
        },
    )


def create_problem_detail(
    error_type: str,
    title: str,
    status: int,
    detail: str,
    instance: str | None = None,
    errors: list[dict[str, str]] | None = None,
    extension: dict[str, Any] | None = None,
) -> ProblemDetail:
    """Helper function to create RFC 9457 Problem Detail error responses

    Args:
        error_type: Error category (will be prefixed with 'urn:openspp:error:')
                   Common types: not-found, validation, authentication, authorization,
                   conflict, server-error
        title: Short human-readable error title (e.g., "Not Found")
        status: HTTP status code (e.g., 404, 422, 500)
        detail: Detailed explanation specific to this error occurrence
        instance: Optional URI of the request that caused the error
        errors: Optional list of field-level errors, each with 'field', 'code', 'message'
        extension: Optional additional problem-type-specific fields

    Returns:
        ProblemDetail: Validated problem detail object ready for JSON serialization

    Examples:
        >>> create_problem_detail(
        ...     error_type="not-found",
        ...     title="Not Found",
        ...     status=404,
        ...     detail="Individual not found with identifier national-id|PH-123",
        ...     instance="/api/v2/spp/Individual/national-id|PH-123",
        ... )

        >>> create_problem_detail(
        ...     error_type="validation",
        ...     title="Validation Error",
        ...     status=422,
        ...     detail="Request data contains validation errors",
        ...     instance="/api/v2/spp/Individual",
        ...     errors=[
        ...         {
        ...             "field": "birthDate",
        ...             "code": "invalid_value",
        ...             "message": "Birth date cannot be in the future",
        ...         }
        ...     ],
        ... )
    """
    # Ensure error_type has correct URN prefix
    if not error_type.startswith("urn:openspp:error:"):
        error_type = f"urn:openspp:error:{error_type}"

    # Convert error dicts to FieldError objects if provided
    field_errors = None
    if errors:
        field_errors = [FieldError(**error) for error in errors]

    return ProblemDetail(
        type=error_type,
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        errors=field_errors,
        extension=extension,
    )
