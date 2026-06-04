# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the user-friendly error formatting helpers."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci_client.services.errors import (
    format_connection_error,
    format_http_error,
    raise_user_friendly_error,
)


@tagged("post_install", "-at_install")
class TestErrorFormatting(TransactionCase):
    # --- format_http_error ---------------------------------------------------

    def test_http_known_codes(self):
        for code in (400, 401, 403, 404, 500, 502, 503, 504):
            msg = format_http_error(code)
            self.assertTrue(msg)

    def test_http_unknown_code_includes_number(self):
        msg = format_http_error(418)
        self.assertIn("418", msg)

    def test_http_401_adds_credential_hints(self):
        msg = format_http_error(401)
        self.assertIn("OAuth2 Token URL", msg)
        self.assertIn("Client ID", msg)

    def test_http_5xx_adds_admin_hint(self):
        for code in (500, 502, 503):
            self.assertIn("administrator", format_http_error(code))

    # --- format_connection_error ---------------------------------------------

    def test_connection_known_types(self):
        for t in ("timeout", "dns", "ssl", "connection"):
            self.assertTrue(format_connection_error(t))

    def test_connection_unknown_type_uses_detail(self):
        msg = format_connection_error("weird", detail="socket reset")
        self.assertIn("socket reset", msg)

    # --- raise_user_friendly_error -------------------------------------------

    def test_raise_http_error(self):
        with self.assertRaises(UserError) as ctx:
            raise_user_friendly_error("http", status_code=404)
        self.assertIn("not found", str(ctx.exception).lower())

    def test_raise_connection_error(self):
        with self.assertRaises(UserError) as ctx:
            raise_user_friendly_error("connection", connection_type="timeout")
        self.assertIn("timed out", str(ctx.exception).lower())

    def test_raise_unknown_error_type(self):
        with self.assertRaises(UserError) as ctx:
            raise_user_friendly_error("mystery")
        self.assertIn("unexpected", str(ctx.exception).lower())
