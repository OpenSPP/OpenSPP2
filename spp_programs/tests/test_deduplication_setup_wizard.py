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

    def _wizard(self, method, name, with_id_types=True):
        wizard = self.env["spp.deduplication.setup.wizard"].create(
            {"program_id": self.program.id, "method": method, "name": name}
        )
        if with_id_types and method == "spp.deduplication.manager.id_dedup":
            # The dialog requires these for the ID method, so the helper fills
            # them in the way a user would. An ID manager with none set compares
            # nothing (OP#1171 round 2).
            wizard.supported_id_document_type_ids = self._id_types()
        return wizard

    def _id_types(self, limit=2):
        return self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:id-type")],
            limit=limit,
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

        The row has to be denied through ``link``. The field is a Many2many,
        and for those the list renderer reads
        ``"link" in activeActions ? link : create`` — so the list's create="0"
        and a create domain were both ignored, the row stayed, and it opened
        the link picker: every deduplication manager in the database, other
        programs' included (OP#1171 round 1).

        ``unlink`` is deliberately left out: removing a method stays available.
        """
        arch = etree.fromstring(self.env.ref("spp_programs.view_program_form_config_cards").arch)
        field = arch.xpath("//field[@name='deduplication_manager_ids']")[0]
        options = field.get("options") or ""

        self.assertIn("'link'", options, "the link row is what the renderer shows for a Many2many")
        self.assertIn("'create'", options, "create must be denied too")
        self.assertNotIn("'unlink'", options, "removing a method must stay possible")
        self.assertEqual(field.xpath("./list")[0].get("create"), "0")

    # ------------------------------------------------------------------
    # the ID document method
    # ------------------------------------------------------------------

    def test_the_dialog_asks_which_id_types_to_compare(self):
        """The field belongs to this method, so the dialog has to carry it.

        `deduplicate_beneficiaries` keeps only documents whose type is in
        supported_id_document_type_ids, so a manager created without any finds
        no duplicates at all and says nothing about why (OP#1171 round 2).
        """
        arch = etree.fromstring(self.env.ref("spp_programs.view_deduplication_setup_wizard_form").arch)
        field = arch.xpath("//field[@name='supported_id_document_type_ids']")[0]

        self.assertIn("id_dedup", field.get("invisible") or "", "only the ID method compares documents")
        self.assertIn("id_dedup", field.get("required") or "", "an empty list would match nothing")

    def test_the_chosen_id_types_reach_the_manager(self):
        id_types = self._id_types()
        self.assertTrue(id_types, "spp_vocabulary seeds ID types; the dialog needs them")
        wizard = self._wizard("spp.deduplication.manager.id_dedup", "By ID")
        wizard.supported_id_document_type_ids = id_types

        wizard.action_create_manager()

        concrete = self._wrappers().manager_ref_id
        self.assertEqual(concrete.supported_id_document_type_ids, id_types)

    def test_the_id_method_is_refused_without_a_type(self):
        """Required in the view covers the dialog, not a programmatic caller."""
        with self.assertRaises(UserError):
            self._wizard("spp.deduplication.manager.id_dedup", "By ID", with_id_types=False).action_create_manager()

        self.assertFalse(self._wrappers(), "nothing should be created")

    def test_the_other_methods_do_not_ask_for_id_types(self):
        for method in ("spp.deduplication.manager.default", "spp.deduplication.manager.phone_number"):
            with self.subTest(method=method):
                program = self.env["spp.program"].create({"name": f"No ID types {method} [TEST]"})
                wizard = self.env["spp.deduplication.setup.wizard"].create(
                    {"program_id": program.id, "method": method, "name": "No types"}
                )

                wizard.action_create_manager()

                self.assertEqual(len(program.deduplication_manager_ids), 1)

    # ------------------------------------------------------------------
    # removing a method
    # ------------------------------------------------------------------

    def test_a_method_can_be_added_again_after_it_is_removed(self):
        """The ✕ removes the relation, not the record.

        QA removed a method and could not add it back: the duplicate check
        searched wrappers by ``program_id`` and found the one the card no
        longer showed (OP#1171 round 1).
        """
        self._wizard("spp.deduplication.manager.default", "Shared members").action_create_manager()
        removed = self.program.deduplication_manager_ids
        concrete = removed.manager_ref_id
        self.program.write({"deduplication_manager_ids": [(3, removed.id)]})

        self._wizard("spp.deduplication.manager.default", "Shared members").action_create_manager()

        self.assertEqual(len(self.program.deduplication_manager_ids), 1, "the method should be back")
        self.assertFalse(removed.exists(), "the removed wrapper should not linger")
        self.assertFalse(concrete.exists(), "nor the method behind it")

    def test_the_sweep_survives_a_reference_pointing_nowhere(self):
        """manager_ref_id is a Reference: no foreign key, so it can dangle.

        Unlinking it blind would raise MissingError, and it would raise it on
        the Add button — the one place this sweep runs.
        """
        self._wizard("spp.deduplication.manager.default", "Shared members").action_create_manager()
        dangling = self.program.deduplication_manager_ids
        dangling.manager_ref_id.unlink()  # takes the wrapper with it
        dangling = self.env["spp.deduplication.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": "spp.deduplication.manager.default,999999999",
            }
        )

        self._wizard("spp.deduplication.manager.default", "Shared members").action_create_manager()

        self.assertFalse(dangling.exists(), "the stale wrapper should be swept")
        self.assertEqual(len(self.program.deduplication_manager_ids), 1)

    def test_the_sweep_spares_a_method_another_program_uses(self):
        """The relation is a Many2many; a linked wrapper is not garbage."""
        self._wizard("spp.deduplication.manager.id_dedup", "By ID").action_create_manager()
        shared = self.program.deduplication_manager_ids
        other = self.env["spp.program"].create({"name": "Dedup Sweep Bystander [TEST]"})
        self.program.write({"deduplication_manager_ids": [(3, shared.id)]})
        other.write({"deduplication_manager_ids": [(4, shared.id)]})

        self._wizard("spp.deduplication.manager.phone_number", "By phone").action_create_manager()

        self.assertTrue(shared.exists(), "another program still uses this method")
        self.assertIn(shared, other.deduplication_manager_ids)

    def test_the_sweep_spares_a_method_reached_through_another_wrapper(self):
        """Two wrappers can point at one concrete; the cascade is not scoped.

        ``source_mixin.unlink()`` looks the wrappers up by ``manager_ref_id``
        across every program (``get_managers_for_unlink``), so deleting the
        concrete to clean up *this* program's leftover would take the other
        program's row with it and quietly return its card to "not configured".
        The sibling test above covers a shared *wrapper*; this one covers a
        shared *concrete*, which is the shape the Reference-field UI this
        wizard replaces allowed users to create (#445 review).
        """
        self._wizard("spp.deduplication.manager.id_dedup", "By ID").action_create_manager()
        leftover = self.program.deduplication_manager_ids
        concrete = leftover.manager_ref_id

        # A second wrapper on another program, pointing at the same method.
        other = self.env["spp.program"].create({"name": "Dedup Shared Concrete [TEST]"})
        twin = self.env["spp.deduplication.manager"].create(
            {
                "program_id": other.id,
                "manager_ref_id": f"{concrete._name},{concrete.id}",
            }
        )
        other.write({"deduplication_manager_ids": [(4, twin.id)]})

        # Remove it from this program's card, then trip the sweep.
        self.program.write({"deduplication_manager_ids": [(3, leftover.id)]})
        self._wizard("spp.deduplication.manager.phone_number", "By phone").action_create_manager()

        self.assertFalse(leftover.exists(), "this program's leftover row should be swept")
        self.assertTrue(concrete.exists(), "the method itself is still in use elsewhere")
        self.assertTrue(twin.exists(), "the other program's row must survive the cascade")
        self.assertIn(twin, other.deduplication_manager_ids)
