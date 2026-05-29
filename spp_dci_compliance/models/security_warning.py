# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Security Warning Model.

Provides warnings when development/testing security settings are enabled.
"""

from odoo import api, models


class DCISecurityWarning(models.AbstractModel):
    """Abstract model for checking DCI security configuration.

    This model provides methods to check if insecure development/testing
    settings are enabled in the DCI configuration.
    """

    _name = "spp.dci.security.warning"
    _description = "DCI Security Warning"

    # Security settings that should be disabled in production
    INSECURE_SETTINGS = [
        {
            "key": "dci.allow_unsigned_requests",
            "name": "Allow Unsigned Requests",
            "description": "DCI signature verification is disabled. "
            "Any request will be accepted without cryptographic verification.",
        },
        {
            "key": "dci.bypass_bearer_auth",
            "name": "Bypass Bearer Authentication",
            "description": "Bearer token authentication is disabled. "
            "API requests will be accepted without authentication.",
        },
        {
            "key": "dci.allow_http_callbacks",
            "name": "Allow HTTP Callbacks",
            "description": "HTTP (non-HTTPS) callback URLs are allowed. "
            "Callback data may be transmitted without encryption.",
        },
        {
            "key": "dci.allow_internal_callback_ips",
            "name": "Allow Internal Callback IPs",
            "description": "Callbacks to internal/private IP addresses are allowed. "
            "This could expose internal services to SSRF attacks.",
        },
    ]

    @api.model
    def get_security_warnings(self):
        """Get list of active security warnings.

        Returns:
            list: List of dictionaries with warning details:
                - key: Config parameter key
                - name: Human-readable name
                - description: Detailed description of the risk
        """
        config = self.env["ir.config_parameter"].sudo()
        warnings = []

        for setting in self.INSECURE_SETTINGS:
            value = config.get_param(setting["key"], "false")
            if value.lower() == "true":
                warnings.append(setting)

        return warnings

    @api.model
    def has_security_warnings(self):
        """Check if any security warnings are active.

        Returns:
            bool: True if any insecure settings are enabled
        """
        return len(self.get_security_warnings()) > 0

    @api.model
    def get_warning_summary(self):
        """Get a summary of security warnings for display.

        Returns:
            dict: Summary with count and details
        """
        warnings = self.get_security_warnings()
        return {
            "has_warnings": len(warnings) > 0,
            "warning_count": len(warnings),
            "warnings": warnings,
            "message": f"{len(warnings)} DCI security setting(s) are in development mode" if warnings else "",
        }
