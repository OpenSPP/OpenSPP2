"""Test cases for spp.case model."""

from datetime import date, timedelta

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCase(TransactionCase):
    """Test the main spp.case model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()

        # Create test users (include base.group_user for internal user access)
        cls.case_worker = cls.env["res.users"].create(
            {
                "name": "Test Case Worker",
                "login": "test_worker",
                "email": "worker@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

        cls.supervisor = cls.env["res.users"].create(
            {
                "name": "Test Supervisor",
                "login": "test_supervisor",
                "email": "supervisor@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_supervisor").id),
                ],
            }
        )

        # Create test partner (client)
        cls.client = cls.env["res.partner"].create(
            {
                "name": "Test Client",
                "email": "client@test.com",
            }
        )

        # Create case type
        cls.case_type = cls.env["spp.case.type"].create(
            {
                "name": "Social Protection",
                "code": "SP001",
                "domain": "social_protection",
                "default_intensity": "2",
            }
        )

        # Create case stages
        cls.stage_intake = cls.env["spp.case.stage"].create(
            {
                "name": "Intake",
                "sequence": 1,
                "phase": "intake",
                "is_closed": False,
            }
        )

        cls.stage_planning = cls.env["spp.case.stage"].create(
            {
                "name": "Planning",
                "sequence": 2,
                "phase": "planning",
                "is_requires_plan": True,
                "is_closed": False,
            }
        )

        cls.stage_closed = cls.env["spp.case.stage"].create(
            {
                "name": "Closed",
                "sequence": 99,
                "phase": "closure",
                "is_closed": True,
            }
        )

        # Create case team
        cls.team = cls.env["spp.case.team"].create(
            {
                "name": "Test Team",
                "supervisor_id": cls.supervisor.id,
                "member_ids": [Command.set([cls.case_worker.id])],
            }
        )

    def test_create_case(self):
        """Test creating a case and verify defaults."""
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Client needs assistance</p>",
            }
        )

        self.assertTrue(case.name, "Case number should be generated")
        self.assertTrue(case.name.startswith("CASE-"), "Case number should have prefix")
        self.assertEqual(case.intensity_level, "2", "Default intensity should be level 2")
        self.assertEqual(case.priority, "medium", "Default priority should be medium")
        self.assertEqual(case.client_type, "individual", "Default client type should be individual")
        self.assertEqual(case.opened_date, date.today(), "Opened date should be today")
        self.assertTrue(case.is_active, "Case should be active")

    def test_case_number_generation(self):
        """Test that case numbers are auto-generated and unique."""
        case1 = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Issue 1</p>",
            }
        )

        case2 = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Issue 2</p>",
            }
        )

        self.assertTrue(case1.name, "Case 1 should have a number")
        self.assertTrue(case2.name, "Case 2 should have a number")
        self.assertNotEqual(case1.name, case2.name, "Case numbers should be unique")

    def test_case_stage_transition(self):
        """Test stage changes."""
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "stage_id": self.stage_intake.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Verify initial stage
        self.assertEqual(case.stage_id, self.stage_intake)
        self.assertTrue(case.is_active, "Case should be active in intake stage")

        # Try moving to stage that requires plan (should fail)
        with self.assertRaises(
            ValidationError,
            msg="Should not allow transition to stage requiring plan without plan",
        ):
            case.stage_id = self.stage_planning

    def test_case_close_reopen(self):
        """Test closure and reopening of cases."""
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "stage_id": self.stage_intake.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Close the case
        case.action_close_case()

        self.assertEqual(case.stage_id, self.stage_closed, "Case should be in closed stage")
        self.assertFalse(case.is_active, "Case should not be active when closed")
        self.assertEqual(
            case.actual_closure_date,
            date.today(),
            "Closure date should be today",
        )

        # Reopen the case
        case.action_reopen_case()

        self.assertEqual(case.stage_id, self.stage_intake, "Case should be back in intake stage")
        self.assertTrue(case.is_active, "Case should be active after reopening")
        self.assertFalse(case.actual_closure_date, "Closure date should be cleared after reopening")

    def test_days_open_computation(self):
        """Test days_open computed field."""
        # Create case with opened_date in the past
        past_date = date.today() - timedelta(days=10)
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "opened_date": past_date,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Compute days_open
        case._compute_days_open()

        self.assertEqual(
            case.days_open,
            10,
            "Days open should be 10 for case opened 10 days ago",
        )

        # Close the case
        case.write(
            {
                "stage_id": self.stage_closed.id,
                "actual_closure_date": date.today(),
            }
        )

        # Recompute days_open
        case._compute_days_open()

        self.assertEqual(
            case.days_open,
            10,
            "Days open should be 10 (from open to close)",
        )

    def test_intensity_level_constraints(self):
        """Test intensity level validation with stages."""
        # Create stage requiring minimum intensity
        high_intensity_stage = self.env["spp.case.stage"].create(
            {
                "name": "High Intensity Stage",
                "phase": "implementation",
                "min_intensity": "3",
            }
        )

        # Create case with low intensity
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "intensity_level": "1",
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Try to move to high intensity stage (should fail)
        with self.assertRaises(
            ValidationError,
            msg="Should not allow transition to high intensity stage with low intensity case",
        ):
            case.stage_id = high_intensity_stage

        # Increase intensity and try again
        case.intensity_level = "3"
        case.stage_id = high_intensity_stage
        self.assertEqual(
            case.stage_id,
            high_intensity_stage,
            "Should allow transition after increasing intensity",
        )

    def test_onchange_case_type(self):
        """Test that changing case type sets default intensity."""
        case = self.env["spp.case"].new(
            {
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Set case type
        case.case_type_id = self.case_type
        case._onchange_case_type_id()

        self.assertEqual(
            case.intensity_level,
            self.case_type.default_intensity,
            "Intensity should match case type default",
        )

    def test_onchange_team(self):
        """Test that changing team sets supervisor."""
        case = self.env["spp.case"].new(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Set team
        case.team_id = self.team
        case._onchange_team_id()

        self.assertEqual(
            case.supervisor_id,
            self.team.supervisor_id,
            "Supervisor should match team supervisor",
        )

    def test_has_active_plan_computation(self):
        """Test has_active_plan computed field."""
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Case should not have active plan initially
        case._compute_has_active_plan()
        self.assertFalse(case.has_active_plan, "New case should not have active plan")

        # Create an approved plan
        self.env["spp.case.intervention.plan"].create(
            {
                "case_id": case.id,
                "name": "Test Plan",
                "goals": "<p>Test goals</p>",
                "state": "approved",
                "is_current": True,
            }
        )

        # Recompute
        case._compute_has_active_plan()
        self.assertTrue(case.has_active_plan, "Case should have active plan")

    def test_current_plan_computation(self):
        """Test current_plan_id computed field."""
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Create a current plan
        current_plan = self.env["spp.case.intervention.plan"].create(
            {
                "case_id": case.id,
                "name": "Current Plan",
                "goals": "<p>Test goals</p>",
                "is_current": True,
            }
        )

        # Create an old plan
        self.env["spp.case.intervention.plan"].create(
            {
                "case_id": case.id,
                "name": "Old Plan",
                "goals": "<p>Old goals</p>",
                "is_current": False,
            }
        )

        # Compute current plan
        case._compute_current_plan()
        self.assertEqual(
            case.current_plan_id,
            current_plan,
            "Should return the current plan",
        )

    def test_is_active_computation(self):
        """Test is_active computed field based on stage."""
        case = self.env["spp.case"].create(
            {
                "case_type_id": self.case_type.id,
                "partner_id": self.client.id,
                "case_worker_id": self.case_worker.id,
                "stage_id": self.stage_intake.id,
                "presenting_issue": "<p>Test issue</p>",
            }
        )

        # Should be active in intake stage
        case._compute_is_active()
        self.assertTrue(case.is_active, "Case should be active in open stage")

        # Move to closed stage
        case.stage_id = self.stage_closed

        # Should not be active in closed stage
        case._compute_is_active()
        self.assertFalse(case.is_active, "Case should not be active in closed stage")
