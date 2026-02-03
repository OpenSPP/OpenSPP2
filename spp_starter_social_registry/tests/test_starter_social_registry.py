# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for this bundle are in spp_starter/tests/test_starter_bundles.py."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStarterModule(TransactionCase):
    """Placeholder test class - main tests are in spp_starter."""

    def test_module_exists(self):
        """Verify module record exists."""
        module = self.env["ir.module.module"].search([("name", "=", "spp_starter_social_registry")])
        self.assertTrue(module, "Module should exist")
