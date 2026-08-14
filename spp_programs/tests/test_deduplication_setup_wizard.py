# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1171: adding a deduplication method should not expose the plumbing.

Adding one used to mean editing the wrapper's ``manager_ref_id`` inline — a
Reference field asking for a model and then a record of it. These tests cover
the replacement: a dialog that asks for the method and a name, and a card that
matches the other configuration sections.
"""

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDeduplicationSetupWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create({"name": "Dedup Setup Wizard [TEST]"})

    def _wizard(self, method, name):
        return self.env["spp.deduplication.setup.wizard"].create(
            {"program_id": self.program.id, "method": method, "name": name}
        )

    def _wrappers(self):
        return self.env["spp.deduplication.manager"].search([("program_id", "=", self.program.id)])

    def test_it_creates_the_concrete_manager_and_its_wrapper(self):
        """One dialog, both records — the wrapper is what the program reads."""
        self._wizard("spp.deduplication.manager.id_dedup", "By ID").action_create_manager()

        wrappers = self._wrappers()
        self.assertEqual(len(wrappers), 1, "the program should have one deduplication method")
        concrete = wrappers.manager_ref_id
        self.assertEqual(concrete._name, "spp.deduplication.manager.id_dedup")
        self.assertEqual(concrete.name, "By ID")
        self.assertEqual(concrete.program_id, self.program)

    def test_each_method_can_be_added(self):
        for method, name in (
            ("spp.deduplication.manager.default", "Shared members"),
            ("spp.deduplication.manager.id_dedup", "By ID"),
            ("spp.deduplication.manager.phone_number", "By phone"),
        ):
            with self.subTest(method=method):
                self._wizard(method, name).action_create_manager()

        self.assertEqual(len(self._wrappers()), 3, "a program may check by more than one method")

    def test_the_same_method_cannot_be_added_twice(self):
        """Two identical methods would just run the same check twice."""
        self._wizard("spp.deduplication.manager.phone_number", "By phone").action_create_manager()

        with self.assertRaises(UserError):
            self._wizard("spp.deduplication.manager.phone_number", "By phone again").action_create_manager()

        self.assertEqual(len(self._wrappers()), 1)

    def test_the_name_is_suggested_from_the_method(self):
        """The second step should be one keystroke, not a blank field."""
        wizard = self.env["spp.deduplication.setup.wizard"].new(
            {"program_id": self.program.id, "method": "spp.deduplication.manager.phone_number"}
        )
        wizard._onchange_method_suggests_a_name()
        self.assertEqual(wizard.name, "Phone number")

        # A name the user typed is left alone.
        wizard.name = "Our own wording"
        wizard.method = "spp.deduplication.manager.id_dedup"
        wizard._onchange_method_suggests_a_name()
        self.assertEqual(wizard.name, "Our own wording")

    def test_the_method_description_follows_the_selection(self):
        wizard = self._wizard("spp.deduplication.manager.default", "Shared members")
        self.assertIn("member in common", wizard.method_description)

    # ------------------------------------------------------------------
    # the program card
    # ------------------------------------------------------------------

    def test_the_count_drives_the_card_zero_state(self):
        self.assertEqual(self.program.deduplication_manager_count, 0)

        self._wizard("spp.deduplication.manager.id_dedup", "By ID").action_create_manager()
        self.program.invalidate_recordset()

        self.assertEqual(self.program.deduplication_manager_count, 1)

    def test_duplicate_detection_is_a_card_like_the_others(self):
        """It was the last section still rendered as a bare group with an
        inline list, which is what put the Reference field in front of users."""
        arch = etree.fromstring(self.env.ref("spp_programs.view_program_form_config_cards").arch)

        headings = arch.xpath("//div[contains(@class, 'card-header')]//h5/text()")
        self.assertIn(
            "Duplicate Detection",
            [h.strip() for h in headings],
            f"Duplicate Detection should be a card beside the others, found {headings}",
        )

        add_buttons = arch.xpath("//button[@name='action_add_deduplication_manager']")
        self.assertTrue(add_buttons, "the card needs an Add button")

    def test_the_reference_field_is_gone_from_the_card(self):
        """No inline manager_ref_id list for deduplication any more."""
        arch = etree.fromstring(self.env.ref("spp_programs.view_program_form_config_cards").arch)
        inline = arch.xpath("//field[@name='deduplication_manager_ids']//field[@name='manager_ref_id']")
        self.assertFalse(inline, "the wrapper's Reference field should no longer be edited inline")

    # ------------------------------------------------------------------
    # access
    # ------------------------------------------------------------------

    def test_a_programs_manager_can_actually_use_it(self):
        """Guards the ACL, which the rest of this file cannot.

        Tests run as superuser, and superuser bypasses access rules entirely.
        The first version of this wizard shipped with no ir.model.access row at
        all: every test here passed, and the first real user to click Add got
        "You are not allowed to access 'Add a Deduplication Method' records —
        no group currently allows this operation".
        """
        manager = self.env["res.users"].create(
            {
                "name": "Dedup Wizard Manager [TEST]",
                "login": "dedup_wizard_manager_test",
                "email": "dedup_wizard_manager@example.test",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("spp_programs.group_programs_manager").id,
                        ],
                    )
                ],
            }
        )

        wizard = (
            self.env["spp.deduplication.setup.wizard"]
            .with_user(manager)
            .create(
                {
                    "program_id": self.program.id,
                    "method": "spp.deduplication.manager.phone_number",
                    "name": "By phone",
                }
            )
        )
        wizard.action_create_manager()

        self.assertEqual(len(self._wrappers()), 1, "a programs manager should be able to add a method")

    # ------------------------------------------------------------------
    # editing when there is more than one method
    # ------------------------------------------------------------------

    def test_edit_opens_the_method_when_there_is_only_one(self):
        self._wizard("spp.deduplication.manager.id_dedup", "By ID").action_create_manager()
        self.program.invalidate_recordset()

        action = self.program.action_configure_deduplication()

        self.assertEqual(action.get("res_model"), "spp.deduplication.manager.id_dedup")

    def test_edit_is_not_offered_when_there_are_several(self):
        """One button cannot sensibly open two methods.

        It used to open deduplication_manager_ids[0] — silently editing the
        first and leaving the second unreachable. Opening a list in a dialog
        was no better: a dialog list cannot drill into a form, so the rows
        looked clickable and did nothing. With several methods the header
        offers no Edit at all, and each row in the card body carries its own.
        """
        arch = etree.fromstring(self.env.ref("spp_programs.view_program_form_config_cards").arch)
        edit = arch.xpath("//button[@name='action_configure_deduplication'][contains(@class,'btn-primary')]")[0]
        self.assertIn(
            "deduplication_manager_count != 1",
            edit.get("invisible") or "",
            "Edit should only appear when there is exactly one method",
        )

    def test_the_multi_method_fallback_is_navigable(self):
        """If anything does call it with several, it must not be a dead end."""
        self._wizard("spp.deduplication.manager.id_dedup", "By ID").action_create_manager()
        self._wizard("spp.deduplication.manager.phone_number", "By phone").action_create_manager()
        self.program.invalidate_recordset()

        action = self.program.action_configure_deduplication()

        self.assertEqual(action.get("res_model"), "spp.deduplication.manager")
        self.assertNotEqual(action.get("target"), "new", "a dialog list cannot open a form")
        _field, _operator, ids = action["domain"][0]
        self.assertEqual(len(ids), 2, "both methods should be reachable")

    def test_the_card_lists_every_method_not_a_summary_line(self):
        """Each configured method gets its own row and its own cog."""
        arch = etree.fromstring(self.env.ref("spp_programs.view_program_form_config_cards").arch)
        rows = arch.xpath("//field[@name='deduplication_manager_ids']//field[@name='display_name']")
        cogs = arch.xpath("//field[@name='deduplication_manager_ids']//button[@name='open_manager_form']")

        self.assertTrue(rows, "the card should list the methods")
        self.assertTrue(cogs, "each method needs its own way in")

    def test_the_card_does_not_offer_add_a_line(self):
        """Adding goes through the Add button, which asks for the method.

        An inline "Add a line" would create a bare wrapper with no method set —
        the Reference-field trap this ticket removes. The list attribute alone
        did not suppress it, so the field carries a create domain that never
        matches (the same mechanism OP#1057 needed).
        """
        arch = etree.fromstring(self.env.ref("spp_programs.view_program_form_config_cards").arch)
        field = arch.xpath("//field[@name='deduplication_manager_ids']")[0]

        self.assertIn("'create'", field.get("options") or "", "create must be denied through options")
        self.assertEqual(field.xpath("./list")[0].get("create"), "0")

