# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestSimulationScenario(SimulationTestCommon):
    """Tests for spp.simulation.scenario model."""

    def test_create_scenario(self):
        """Test basic scenario creation."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "New Scenario",
                "target_type": "group",
                "targeting_expression": "true",
            }
        )
        self.assertEqual(scenario.state, "draft")
        self.assertEqual(scenario.target_type, "group")
        self.assertEqual(scenario.budget_strategy, "none")

    def test_state_transitions(self):
        """Test scenario state machine transitions."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "State Test",
                "target_type": "group",
                "targeting_expression": "true",
            }
        )
        self.assertEqual(scenario.state, "draft")

        # Draft -> Ready
        scenario.action_set_ready()
        self.assertEqual(scenario.state, "ready")

        # Ready -> Draft
        scenario.action_set_draft()
        self.assertEqual(scenario.state, "draft")

        # Draft -> Ready -> Archived
        scenario.action_set_ready()
        scenario.action_archive()
        self.assertEqual(scenario.state, "archived")

    def test_cannot_set_ready_without_expression(self):
        """Test that scenario cannot be marked ready without a targeting expression."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "No Expression",
                "target_type": "group",
                "targeting_expression": False,
            }
        )
        with self.assertRaises(ValidationError):
            scenario.action_set_ready()

    def test_cannot_run_draft_scenario(self):
        """Test that draft scenarios cannot be run."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Draft Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "draft",
            }
        )
        with self.assertRaises(UserError):
            scenario.action_run_simulation()

    def test_run_count_computed(self):
        """Test that run_count is correctly computed."""
        self.assertEqual(self.scenario.run_count, 0)

    def test_duplicate_for_comparison(self):
        """Test duplicating a scenario for comparison."""
        result = self.scenario.action_duplicate_for_comparison()
        new_scenario_id = result["res_id"]
        new_scenario = self.env["spp.simulation.scenario"].browse(new_scenario_id)
        self.assertIn("Comparison", new_scenario.name)
        self.assertEqual(new_scenario.state, "draft")
        self.assertEqual(new_scenario.targeting_expression, self.scenario.targeting_expression)

    def test_create_from_template(self):
        """Test creating a scenario from a template."""
        result = self.env["spp.simulation.scenario"].action_create_from_template(self.template.id)
        scenario_id = result["res_id"]
        scenario = self.env["spp.simulation.scenario"].browse(scenario_id)
        self.assertEqual(scenario.name, self.template.name)
        self.assertEqual(scenario.target_type, self.template.target_type)
        self.assertEqual(scenario.targeting_expression, self.template.targeting_expression)
        self.assertEqual(scenario.template_id, self.template)
        # Check that entitlement rule was created
        self.assertEqual(len(scenario.entitlement_rule_ids), 1)
        self.assertEqual(scenario.entitlement_rule_ids.amount, 500.0)

    def test_create_from_invalid_template(self):
        """Test creating from a non-existent template raises error."""
        with self.assertRaises(UserError):
            self.env["spp.simulation.scenario"].action_create_from_template(99999)

    def test_view_runs_action(self):
        """Test the view runs action returns correct domain."""
        result = self.scenario.action_view_runs()
        self.assertEqual(result["res_model"], "spp.simulation.run")
        self.assertIn(("scenario_id", "=", self.scenario.id), result["domain"])
