import json

from werkzeug.urls import url_encode
from werkzeug.wrappers import Response

from odoo import http
from odoo.http import request

from odoo.addons.portal.controllers.web import Home

from ..utils import get_param, telemetry_payload, version_info_payload


class OpenSPPHome(Home):
    """Restrict debug mode to administrators when enabled via parameter."""

    @http.route()
    def web_client(self, s_action=None, **kw):
        # Enforce optional debug restriction before rendering
        debug_admin_only = get_param(request.env, "spp.debug.admin_only", "True") == "True"

        # Detect debug flag from kwargs or query string
        has_debug = bool(kw.get("debug")) or ("debug" in (request.httprequest.args or {}))
        if debug_admin_only and has_debug:
            uid = request.session.uid
            # If not logged in or not admin, strip debug and redirect
            is_admin = False
            if uid:
                # Restore the user on the environment (auth="none" means public user initially)
                request.update_env(user=uid)
                if request.env.user:
                    is_admin = request.env.user._is_admin()
            if not is_admin:
                kw.pop("debug", None)
                args = {k: v for k, v in request.httprequest.args.items() if k != "debug"}
                query = url_encode(args)
                # Redirect target is always the internal /web endpoint with preserved query string
                # (relative URL only), so this is not an open redirect.
                return request.redirect(  # nosemgrep: odoo-unvalidated-redirect
                    # Target is fixed internal path, not user-controlled URL.
                    "/web" + (f"?{query}" if query else "")
                )

        return super().web_client(s_action, **kw)


class OpenSPPBrandingController(http.Controller):
    """Custom routes for OpenSPP branding"""

    @http.route("/openspp/about", type="http", auth="public")
    def openspp_about(self, **kwargs):
        """Custom about page for OpenSPP"""
        return json.dumps(
            {
                "title": "About OpenSPP",
                "version": "1.0.0",
                "system_name": get_param(request.env, "spp.system.name", "OpenSPP Platform"),
                "documentation_url": get_param(request.env, "spp.documentation.url", "https://docs.openspp.org"),
                "support_url": get_param(request.env, "spp.support.url", "https://openspp.org"),
            }
        )

    @http.route("/web/webclient/version_info", type="jsonrpc", auth="none")
    def version_info(self):
        """Override version info to show OpenSPP branding"""
        return version_info_payload(request.env)

    @http.route("/publisher-warranty", type="http", auth="none", csrf=False)
    def publisher_warranty(self, **kwargs):
        """Handle telemetry based on configuration"""
        payload = telemetry_payload(request.env)
        return Response(json.dumps(payload), content_type="application/json")
