# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestSimulationService(SimulationTestCommon):
    """Tests for spp.simulation.service orchestration pipeline."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a group scenario with proper targeting expression
        cls.group_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Group Targeting Scenario",
                "target_type": "group",
                "targeting_expression": "household_size(r) >= 2",
                "state": "ready",
            }
        )
        cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.group_scenario.id,
                "amount_mode": "fixed",
                "amount": 1000.0,
            }
        )

        # Create an individual scenario
        cls.individual_scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Individual Targeting Scenario",
                "target_type": "individual",
                "targeting_expression": "age_years(r.birthdate) >= 18",
                "state": "ready",
            }
        )
        cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.individual_scenario.id,
                "amount_mode": "fixed",
                "amount": 500.0,
            }
        )

        # Create a simple scenario using existing data from common.py
        cls.simple_scenario = cls.scenario  # Use the one from common.py

    def test_execute_simulation_happy_path(self):
        """Test successful simulation execution with all metrics computed."""
        # Use simple scenario from common.py (targeting_expression="true")
        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run = service.execute_simulation(self.simple_scenario)

        self.assertEqual(
            run.state,
            "completed",
            "Simulation run should complete successfully",
        )
        self.assertGreater(
            run.beneficiary_count,
            0,
            "Beneficiary count should be greater than 0 with targeting_expression='true'",
        )
        self.assertGreater(
            run.total_registry_count,
            0,
            "Total registry count should be greater than 0",
        )
        # Verify coverage_rate is calculated correctly
        expected_coverage = (run.beneficiary_count / run.total_registry_count * 100) if run.total_registry_count else 0
        self.assertAlmostEqual(
            run.coverage_rate,
            expected_coverage,
            places=2,
            msg="Coverage rate should be correctly calculated as (beneficiary_count / total_registry_count * 100)",
        )
        self.assertGreater(
            run.total_cost,
            0,
            "Total cost should be greater than 0 because entitlement rule exists",
        )
        self.assertEqual(
            run.total_cost,
            run.beneficiary_count * 1000.0,
            "Total cost should be beneficiary_count * 1000.0 per beneficiary",
        )
        self.assertTrue(
            run.distribution_json,
            "Distribution JSON should be populated",
        )
        self.assertIn(
            "gini_coefficient",
            run.distribution_json,
            "Distribution JSON should contain gini_coefficient",
        )
        self.assertTrue(
            run.fairness_json,
            "Fairness JSON should be populated",
        )
        self.assertIn(
            "equity_score",
            run.fairness_json,
            "Fairness JSON should contain equity_score",
        )
        self.assertTrue(
            run.scenario_snapshot_json,
            "Scenario snapshot JSON should be populated",
        )
        self.assertEqual(
            run.scenario_snapshot_json.get("name"),
            self.simple_scenario.name,
            "Snapshot should capture scenario name",
        )
        self.assertEqual(
            run.scenario_snapshot_json.get("target_type"),
            "group",
            "Snapshot should capture target_type",
        )
        self.assertGreater(
            run.execution_duration_seconds,
            0,
            "Execution duration should be greater than 0",
        )
        self.assertTrue(
            run.executed_at,
            "Executed_at timestamp should be set",
        )

    def test_execute_simulation_error_handling(self):
        """Test simulation error handling with invalid targeting expression."""
        # Create a scenario with deliberately invalid expression
        error_scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Error Scenario",
                "target_type": "group",
                "targeting_expression": "invalid_function(x)",
                "state": "ready",
            }
        )

        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run = service.execute_simulation(error_scenario)

        self.assertEqual(
            run.state,
            "failed",
            "Simulation run should fail with invalid targeting expression",
        )
        self.assertTrue(
            run.error_message,
            "Error message should be populated on failed run",
        )
        self.assertGreater(
            run.execution_duration_seconds,
            0,
            "Execution duration should be recorded even on failure",
        )
        self.assertTrue(
            run.executed_at,
            "Executed_at timestamp should be set even on failure",
        )

    def test_archived_scenario_cannot_run(self):
        """Test that archived scenarios cannot be run."""
        # Archive the scenario
        self.simple_scenario.write({"state": "archived"})

        # Attempt to run via action_run_simulation
        with self.assertRaises(UserError, msg="Archived scenario should not be runnable") as exc_context:
            self.simple_scenario.with_user(self.user_officer).action_run_simulation()

        self.assertIn(
            "Ready",
            str(exc_context.exception),
            "Error message should mention 'Ready' state requirement",
        )

        # Restore state for other tests
        self.simple_scenario.write({"state": "ready"})

    def test_budget_strategy_cap_total(self):
        """Test budget_strategy='cap_total' limits total spending."""
        # Create scenario with budget less than full cost
        # 5 beneficiaries * 1000.0 = 5000.0 total
        # Budget: 3000.0 (should cap at 3 full beneficiaries)
        cap_scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Cap Total Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_strategy": "cap_total",
                "budget_amount": 3000.0,
                "state": "ready",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cap_scenario.id,
                "amount_mode": "fixed",
                "amount": 1000.0,
            }
        )

        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run = service.execute_simulation(cap_scenario)

        self.assertEqual(
            run.state,
            "completed",
            "Simulation should complete successfully",
        )
        self.assertLessEqual(
            run.total_cost,
            cap_scenario.budget_amount,
            "Total cost should not exceed budget amount with cap_total strategy",
        )
        self.assertEqual(
            run.total_cost,
            3000.0,
            "Total cost should equal budget (3 beneficiaries at full amount)",
        )
        self.assertGreater(
            run.budget_utilization,
            90.0,
            "Budget utilization should be high (near 100%)",
        )

    def test_budget_strategy_proportional_reduction(self):
        """Test budget_strategy='proportional_reduction' scales down all amounts."""
        # Create scenario with proportional reduction
        # 5 beneficiaries * 1000.0 = 5000.0 total
        # Budget: 3000.0 (should reduce each by 60% to 600.0)
        proportional_scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Proportional Reduction Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_strategy": "proportional_reduction",
                "budget_amount": 3000.0,
                "state": "ready",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": proportional_scenario.id,
                "amount_mode": "fixed",
                "amount": 1000.0,
            }
        )

        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run = service.execute_simulation(proportional_scenario)

        self.assertEqual(
            run.state,
            "completed",
            "Simulation should complete successfully",
        )
        self.assertAlmostEqual(
            run.total_cost,
            proportional_scenario.budget_amount,
            delta=1.0,
            msg="Total cost should approximately equal budget amount with proportional reduction",
        )
        self.assertGreater(
            run.budget_utilization,
            99.0,
            "Budget utilization should be approximately 100%",
        )
        self.assertLessEqual(
            run.budget_utilization,
            100.0,
            "Budget utilization should not exceed 100%",
        )

    def test_budget_strategy_none(self):
        """Test budget_strategy='none' has no budget constraint."""
        # Use simple scenario which has budget_strategy="none" by default
        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run = service.execute_simulation(self.simple_scenario)

        self.assertEqual(
            run.state,
            "completed",
            "Simulation should complete successfully",
        )
        self.assertGreater(
            run.total_cost,
            0,
            "Total cost should be greater than 0",
        )
        self.assertEqual(
            run.budget_utilization,
            0.0,
            "Budget utilization should be 0 when no budget constraint is set",
        )

    def test_geographic_breakdown_populated(self):
        """Test that geographic breakdown is populated for registrants with area_id."""
        # Use simple scenario with group registrants (they have area_id from common.py)
        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run = service.execute_simulation(self.simple_scenario)

        self.assertEqual(
            run.state,
            "completed",
            "Simulation should complete successfully",
        )
        self.assertTrue(
            run.geographic_json,
            "Geographic JSON should be populated",
        )
        # The 5 group registrants from common.py have area_id set
        area_key = str(self.area.id)
        self.assertIn(
            area_key,
            run.geographic_json,
            "Geographic breakdown should include the test area",
        )
        area_data = run.geographic_json[area_key]
        self.assertGreater(
            area_data["count"],
            0,
            "Test area should have at least some beneficiaries",
        )
        self.assertGreater(
            area_data["amount"],
            0,
            "Test area should have total amount greater than 0",
        )
        self.assertGreater(
            area_data["coverage_rate"],
            0,
            "Test area coverage rate should be greater than 0",
        )
        self.assertIn(
            "name",
            area_data,
            "Geographic data should include area name",
        )
        # Verify all geographic data entries have the required fields
        for area_id, data in run.geographic_json.items():
            self.assertIn("name", data, f"Area {area_id} should have name")
            self.assertIn("count", data, f"Area {area_id} should have count")
            self.assertIn("amount", data, f"Area {area_id} should have amount")
            self.assertIn("coverage_rate", data, f"Area {area_id} should have coverage_rate")

    def test_scenario_snapshot_captured(self):
        """Test that scenario snapshot persists original config even after modification."""
        # Run simulation first
        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run = service.execute_simulation(self.simple_scenario)

        # Capture original snapshot values
        original_name = run.scenario_snapshot_json.get("name")
        original_targeting = run.scenario_snapshot_json.get("targeting_expression")

        # Modify the scenario
        self.simple_scenario.write(
            {
                "name": "Modified Scenario Name",
                "targeting_expression": "false",
            }
        )

        # Re-read the run to ensure fresh data
        run.invalidate_recordset()

        # Assert snapshot still reflects original config
        self.assertEqual(
            run.scenario_snapshot_json.get("name"),
            original_name,
            "Snapshot should preserve original scenario name",
        )
        self.assertEqual(
            run.scenario_snapshot_json.get("targeting_expression"),
            original_targeting,
            "Snapshot should preserve original targeting expression",
        )
        self.assertNotEqual(
            run.scenario_snapshot_json.get("name"),
            self.simple_scenario.name,
            "Snapshot should differ from modified scenario name",
        )

        # Restore scenario for other tests
        self.simple_scenario.write(
            {
                "name": "Test Scenario",
                "targeting_expression": "true",
            }
        )
