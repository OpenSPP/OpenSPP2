"""User-friendly error messages for DCI operations."""

from odoo import _
from odoo.exceptions import UserError

# HTTP error code to user message mapping
HTTP_ERROR_MESSAGES = {
    400: _("The request was invalid. Please check your data and try again."),
    401: _("Authentication failed. Please verify the credentials in Data Source settings."),
    403: _("Access denied. The external registry rejected our request."),
    404: _("The requested resource was not found on the external registry."),
    500: _("The external registry encountered an error. Please try again later."),
    502: _("Unable to reach the external registry. Please try again later."),
    503: _("The external registry is temporarily unavailable. Please try again later."),
    504: _("Connection timed out. The external registry is not responding."),
}


def format_http_error(status_code: int, technical_detail: str = None) -> str:
    """Format HTTP error for end user display.

    Args:
        status_code: HTTP status code
        technical_detail: Optional technical details (logged separately)

    Returns:
        User-friendly error message
    """
    user_msg = HTTP_ERROR_MESSAGES.get(status_code, _("Connection error (HTTP %s).") % status_code)

    # Add helpful next steps
    if status_code == 401:
        user_msg += _(
            "\n\nPlease check:\n"
            "• Bearer Token (must match the server's allow-list), or\n"
            "• OAuth2 Token URL, Client ID, Secret and Scope"
        )
    elif status_code in (500, 502, 503):
        user_msg += _("\n\nIf the problem persists, contact the registry administrator.")

    return user_msg


def format_connection_error(error_type: str, detail: str = None) -> str:
    """Format connection error for end user display.

    Args:
        error_type: Type of connection error (timeout, dns, ssl, connection)
        detail: Optional technical details

    Returns:
        User-friendly error message
    """
    messages = {
        "timeout": _("Connection timed out. The external registry is not responding."),
        "dns": _("Could not resolve the server address. Please check the Base URL."),
        "ssl": _("SSL certificate verification failed. Check 'Verify SSL' setting or contact administrator."),
        "connection": _("Could not connect to the external registry. Please check the Base URL."),
    }
    return messages.get(error_type, _("Connection failed: %s") % detail)


def raise_user_friendly_error(error_type: str, **kwargs):
    """Raise UserError with user-friendly message.

    Args:
        error_type: Type of error (http, connection)
        **kwargs: Additional parameters for error formatting

    Raises:
        UserError: With user-friendly message
    """
    if error_type == "http":
        raise UserError(format_http_error(kwargs.get("status_code"), kwargs.get("detail")))
    elif error_type == "connection":
        raise UserError(format_connection_error(kwargs.get("connection_type"), kwargs.get("detail")))
    else:
        raise UserError(_("An unexpected error occurred. Please contact your administrator."))
