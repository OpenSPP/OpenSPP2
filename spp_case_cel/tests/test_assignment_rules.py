# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests.common import TransactionCase


class TestAssignmentRules(TransactionCase):
    """Test Case assignment rules with CEL expressions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AssignmentRule = cls.env["spp.case.assignment.rule"]
        cls.Case = cls.env["spp.case"]
        cls.CaseType = cls.env["spp.case.type"]
        cls.Team = cls.env["spp.case.team"]
        cls.Partner = cls.env["res.partner"]
        cls.User = cls.env["res.users"]

        # Create test case type
        cls.case_type = cls.CaseType.create(
            {
                "name": "General Support",
                "code": "GEN",
            }
        )

        # Create test users (case workers)
        cls.worker1 = cls.User.create(
            {
                "name": "Worker One",
                "login": "worker_one_test",
                "email": "worker1@test.com",
            }
        )
        cls.worker2 = cls.User.create(
            {
                "name": "Worker Two",
                "login": "worker_two_test",
                "email": "worker2@test.com",
            }
        )
        cls.worker3 = cls.User.create(
            {
                "name": "Worker Three",
                "login": "worker_three_test",
                "email": "worker3@test.com",
            }
        )
        cls.supervisor = cls.User.create(
            {
                "name": "Supervisor",
                "login": "supervisor_test",
                "email": "supervisor@test.com",
            }
        )

        # Create test teams
        cls.team1 = cls.Team.create(
            {
                "name": "Alpha Team",
                "member_ids": [Command.set([cls.worker1.id, cls.worker2.id])],
            }
        )
        cls.team2 = cls.Team.create(
            {
                "name": "Beta Team",
                "member_ids": [Command.set([cls.worker3.id])],
            }
        )

        # Create test partner (client)
        cls.partner = cls.Partner.create(
            {
                "name": "Test Client",
            }
        )

        # Get an admin user as default case worker for setup
        cls.admin_user = cls.env.ref("base.user_admin")

    def _create_case(self, **kwargs):
        """Helper to create a case with default values."""
        defaults = {
            "case_type_id": self.case_type.id,
            "partner_id": self.partner.id,
            "case_worker_id": self.admin_user.id,
            "presenting_issue": "<p>Test presenting issue</p>",
            "intensity_level": "2",
            "priority": "medium",
            "intake_source": "walk_in",
            "client_type": "individual",
        }
        defaults.update(kwargs)
        return self.Case.create(defaults)

    # =====================================================
    # UNIT TESTS - Test individual components
    # =====================================================

    def test_assignment_rule_creation(self):
        """Test assignment rule can be created with proper defaults."""
        rule = self.AssignmentRule.create(
            {
                "name": "Assign High Intensity to Team",
                "condition_cel": "intensity == '3'",
                "assign_team_id": self.team1.id,
            }
        )
        self.assertTrue(rule.active)
        self.assertEqual(rule.match_count, 0)
        self.assertEqual(rule.sequence, 10)
        self.assertEqual(rule.max_cases_per_worker, 25)  # Default value

    def test_expression_evaluation_with_operators(self):
        """Test CEL expression evaluation with AND/OR operators."""
        rule = self.AssignmentRule.create(
            {
                "name": "Test Expression",
                "condition_cel": "",
            }
        )

        # Test AND (and)
        context = {"intensity": "3", "priority": "urgent"}
        result = rule._evaluate_expression("intensity == '3' and priority == 'urgent'", context)
        self.assertTrue(result)

        # Test failure case
        context = {"intensity": "3", "priority": "low"}
        result = rule._evaluate_expression("intensity == '3' and priority == 'urgent'", context)
        self.assertFalse(result)

        # Test OR (or)
        context = {"intensity": "1", "priority": "urgent"}
        result = rule._evaluate_expression("intensity == '3' or priority == 'urgent'", context)
        self.assertTrue(result)

    # =====================================================
    # INTEGRATION TESTS - Verify assignment actually works
    # =====================================================

    def test_apply_assignment_sets_team(self):
        """Test apply_assignment() actually assigns team to case."""
        rule = self.AssignmentRule.create(
            {
                "name": "Assign High Intensity to Alpha Team",
                "condition_cel": "intensity == '3'",
                "assign_team_id": self.team1.id,
            }
        )

        case = self._create_case(intensity_level="3")
        self.assertFalse(case.team_id)

        # Apply assignment
        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result, "apply_assignment should return True when rule matches")
        self.assertEqual(case.team_id, self.team1, "Case should be assigned to team1")
        self.assertEqual(rule.match_count, 1, "Rule match_count should increment")

    def test_apply_assignment_sets_worker(self):
        """Test apply_assignment() can directly assign a specific worker."""
        self.AssignmentRule.create(
            {
                "name": "Assign Urgent to Worker1",
                "condition_cel": "priority == 'urgent'",
                "assign_worker_id": self.worker1.id,
            }
        )

        case = self._create_case(priority="urgent")

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        self.assertEqual(case.case_worker_id, self.worker1, "Case should be assigned to worker1")

    def test_apply_assignment_sets_supervisor(self):
        """Test apply_assignment() can assign a supervisor."""
        self.AssignmentRule.create(
            {
                "name": "Assign Supervisor for High Intensity",
                "condition_cel": "intensity == '3'",
                "assign_supervisor_id": self.supervisor.id,
            }
        )

        case = self._create_case(intensity_level="3")
        self.assertFalse(case.supervisor_id)

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        self.assertEqual(case.supervisor_id, self.supervisor, "Supervisor should be assigned")

    def test_apply_assignment_sets_multiple(self):
        """Test apply_assignment() can set team, worker, and supervisor together."""
        self.AssignmentRule.create(
            {
                "name": "Full Assignment",
                "condition_cel": "priority == 'urgent' and intensity == '3'",
                "assign_team_id": self.team1.id,
                "assign_worker_id": self.worker1.id,
                "assign_supervisor_id": self.supervisor.id,
            }
        )

        case = self._create_case(priority="urgent", intensity_level="3")

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        self.assertEqual(case.team_id, self.team1)
        self.assertEqual(case.case_worker_id, self.worker1)
        self.assertEqual(case.supervisor_id, self.supervisor)

    def test_apply_assignment_no_match(self):
        """Test apply_assignment() returns False when no rules match."""
        rule = self.AssignmentRule.create(
            {
                "name": "High Intensity Only",
                "condition_cel": "intensity == '3'",
                "assign_team_id": self.team1.id,
            }
        )

        # Create a low intensity case
        case = self._create_case(intensity_level="1")

        result = self.AssignmentRule.apply_assignment(case)

        self.assertFalse(result, "Should return False when no rules match")
        self.assertFalse(case.team_id, "Team should remain unassigned")
        self.assertEqual(rule.match_count, 0)

    def test_apply_assignment_first_match_wins(self):
        """Test that first matching rule (by sequence) is applied."""
        rule1 = self.AssignmentRule.create(
            {
                "name": "First Rule",
                "sequence": 10,
                "condition_cel": "",  # Always matches
                "assign_team_id": self.team1.id,
            }
        )
        rule2 = self.AssignmentRule.create(
            {
                "name": "Second Rule",
                "sequence": 20,
                "condition_cel": "",  # Would also match
                "assign_team_id": self.team2.id,
            }
        )

        case = self._create_case()

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        # First rule should win (lower sequence)
        self.assertEqual(case.team_id, self.team1, "First matching rule should be applied")
        self.assertEqual(rule1.match_count, 1)
        self.assertEqual(rule2.match_count, 0)

    def test_apply_assignment_inactive_rules_skipped(self):
        """Test that inactive assignment rules are not applied."""
        rule = self.AssignmentRule.create(
            {
                "name": "Inactive Rule",
                "active": False,
                "condition_cel": "",  # Would always match if active
                "assign_team_id": self.team1.id,
            }
        )

        case = self._create_case()

        result = self.AssignmentRule.apply_assignment(case)

        self.assertFalse(result)
        self.assertFalse(case.team_id)
        self.assertEqual(rule.match_count, 0)

    # =====================================================
    # WORKLOAD BALANCING TESTS
    # =====================================================

    def test_workload_balancing_assigns_to_least_busy(self):
        """Test that workload balancing assigns to worker with fewest cases."""
        # First, give worker1 some existing cases
        for i in range(3):
            self._create_case(
                case_worker_id=self.worker1.id,
                presenting_issue=f"<p>Existing case {i}</p>",
            )

        # worker2 has no cases
        self.AssignmentRule.create(
            {
                "name": "Balance Workload",
                "condition_cel": "",  # Always matches
                "assign_team_id": self.team1.id,
                "is_consider_workload": True,
                "max_cases_per_worker": 25,
            }
        )

        # Create new case to be assigned
        case = self._create_case()

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        self.assertEqual(case.team_id, self.team1)
        # worker2 should get the case since they have fewer cases than worker1
        self.assertEqual(case.case_worker_id, self.worker2, "Case should be assigned to worker with lowest caseload")

    def test_workload_balancing_respects_max_cases(self):
        """Test that workers at max capacity are skipped."""
        # Set max_cases_per_worker to 2 and give worker1 2 cases
        for i in range(2):
            self._create_case(
                case_worker_id=self.worker1.id,
                presenting_issue=f"<p>Worker1 case {i}</p>",
            )

        # Give worker2 1 case
        self._create_case(
            case_worker_id=self.worker2.id,
            presenting_issue="<p>Worker2 case</p>",
        )

        self.AssignmentRule.create(
            {
                "name": "Balance with Low Max",
                "condition_cel": "",
                "assign_team_id": self.team1.id,
                "is_consider_workload": True,
                "max_cases_per_worker": 2,  # Low limit
            }
        )

        case = self._create_case()

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        # worker1 is at capacity (2 cases), so worker2 should get it
        self.assertEqual(case.case_worker_id, self.worker2, "Worker at max capacity should be skipped")

    def test_workload_balancing_no_available_worker(self):
        """Test behavior when all workers are at max capacity."""
        # Create a team where we can control the member
        solo_team = self.Team.create(
            {
                "name": "Solo Team",
                "member_ids": [Command.set([self.worker3.id])],
            }
        )

        # Give worker3 cases up to max
        for i in range(3):
            self._create_case(
                case_worker_id=self.worker3.id,
                presenting_issue=f"<p>Worker3 case {i}</p>",
            )

        self.AssignmentRule.create(
            {
                "name": "Balance Solo Team",
                "condition_cel": "",
                "assign_team_id": solo_team.id,
                "is_consider_workload": True,
                "max_cases_per_worker": 3,  # worker3 is at max
            }
        )

        case = self._create_case()

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        # Team should still be assigned even if no worker available
        self.assertEqual(case.team_id, solo_team)
        # case_worker_id should remain unchanged (admin_user from _create_case)
        self.assertEqual(case.case_worker_id, self.admin_user)

    def test_workload_balancing_disabled_uses_direct_worker(self):
        """Test that without workload balancing, direct worker is assigned."""
        self.AssignmentRule.create(
            {
                "name": "Direct Assignment",
                "condition_cel": "",
                "assign_team_id": self.team1.id,
                "assign_worker_id": self.worker1.id,
                "is_consider_workload": False,  # Explicitly disabled
            }
        )

        case = self._create_case()

        result = self.AssignmentRule.apply_assignment(case)

        self.assertTrue(result)
        # Should use direct worker assignment, not workload balancing
        self.assertEqual(case.case_worker_id, self.worker1)

    # =====================================================
    # CONTEXT BUILDING TESTS
    # =====================================================

    def test_evaluate_builds_correct_context(self):
        """Test that evaluate() builds context with all expected variables."""
        rule = self.AssignmentRule.create(
            {
                "name": "Test Context",
                "condition_cel": "intensity == '3' and priority == 'urgent'",
            }
        )

        case = self._create_case(
            intensity_level="3",
            priority="urgent",
            intake_source="grm",
            client_type="household",
        )

        context = rule._build_evaluation_context(case)

        self.assertIn("case", context)
        self.assertIn("case_type", context)
        self.assertIn("intensity", context)
        self.assertIn("priority", context)
        self.assertIn("client", context)
        self.assertIn("client_type", context)
        self.assertIn("intake_source", context)
        self.assertEqual(context["intensity"], "3")
        self.assertEqual(context["priority"], "urgent")

        # Verify evaluate() works correctly
        result = rule.evaluate(case)
        self.assertTrue(result)

    def test_evaluate_returns_false_on_error(self):
        """Test that evaluate() returns False on expression errors."""
        rule = self.AssignmentRule.create(
            {
                "name": "Invalid Expression",
                "condition_cel": "invalid_syntax (((",
            }
        )

        case = self._create_case()

        # Should return False (not raise exception)
        result = rule.evaluate(case)
        self.assertFalse(result)
