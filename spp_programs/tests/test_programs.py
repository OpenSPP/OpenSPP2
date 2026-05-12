import uuid
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


class TestProgram(TransactionCase):
    def setUp(self):
        super().setUp()

        self.program = self.env["spp.program"].create({"name": "Test Program"})

        manager_default = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Default",
                "program_id": self.program.id,
            }
        )
        eligibility_manager = self.env["spp.eligibility.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": f"{manager_default._name},{str(manager_default.id)}",
            }
        )
        self.program.update({"eligibility_manager_ids": [(4, eligibility_manager.id)]})

        self.program_2 = self.env["spp.program"].create({"name": "Test Program 2"})

    @mute_logger("root")
    @patch("odoo.addons.spp_programs.models.programs.len")
    def test_01_import_eligible_registrants(self, mocker):
        mocker.__name__ = "len__mocker"
        action = self.program_2.import_eligible_registrants()

        self.assertEqual(
            [
                action.get("type"),
                action.get("tag"),
                action["params"].get("message"),
                action["params"].get("type"),
            ],
            [
                "ir.actions.client",
                "display_notification",
                "No Eligibility Manager defined.",
                "danger",
            ],
        )

        mocker.return_value = 1
        action_2 = self.program.import_eligible_registrants()

        self.assertEqual(
            [action_2.get("type"), action_2.get("tag"), action_2["params"].get("type")],
            ["ir.actions.client", "display_notification", "success"],
        )

        mocker.return_value = 1000
        action_3 = self.program.import_eligible_registrants()

        self.assertEqual(
            [action_3.get("type"), action_3.get("tag"), action_3["params"].get("type")],
            ["ir.actions.client", "display_notification", "success"],
        )


@tagged("post_install", "-at_install")
class TestSPPProgram(TransactionCase):
    """Comprehensive tests for the spp.program model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create registrant partners
        cls.registrant_group = cls.env["res.partner"].create(
            {
                "name": "Test Group Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.registrant_individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual Registrant [TEST]",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create the program used by most tests
        cls.program = cls.env["spp.program"].create({"name": f"Main Test Program [{uuid.uuid4().hex[:6]}]"})

        # ---------------------------------------------------------------
        # Approval definitions (required by cycle and entitlement managers)
        # ---------------------------------------------------------------
        cycle_model = cls.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)

        cls.cycle_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Cycle Approval [TEST]",
                "model_id": cycle_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )
        cls.entitlement_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Entitlement Approval [TEST]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # ---------------------------------------------------------------
        # Cycle manager: two-record pattern
        #   1. spp.cycle.manager.default  (implementation)
        #   2. spp.cycle.manager          (wrapper with manager_ref_id)
        # ---------------------------------------------------------------
        cls.cycle_manager_default = cls.env["spp.cycle.manager.default"].create(
            {
                "name": "Default Cycle Manager [TEST]",
                "program_id": cls.program.id,
                "approval_definition_id": cls.cycle_approval_definition.id,
            }
        )
        cls.cycle_manager = cls.env["spp.cycle.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"{cls.cycle_manager_default._name},{cls.cycle_manager_default.id}"),
            }
        )
        cls.program.write({"cycle_manager_ids": [(4, cls.cycle_manager.id)]})

        # ---------------------------------------------------------------
        # Entitlement manager: two-record pattern
        #   1. spp.program.entitlement.manager.default  (implementation)
        #   2. spp.program.entitlement.manager          (wrapper)
        # ---------------------------------------------------------------
        cls.entitlement_manager_default = cls.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Default Entitlement Manager [TEST]",
                "program_id": cls.program.id,
                "approval_definition_id": cls.entitlement_approval_definition.id,
            }
        )
        cls.entitlement_manager = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"{cls.entitlement_manager_default._name},{cls.entitlement_manager_default.id}"),
            }
        )
        cls.program.write({"entitlement_manager_ids": [(4, cls.entitlement_manager.id)]})

        # ---------------------------------------------------------------
        # Program manager: two-record pattern
        #   1. spp.program.manager.default  (implementation)
        #   2. spp.program.manager          (wrapper)
        # ---------------------------------------------------------------
        cls.program_manager_default = cls.env["spp.program.manager.default"].create(
            {
                "name": "Default Program Manager [TEST]",
                "program_id": cls.program.id,
            }
        )
        cls.program_manager = cls.env["spp.program.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"{cls.program_manager_default._name},{cls.program_manager_default.id}"),
            }
        )
        cls.program.write({"program_manager_ids": [(4, cls.program_manager.id)]})

        # ---------------------------------------------------------------
        # Eligibility manager
        # ---------------------------------------------------------------
        cls.eligibility_manager_default = cls.env["spp.program.membership.manager.default"].create(
            {
                "name": "Default Eligibility Manager [TEST]",
                "program_id": cls.program.id,
            }
        )
        cls.eligibility_manager = cls.env["spp.eligibility.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"{cls.eligibility_manager_default._name},{cls.eligibility_manager_default.id}"),
            }
        )
        cls.program.write({"eligibility_manager_ids": [(4, cls.eligibility_manager.id)]})

    # ------------------------------------------------------------------
    # Program creation
    # ------------------------------------------------------------------

    def test_program_creation_requires_name(self):
        """spp.program requires the name field at the DB level."""
        import psycopg2

        with self.assertRaises(psycopg2.IntegrityError):
            self.env["spp.program"].create({})

    def test_program_creation_default_state(self):
        """A newly created program defaults to 'active' state."""
        program = self.env["spp.program"].create({"name": f"State Check Program [{uuid.uuid4().hex[:6]}]"})
        self.assertEqual(program.state, "active")

    def test_program_creation_default_target_type(self):
        """A newly created program defaults to 'group' target_type."""
        program = self.env["spp.program"].create({"name": f"Target Type Program [{uuid.uuid4().hex[:6]}]"})
        self.assertEqual(program.target_type, "group")

    def test_program_unique_name_constraint(self):
        """Creating two programs with the same name raises UserError."""
        unique_name = f"Unique Program [{uuid.uuid4().hex[:6]}]"
        self.env["spp.program"].create({"name": unique_name})
        with self.assertRaises(UserError):
            self.env["spp.program"].create({"name": unique_name})

    def test_program_unique_name_allows_different_names(self):
        """Programs with different names can coexist."""
        p1 = self.env["spp.program"].create({"name": f"Program A [{uuid.uuid4().hex[:6]}]"})
        p2 = self.env["spp.program"].create({"name": f"Program B [{uuid.uuid4().hex[:6]}]"})
        self.assertNotEqual(p1.id, p2.id)

    # ------------------------------------------------------------------
    # get_manager()
    # ------------------------------------------------------------------

    def test_get_manager_cycle(self):
        """get_manager(MANAGER_CYCLE) returns the cycle manager implementation."""
        manager = self.program.get_manager(self.program.MANAGER_CYCLE)
        self.assertEqual(manager, self.cycle_manager_default)

    def test_get_manager_entitlement(self):
        """get_manager(MANAGER_ENTITLEMENT) returns the entitlement manager implementation."""
        manager = self.program.get_manager(self.program.MANAGER_ENTITLEMENT)
        self.assertEqual(manager, self.entitlement_manager_default)

    def test_get_manager_program(self):
        """get_manager(MANAGER_PROGRAM) returns the program manager implementation."""
        manager = self.program.get_manager(self.program.MANAGER_PROGRAM)
        self.assertEqual(manager, self.program_manager_default)

    def test_get_manager_unsupported_raises(self):
        """get_manager() raises NotImplementedError for unsupported manager kind."""
        with self.assertRaises(NotImplementedError):
            # MANAGER_ELIGIBILITY is handled by get_managers(), not get_manager()
            self.program.get_manager(self.program.MANAGER_ELIGIBILITY)

    def test_get_manager_returns_none_when_no_manager(self):
        """get_manager() returns None when no manager is configured."""
        program = self.env["spp.program"].create({"name": f"No Manager Program [{uuid.uuid4().hex[:6]}]"})
        result = program.get_manager(program.MANAGER_CYCLE)
        self.assertIsNone(result)

    def test_get_managers_eligibility(self):
        """get_managers(MANAGER_ELIGIBILITY) returns list of eligibility manager implementations."""
        managers = self.program.get_managers(self.program.MANAGER_ELIGIBILITY)
        self.assertIsInstance(managers, list)
        self.assertEqual(len(managers), 1)
        self.assertEqual(managers[0], self.eligibility_manager_default)

    def test_get_managers_unsupported_raises(self):
        """get_managers() raises NotImplementedError for unsupported kind."""
        with self.assertRaises(NotImplementedError):
            self.program.get_managers(self.program.MANAGER_CYCLE)

    # ------------------------------------------------------------------
    # Program membership management
    # ------------------------------------------------------------------

    def test_program_membership_ids_empty_by_default(self):
        """A new program has no memberships."""
        program = self.env["spp.program"].create({"name": f"Empty Membership Program [{uuid.uuid4().hex[:6]}]"})
        self.assertFalse(program.program_membership_ids)

    def test_has_members_false_when_no_memberships(self):
        """has_members is False when no memberships exist."""
        program = self.env["spp.program"].create({"name": f"No Members Program [{uuid.uuid4().hex[:6]}]"})
        self.assertFalse(program.has_members)

    def test_has_members_true_after_adding_membership(self):
        """has_members becomes True after a membership is added."""
        program = self.env["spp.program"].create({"name": f"With Members Program [{uuid.uuid4().hex[:6]}]"})
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant_group.id,
                "program_id": program.id,
                "state": "draft",
            }
        )
        self.assertTrue(program.has_members)

    def test_program_membership_creation(self):
        """A program membership can be created and linked to a program."""
        program = self.env["spp.program"].create({"name": f"Membership Test Program [{uuid.uuid4().hex[:6]}]"})
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant_group.id,
                "program_id": program.id,
                "state": "enrolled",
            }
        )
        self.assertEqual(membership.program_id, program)
        self.assertEqual(membership.state, "enrolled")

    def test_program_membership_uniqueness_constraint(self):
        """A registrant cannot be added to the same program twice."""
        program = self.env["spp.program"].create({"name": f"Unique Membership Program [{uuid.uuid4().hex[:6]}]"})
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant_group.id,
                "program_id": program.id,
            }
        )
        from psycopg2 import IntegrityError

        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["spp.program.membership"].create(
                {
                    "partner_id": self.registrant_group.id,
                    "program_id": program.id,
                }
            )

    # ------------------------------------------------------------------
    # count_beneficiaries() and get_beneficiaries()
    # ------------------------------------------------------------------

    def test_count_beneficiaries_no_state_filter(self):
        """count_beneficiaries(None) counts all memberships regardless of state."""
        program = self.env["spp.program"].create({"name": f"Count All Program [{uuid.uuid4().hex[:6]}]"})
        partner_a = self.env["res.partner"].create({"name": "Count A [TEST]", "is_registrant": True, "is_group": True})
        partner_b = self.env["res.partner"].create({"name": "Count B [TEST]", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create(
            [
                {"partner_id": partner_a.id, "program_id": program.id, "state": "enrolled"},
                {"partner_id": partner_b.id, "program_id": program.id, "state": "draft"},
            ]
        )
        result = program.count_beneficiaries(None)
        self.assertEqual(result["value"], 2)

    def test_count_beneficiaries_with_state_filter(self):
        """count_beneficiaries(['enrolled']) counts only enrolled memberships."""
        program = self.env["spp.program"].create({"name": f"Count Enrolled Program [{uuid.uuid4().hex[:6]}]"})
        partner_a = self.env["res.partner"].create(
            {"name": "Enrolled A [TEST]", "is_registrant": True, "is_group": True}
        )
        partner_b = self.env["res.partner"].create({"name": "Draft B [TEST]", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create(
            [
                {"partner_id": partner_a.id, "program_id": program.id, "state": "enrolled"},
                {"partner_id": partner_b.id, "program_id": program.id, "state": "draft"},
            ]
        )
        result = program.count_beneficiaries(["enrolled"])
        self.assertEqual(result["value"], 1)

    def test_get_beneficiaries_no_filter(self):
        """get_beneficiaries() with no state filter returns all memberships."""
        program = self.env["spp.program"].create({"name": f"Get Beneficiaries Program [{uuid.uuid4().hex[:6]}]"})
        partner_a = self.env["res.partner"].create({"name": "GB A [TEST]", "is_registrant": True, "is_group": True})
        partner_b = self.env["res.partner"].create({"name": "GB B [TEST]", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create(
            [
                {"partner_id": partner_a.id, "program_id": program.id, "state": "enrolled"},
                {"partner_id": partner_b.id, "program_id": program.id, "state": "draft"},
            ]
        )
        result = program.get_beneficiaries()
        self.assertEqual(len(result), 2)

    def test_get_beneficiaries_with_state_string(self):
        """get_beneficiaries() accepts a single state string."""
        program = self.env["spp.program"].create({"name": f"Get Beneficiaries State String [{uuid.uuid4().hex[:6]}]"})
        partner_a = self.env["res.partner"].create({"name": "GBS A [TEST]", "is_registrant": True, "is_group": True})
        partner_b = self.env["res.partner"].create({"name": "GBS B [TEST]", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create(
            [
                {"partner_id": partner_a.id, "program_id": program.id, "state": "enrolled"},
                {"partner_id": partner_b.id, "program_id": program.id, "state": "draft"},
            ]
        )
        result = program.get_beneficiaries(state="enrolled")
        self.assertEqual(len(result), 1)

    def test_get_beneficiaries_count_mode(self):
        """get_beneficiaries(count=True) returns an integer count."""
        program = self.env["spp.program"].create({"name": f"Count Mode Program [{uuid.uuid4().hex[:6]}]"})
        partner_a = self.env["res.partner"].create({"name": "CM A [TEST]", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create(
            {"partner_id": partner_a.id, "program_id": program.id, "state": "enrolled"}
        )
        count = program.get_beneficiaries(count=True)
        self.assertEqual(count, 1)

    def test_get_beneficiaries_cursor_pagination(self):
        """get_beneficiaries() with last_id uses cursor-based pagination."""
        program = self.env["spp.program"].create({"name": f"Cursor Pagination Program [{uuid.uuid4().hex[:6]}]"})
        partners = self.env["res.partner"].create(
            [{"name": f"CP {i} [TEST]", "is_registrant": True, "is_group": True} for i in range(3)]
        )
        memberships = self.env["spp.program.membership"].create(
            [{"partner_id": p.id, "program_id": program.id, "state": "enrolled"} for p in partners]
        )
        # Get first record to use as last_id for pagination
        first_membership = memberships.sorted("id")[0]
        result = program.get_beneficiaries(last_id=first_membership.id)
        # Should return records with id > first_membership.id
        self.assertTrue(all(r.id > first_membership.id for r in result))

    # ------------------------------------------------------------------
    # _compute_eligible_beneficiary_count()
    # ------------------------------------------------------------------

    def test_compute_eligible_beneficiary_count_enrolled_only(self):
        """eligible_beneficiaries_count counts only 'enrolled' memberships."""
        program = self.env["spp.program"].create({"name": f"Eligible Count Program [{uuid.uuid4().hex[:6]}]"})
        partner_enrolled = self.env["res.partner"].create(
            {"name": "Enrolled [TEST]", "is_registrant": True, "is_group": True}
        )
        partner_draft = self.env["res.partner"].create(
            {"name": "Draft [TEST]", "is_registrant": True, "is_group": True}
        )
        self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": partner_enrolled.id,
                    "program_id": program.id,
                    "state": "enrolled",
                },
                {
                    "partner_id": partner_draft.id,
                    "program_id": program.id,
                    "state": "draft",
                },
            ]
        )
        program._compute_eligible_beneficiary_count()
        self.assertEqual(program.eligible_beneficiaries_count, 1)

    def test_compute_beneficiary_count_all_states(self):
        """beneficiaries_count counts all memberships regardless of state."""
        program = self.env["spp.program"].create({"name": f"All States Count Program [{uuid.uuid4().hex[:6]}]"})
        for i, state in enumerate(["enrolled", "draft", "not_eligible"]):
            partner = self.env["res.partner"].create(
                {
                    "name": f"Beneficiary {i} [TEST]",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
            self.env["spp.program.membership"].create(
                {"partner_id": partner.id, "program_id": program.id, "state": state}
            )
        program._compute_beneficiary_count()
        self.assertEqual(program.beneficiaries_count, 3)

    # ------------------------------------------------------------------
    # Program state management: end_program / reactivate_program
    # ------------------------------------------------------------------

    def test_end_program_transitions_to_ended(self):
        """end_program() sets state to 'ended' for an active program."""
        program = self.env["spp.program"].create({"name": f"End State Program [{uuid.uuid4().hex[:6]}]"})
        self.assertEqual(program.state, "active")
        program.with_context(active_ids=[program.id]).end_program()
        self.assertEqual(program.state, "ended")
        self.assertEqual(program.date_ended, fields.Date.today())

    def test_end_program_already_ended_returns_notification(self):
        """end_program() on an already-ended program returns a danger notification."""
        program = self.env["spp.program"].create({"name": f"Already Ended Program [{uuid.uuid4().hex[:6]}]"})
        program.with_context(active_ids=[program.id]).end_program()
        # Calling again on an ended program
        result = program.with_context(active_ids=[program.id]).end_program()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "danger")

    def test_reactivate_program_transitions_to_active(self):
        """reactivate_program() sets state back to 'active' for an ended program."""
        program = self.env["spp.program"].create({"name": f"Reactivate Program [{uuid.uuid4().hex[:6]}]"})
        program.with_context(active_ids=[program.id]).end_program()
        self.assertEqual(program.state, "ended")
        program.with_context(active_ids=[program.id]).reactivate_program()
        self.assertEqual(program.state, "active")
        self.assertFalse(program.date_ended)

    def test_reactivate_active_program_returns_notification(self):
        """reactivate_program() on an already-active program returns a danger notification."""
        program = self.env["spp.program"].create({"name": f"Already Active Program [{uuid.uuid4().hex[:6]}]"})
        result = program.with_context(active_ids=[program.id]).reactivate_program()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "danger")

    # ------------------------------------------------------------------
    # create_new_cycle()
    # ------------------------------------------------------------------

    def test_create_new_cycle_raises_when_no_beneficiaries(self):
        """create_new_cycle() raises UserError when no enrolled registrants exist."""
        with self.assertRaises(UserError, msg="No enrolled registrants"):
            self.program.create_new_cycle()

    def test_create_new_cycle_raises_when_no_cycle_manager(self):
        """create_new_cycle() raises UserError when no cycle manager is configured."""
        program = self.env["spp.program"].create({"name": f"No Cycle Manager Program [{uuid.uuid4().hex[:6]}]"})
        partner = self.env["res.partner"].create(
            {"name": "NCM Registrant [TEST]", "is_registrant": True, "is_group": True}
        )
        self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": program.id,
                "state": "enrolled",
            }
        )
        with self.assertRaises(UserError, msg="No Cycle Manager defined"):
            program.create_new_cycle()

    def test_create_new_cycle_raises_when_no_program_manager(self):
        """create_new_cycle() raises UserError when no program manager is configured."""
        program = self.env["spp.program"].create({"name": f"No Program Manager Program [{uuid.uuid4().hex[:6]}]"})
        partner = self.env["res.partner"].create(
            {
                "name": "NPM Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": program.id,
                "state": "enrolled",
            }
        )
        # Attach a cycle manager but no program manager
        cycle_manager_default = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Cycle Manager Only [TEST]",
                "program_id": program.id,
                "approval_definition_id": self.cycle_approval_definition.id,
            }
        )
        cycle_manager = self.env["spp.cycle.manager"].create(
            {
                "program_id": program.id,
                "manager_ref_id": (f"{cycle_manager_default._name},{cycle_manager_default.id}"),
            }
        )
        program.write({"cycle_manager_ids": [(4, cycle_manager.id)]})
        with self.assertRaises(UserError, msg="No Program Manager defined"):
            program.create_new_cycle()

    def test_create_new_cycle_returns_success_notification(self):
        """create_new_cycle() returns a success notification when all managers are set."""
        # Add an enrolled beneficiary so beneficiaries_count > 0
        partner = self.env["res.partner"].create(
            {
                "name": "Cycle Creator Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": self.program.id,
                "state": "enrolled",
            }
        )
        result = self.program.create_new_cycle()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    # ------------------------------------------------------------------
    # check_managers_limit() constraint
    # ------------------------------------------------------------------

    def test_check_managers_limit_allows_one_cycle_manager(self):
        """A program with exactly one cycle manager passes the constraint."""
        # The program in setUpClass already has one cycle manager; confirm no error
        self.assertEqual(len(self.program.cycle_manager_ids), 1)

    def test_check_managers_limit_raises_for_two_cycle_managers(self):
        """Adding a second cycle manager raises UserError."""
        program = self.env["spp.program"].create({"name": f"Double Cycle Manager Program [{uuid.uuid4().hex[:6]}]"})
        cycle_def_1 = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Cycle Mgr 1 [TEST]",
                "program_id": program.id,
                "approval_definition_id": self.cycle_approval_definition.id,
            }
        )
        cycle_mgr_1 = self.env["spp.cycle.manager"].create(
            {
                "program_id": program.id,
                "manager_ref_id": f"{cycle_def_1._name},{cycle_def_1.id}",
            }
        )
        cycle_def_2 = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Cycle Mgr 2 [TEST]",
                "program_id": program.id,
                "approval_definition_id": self.cycle_approval_definition.id,
            }
        )
        cycle_mgr_2 = self.env["spp.cycle.manager"].create(
            {
                "program_id": program.id,
                "manager_ref_id": f"{cycle_def_2._name},{cycle_def_2.id}",
            }
        )
        with self.assertRaises(UserError):
            program.write({"cycle_manager_ids": [(4, cycle_mgr_1.id), (4, cycle_mgr_2.id)]})

    def test_check_managers_limit_raises_for_two_entitlement_managers(self):
        """Adding a second entitlement manager raises UserError."""
        program = self.env["spp.program"].create(
            {"name": f"Double Entitlement Manager Program [{uuid.uuid4().hex[:6]}]"}
        )
        ent_def_1 = self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Ent Mgr 1 [TEST]",
                "program_id": program.id,
                "approval_definition_id": self.entitlement_approval_definition.id,
            }
        )
        ent_mgr_1 = self.env["spp.program.entitlement.manager"].create(
            {
                "program_id": program.id,
                "manager_ref_id": f"{ent_def_1._name},{ent_def_1.id}",
            }
        )
        ent_def_2 = self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Ent Mgr 2 [TEST]",
                "program_id": program.id,
                "approval_definition_id": self.entitlement_approval_definition.id,
            }
        )
        ent_mgr_2 = self.env["spp.program.entitlement.manager"].create(
            {
                "program_id": program.id,
                "manager_ref_id": f"{ent_def_2._name},{ent_def_2.id}",
            }
        )
        with self.assertRaises(UserError):
            program.write(
                {
                    "entitlement_manager_ids": [
                        (4, ent_mgr_1.id),
                        (4, ent_mgr_2.id),
                    ]
                }
            )

    def test_check_managers_limit_raises_for_two_program_managers(self):
        """Adding a second program manager raises UserError."""
        program = self.env["spp.program"].create({"name": f"Double Program Manager Program [{uuid.uuid4().hex[:6]}]"})
        prog_def_1 = self.env["spp.program.manager.default"].create(
            {"name": "Prog Mgr 1 [TEST]", "program_id": program.id}
        )
        prog_mgr_1 = self.env["spp.program.manager"].create(
            {
                "program_id": program.id,
                "manager_ref_id": f"{prog_def_1._name},{prog_def_1.id}",
            }
        )
        prog_def_2 = self.env["spp.program.manager.default"].create(
            {"name": "Prog Mgr 2 [TEST]", "program_id": program.id}
        )
        prog_mgr_2 = self.env["spp.program.manager"].create(
            {
                "program_id": program.id,
                "manager_ref_id": f"{prog_def_2._name},{prog_def_2.id}",
            }
        )
        with self.assertRaises(UserError):
            program.write({"program_manager_ids": [(4, prog_mgr_1.id), (4, prog_mgr_2.id)]})

    # ------------------------------------------------------------------
    # Enrollment flows
    # ------------------------------------------------------------------

    def test_enroll_eligible_registrants_raises_when_no_beneficiaries(self):
        """enroll_eligible_registrants() raises UserError when beneficiaries_count is 0."""
        program = self.env["spp.program"].create({"name": f"Empty Enrollment Program [{uuid.uuid4().hex[:6]}]"})
        with self.assertRaises(UserError):
            program.enroll_eligible_registrants()

    def test_enroll_eligible_registrants_raises_when_no_program_manager(self):
        """enroll_eligible_registrants() raises UserError when no program manager is set."""
        program = self.env["spp.program"].create({"name": f"No Manager Enrollment Program [{uuid.uuid4().hex[:6]}]"})
        partner = self.env["res.partner"].create(
            {
                "name": "Enroll Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": program.id,
                "state": "draft",
            }
        )
        with self.assertRaises(UserError):
            program.enroll_eligible_registrants()

    def test_verify_eligibility_raises_when_no_program_manager(self):
        """verify_eligibility() raises UserError when no program manager is configured."""
        program = self.env["spp.program"].create({"name": f"No Mgr Verify Eligibility [{uuid.uuid4().hex[:6]}]"})
        partner = self.env["res.partner"].create(
            {
                "name": "VE Registrant [TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": program.id,
                "state": "draft",
            }
        )
        with self.assertRaises(UserError):
            program.verify_eligibility()

    # ------------------------------------------------------------------
    # Fund management integration
    # ------------------------------------------------------------------

    def test_create_journal_creates_journal_for_program(self):
        """create_journal() creates an account.journal linked to the program."""
        program = self.env["spp.program"].create({"name": f"Journal Program [{uuid.uuid4().hex[:6]}]"})
        self.assertFalse(program.journal_id)
        program.create_journal()
        self.assertTrue(program.journal_id)
        self.assertTrue(program.journal_id.is_beneficiary_disb)

    # ------------------------------------------------------------------
    # Cycle count computed field
    # ------------------------------------------------------------------

    def test_compute_cycle_count_with_no_cycles(self):
        """cycles_count is zero when no cycles exist for the program."""
        program = self.env["spp.program"].create({"name": f"No Cycles Program [{uuid.uuid4().hex[:6]}]"})
        self.assertEqual(program.cycles_count, 0)

    def test_compute_cycle_count_increments_with_new_cycle(self):
        """cycles_count increments when a new cycle is created for the program."""
        program = self.env["spp.program"].create({"name": f"Cycle Count Program [{uuid.uuid4().hex[:6]}]"})
        self.assertEqual(program.cycles_count, 0)
        self.env["spp.cycle"].create(
            {
                "name": "Test Cycle [TEST]",
                "program_id": program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )
        program._compute_cycle_count()
        self.assertEqual(program.cycles_count, 1)

    # ------------------------------------------------------------------
    # Hook methods
    # ------------------------------------------------------------------

    def test_pre_enrollment_hook_callable(self):
        """_pre_enrollment_hook() can be called without error."""
        # Base implementation is a no-op; verifying it does not raise
        self.program._pre_enrollment_hook(self.registrant_group)

    def test_post_enrollment_hook_callable(self):
        """_post_enrollment_hook() can be called without error."""
        self.program._post_enrollment_hook(self.registrant_group)

    # ------------------------------------------------------------------
    # create_default_managers (via context)
    # ------------------------------------------------------------------

    def test_create_default_managers_context(self):
        """create_default_managers is invoked when context flag is set."""
        program = (
            self.env["spp.program"]
            .with_context(create_default_managers=True)
            .create({"name": f"Default Managers Program [{uuid.uuid4().hex[:6]}]"})
        )
        # At minimum, a cycle manager, entitlement manager, and program manager
        # should have been created automatically.
        self.assertTrue(program.cycle_manager_ids)
        self.assertTrue(program.entitlement_manager_ids)
        self.assertTrue(program.program_manager_ids)

    # ------------------------------------------------------------------
    # Refresh record action (soft reload — see OP#950)
    # ------------------------------------------------------------------

    def test_action_refresh_record_returns_none(self):
        """`action_refresh_record` returns None so Odoo's view-button hook
        falls through to `model.load()`, refreshing the record in place
        without changing the route or closing the dialog (vs. the old
        `refresh_page` which returned `tag="reload"` and triggered a full
        browser reload that destroyed breadcrumbs)."""
        self.assertIsNone(self.program.action_refresh_record())

    # ------------------------------------------------------------------
    # open_eligible_beneficiaries_form / open_cycles_form / open_program_form
    # ------------------------------------------------------------------

    def test_open_eligible_beneficiaries_form_returns_action(self):
        """open_eligible_beneficiaries_form() returns an act_window action."""
        result = self.program.open_eligible_beneficiaries_form()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.program.membership")

    def test_open_duplicate_membership_form_returns_action(self):
        """open_duplicate_membership_form() returns an act_window for duplicates."""
        result = self.program.open_duplicate_membership_form()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.program.membership")
        self.assertIn(("state", "=", "duplicated"), result["domain"])

    def test_open_cycles_form_returns_action(self):
        """open_cycles_form() returns an act_window action for cycles."""
        result = self.program.open_cycles_form()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.cycle")

    def test_open_program_form_returns_action(self):
        """open_program_form() returns a form act_window action."""
        result = self.program.open_program_form()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["view_mode"], "form")
        self.assertEqual(result["res_id"], self.program.id)

    # ------------------------------------------------------------------
    # Deduplication error path
    # ------------------------------------------------------------------

    def test_deduplicate_beneficiaries_raises_when_no_deduplication_manager(self):
        """deduplicate_beneficiaries() raises UserError when no manager is configured."""
        program = self.env["spp.program"].create({"name": f"No Dedup Manager Program [{uuid.uuid4().hex[:6]}]"})
        with self.assertRaises(UserError):
            program.deduplicate_beneficiaries()

    # ------------------------------------------------------------------
    # Lock fields
    # ------------------------------------------------------------------

    def test_program_is_locked_defaults_to_false(self):
        """A newly created program is not locked."""
        program = self.env["spp.program"].create({"name": f"Lock Default Program [{uuid.uuid4().hex[:6]}]"})
        self.assertFalse(program.is_locked)

    def test_program_can_be_locked(self):
        """A program can be locked and the locked_reason can be set."""
        program = self.env["spp.program"].create({"name": f"Lock Test Program [{uuid.uuid4().hex[:6]}]"})
        program.write({"is_locked": True, "locked_reason": "Background import in progress"})
        self.assertTrue(program.is_locked)
        self.assertEqual(program.locked_reason, "Background import in progress")

    # ------------------------------------------------------------------
    # has_compliance_criteria
    # ------------------------------------------------------------------

    def test_has_compliance_criteria_false_by_default(self):
        """has_compliance_criteria is False when no compliance managers exist."""
        program = self.env["spp.program"].create({"name": f"No Compliance Program [{uuid.uuid4().hex[:6]}]"})
        self.assertFalse(program.has_compliance_criteria)
