# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the ``/dci/security/warnings`` JSON route.

The DCI security warning systray item
(``static/src/components/security_warning/security_warning.js``) calls this route on
every webclient load. These tests pin the contract the JavaScript depends on: the
response shape, that it tracks the insecure ``dci.*`` parameters, that only system
administrators receive the warnings, and that it refuses unauthenticated callers.
"""

import json

from odoo.tests import HttpCase, tagged

EMPTY_SUMMARY = {"has_warnings": False, "warning_count": 0, "warnings": [], "message": ""}


@tagged("post_install", "-at_install")
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

    def _create_internal_user(self):
        return self.env["res.users"].create(
            {
                "name": "Plain Internal User",
                "login": "dci_plain_user",
                "password": "dci_plain_user_pw",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def test_unauthenticated_call_is_refused(self):
        """An anonymous caller gets a session-expired JSON-RPC error, never the payload."""
        body = self._call_route().json()

        self.assertNotIn("result", body)
        self.assertTrue(body["error"]["data"]["name"].endswith("SessionExpiredException"))

    def test_all_settings_secure_returns_no_warnings(self):
        """With every insecure setting off the route reports nothing to show."""
        self.authenticate("admin", "admin")

        response = self._call_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], EMPTY_SUMMARY)

    def test_enabled_setting_is_reported(self):
        """An insecure setting turned on shows up as one warning with its key."""
        self.ConfigParam.set_param("dci.allow_unsigned_requests", "true")
        self.authenticate("admin", "admin")

        result = self._call_route().json()["result"]

        self.assertTrue(result["has_warnings"])
        self.assertEqual(result["warning_count"], 1)
        self.assertEqual([w["key"] for w in result["warnings"]], ["dci.allow_unsigned_requests"])
        self.assertEqual(result["message"], "1 DCI security setting(s) are in development mode")

    def test_non_admin_gets_empty_summary(self):
        """A plain internal user is told nothing, even while an insecure setting is on.

        Only system administrators can act on these settings (the action the systray
        offers opens ``ir.config_parameter``), so only they are told about them.
        """
        self.ConfigParam.set_param("dci.allow_unsigned_requests", "true")
        self._create_internal_user()
        self.authenticate("dci_plain_user", "dci_plain_user_pw")

        response = self._call_route()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"], EMPTY_SUMMARY)
