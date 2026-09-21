# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Regression tests for the database-error guard around ``hide_menus()``.

``hide_menus()`` runs from ``ir.module.module._register_hook`` at the end of
every registry load (startup, install, upgrade, worker reload). A
``psycopg2.Error`` escaping it aborts the registry load, so on a poisoned
cursor every restart fails until the database is repaired by hand. Hiding a
menu is best-effort there: a menu left visible is recoverable, an aborted
registry load is an outage.
"""

import contextlib
import functools
from unittest.mock import patch

import psycopg2
import psycopg2.extensions

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

HOOK_LOGGER = "odoo.addons.spp_hide_menus_base.models.ir_module_module"
MISSING_MENU_XMLID = "spp_hide_menus_base.test_526_menu_that_does_not_exist"


def _failing_lookup_for(menu_xml_id, original_lookup):
    """An ``ir.model.data._xmlid_lookup`` stand-in that aborts the transaction
    for one xmlid and behaves normally for every other one."""

    @functools.wraps(original_lookup)
    def _xmlid_lookup(model, xmlid):
        if xmlid == menu_xml_id:
            model.env.cr.execute("SELECT 1 FROM spp_table_that_does_not_exist")
        return original_lookup(model, xmlid)

    return _xmlid_lookup


@tagged("post_install", "-at_install")
class TestHideMenusDatabaseErrorGuard(TransactionCase):
    def setUp(self):
        super().setUp()
        self.IrModule = self.env["ir.module.module"]
        self.HideMenu = self.env["spp.hide.menu"]
        self.hide_group = self.HideMenu._hide_group()
        self.assertTrue(self.hide_group, "precondition: the hide group must exist")

    def _catalog(self, **entries):
        """Replace MENU_APP with ``{module_name: menu_xml_id}`` for the test."""
        menu_app = {module: {"menu_xml_id": xml_id} for module, xml_id in entries.items()}
        return patch.object(type(self.IrModule), "MENU_APP", menu_app)

    def _menu_with_external_id(self, name):
        """A menu with no hide configuration yet, reachable through a fresh xmlid."""
        taken = self.HideMenu.search([]).menu_id.ids
        menu = self.env["ir.ui.menu"].search([("id", "not in", taken)], limit=1)
        self.assertTrue(menu, "no unconfigured ir.ui.menu left to test against")
        self.env["ir.model.data"].create(
            {"module": "spp_hide_menus_base", "name": name, "model": "ir.ui.menu", "res_id": menu.id}
        )
        return menu, f"spp_hide_menus_base.{name}"

    def _first_and_last_module(self):
        """Two module names at opposite ends of the order hide_menus() walks,
        so a failure planted on the last one is reached after the first one
        has already done its work."""
        modules = self.IrModule.search([])
        self.assertGreater(len(modules), 1)
        return modules[0].name, modules[-1].name

    def _poison_cursor(self):
        # Odoo's assertRaises runs its body in a savepoint and rolls it back,
        # which would un-poison the cursor; suppress keeps the transaction aborted.
        with mute_logger("odoo.sql_db"), contextlib.suppress(psycopg2.Error):
            self.env.cr.execute("SELECT 1 FROM spp_table_that_does_not_exist")
        self.assertEqual(
            self.env.cr.connection.get_transaction_status(),
            psycopg2.extensions.TRANSACTION_STATUS_INERROR,
            "precondition: the transaction must be aborted before the hook runs",
        )

    def test_01_missing_menu_xmlid_is_skipped(self):
        """A catalog entry whose menu does not exist neither raises nor warns."""
        first, _last = self._first_and_last_module()
        before = self.HideMenu.search([])

        with self._catalog(**{first: MISSING_MENU_XMLID}), self.assertNoLogs(HOOK_LOGGER, level="WARNING"):
            self.IrModule._register_hook()

        self.assertEqual(self.HideMenu.search([]), before)

    def test_02_database_error_inside_hook_is_logged_and_skipped(self):
        """A SQL failure while hiding is logged, the registry load continues,
        and the half-done pass is rolled back as a whole."""
        first, last = self._first_and_last_module()
        menu, menu_xml_id = self._menu_with_external_id("test_526_real_menu")
        groups_before = menu.group_ids
        self.assertNotIn(self.hide_group, groups_before, "precondition: the menu starts visible")
        IrModelData = type(self.env["ir.model.data"])
        failing_lookup = _failing_lookup_for(MISSING_MENU_XMLID, IrModelData._xmlid_lookup)

        with (
            self._catalog(**{first: menu_xml_id, last: MISSING_MENU_XMLID}),
            patch.object(IrModelData, "_xmlid_lookup", failing_lookup),
            mute_logger("odoo.sql_db"),
            self.assertLogs(HOOK_LOGGER, level="WARNING") as captured,
        ):
            self.IrModule._register_hook()

        self.assertTrue(
            any("menu" in message for message in captured.output),
            f"expected a skipped-hiding warning, got {captured.output}",
        )
        # The transaction is still usable: the failure was contained in a savepoint.
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))
        # ...and the pass is atomic: the menu hidden before the failure is visible again
        # and its configuration row is gone.
        self.assertEqual(menu.group_ids, groups_before)
        self.assertFalse(self.HideMenu.search([("menu_id", "=", menu.id)]))

    def test_03_hook_survives_already_aborted_transaction(self):
        """The hook must not raise when the cursor is already poisoned before it starts."""
        self.env.cr.execute("SAVEPOINT test_526_poisoned_cursor")
        try:
            self._poison_cursor()
            with mute_logger("odoo.sql_db"), self.assertLogs(HOOK_LOGGER, level="WARNING"):
                self.IrModule._register_hook()
        finally:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT test_526_poisoned_cursor")
            self.env.cr.execute("RELEASE SAVEPOINT test_526_poisoned_cursor")

    def test_04_callers_pending_writes_are_not_swallowed(self):
        """A failure flushing the caller's own pending writes is the caller's error.

        The guard covers only the hiding pass. Pending ORM writes queued before
        it are flushed ahead of the guard, so their failure surfaces where it
        belongs instead of being logged as a menu-hiding problem.
        """
        menu, _menu_xml_id = self._menu_with_external_id("test_526_pending_write_menu")
        row = self.HideMenu.create({"menu_id": menu.id, "xml_id": "test.pending"})
        self.env.cr.execute("SAVEPOINT test_526_pending_write")
        try:
            row.write({"xml_id": "test.pending_changed"})  # queued, not flushed yet
            self._poison_cursor()

            raised = None
            with mute_logger("odoo.sql_db"), self.assertNoLogs(HOOK_LOGGER, level="WARNING"):
                try:
                    self.IrModule.hide_menus()
                except psycopg2.Error as exc:
                    raised = exc
            self.assertIsInstance(raised, psycopg2.errors.InFailedSqlTransaction)
        finally:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT test_526_pending_write")
            self.env.cr.execute("RELEASE SAVEPOINT test_526_pending_write")
