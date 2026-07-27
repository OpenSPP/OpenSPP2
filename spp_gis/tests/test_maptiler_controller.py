# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the MapTiler API key controller in spp_gis."""

from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.spp_gis.controllers.main import MainController


@tagged("post_install", "-at_install")
class TestMapTilerApiKeyController(TransactionCase):
    """Test get_maptiler_api_key placeholder/absent-key handling."""

    def _get_maptiler_api_key(self):
        """Call the controller method with a request bound to the test env."""
        # `request` is an unbound werkzeug LocalProxy during tests; replace it
        # with a plain object exposing the test env (`new=` avoids introspecting
        # the proxy, which raises RuntimeError when unbound).
        fake_request = SimpleNamespace(env=self.env)
        with patch("odoo.addons.spp_gis.controllers.main.request", new=fake_request):
            return MainController().get_maptiler_api_key()

    def test_configured_key_is_returned(self):
        """A real configured key is returned as-is."""
        self.env["ir.config_parameter"].sudo().set_param("spp_gis.map_tiler_api_key", "real-api-key")
        result = self._get_maptiler_api_key()
        self.assertEqual(result["mapTilerKey"], "real-api-key")

    def test_placeholder_key_treated_as_not_configured(self):
        """The default placeholder value is returned as False (not configured)."""
        self.env["ir.config_parameter"].sudo().set_param("spp_gis.map_tiler_api_key", "YOUR_MAPTILER_API_KEY_HERE")
        result = self._get_maptiler_api_key()
        self.assertFalse(result["mapTilerKey"])

    def test_absent_key_returns_false(self):
        """When the parameter is not set at all, mapTilerKey is False."""
        param = self.env["ir.config_parameter"].sudo().search([("key", "=", "spp_gis.map_tiler_api_key")])
        param.unlink()
        result = self._get_maptiler_api_key()
        self.assertFalse(result["mapTilerKey"])

    def test_web_base_url_included(self):
        """The response always includes the web base URL."""
        result = self._get_maptiler_api_key()
        expected = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        self.assertEqual(result["webBaseUrl"], expected)
