from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApprovalFreeze(TransactionCase):
    """Test cases for the approval freeze model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test company
        cls.test_company = cls.env["res.company"].create(
            {
                "name": "Test Freeze Company",
            }
        )

        cls.other_company = cls.env["res.company"].create(
            {
                "name": "Other Freeze Company",
            }
        )

    # === Basic Creation Tests ===

    def test_freeze_creation_basic(self):
        """Test creating a basic freeze period."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Test Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=7),
            }
        )

        self.assertEqual(freeze.name, "Test Freeze")
        self.assertEqual(freeze.reason, "audit")
        self.assertTrue(freeze.date_start)
        self.assertTrue(freeze.date_end)

    def test_freeze_creation_all_reasons(self):
        """Test creating freeze periods with all reason types."""
        reasons = ["election", "audit", "regulatory", "maintenance", "other"]

        for reason in reasons:
            freeze = self.env["spp.approval.freeze"].create(
                {
                    "name": f"Freeze for {reason}",
                    "reason": reason,
                    "date_start": fields.Datetime.now(),
                    "date_end": fields.Datetime.now() + timedelta(days=1),
                }
            )
            self.assertEqual(freeze.reason, reason)

    def test_freeze_creation_with_company(self):
        """Test creating freeze with specific company."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Company Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=1),
                "company_id": self.test_company.id,
            }
        )

        self.assertEqual(freeze.company_id, self.test_company)

    def test_freeze_creation_with_models(self):
        """Test creating freeze affecting specific models."""
        partner_model = self.env.ref("base.model_res_partner")
        user_model = self.env.ref("base.model_res_users")

        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Model Specific Freeze",
                "reason": "maintenance",
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=1),
                "model_ids": [Command.set([partner_model.id, user_model.id])],
            }
        )

        self.assertEqual(len(freeze.model_ids), 2)
        self.assertIn(partner_model, freeze.model_ids)
        self.assertIn(user_model, freeze.model_ids)

    # === State Computation Tests ===

    def test_state_draft_before_start(self):
        """Test freeze state is draft before start date."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Future Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() + timedelta(days=1),
                "date_end": fields.Datetime.now() + timedelta(days=7),
            }
        )

        # Force recompute
        freeze._compute_state()

        self.assertEqual(freeze.state, "draft")

    def test_state_active_during_period(self):
        """Test freeze state is active during freeze period."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Active Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
            }
        )

        # Force recompute
        freeze._compute_state()

        self.assertEqual(freeze.state, "active")

    def test_state_ended_after_period(self):
        """Test freeze state is ended after end date."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Past Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(days=7),
                "date_end": fields.Datetime.now() - timedelta(days=1),
            }
        )

        # Force recompute
        freeze._compute_state()

        self.assertEqual(freeze.state, "ended")

    def test_state_cancelled_persists(self):
        """Test cancelled state persists even if dates change."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Cancelled Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=1),
            }
        )

        freeze.action_cancel()
        self.assertEqual(freeze.state, "cancelled")

        # Force recompute
        freeze._compute_state()

        # Should still be cancelled
        self.assertEqual(freeze.state, "cancelled")

    # === Action Tests ===

    def test_action_activate(self):
        """Test manually activating a freeze period."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Future Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() + timedelta(days=1),
                "date_end": fields.Datetime.now() + timedelta(days=7),
            }
        )

        before_activate = fields.Datetime.now()
        freeze.action_activate()
        after_activate = fields.Datetime.now()

        # date_start should be updated to now
        self.assertTrue(before_activate <= freeze.date_start <= after_activate)

        # State should be active
        freeze._compute_state()
        self.assertEqual(freeze.state, "active")

    def test_action_end(self):
        """Test manually ending a freeze period."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Active Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(days=1),
            }
        )

        before_end = fields.Datetime.now()
        freeze.action_end()
        after_end = fields.Datetime.now()

        # date_end should be updated to now
        self.assertTrue(before_end <= freeze.date_end <= after_end)

        # State should be ended
        freeze._compute_state()
        self.assertEqual(freeze.state, "ended")

    def test_action_cancel(self):
        """Test cancelling a freeze period."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "To Cancel",
                "reason": "audit",
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=1),
            }
        )

        freeze.action_cancel()

        self.assertEqual(freeze.state, "cancelled")

    def test_action_activate_cancelled_raises_error(self):
        """Test that cancelled freeze cannot be activated."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Cancelled",
                "reason": "audit",
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=1),
            }
        )

        freeze.action_cancel()

        with self.assertRaises(UserError) as cm:
            freeze.action_activate()

        self.assertIn("cancelled", str(cm.exception))

    # === is_frozen Tests ===

    def test_is_frozen_during_active_freeze(self):
        """Test is_frozen returns True during active freeze."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Active Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
            }
        )

        result = self.env["spp.approval.freeze"].is_frozen()

        self.assertTrue(result["frozen"])
        self.assertEqual(result["reason"], "Active Freeze")
        self.assertEqual(result["freeze_id"], freeze.id)
        self.assertTrue(result["date_end"])

    def test_is_frozen_no_freeze(self):
        """Test is_frozen returns False when no freeze active."""
        result = self.env["spp.approval.freeze"].is_frozen()

        self.assertFalse(result["frozen"])

    def test_is_frozen_before_freeze(self):
        """Test is_frozen returns False before freeze starts."""
        self.env["spp.approval.freeze"].create(
            {
                "name": "Future Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() + timedelta(days=1),
                "date_end": fields.Datetime.now() + timedelta(days=7),
            }
        )

        result = self.env["spp.approval.freeze"].is_frozen()

        self.assertFalse(result["frozen"])

    def test_is_frozen_after_freeze(self):
        """Test is_frozen returns False after freeze ends."""
        self.env["spp.approval.freeze"].create(
            {
                "name": "Past Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(days=7),
                "date_end": fields.Datetime.now() - timedelta(days=1),
            }
        )

        result = self.env["spp.approval.freeze"].is_frozen()

        self.assertFalse(result["frozen"])

    def test_is_frozen_cancelled_freeze(self):
        """Test is_frozen returns False for cancelled freeze."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Cancelled Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
            }
        )

        freeze.action_cancel()

        result = self.env["spp.approval.freeze"].is_frozen()

        self.assertFalse(result["frozen"])

    # === Model Filtering Tests ===

    def test_is_frozen_model_specific_matching(self):
        """Test freeze affects only specified models."""
        partner_model = self.env.ref("base.model_res_partner")

        self.env["spp.approval.freeze"].create(
            {
                "name": "Partner Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
                "model_ids": [Command.set([partner_model.id])],
            }
        )

        # Should be frozen for res.partner
        result = self.env["spp.approval.freeze"].is_frozen(model_name="res.partner")
        self.assertTrue(result["frozen"])

        # Should not be frozen for res.users
        result = self.env["spp.approval.freeze"].is_frozen(model_name="res.users")
        self.assertFalse(result["frozen"])

    def test_is_frozen_no_model_filter_affects_all(self):
        """Test freeze without model filter affects all models."""
        self.env["spp.approval.freeze"].create(
            {
                "name": "Global Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
                # No model_ids specified
            }
        )

        # Should be frozen for all models
        result1 = self.env["spp.approval.freeze"].is_frozen(model_name="res.partner")
        self.assertTrue(result1["frozen"])

        result2 = self.env["spp.approval.freeze"].is_frozen(model_name="res.users")
        self.assertTrue(result2["frozen"])

    # === Company Filtering Tests ===

    def test_is_frozen_company_specific_matching(self):
        """Test freeze affects only specified company."""
        self.env["spp.approval.freeze"].create(
            {
                "name": "Company Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
                "company_id": self.test_company.id,
            }
        )

        # Should be frozen for test_company
        result = self.env["spp.approval.freeze"].is_frozen(company_id=self.test_company.id)
        self.assertTrue(result["frozen"])

        # Should not be frozen for other_company
        result = self.env["spp.approval.freeze"].is_frozen(company_id=self.other_company.id)
        self.assertFalse(result["frozen"])

    def test_is_frozen_no_company_affects_all(self):
        """Test freeze without company affects all companies."""
        self.env["spp.approval.freeze"].create(
            {
                "name": "Global Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
                "company_id": False,
            }
        )

        # Should be frozen for all companies
        result1 = self.env["spp.approval.freeze"].is_frozen(company_id=self.test_company.id)
        self.assertTrue(result1["frozen"])

        result2 = self.env["spp.approval.freeze"].is_frozen(company_id=self.other_company.id)
        self.assertTrue(result2["frozen"])

    # === Combined Filtering Tests ===

    def test_is_frozen_model_and_company_filtering(self):
        """Test freeze with both model and company filters."""
        partner_model = self.env.ref("base.model_res_partner")

        self.env["spp.approval.freeze"].create(
            {
                "name": "Specific Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
                "company_id": self.test_company.id,
                "model_ids": [Command.set([partner_model.id])],
            }
        )

        # Should be frozen for matching model and company
        result = self.env["spp.approval.freeze"].is_frozen(model_name="res.partner", company_id=self.test_company.id)
        self.assertTrue(result["frozen"])

        # Should not be frozen for matching model but different company
        result = self.env["spp.approval.freeze"].is_frozen(model_name="res.partner", company_id=self.other_company.id)
        self.assertFalse(result["frozen"])

        # Should not be frozen for different model but matching company
        result = self.env["spp.approval.freeze"].is_frozen(model_name="res.users", company_id=self.test_company.id)
        self.assertFalse(result["frozen"])

    # === Multiple Freeze Tests ===

    def test_is_frozen_multiple_freezes_returns_first(self):
        """Test that is_frozen returns first matching freeze."""
        freeze1 = self.env["spp.approval.freeze"].create(
            {
                "name": "First Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=2),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
            }
        )

        freeze2 = self.env["spp.approval.freeze"].create(
            {
                "name": "Second Freeze",
                "reason": "election",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=2),
            }
        )

        result = self.env["spp.approval.freeze"].is_frozen()

        self.assertTrue(result["frozen"])
        # Should return first freeze found (implementation dependent)
        self.assertIn(result["freeze_id"], [freeze1.id, freeze2.id])

    # === Audit Fields Tests ===

    def test_created_by_field(self):
        """Test created_by_id is set automatically."""
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Test Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=1),
            }
        )

        self.assertTrue(freeze.created_by_id)
        self.assertEqual(freeze.created_by_id, self.env.user)

    # === Description Field Tests ===

    def test_freeze_with_description(self):
        """Test freeze with detailed description."""
        description = "This freeze is for annual audit period as required by law."
        freeze = self.env["spp.approval.freeze"].create(
            {
                "name": "Annual Audit Freeze",
                "reason": "audit",
                "description": description,
                "date_start": fields.Datetime.now(),
                "date_end": fields.Datetime.now() + timedelta(days=7),
            }
        )

        self.assertEqual(freeze.description, description)

    # === Edge Cases ===

    def test_freeze_instant_period(self):
        """Test freeze with same start and end time raises validation error."""
        now = fields.Datetime.now()
        # Creating a freeze with date_start == date_end should raise ValidationError
        with self.assertRaises(ValidationError):
            self.env["spp.approval.freeze"].create(
                {
                    "name": "Instant Freeze",
                    "reason": "maintenance",
                    "date_start": now,
                    "date_end": now,
                }
            )

    def test_multiple_overlapping_freezes(self):
        """Test handling of multiple overlapping freeze periods."""
        base_time = fields.Datetime.now()

        freeze1 = self.env["spp.approval.freeze"].create(
            {
                "name": "Freeze 1",
                "reason": "audit",
                "date_start": base_time - timedelta(hours=2),
                "date_end": base_time + timedelta(hours=2),
            }
        )

        freeze2 = self.env["spp.approval.freeze"].create(
            {
                "name": "Freeze 2",
                "reason": "election",
                "date_start": base_time - timedelta(hours=1),
                "date_end": base_time + timedelta(hours=3),
            }
        )

        # Both should be active
        freeze1._compute_state()
        freeze2._compute_state()
        self.assertEqual(freeze1.state, "active")
        self.assertEqual(freeze2.state, "active")

        # is_frozen should return frozen
        result = self.env["spp.approval.freeze"].is_frozen()
        self.assertTrue(result["frozen"])
