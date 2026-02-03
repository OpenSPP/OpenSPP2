"""Tests for spp.artifact.version model."""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestArtifactVersion(TransactionCase):
    """Test cases for ArtifactVersion model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ArtifactVersion = cls.env["spp.artifact.version"]
        # Use res.partner as a test model since it's always available
        cls.test_partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner for Versioning",
            }
        )

    def test_create_version(self):
        """Test creating a version record."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Initial version",
                "data_snapshot": {"name": "Test Partner for Versioning"},
            }
        )
        self.assertEqual(version.version, 1)
        self.assertEqual(version.state, "draft")
        self.assertEqual(version.model, "res.partner")
        self.assertEqual(version.res_id, self.test_partner.id)
        self.assertEqual(version.artifact_name, "Test Partner for Versioning")

    def test_version_positive_constraint(self):
        """Test that version number must be positive."""
        with self.assertRaises(ValidationError):
            self.ArtifactVersion.create(
                {
                    "model": "res.partner",
                    "res_id": self.test_partner.id,
                    "version": 0,
                    "change_summary": "Invalid version",
                }
            )

    def test_version_unique_constraint(self):
        """Test that version number must be unique per artifact."""
        self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "First version",
            }
        )
        with self.assertRaises(ValidationError):
            self.ArtifactVersion.create(
                {
                    "model": "res.partner",
                    "res_id": self.test_partner.id,
                    "version": 1,
                    "change_summary": "Duplicate version",
                }
            )

    def test_single_current_version_constraint(self):
        """Test that only one version can be current at a time."""
        self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "First current",
                "state": "current",
            }
        )
        with self.assertRaises(ValidationError):
            self.ArtifactVersion.create(
                {
                    "model": "res.partner",
                    "res_id": self.test_partner.id,
                    "version": 2,
                    "change_summary": "Second current",
                    "state": "current",
                }
            )

    def test_state_transitions_draft_to_activated(self):
        """Test activating a draft version."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "To be activated",
            }
        )
        self.assertEqual(version.state, "draft")
        version.action_activate_now()
        self.assertEqual(version.state, "current")
        self.assertEqual(version.effective_date, fields.Date.today())

    def test_state_transitions_approval_workflow(self):
        """Test approval workflow state transitions."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Needs approval",
            }
        )
        # Submit for approval
        version.action_submit_for_approval()
        self.assertEqual(version.state, "pending")

        # Approve
        version.action_approve()
        self.assertEqual(version.state, "approved")

    def test_state_transitions_rejection(self):
        """Test rejection returns to draft."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Will be rejected",
            }
        )
        version.action_submit_for_approval()
        version.action_reject()
        self.assertEqual(version.state, "draft")

    def test_schedule_version(self):
        """Test scheduling a version for future activation."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Scheduled version",
            }
        )
        future_date = fields.Date.today() + timedelta(days=7)
        version.action_schedule(future_date)
        self.assertEqual(version.state, "scheduled")
        self.assertEqual(version.effective_date, future_date)
        self.assertEqual(version.days_until_active, 7)
        self.assertTrue(version.is_scheduled)

    def test_schedule_past_date_fails(self):
        """Test that scheduling with past date fails."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Bad schedule",
            }
        )
        past_date = fields.Date.today() - timedelta(days=1)
        with self.assertRaises(ValidationError):
            version.action_schedule(past_date)

    def test_cancel_scheduled_version(self):
        """Test cancelling a scheduled version."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "To cancel",
            }
        )
        future_date = fields.Date.today() + timedelta(days=7)
        version.action_schedule(future_date)
        version.action_cancel_scheduled()
        self.assertEqual(version.state, "cancelled")

    def test_activation_supersedes_previous(self):
        """Test that activating a version supersedes the previous one."""
        version1 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Version 1",
                "state": "current",
            }
        )
        version2 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 2,
                "change_summary": "Version 2",
            }
        )
        version2.action_activate_now()
        # Refresh version1 from database
        version1.invalidate_recordset()
        self.assertEqual(version1.state, "superseded")
        self.assertEqual(version2.state, "current")
        self.assertEqual(version2.supersedes_id, version1)

    def test_restore_as_new(self):
        """Test restoring a version creates a new draft version."""
        version1 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Original",
                "data_snapshot": {"name": "Original Data"},
                "state": "superseded",
            }
        )
        result = version1.action_restore_as_new()
        # Should return wizard action
        self.assertEqual(result["res_model"], "spp.artifact.version.schedule.wizard")

        # Find the new version
        new_version = self.ArtifactVersion.search(
            [
                ("model", "=", "res.partner"),
                ("res_id", "=", self.test_partner.id),
                ("version", "=", 2),
            ]
        )
        self.assertEqual(new_version.state, "draft")
        self.assertEqual(new_version.data_snapshot, {"name": "Original Data"})
        self.assertIn("Restored from v1", new_version.change_summary)

    def test_serialize_deserialize_snapshot(self):
        """Test serialization of various field types."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Serialization test",
            }
        )
        # Test serialization with partner record
        snapshot = version._serialize_snapshot(self.test_partner, ["name", "create_date", "parent_id"])
        self.assertEqual(snapshot["name"], "Test Partner for Versioning")
        # Many2one should be serialized as ID
        self.assertFalse(snapshot["parent_id"])  # No parent
        # Datetime should be ISO format string
        self.assertIsInstance(snapshot["create_date"], str)

    def test_approval_required_check(self):
        """Test approval requirement checking."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Approval check",
            }
        )
        # By default, no approval required
        self.assertFalse(version._is_approval_required())

        # Set global parameter
        self.env["ir.config_parameter"].sudo().set_param("spp_versioning.require_approval", "True")
        self.assertTrue(version._is_approval_required())

        # Clean up
        self.env["ir.config_parameter"].sudo().set_param("spp_versioning.require_approval", "False")

    def test_approval_required_blocks_scheduling(self):
        """Test that approval requirement blocks scheduling from draft."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Blocked schedule",
            }
        )
        # Set global parameter to require approval
        self.env["ir.config_parameter"].sudo().set_param("spp_versioning.require_approval", "True")
        try:
            future_date = fields.Date.today() + timedelta(days=7)
            with self.assertRaises(ValidationError):
                version.action_schedule(future_date)

            # After approval, scheduling should work
            version.action_submit_for_approval()
            version.action_approve()
            version.action_schedule(future_date)
            self.assertEqual(version.state, "scheduled")
        finally:
            # Clean up
            self.env["ir.config_parameter"].sudo().set_param("spp_versioning.require_approval", "False")

    def test_compute_artifact_name_deleted(self):
        """Test artifact name computation when artifact is deleted."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Will be orphaned",
            }
        )
        self.assertEqual(version.artifact_name, "Test Partner for Versioning")
        # Manually update res_id to non-existent record
        version.write({"res_id": 999999999})
        version.invalidate_recordset()
        self.assertEqual(version.artifact_name, "Deleted")

    def test_view_artifact_action(self):
        """Test action to view artifact."""
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "View test",
            }
        )
        action = version.action_view_artifact()
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.test_partner.id)
