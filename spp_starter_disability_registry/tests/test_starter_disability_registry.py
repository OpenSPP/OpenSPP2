# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the Disability Registry starter bundle."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStarterModule(TransactionCase):
    """Verify the bundle installed and set its registry type."""

    def test_module_exists(self):
        """Verify module record exists."""
        module = self.env["ir.module.module"].search([("name", "=", "spp_starter_disability_registry")])
        self.assertTrue(module, "Module should exist")

    def test_registry_type_parameter(self):
        """The bundle sets spp_starter.registry_type to disability_registry."""
        value = self.env["ir.config_parameter"].sudo().get_param("spp_starter.registry_type")
        self.assertEqual(value, "disability_registry")
