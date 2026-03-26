# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Comprehensive tests for manager models in spp_programs/models/managers/.

Covers:
- CycleManager / DefaultCycleManager
- DefaultCashEntitlementManager
- PaymentManager / DefaultFilePaymentManager
- ProgramManager / DefaultProgramManager
- DeduplicationManager / DefaultDeduplication
"""

import logging

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestCycleManagerSelection(TransactionCase):
    """Tests for CycleManager._selection_manager_ref_id."""

    def test_selection_includes_default(self):
        """_selection_manager_ref_id must include the Default cycle manager."""
        manager = self.env["spp.cycle.manager"]
        selection = manager._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        self.assertIn(
            "spp.cycle.manager.default",
            model_names,
            "Selection must include spp.cycle.manager.default",
        )

    def test_selection_no_duplicates(self):
        """Each manager type must appear at most once in the selection."""
        manager = self.env["spp.cycle.manager"]
        selection = manager._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        self.assertEqual(
            len(model_names),
            len(set(model_names)),
            "Selection should not contain duplicate entries",
        )


@tagged("post_install", "-at_install")
class TestEntitlementManagerSelection(TransactionCase):
    """Tests for EntitlementManager._selection_manager_ref_id."""

    def test_selection_includes_default(self):
        """_selection_manager_ref_id must include the Default entitlement manager."""
        manager = self.env["spp.program.entitlement.manager"]
        selection = manager._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        self.assertIn(
            "spp.program.entitlement.manager.default",
            model_names,
            "Selection must include spp.program.entitlement.manager.default",
        )


@tagged("post_install", "-at_install")
class TestPaymentManagerSelection(TransactionCase):
    """Tests for PaymentManager._selection_manager_ref_id."""

    def test_selection_includes_default(self):
        """_selection_manager_ref_id must include the Default payment manager."""
        manager = self.env["spp.program.payment.manager"]
        selection = manager._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        self.assertIn(
            "spp.program.payment.manager.default",
            model_names,
            "Selection must include spp.program.payment.manager.default",
        )


@tagged("post_install", "-at_install")
class TestProgramManagerSelection(TransactionCase):
    """Tests for ProgramManager._selection_manager_ref_id."""

    def test_selection_includes_default(self):
        """_selection_manager_ref_id must include the Default program manager."""
        manager = self.env["spp.program.manager"]
        selection = manager._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        self.assertIn(
            "spp.program.manager.default",
            model_names,
            "Selection must include spp.program.manager.default",
        )


@tagged("post_install", "-at_install")
class TestDeduplicationManagerSelection(TransactionCase):
    """Tests for DeduplicationManager._selection_manager_ref_id."""

    def test_selection_includes_all_defaults(self):
        """_selection_manager_ref_id must include all three built-in dedup managers."""
        manager = self.env["spp.deduplication.manager"]
        selection = manager._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        for expected in [
            "spp.deduplication.manager.default",
            "spp.deduplication.manager.phone_number",
            "spp.deduplication.manager.id_dedup",
        ]:
            self.assertIn(expected, model_names, f"Selection must include {expected}")


@tagged("post_install", "-at_install")
class TestDefaultCycleManagerBase(TransactionCase):
    """
    Integration tests for DefaultCycleManager.

    Each test that modifies state creates its own cycle to avoid inter-test
    interference within the same transaction.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        cls.company = cls.env.company
        cls.currency = cls.env.ref("base.USD")

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Disbursement Journal [MANAGERS TEST]",
                "code": "TMGJ",
                "type": "bank",
                "currency_id": cls.currency.id,
                "company_id": cls.company.id,
                "is_beneficiary_disb": True,
            }
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program [MANAGERS TEST]",
                "journal_id": cls.journal.id,
            }
        )

        # Entitlement approval definition
        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
        cls.entitlement_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Entitlement Approval [MANAGERS TEST]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # Entitlement manager — two-record pattern
        cls.entitlement_manager_default = cls.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Test Entitlement Manager [MANAGERS TEST]",
                "program_id": cls.program.id,
                "amount_per_cycle": 100.0,
                "amount_per_individual_in_group": 0.0,
                "approval_definition_id": cls.entitlement_approval_definition.id,
            }
        )
        cls.entitlement_manager = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.default,{cls.entitlement_manager_default.id}"),
            }
        )

        # Cycle approval definition
        cycle_model = cls.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
        cls.cycle_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Cycle Approval [MANAGERS TEST]",
                "model_id": cycle_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # Cycle manager — two-record pattern
        cls.cycle_manager_default = cls.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager [MANAGERS TEST]",
                "program_id": cls.program.id,
                "auto_approve_entitlements": False,
                "approval_definition_id": cls.cycle_approval_definition.id,
            }
        )
        cls.cycle_manager = cls.env["spp.cycle.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.cycle.manager.default,{cls.cycle_manager_default.id}"),
            }
        )

        # Link managers to program
        cls.program.write(
            {
                "cycle_manager_ids": [(4, cls.cycle_manager.id)],
                "entitlement_manager_ids": [(4, cls.entitlement_manager.id)],
            }
        )

        # Beneficiaries
        cls.beneficiary1 = cls.env["res.partner"].create(
            {
                "name": "Beneficiary 1 [MANAGERS TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.beneficiary2 = cls.env["res.partner"].create(
            {
                "name": "Beneficiary 2 [MANAGERS TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Enroll beneficiaries in the program
        cls.env["spp.program.membership"].create(
            [
                {
                    "partner_id": cls.beneficiary1.id,
                    "program_id": cls.program.id,
                    "state": "enrolled",
                },
                {
                    "partner_id": cls.beneficiary2.id,
                    "program_id": cls.program.id,
                    "state": "enrolled",
                },
            ]
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_cycle(self, name, state="draft"):
        today = fields.Date.today()
        return self.env["spp.cycle"].create(
            {
                "name": name,
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": state,
            }
        )

    def _add_enrolled_members(self, cycle):
        self.env["spp.cycle.membership"].create(
            [
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary1.id,
                    "state": "enrolled",
                },
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary2.id,
                    "state": "enrolled",
                },
            ]
        )

    # ------------------------------------------------------------------
    # DefaultCycleManager.new_cycle
    # ------------------------------------------------------------------

    def test_new_cycle_creates_cycle_with_dates(self):
        """new_cycle() must create an spp.cycle record with non-null dates."""
        today = fields.Date.today()
        cycle = self.cycle_manager_default.new_cycle("New Cycle Via Manager [MANAGERS TEST]", today, 1)
        self.assertTrue(cycle, "new_cycle should return a cycle record")
        self.assertTrue(cycle.start_date, "Cycle start_date must be set")
        self.assertTrue(cycle.end_date, "Cycle end_date must be set")
        self.assertEqual(cycle.program_id, self.program)
        self.assertEqual(cycle.state, "draft")

    def test_new_cycle_inherits_auto_approve_flag(self):
        """Cycles created by the manager must inherit auto_approve_entitlements."""
        self.cycle_manager_default.auto_approve_entitlements = True
        today = fields.Date.today()
        cycle = self.cycle_manager_default.new_cycle("Auto Approve Cycle [MANAGERS TEST]", today, 2)
        self.assertTrue(
            cycle.auto_approve_entitlements,
            "Cycle must inherit auto_approve_entitlements=True from manager",
        )
        # Restore default
        self.cycle_manager_default.auto_approve_entitlements = False

    # ------------------------------------------------------------------
    # DefaultCycleManager.mark_ended / mark_cancelled / mark_distributed
    # ------------------------------------------------------------------

    def test_mark_ended_sets_state(self):
        """mark_ended() must transition cycle state to the ended constant."""
        cycle = self._make_cycle("Mark Ended Cycle [MANAGERS TEST]", state="approved")
        self.cycle_manager_default.mark_ended(cycle)
        self.assertEqual(cycle.state, "ended", "State should be 'ended' after mark_ended")

    def test_mark_cancelled_sets_state(self):
        """mark_cancelled() must transition cycle state to cancelled."""
        cycle = self._make_cycle("Mark Cancelled Cycle [MANAGERS TEST]", state="approved")
        self.cycle_manager_default.mark_cancelled(cycle)
        self.assertEqual(cycle.state, "cancelled", "State should be 'cancelled' after mark_cancelled")

    def test_mark_distributed_sets_state(self):
        """mark_distributed() must transition cycle state to distributed."""
        cycle = self._make_cycle("Mark Distributed Cycle [MANAGERS TEST]", state="approved")
        self.cycle_manager_default.mark_distributed(cycle)
        self.assertEqual(
            cycle.state,
            "distributed",
            "State should be 'distributed' after mark_distributed",
        )

    # ------------------------------------------------------------------
    # DefaultCycleManager.approve_cycle
    # ------------------------------------------------------------------

    def test_approve_cycle_wrong_state_returns_danger_notification(self):
        """approve_cycle on a draft cycle returns a danger client notification."""
        cycle = self._make_cycle("Draft Approve Cycle [MANAGERS TEST]", state="draft")
        result = self.cycle_manager_default.approve_cycle(cycle)
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "danger")

    def test_approve_cycle_transitions_to_approved(self):
        """approve_cycle on a 'to_approve' cycle must set state=approved (as admin)."""
        cycle = self._make_cycle("To Approve Cycle [MANAGERS TEST]", state="to_approve")
        # Run as superuser (uid=1) to skip the group membership check in on_state_change
        self.cycle_manager_default.sudo().approve_cycle(cycle)
        self.assertEqual(
            cycle.state,
            "approved",
            "Cycle state should be 'approved' after approve_cycle",
        )
        self.assertTrue(cycle.approved_date, "approved_date must be set")

    # ------------------------------------------------------------------
    # DefaultCycleManager.on_state_change validation
    # ------------------------------------------------------------------

    def test_on_state_change_raises_when_no_approval_definition(self):
        """on_state_change must raise ValidationError if approval_definition_id is unset."""
        cycle = self._make_cycle("No Approval Def Cycle [MANAGERS TEST]", state="approved")
        # Create a manager without an approval definition
        manager_no_def = self.env["spp.cycle.manager.default"].create(
            {
                "name": "No Approval Def Manager [MANAGERS TEST]",
                "program_id": self.program.id,
            }
        )
        with self.assertRaises(ValidationError):
            manager_no_def.on_state_change(cycle)

    # ------------------------------------------------------------------
    # DefaultCycleManager.prepare_entitlements
    # ------------------------------------------------------------------

    def test_prepare_entitlements_creates_entitlements(self):
        """prepare_entitlements delegates to the entitlement manager and creates records."""
        cycle = self._make_cycle("Prepare Entitlements Cycle [MANAGERS TEST]")
        self._add_enrolled_members(cycle)

        before_count = self.env["spp.entitlement"].search_count([("cycle_id", "=", cycle.id)])
        self.assertEqual(before_count, 0, "No entitlements before prepare_entitlements")

        self.cycle_manager_default.prepare_entitlements(cycle)

        after_count = self.env["spp.entitlement"].search_count([("cycle_id", "=", cycle.id)])
        self.assertGreater(after_count, 0, "Entitlements should be created")

    # ------------------------------------------------------------------
    # DefaultCycleManager.add_beneficiaries
    # ------------------------------------------------------------------

    def test_add_beneficiaries_returns_notification(self):
        """add_beneficiaries returns a client notification action dict."""
        cycle = self._make_cycle("Add Beneficiaries Cycle [MANAGERS TEST]")
        result = self.cycle_manager_default.add_beneficiaries(
            cycle,
            [self.beneficiary1.id, self.beneficiary2.id],
            state="enrolled",
        )
        self.assertIn("type", result, "Result must be an action dict")
        self.assertEqual(result["type"], "ir.actions.client")

    def test_add_beneficiaries_no_duplicates(self):
        """add_beneficiaries must not create duplicate cycle memberships."""
        cycle = self._make_cycle("No Dup Beneficiaries Cycle [MANAGERS TEST]")
        self.cycle_manager_default.add_beneficiaries(cycle, [self.beneficiary1.id], state="enrolled")
        # Adding the same beneficiary again should not create a second record
        self.cycle_manager_default.add_beneficiaries(cycle, [self.beneficiary1.id], state="enrolled")
        count = self.env["spp.cycle.membership"].search_count(
            [
                ("cycle_id", "=", cycle.id),
                ("partner_id", "=", self.beneficiary1.id),
            ]
        )
        self.assertEqual(count, 1, "Beneficiary should only appear once in the cycle")

    def test_add_beneficiaries_empty_list_returns_warning(self):
        """add_beneficiaries with an empty list returns a warning notification."""
        cycle = self._make_cycle("Empty Beneficiaries Cycle [MANAGERS TEST]")
        result = self.cycle_manager_default.add_beneficiaries(cycle, [], state="enrolled")
        self.assertEqual(result["params"]["type"], "warning")

    # ------------------------------------------------------------------
    # DefaultCycleManager recurrence fields
    # ------------------------------------------------------------------

    def test_cycle_duration_default_value(self):
        """cycle_duration should default to 1."""
        self.assertEqual(
            self.cycle_manager_default.cycle_duration,
            1,
            "cycle_duration must default to 1",
        )

    def test_compute_interval_from_cycle_duration(self):
        """interval must reflect cycle_duration."""
        self.cycle_manager_default.cycle_duration = 3
        self.cycle_manager_default._compute_interval()
        self.assertEqual(
            self.cycle_manager_default.interval,
            3,
            "interval should equal cycle_duration",
        )

    # ------------------------------------------------------------------
    # DefaultCycleManager._ensure_can_edit_cycle
    # ------------------------------------------------------------------

    def test_ensure_can_edit_cycle_raises_when_not_draft(self):
        """_ensure_can_edit_cycle must raise ValidationError for non-draft cycles."""
        cycle = self._make_cycle("Non Draft Edit Cycle [MANAGERS TEST]", state="to_approve")
        with self.assertRaises(ValidationError):
            self.cycle_manager_default._ensure_can_edit_cycle(cycle)

    def test_ensure_can_edit_cycle_passes_for_draft(self):
        """_ensure_can_edit_cycle must not raise for draft cycles."""
        cycle = self._make_cycle("Draft Edit Cycle [MANAGERS TEST]", state="draft")
        # Should not raise
        self.cycle_manager_default._ensure_can_edit_cycle(cycle)


@tagged("post_install", "-at_install")
class TestDefaultCashEntitlementManagerBase(TransactionCase):
    """
    Integration tests for DefaultCashEntitlementManager.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        cls.company = cls.env.company
        cls.currency = cls.env.ref("base.USD")

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Disbursement Journal [ENT MGR TEST]",
                "code": "TEMT",
                "type": "bank",
                "currency_id": cls.currency.id,
                "company_id": cls.company.id,
                "is_beneficiary_disb": True,
            }
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program [ENT MGR TEST]",
                "journal_id": cls.journal.id,
            }
        )

        # Approval definition for entitlements
        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
        cls.approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Entitlement Approval [ENT MGR TEST]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # Entitlement manager — two-record pattern
        cls.ent_manager_default = cls.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Test Entitlement Manager [ENT MGR TEST]",
                "program_id": cls.program.id,
                "amount_per_cycle": 200.0,
                "amount_per_individual_in_group": 50.0,
                "approval_definition_id": cls.approval_definition.id,
            }
        )
        cls.ent_manager = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.default,{cls.ent_manager_default.id}"),
            }
        )
        cls.program.write({"entitlement_manager_ids": [(4, cls.ent_manager.id)]})

        # Beneficiaries
        cls.beneficiary1 = cls.env["res.partner"].create(
            {
                "name": "Ent Beneficiary 1 [ENT MGR TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.beneficiary2 = cls.env["res.partner"].create(
            {
                "name": "Ent Beneficiary 2 [ENT MGR TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Enroll beneficiaries in program
        cls.env["spp.program.membership"].create(
            [
                {
                    "partner_id": cls.beneficiary1.id,
                    "program_id": cls.program.id,
                    "state": "enrolled",
                },
                {
                    "partner_id": cls.beneficiary2.id,
                    "program_id": cls.program.id,
                    "state": "enrolled",
                },
            ]
        )

        # Cycle
        today = fields.Date.today()
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle [ENT MGR TEST]",
                "program_id": cls.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
            }
        )
        # Enrolled cycle memberships
        cls.env["spp.cycle.membership"].create(
            [
                {
                    "cycle_id": cls.cycle.id,
                    "partner_id": cls.beneficiary1.id,
                    "state": "enrolled",
                },
                {
                    "cycle_id": cls.cycle.id,
                    "partner_id": cls.beneficiary2.id,
                    "state": "enrolled",
                },
            ]
        )

    # ------------------------------------------------------------------
    # prepare_entitlements
    # ------------------------------------------------------------------

    def test_prepare_entitlements_creates_one_per_beneficiary(self):
        """prepare_entitlements must create exactly one entitlement per enrolled member."""
        # Use a dedicated cycle to avoid interference with other tests
        today = fields.Date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Prepare Ent Cycle [ENT MGR TEST]",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
            }
        )
        self.env["spp.cycle.membership"].create(
            [
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary1.id,
                    "state": "enrolled",
                },
                {
                    "cycle_id": cycle.id,
                    "partner_id": self.beneficiary2.id,
                    "state": "enrolled",
                },
            ]
        )
        beneficiaries = self.env["spp.cycle.membership"].search(
            [("cycle_id", "=", cycle.id), ("state", "=", "enrolled")]
        )
        self.ent_manager_default.prepare_entitlements(cycle, beneficiaries)
        count = self.env["spp.entitlement"].search_count([("cycle_id", "=", cycle.id)])
        self.assertEqual(count, 2, "Two enrolled members should yield two entitlements")

    def test_prepare_entitlements_idempotent(self):
        """prepare_entitlements called twice should not create duplicate entitlements."""
        today = fields.Date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Idempotent Prepare Cycle [ENT MGR TEST]",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
            }
        )
        membership = self.env["spp.cycle.membership"].create(
            {
                "cycle_id": cycle.id,
                "partner_id": self.beneficiary1.id,
                "state": "enrolled",
            }
        )
        self.ent_manager_default.prepare_entitlements(cycle, membership)
        self.ent_manager_default.prepare_entitlements(cycle, membership)
        count = self.env["spp.entitlement"].search_count([("cycle_id", "=", cycle.id)])
        self.assertEqual(count, 1, "Duplicate entitlement must not be created")

    # ------------------------------------------------------------------
    # set_pending_validation_entitlements
    # ------------------------------------------------------------------

    def test_set_pending_validation_transitions_state(self):
        """set_pending_validation_entitlements must move draft entitlements to pending_validation."""
        today = fields.Date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Set Pending Validation Cycle [ENT MGR TEST]",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
            }
        )
        entitlement = self.env["spp.entitlement"].create(
            {
                "partner_id": self.beneficiary1.id,
                "cycle_id": cycle.id,
                "valid_from": today,
                "initial_amount": 200.0,
                "state": "draft",
            }
        )
        self.ent_manager_default.set_pending_validation_entitlements(cycle)
        self.assertEqual(
            entitlement.state,
            "pending_validation",
            "Entitlement state should be pending_validation after set_pending_validation_entitlements",
        )

    def test_set_pending_validation_raises_without_approval_definition(self):
        """set_pending_validation_entitlements must raise ValidationError if no approval definition."""
        today = fields.Date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": "No Def Pending Validation Cycle [ENT MGR TEST]",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
            }
        )
        self.env["spp.entitlement"].create(
            {
                "partner_id": self.beneficiary1.id,
                "cycle_id": cycle.id,
                "valid_from": today,
                "initial_amount": 50.0,
                "state": "draft",
            }
        )
        manager_no_def = self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "No Def Ent Manager [ENT MGR TEST]",
                "program_id": self.program.id,
                "amount_per_cycle": 100.0,
            }
        )
        with self.assertRaises(ValidationError):
            manager_no_def.set_pending_validation_entitlements(cycle)

    # ------------------------------------------------------------------
    # cancel_entitlements
    # ------------------------------------------------------------------

    def test_cancel_entitlements_sets_state_to_cancelled(self):
        """cancel_entitlements must set all relevant entitlements to 'cancelled'."""
        today = fields.Date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Cancel Ent Cycle [ENT MGR TEST]",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
            }
        )
        entitlement = self.env["spp.entitlement"].create(
            {
                "partner_id": self.beneficiary1.id,
                "cycle_id": cycle.id,
                "valid_from": today,
                "initial_amount": 100.0,
                "state": "draft",
            }
        )
        self.ent_manager_default.cancel_entitlements(cycle)
        self.assertEqual(
            entitlement.state,
            "cancelled",
            "Entitlement state should be 'cancelled'",
        )

    # ------------------------------------------------------------------
    # open_entitlements_form / open_entitlement_form
    # ------------------------------------------------------------------

    def test_open_entitlements_form_returns_correct_action(self):
        """open_entitlements_form must return an ir.actions.act_window for spp.entitlement."""
        result = self.ent_manager_default.open_entitlements_form(self.cycle)
        self.assertIn("type", result)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.entitlement")
        self.assertIn(("cycle_id", "=", self.cycle.id), result["domain"])

    def test_open_entitlement_form_returns_single_record_action(self):
        """open_entitlement_form must return a form action pointing to the entitlement record."""
        today = fields.Date.today()
        entitlement = self.env["spp.entitlement"].create(
            {
                "partner_id": self.beneficiary1.id,
                "cycle_id": self.cycle.id,
                "valid_from": today,
                "initial_amount": 100.0,
                "state": "draft",
            }
        )
        result = self.ent_manager_default.open_entitlement_form(entitlement)
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.entitlement")
        self.assertEqual(result["res_id"], entitlement.id)
        self.assertEqual(result["view_mode"], "form")
        self.assertEqual(result["target"], "new")

    # ------------------------------------------------------------------
    # IS_CASH_ENTITLEMENT flag
    # ------------------------------------------------------------------

    def test_is_cash_entitlement_flag(self):
        """IS_CASH_ENTITLEMENT must be True for DefaultCashEntitlementManager."""
        self.assertTrue(
            self.ent_manager_default.IS_CASH_ENTITLEMENT,
            "IS_CASH_ENTITLEMENT must be True",
        )

    # ------------------------------------------------------------------
    # _calculate_amount
    # ------------------------------------------------------------------

    def test_calculate_amount_per_cycle_only(self):
        """_calculate_amount for an individual beneficiary returns amount_per_cycle."""
        individual = self.env["res.partner"].create(
            {
                "name": "Calc Ent Individual [ENT MGR TEST]",
                "is_registrant": True,
                "is_group": False,
            }
        )
        amount = self.ent_manager_default._calculate_amount(individual, 0)
        self.assertEqual(amount, 200.0, "Amount should equal amount_per_cycle for individuals")

    def test_calculate_amount_includes_per_individual_for_group(self):
        """_calculate_amount for a group includes amount_per_individual_in_group."""
        group_partner = self.env["res.partner"].create(
            {
                "name": "Calc Ent Group [ENT MGR TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        # 200 (per cycle) + 2 * 50 (per individual) = 300
        amount = self.ent_manager_default._calculate_amount(group_partner, 2)
        self.assertEqual(amount, 300.0, "Amount should include per-individual amounts for groups")

    def test_calculate_amount_respects_max_individual_in_group(self):
        """_calculate_amount caps the individual count at max_individual_in_group."""
        self.ent_manager_default.max_individual_in_group = 1
        group_partner = self.env["res.partner"].create(
            {
                "name": "Calc Max Group [ENT MGR TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        # 200 + min(5, 1) * 50 = 250
        amount = self.ent_manager_default._calculate_amount(group_partner, 5)
        self.assertEqual(amount, 250.0, "Amount should be capped by max_individual_in_group")
        self.ent_manager_default.max_individual_in_group = 0  # Restore

    # ------------------------------------------------------------------
    # check_fund_balance
    # ------------------------------------------------------------------

    def test_check_fund_balance_returns_numeric(self):
        """check_fund_balance must return a numeric value (float)."""
        balance = self.ent_manager_default.check_fund_balance(self.program.id)
        self.assertIsInstance(balance, float, "check_fund_balance must return a float")

    def test_check_fund_balance_increases_with_fund(self):
        """check_fund_balance must increase after a posted program fund is created."""
        balance_before = self.ent_manager_default.check_fund_balance(self.program.id)
        self.env["spp.program.fund"].create(
            {
                "name": "PF Test Fund Balance [ENT MGR TEST]",
                "program_id": self.program.id,
                "amount": 10_000.0,
                "state": "posted",
            }
        )
        balance_after = self.ent_manager_default.check_fund_balance(self.program.id)
        self.assertGreater(
            balance_after,
            balance_before,
            "Fund balance should increase after adding a posted fund",
        )


@tagged("post_install", "-at_install")
class TestDefaultProgramManagerBase(TransactionCase):
    """
    Integration tests for DefaultProgramManager.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        cls.company = cls.env.company
        cls.currency = cls.env.ref("base.USD")

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Disbursement Journal [PROG MGR TEST]",
                "code": "TPMT",
                "type": "bank",
                "currency_id": cls.currency.id,
                "company_id": cls.company.id,
                "is_beneficiary_disb": True,
            }
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program [PROG MGR TEST]",
                "journal_id": cls.journal.id,
            }
        )

        # Cycle approval definition
        cycle_model = cls.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
        cls.cycle_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Cycle Approval [PROG MGR TEST]",
                "model_id": cycle_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # Cycle manager — two-record pattern
        cls.cycle_manager_default = cls.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager [PROG MGR TEST]",
                "program_id": cls.program.id,
                "approval_definition_id": cls.cycle_approval_definition.id,
            }
        )
        cls.cycle_manager = cls.env["spp.cycle.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.cycle.manager.default,{cls.cycle_manager_default.id}"),
            }
        )

        # Program manager — two-record pattern
        cls.prog_manager_default = cls.env["spp.program.manager.default"].create(
            {
                "name": "Test Program Manager [PROG MGR TEST]",
                "program_id": cls.program.id,
            }
        )
        cls.prog_manager = cls.env["spp.program.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.manager.default,{cls.prog_manager_default.id}"),
            }
        )

        # Eligibility manager
        cls.elig_manager_default = cls.env["spp.program.membership.manager.default"].create(
            {
                "name": "Test Eligibility Manager [PROG MGR TEST]",
                "program_id": cls.program.id,
                "eligibility_domain": "[]",
            }
        )
        cls.elig_manager = cls.env["spp.eligibility.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.membership.manager.default,{cls.elig_manager_default.id}"),
            }
        )

        # Entitlement approval definition
        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
        cls.entitlement_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Entitlement Approval [PROG MGR TEST]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )
        cls.ent_manager_default = cls.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Test Entitlement Manager [PROG MGR TEST]",
                "program_id": cls.program.id,
                "amount_per_cycle": 150.0,
                "approval_definition_id": cls.entitlement_approval_definition.id,
            }
        )
        cls.ent_manager = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.default,{cls.ent_manager_default.id}"),
            }
        )

        cls.program.write(
            {
                "cycle_manager_ids": [(4, cls.cycle_manager.id)],
                "program_manager_ids": [(4, cls.prog_manager.id)],
                "eligibility_manager_ids": [(4, cls.elig_manager.id)],
                "entitlement_manager_ids": [(4, cls.ent_manager.id)],
            }
        )

        # Registrant (draft state — not yet enrolled)
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Prog Mgr Registrant [PROG MGR TEST]",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.registrant.id,
                "program_id": cls.program.id,
                "state": "draft",
            }
        )

    # ------------------------------------------------------------------
    # ProgramManager._selection_manager_ref_id (wrapper model)
    # ------------------------------------------------------------------

    def test_program_manager_wrapper_selection(self):
        """spp.program.manager wrapper selection includes 'spp.program.manager.default'."""
        selection = self.env["spp.program.manager"]._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        self.assertIn("spp.program.manager.default", model_names)

    # ------------------------------------------------------------------
    # DefaultProgramManager.last_cycle
    # ------------------------------------------------------------------

    def test_last_cycle_returns_none_when_no_cycles(self):
        """last_cycle returns None when the program has no cycles."""
        # Create a fresh program with no cycles
        program_no_cycles = self.env["spp.program"].create({"name": "No Cycles Program [PROG MGR TEST]"})
        mgr = self.env["spp.program.manager.default"].create(
            {
                "name": "No Cycles Prog Manager [PROG MGR TEST]",
                "program_id": program_no_cycles.id,
            }
        )
        self.assertIsNone(mgr.last_cycle(), "last_cycle should return None when no cycles exist")

    # ------------------------------------------------------------------
    # DefaultProgramManager.new_cycle
    # ------------------------------------------------------------------

    def test_new_cycle_creates_cycle_for_program(self):
        """new_cycle creates a spp.cycle record linked to the program."""
        cycle = self.prog_manager_default.new_cycle()
        self.assertTrue(cycle, "new_cycle should return a cycle record")
        self.assertEqual(cycle.program_id, self.program)

    def test_new_cycle_increments_sequence(self):
        """Subsequent new_cycle calls produce increasing sequence numbers."""
        cycle1 = self.prog_manager_default.new_cycle()
        cycle2 = self.prog_manager_default.new_cycle()
        self.assertGreater(
            cycle2.sequence,
            cycle1.sequence,
            "Second cycle must have a higher sequence than first",
        )

    # ------------------------------------------------------------------
    # DefaultProgramManager.enroll_eligible_registrants
    # ------------------------------------------------------------------

    def test_enroll_eligible_registrants_returns_notification(self):
        """enroll_eligible_registrants must return a client notification action dict."""
        result = self.prog_manager_default.enroll_eligible_registrants(state=["draft"])
        self.assertIn("type", result)
        self.assertEqual(result["type"], "ir.actions.client")


@tagged("post_install", "-at_install")
class TestPaymentManagerBase(TransactionCase):
    """Tests for PaymentManager / DefaultFilePaymentManager."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        cls.company = cls.env.company
        cls.currency = cls.env.ref("base.USD")

        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Disbursement Journal [PAY MGR TEST]",
                "code": "TPAY",
                "type": "bank",
                "currency_id": cls.currency.id,
                "company_id": cls.company.id,
                "is_beneficiary_disb": True,
            }
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program [PAY MGR TEST]",
                "journal_id": cls.journal.id,
            }
        )

        # Payment batch tag is required by the constraint when create_batch=True
        cls.batch_tag = cls.env["spp.payment.batch.tag"].create(
            {
                "name": "Default Tag [PAY MGR TEST]",
                "order": 1,
                "domain": "[]",
                "max_batch_size": 500,
            }
        )

        # Payment manager — two-record pattern
        cls.pay_manager_default = cls.env["spp.program.payment.manager.default"].create(
            {
                "name": "Test Payment Manager [PAY MGR TEST]",
                "program_id": cls.program.id,
                "create_batch": True,
                "batch_tag_ids": [(4, cls.batch_tag.id)],
            }
        )
        cls.pay_manager = cls.env["spp.program.payment.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.program.payment.manager.default,{cls.pay_manager_default.id}"),
            }
        )
        cls.program.write({"payment_manager_ids": [(4, cls.pay_manager.id)]})

        today = fields.Date.today()
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle [PAY MGR TEST]",
                "program_id": cls.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "approved",
            }
        )

    # ------------------------------------------------------------------
    # _selection_manager_ref_id (wrapper)
    # ------------------------------------------------------------------

    def test_payment_manager_wrapper_selection(self):
        """spp.program.payment.manager wrapper selection includes Default."""
        selection = self.env["spp.program.payment.manager"]._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        self.assertIn("spp.program.payment.manager.default", model_names)

    # ------------------------------------------------------------------
    # send_payments with empty batches
    # ------------------------------------------------------------------

    def test_send_payments_empty_batches_returns_warning(self):
        """_send_payments with no batches returns a warning notification."""
        result = self.pay_manager_default._send_payments(None)
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["params"]["type"], "warning")

    # ------------------------------------------------------------------
    # prepare_payments with no approved entitlements
    # ------------------------------------------------------------------

    def test_prepare_payments_no_approved_entitlements_returns_danger(self):
        """prepare_payments when there are no approved entitlements returns danger."""
        result = self.pay_manager_default.prepare_payments(self.cycle)
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(
            result["params"]["type"],
            "danger",
            "Should return danger when no approved entitlements exist",
        )

    # ------------------------------------------------------------------
    # constrains_batch_tag_ids
    # ------------------------------------------------------------------

    def test_batch_tag_constraint_empty_tags_with_create_batch_raises(self):
        """batch_tag_ids constraint raises ValidationError when clearing tags with create_batch=True."""
        manager = self.env["spp.program.payment.manager.default"].create(
            {
                "name": "Constraint Test Pay Manager [PAY MGR TEST]",
                "program_id": self.program.id,
                "create_batch": True,
                "batch_tag_ids": [(4, self.batch_tag.id)],
            }
        )
        with self.assertRaises(ValidationError):
            manager.write({"batch_tag_ids": [(5,)]})


@tagged("post_install", "-at_install")
class TestDefaultDeduplicationManagerBase(TransactionCase):
    """
    Integration tests for DeduplicationManager / DefaultDeduplication.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program [DEDUP TEST]",
                "target_type": "group",
            }
        )

        # Deduplication manager — two-record pattern
        cls.dedup_manager_default = cls.env["spp.deduplication.manager.default"].create(
            {
                "name": "Test Dedup Manager [DEDUP TEST]",
                "program_id": cls.program.id,
            }
        )
        cls.dedup_manager = cls.env["spp.deduplication.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": (f"spp.deduplication.manager.default,{cls.dedup_manager_default.id}"),
            }
        )
        cls.program.write({"deduplication_manager_ids": [(4, cls.dedup_manager.id)]})

    # ------------------------------------------------------------------
    # _selection_manager_ref_id
    # ------------------------------------------------------------------

    def test_deduplication_manager_wrapper_selection(self):
        """spp.deduplication.manager wrapper selection includes all three built-in managers."""
        selection = self.env["spp.deduplication.manager"]._selection_manager_ref_id()
        model_names = [item[0] for item in selection]
        for expected in [
            "spp.deduplication.manager.default",
            "spp.deduplication.manager.phone_number",
            "spp.deduplication.manager.id_dedup",
        ]:
            self.assertIn(expected, model_names)

    # ------------------------------------------------------------------
    # DefaultDeduplication capabilities
    # ------------------------------------------------------------------

    def test_default_dedup_capability_flags(self):
        """DefaultDeduplication must support both individual and group deduplication."""
        self.assertTrue(self.dedup_manager_default._capability_individual)
        self.assertTrue(self.dedup_manager_default._capability_group)

    # ------------------------------------------------------------------
    # deduplicate_beneficiaries — no beneficiaries
    # ------------------------------------------------------------------

    def test_deduplicate_beneficiaries_no_members_returns_zero(self):
        """deduplicate_beneficiaries with no enrolled members returns 0 duplicates."""
        count = self.dedup_manager_default.deduplicate_beneficiaries(["enrolled"])
        self.assertEqual(count, 0, "No members means no duplicates")

    # ------------------------------------------------------------------
    # deduplicate_beneficiaries — with duplicate individuals
    # ------------------------------------------------------------------

    def test_deduplicate_beneficiaries_marks_duplicated_groups(self):
        """Groups sharing the same individual member must be marked as duplicated."""
        # Create two groups sharing one individual
        individual = self.env["res.partner"].create(
            {
                "name": "Shared Individual [DEDUP TEST]",
                "is_registrant": True,
                "is_group": False,
            }
        )
        group1 = self.env["res.partner"].create(
            {
                "name": "Group 1 [DEDUP TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        group2 = self.env["res.partner"].create(
            {
                "name": "Group 2 [DEDUP TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        # Both groups contain the same individual
        self.env["spp.group.membership"].create(
            [
                {"individual": individual.id, "group": group1.id},
                {"individual": individual.id, "group": group2.id},
            ]
        )
        # Enroll both groups in the program
        self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": group1.id,
                    "program_id": self.program.id,
                    "state": "enrolled",
                },
                {
                    "partner_id": group2.id,
                    "program_id": self.program.id,
                    "state": "enrolled",
                },
            ]
        )
        count = self.dedup_manager_default.deduplicate_beneficiaries(["enrolled"])
        self.assertGreater(count, 0, "Duplicate groups should be detected")

    # ------------------------------------------------------------------
    # _record_duplicate
    # ------------------------------------------------------------------

    def test_record_duplicate_creates_duplicate_record(self):
        """_record_duplicate must create an spp.program.membership.duplicate entry."""
        group_a = self.env["res.partner"].create(
            {
                "name": "Record Dup Group A [DEDUP TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": group_a.id,
                "program_id": self.program.id,
                "state": "enrolled",
            }
        )
        before = self.env["spp.program.membership.duplicate"].search_count(
            [("deduplication_manager_id", "=", self.dedup_manager_default.id)]
        )
        self.dedup_manager_default._record_duplicate(
            self.dedup_manager_default,
            [membership.id],
            "Test Reason",
        )
        after = self.env["spp.program.membership.duplicate"].search_count(
            [("deduplication_manager_id", "=", self.dedup_manager_default.id)]
        )
        self.assertGreater(after, before, "A duplicate record should be created")

    def test_record_duplicate_not_duplicated_twice(self):
        """_record_duplicate must not create a second entry for the same beneficiary/reason."""
        group_b = self.env["res.partner"].create(
            {
                "name": "Record Dup Group B [DEDUP TEST]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": group_b.id,
                "program_id": self.program.id,
                "state": "enrolled",
            }
        )
        self.dedup_manager_default._record_duplicate(self.dedup_manager_default, [membership.id], "Idempotent Reason")
        self.dedup_manager_default._record_duplicate(self.dedup_manager_default, [membership.id], "Idempotent Reason")
        count = self.env["spp.program.membership.duplicate"].search_count(
            [
                ("deduplication_manager_id", "=", self.dedup_manager_default.id),
                ("reason", "=", "Idempotent Reason"),
                ("beneficiary_ids", "in", [membership.id]),
            ]
        )
        self.assertEqual(count, 1, "Duplicate record should only be created once")
