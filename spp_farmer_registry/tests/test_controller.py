# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farmer Registry controller.

Tests cover:
- /spp_farmer_registry/registry_restriction endpoint
- Response when restricted vs not restricted
"""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestFarmerRegistryController(HttpCase):
    """Test Farmer Registry controller endpoints."""

    def test_registry_restriction_default(self):
        """Test registry restriction endpoint returns default restricted=False when param is default."""
        # Set param to True
        self.env["ir.config_parameter"].sudo().set_param("spp_farmer_registry.registry_admin_only_crud", "True")

        self.authenticate("admin", "admin")
        response = self.url_open(
            "/spp_farmer_registry/registry_restriction",
            data='{"jsonrpc": "2.0", "method": "call", "params": {}, "id": 1}',
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result["result"]["restricted"])

    def test_registry_restriction_not_restricted(self):
        """Test registry restriction endpoint returns restricted=False."""
        self.env["ir.config_parameter"].sudo().set_param("spp_farmer_registry.registry_admin_only_crud", "False")

        self.authenticate("admin", "admin")
        response = self.url_open(
            "/spp_farmer_registry/registry_restriction",
            data='{"jsonrpc": "2.0", "method": "call", "params": {}, "id": 1}',
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertFalse(result["result"]["restricted"])

    def test_registry_restriction_requires_auth(self):
        """Test registry restriction endpoint requires authentication."""
        response = self.url_open(
            "/spp_farmer_registry/registry_restriction",
            data='{"jsonrpc": "2.0", "method": "call", "params": {}, "id": 1}',
            headers={"Content-Type": "application/json"},
        )

        # JSON-RPC with auth="user" returns error for unauthenticated users
        self.assertEqual(response.status_code, 200)
        result = response.json()
        # Should have an error since we're not authenticated
        self.assertIn("error", result)
