from datetime import timedelta

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApprovalReview(TransactionCase):
    """Test cases for the approval review model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test users
        cls.user_submitter = cls.env["res.users"].create(
            {
                "name": "Test Submitter",
                "login": "test_submitter_review",
                "email": "submitter_review@test.com",
            }
        )

        cls.user_approver = cls.env["res.users"].create(
            {
                "name": "Test Approver",
                "login": "test_approver_review",
                "email": "approver_review@test.com",
                "group_ids": [Command.link(cls.env.ref("spp_approval.group_approval_approver").id)],
            }
        )

        cls.user_approver2 = cls.env["res.users"].create(
            {
                "name": "Test Approver 2",
                "login": "test_approver_review2",
                "email": "approver_review2@test.com",
                "group_ids": [Command.link(cls.env.ref("spp_approval.group_approval_approver").id)],
            }
        )

        # Create test group
        cls.test_group = cls.env["res.groups"].create(
            {
                "name": "Test Review Group",
                "user_ids": [Command.link(cls.user_approver.id)],
            }
        )

        # Create approval definitions
        cls.definition_user = cls.env["spp.approval.definition"].create(
            {
                "name": "User Review",
                "model_id": cls.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(cls.user_approver.id)],
            }
        )

        cls.definition_group = cls.env["spp.approval.definition"].create(
            {
                "name": "Group Review",
                "model_id": cls.env.ref("base.model_res_partner").id,
                "approval_type": "group",
                "approval_group_id": cls.test_group.id,
            }
        )

        cls.definition_with_sla = cls.env["spp.approval.definition"].create(
            {
                "name": "SLA Review",
                "model_id": cls.env.ref("base.model_res_partner").id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(cls.user_approver.id)],
                "sla_days": 3,
            }
        )

    # === Basic Creation Tests ===

    def test_review_creation(self):
        """Test creating an approval review."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        self.assertEqual(review.status, "pending")
        self.assertEqual(review.model, "res.partner")
        self.assertEqual(review.res_id, partner.id)
        self.assertEqual(review.definition_id, self.definition_user)
        self.assertEqual(review.requested_by_id, self.user_submitter)
        self.assertTrue(review.requested_date)

    def test_review_polymorphic_reference(self):
        """Test polymorphic reference correctly links to records."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
            }
        )

        # Test get_record method
        record = review.get_record()
        self.assertEqual(record, partner)
        self.assertEqual(record.name, "Test Partner")

    def test_review_get_record_nonexistent(self):
        """Test get_record with non-existent record."""
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": 999999,  # Non-existent ID
                "definition_id": self.definition_user.id,
            }
        )

        record = review.get_record()
        self.assertFalse(record.exists())

    # === Status Change Tests ===

    def test_action_approve(self):
        """Test approving a review."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        before_approve = fields.Datetime.now()
        review.with_user(self.user_approver).action_approve(comment="Looks good!")
        after_approve = fields.Datetime.now()

        self.assertEqual(review.status, "approved")
        self.assertEqual(review.reviewer_id, self.user_approver)
        self.assertEqual(review.comment, "Looks good!")
        self.assertTrue(before_approve <= review.review_date <= after_approve)

    def test_action_reject(self):
        """Test rejecting a review."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "requested_by_id": self.user_submitter.id,
            }
        )

        before_reject = fields.Datetime.now()
        review.with_user(self.user_approver).action_reject(comment="Missing documentation")
        after_reject = fields.Datetime.now()

        self.assertEqual(review.status, "rejected")
        self.assertEqual(review.reviewer_id, self.user_approver)
        self.assertEqual(review.comment, "Missing documentation")
        self.assertTrue(before_reject <= review.review_date <= after_reject)

    def test_action_approve_without_comment(self):
        """Test approving without a comment."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
            }
        )

        review.with_user(self.user_approver).action_approve()

        self.assertEqual(review.status, "approved")
        self.assertFalse(review.comment)

    # === SLA Tests ===

    def test_sla_deadline_computed(self):
        """Test SLA deadline is computed correctly."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        requested_date = fields.Datetime.now()
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_with_sla.id,
                "requested_date": requested_date,
            }
        )

        # SLA deadline should be 3 days from requested_date
        expected_deadline = requested_date + timedelta(days=3)
        self.assertTrue(review.sla_deadline)
        # Allow 1 second tolerance for computation time
        self.assertTrue(abs((review.sla_deadline - expected_deadline).total_seconds()) < 1)

    def test_sla_deadline_no_sla(self):
        """Test SLA deadline is not set when no SLA configured."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,  # No SLA
            }
        )

        self.assertFalse(review.sla_deadline)

    def test_sla_exceeded_pending_past_deadline(self):
        """Test SLA exceeded for pending review past deadline."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create review with old requested_date
        old_date = fields.Datetime.now() - timedelta(days=5)
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_with_sla.id,  # 3 days SLA
                "requested_date": old_date,
            }
        )

        # Force recompute
        review._compute_sla_exceeded()

        # SLA should be exceeded (5 days > 3 days)
        self.assertTrue(review.is_sla_exceeded)

    def test_sla_not_exceeded_pending_before_deadline(self):
        """Test SLA not exceeded for pending review before deadline."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create review with recent requested_date
        recent_date = fields.Datetime.now() - timedelta(days=1)
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_with_sla.id,  # 3 days SLA
                "requested_date": recent_date,
            }
        )

        # Force recompute
        review._compute_sla_exceeded()

        # SLA should not be exceeded (1 day < 3 days)
        self.assertFalse(review.is_sla_exceeded)

    def test_sla_exceeded_approved_after_deadline(self):
        """Test SLA exceeded when approved after deadline."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        old_date = fields.Datetime.now() - timedelta(days=5)
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_with_sla.id,  # 3 days SLA
                "requested_date": old_date,
            }
        )

        # Approve now (5 days after request)
        review.action_approve()

        # Force recompute
        review._compute_sla_exceeded()

        # SLA should be exceeded
        self.assertTrue(review.is_sla_exceeded)

    def test_sla_not_exceeded_approved_before_deadline(self):
        """Test SLA not exceeded when approved before deadline."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        recent_date = fields.Datetime.now() - timedelta(days=1)
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_with_sla.id,  # 3 days SLA
                "requested_date": recent_date,
            }
        )

        # Approve now (1 day after request)
        review.action_approve()

        # Force recompute
        review._compute_sla_exceeded()

        # SLA should not be exceeded
        self.assertFalse(review.is_sla_exceeded)

    # === Query Method Tests ===

    def test_get_pending_for_user_basic(self):
        """Test getting pending reviews for a user."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create pending review for user_approver
        review1 = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "pending",
            }
        )

        # Create approved review (should not be returned)
        review2 = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "approved",
            }
        )

        pending = self.env["spp.approval.review"].get_pending_for_user(user_id=self.user_approver.id)

        self.assertIn(review1, pending)
        self.assertNotIn(review2, pending)

    def test_get_pending_for_user_group_based(self):
        """Test getting pending reviews for group-based approval."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create review for group
        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_group.id,
                "status": "pending",
            }
        )

        # user_approver is in the group
        pending = self.env["spp.approval.review"].get_pending_for_user(user_id=self.user_approver.id)

        self.assertIn(review, pending)

        # user_approver2 is not in the group
        pending2 = self.env["spp.approval.review"].get_pending_for_user(user_id=self.user_approver2.id)

        self.assertNotIn(review, pending2)

    def test_get_pending_for_user_with_limit(self):
        """Test getting pending reviews with limit."""
        partners = self.env["res.partner"].create(
            [
                {"name": "Partner 1"},
                {"name": "Partner 2"},
                {"name": "Partner 3"},
            ]
        )

        # Create multiple pending reviews
        for partner in partners:
            self.env["spp.approval.review"].create(
                {
                    "model": "res.partner",
                    "res_id": partner.id,
                    "definition_id": self.definition_user.id,
                    "status": "pending",
                }
            )

        pending = self.env["spp.approval.review"].get_pending_for_user(user_id=self.user_approver.id, limit=2)

        self.assertEqual(len(pending), 2)

    def test_get_pending_for_user_ordering(self):
        """Test pending reviews are ordered by requested_date."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create reviews with different dates
        old_date = fields.Datetime.now() - timedelta(days=2)
        recent_date = fields.Datetime.now() - timedelta(days=1)

        self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "requested_date": old_date,
                "status": "pending",
            }
        )

        self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id + 1,
                "definition_id": self.definition_user.id,
                "requested_date": recent_date,
                "status": "pending",
            }
        )

        pending = self.env["spp.approval.review"].get_pending_for_user(user_id=self.user_approver.id)

        # Older review should come first
        self.assertTrue(pending[0].requested_date < pending[1].requested_date)

    def test_get_pending_for_user_current_user(self):
        """Test getting pending reviews for current user (default)."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "pending",
            }
        )

        # Get pending as user_approver (current user in context)
        pending = self.env["spp.approval.review"].with_user(self.user_approver).get_pending_for_user()

        self.assertIn(review, pending)

    # === Summary Tests ===

    def test_get_pending_summary_basic(self):
        """Test getting pending approval summary."""
        # Create reviews for different models
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.env["res.users"].create({"name": "Test User", "login": "testuser"})

        # Create partner reviews
        for i in range(3):
            self.env["spp.approval.review"].create(
                {
                    "model": "res.partner",
                    "res_id": partner.id + i,
                    "definition_id": self.definition_user.id,
                    "status": "pending",
                }
            )

        summary = self.env["spp.approval.review"].get_pending_summary(user_id=self.user_approver.id)

        # Should have one entry for res.partner
        partner_summary = next((s for s in summary if s["model"] == "res.partner"), None)
        self.assertIsNotNone(partner_summary)
        self.assertEqual(partner_summary["pending_count"], 3)
        self.assertTrue(partner_summary["oldest_request"])

    def test_get_pending_summary_multiple_models(self):
        """Test summary with multiple models."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create user-type definition for res.users
        user_model = self.env.ref("base.model_res_users")
        user_definition = self.env["spp.approval.definition"].create(
            {
                "name": "User Approval",
                "model_id": user_model.id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
            }
        )

        user = self.env["res.users"].create({"name": "Test User", "login": "testuser_summary"})

        # Create reviews for different models
        self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "pending",
            }
        )

        self.env["spp.approval.review"].create(
            {
                "model": "res.users",
                "res_id": user.id,
                "definition_id": user_definition.id,
                "status": "pending",
            }
        )

        summary = self.env["spp.approval.review"].get_pending_summary(user_id=self.user_approver.id)

        # Should have entries for both models
        models = [s["model"] for s in summary]
        self.assertIn("res.partner", models)
        self.assertIn("res.users", models)

    def test_get_pending_summary_excludes_approved(self):
        """Test summary excludes approved/rejected reviews."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create pending review
        self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "pending",
            }
        )

        # Create approved review (should not be counted)
        self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id + 1,
                "definition_id": self.definition_user.id,
                "status": "approved",
            }
        )

        summary = self.env["spp.approval.review"].get_pending_summary(user_id=self.user_approver.id)

        partner_summary = next((s for s in summary if s["model"] == "res.partner"), None)
        self.assertEqual(partner_summary["pending_count"], 1)

    def test_get_pending_summary_ordering(self):
        """Test summary is ordered by pending count descending."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create user-type definition for res.users
        user_model = self.env.ref("base.model_res_users")
        user_definition = self.env["spp.approval.definition"].create(
            {
                "name": "User Approval",
                "model_id": user_model.id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver.id)],
            }
        )

        user = self.env["res.users"].create({"name": "Test User", "login": "testuser_ordering"})

        # Create more partner reviews than user reviews
        for i in range(3):
            self.env["spp.approval.review"].create(
                {
                    "model": "res.partner",
                    "res_id": partner.id + i,
                    "definition_id": self.definition_user.id,
                    "status": "pending",
                }
            )

        self.env["spp.approval.review"].create(
            {
                "model": "res.users",
                "res_id": user.id,
                "definition_id": user_definition.id,
                "status": "pending",
            }
        )

        summary = self.env["spp.approval.review"].get_pending_summary(user_id=self.user_approver.id)

        # Partner should come first (3 pending) before users (1 pending)
        self.assertEqual(summary[0]["model"], "res.partner")
        self.assertTrue(summary[0]["pending_count"] >= summary[1]["pending_count"])

    # === Unique Constraint Tests ===

    def test_unique_pending_review_constraint(self):
        """Test that only one pending review per definition per record is allowed."""
        from psycopg2 import IntegrityError

        from odoo.tools import mute_logger

        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create first pending review
        self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "pending",
            }
        )

        # Try to create second pending review for same record and definition
        # This should fail due to unique constraint
        with mute_logger("odoo.sql_db"):
            with self.assertRaises(IntegrityError):
                with self.cr.savepoint():
                    self.env["spp.approval.review"].create(
                        {
                            "model": "res.partner",
                            "res_id": partner.id,
                            "definition_id": self.definition_user.id,
                            "status": "pending",
                        }
                    )

    def test_multiple_reviews_allowed_different_status(self):
        """Test multiple reviews allowed if status is different."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        # Create approved review
        review1 = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "approved",
            }
        )

        # Create pending review for same record (should work)
        review2 = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
                "status": "pending",
            }
        )

        self.assertTrue(review1.exists())
        self.assertTrue(review2.exists())

    # === Edge Cases ===

    def test_review_with_empty_comment(self):
        """Test review can be approved/rejected with empty comment."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})

        review = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "definition_id": self.definition_user.id,
            }
        )

        # Approve with no comment
        review.action_approve()
        self.assertEqual(review.status, "approved")

        # Create another for reject
        review2 = self.env["spp.approval.review"].create(
            {
                "model": "res.partner",
                "res_id": partner.id + 1,
                "definition_id": self.definition_user.id,
            }
        )

        # Reject with no comment
        review2.action_reject()
        self.assertEqual(review2.status, "rejected")
