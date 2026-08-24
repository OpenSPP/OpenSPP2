# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the central Registry Settings (OP#1009).

The "Restrict Registry Edits to Admin Only" toggle lives in spp_registry and
keeps both legacy config-parameter keys in sync so whichever starter
controller is installed reads the operator's choice.
"""

from lxml import etree

from odoo.exceptions import AccessError
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

    # ------------------------------------------------------------------
    # who can actually change it (OP#1009 review)
    # ------------------------------------------------------------------

    def _user(self, login, *group_xmlids):
        return (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": login,
                    "login": login,
                    "email": f"{login}@example.test",
                    "group_ids": [
                        (6, 0, [self.env.ref("base.group_user").id] + [self.env.ref(g).id for g in group_xmlids])
                    ],
                }
            )
        )

    def test_saving_requires_a_settings_administrator(self):
        """res.config.settings.execute() refuses anyone who is not an Odoo admin.

        `if not self.env.is_admin(): raise AccessError(...)`, and is_admin means
        superuser or base.group_erp_manager. The OpenSPP admin and
        registry-config-admin groups have neither, and granting them
        group_erp_manager would be a privilege escalation — so the menu is gated
        to match, and this pins the behaviour that gating reflects.
        """
        for groups in (
            ("spp_security.group_spp_admin",),
            ("spp_registry.group_registry_config_admin",),
        ):
            with self.subTest(groups=groups):
                user = self._user("cfg_" + groups[0].split(".")[-1][:20], *groups)
                settings = self.env["res.config.settings"].with_user(user).create({})

                with self.assertRaises(AccessError):
                    settings.execute()

    def test_a_settings_administrator_can_save(self):
        admin = self._user("cfg_erp_manager", "base.group_erp_manager")
        settings = self.env["res.config.settings"].with_user(admin).create(
            {"is_registry_admin_only_crud": False}
        )

        settings.execute()

        self.assertEqual(self._icp().get_param(FARMER_KEY), "False")
        self.assertEqual(self._icp().get_param(SPMIS_KEY), "False")

    def test_the_general_settings_menu_is_gated_on_who_can_save(self):
        """Offering the menu more widely means a form that throws on Save."""
        menu = self.env.ref("spp_registry.menu_registry_settings_general")

        self.assertIn(self.env.ref("base.group_erp_manager"), menu.group_ids)

    def test_the_relocated_configuration_menus_stay_available(self):
        """Those are ordinary actions with their own gates — they do work."""
        root = self.env.ref("spp_registry.menu_registry_settings_root")
        groups = root.group_ids

        self.assertIn(self.env.ref("spp_security.group_spp_admin"), groups)
        self.assertIn(self.env.ref("spp_registry.group_registry_config_admin"), groups)

    def test_the_settings_help_says_who_can_change_it(self):
        arch = etree.fromstring(self.env.ref("spp_registry.res_config_settings_registry_view_form").arch)
        setting = arch.xpath("//setting[contains(@string, 'Restrict Registry Edits')]")[0]

        self.assertIn("Settings administrator", setting.get("help") or "")
