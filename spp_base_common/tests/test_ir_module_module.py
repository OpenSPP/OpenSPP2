import contextlib
from unittest.mock import patch

import psycopg2
import psycopg2.extensions

from odoo.tests import TransactionCase
from odoo.tools import mute_logger

HOOK_LOGGER = "odoo.addons.spp_base_common.models.ir_module_module"
DISCUSS_ICON = "spp_base_common,static/description/icon-Discuss-White-line.png"


def _failing_lookup_for(menu_xml_id, original_lookup):
    """Build an ``ir.model.data._xmlid_lookup`` stand-in that aborts the
    transaction for one menu and behaves normally for every other xmlid, so the
    other ``next()`` overrides in the MRO keep working."""

    def _xmlid_lookup(model, xmlid):
        if xmlid == menu_xml_id:
            model.env.cr.execute("SELECT 1 FROM spp_table_that_does_not_exist")
        return original_lookup(model, xmlid)

    return _xmlid_lookup


class TestIRModuleModule(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.IrModule = cls.env["ir.module.module"]

        cls.survey_module = cls.IrModule.search([("name", "=", "mail")], limit=1)
        cls.survey_module.button_install()

    def test_01_update_menu_icons(self):
        # Verify that the icon was updated
        self.survey_module.next()
        menu = self.env.ref("mail.menu_root_discuss")
        self.assertEqual(menu.web_icon, DISCUSS_ICON)

    def test_02_missing_menu_xmlid_is_skipped(self):
        """An ICON_MAP entry whose menu does not exist neither raises nor blocks the others."""
        discuss_menu = self.env.ref("mail.menu_root_discuss")
        discuss_menu.write({"web_icon": False})
        broken_entry = {
            "base": {
                "menu_xml_id": "spp_base_common.menu_that_does_not_exist",
                "icon": "spp_base_common,static/description/icon-fast-api.png",
            }
        }

        with patch.dict(self.IrModule.ICON_MAP, broken_entry):
            self.IrModule.update_menu_icons()

        self.assertEqual(discuss_menu.web_icon, DISCUSS_ICON)

    def test_03_database_error_inside_hook_is_logged_and_skipped(self):
        """A SQL failure while decorating is logged, and the module operation still completes."""
        # Fail on a menu only this hook looks up, so the sibling next() override in
        # spp_hide_menus_base (which shares every real menu xmlid) is not affected.
        test_menu_xml_id = "spp_base_common.test_383_menu"
        icon_entry = {"base": {"menu_xml_id": test_menu_xml_id, "icon": DISCUSS_ICON}}
        IrModelData = type(self.env["ir.model.data"])
        failing_lookup = _failing_lookup_for(test_menu_xml_id, IrModelData._xmlid_lookup)

        with (
            patch.dict(self.IrModule.ICON_MAP, icon_entry),
            patch.object(IrModelData, "_xmlid_lookup", failing_lookup),
            mute_logger("odoo.sql_db"),
            self.assertLogs(HOOK_LOGGER, level="WARNING") as captured,
        ):
            action = self.survey_module.next()

        self.assertEqual(action.get("type"), "ir.actions.act_url")
        self.assertTrue(
            any("menu icon" in message for message in captured.output),
            f"expected a skipped-decoration warning, got {captured.output}",
        )
        # The transaction is still usable: the failure was contained in a savepoint.
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))

    def test_04_hook_survives_already_aborted_transaction(self):
        """The hook must not raise when the cursor is already poisoned before it starts."""
        # Odoo's assertRaises runs its body in a savepoint and rolls it back, which
        # would un-poison the cursor; a bare try/except keeps the transaction aborted.
        self.env.cr.execute("SAVEPOINT test_383_poisoned_cursor")
        try:
            with mute_logger("odoo.sql_db"), contextlib.suppress(psycopg2.Error):
                self.env.cr.execute("SELECT 1 FROM spp_table_that_does_not_exist")
            self.assertEqual(
                self.env.cr._cnx.get_transaction_status(),
                psycopg2.extensions.TRANSACTION_STATUS_INERROR,
                "precondition: the transaction must be aborted before the hook runs",
            )

            with mute_logger("odoo.sql_db"), self.assertLogs(HOOK_LOGGER, level="WARNING"):
                self.IrModule.update_menu_icons()
        finally:
            self.env.cr.execute("ROLLBACK TO SAVEPOINT test_383_poisoned_cursor")
