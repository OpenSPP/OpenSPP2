"""Test cases for spp.case.intervention model."""

from datetime import date, timedelta

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseIntervention(TransactionCase):
    """Test the intervention model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()

        # Create test users (include base.group_user for internal user access)
        cls.case_worker = cls.env["res.users"].create(
            {
                "name": "Test Case Worker",
                "login": "test_worker_intervention",
                "email": "worker_intervention@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

        # Create test partner (client)
        cls.client = cls.env["res.partner"].create(
            {
                "name": "Test Client Intervention",
                "email": "client_intervention@test.com",
            }
        )

        # Create service provider
        cls.provider = cls.env["res.partner"].create(
            {
                "name": "Service Provider",
                "email": "provider@test.com",
            }
        )

        # Create case type
        cls.case_type = cls.env["spp.case.type"].create(
            {
                "name": "Social Protection Intervention",
                "code": "SPI001",
                "domain": "social_protection",
            }
        )

        # Create test case
        cls.case = cls.env["spp.case"].create(
            {
                "case_type_id": cls.case_type.id,
                "partner_id": cls.client.id,
                "case_worker_id": cls.case_worker.id,
                "presenting_issue": "<p>Client needs assistance</p>",
            }
        )

        # Create test plan
        cls.plan = cls.env["spp.case.intervention.plan"].create(
            {
                "name": "Test Plan",
                "case_id": cls.case.id,
                "goals": "<p>Help client achieve goals</p>",
            }
        )

    def test_create_intervention(self):
        """Test creating an intervention and verify defaults."""
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Job Training",
                "plan_id": self.plan.id,
                "description": "Enroll client in job training program",
                "target_outcome": "Client completes job training",
            }
        )

        self.assertEqual(intervention.state, "planned", "New intervention should be in planned state")
        self.assertEqual(
            intervention.responsible,
            "joint",
            "Default responsible party should be joint",
        )
        self.assertEqual(
            intervention.case_id,
            self.case,
            "Case should be related through plan",
        )
        self.assertEqual(intervention.sequence, 10, "Default sequence should be 10")

    def test_intervention_completion(self):
        """Test intervention completion workflow."""
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Test Intervention",
                "plan_id": self.plan.id,
                "state": "planned",
            }
        )

        # Start the intervention
        intervention.action_start()
        self.assertEqual(
            intervention.state,
            "in_progress",
            "Intervention should be in progress after start",
        )

        # Complete the intervention
        intervention.action_complete()
        self.assertEqual(
            intervention.state,
            "completed",
            "Intervention should be completed",
        )
        self.assertEqual(
            intervention.completed_date,
            date.today(),
            "Completed date should be today",
        )

    def test_intervention_not_completed(self):
        """Test marking intervention as not completed."""
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Test Intervention",
                "plan_id": self.plan.id,
                "state": "in_progress",
            }
        )

        # Mark as not completed
        intervention.action_mark_not_completed()
        self.assertEqual(
            intervention.state,
            "not_completed",
            "Intervention should be marked as not completed",
        )

    def test_intervention_cancel(self):
        """Test cancelling an intervention."""
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Test Intervention",
                "plan_id": self.plan.id,
                "state": "planned",
            }
        )

        # Cancel the intervention
        intervention.action_cancel()
        self.assertEqual(intervention.state, "cancelled", "Intervention should be cancelled")

    def test_intervention_reset(self):
        """Test resetting an intervention back to planned."""
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Test Intervention",
                "plan_id": self.plan.id,
                "state": "completed",
                "completed_date": date.today(),
            }
        )

        # Reset the intervention
        intervention.action_reset()
        self.assertEqual(intervention.state, "planned", "Intervention should be reset to planned")
        self.assertFalse(
            intervention.completed_date,
            "Completed date should be cleared",
        )

    def test_case_id_related_field(self):
        """Test that case_id is properly related through plan."""
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Test Intervention",
                "plan_id": self.plan.id,
            }
        )

        # Verify case is accessible through related field
        self.assertEqual(
            intervention.case_id,
            self.case,
            "Case should be accessible through plan",
        )
        self.assertEqual(
            intervention.case_id.partner_id,
            self.client,
            "Should be able to access case fields through related field",
        )

    def test_is_overdue_computation(self):
        """Test is_overdue computed field."""
        # Create intervention with past target date
        past_date = date.today() - timedelta(days=5)
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Overdue Intervention",
                "plan_id": self.plan.id,
                "target_date": past_date,
                "state": "in_progress",
            }
        )

        # Compute is_overdue
        intervention._compute_is_overdue()
        self.assertTrue(
            intervention.is_overdue,
            "Intervention with past target date should be overdue",
        )

        # Create intervention with future target date
        future_date = date.today() + timedelta(days=5)
        intervention2 = self.env["spp.case.intervention"].create(
            {
                "name": "Future Intervention",
                "plan_id": self.plan.id,
                "target_date": future_date,
                "state": "planned",
            }
        )

        intervention2._compute_is_overdue()
        self.assertFalse(
            intervention2.is_overdue,
            "Intervention with future target date should not be overdue",
        )

        # Completed interventions should not be overdue
        intervention3 = self.env["spp.case.intervention"].create(
            {
                "name": "Completed Intervention",
                "plan_id": self.plan.id,
                "target_date": past_date,
                "state": "completed",
            }
        )

        intervention3._compute_is_overdue()
        self.assertFalse(
            intervention3.is_overdue,
            "Completed intervention should not be overdue",
        )

    def test_days_until_due_computation(self):
        """Test days_until_due computed field."""
        # Create intervention due in 10 days
        future_date = date.today() + timedelta(days=10)
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "Future Intervention",
                "plan_id": self.plan.id,
                "target_date": future_date,
            }
        )

        intervention._compute_days_until_due()
        self.assertEqual(
            intervention.days_until_due,
            10,
            "Should show 10 days until due",
        )

        # Create intervention that was due 5 days ago
        past_date = date.today() - timedelta(days=5)
        intervention2 = self.env["spp.case.intervention"].create(
            {
                "name": "Past Intervention",
                "plan_id": self.plan.id,
                "target_date": past_date,
            }
        )

        intervention2._compute_days_until_due()
        self.assertEqual(
            intervention2.days_until_due,
            -5,
            "Should show -5 days (overdue by 5 days)",
        )

    def test_responsible_party_types(self):
        """Test different responsible party types."""
        # Client responsible
        intervention1 = self.env["spp.case.intervention"].create(
            {
                "name": "Client Task",
                "plan_id": self.plan.id,
                "responsible": "client",
            }
        )
        self.assertEqual(intervention1.responsible, "client")

        # Worker responsible
        intervention2 = self.env["spp.case.intervention"].create(
            {
                "name": "Worker Task",
                "plan_id": self.plan.id,
                "responsible": "worker",
            }
        )
        self.assertEqual(intervention2.responsible, "worker")

        # Provider responsible
        intervention3 = self.env["spp.case.intervention"].create(
            {
                "name": "Provider Task",
                "plan_id": self.plan.id,
                "responsible": "provider",
                "provider_id": self.provider.id,
            }
        )
        self.assertEqual(intervention3.responsible, "provider")
        self.assertEqual(intervention3.provider_id, self.provider)

    def test_onchange_responsible(self):
        """Test that provider is cleared when responsible changes."""
        intervention = self.env["spp.case.intervention"].new(
            {
                "name": "Test Intervention",
                "plan_id": self.plan.id,
                "responsible": "provider",
                "provider_id": self.provider.id,
            }
        )

        # Change responsible to non-provider
        intervention.responsible = "worker"
        intervention._onchange_responsible()

        self.assertFalse(
            intervention.provider_id,
            "Provider should be cleared when responsible changes",
        )

    def test_intervention_sequence_ordering(self):
        """Test that interventions are ordered by sequence."""
        # Create interventions with different sequences
        intervention1 = self.env["spp.case.intervention"].create(
            {
                "name": "Third",
                "plan_id": self.plan.id,
                "sequence": 30,
            }
        )

        intervention2 = self.env["spp.case.intervention"].create(
            {
                "name": "First",
                "plan_id": self.plan.id,
                "sequence": 10,
            }
        )

        intervention3 = self.env["spp.case.intervention"].create(
            {
                "name": "Second",
                "plan_id": self.plan.id,
                "sequence": 20,
            }
        )

        # Search interventions for this plan
        interventions = self.env["spp.case.intervention"].search([("plan_id", "=", self.plan.id)])

        # Verify order
        self.assertEqual(interventions[0], intervention2, "First should be sequence 10")
        self.assertEqual(interventions[1], intervention3, "Second should be sequence 20")
        self.assertEqual(interventions[2], intervention1, "Third should be sequence 30")

    def test_intervention_without_target_date(self):
        """Test intervention without target date."""
        intervention = self.env["spp.case.intervention"].create(
            {
                "name": "No Date Intervention",
                "plan_id": self.plan.id,
            }
        )

        intervention._compute_is_overdue()
        intervention._compute_days_until_due()

        self.assertFalse(
            intervention.is_overdue,
            "Intervention without target date should not be overdue",
        )
        self.assertEqual(
            intervention.days_until_due,
            0,
            "Intervention without target date should show 0 days",
        )

    def test_multiple_interventions_progress(self):
        """Test that multiple interventions affect plan progress correctly."""
        # Create multiple interventions
        interventions = []
        for i in range(5):
            intervention = self.env["spp.case.intervention"].create(
                {
                    "name": f"Intervention {i+1}",
                    "plan_id": self.plan.id,
                    "state": "planned",
                    "sequence": (i + 1) * 10,
                }
            )
            interventions.append(intervention)

        # Verify all are planned
        for intervention in interventions:
            self.assertEqual(intervention.state, "planned")

        # Complete some interventions
        interventions[0].action_complete()
        interventions[1].action_complete()

        # Verify states
        self.assertEqual(interventions[0].state, "completed")
        self.assertEqual(interventions[1].state, "completed")
        self.assertEqual(interventions[2].state, "planned")

        # Check plan progress
        self.plan._compute_progress()
        self.assertEqual(
            self.plan.progress_percentage,
            40.0,
            "Plan should be 40% complete (2 of 5)",
        )
