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

        # Create test currency
        cls.currency = cls.env.ref("base.USD")

        # Create test journal for program
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Bank Journal",
                "code": "TBNK",
                "type": "bank",
                "currency_id": cls.currency.id,
                "company_id": cls.company.id,
            }
        )

        # Create test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program - Auto Approve Fund Check",
                "journal_id": cls.journal.id,
            }
        )

        # Create cash entitlement manager with auto-approve enabled
        cls.entitlement_manager = cls.env["spp.program.entitlement.manager.default"].create(
            {
                "name": "Test Cash Entitlement Manager",
                "program_id": cls.program.id,
                "amount_per_cycle": 100.0,
                "amount_per_individual_in_group": 0.0,
            }
        )

        # Create cycle manager with auto-approve enabled
        cls.cycle_manager = cls.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager",
                "program_id": cls.program.id,
                "auto_approve_entitlements": True,
            }
        )

        # Link managers to program
        cls.program.write(
            {
                "cycle_manager_id": cls.cycle_manager.id,
                "entitlement_manager_ids": [(4, cls.entitlement_manager.id)],
            }
        )

        # Create test beneficiaries
        cls.beneficiary1 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 1",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.beneficiary2 = cls.env["res.partner"].create(
            {
                "name": "Test Beneficiary 2",
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

        # Create test cycle
        today = fields.Date.today()
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle - Fund Check",
                "program_id": cls.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "draft",
            }
        )

    def _create_program_fund(self, amount):
        """Helper method to create program funds."""
        return self.env["spp.program.fund"].create(
            {
                "program_id": self.program.id,
                "amount": amount,
                "company_id": self.company.id,
                "state": "posted",
            }
        )

    def _create_entitlements(self):
        """Helper method to create entitlements for the cycle."""
        self.cycle.prepare_entitlement()

    @patch("odoo.fields.Date.today")
    def test_01_cycle_approval_with_sufficient_funds(self, mock_today):
        """Test that cycle approval succeeds when funds are sufficient."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create entitlements (2 beneficiaries * 100 = 200 total)
        self._create_entitlements()

        # Add sufficient funds (250 > 200 needed)
        self._create_program_fund(250.0)

        # Set cycle to 'to_approve' state
        self.cycle.write({"state": "to_approve"})

        # Approve cycle with auto-approve enabled
        self.cycle.action_approve()

        # Cycle should be approved
        self.assertEqual(
            self.cycle.state,
            "approved",
            "Cycle should be approved when funds are sufficient",
        )

        # Entitlements should be approved
        entitlements = self.cycle.get_entitlements(["approved"], entitlement_model="spp.entitlement")
        self.assertEqual(len(entitlements), 2, "Both entitlements should be approved")

    @patch("odoo.fields.Date.today")
    def test_02_cycle_approval_with_insufficient_funds(self, mock_today):
        """Test that cycle approval fails when funds are insufficient."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create new cycle for this test
        today = fields.Date.today()
        test_cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle - Insufficient Funds",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "draft",
            }
        )

        # Create entitlements (2 beneficiaries * 100 = 200 total)
        test_cycle.prepare_entitlement()

        # Add insufficient funds (150 < 200 needed)
        self._create_program_fund(150.0)

        # Set cycle to 'to_approve' state
        test_cycle.write({"state": "to_approve"})

        # Approve cycle with auto-approve enabled - should fail
        result = test_cycle.action_approve()

        # Should return error notification
        self.assertEqual(result["type"], "ir.actions.client", "Should return client action")
        self.assertEqual(result["tag"], "display_notification", "Should return notification")
        self.assertEqual(result["params"]["type"], "danger", "Should return danger notification")
        self.assertIn(
            "Insufficient funds",
            result["params"]["message"],
            "Should mention insufficient funds",
        )

        # Cycle should NOT be approved
        self.assertEqual(test_cycle.state, "to_approve", "Cycle should remain in 'to_approve' state")

        # Entitlements should NOT be approved
        entitlements = test_cycle.get_entitlements(["approved"], entitlement_model="spp.entitlement")
        self.assertEqual(len(entitlements), 0, "No entitlements should be approved")

    @patch("odoo.fields.Date.today")
    def test_03_cycle_approval_with_exact_funds(self, mock_today):
        """Test that cycle approval succeeds when funds exactly match needed amount."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create new cycle for this test
        today = fields.Date.today()
        test_cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle - Exact Funds",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "draft",
            }
        )

        # Create entitlements (2 beneficiaries * 100 = 200 total)
        test_cycle.prepare_entitlement()

        # Add exact funds (200 = 200 needed)
        self._create_program_fund(200.0)

        # Set cycle to 'to_approve' state
        test_cycle.write({"state": "to_approve"})

        # Approve cycle with auto-approve enabled
        test_cycle.action_approve()

        # Cycle should be approved
        self.assertEqual(
            test_cycle.state,
            "approved",
            "Cycle should be approved when funds are exact",
        )

        # Entitlements should be approved
        entitlements = test_cycle.get_entitlements(["approved"], entitlement_model="spp.entitlement")
        self.assertEqual(len(entitlements), 2, "Both entitlements should be approved")

    @patch("odoo.fields.Date.today")
    def test_04_cycle_approval_without_auto_approve(self, mock_today):
        """Test that cycle approval works normally when auto-approve is disabled."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create cycle manager without auto-approve
        cycle_manager_no_auto = self.env["spp.cycle.manager.default"].create(
            {
                "name": "Test Cycle Manager - No Auto Approve",
                "program_id": self.program.id,
                "auto_approve_entitlements": False,
            }
        )

        # Create new program with this manager
        program_no_auto = self.env["spp.program"].create(
            {
                "name": "Test Program - No Auto Approve",
                "journal_id": self.journal.id,
                "cycle_manager_id": cycle_manager_no_auto.id,
            }
        )

        # Create cycle
        today = fields.Date.today()
        test_cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle - No Auto Approve",
                "program_id": program_no_auto.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "draft",
            }
        )

        # Set cycle to 'to_approve' state
        test_cycle.write({"state": "to_approve"})

        # Approve cycle without auto-approve (no funds needed)
        test_cycle.action_approve()

        # Cycle should be approved even without funds
        self.assertEqual(
            test_cycle.state,
            "approved",
            "Cycle should be approved when auto-approve is disabled (no fund check)",
        )

    @patch("odoo.fields.Date.today")
    def test_05_cycle_approval_with_no_entitlements(self, mock_today):
        """Test that cycle approval with auto-approve shows warning when no entitlements exist."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create new cycle with no beneficiaries
        empty_program = self.env["spp.program"].create(
            {
                "name": "Test Program - Empty",
                "journal_id": self.journal.id,
                "cycle_manager_id": self.cycle_manager.id,
                "entitlement_manager_ids": [(4, self.entitlement_manager.id)],
            }
        )

        today = fields.Date.today()
        test_cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle - Empty",
                "program_id": empty_program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "to_approve",
            }
        )

        # Approve cycle with auto-approve enabled but no entitlements
        result = test_cycle.action_approve()

        # Should return warning notification
        self.assertEqual(result["type"], "ir.actions.client", "Should return client action")
        self.assertEqual(result["tag"], "display_notification", "Should return notification")
        self.assertEqual(result["params"]["type"], "warning", "Should return warning notification")
        self.assertIn(
            "no entitlements",
            result["params"]["message"],
            "Should mention no entitlements",
        )

        # Cycle should be approved
        self.assertEqual(
            test_cycle.state,
            "approved",
            "Cycle should be approved even with no entitlements",
        )

    @patch("odoo.fields.Date.today")
    def test_06_fund_check_considers_already_approved_entitlements(self, mock_today):
        """Test that fund balance calculation considers already approved entitlements from other cycles."""
        mock_today.__name__ = "mock_today"
        mock_today.return_value = date(2024, 8, 1)

        # Create and approve first cycle
        today = fields.Date.today()
        first_cycle = self.env["spp.cycle"].create(
            {
                "name": "First Cycle",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": fields.Date.add(today, days=30),
                "state": "draft",
            }
        )

        # Create entitlements for first cycle (2 * 100 = 200)
        first_cycle.prepare_entitlement()

        # Add funds (400 total)
        self._create_program_fund(400.0)

        # Approve first cycle
        first_cycle.write({"state": "to_approve"})
        first_cycle.action_approve()

        # First cycle should be approved (200 used, 200 remaining)
        self.assertEqual(first_cycle.state, "approved", "First cycle should be approved")

        # Create second cycle
        second_cycle = self.env["spp.cycle"].create(
            {
                "name": "Second Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.add(today, days=31),
                "end_date": fields.Date.add(today, days=60),
                "state": "draft",
            }
        )

        # Create entitlements for second cycle (2 * 100 = 200)
        second_cycle.prepare_entitlement()

        # Approve second cycle - should succeed with remaining 200
        second_cycle.write({"state": "to_approve"})
        second_cycle.action_approve()

        # Second cycle should be approved
        self.assertEqual(
            second_cycle.state,
            "approved",
            "Second cycle should be approved with remaining funds",
        )

        # Create third cycle - should fail as no funds left
        third_cycle = self.env["spp.cycle"].create(
            {
                "name": "Third Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.add(today, days=61),
                "end_date": fields.Date.add(today, days=90),
                "state": "draft",
            }
        )

        # Create entitlements for third cycle (2 * 100 = 200)
        third_cycle.prepare_entitlement()

        # Try to approve third cycle - should fail (no funds left)
        third_cycle.write({"state": "to_approve"})
        result = third_cycle.action_approve()

        # Should return error
        self.assertEqual(result["params"]["type"], "danger", "Should return danger notification")
        self.assertEqual(third_cycle.state, "to_approve", "Third cycle should not be approved")
