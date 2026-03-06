"""Test cases for security rules in spp_case_base."""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCaseSecurity(TransactionCase):
    """Test security rules for case management."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for all test methods."""
        super().setUpClass()

        # Create test users with different roles (include base.group_user for internal user access)
        cls.worker1 = cls.env["res.users"].create(
            {
                "name": "Case Worker 1",
                "login": "worker1",
                "email": "worker1@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

        cls.worker2 = cls.env["res.users"].create(
            {
                "name": "Case Worker 2",
                "login": "worker2",
                "email": "worker2@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_worker").id),
                ],
            }
        )

        cls.supervisor = cls.env["res.users"].create(
            {
                "name": "Supervisor",
                "login": "supervisor",
                "email": "supervisor@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_supervisor").id),
                ],
            }
        )

        cls.manager = cls.env["res.users"].create(
            {
                "name": "Manager",
                "login": "manager",
                "email": "manager@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_case_base.group_case_manager").id),
                ],
            }
        )

        # Create test clients
        cls.client1 = cls.env["res.partner"].create(
            {
                "name": "Client 1",
                "email": "client1@test.com",
            }
        )

        cls.client2 = cls.env["res.partner"].create(
            {
                "name": "Client 2",
                "email": "client2@test.com",
            }
        )

        cls.client3 = cls.env["res.partner"].create(
            {
                "name": "Client 3",
                "email": "client3@test.com",
            }
        )

        # Create case type
        cls.case_type = cls.env["spp.case.type"].create(
            {
                "name": "Social Protection Security",
                "code": "SPS001",
                "domain": "social_protection",
            }
        )

        # Create team
        cls.team = cls.env["spp.case.team"].create(
            {
                "name": "Test Team",
                "supervisor_id": cls.supervisor.id,
                "member_ids": [Command.set([cls.worker1.id, cls.worker2.id])],
            }
        )

        # Create cases with different assignments
        # Worker 1's own case
        cls.case_worker1 = (
            cls.env["spp.case"]
            .with_user(cls.worker1)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client1.id,
                    "case_worker_id": cls.worker1.id,
                    "presenting_issue": "<p>Worker 1's case</p>",
                }
            )
        )

        # Worker 2's own case
        cls.case_worker2 = (
            cls.env["spp.case"]
            .with_user(cls.worker2)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client2.id,
                    "case_worker_id": cls.worker2.id,
                    "presenting_issue": "<p>Worker 2's case</p>",
                }
            )
        )

        # Supervisor's case (in team)
        cls.case_supervisor = (
            cls.env["spp.case"]
            .with_user(cls.supervisor)
            .create(
                {
                    "case_type_id": cls.case_type.id,
                    "partner_id": cls.client3.id,
                    "case_worker_id": cls.worker1.id,
                    "supervisor_id": cls.supervisor.id,
                    "team_id": cls.team.id,
                    "presenting_issue": "<p>Supervisor's case</p>",
                }
            )
        )

    def test_worker_access_own_cases(self):
        """Test that workers can only see their own cases."""
        # Worker 1 should see only their own case
        cases = self.env["spp.case"].with_user(self.worker1).search([])

        # Should see case_worker1 and case_supervisor (both assigned to worker1)
        self.assertIn(
            self.case_worker1,
            cases,
            "Worker 1 should see their own case",
        )
        self.assertIn(
            self.case_supervisor,
            cases,
            "Worker 1 should see case assigned to them",
        )
        self.assertNotIn(
            self.case_worker2,
            cases,
            "Worker 1 should not see Worker 2's case",
        )

        # Worker 2 should see only their own case
        cases = self.env["spp.case"].with_user(self.worker2).search([])

        self.assertIn(
            self.case_worker2,
            cases,
            "Worker 2 should see their own case",
        )
        self.assertNotIn(
            self.case_worker1,
            cases,
            "Worker 2 should not see Worker 1's case",
        )
        self.assertNotIn(
            self.case_supervisor,
            cases,
            "Worker 2 should not see supervisor's case",
        )

    def test_supervisor_access_team_cases(self):
        """Test that supervisors can see team cases."""
        # Supervisor should see cases they supervise and team cases
        cases = self.env["spp.case"].with_user(self.supervisor).search([])

        # Should see case_supervisor (supervised by them)
        self.assertIn(
            self.case_supervisor,
            cases,
            "Supervisor should see cases they supervise",
        )

        # Count should include supervised cases
        self.assertGreaterEqual(
            len(cases),
            1,
            "Supervisor should see at least supervised cases",
        )

    def test_manager_access_all_cases(self):
        """Test that managers can see all cases."""
        # Manager should see all cases
        cases = self.env["spp.case"].with_user(self.manager).search([])

        self.assertIn(
            self.case_worker1,
            cases,
            "Manager should see Worker 1's case",
        )
        self.assertIn(
            self.case_worker2,
            cases,
            "Manager should see Worker 2's case",
        )
        self.assertIn(
            self.case_supervisor,
            cases,
            "Manager should see Supervisor's case",
        )

        # Should see all 3 cases
        self.assertGreaterEqual(
            len(cases),
            3,
            "Manager should see all cases",
        )

    def test_worker_create_case(self):
        """Test that workers can create cases assigned to themselves."""
        new_client = self.env["res.partner"].create(
            {
                "name": "New Client",
                "email": "newclient@test.com",
            }
        )

        # Worker should be able to create their own case
        new_case = (
            self.env["spp.case"]
            .with_user(self.worker1)
            .create(
                {
                    "case_type_id": self.case_type.id,
                    "partner_id": new_client.id,
                    "case_worker_id": self.worker1.id,
                    "presenting_issue": "<p>New case</p>",
                }
            )
        )

        self.assertTrue(new_case, "Worker should be able to create case")
        self.assertEqual(
            new_case.case_worker_id,
            self.worker1,
            "Case should be assigned to worker",
        )

    def test_worker_write_own_case(self):
        """Test that workers can modify their own cases."""
        # Worker 1 should be able to modify their own case
        self.case_worker1.with_user(self.worker1).write(
            {
                "priority": "high",
            }
        )

        self.assertEqual(
            self.case_worker1.priority,
            "high",
            "Worker should be able to modify their own case",
        )

    def test_intervention_plan_security(self):
        """Test security rules for intervention plans."""
        # Create plan for Worker 1's case
        plan1 = (
            self.env["spp.case.intervention.plan"]
            .with_user(self.worker1)
            .create(
                {
                    "case_id": self.case_worker1.id,
                    "name": "Worker 1 Plan",
                    "goals": "<p>Test goals</p>",
                }
            )
        )

        # Worker 1 should see their own plan
        plans = self.env["spp.case.intervention.plan"].with_user(self.worker1).search([])
        self.assertIn(plan1, plans, "Worker should see their own case plan")

        # Create plan for Worker 2's case
        plan2 = (
            self.env["spp.case.intervention.plan"]
            .with_user(self.worker2)
            .create(
                {
                    "case_id": self.case_worker2.id,
                    "name": "Worker 2 Plan",
                    "goals": "<p>Test goals</p>",
                }
            )
        )

        # Worker 1 should NOT see Worker 2's plan
        plans = self.env["spp.case.intervention.plan"].with_user(self.worker1).search([])
        self.assertNotIn(
            plan2,
            plans,
            "Worker should not see other worker's case plan",
        )

        # Manager should see all plans
        plans = self.env["spp.case.intervention.plan"].with_user(self.manager).search([])
        self.assertIn(plan1, plans, "Manager should see all plans")
        self.assertIn(plan2, plans, "Manager should see all plans")

    def test_intervention_security(self):
        """Test security rules for interventions."""
        # Create plan and intervention for Worker 1
        plan1 = (
            self.env["spp.case.intervention.plan"]
            .with_user(self.worker1)
            .create(
                {
                    "case_id": self.case_worker1.id,
                    "name": "Plan 1",
                    "goals": "<p>Goals 1</p>",
                }
            )
        )

        intervention1 = (
            self.env["spp.case.intervention"]
            .with_user(self.worker1)
            .create(
                {
                    "name": "Intervention 1",
                    "plan_id": plan1.id,
                }
            )
        )

        # Worker 1 should see their own intervention
        interventions = self.env["spp.case.intervention"].with_user(self.worker1).search([])
        self.assertIn(
            intervention1,
            interventions,
            "Worker should see their own case intervention",
        )

        # Create plan and intervention for Worker 2
        plan2 = (
            self.env["spp.case.intervention.plan"]
            .with_user(self.worker2)
            .create(
                {
                    "case_id": self.case_worker2.id,
                    "name": "Plan 2",
                    "goals": "<p>Goals 2</p>",
                }
            )
        )

        intervention2 = (
            self.env["spp.case.intervention"]
            .with_user(self.worker2)
            .create(
                {
                    "name": "Intervention 2",
                    "plan_id": plan2.id,
                }
            )
        )

        # Worker 1 should NOT see Worker 2's intervention
        interventions = self.env["spp.case.intervention"].with_user(self.worker1).search([])
        self.assertNotIn(
            intervention2,
            interventions,
            "Worker should not see other worker's intervention",
        )

        # Manager should see all interventions
        interventions = self.env["spp.case.intervention"].with_user(self.manager).search([])
        self.assertIn(
            intervention1,
            interventions,
            "Manager should see all interventions",
        )
        self.assertIn(
            intervention2,
            interventions,
            "Manager should see all interventions",
        )

    def test_supervisor_approve_team_plans(self):
        """Test that supervisors can approve team plans."""
        # Create plan for case supervised by supervisor
        plan = (
            self.env["spp.case.intervention.plan"]
            .with_user(self.worker1)
            .create(
                {
                    "case_id": self.case_supervisor.id,
                    "name": "Team Plan",
                    "goals": "<p>Team goals</p>",
                }
            )
        )

        # Add intervention so it can be submitted
        self.env["spp.case.intervention"].with_user(self.worker1).create(
            {
                "name": "Team Intervention",
                "plan_id": plan.id,
            }
        )

        # Submit for approval
        plan.with_user(self.worker1).action_submit_for_approval()

        # Supervisor should be able to approve
        plan.with_user(self.supervisor).action_approve()

        self.assertEqual(
            plan.state,
            "approved",
            "Supervisor should be able to approve team plan",
        )
        self.assertEqual(
            plan.approved_by_id,
            self.supervisor,
            "Supervisor should be recorded as approver",
        )

    def test_group_hierarchy(self):
        """Test that group hierarchy is correct."""
        # Supervisor should have worker permissions (through implied groups)
        self.assertIn(
            self.env.ref("spp_case_base.group_case_worker"),
            self.supervisor.all_group_ids,
            "Supervisor should have worker permissions",
        )

        # Manager should have supervisor permissions (through implied groups)
        self.assertIn(
            self.env.ref("spp_case_base.group_case_supervisor"),
            self.manager.all_group_ids,
            "Manager should have supervisor permissions",
        )

        # Manager should have worker permissions (through hierarchy)
        self.assertIn(
            self.env.ref("spp_case_base.group_case_worker"),
            self.manager.all_group_ids,
            "Manager should have worker permissions through hierarchy",
        )
