# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request


class FarmerRegistryController(http.Controller):
    @http.route("/spp_farmer_registry/registry_restriction", type="jsonrpc", auth="user")
    def get_registry_restriction(self):
        """Return whether registry CRUD is restricted to admin only."""
        ICP = request.env["ir.config_parameter"].sudo()  # nosemgrep
        value = ICP.get_param(
            "spp_farmer_registry.registry_admin_only_crud", "False"
        )
        return {"restricted": value == "True"}
