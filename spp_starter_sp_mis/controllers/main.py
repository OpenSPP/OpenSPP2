# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request


class SPMISController(http.Controller):
    @http.route("/spp_starter_sp_mis/registry_restriction", type="jsonrpc", auth="user")
    def get_registry_restriction(self):
        """Return whether registry CRUD is restricted to admin only."""
        value = request.env["ir.config_parameter"].sudo().get_param("spp_starter.registry_admin_only_crud", "False")
        return {"restricted": value == "True"}
