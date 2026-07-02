# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp_hide_menus_base — hide/show menu visibility logic.

The module patches ``ir.module.module`` to hide a curated list of stock
Odoo menus (Project, Calendar, Stock, ...) from the OpenSPP user group
when an install/upgrade completes. The tests exercise the ``hide_menu``
and ``show_menu`` round-trip on ``spp.hide.menu`` directly so we cover
the model's state transition without depending on a real "Apps install"
flow.
"""

from odoo import Command
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

    def test_hide_menus_processes_catalog(self):
        """``ir.module.module.hide_menus()`` walks MENU_APP and creates a
        ``spp.hide.menu`` record (state=hide) for every entry whose menu
        xml_id resolves in the current DB.
        """
        IrModuleModule = self.env["ir.module.module"]
        HideMenu = self.env["spp.hide.menu"]

        # Figure out which catalog entries are actually resolvable here —
        # most stock Odoo modules in MENU_APP (mail, contacts, ...) are
        # present in any test DB, but a few (mass_mailing, survey, ...)
        # may not be installed.
        resolvable = []
        for module_name, info in IrModuleModule.MENU_APP.items():
            menu = self.env.ref(info["menu_xml_id"], raise_if_not_found=False)
            module = IrModuleModule.search([("name", "=", module_name)], limit=1)
            if menu and module:
                resolvable.append((module_name, menu.id))

        if not resolvable:
            self.skipTest("No MENU_APP entries are resolvable in this test DB")

        # Wipe any pre-existing spp.hide.menu so the test's assertions are
        # clearly about hide_menus()'s effect, not the install hook.
        HideMenu.search([]).unlink()

        IrModuleModule.hide_menus()

        for module_name, menu_id in resolvable:
            record = HideMenu.search([("menu_id", "=", menu_id)], limit=1)
            self.assertTrue(
                record,
                f"hide_menus() didn't create a spp.hide.menu for {module_name!r}",
            )
            self.assertEqual(
                record.state,
                "hide",
                f"spp.hide.menu for {module_name!r} expected state=hide, got {record.state}",
            )

    def test_hide_menus_is_idempotent(self):
        """Calling hide_menus() twice doesn't double-hide already-hidden menus.

        After the first pass every resolvable entry is in state=hide. A
        second pass must leave them in state=hide (the inner guard
        ``elif hidden_menus.state == "show"`` skips them).
        """
        IrModuleModule = self.env["ir.module.module"]
        HideMenu = self.env["spp.hide.menu"]

        HideMenu.search([]).unlink()
        IrModuleModule.hide_menus()
        after_first = HideMenu.search([])
        self.assertTrue(
            after_first,
            "hide_menus() didn't create any records — nothing to check idempotency against",
        )

        IrModuleModule.hide_menus()
        after_second = HideMenu.search([])
        # No duplicates created and every record stayed in state=hide.
        self.assertEqual(set(after_first.ids), set(after_second.ids))
        for record in after_second:
            self.assertEqual(record.state, "hide")

    def test_reapply_hide_after_simulated_upgrade_reset(self):
        """_reapply_hide() re-applies the hide group after a module upgrade
        reset the menu's group_ids via XML (noupdate="0").

        A real module upgrade can't run inside a test transaction, so we
        simulate its effect: hide the menu, then overwrite group_ids the way
        an XML data reload would, dropping the hide group. _reapply_hide()
        must detect the stale state and restore the hidden configuration.
        """
        hide_group = self.env.ref("spp_hide_menus_base.group_hide_menus_user")
        record = self.env["spp.hide.menu"].create({"menu_id": self.menu.id, "xml_id": "test.hide_menu_target"})
        record.hide_menu()
        self.assertIn(hide_group, self.menu.group_ids, "precondition: menu should be hidden")

        # Simulate the upgrade resetting group_ids to the module's XML default
        # (some real group, without the hide group).
        reset_groups = self.env.ref("base.group_user")
        self.menu.write({"group_ids": [Command.set([reset_groups.id])]})
        self.assertNotIn(hide_group, self.menu.group_ids, "precondition: reset must drop the hide group")

        record._reapply_hide()

        self.assertIn(
            hide_group,
            self.menu.group_ids,
            "_reapply_hide() should restore the hide group after an upgrade reset",
        )
        # The reset groups become the new restore snapshot so show_menu()
        # returns the menu to its real post-upgrade default.
        self.assertEqual(record.default_group_ids, reset_groups)

    def test_reapply_hide_noop_when_already_hidden(self):
        """_reapply_hide() is a no-op when the hide group is still present.

        If no upgrade reset happened, the guard (hide_group not in
        group_ids) is False, so neither group_ids nor the saved snapshot
        should change.
        """
        hide_group = self.env.ref("spp_hide_menus_base.group_hide_menus_user")
        record = self.env["spp.hide.menu"].create({"menu_id": self.menu.id, "xml_id": "test.hide_menu_target"})
        record.hide_menu()
        groups_before = self.menu.group_ids
        snapshot_before = record.default_group_ids
        self.assertIn(hide_group, groups_before, "precondition: menu should be hidden")

        record._reapply_hide()

        self.assertEqual(self.menu.group_ids, groups_before)
        self.assertEqual(record.default_group_ids, snapshot_before)

    def test_hide_menus_reapplies_after_reset(self):
        """``hide_menus()`` re-hides an already-hidden menu whose group_ids
        were reset, exercising the ``elif ... state == "hide"`` branch.

        This is the end-to-end shape of the upgrade bug: a menu is hidden,
        a later module upgrade resets its group_ids, and the next
        install/upgrade pass through hide_menus() must put the hide group
        back.
        """
        IrModuleModule = self.env["ir.module.module"]
        HideMenu = self.env["spp.hide.menu"]
        hide_group = self.env.ref("spp_hide_menus_base.group_hide_menus_user")

        # Find one resolvable MENU_APP entry to drive the real entry point.
        target = None
        for module_name, info in IrModuleModule.MENU_APP.items():
            menu = self.env.ref(info["menu_xml_id"], raise_if_not_found=False)
            module = IrModuleModule.search([("name", "=", module_name)], limit=1)
            if menu and module:
                target = menu
                break
        if target is None:
            self.skipTest("No MENU_APP entries are resolvable in this test DB")

        # First pass creates the record and hides the menu.
        HideMenu.search([]).unlink()
        IrModuleModule.hide_menus()
        record = HideMenu.search([("menu_id", "=", target.id)], limit=1)
        self.assertTrue(record, "hide_menus() should have created a hide record")
        self.assertEqual(record.state, "hide")
        self.assertIn(hide_group, target.group_ids)

        # Simulate an upgrade resetting the menu's group_ids via XML.
        reset_groups = self.env.ref("base.group_user")
        target.write({"group_ids": [Command.set([reset_groups.id])]})
        self.assertNotIn(hide_group, target.group_ids)

        # Second pass must re-hide via the state == "hide" branch.
        IrModuleModule.hide_menus()
        self.assertIn(
            hide_group,
            target.group_ids,
            "hide_menus() should re-hide a menu whose group_ids were reset on upgrade",
        )

    def test_register_hook_rehides_after_reset(self):
        """``_register_hook()`` re-applies hiding on every registry load.

        ``ir.module.module.next()`` only runs on the immediate
        install/upgrade path (button_immediate_*). Upgrades performed
        through the ``base.module.upgrade`` wizard or the CLI (``-u``)
        reload module XML — resetting ``group_ids`` — but never call
        ``next()``. ``_register_hook`` runs at the end of *every* registry
        load, so it must re-hide regardless of the upgrade path. We can't
        run a real upgrade in a test, so we reset the groups by hand and
        call the hook the way the loader does.
        """
        IrModuleModule = self.env["ir.module.module"]
        HideMenu = self.env["spp.hide.menu"]
        hide_group = self.env.ref("spp_hide_menus_base.group_hide_menus_user")

        target = None
        for module_name, info in IrModuleModule.MENU_APP.items():
            menu = self.env.ref(info["menu_xml_id"], raise_if_not_found=False)
            module = IrModuleModule.search([("name", "=", module_name)], limit=1)
            if menu and module:
                target = menu
                break
        if target is None:
            self.skipTest("No MENU_APP entries are resolvable in this test DB")

        HideMenu.search([]).unlink()
        IrModuleModule.hide_menus()
        self.assertIn(hide_group, target.group_ids, "precondition: menu should be hidden")

        # Simulate the wizard/CLI upgrade path: group_ids reset, next() not called.
        reset_groups = self.env.ref("base.group_user")
        target.write({"group_ids": [Command.set([reset_groups.id])]})
        self.assertNotIn(hide_group, target.group_ids)

        IrModuleModule._register_hook()

        self.assertIn(
            hide_group,
            target.group_ids,
            "_register_hook() should re-hide menus on every registry load, "
            "covering upgrade paths that never call next()",
        )

    def test_hide_menus_skips_unknown_modules(self):
        """An ir.module.module record whose name isn't in MENU_APP must be
        ignored by hide_menus() — no spp.hide.menu record is created for it.
        """
        IrModuleModule = self.env["ir.module.module"]
        HideMenu = self.env["spp.hide.menu"]

        # ``base`` is always installed and is NOT in MENU_APP.
        self.assertNotIn("base", IrModuleModule.MENU_APP)

        before = HideMenu.search([]).ids
        IrModuleModule.hide_menus()
        after = HideMenu.search([]).ids

        # Whatever new records appeared, none should belong to the ``base`` menu.
        new_ids = set(after) - set(before)
        for record in HideMenu.browse(list(new_ids)):
            self.assertNotEqual(
                record.menu_id.id,
                self.env.ref("base.menu_administration").id
                if self.env.ref("base.menu_administration", raise_if_not_found=False)
                else 0,
                "hide_menus() shouldn't touch base.menu_administration",
            )
