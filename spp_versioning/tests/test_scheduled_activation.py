"""Tests for scheduled version activation."""

from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScheduledActivation(TransactionCase):
    """Test cases for scheduled version activation via cron."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ArtifactVersion = cls.env["spp.artifact.version"]
        cls.test_partner = cls.env["res.partner"].create({"name": "Test Partner for Scheduling"})

    def test_cron_activates_due_versions(self):
        """Test that cron activates versions whose effective_date has arrived."""
        # Create a scheduled version with today's date (should be activated)
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Due for activation",
                "state": "scheduled",
                "effective_date": fields.Date.today(),
            }
        )
        self.assertEqual(version.state, "scheduled")

        # Run cron
        self.ArtifactVersion._cron_activate_scheduled_versions()

        # Refresh and check
        version.invalidate_recordset()
        self.assertEqual(version.state, "current")

    def test_cron_skips_future_versions(self):
        """Test that cron does not activate versions with future effective_date."""
        future_date = fields.Date.today() + timedelta(days=7)
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Future version",
                "state": "scheduled",
                "effective_date": future_date,
            }
        )
        # Run cron
        self.ArtifactVersion._cron_activate_scheduled_versions()

        # Should still be scheduled
        version.invalidate_recordset()
        self.assertEqual(version.state, "scheduled")

    def test_cron_activates_past_due_versions(self):
        """Test that cron activates versions that are past due."""
        past_date = fields.Date.today() - timedelta(days=1)
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Past due version",
                "state": "scheduled",
                "effective_date": past_date,
            }
        )
        # Run cron
        self.ArtifactVersion._cron_activate_scheduled_versions()

        # Should be activated
        version.invalidate_recordset()
        self.assertEqual(version.state, "current")

    def test_cron_supersedes_previous_current(self):
        """Test that cron properly supersedes the previous current version."""
        # Create current version
        version1 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Current version",
                "state": "current",
                "effective_date": fields.Date.today() - timedelta(days=30),
            }
        )
        # Create scheduled version for today
        version2 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 2,
                "change_summary": "New version",
                "state": "scheduled",
                "effective_date": fields.Date.today(),
            }
        )
        # Run cron
        self.ArtifactVersion._cron_activate_scheduled_versions()

        # Check states
        version1.invalidate_recordset()
        version2.invalidate_recordset()
        self.assertEqual(version1.state, "superseded")
        self.assertEqual(version2.state, "current")
        self.assertEqual(version2.supersedes_id, version1)

    def test_cron_handles_multiple_artifacts(self):
        """Test that cron handles multiple artifacts correctly."""
        partner1 = self.env["res.partner"].create({"name": "Partner 1"})
        partner2 = self.env["res.partner"].create({"name": "Partner 2"})

        version1 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner1.id,
                "version": 1,
                "change_summary": "P1 V1",
                "state": "scheduled",
                "effective_date": fields.Date.today(),
            }
        )
        version2 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner2.id,
                "version": 1,
                "change_summary": "P2 V1",
                "state": "scheduled",
                "effective_date": fields.Date.today(),
            }
        )

        # Run cron
        self.ArtifactVersion._cron_activate_scheduled_versions()

        version1.invalidate_recordset()
        version2.invalidate_recordset()
        self.assertEqual(version1.state, "current")
        self.assertEqual(version2.state, "current")

    def test_cron_activates_in_version_order(self):
        """Test that multiple scheduled versions for same artifact activate in order."""
        # Create two scheduled versions for the same date
        version1 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "V1",
                "state": "scheduled",
                "effective_date": fields.Date.today() - timedelta(days=1),
            }
        )
        version2 = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 2,
                "change_summary": "V2",
                "state": "scheduled",
                "effective_date": fields.Date.today(),
            }
        )

        # Run cron
        self.ArtifactVersion._cron_activate_scheduled_versions()

        version1.invalidate_recordset()
        version2.invalidate_recordset()
        # Both should be processed, v2 should be current (processed last)
        self.assertEqual(version1.state, "superseded")
        self.assertEqual(version2.state, "current")

    def test_days_until_active_computation(self):
        """Test the days_until_active computed field."""
        future_date = fields.Date.today() + timedelta(days=10)
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Future",
                "state": "scheduled",
                "effective_date": future_date,
            }
        )
        self.assertEqual(version.days_until_active, 10)

        # Past or today should be 0
        version.write({"effective_date": fields.Date.today()})
        version.invalidate_recordset()
        self.assertEqual(version.days_until_active, 0)

    def test_is_scheduled_computation(self):
        """Test the is_scheduled computed field."""
        future_date = fields.Date.today() + timedelta(days=5)
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": self.test_partner.id,
                "version": 1,
                "change_summary": "Scheduled",
                "state": "scheduled",
                "effective_date": future_date,
            }
        )
        self.assertTrue(version.is_scheduled)

        # Change state to current
        version.write({"state": "current"})
        version.invalidate_recordset()
        self.assertFalse(version.is_scheduled)
