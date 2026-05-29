# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Typed Notary client exceptions."""

from __future__ import annotations

from typing import Any


class NotaryError(Exception):
    """Base class for Notary errors with non-stringified structured context."""

    default_message = "Notary request failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message or self.default_message)
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotaryConfigurationError(NotaryError, ValueError):
    """Client configuration is missing or invalid."""

    default_message = "Notary client configuration is invalid"


class NotaryPurposeMissing(NotaryConfigurationError):
    """A data-purpose URL was required but no layer supplied one."""

    default_message = "Notary data-purpose is required"


class NotarySubjectIdMissing(NotaryConfigurationError):
    """A subject identifier was required but could not be resolved."""

    default_message = "Notary subject_id is required"


class NotarySubjectNotFound(NotaryError):
    """The source could not find a matching subject."""

    default_message = "Notary subject was not found"


class NotarySourceAmbiguous(NotaryError):
    """The source found more than one matching subject."""

    default_message = "Notary source returned an ambiguous subject match"


class NotarySourceUnavailable(NotaryError):
    """The upstream source is unavailable."""

    default_message = "Notary source is unavailable"


class NotaryClaimNotFound(NotaryError):
    """A requested claim is not known to Notary."""

    default_message = "Notary claim was not found"


class NotaryClaimVersionNotFound(NotaryError):
    """A requested claim version is not known to Notary."""

    default_message = "Notary claim version was not found"


class NotaryRuleEvaluationFailed(NotaryError):
    """A Notary claim rule failed during evaluation."""

    default_message = "Notary claim rule evaluation failed"


class NotaryFormatNotSupported(NotaryError):
    """The requested claim response format is unsupported."""

    default_message = "Notary claim format is not supported"


class NotaryAuthError(NotaryError):
    """Authentication or authorization failed."""

    default_message = "Notary authentication failed"


class NotaryRequestError(NotaryError):
    """The Notary rejected the request payload."""

    default_message = "Notary request is invalid"


class NotaryRateLimited(NotaryError):
    """Notary rejected the call due to rate limiting."""

    default_message = "Notary rate limit exceeded"


class NotaryTransportError(NotaryError):
    """The Notary service could not be reached."""

    default_message = "Notary transport failed"


ERROR_CODE_EXCEPTIONS = {
    "source.not_found": NotarySubjectNotFound,
    "source.ambiguous": NotarySourceAmbiguous,
    "source.unavailable": NotarySourceUnavailable,
    "claim.not_found": NotaryClaimNotFound,
    "claim.version_not_found": NotaryClaimVersionNotFound,
    "claim.rule_evaluation_failed": NotaryRuleEvaluationFailed,
    "claim.format_not_supported": NotaryFormatNotSupported,
}


def exception_from_error_payload(status_code: int, payload: dict[str, Any] | None):
    """Return the typed exception class and Notary error code for a response."""
    error = payload.get("error", payload) if isinstance(payload, dict) else {}
    code = error.get("code") if isinstance(error, dict) else None
    if status_code == 429:
        return NotaryRateLimited, code or "rate_limited"
    if status_code in (401, 403) or (code and code.startswith("auth.")):
        return NotaryAuthError, code
    if status_code in (400, 422):
        return NotaryRequestError, code or "request.invalid"
    return ERROR_CODE_EXCEPTIONS.get(code, NotaryError), code
