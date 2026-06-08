# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Controller for DCI security warning API."""

from odoo import http
from odoo.http import request


class DCISecurityWarningController(http.Controller):
    """Controller providing API endpoints for DCI security warnings."""

    @http.route("/dci/security/warnings", type="json", auth="user")
    def get_security_warnings(self):
        """Get current DCI security warnings.

        Returns JSON with warning information for the systray widget.

        Returns:
            dict: Security warning summary
        """
        return request.env["spp.dci.security.warning"].get_warning_summary()
