# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the central Registry Settings (OP#1009).

The "Restrict Registry Edits to Admin Only" toggle lives in spp_registry and
keeps both legacy config-parameter keys in sync so whichever starter
controller is installed reads the operator's choice.
"""

from odoo.tests import TransactionCase, tagged

FARMER_KEY = "spp_farmer_registry.registry_admin_only_crud"
SPMIS_KEY = "spp_starter.registry_admin_only_crud"


@tagged("post_install", "-at_install")
class TestRegistryResConfigSettings(TransactionCase):
    """Registry admin-only-CRUD toggle: default + dual-key sync."""

    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    def _clear_keys(self):
        self._icp().search([("key", "in", [FARMER_KEY, SPMIS_KEY])]).unlink()

    def test_defaults_true_when_unset(self):
        """With neither legacy key set, the toggle defaults to True (secure)."""
        self._clear_keys()
        settings = self.env["res.config.settings"].create({})
        self.assertTrue(settings.is_registry_admin_only_crud)

    def test_set_values_writes_both_keys(self):
        """Saving the toggle writes BOTH legacy keys so either controller reads it."""
        settings = self.env["res.config.settings"].create({"is_registry_admin_only_crud": True})
        settings.execute()
        self.assertEqual(self._icp().get_param(FARMER_KEY), "True")
        self.assertEqual(self._icp().get_param(SPMIS_KEY), "True")

        settings = self.env["res.config.settings"].create({"is_registry_admin_only_crud": False})
        settings.execute()
        self.assertEqual(self._icp().get_param(FARMER_KEY), "False")
        self.assertEqual(self._icp().get_param(SPMIS_KEY), "False")

    def test_get_values_reflects_an_explicit_key(self):
        """An explicit value on either legacy key is reflected in the toggle."""
        self._clear_keys()
        self._icp().set_param(SPMIS_KEY, "False")
        settings = self.env["res.config.settings"].create({})
        self.assertFalse(settings.is_registry_admin_only_crud)

        self._clear_keys()
        self._icp().set_param(FARMER_KEY, "True")
        settings = self.env["res.config.settings"].create({})
        self.assertTrue(settings.is_registry_admin_only_crud)
