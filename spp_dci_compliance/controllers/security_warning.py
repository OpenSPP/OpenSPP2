# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Controller for DCI security warning API."""

from odoo import http
from odoo.http import request


class DCISecurityWarningController(http.Controller):
    """Controller providing API endpoints for DCI security warnings."""

    @http.route("/dci/security/warnings", type="jsonrpc", auth="user")
    def get_security_warnings(self):
        """Get current DCI security warnings.

        Returns JSON with warning information for the systray widget. Only system
        administrators can change the settings involved, so anyone else is told
        there is nothing to show.

        Returns:
            dict: Security warning summary
        """
        warning_model = request.env["spp.dci.security.warning"]
        if not request.env.user.has_group("base.group_system"):
            return warning_model.summarize([])
        return warning_model.get_warning_summary()
