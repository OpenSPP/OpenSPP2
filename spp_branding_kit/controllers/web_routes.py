# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import http

from odoo.addons.web.controllers.home import Home


class OpenSPPWebClient(Home):
    """
    Extend Home to add /openspp routes as an alias for /odoo routes.

    This provides OpenSPP branding in URLs:
    - /openspp/programs/123 instead of /odoo/programs/123
    - /openspp/individuals/456 instead of /odoo/individuals/456

    Both /odoo and /openspp routes remain functional for compatibility.
    """

    @http.route(
        ["/openspp", "/openspp/<path:subpath>"],
        type="http",
        auth="none",
        readonly=True,
    )
    def openspp_web_client(self, subpath=None, **kw):
        """
        Handle /openspp and /openspp/<path> routes.

        Delegates to the same logic as /odoo/<path> by calling the parent
        web_client method which handles action resolution and record routing.
        """
        return self.web_client(s_action=subpath, **kw)
