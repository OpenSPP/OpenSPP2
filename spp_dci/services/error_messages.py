# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Error message catalog.

Centralizes generic error messages for external DCI responses.
Internal details should be logged but not exposed to clients.
"""

from ..schemas.constants import SearchStatusReasonCode


class DCIErrorMessages:
    """Centralized error messages for DCI responses.

    These messages are safe for external exposure (no internal details).
    Use these instead of exposing exception messages to API clients.
    """

    # Search errors
    PROCESSING_ERROR = "An error occurred while processing your request"
    INVALID_QUERY = "The search query format is invalid"
    INVALID_REGISTRY_TYPE = "The specified registry type is not supported"
    NOT_FOUND = "The requested record was not found"

    # Subscription errors
    SUBSCRIPTION_CREATION_FAILED = "Failed to create subscription. Please check your request."
    UNSUBSCRIPTION_FAILED = "Failed to process unsubscription request"

    # Registry alias errors (501 Not Implemented)
    REGISTRY_NOT_IMPLEMENTED = "This registry type is not yet implemented"

    # Callback errors
    CALLBACK_FAILED = "Failed to deliver callback notification"

    # Generic errors
    INTERNAL_ERROR = "An internal error occurred"
    VALIDATION_ERROR = "Request validation failed"

    @classmethod
    def get_search_error(cls, code: SearchStatusReasonCode) -> str:
        """Get error message for search status reason code.

        Args:
            code: SearchStatusReasonCode enum value

        Returns:
            str: Human-readable error message
        """
        mapping = {
            SearchStatusReasonCode.SEARCH_CRITERIA_INVALID: cls.INVALID_QUERY,
            SearchStatusReasonCode.FILTER_INVALID: cls.INVALID_QUERY,
            SearchStatusReasonCode.REFERENCE_ID_INVALID: cls.NOT_FOUND,
            SearchStatusReasonCode.PAGINATION_INVALID: "Invalid pagination parameters",
            SearchStatusReasonCode.TOO_MANY_RECORDS: "Search returned too many records",
            SearchStatusReasonCode.SORT_INVALID: "Invalid sort parameters",
            SearchStatusReasonCode.TIMESTAMP_INVALID: "Invalid timestamp format",
            SearchStatusReasonCode.REFERENCE_ID_DUPLICATE: "Duplicate reference ID",
        }
        return mapping.get(code, cls.PROCESSING_ERROR)
