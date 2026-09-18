# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the ``/dci/security/warnings`` JSON route.

The DCI security warning systray item
(``static/src/components/security_warning/security_warning.js``) calls this route on
every webclient load. These tests pin the contract the JavaScript depends on: the
response shape, that it tracks the insecure ``dci.*`` parameters, and that it refuses
unauthenticated callers.
"""

import json

from odoo.tests import HttpCase


class TestDCISecurityWarningController(HttpCase):
    """Test cases for the security warning JSON route."""

    ROUTE = "/dci/security/warnings"

    def setUp(self):
        super().setUp()
        self.ConfigParam = self.env["ir.config_parameter"].sudo()
        for setting in self.env["spp.dci.security.warning"].INSECURE_SETTINGS:
            self.ConfigParam.set_param(setting["key"], "false")

    def _call_route(self):
        return self.url_open(
            self.ROUTE,
            data=json.dumps({"jsonrpc": "2.0", "method": "call", "params": {}}),
            headers={"Content-Type": "application/json"},
        )

    def test_unauthenticated_call_is_refused(self):
        """An anonymous caller gets a JSON-RPC error, never the warning payload."""
        body = self._call_route().json()

        self.assertIn("error", body)
        self.assertNotIn("result", body)

    def test_all_settings_secure_returns_no_warnings(self):
        """With every insecure setting off the route reports nothing to show."""
        self.authenticate("admin", "admin")

        response = self._call_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["result"],
            {"has_warnings": False, "warning_count": 0, "warnings": [], "message": ""},
        )

    def test_enabled_setting_is_reported(self):
        """An insecure setting turned on shows up as one warning with its key."""
        self.ConfigParam.set_param("dci.allow_unsigned_requests", "true")
        self.authenticate("admin", "admin")

        result = self._call_route().json()["result"]

        self.assertTrue(result["has_warnings"])
        self.assertEqual(result["warning_count"], 1)
        self.assertEqual([w["key"] for w in result["warnings"]], ["dci.allow_unsigned_requests"])
        self.assertEqual(result["message"], "1 DCI security setting(s) are in development mode")
