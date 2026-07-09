from odoo import http
from odoo.http import request


class MainController(http.Controller):
    @http.route("/get_maptiler_api_key", type="jsonrpc", auth="user")
    def get_maptiler_api_key(self):
        # nosemgrep: odoo-sudo-without-context
        map_tiler_api_key = request.env["ir.config_parameter"].sudo().get_param("spp_gis.map_tiler_api_key")
        # Treat the default placeholder as "not configured"
        if map_tiler_api_key == "YOUR_MAPTILER_API_KEY_HERE":
            map_tiler_api_key = False
        # nosemgrep: odoo-sudo-without-context
        web_base_url = request.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return {"mapTilerKey": map_tiler_api_key, "webBaseUrl": web_base_url}
