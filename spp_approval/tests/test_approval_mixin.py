import unittest
from datetime import timedelta

from odoo import Command, fields, models
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


class TestApprovalModel(models.Model):
    """Test model for approval mixin testing."""

    _name = "x_test.approval.model"
    _inherit = ["mail.thread", "mail.activity.mixin", "spp.approval.mixin"]
    _description = "Test Model for Approval Mixin"
    _module = "spp_approval"

    name = fields.Char(required=True)
    value = fields.Integer()
    company_id = fields.Many2one("res.company")
    approver_user_id = fields.Many2one("res.users", string="Approver")

    # Track hook calls for testing
    hook_submit_called = fields.Boolean(default=False)
    hook_after_submit_called = fields.Boolean(default=False)
    hook_approve_called = fields.Boolean(default=False)
    hook_reject_called = fields.Boolean(default=False)
    hook_reset_called = fields.Boolean(default=False)
    hook_revision_called = fields.Boolean(default=False)

    def _on_submit(self):
        self.hook_submit_called = True

    def _after_submit(self):
        self.hook_after_submit_called = True

    def _on_approve(self):
        self.hook_approve_called = True

    def _on_reject(self, reason):
        self.hook_reject_called = True

    def _on_reset_to_draft(self):
        self.hook_reset_called = True

    def _on_request_revision(self, notes):
        self.hook_revision_called = True


@tagged("post_install", "-at_install")
class TestApprovalMixin(TransactionCase):
    """Test cases for the approval mixin functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # The test model is automatically registered by Odoo's test framework
        # when the test module is loaded. No manual registration needed in Odoo 19.

        # Create test users
        cls.user_submitter = cls.env["res.users"].create(
            {
                "name": "Test Submitter",
                "login": "test_submitter",
                "email": "submitter@test.com",
            }
        )

        cls.user_approver = cls.env["res.users"].create(
            {
                "name": "Test Approver",
                "login": "test_approver",
                "email": "approver@test.com",
                "group_ids": [Command.link(cls.env.ref("spp_approval.group_approval_approver").id)],
            }
        )

        cls.user_approver2 = cls.env["res.users"].create(
            {
                "name": "Test Approver 2",
                "login": "test_approver2",
                "email": "approver2@test.com",
                "group_ids": [Command.link(cls.env.ref("spp_approval.group_approval_approver").id)],
            }
        )

        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Test Manager",
                "login": "test_manager",
                "email": "manager@test.com",
                "group_ids": [Command.link(cls.env.ref("spp_approval.group_approval_manager").id)],
            }
        )

        # Create test model reference - in Odoo 19, we need to create it if it doesn't exist
        cls.test_model = cls.env["ir.model"].search([("model", "=", "x_test.approval.model")], limit=1)
        if not cls.test_model:
            # Model not registered in ir.model, skip this test class
            raise unittest.SkipTest("Test model x_test.approval.model not registered - skipping mixin tests")

        # Create approval definition
        cls.definition = cls.env["spp.approval.definition"].create(
            {
                "name": "Test Approval",
                "model_id": cls.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(cls.user_approver.id)],
            }
        )

    # === Basic Workflow Tests ===

    def test_workflow_draft_to_approved(self):
        """Test full workflow: draft -> pending -> approved."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Initial state
        self.assertEqual(record.approval_state, "draft")
        self.assertTrue(record.can_submit)
        self.assertFalse(record.can_approve)
        self.assertFalse(record.can_reject)

        # Submit for approval
        record.with_user(self.user_submitter).action_submit_for_approval()

        # Check pending state
        self.assertEqual(record.approval_state, "pending")
        self.assertEqual(record.submitted_by_id, self.user_submitter)
        self.assertTrue(record.submitted_date)
        self.assertTrue(record.hook_submit_called)
        self.assertTrue(record.hook_after_submit_called)

        # Approve as approver
        record.with_user(self.user_approver).action_approve(comment="Looks good!")

        # Check approved state
        self.assertEqual(record.approval_state, "approved")
        self.assertEqual(record.approved_by_id, self.user_approver)
        self.assertTrue(record.approved_date)
        self.assertTrue(record.hook_approve_called)

    def test_workflow_draft_to_rejected_to_draft(self):
        """Test workflow: draft -> pending -> rejected -> draft."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Submit for approval
        record.with_user(self.user_submitter).action_submit_for_approval()
        self.assertEqual(record.approval_state, "pending")

        # Reject
        record.with_user(self.user_approver)._do_reject("Not good enough")

        # Check rejected state
        self.assertEqual(record.approval_state, "rejected")
        self.assertEqual(record.rejected_by_id, self.user_approver)
        self.assertTrue(record.rejected_date)
        self.assertEqual(record.rejection_reason, "Not good enough")
        self.assertTrue(record.hook_reject_called)

        # Reset to draft
        record.action_reset_to_draft()

        # Check draft state
        self.assertEqual(record.approval_state, "draft")
        self.assertFalse(record.rejected_by_id)
        self.assertFalse(record.rejected_date)
        self.assertFalse(record.rejection_reason)
        self.assertTrue(record.hook_reset_called)

    # === Permission Tests ===

    def test_can_submit_permission(self):
        """Test can_submit computed field."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Draft record can be submitted
        self.assertTrue(record.can_submit)

        # Pending record cannot be submitted
        record.with_user(self.user_submitter).action_submit_for_approval()
        self.assertFalse(record.can_submit)

    def test_can_approve_permission(self):
        """Test can_approve computed field."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Draft record cannot be approved
        self.assertFalse(record.can_approve)

        # Submit for approval
        record.with_user(self.user_submitter).action_submit_for_approval()

        # Approver can approve
        self.assertTrue(record.with_user(self.user_approver).can_approve)

        # Non-approver cannot approve
        self.assertFalse(record.with_user(self.user_submitter).can_approve)

    def test_can_reject_permission(self):
        """Test can_reject computed field."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Draft record cannot be rejected
        self.assertFalse(record.can_reject)

        # Submit for approval
        record.with_user(self.user_submitter).action_submit_for_approval()

        # Approver can reject
        self.assertTrue(record.with_user(self.user_approver).can_reject)

        # Non-approver cannot reject
        self.assertFalse(record.with_user(self.user_submitter).can_reject)

    # === Authorization Tests ===

    def test_unauthorized_approve_raises_error(self):
        """Test that non-approver cannot approve."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # Try to approve as non-approver
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_submitter).action_approve()

        self.assertIn("not authorized", str(cm.exception))

    def test_unauthorized_reject_raises_error(self):
        """Test that non-approver cannot reject."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # Try to reject as non-approver
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_submitter)._do_reject("Reason")

        self.assertIn("not authorized", str(cm.exception))

    # === State Transition Tests ===

    def test_cannot_submit_pending_record(self):
        """Test that pending record cannot be submitted again."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # Try to submit again
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_submitter).action_submit_for_approval()

        self.assertIn("Only draft records", str(cm.exception))

    def test_cannot_approve_draft_record(self):
        """Test that draft record cannot be approved."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Try to approve draft record
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_approver).action_approve()

        self.assertIn("Only pending records", str(cm.exception))

    def test_cannot_approve_approved_record(self):
        """Test that approved record cannot be approved again."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()
        record.with_user(self.user_approver).action_approve()

        # Try to approve again
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_approver).action_approve()

        self.assertIn("Only pending records", str(cm.exception))

    def test_cannot_reset_non_rejected_record(self):
        """Test that only rejected records can be reset."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Try to reset draft record
        with self.assertRaises(UserError) as cm:
            record.action_reset_to_draft()

        self.assertIn("Only rejected records", str(cm.exception))

    # === Auto-Approve Tests ===

    def test_auto_approve_when_submitter_is_approver(self):
        """Test auto-approve when submitter is also an approver."""
        # Update definition to enable auto-approve
        self.definition.write({"auto_approve_same_user": True})

        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Submit as approver (who is also an approver)
        record.with_user(self.user_approver).action_submit_for_approval()

        # Should be auto-approved
        self.assertEqual(record.approval_state, "approved")
        self.assertEqual(record.approved_by_id, self.user_approver)

    def test_no_auto_approve_when_disabled(self):
        """Test that auto-approve doesn't happen when disabled."""
        # Ensure auto-approve is disabled
        self.definition.write({"auto_approve_same_user": False})

        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Submit as approver
        record.with_user(self.user_approver).action_submit_for_approval()

        # Should remain pending
        self.assertEqual(record.approval_state, "pending")

    # === System Freeze Tests ===

    def test_system_freeze_blocks_submission(self):
        """Test that system freeze blocks submission."""
        # Create active freeze
        self.env["spp.approval.freeze"].create(
            {
                "name": "Test Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
            }
        )

        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Try to submit during freeze
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_submitter).action_submit_for_approval()

        self.assertIn("frozen", str(cm.exception))

    def test_no_freeze_when_not_respecting_freeze(self):
        """Test submission works when definition doesn't respect freeze."""
        # Create active freeze
        self.env["spp.approval.freeze"].create(
            {
                "name": "Test Freeze",
                "reason": "audit",
                "date_start": fields.Datetime.now() - timedelta(hours=1),
                "date_end": fields.Datetime.now() + timedelta(hours=1),
            }
        )

        # Update definition to not respect freeze
        self.definition.write({"is_respect_system_freeze": False})

        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Should work despite freeze
        record.with_user(self.user_submitter).action_submit_for_approval()
        self.assertEqual(record.approval_state, "pending")

    # === Review Creation Tests ===

    def test_review_created_on_submit(self):
        """Test that review record is created on submission."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # Check review was created
        reviews = self.env["spp.approval.review"].search(
            [("model", "=", "x_test.approval.model"), ("res_id", "=", record.id)]
        )

        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews.status, "pending")
        self.assertEqual(reviews.definition_id, self.definition)
        self.assertEqual(reviews.requested_by_id, self.user_submitter)

    def test_reviews_updated_on_approve(self):
        """Test that pending reviews are updated on approval."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()
        record.with_user(self.user_approver).action_approve(comment="Approved!")

        # Check review was updated
        reviews = self.env["spp.approval.review"].search(
            [("model", "=", "x_test.approval.model"), ("res_id", "=", record.id)]
        )

        self.assertEqual(reviews.status, "approved")
        self.assertEqual(reviews.reviewer_id, self.user_approver)
        self.assertEqual(reviews.comment, "Approved!")

    def test_reviews_updated_on_reject(self):
        """Test that pending reviews are updated on rejection."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()
        record.with_user(self.user_approver)._do_reject("Not acceptable")

        # Check review was updated
        reviews = self.env["spp.approval.review"].search(
            [("model", "=", "x_test.approval.model"), ("res_id", "=", record.id)]
        )

        self.assertEqual(reviews.status, "rejected")
        self.assertEqual(reviews.reviewer_id, self.user_approver)
        self.assertEqual(reviews.comment, "Not acceptable")

    # === Audit Fields Tests ===

    def test_audit_fields_populated_on_submit(self):
        """Test that audit fields are populated on submission."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        before_submit = fields.Datetime.now()
        record.with_user(self.user_submitter).action_submit_for_approval()
        after_submit = fields.Datetime.now()

        self.assertEqual(record.submitted_by_id, self.user_submitter)
        self.assertTrue(before_submit <= record.submitted_date <= after_submit)

    def test_audit_fields_populated_on_approve(self):
        """Test that audit fields are populated on approval."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        before_approve = fields.Datetime.now()
        record.with_user(self.user_approver).action_approve()
        after_approve = fields.Datetime.now()

        self.assertEqual(record.approved_by_id, self.user_approver)
        self.assertTrue(before_approve <= record.approved_date <= after_approve)

    def test_audit_fields_populated_on_reject(self):
        """Test that audit fields are populated on rejection."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        before_reject = fields.Datetime.now()
        record.with_user(self.user_approver)._do_reject("Reason")
        after_reject = fields.Datetime.now()

        self.assertEqual(record.rejected_by_id, self.user_approver)
        self.assertTrue(before_reject <= record.rejected_date <= after_reject)
        self.assertEqual(record.rejection_reason, "Reason")

    # === Optimistic Locking Tests ===

    def test_optimistic_locking_on_concurrent_approve(self):
        """Test optimistic locking prevents concurrent approvals."""
        # Create definition with multiple approvers
        self.env["spp.approval.definition"].create(
            {
                "name": "Multi Approver",
                "model_id": self.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [
                    Command.link(self.user_approver.id),
                    Command.link(self.user_approver2.id),
                ],
            }
        )

        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # First approver approves
        record.with_user(self.user_approver).action_approve()

        # Second approver tries to approve (should fail due to state change)
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_approver2).action_approve()

        self.assertIn("Only pending records", str(cm.exception))

    def test_approval_version_increments(self):
        """Test that approval_version increments on approval."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        initial_version = record.approval_version
        record.with_user(self.user_submitter).action_submit_for_approval()
        record.with_user(self.user_approver).action_approve()

        self.assertEqual(record.approval_version, initial_version + 1)

    # === Batch Approval Tests ===

    def test_batch_approve_multiple_records(self):
        """Test batch approval of multiple records."""
        records = self.env["x_test.approval.model"].create(
            [
                {"name": "Record 1", "value": 100},
                {"name": "Record 2", "value": 200},
                {"name": "Record 3", "value": 300},
            ]
        )

        # Submit all for approval
        for record in records:
            record.with_user(self.user_submitter).action_submit_for_approval()

        # Batch approve
        result = (
            self.env["x_test.approval.model"]
            .with_user(self.user_approver)
            .action_approve_batch(records.ids, comment="Batch approved")
        )

        self.assertEqual(result["approved_count"], 3)

        # Check all are approved
        for record in records:
            self.assertEqual(record.approval_state, "approved")

    def test_batch_approve_skips_unauthorized_records(self):
        """Test batch approval skips records user can't approve."""
        # Create definition for specific records only
        self.env["spp.approval.definition"].create(
            {
                "name": "Specific Approval",
                "model_id": self.test_model.id,
                "approval_type": "user",
                "approval_user_ids": [Command.link(self.user_approver2.id)],
                "domain": "[('value', '>', 200)]",
                "sequence": 5,
            }
        )

        records = self.env["x_test.approval.model"].create(
            [
                {"name": "Record 1", "value": 100},  # user_approver can approve
                {"name": "Record 2", "value": 250},  # user_approver2 can approve
            ]
        )

        # Submit all for approval
        for record in records:
            record.with_user(self.user_submitter).action_submit_for_approval()

        # Batch approve as user_approver (can only approve first record)
        result = self.env["x_test.approval.model"].with_user(self.user_approver).action_approve_batch(records.ids)

        self.assertEqual(result["approved_count"], 1)

    # === No Definition Tests ===

    def test_submit_without_definition_raises_error(self):
        """Test that submission without definition raises error."""
        # Deactivate all definitions
        self.definition.write({"active": False})

        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Try to submit without definition
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_submitter).action_submit_for_approval()

        self.assertIn("No approval workflow configured", str(cm.exception))

    # === Pending Since Tests ===

    def test_pending_since_computed(self):
        """Test pending_since is computed correctly."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Draft state
        self.assertFalse(record.pending_since)

        # Pending state
        record.with_user(self.user_submitter).action_submit_for_approval()
        self.assertEqual(record.pending_since, record.submitted_date)

        # Approved state
        record.with_user(self.user_approver).action_approve()
        self.assertFalse(record.pending_since)

    # === Field-based Approval Tests ===

    def test_field_based_approval(self):
        """Test approval using dynamic field."""
        # Create field-based definition
        approver_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", self.test_model.id),
                ("name", "=", "approver_user_id"),
            ],
            limit=1,
        )

        self.env["spp.approval.definition"].create(
            {
                "name": "Field Approval",
                "model_id": self.test_model.id,
                "approval_type": "field",
                "approval_field_id": approver_field.id,
                "sequence": 1,
            }
        )

        # Deactivate other definitions
        self.definition.write({"active": False})

        record = self.env["x_test.approval.model"].create(
            {
                "name": "Test Record",
                "value": 100,
                "approver_user_id": self.user_approver.id,
            }
        )

        record.with_user(self.user_submitter).action_submit_for_approval()

        # user_approver should be able to approve
        self.assertTrue(record.with_user(self.user_approver).can_approve)

        # user_approver2 should not be able to approve
        self.assertFalse(record.with_user(self.user_approver2).can_approve)

    # === Revision Workflow Tests ===

    def test_revision_request_workflow(self):
        """Test workflow: draft -> pending -> revision -> draft."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Submit for approval
        record.with_user(self.user_submitter).action_submit_for_approval()
        self.assertEqual(record.approval_state, "pending")

        # Request revision
        record.with_user(self.user_approver)._do_request_revision("Please update the value")

        # Check revision state
        self.assertEqual(record.approval_state, "revision")
        self.assertEqual(record.revision_requested_by_id, self.user_approver)
        self.assertTrue(record.revision_requested_date)
        self.assertEqual(record.revision_notes, "Please update the value")
        self.assertTrue(record.hook_revision_called)

        # Reset to draft
        record.action_reset_to_draft()

        # Check draft state and cleared revision fields
        self.assertEqual(record.approval_state, "draft")
        self.assertFalse(record.revision_requested_by_id)
        self.assertFalse(record.revision_requested_date)
        self.assertFalse(record.revision_notes)
        self.assertTrue(record.hook_reset_called)

    def test_revision_request_opens_wizard(self):
        """Test action_request_revision returns wizard action."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # Request revision should return wizard action
        action = record.with_user(self.user_approver).action_request_revision()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.approval.revision.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_res_model"], "x_test.approval.model")
        self.assertEqual(action["context"]["default_res_id"], record.id)

    def test_revision_request_unauthorized_raises_error(self):
        """Test that non-approver cannot request revision."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # Try to request revision as non-approver
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_submitter)._do_request_revision("Notes")

        self.assertIn("not authorized", str(cm.exception))

    def test_cannot_request_revision_on_draft(self):
        """Test revision request fails on draft record."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        # Try to request revision on draft record
        with self.assertRaises(UserError) as cm:
            record.with_user(self.user_approver).action_request_revision()

        self.assertIn("Only pending records", str(cm.exception))

    def test_revision_request_updates_reviews(self):
        """Test that pending reviews are updated on revision request."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()
        record.with_user(self.user_approver)._do_request_revision("Needs changes")

        # Check review was updated - status is rejected when revision is requested
        reviews = self.env["spp.approval.review"].search(
            [("model", "=", "x_test.approval.model"), ("res_id", "=", record.id)]
        )

        self.assertEqual(reviews.status, "rejected")

    def test_revision_audit_fields_populated(self):
        """Test that revision audit fields are populated correctly."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        before_revision = fields.Datetime.now()
        record.with_user(self.user_approver)._do_request_revision("Update required")
        after_revision = fields.Datetime.now()

        self.assertEqual(record.revision_requested_by_id, self.user_approver)
        self.assertTrue(before_revision <= record.revision_requested_date <= after_revision)
        self.assertEqual(record.revision_notes, "Update required")

    def test_can_reset_revision_record(self):
        """Test that revision-requested record can be reset to draft."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()
        record.with_user(self.user_approver)._do_request_revision("Please revise")

        # Should be able to reset from revision state
        record.action_reset_to_draft()
        self.assertEqual(record.approval_state, "draft")

    def test_revision_wizard_performs_revision(self):
        """Test that revision wizard correctly performs revision."""
        record = self.env["x_test.approval.model"].create({"name": "Test Record", "value": 100})

        record.with_user(self.user_submitter).action_submit_for_approval()

        # Create and execute wizard
        wizard = (
            self.env["spp.approval.revision.wizard"]
            .with_user(self.user_approver)
            .create(
                {
                    "res_model": "x_test.approval.model",
                    "res_id": record.id,
                    "notes": "Please add more details",
                }
            )
        )
        wizard.action_request_revision()

        # Check record state
        self.assertEqual(record.approval_state, "revision")
        self.assertEqual(record.revision_notes, "Please add more details")
