# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp_hide_menus_base — hide/show menu visibility logic.

The module patches ``ir.module.module`` to hide a curated list of stock
Odoo menus (Project, Calendar, Stock, ...) from the OpenSPP user group
when an install/upgrade completes. The tests exercise the ``hide_menu``
and ``show_menu`` round-trip on ``spp.hide.menu`` directly so we cover
the model's state transition without depending on a real "Apps install"
flow.
"""

from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


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

    def _without_unique_constraint(self):
        """Reproduce a database on which UNIQUE(menu_id) could not be applied.

        That state is real rather than hypothetical: ``Registry.post_constraint``
        catches any failure from creating a constraint and only logs it, so a
        database that already held duplicates when this module upgraded keeps them
        *and* keeps running. Those are exactly the databases the defensive read has
        to survive, and the only way to build one in a test is to take the
        constraint back off.

        DDL is transactional in PostgreSQL, so the constraint returns when the
        test's transaction rolls back.
        """
        self.env.cr.execute("ALTER TABLE spp_hide_menu DROP CONSTRAINT IF EXISTS spp_hide_menu_unique_menu")

    def _menu_without_hide_row(self):
        """A menu no spp.hide.menu row points at yet."""
        taken = self.env["spp.hide.menu"].search([]).menu_id.ids
        menu = self.env["ir.ui.menu"].search([("id", "not in", taken)], limit=1)
        self.assertTrue(menu, "no unconfigured ir.ui.menu left to test against")
        return menu

    def test_a_menu_cannot_have_two_hide_configurations(self):
        """UNIQUE(menu_id): the state that aborts the registry load is rejected.

        Two rows for one menu make hide_menus() read ``.state`` off a
        multi-record set, which raises Expected singleton from _register_hook and
        brings the whole instance down. The constraint stops it being creatable.
        """
        menu = self._menu_without_hide_row()
        self.env["spp.hide.menu"].create({"menu_id": menu.id, "xml_id": "test.first"})

        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env["spp.hide.menu"].create({"menu_id": menu.id, "xml_id": "test.second"})
                self.env.flush_all()
        # The savepoint rolled the failed create back in the database, but the
        # ORM cache still holds the aborted record; drop it so later reads in
        # this transaction cannot see a row that does not exist.
        self.env.invalidate_all()

    def _forget_hide_groups(self):
        """Remove both hide-group xml_ids, as on a database with mangled module data."""
        self.env["ir.model.data"].search(
            [
                ("module", "=", "spp_hide_menus_base"),
                ("name", "in", ["group_hide_menus_user", "group_menu_visibility"]),
            ]
        ).unlink()

    def test_primary_survives_a_missing_hide_group(self):
        """The defensive read must not raise even with the hide group gone.

        ``_primary()`` runs on the ``_register_hook`` path; an ``env.ref`` that
        raises there recreates the outage this module guards against. With no
        group to rank by, the lowest id is the deterministic fallback.
        """
        menu = self._menu_without_hide_row()
        self._without_unique_constraint()
        ids = []
        for xml_id in ("test.nogroup_a", "test.nogroup_b"):
            self.env.cr.execute(
                "INSERT INTO spp_hide_menu (menu_id, state, xml_id) VALUES (%s, 'hide', %s) RETURNING id",
                (menu.id, xml_id),
            )
            ids.append(self.env.cr.fetchone()[0])
        self._forget_hide_groups()

        both = self.env["spp.hide.menu"].browse(ids)
        self.assertEqual(both._primary().id, ids[0], "lowest id must govern when no group can rank the rows")

    def test_hide_menu_is_a_noop_without_the_hide_group(self):
        """``hide_menu()`` also runs from ``_register_hook`` via ``hide_menus()``;
        with no group to collapse onto it must warn and leave the menu alone,
        not raise."""
        menu = self._menu_without_hide_row()
        rec = self.env["spp.hide.menu"].create({"menu_id": menu.id, "xml_id": "test.nogroup"})
        groups_before = menu.group_ids
        self._forget_hide_groups()

        rec.hide_menu()
        self.assertEqual(rec.state, "show", "the row must not pretend the menu was hidden")
        self.assertEqual(menu.group_ids, groups_before, "the menu must be left as it was")

        rec.state = "hide"
        rec._reapply_hide()
        self.assertEqual(menu.group_ids, groups_before, "_reapply_hide must be a no-op too")

    def test_primary_prefers_a_row_that_can_still_restore_its_menu(self):
        """Which duplicate survives is not arbitrary.

        ``hide_menu()`` snapshots ``group_ids`` into ``default_group_ids``, so a
        row created after the menu was already collapsed holds only the hide
        group and ``show_menu()`` on it restores a menu nobody can see. The
        de-dup migration ranks rows by the same rule.
        """
        menu = self._menu_without_hide_row()
        hide_group = self.env["spp.hide.menu"]._hide_group()
        real_groups = self.env.ref("base.group_user")

        degraded = self.env["spp.hide.menu"].create({"menu_id": menu.id, "xml_id": "test.degraded"})
        degraded.default_group_ids = [Command.set([hide_group.id])]

        self._without_unique_constraint()
        self.env.cr.execute(
            "INSERT INTO spp_hide_menu (menu_id, state, xml_id) VALUES (%s, 'hide', 'test.good') RETURNING id",
            (menu.id,),
        )
        good = self.env["spp.hide.menu"].browse(self.env.cr.fetchone()[0])
        good.default_group_ids = [Command.set([real_groups.id])]

        both = degraded + good
        self.assertEqual(both._primary(), good, "_primary() must not pick the degraded row")

        empty = self.env["spp.hide.menu"].browse(good.id)
        empty.default_group_ids = [Command.clear()]
        self.assertEqual(
            (degraded + empty)._primary(),
            empty,
            "an empty snapshot is a valid one — a menu with no groups restores to no groups",
        )

    def test_hide_menus_tolerates_a_duplicate_the_constraint_could_not_block(self):
        """The defensive half of the fix, and why the constraint alone is not enough.

        ``Registry.post_constraint`` logs and swallows a constraint it cannot
        apply, so a database that still held duplicates when UNIQUE(menu_id)
        landed keeps running without it. hide_menus() must not raise there —
        before this change it did, from _register_hook, taking the instance down.
        """
        menu = self._menu_without_hide_row()
        external_id = "spp_hide_menus_base.test_menu_for_duplicate"
        self.env["ir.model.data"].create(
            {
                "module": "spp_hide_menus_base",
                "name": "test_menu_for_duplicate",
                "model": "ir.ui.menu",
                "res_id": menu.id,
            }
        )

        self._without_unique_constraint()
        for xml_id in ("test.dup_a", "test.dup_b"):
            self.env.cr.execute(
                "INSERT INTO spp_hide_menu (menu_id, state, xml_id) VALUES (%s, 'hide', %s)",
                (menu.id, xml_id),
            )
        self.env.invalidate_all()
        self.assertEqual(
            self.env["spp.hide.menu"].search_count([("menu_id", "=", menu.id)]),
            2,
            "precondition: the duplicate must exist for this test to mean anything",
        )

        # ``base`` is always installed, so this exercises the real loop rather
        # than depending on which optional Odoo apps the test database happens
        # to carry.
        menu_app = dict(self.env["ir.module.module"].MENU_APP, base={"menu_xml_id": external_id})
        with patch.object(type(self.env["ir.module.module"]), "MENU_APP", menu_app):
            self.env["ir.module.module"].hide_menus()

        # Not raising is necessary but not sufficient: the governing row must
        # actually have hidden the menu, otherwise a _primary() that picked a
        # wrong row would pass this test while leaving the menu visible.
        self.assertEqual(
            menu.group_ids,
            self.env["spp.hide.menu"]._hide_group(),
            "the surviving duplicate must actually govern: the menu is collapsed onto the hide group",
        )
