# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the program enrollment wizard."""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import Common


@tagged("post_install", "-at_install")
class TestEnrollmentWizard(Common):
    """Tests for spp.program.enrollment.wizard."""

    def setUp(self):
        super().setUp()
        # Activate the program for enrollment
        self.program.state = "active"

    def test_enrollment_creates_membership(self):
        """Test that enrollment creates a program membership."""
        wizard = self.env["spp.program.enrollment.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )

        # Verify no existing membership
        existing = self.env["spp.program.membership"].search(
            [
                ("partner_id", "=", self.registrant.id),
                ("program_id", "=", self.program.id),
            ]
        )
        self.assertFalse(existing)

        # Enroll
        wizard.action_enroll()

        # Verify membership was created
        membership = self.env["spp.program.membership"].search(
            [
                ("partner_id", "=", self.registrant.id),
                ("program_id", "=", self.program.id),
            ]
        )
        self.assertTrue(membership)
        self.assertEqual(membership.state, "draft")

    def test_enrollment_returns_notification_action(self):
        """Test that enrollment returns a notification action, not a redirect."""
        wizard = self.env["spp.program.enrollment.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )

        result = wizard.action_enroll()

        # Should return a notification action, not a window action
        self.assertEqual(result.get("type"), "ir.actions.client")
        self.assertEqual(result.get("tag"), "display_notification")

        # Should have success notification params
        params = result.get("params", {})
        self.assertEqual(params.get("type"), "success")
        self.assertIn(self.program.name, params.get("message", ""))

        # Should close the wizard after notification
        next_action = params.get("next", {})
        self.assertEqual(next_action.get("type"), "ir.actions.act_window_close")

    def test_enrollment_already_enrolled_raises_error(self):
        """Test that enrolling when already enrolled raises UserError."""
        # Create existing membership
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
                "state": "draft",
            }
        )

        wizard = self.env["spp.program.enrollment.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )

        # Should be flagged as already enrolled
        self.assertTrue(wizard.is_already_enrolled)

        # Should raise UserError
        with self.assertRaises(UserError):
            wizard.action_enroll()

    def test_compute_existing_programs(self):
        """Test that existing programs are computed correctly."""
        # Create membership in another program
        other_program = self.env["spp.program"].create({"name": "Other Program", "state": "active"})
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": other_program.id,
                "state": "enrolled",
            }
        )

        wizard = self.env["spp.program.enrollment.wizard"].create(
            {
                "partner_id": self.registrant.id,
                "program_id": self.program.id,
            }
        )

        # Should show the other program in existing programs
        self.assertIn(other_program, wizard.existing_program_ids)
        # Should not be flagged as already enrolled in the selected program
        self.assertFalse(wizard.is_already_enrolled)
