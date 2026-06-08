# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farmer Registry res.config.settings extension.

Tests cover:
- Config parameter read/write for registry CRUD restriction
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResConfigSettings(TransactionCase):
    """Test res.config.settings farmer registry extension."""

    def test_registry_admin_only_crud_default(self):
        """Test that is_registry_admin_only_crud defaults to True."""
        settings = self.env["res.config.settings"].create({})
        self.assertTrue(settings.is_registry_admin_only_crud)

    def test_registry_admin_only_crud_write_true(self):
        """Test setting is_registry_admin_only_crud to True persists."""
        settings = self.env["res.config.settings"].create(
            {
                "is_registry_admin_only_crud": True,
            }
        )
        settings.execute()

        value = self.env["ir.config_parameter"].sudo().get_param("spp_farmer_registry.registry_admin_only_crud")
        self.assertEqual(value, "True")

    def test_registry_admin_only_crud_write_false(self):
        """Test setting is_registry_admin_only_crud to False updates param."""
        # First set to True so param exists
        settings = self.env["res.config.settings"].create(
            {
                "is_registry_admin_only_crud": True,
            }
        )
        settings.execute()

        # Then set to False
        settings2 = self.env["res.config.settings"].create(
            {
                "is_registry_admin_only_crud": False,
            }
        )
        settings2.execute()

        value = self.env["ir.config_parameter"].sudo().get_param("spp_farmer_registry.registry_admin_only_crud")
        # Odoo may store "False" as string or delete the param (returning False bool)
        self.assertIn(value, (False, "False"))

    def test_registry_admin_only_crud_roundtrip(self):
        """Test that config parameter survives a settings roundtrip to True."""
        # Set to True
        settings1 = self.env["res.config.settings"].create(
            {
                "is_registry_admin_only_crud": True,
            }
        )
        settings1.execute()

        # Read back — should be True
        settings2 = self.env["res.config.settings"].create({})
        self.assertTrue(settings2.is_registry_admin_only_crud)
