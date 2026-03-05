"""Test cases for spp.case program integration."""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCasePrograms(TransactionCase):
    """Test the spp.case program integration."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()

        # Create case worker user for required case_worker_id field
        cls.case_worker = cls.env["res.users"].create(
            {
                "name": "Test Case Worker",
                "login": "test_case_worker",
                "email": "caseworker@test.com",
            }
        )

        # Create test partner (client)
        cls.client = cls.env["res.partner"].create(
            {
                "name": "Test Client",
                "email": "client@test.com",
            }
        )

        # Create program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program",
                "target_type": "individual",
            }
        )

        # Create program membership - enrolled
        cls.membership_enrolled = cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.client.id,
                "program_id": cls.program.id,
                "state": "enrolled",
            }
        )

        # Create program membership - paused
        cls.program_paused = cls.env["spp.program"].create(
            {
                "name": "Test Program Paused",
                "target_type": "individual",
            }
        )
        cls.membership_paused = cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.client.id,
                "program_id": cls.program_paused.id,
                "state": "paused",
            }
        )

        # Create program membership - exited (not active)
        cls.program_exited = cls.env["spp.program"].create(
            {
                "name": "Test Program Exited",
                "target_type": "individual",
            }
        )
        cls.membership_exited = cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.client.id,
                "program_id": cls.program_exited.id,
                "state": "exited",
            }
        )

        # Create case type
        cls.case_type = cls.env["spp.case.type"].create(
            {
                "name": "Social Protection",
                "code": "SP001",
                "domain": "social_protection",
            }
        )

        # Create case
        cls.case = cls.env["spp.case"].create(
            {
                "partner_id": cls.client.id,
                "case_type_id": cls.case_type.id,
                "case_worker_id": cls.case_worker.id,
                "presenting_issue": "<p>Test presenting issue for case programs</p>",
            }
        )

    def test_program_membership_computation(self):
        """Test that program membership info is computed correctly."""
        # Set program memberships
        self.case.program_membership_ids = [
            Command.set([self.membership_enrolled.id, self.membership_paused.id, self.membership_exited.id])
        ]

        # Trigger computation
        self.case._compute_program_info()

        # Should have active enrollment (enrolled + paused)
        self.assertTrue(self.case.has_active_enrollment)
        # Should count 2 active programs (enrolled + paused)
        self.assertEqual(self.case.active_program_count, 2)
        # Should include both active program names
        self.assertIn("Test Program", self.case.enrolled_program_names)
        self.assertIn("Test Program Paused", self.case.enrolled_program_names)
        # Should not include exited program
        self.assertNotIn("Test Program Exited", self.case.enrolled_program_names)

    def test_no_active_enrollment(self):
        """Test case with no active enrollments."""
        # Set only exited membership
        self.case.program_membership_ids = [Command.set([self.membership_exited.id])]

        # Trigger computation
        self.case._compute_program_info()

        # Should not have active enrollment
        self.assertFalse(self.case.has_active_enrollment)
        # Should count 0 active programs
        self.assertEqual(self.case.active_program_count, 0)
        # Should have empty program names
        self.assertEqual(self.case.enrolled_program_names, "")

    def test_onchange_partner_programs(self):
        """Test that program memberships load when partner is selected."""
        # Create new case - partner_id is required so we'll start with a dummy partner
        # and then test the onchange when we switch partners
        dummy_partner = self.env["res.partner"].create({"name": "Dummy Partner"})
        new_case = self.env["spp.case"].create(
            {
                "partner_id": dummy_partner.id,
                "case_type_id": self.case_type.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Set partner - should trigger onchange
        new_case.partner_id = self.client
        new_case._onchange_partner_programs()

        # Should have loaded all memberships for this partner
        membership_ids = new_case.program_membership_ids.ids
        self.assertIn(self.membership_enrolled.id, membership_ids)
        self.assertIn(self.membership_paused.id, membership_ids)
        self.assertIn(self.membership_exited.id, membership_ids)

    def test_action_view_program_enrollments(self):
        """Test action to view program enrollments."""
        self.case.program_membership_ids = [Command.set([self.membership_enrolled.id, self.membership_paused.id])]

        action = self.case.action_view_program_enrollments()

        # Should return action dict
        self.assertEqual(action["name"], "Program Enrollments")
        self.assertEqual(action["res_model"], "spp.program.membership")
        self.assertEqual(action["view_mode"], "list,form")
        # Should filter to case's memberships
        self.assertIn(self.membership_enrolled.id, action["domain"][0][2])
        self.assertIn(self.membership_paused.id, action["domain"][0][2])

    def test_action_view_triggered_program(self):
        """Test action to view triggered program."""
        # Set triggered program
        self.case.triggered_by_program_id = self.program

        action = self.case.action_view_triggered_program()

        # Should return action dict
        self.assertEqual(action["name"], "Program")
        self.assertEqual(action["res_model"], "spp.program")
        self.assertEqual(action["res_id"], self.program.id)
        self.assertEqual(action["view_mode"], "form")

    def test_action_view_triggered_program_no_program(self):
        """Test action when no triggered program is set."""
        # No triggered program
        self.case.triggered_by_program_id = False

        action = self.case.action_view_triggered_program()

        # Should return False
        self.assertFalse(action)
