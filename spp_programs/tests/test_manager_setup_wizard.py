# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1172: one way to configure a program, and it stays that program's own.

Every card on the Configuration tab used to be filled through an inline list
with a `manager_ref_id` Reference field. Both halves of that control offered
other programs' managers, so one program could be configured with another's
while the manager went on running against the program it was created for.

These tests cover the replacement — one Add dialog for every card — and the
isolation rules that hold whether the configuration arrives from the form, the
API, or a duplicated program.
"""

from lxml import etree

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.constants import MANAGER_CATEGORIES

# The cards this branch converted. Deduplication is deliberately absent: its
# card is being converted under OP#1171 and lands separately.
CONVERTED = ["eligibility", "entitlement", "cycle", "compliance", "payment", "notification"]


@tagged("post_install", "-at_install")
class TestManagerSetupWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create({"name": "Manager Setup Wizard [TEST]"})
        cls.wizard_model = cls.env["spp.manager.setup.wizard"]

    def _add(self, category, method=None, name="A method", program=None):
        """Add a method the way the dialog does."""
        methods = self.wizard_model._methods_for_category(category)
        wizard = self.wizard_model.with_context(default_category=category).create(
            {
                "program_id": (program or self.program).id,
                "category": category,
                "method": method or methods[0][0],
                "name": name,
            }
        )
        wizard.action_create_manager()
        return wizard

    def _configured(self, category, program=None):
        return (program or self.program)[MANAGER_CATEGORIES[category]["field"]]

    # ------------------------------------------------------------------
    # the dialog
    # ------------------------------------------------------------------

    def test_every_card_can_be_configured_through_the_dialog(self):
        """One dialog, every category — including the One2many one.

        Compliance resolves from the wrapper's program_id while the rest are
        Many2many and need an explicit link, which is the step that used to be
        forgotten: the manager gets created and the program never picks it up.
        """
        for category in CONVERTED:
            methods = self.wizard_model._methods_for_category(category)
            if not methods:
                continue
            with self.subTest(category=category):
                program = self.env["spp.program"].create({"name": f"Dialog {category} [TEST]"})
                self._add(category, name=f"My {category}", program=program)

                configured = self._configured(category, program)
                self.assertEqual(len(configured), 1, f"{category} should be wired to the program")
                self.assertEqual(configured.manager_ref_id.name, f"My {category}")
                self.assertEqual(configured.manager_ref_id.program_id, program)

    def test_the_methods_come_from_the_wrapper_not_a_list_here(self):
        """So a module that adds a method is offered without editing the wizard."""
        wrapper = self.env[MANAGER_CATEGORIES["eligibility"]["wrapper"]]
        offered = dict(self.wizard_model._methods_for_category("eligibility"))

        self.assertTrue(offered, "eligibility should offer at least one method")
        for model, _label in wrapper._selection_manager_ref_id():
            if model in self.env:
                self.assertIn(model, offered, f"{model} is registered on the wrapper but not offered")

    def test_an_unknown_category_offers_nothing(self):
        self.assertEqual(self.wizard_model._methods_for_category("not-a-category"), [])

    def test_the_name_is_suggested_from_the_method(self):
        methods = self.wizard_model._methods_for_category("eligibility")
        if len(methods) < 2:
            self.skipTest("needs a category with more than one method")
        wizard = self.wizard_model.with_context(default_category="eligibility").new(
            {"program_id": self.program.id, "category": "eligibility", "method": methods[0][0]}
        )
        wizard._onchange_method_suggests_a_name()
        self.assertEqual(wizard.name, methods[0][1])

        # A name the user typed is left alone.
        wizard.name = "Our own wording"
        wizard.method = methods[1][0]
        wizard._onchange_method_suggests_a_name()
        self.assertEqual(wizard.name, "Our own wording")

    def test_the_same_method_cannot_be_added_twice(self):
        program = self.env["spp.program"].create({"name": "Twice [TEST]"})
        self._add("eligibility", name="First", program=program)

        with self.assertRaises(UserError):
            self._add("eligibility", name="Second", program=program)

    def test_a_method_can_be_added_again_after_it_is_removed(self):
        """The ✕ on a Many2many row removes the relation, not the record.

        The leftover kept its program_id, so the duplicate check used to refuse
        a method the card no longer showed (OP#1171).
        """
        program = self.env["spp.program"].create({"name": "Re-add [TEST]"})
        self._add("eligibility", name="First", program=program)
        removed = program.eligibility_manager_ids
        program.write({"eligibility_manager_ids": [(3, removed.id)]})

        self._add("eligibility", name="Second", program=program)

        self.assertEqual(len(program.eligibility_manager_ids), 1, "the method should be back")
        self.assertFalse(removed.exists(), "the removed method should not linger")

    def test_a_category_with_no_method_says_so(self):
        """Notifications have no channel until a bridge module is installed."""
        empty = [c for c in CONVERTED if not self.wizard_model._methods_for_category(c)]
        if not empty:
            self.skipTest("every category has a method installed")
        with self.assertRaises(UserError):
            self.program.with_context(manager_category=empty[0]).action_add_manager()

    def test_add_is_refused_on_an_ended_program(self):
        program = self.env["spp.program"].create({"name": "Ended [TEST]", "state": "ended"})
        self.assertFalse(program.with_context(manager_category="eligibility").action_add_manager())

    def test_the_dead_end_helper_now_opens_the_dialog(self):
        """It used to pop "add a manager using the list below" — that list is gone."""
        action = self.program._open_manager_setup_wizard("eligibility")

        self.assertEqual(action.get("type"), "ir.actions.act_window")
        self.assertEqual(action.get("res_model"), "spp.manager.setup.wizard")

    # ------------------------------------------------------------------
    # entitlements: one per program, for now (OP#1172 round 1)
    # ------------------------------------------------------------------

    def test_a_second_entitlement_method_is_refused_with_the_real_reason(self):
        """QA asked for several cash entitlements; the engine allows one.

        spp.program.check_managers_limit refuses a second entitlement manager,
        and the cycle machinery reaches for exactly one — get_manager() calls
        ensure_one(), and get_managers() raises NotImplementedError for this
        kind. Accepting a second here would create a program every cycle
        operation then failed on, so the dialog refuses and says why.

        This test pins today's limit rather than blessing it: when the engine
        learns to iterate entitlement managers, this is the test that changes.
        """
        program = self.env["spp.program"].create({"name": "One Entitlement [TEST]"})
        self._add("entitlement", method="spp.program.entitlement.manager.cash", name="First cash", program=program)

        with self.assertRaises(UserError) as cm:
            self._add("entitlement", method="spp.program.entitlement.manager.cash", name="Second cash", program=program)
        self.assertIn("supports one", str(cm.exception))

        with self.assertRaises(UserError):
            self._add("entitlement", method="spp.program.entitlement.manager.inkind", name="Goods", program=program)

        self.assertEqual(len(program.entitlement_manager_ids), 1, "the program keeps the method it had")

    def test_the_engine_still_reaches_for_exactly_one_entitlement_manager(self):
        """Guards the reason above: if this stops being true, revisit the limit."""
        program = self.env["spp.program"].create({"name": "Engine Assumption [TEST]"})
        self._add("entitlement", method="spp.program.entitlement.manager.cash", name="Cash", program=program)

        self.assertTrue(program.get_manager(program.MANAGER_ENTITLEMENT))
        with self.assertRaises(NotImplementedError):
            program.get_managers(program.MANAGER_ENTITLEMENT)

    # ------------------------------------------------------------------
    # isolation
    # ------------------------------------------------------------------

    def test_another_programs_method_cannot_be_linked_in(self):
        owner = self.env["spp.program"].create({"name": "Owner [TEST]"})
        self._add("eligibility", name="Owner's rule", program=owner)
        borrower = self.env["spp.program"].create({"name": "Borrower [TEST]"})

        with self.assertRaises(ValidationError):
            borrower.write({"eligibility_manager_ids": [(4, owner.eligibility_manager_ids.id)]})

    def test_another_programs_method_cannot_be_linked_at_creation(self):
        owner = self.env["spp.program"].create({"name": "Owner At Create [TEST]"})
        self._add("eligibility", name="Owner's rule", program=owner)

        with self.assertRaises(ValidationError):
            self.env["spp.program"].create(
                {
                    "name": "Borrower At Create [TEST]",
                    "eligibility_manager_ids": [(4, owner.eligibility_manager_ids.id)],
                }
            )

    def test_a_database_that_already_shares_one_stays_editable(self):
        """Only what a write adds is checked.

        Rejecting everything already linked would trap a database polluted by
        the old picker: the ✕ is itself a write, and with two foreign methods
        linked, removing one would be refused because of the other.
        """
        owner = self.env["spp.program"].create({"name": "Legacy Owner [TEST]"})
        self._add("eligibility", name="First", program=owner)
        self._add("cycle", name="Second", program=owner)
        polluted = self.env["spp.program"].create({"name": "Legacy Borrower [TEST]"})
        for field_name, wrapper in (
            ("eligibility_manager_ids", owner.eligibility_manager_ids),
            ("cycle_manager_ids", owner.cycle_manager_ids),
        ):
            field = self.env["spp.program"]._fields[field_name]
            self.env.cr.execute(
                f"INSERT INTO {field.relation} ({field.column1}, {field.column2}) VALUES (%s, %s)",
                (polluted.id, wrapper.id),
            )
        polluted.invalidate_recordset()

        # Taking one off is a write on a field that still holds the other.
        polluted.write({"eligibility_manager_ids": [(3, owner.eligibility_manager_ids.id)]})

        self.assertFalse(polluted.eligibility_manager_ids)
        self.assertEqual(polluted.cycle_manager_ids, owner.cycle_manager_ids)

    def test_duplicating_a_program_copies_its_configuration(self):
        """A plain copy would link the source's methods into the duplicate."""
        source = self.env["spp.program"].create({"name": "Source [TEST]"})
        self._add("eligibility", name="Source rule", program=source)

        duplicate = source.copy({"name": "Duplicate [TEST]"})

        self.assertTrue(duplicate.eligibility_manager_ids, "the duplicate should be configured too")
        self.assertNotEqual(
            duplicate.eligibility_manager_ids,
            source.eligibility_manager_ids,
            "the duplicate must not share the source's method",
        )
        self.assertEqual(duplicate.eligibility_manager_ids.manager_ref_id.program_id, duplicate)
        self.assertEqual(source.eligibility_manager_ids.manager_ref_id.name, "Source rule")

    # ------------------------------------------------------------------
    # the cards
    # ------------------------------------------------------------------

    def _arch(self):
        return etree.fromstring(self.env.ref("spp_programs.view_program_form_config_cards").arch)

    def test_every_card_offers_add(self):
        arch = self._arch()
        for category in CONVERTED:
            with self.subTest(category=category):
                buttons = arch.xpath(f"//button[@name='action_add_manager'][contains(@context, \"'{category}'\")]")
                self.assertTrue(buttons, f"the {category} card needs an Add button")

    def test_no_card_edits_the_reference_field_inline(self):
        """The Reference field is what offered other programs' managers."""
        arch = self._arch()
        for category in CONVERTED:
            field = MANAGER_CATEGORIES[category]["field"]
            with self.subTest(category=category):
                self.assertFalse(
                    arch.xpath(f"//field[@name='{field}']//field[@name='manager_ref_id']"),
                    f"{category} should list methods, not edit their Reference",
                )

    def test_no_card_offers_add_a_line(self):
        """Denied through 'link' as well as 'create'.

        These fields are Many2many, and for those the list renderer reads
        `"link" in activeActions ? link : create`, so create="0" on the list
        was never consulted and the row it left opened a picker listing every
        program's managers.
        """
        arch = self._arch()
        for category in CONVERTED:
            field_name = MANAGER_CATEGORIES[category]["field"]
            with self.subTest(category=category):
                field = arch.xpath(f"//field[@name='{field_name}']")[0]
                options = field.get("options") or ""
                self.assertIn("'link'", options, "the link row is what a Many2many shows")
                self.assertIn("'create'", options, "create must be denied too")
                self.assertNotIn("'unlink'", options, "removing a method must stay possible")
                self.assertEqual(field.xpath("./list")[0].get("create"), "0")

    def test_edit_is_only_offered_when_there_is_one_method(self):
        """One button cannot sensibly open two, and it used to open the first."""
        arch = self._arch()
        for category in CONVERTED:
            count = f"{category}_manager_count"
            with self.subTest(category=category):
                edit = arch.xpath(f"//button[@name='action_configure_{category}'][contains(@class,'btn-primary')]")[0]
                self.assertIn(count, edit.get("invisible") or "")

    def test_notifications_is_a_card_like_the_rest(self):
        """It was the last section still rendered as a bare group."""
        headings = [h.strip() for h in self._arch().xpath("//div[contains(@class, 'card-header')]//h5/text()")]

        self.assertIn("Notifications", headings, f"found {headings}")
