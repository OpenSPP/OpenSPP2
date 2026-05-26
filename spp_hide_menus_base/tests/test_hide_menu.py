# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp_hide_menus_base — hide/show menu visibility logic.

The module patches ``ir.module.module`` to hide a curated list of stock
Odoo menus (Project, Calendar, Stock, ...) from the OpenSPP user group
when an install/upgrade completes. The tests exercise the ``hide_menu``
and ``show_menu`` round-trip on ``spp.hide.menu`` directly so we cover
the model's state transition without depending on a real "Apps install"
flow.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSppHideMenu(TransactionCase):
    """Exercise the hide / show round-trip on a sample menu."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Pick any existing menu we can safely toggle in a test transaction.
        cls.menu = cls.env["ir.ui.menu"].search([], limit=1)
        if not cls.menu:
            raise AssertionError("No ir.ui.menu records found to test against")

    def test_module_is_installed(self):
        module = self.env["ir.module.module"].search([("name", "=", "spp_hide_menus_base")], limit=1)
        self.assertEqual(module.state, "installed")

    def test_group_hide_menus_user_seed(self):
        """security/groups.xml must declare the hide-menus-user group."""
        group = self.env.ref("spp_hide_menus_base.group_hide_menus_user", raise_if_not_found=False)
        self.assertTrue(
            group,
            "group_hide_menus_user must exist — hide_menu() falls back on it",
        )

    def test_hide_menu_transition(self):
        """hide_menu() flips state show → hide and snapshots original groups."""
        original_groups = self.env["ir.ui.menu"].browse(self.menu.id).group_ids
        record = self.env["spp.hide.menu"].create({"menu_id": self.menu.id, "xml_id": "test.hide_menu_target"})
        self.assertEqual(record.state, "show")

        record.hide_menu()

        self.assertEqual(record.state, "hide")
        # Original groups were saved on the record so show_menu can restore them.
        self.assertEqual(record.default_group_ids, original_groups)

    def test_show_menu_restores_original_groups(self):
        """show_menu() restores the snapshot taken at hide time."""
        original_groups = self.env["ir.ui.menu"].browse(self.menu.id).group_ids
        record = self.env["spp.hide.menu"].create({"menu_id": self.menu.id, "xml_id": "test.hide_menu_target"})
        record.hide_menu()
        # Menu is now restricted to the hide-menus-user group only.
        self.assertNotEqual(self.menu.group_ids, original_groups)

        record.show_menu()
        self.assertEqual(record.state, "show")
        self.assertEqual(self.menu.group_ids, original_groups)

    def test_hide_menu_noop_when_already_hidden(self):
        """Calling hide_menu twice doesn't change state or groups again."""
        record = self.env["spp.hide.menu"].create({"menu_id": self.menu.id, "xml_id": "test.hide_menu_target"})
        record.hide_menu()
        snapshot = record.default_group_ids
        record.hide_menu()  # second call — guarded by state == "show"
        self.assertEqual(record.state, "hide")
        # Original snapshot must not be overwritten by the second call.
        self.assertEqual(record.default_group_ids, snapshot)

    def test_menu_app_catalog_is_well_formed(self):
        """ir.module.module.MENU_APP entries must point to a menu xml_id."""
        IrModuleModule = self.env["ir.module.module"]
        for module_name, info in IrModuleModule.MENU_APP.items():
            self.assertIn(
                "menu_xml_id",
                info,
                f"MENU_APP[{module_name!r}] missing required 'menu_xml_id'",
            )
            self.assertTrue(
                info["menu_xml_id"],
                f"MENU_APP[{module_name!r}].menu_xml_id is empty",
            )
