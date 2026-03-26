# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from datetime import date
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestCycleAutoApproveFundCheck(TransactionCase):
    """Test cycle approval with auto-approve entitlements and fund checking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Create test company
        cls.company = cls.env.company

        # Ensure the current user is in the base.group_user group
        # (required for approval workflow checks)
        user_group = cls.env.ref("base.group_user")
        if cls.env.user not in user_group.user_ids:
            user_group.write({"user_ids": [(4, cls.env.user.id)]})

        # Create test currency
        cls.currency = cls.env.ref("base.USD")

        # Create test journal for program
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Bank Journal [FUND CHECK]",
                "code": "TFCK",
                "type": "bank",
                "currency_id": cls.currency.id,
                "company_id": cls.company.id,
            }
        )

        # Create approval definition for entitlements
        entitlement_model = cls.env["ir.model"].search([("model", "=", "spp.entitlement")], limit=1)
        cls.entitlement_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Entitlement Approval [FUND CHECK]",
                "model_id": entitlement_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # Create approval definition for cycles
        cycle_model = cls.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
        cls.cycle_approval_definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Cycle Approval [FUND CHECK]",
                "model_id": cycle_model.id,
                "approval_type": "group",
                "approval_group_id": cls.env.ref("base.group_user").id,
            }
        )

        # Create test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program - Auto Approve Fund Check",
                "journal_id": cls.journal.id,
            }
        )

        # Create entitlement manager with auto-approve enabled and approval definition
        # Two-record pattern: default manager + wrapper
        cls.entitlement_manager_default = cls.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Test Cash Entitlement Manager [FUND CHECK]",
                "program_id": cls.program.id,
                "amount_per_cycle": 100.0,
                "amount_per_individual_in_group": 0.0,
                "approval_definition_id": cls.entitlement_approval_definition.id,
            }
        )
        cls.entitlement_manager = cls.env["spp.program.entitlement.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"spp.program.entitlement.manager.default,{cls.entitlement_manager_default.id}",
            }
        )

        # Create cycle manager with auto-approve enabled
        # Two-record pattern: default manager + wrapper
        cls.cycle_manager_default = cls.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager [FUND CHECK]",
                "program_id": cls.program.id,
                "auto_approve_entitlements": True,
                "approval_definition_id": cls.cycle_approval_definition.id,
            }
        )
        cls.cycle_manager = cls.env["spp.cycle.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"spp.cycle.manager.default,{cls.cycle_manager_default.id}",
            }
        )

        # Link managers to program
        cls.program.write(
            {
                "cycle_manager_ids": [(4, cls.cycle_manager.id)],
                "entitlement_manager_ids": [(4, cls.entitlement_manager.id)],
            }
        )

        # Create test beneficiaries
        cls.beneficiary1 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 1 [FUND CHECK]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.beneficiary2 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 2 [FUND CHECK]",
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

    def _create_program_fund(self, amount, program=None):
        """Helper method to create program funds."""
        if program is None:
            program = self.program
        return self.env["spp.program.fund"].create(
            {
                "program_id": program.id,
                "amount": amount,
                "company_id": self.company.id,
                "state": "posted",
            }
        )

    def _make_cycle(self, name, program=None, state="draft", auto_approve_entitlements=True):
        """Helper: create a fresh cycle attached to the given program.

        Sets auto_approve_entitlements=True by default since most tests in this
        class test the auto-approve with fund-checking behavior. Pass False
        for tests that verify non-auto-approve behavior.
        """
        if program is None:
            program = self.program
        today = fields.Date.today()
        return self.env["spp.cycle"].create(
            {
                "name": name,
                "program_id": program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": state,
                "auto_approve_entitlements": auto_approve_entitlements,
            }
        )

    def _add_enrolled_members(self, cycle):
        """Helper: add the class-level beneficiaries as enrolled cycle members."""
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

    def _submit_and_approve_cycle(self, cycle):
        """Helper: submit cycle for approval then approve it through the full workflow.

        This follows the proper approval flow:
        1. action_submit_for_approval() creates an spp.approval.review in 'pending' status
           and transitions the cycle to 'to_approve' (approval_state = 'pending').
        2. action_approve() checks _check_can_approve(), which verifies the pending review
           exists and the user is authorized.

        The test environment runs as admin (uid=1), which bypasses the group check in
        on_state_change() (cycle_manager_base.py line 276).
        """
        cycle.action_submit_for_approval()
        cycle.action_approve()

    @patch("odoo.fields.Date.today")
    def test_01_cycle_approval_with_sufficient_funds(self, mock_today):
        """Test that cycle approval succeeds when funds are sufficient."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle("Test Cycle - Sufficient Funds [01]")
        self._add_enrolled_members(cycle)

        # Create entitlements (2 beneficiaries * 100 = 200 total)
        cycle.prepare_entitlement()

        # Add sufficient funds (250 > 200 needed)
        self._create_program_fund(250.0)

        # Submit for approval, then approve through the proper flow
        self._submit_and_approve_cycle(cycle)

        # Cycle should be approved
        self.assertEqual(
            cycle.state,
            "approved",
            "Cycle should be approved when funds are sufficient",
        )

        # Entitlements should be approved
        entitlements = cycle.get_entitlements(["approved"], entitlement_model="spp.entitlement")
        self.assertEqual(len(entitlements), 2, "Both entitlements should be approved")

    @patch("odoo.fields.Date.today")
    def test_02_cycle_approval_with_insufficient_funds(self, mock_today):
        """Test that cycle approval fails when funds are insufficient."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle("Test Cycle - Insufficient Funds [02]")
        self._add_enrolled_members(cycle)

        # Create entitlements (2 beneficiaries * 100 = 200 total)
        cycle.prepare_entitlement()

        # Add insufficient funds (150 < 200 needed)
        self._create_program_fund(150.0)

        # Submit cycle for approval (transitions to to_approve, creates approval review)
        cycle.action_submit_for_approval()
        self.assertEqual(cycle.state, "to_approve")

        # Attempt approval - the fund check inside approve_cycle should fail
        result = cycle.action_approve()

        # Should return an error notification (fund check failed before cycle was approved)
        self.assertIsNotNone(result, "Should return a client action notification")
        self.assertEqual(result["type"], "ir.actions.client", "Should return client action")
        self.assertEqual(result["tag"], "display_notification", "Should return notification")
        self.assertEqual(result["params"]["type"], "danger", "Should return danger notification")
        self.assertIn(
            "Insufficient funds",
            result["params"]["message"],
            "Should mention insufficient funds",
        )

        # Cycle should NOT be approved - remains in to_approve
        self.assertEqual(cycle.state, "to_approve", "Cycle should remain in 'to_approve' state")

        # Entitlements should NOT be approved
        entitlements = cycle.get_entitlements(["approved"], entitlement_model="spp.entitlement")
        self.assertEqual(len(entitlements), 0, "No entitlements should be approved")

    @patch("odoo.fields.Date.today")
    def test_03_cycle_approval_with_exact_funds(self, mock_today):
        """Test that cycle approval succeeds when funds exactly match needed amount."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        cycle = self._make_cycle("Test Cycle - Exact Funds [03]")
        self._add_enrolled_members(cycle)

        # Create entitlements (2 beneficiaries * 100 = 200 total)
        cycle.prepare_entitlement()

        # Add exact funds (200 = 200 needed)
        self._create_program_fund(200.0)

        # Submit for approval, then approve through the proper flow
        self._submit_and_approve_cycle(cycle)

        # Cycle should be approved
        self.assertEqual(
            cycle.state,
            "approved",
            "Cycle should be approved when funds are exact",
        )

        # Entitlements should be approved
        entitlements = cycle.get_entitlements(["approved"], entitlement_model="spp.entitlement")
        self.assertEqual(len(entitlements), 2, "Both entitlements should be approved")

    @patch("odoo.fields.Date.today")
    def test_04_cycle_approval_without_auto_approve(self, mock_today):
        """Test that cycle approval works normally when auto-approve is disabled."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create a separate program with auto-approve disabled
        program_no_auto = self.env["spp.program"].create(
            {
                "name": "Test Program - No Auto Approve [04]",
                "journal_id": self.journal.id,
            }
        )

        # Entitlement manager also needs an approval_definition_id
        ent_manager_no_auto_default = self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Entitlement Manager - No Auto Approve [04]",
                "program_id": program_no_auto.id,
                "amount_per_cycle": 100.0,
                "amount_per_individual_in_group": 0.0,
                "approval_definition_id": self.entitlement_approval_definition.id,
            }
        )
        ent_manager_no_auto = self.env["spp.program.entitlement.manager"].create(
            {
                "program_id": program_no_auto.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.default,{ent_manager_no_auto_default.id}"),
            }
        )

        cycle_manager_no_auto_default = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager - No Auto Approve [04]",
                "program_id": program_no_auto.id,
                "auto_approve_entitlements": False,
                "approval_definition_id": self.cycle_approval_definition.id,
            }
        )
        cycle_manager_no_auto = self.env["spp.cycle.manager"].create(
            {
                "program_id": program_no_auto.id,
                "manager_ref_id": (f"spp.cycle.manager.default,{cycle_manager_no_auto_default.id}"),
            }
        )
        program_no_auto.write(
            {
                "cycle_manager_ids": [(4, cycle_manager_no_auto.id)],
                "entitlement_manager_ids": [(4, ent_manager_no_auto.id)],
            }
        )

        # Enroll beneficiaries in this program
        self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": self.beneficiary1.id,
                    "program_id": program_no_auto.id,
                    "state": "enrolled",
                },
                {
                    "partner_id": self.beneficiary2.id,
                    "program_id": program_no_auto.id,
                    "state": "enrolled",
                },
            ]
        )

        cycle = self._make_cycle(
            "Test Cycle - No Auto Approve [04]",
            program=program_no_auto,
            auto_approve_entitlements=False,
        )
        self._add_enrolled_members(cycle)
        cycle.prepare_entitlement()

        # No funds needed because auto-approve is disabled (no fund check occurs)
        # Submit for approval then approve
        self._submit_and_approve_cycle(cycle)

        # Cycle should be approved even without funds
        self.assertEqual(
            cycle.state,
            "approved",
            "Cycle should be approved when auto-approve is disabled (no fund check)",
        )

    @patch("odoo.fields.Date.today")
    def test_05_cycle_approval_with_no_entitlements_shows_warning(self, mock_today):
        """Test that cycle approval with auto-approve shows warning when no entitlements exist."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create a new program with no beneficiaries enrolled
        empty_program = self.env["spp.program"].create(
            {
                "name": "Test Program - Empty [05]",
                "journal_id": self.journal.id,
            }
        )
        empty_ent_mgr_default = self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Empty Entitlement Manager [05]",
                "program_id": empty_program.id,
                "amount_per_cycle": 100.0,
                "amount_per_individual_in_group": 0.0,
                "approval_definition_id": self.entitlement_approval_definition.id,
            }
        )
        empty_ent_mgr = self.env["spp.program.entitlement.manager"].create(
            {
                "program_id": empty_program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.default,{empty_ent_mgr_default.id}"),
            }
        )
        empty_cm_default = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Empty Cycle Manager [05]",
                "program_id": empty_program.id,
                "auto_approve_entitlements": True,
                "approval_definition_id": self.cycle_approval_definition.id,
            }
        )
        empty_cm = self.env["spp.cycle.manager"].create(
            {
                "program_id": empty_program.id,
                "manager_ref_id": f"spp.cycle.manager.default,{empty_cm_default.id}",
            }
        )
        empty_program.write(
            {
                "cycle_manager_ids": [(4, empty_cm.id)],
                "entitlement_manager_ids": [(4, empty_ent_mgr.id)],
            }
        )

        # Create a beneficiary enrolled in empty_program and add a single entitlement
        # directly so the cycle can be submitted for approval (requires entitlements).
        # The auto-approve should then encounter "no entitlements" when it looks for
        # draft/pending_validation ones after they've already been approved, but here we
        # want to test the approve path that returns a warning.
        # Instead: enroll a beneficiary, prepare entitlement, set it to approved manually
        # so that when approve_cycle runs with auto_approve=True it finds no pending ones.
        solo_beneficiary = self.env["res.partner"].create(
            {
                "name": "Solo Beneficiary [05]",
                "is_registrant": True,
                "is_group": True,
            }
        )
        self.env["spp.program.membership"].create(
            {
                "partner_id": solo_beneficiary.id,
                "program_id": empty_program.id,
                "state": "enrolled",
            }
        )

        today = fields.Date.today()
        test_cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle - Empty [05]",
                "program_id": empty_program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "draft",
                "auto_approve_entitlements": True,
            }
        )
        self.env["spp.cycle.membership"].create(
            {
                "cycle_id": test_cycle.id,
                "partner_id": solo_beneficiary.id,
                "state": "enrolled",
            }
        )

        # Prepare entitlements so the cycle can be submitted
        test_cycle.prepare_entitlement()

        # Submit for approval (creates approval review, transitions to to_approve)
        test_cycle.action_submit_for_approval()
        self.assertEqual(test_cycle.state, "to_approve")

        # Manually mark the entitlement as already approved so approve_cycle's
        # auto-approve path finds no draft/pending_validation entitlements.
        # This triggers the "no entitlements to process" warning path.
        entitlement = test_cycle.get_entitlements(["pending_validation"], entitlement_model="spp.entitlement")
        # Update the approval review for the entitlement to approved and change its state
        entitlement.approval_review_ids.filtered(lambda r: r.status == "pending").write({"status": "approved"})
        entitlement.write({"state": "approved"})

        # Approve the cycle - since all entitlements are already approved,
        # auto-approve finds no pending entitlements and returns a warning
        result = test_cycle.action_approve()

        # Should return a warning notification about no entitlements
        self.assertIsNotNone(result, "Should return a client action notification")
        self.assertEqual(result["type"], "ir.actions.client", "Should return client action")
        self.assertEqual(result["tag"], "display_notification", "Should return notification")
        self.assertEqual(result["params"]["type"], "warning", "Should return warning notification")
        self.assertIn(
            "no entitlements",
            result["params"]["message"],
            "Should mention no entitlements",
        )

        # Cycle should be approved even with no pending entitlements
        self.assertEqual(
            test_cycle.state,
            "approved",
            "Cycle should be approved even with no pending entitlements",
        )

    @patch("odoo.fields.Date.today")
    def test_06_fund_check_considers_already_approved_entitlements(self, mock_today):
        """Test that fund balance calculation considers already approved entitlements from other cycles."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create a separate program so funds don't bleed from test_01/test_03
        fund_program = self.env["spp.program"].create(
            {
                "name": "Test Program - Multi-Cycle Fund Check [06]",
                "journal_id": self.journal.id,
            }
        )
        ent_mgr_default = self.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Entitlement Manager [06]",
                "program_id": fund_program.id,
                "amount_per_cycle": 100.0,
                "amount_per_individual_in_group": 0.0,
                "approval_definition_id": self.entitlement_approval_definition.id,
            }
        )
        ent_mgr = self.env["spp.program.entitlement.manager"].create(
            {
                "program_id": fund_program.id,
                "manager_ref_id": (f"spp.program.entitlement.manager.default,{ent_mgr_default.id}"),
            }
        )
        cycle_mgr_default = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Cycle Manager [06]",
                "program_id": fund_program.id,
                "auto_approve_entitlements": True,
                "approval_definition_id": self.cycle_approval_definition.id,
            }
        )
        cycle_mgr = self.env["spp.cycle.manager"].create(
            {
                "program_id": fund_program.id,
                "manager_ref_id": f"spp.cycle.manager.default,{cycle_mgr_default.id}",
            }
        )
        fund_program.write(
            {
                "cycle_manager_ids": [(4, cycle_mgr.id)],
                "entitlement_manager_ids": [(4, ent_mgr.id)],
            }
        )

        # Enroll two beneficiaries (each gets 100, so 200 per cycle)
        self.env["spp.program.membership"].create(
            [
                {
                    "partner_id": self.beneficiary1.id,
                    "program_id": fund_program.id,
                    "state": "enrolled",
                },
                {
                    "partner_id": self.beneficiary2.id,
                    "program_id": fund_program.id,
                    "state": "enrolled",
                },
            ]
        )

        # Add total funds of 400 (enough for exactly two cycles of 200 each)
        self._create_program_fund(400.0, program=fund_program)

        today = fields.Date.today()

        # --- First cycle (200 used, 200 remaining) ---
        first_cycle = self.env["spp.cycle"].create(
            {
                "name": "First Cycle [06]",
                "program_id": fund_program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "auto_approve_entitlements": True,
            }
        )
        self.env["spp.cycle.membership"].create(
            [
                {"cycle_id": first_cycle.id, "partner_id": self.beneficiary1.id, "state": "enrolled"},
                {"cycle_id": first_cycle.id, "partner_id": self.beneficiary2.id, "state": "enrolled"},
            ]
        )
        first_cycle.prepare_entitlement()
        self._submit_and_approve_cycle(first_cycle)
        self.assertEqual(first_cycle.state, "approved", "First cycle should be approved")

        # --- Second cycle (uses remaining 200) ---
        second_cycle = self.env["spp.cycle"].create(
            {
                "name": "Second Cycle [06]",
                "program_id": fund_program.id,
                "start_date": fields.Date.add(today, days=31),
                "end_date": fields.Date.add(today, days=60),
                "auto_approve_entitlements": True,
            }
        )
        self.env["spp.cycle.membership"].create(
            [
                {"cycle_id": second_cycle.id, "partner_id": self.beneficiary1.id, "state": "enrolled"},
                {"cycle_id": second_cycle.id, "partner_id": self.beneficiary2.id, "state": "enrolled"},
            ]
        )
        second_cycle.prepare_entitlement()
        self._submit_and_approve_cycle(second_cycle)
        self.assertEqual(
            second_cycle.state,
            "approved",
            "Second cycle should be approved with remaining funds",
        )

        # --- Third cycle (no funds left, should fail) ---
        third_cycle = self.env["spp.cycle"].create(
            {
                "name": "Third Cycle [06]",
                "program_id": fund_program.id,
                "start_date": fields.Date.add(today, days=61),
                "end_date": fields.Date.add(today, days=90),
                "auto_approve_entitlements": True,
            }
        )
        self.env["spp.cycle.membership"].create(
            [
                {"cycle_id": third_cycle.id, "partner_id": self.beneficiary1.id, "state": "enrolled"},
                {"cycle_id": third_cycle.id, "partner_id": self.beneficiary2.id, "state": "enrolled"},
            ]
        )
        third_cycle.prepare_entitlement()

        # Submit for approval first so the cycle is in to_approve state
        third_cycle.action_submit_for_approval()
        self.assertEqual(third_cycle.state, "to_approve")

        # Attempt approval - should fail with insufficient funds
        result = third_cycle.action_approve()

        # Should return an error notification
        self.assertIsNotNone(result, "Should return a client action notification")
        self.assertEqual(result["params"]["type"], "danger", "Should return danger notification")
        self.assertEqual(third_cycle.state, "to_approve", "Third cycle should not be approved")
