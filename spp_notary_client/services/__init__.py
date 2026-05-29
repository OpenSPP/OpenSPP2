# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Pure Python Notary client services."""

from .client import NotaryClient, normalize_config
from .exceptions import (
    NotaryAuthError,
    NotaryClaimNotFound,
    NotaryClaimVersionNotFound,
    NotaryConfigurationError,
    NotaryError,
    NotaryFormatNotSupported,
    NotaryRequestError,
    NotaryRateLimited,
    NotaryRuleEvaluationFailed,
    NotarySourceAmbiguous,
    NotarySourceUnavailable,
    NotarySubjectNotFound,
    NotaryTransportError,
)
