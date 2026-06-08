# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Supplemental coverage tests for spp_simulation module.

Covers gaps in:
- SimulationRun HTML computed fields (summary, distribution, metrics, efficiency)
- SimulationService error handling branches
- Budget strategy edge cases
- Comparison overlap edge cases
- Scenario state transitions and computed fields
"""

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("post_install", "-at_install")
class TestRunHTMLComputedFields(SimulationTestCommon):
    """Tests for SimulationRun HTML computed field branches."""

    def _create_completed_run(self, **kwargs):
        """Helper to create a completed run with given result fields."""
        vals = {
            "scenario_id": self.scenario.id,
            "state": "completed",
            "beneficiary_count": 5,
            "total_cost": 5000.0,
            "coverage_rate": 50.0,
            "gini_coefficient": 0.0,
        }
        vals.update(kwargs)
        return self.env["spp.simulation.run"].create(vals)

    def test_summary_html_not_completed(self):
        """Summary HTML is False when run is not completed."""
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "running",
            }
        )
        self.assertFalse(run.summary_html)

    def test_summary_html_with_equity_high(self):
        """Parity label is 'proportional' when equity >= 80."""
        run = self._create_completed_run(equity_score=85.0)
        self.assertIn("proportional", run.summary_html)

    def test_summary_html_with_equity_medium(self):
        """Parity label is 'some variation' when 60 <= equity < 80."""
        run = self._create_completed_run(equity_score=65.0)
        self.assertIn("some variation", run.summary_html)

    def test_summary_html_with_equity_low(self):
        """Parity label is 'significant variation' when equity < 60."""
        run = self._create_completed_run(equity_score=40.0)
        self.assertIn("significant variation", run.summary_html)

    def test_summary_html_with_budget_utilization(self):
        """Budget utilization is shown when scenario has budget_amount."""
        self.scenario.write({"budget_amount": 10000.0})
        run = self._create_completed_run(budget_utilization=50.0)
        self.assertIn("50.0", run.summary_html)

    def test_summary_html_individual_target(self):
        """Target type label shows 'individuals' for individual targeting."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Individual Scenario",
                "target_type": "individual",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        run = self._create_completed_run(scenario_id=scenario.id)
        self.assertIn("individuals", run.summary_html)

    def test_distribution_summary_html_not_completed(self):
        """Distribution summary HTML is False when not completed."""
        run = self.env["spp.simulation.run"].create({"scenario_id": self.scenario.id, "state": "running"})
        self.assertFalse(run.distribution_summary_html)

    def test_distribution_summary_right_skewed(self):
        """Skew classification detects right-skewed distribution."""
        run = self._create_completed_run(
            gini_coefficient=0.1,
            distribution_json={
                "mean": 1200.0,
                "median": 1000.0,
                "minimum": 500.0,
                "maximum": 2000.0,
            },
        )
        self.assertIn("right-skewed", run.distribution_summary_html)

    def test_distribution_summary_left_skewed(self):
        """Skew classification detects left-skewed distribution."""
        run = self._create_completed_run(
            gini_coefficient=0.1,
            distribution_json={
                "mean": 800.0,
                "median": 1000.0,
                "minimum": 500.0,
                "maximum": 2000.0,
            },
        )
        self.assertIn("left-skewed", run.distribution_summary_html)

    def test_distribution_summary_symmetric(self):
        """Skew classification detects symmetric distribution."""
        run = self._create_completed_run(
            gini_coefficient=0.1,
            distribution_json={
                "mean": 1000.0,
                "median": 1000.0,
                "minimum": 500.0,
                "maximum": 1500.0,
            },
        )
        self.assertIn("symmetric", run.distribution_summary_html)

    def test_distribution_summary_gini_labels(self):
        """Gini labels: nearly equal < 0.2, moderate < 0.4, unequal >= 0.4."""
        for gini, expected_label in [
            (0.1, "nearly equal"),
            (0.3, "moderately distributed"),
            (0.5, "unequally distributed"),
        ]:
            run = self._create_completed_run(
                gini_coefficient=gini,
                distribution_json={"mean": 1000.0, "median": 1000.0, "minimum": 500.0, "maximum": 1500.0},
            )
            self.assertIn(expected_label, run.distribution_summary_html)

    def test_distribution_details_html_no_data(self):
        """Details HTML is False when no distribution data."""
        run = self._create_completed_run(distribution_json=False)
        self.assertFalse(run.distribution_details_html)

    def test_distribution_details_html_with_data(self):
        """Details HTML renders tables with percentile data."""
        run = self._create_completed_run(
            distribution_json={
                "count": 10,
                "total": 10000.0,
                "minimum": 500.0,
                "maximum": 2000.0,
                "mean": 1000.0,
                "median": 950.0,
                "standard_deviation": 300.0,
                "percentiles": {"p10": 600.0, "p25": 750.0, "p50": 950.0, "p75": 1200.0, "p90": 1800.0},
            },
        )
        self.assertIn("Statistics", run.distribution_details_html)
        self.assertIn("Percentiles", run.distribution_details_html)

    def test_metric_results_html_no_data(self):
        """Metric results HTML is False when no metrics."""
        run = self._create_completed_run(metric_results_json=False)
        self.assertFalse(run.metric_results_html)

    def test_metric_results_html_value_fallback(self):
        """Metric HTML falls through value -> rate -> ratio keys."""
        run = self._create_completed_run(
            metric_results_json={
                "coverage_metric": {"type": "coverage", "rate": 75.5},
                "ratio_metric": {"type": "ratio", "ratio": 0.85},
                "aggregate_metric": {"type": "aggregate", "value": 42},
            },
        )
        html = run.metric_results_html
        self.assertIn("75.5%", html)
        self.assertIn("0.85", html)
        self.assertIn("42", html)

    def test_targeting_efficiency_html_no_data(self):
        """Targeting efficiency HTML is False when no data."""
        run = self._create_completed_run(targeting_efficiency_json=False)
        self.assertFalse(run.targeting_efficiency_html)

    def test_targeting_efficiency_html_error_state(self):
        """Targeting efficiency with error key shows muted message."""
        run = self._create_completed_run(
            targeting_efficiency_json={"error": "no ideal expression"},
        )
        self.assertIn("text-muted", run.targeting_efficiency_html)

    def test_targeting_efficiency_html_with_data(self):
        """Targeting efficiency with valid data renders confusion matrix."""
        run = self._create_completed_run(
            targeting_efficiency_json={
                "true_positives": 10,
                "false_positives": 2,
                "false_negatives": 3,
                "total_simulated": 12,
                "total_ideal": 13,
            },
        )
        html = run.targeting_efficiency_html
        self.assertIn("True Positives", html)
        self.assertIn("False Positives", html)

    def test_geographic_html_not_completed(self):
        """Geographic HTML is False when not completed."""
        run = self.env["spp.simulation.run"].create({"scenario_id": self.scenario.id, "state": "running"})
        self.assertFalse(run.geographic_html)

    def test_geographic_html_with_data(self):
        """Geographic HTML renders area breakdown table."""
        run = self._create_completed_run(
            geographic_json={
                "1": {"name": "Area A", "count": 100, "amount": 50000.0, "coverage_rate": 80.0},
                "2": {"name": "Area B", "count": 50, "amount": 25000.0, "coverage_rate": 40.0},
            },
        )
        self.assertIn("Area A", run.geographic_html)
        self.assertIn("Area B", run.geographic_html)


@tagged("post_install", "-at_install")
class TestRunSnapshotFields(SimulationTestCommon):
    """Tests for scenario snapshot computed fields."""

    def test_snapshot_fields_parsed(self):
        """Snapshot JSON is parsed into individual fields."""
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "scenario_snapshot_json": {
                    "name": "Snapshot Name",
                    "target_type": "group",
                    "targeting_expression": "r.age > 18",
                    "budget_strategy": "cap_total",
                    "budget_amount": 50000.0,
                },
            }
        )
        self.assertEqual(run.scenario_snapshot_target_type, "Group (Household)")
        self.assertEqual(run.scenario_snapshot_budget_strategy, "Cap at Budget Total")
        self.assertEqual(run.scenario_snapshot_budget_amount, 50000.0)
        self.assertEqual(run.scenario_snapshot_targeting_expression, "r.age > 18")

    def test_snapshot_fields_no_data(self):
        """Snapshot fields are empty when no JSON."""
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "scenario_snapshot_json": False,
            }
        )
        self.assertFalse(run.scenario_snapshot_target_type)

    def test_run_unlink_blocked(self):
        """Simulation runs cannot be deleted."""
        run = self.env["spp.simulation.run"].create({"scenario_id": self.scenario.id, "state": "completed"})
        with self.assertRaises(UserError):
            run.unlink()


@tagged("post_install", "-at_install")
class TestBudgetStrategyEdgeCases(SimulationTestCommon):
    """Tests for budget strategy branches in simulation service."""

    def test_budget_none_returns_original(self):
        """Budget strategy 'none' returns amounts unchanged."""
        service = self.env["spp.simulation.service"]
        self.scenario.write({"budget_strategy": "none", "budget_amount": 0})
        amounts = [100.0, 200.0, 300.0]
        result = service._apply_budget_strategy(self.scenario, amounts)
        self.assertEqual(result, amounts)

    def test_budget_cap_total_under_budget(self):
        """cap_total with total <= budget returns amounts unchanged."""
        service = self.env["spp.simulation.service"]
        self.scenario.write({"budget_strategy": "cap_total", "budget_amount": 1000.0})
        amounts = [100.0, 200.0, 300.0]
        result = service._apply_budget_strategy(self.scenario, amounts)
        self.assertEqual(result, amounts)

    def test_budget_cap_total_over_budget(self):
        """cap_total with total > budget zeroes out excess beneficiaries."""
        service = self.env["spp.simulation.service"]
        self.scenario.write({"budget_strategy": "cap_total", "budget_amount": 250.0})
        amounts = [100.0, 200.0, 300.0]
        result = service._apply_budget_strategy(self.scenario, amounts)
        # 250 budget: first 100 fits (remaining=150), second 200>150 so 0, third also 0
        self.assertEqual(result[0], 100.0)
        self.assertEqual(result[1], 0.0)
        self.assertEqual(result[2], 0.0)

    def test_budget_proportional_reduction(self):
        """proportional_reduction scales amounts to fit budget."""
        service = self.env["spp.simulation.service"]
        self.scenario.write({"budget_strategy": "proportional_reduction", "budget_amount": 300.0})
        amounts = [100.0, 200.0, 300.0]
        result = service._apply_budget_strategy(self.scenario, amounts)
        # Total 600, budget 300, ratio 0.5
        self.assertAlmostEqual(result[0], 50.0)
        self.assertAlmostEqual(result[1], 100.0)
        self.assertAlmostEqual(result[2], 150.0)

    def test_budget_proportional_under_budget(self):
        """proportional_reduction with total <= budget returns unchanged."""
        service = self.env["spp.simulation.service"]
        self.scenario.write({"budget_strategy": "proportional_reduction", "budget_amount": 1000.0})
        amounts = [100.0, 200.0, 300.0]
        result = service._apply_budget_strategy(self.scenario, amounts)
        self.assertEqual(result, amounts)

    def test_budget_zero_total_returns_unchanged(self):
        """Zero total amounts returns unchanged regardless of strategy."""
        service = self.env["spp.simulation.service"]
        self.scenario.write({"budget_strategy": "cap_total", "budget_amount": 100.0})
        amounts = [0.0, 0.0, 0.0]
        result = service._apply_budget_strategy(self.scenario, amounts)
        self.assertEqual(result, amounts)


@tagged("post_install", "-at_install")
class TestServiceErrorHandling(SimulationTestCommon):
    """Tests for error handling branches in simulation service."""

    def test_apply_multiplier_invalid_field(self):
        """Multiplier rule with nonexistent field logs warning and returns."""
        service = self.env["spp.simulation.service"]
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "multiplier",
                "amount": 100.0,
                "multiplier_field": "nonexistent_field_xyz",
            }
        )
        amounts = {1: 0.0}
        # Should not raise, just log warning
        service._apply_multiplier_rule(rule, [1], amounts)
        self.assertEqual(amounts[1], 0.0)

    def test_apply_multiplier_empty_ids(self):
        """Multiplier rule with empty IDs returns immediately."""
        service = self.env["spp.simulation.service"]
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "multiplier",
                "amount": 100.0,
                "multiplier_field": "name",
            }
        )
        amounts = {}
        service._apply_multiplier_rule(rule, [], amounts)
        self.assertEqual(amounts, {})

    def test_apply_cel_rule_empty_ids(self):
        """CEL rule with empty IDs returns immediately."""
        service = self.env["spp.simulation.service"]
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "cel",
                "amount": 100.0,
                "amount_cel_expression": "base_amount * 2",
            }
        )
        amounts = {}
        service._apply_cel_rule(rule, [], amounts)
        self.assertEqual(amounts, {})

    def test_filter_by_condition_invalid_expression(self):
        """Invalid condition expression returns all beneficiary IDs."""
        service = self.env["spp.simulation.service"]
        ids = list(self.group_registrants.ids)
        with patch.object(
            type(self.env["spp.cel.service"]),
            "compile_expression",
            side_effect=Exception("CEL error"),
        ):
            result = service._filter_by_condition("invalid!!", ids, "group")
        self.assertEqual(result, ids)


@tagged("post_install", "-at_install")
class TestScenarioEdgeCases(SimulationTestCommon):
    """Tests for scenario model edge cases."""

    def test_compute_cel_profile_group(self):
        """CEL profile is 'registry_groups' for group target type."""
        self.assertEqual(self.scenario.cel_profile, "registry_groups")

    def test_compute_cel_profile_individual(self):
        """CEL profile is 'registry_individuals' for individual target type."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Individual Test",
                "target_type": "individual",
                "targeting_expression": "true",
            }
        )
        self.assertEqual(scenario.cel_profile, "registry_individuals")

    def test_targeting_preview_count_invalid_expression(self):
        """Invalid targeting expression sets preview count to 0."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Invalid Expr",
                "target_type": "group",
                "targeting_expression": "this_is_invalid!!!",
            }
        )
        self.assertEqual(scenario.targeting_preview_count, 0)

    def test_scenario_draft_to_ready(self):
        """Scenario can transition from draft to ready."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Draft To Ready",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "draft",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario.id,
                "amount_mode": "fixed",
                "amount": 500.0,
            }
        )
        scenario.action_set_ready()
        self.assertEqual(scenario.state, "ready")

    def test_scenario_set_ready_without_expression_raises(self):
        """Setting ready without targeting expression raises error."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "No Expression",
                "target_type": "group",
                "targeting_expression": False,
                "state": "draft",
            }
        )
        with self.assertRaises(ValidationError):
            scenario.action_set_ready()


@tagged("post_install", "-at_install")
class TestComparisonEdgeCases(SimulationTestCommon):
    """Tests for comparison overlap edge cases."""

    def test_comparison_with_empty_runs(self):
        """Comparison with runs that have no targeting expression."""
        run1 = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 0,
            }
        )
        scenario2 = self.env["spp.simulation.scenario"].create(
            {
                "name": "Second Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario2.id,
                "amount_mode": "fixed",
                "amount": 500.0,
            }
        )
        run2 = self.env["spp.simulation.run"].create(
            {
                "scenario_id": scenario2.id,
                "state": "completed",
                "beneficiary_count": 5,
            }
        )

        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Test Comparison",
                "run_ids": [(6, 0, [run1.id, run2.id])],
            }
        )
        # Should not raise
        comparison.action_compute_comparison()
        self.assertTrue(comparison.comparison_json)

    def test_compare_wizard_minimum_runs(self):
        """Compare wizard requires at least 2 runs."""
        run = self.env["spp.simulation.run"].create({"scenario_id": self.scenario.id, "state": "completed"})
        wizard = self.env["spp.simulation.compare.wizard"].create({"run_ids": [(6, 0, [run.id])]})
        with self.assertRaises(ValidationError):
            wizard.action_compare()


@tagged("post_install", "-at_install")
class TestEntitlementRuleEdgeCases(SimulationTestCommon):
    """Tests for entitlement rule constraint edge cases."""

    def test_fixed_amount_zero_allowed(self):
        """Fixed amount of exactly 0 is allowed."""
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "fixed",
                "amount": 0.0,
            }
        )
        self.assertEqual(rule.amount, 0.0)

    def test_multiplier_with_max(self):
        """Multiplier rule with max_multiplier set."""
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "multiplier",
                "amount": 100.0,
                "multiplier_field": "name",
                "max_multiplier": 5.0,
            }
        )
        self.assertEqual(rule.max_multiplier, 5.0)

    def test_negative_fixed_amount_raises(self):
        """Negative fixed amount raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.entitlement.rule"].create(
                {
                    "scenario_id": self.scenario.id,
                    "amount_mode": "fixed",
                    "amount": -100.0,
                }
            )


@tagged("post_install", "-at_install")
class TestGeographicBreakdown(SimulationTestCommon):
    """Tests for geographic breakdown computation."""

    def test_geographic_breakdown_empty(self):
        """Empty beneficiary list returns empty breakdown."""
        service = self.env["spp.simulation.service"]
        result = service._compute_geographic_breakdown(self.scenario, [], [])
        self.assertEqual(result, {})

    def test_geographic_breakdown_with_areas(self):
        """Beneficiaries with areas are grouped correctly."""
        service = self.env["spp.simulation.service"]
        ids = list(self.group_registrants.ids)
        amounts = [1000.0] * len(ids)
        result = service._compute_geographic_breakdown(self.scenario, ids, amounts)
        # Result is {area_id_str: {name, count, amount, coverage_rate}}
        self.assertIsInstance(result, dict)
        self.assertTrue(len(result) > 0)
        # Each area entry has the expected keys
        for _area_key, area_info in result.items():
            self.assertIn("name", area_info)
            self.assertIn("count", area_info)
            self.assertIn("amount", area_info)
            self.assertIn("coverage_rate", area_info)
