"""Test cases for spp.case.intervention.plan model."""

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseInterventionPlan(TransactionCase):
    """Test the intervention plan model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()

        # Create test users (include base.group_user for internal user access)
        cls.case_worker = cls.env["res.users"].create(
            {
                "name": "Test Case Worker",
                "login": "test_worker_plan",
                "email": "worker_plan@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

        cls.supervisor = cls.env["res.users"].create(
            {
                "name": "Test Supervisor",
                "login": "test_supervisor_plan",
                "email": "supervisor_plan@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_supervisor").id),
                ],
            }
        )

        # Create test partner (client)
        cls.client = cls.env["res.partner"].create(
            {
                "name": "Test Client Plan",
                "email": "client_plan@test.com",
            }
        )

        # Create case type
        cls.case_type = cls.env["spp.case.type"].create(
            {
                "name": "Social Protection Plan",
                "code": "SPP001",
                "domain": "social_protection",
            }
        )

        # Create test case (with supervisor assigned for approval workflow tests)
        cls.case = cls.env["spp.case"].create(
            {
                "case_type_id": cls.case_type.id,
                "partner_id": cls.client.id,
                "case_worker_id": cls.case_worker.id,
                "supervisor_id": cls.supervisor.id,
                "presenting_issue": "<p>Client needs assistance</p>",
            }
        )

    def test_complete_clears_is_current(self):
        """Completing a plan ends its tenure as the case's current plan."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Plan To Complete",
                "case_id": self.case.id,
                "goals": "<p>Reach self-sufficiency</p>",
            }
        )
        self.assertTrue(plan.is_current, "New plan should start as current")
        self.assertEqual(
            self.case.current_plan_id,
            plan,
            "New plan should be the case's current plan",
        )

        plan.action_complete()

        self.assertEqual(plan.state, "completed", "Plan should be completed")
        self.assertFalse(
            plan.is_current,
            "Completed plan should no longer be marked current",
        )
        self.assertFalse(
            self.case.current_plan_id,
            "Case should have no current plan once the plan is completed",
        )

    def test_create_plan(self):
        """Test creating a plan and verify defaults."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Intervention Plan",
                "case_id": self.case.id,
                "goals": "<p>Help client achieve self-sufficiency</p>",
                "expected_outcomes": "<p>Client finds employment</p>",
            }
        )

        self.assertEqual(plan.state, "draft", "New plan should be in draft state")
        self.assertEqual(plan.version, 1, "New plan should be version 1")
        self.assertTrue(plan.is_current, "New plan should be marked as current")
        self.assertFalse(plan.approved_by_id, "Draft plan should not have approver")
        self.assertFalse(plan.approved_date, "Draft plan should not have approval date")

    def test_auto_name_generation(self):
        """Test that plan name is auto-generated if not provided."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
            }
        )

        self.assertTrue(plan.name, "Plan name should be generated")
        self.assertIn(self.case.name, plan.name, "Plan name should include case number")
        self.assertIn("Plan v1", plan.name, "Plan name should include version")

    def test_plan_versioning(self):
        """Test version creation."""
        # Create initial plan
        plan_v1 = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Initial Plan",
                "case_id": self.case.id,
                "goals": "<p>Version 1 goals</p>",
                "state": "approved",
            }
        )

        self.assertEqual(plan_v1.version, 1, "First plan should be version 1")
        self.assertTrue(plan_v1.is_current, "First plan should be current")

        # Create revision
        result = plan_v1.action_create_revision()

        # Get the new version
        plan_v2 = self.env["spp.case.intervention.plan"].browse(result["res_id"])

        self.assertEqual(plan_v2.version, 2, "New plan should be version 2")
        self.assertTrue(plan_v2.is_current, "New plan should be current")
        self.assertEqual(plan_v2.state, "draft", "New plan should be in draft state")
        self.assertEqual(
            plan_v2.previous_version_id,
            plan_v1,
            "New plan should reference previous version",
        )

        # Check that old plan is no longer current
        self.assertFalse(plan_v1.is_current, "Old plan should not be current")
        self.assertEqual(plan_v1.state, "revised", "Old plan should be revised")

    def test_plan_approval_workflow(self):
        """Test state transitions through approval workflow."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Plan",
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
            }
        )

        # Create intervention (required for submission)
        self.env["spp.case.intervention"].create(
            {
                "name": "Test Intervention",
                "plan_id": plan.id,
                "description": "Test intervention",
            }
        )

        # Test draft -> pending_approval
        self.assertEqual(plan.state, "draft")
        plan.action_submit_for_approval()
        self.assertEqual(
            plan.state,
            "pending_approval",
            "Plan should be pending approval after submission",
        )

        # Test pending_approval -> approved
        plan.with_user(self.supervisor).action_approve()
        self.assertEqual(plan.state, "approved", "Plan should be approved after approval action")
        self.assertEqual(
            plan.approved_by_id,
            self.supervisor,
            "Approver should be recorded",
        )
        self.assertTrue(plan.approved_date, "Approval date should be recorded")

        # Test approved -> active
        plan.action_activate()
        self.assertEqual(plan.state, "active", "Plan should be active after activation")

        # Test active -> completed
        plan.action_complete()
        self.assertEqual(plan.state, "completed", "Plan should be completed after completion action")
        self.assertTrue(plan.actual_end_date, "Completion date should be recorded")

    def test_submit_without_interventions(self):
        """Test that plan cannot be submitted without interventions."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Empty Plan",
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
            }
        )

        # Try to submit without interventions
        with self.assertRaises(
            ValidationError,
            msg="Should not allow submission without interventions",
        ):
            plan.action_submit_for_approval()

    def test_activate_without_approval(self):
        """Test that only approved plans can be activated."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Plan",
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
            }
        )

        # Try to activate draft plan
        with self.assertRaises(
            ValidationError,
            msg="Should not allow activation of non-approved plan",
        ):
            plan.action_activate()

    def test_reset_to_draft(self):
        """Test resetting plan back to draft."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Plan",
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
            }
        )

        # Create intervention and submit
        self.env["spp.case.intervention"].create(
            {
                "name": "Test Intervention",
                "plan_id": plan.id,
            }
        )

        plan.action_submit_for_approval()
        self.assertEqual(plan.state, "pending_approval")

        # Reset to draft
        plan.action_reset_to_draft()
        self.assertEqual(plan.state, "draft", "Plan should be reset to draft")

    def test_cannot_reset_completed_plan(self):
        """Test that completed plans cannot be reset to draft."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Plan",
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
                "state": "completed",
            }
        )

        # Try to reset completed plan
        with self.assertRaises(
            ValidationError,
            msg="Should not allow resetting completed plan",
        ):
            plan.action_reset_to_draft()

    def test_progress_computation(self):
        """Test progress percentage computation."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Plan",
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
            }
        )

        # Create 4 interventions
        interventions = []
        for i in range(4):
            intervention = self.env["spp.case.intervention"].create(
                {
                    "name": f"Intervention {i + 1}",
                    "plan_id": plan.id,
                    "state": "planned",
                }
            )
            interventions.append(intervention)

        # Initially 0% complete
        plan._compute_progress()
        self.assertEqual(plan.progress_percentage, 0.0, "Progress should be 0% initially")

        # Complete 2 interventions (50%)
        interventions[0].state = "completed"
        interventions[1].state = "completed"

        plan._compute_progress()
        self.assertEqual(plan.progress_percentage, 50.0, "Progress should be 50% with 2/4 complete")

        # Complete all interventions (100%)
        interventions[2].state = "completed"
        interventions[3].state = "completed"

        plan._compute_progress()
        self.assertEqual(
            plan.progress_percentage,
            100.0,
            "Progress should be 100% with all complete",
        )

    def test_intervention_count_computation(self):
        """Test intervention count computations."""
        plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Plan",
                "case_id": self.case.id,
                "goals": "<p>Test goals</p>",
            }
        )

        # Create interventions with different states
        self.env["spp.case.intervention"].create(
            {
                "name": "Intervention 1",
                "plan_id": plan.id,
                "state": "planned",
            }
        )

        self.env["spp.case.intervention"].create(
            {
                "name": "Intervention 2",
                "plan_id": plan.id,
                "state": "completed",
            }
        )

        self.env["spp.case.intervention"].create(
            {
                "name": "Intervention 3",
                "plan_id": plan.id,
                "state": "completed",
            }
        )

        # Compute counts
        plan._compute_intervention_count()

        self.assertEqual(plan.intervention_count, 3, "Should have 3 total interventions")
        self.assertEqual(
            plan.completed_intervention_count,
            2,
            "Should have 2 completed interventions",
        )

    def test_single_current_plan_constraint(self):
        """Test that only one plan can be current per case."""
        # Create first current plan
        self.env["spp.case.intervention.plan"].create(
            {
                "name": "Plan 1",
                "case_id": self.case.id,
                "goals": "<p>Goals 1</p>",
                "is_current": True,
            }
        )

        # Try to create second current plan
        with self.assertRaises(
            ValidationError,
            msg="Should not allow multiple current plans for same case",
        ):
            self.env["spp.case.intervention.plan"].create(
                {
                    "name": "Plan 2",
                    "case_id": self.case.id,
                    "goals": "<p>Goals 2</p>",
                    "is_current": True,
                }
            )

        # Create non-current plan (should work)
        plan2 = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Plan 2",
                "case_id": self.case.id,
                "goals": "<p>Goals 2</p>",
                "is_current": False,
            }
        )

        self.assertFalse(plan2.is_current, "Second plan should not be current")

    def test_plan_copy_behavior(self):
        """Test that plan copy creates new version with proper defaults."""
        original_plan = self.env["spp.case.intervention.plan"].create(
            {
                "name": "Original Plan",
                "case_id": self.case.id,
                "goals": "<p>Original goals</p>",
                "version": 5,
                "state": "approved",
                "approved_by_id": self.supervisor.id,
            }
        )

        # Use action_create_revision which uses copy internally
        result = original_plan.action_create_revision()
        new_plan = self.env["spp.case.intervention.plan"].browse(result["res_id"])

        # Check that new version has correct values
        self.assertEqual(new_plan.version, 6, "Version should be incremented")
        self.assertEqual(new_plan.state, "draft", "Copy should be in draft")
        self.assertFalse(new_plan.approved_by_id, "Copy should not have approver")
        self.assertFalse(new_plan.approved_date, "Copy should not have approval date")
        self.assertTrue(new_plan.is_current, "New version should be current")
        self.assertFalse(original_plan.is_current, "Old version should not be current")
