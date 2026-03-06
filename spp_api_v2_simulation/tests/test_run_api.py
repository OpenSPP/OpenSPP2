# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for simulation run API logic."""

from odoo.tests import tagged

from .common import SimulationApiTestCase


@tagged("-at_install", "post_install")
class TestRunApi(SimulationApiTestCase):
    """Test run endpoint logic and schemas."""

    def test_run_to_summary_conversion(self):
        """Test conversion of Odoo run to Pydantic summary."""
        from ..routers.run import _run_to_summary

        summary = _run_to_summary(self.run_completed)

        # Verify basic fields
        self.assertEqual(summary.id, self.run_completed.id)
        self.assertEqual(summary.scenario_id, self.scenario_ready.id)
        self.assertEqual(summary.scenario_name, "Ready Test Scenario")
        self.assertEqual(summary.state, "completed")

        # Verify metrics
        self.assertEqual(summary.beneficiary_count, 5)
        self.assertEqual(summary.total_cost, 2500.0)
        self.assertEqual(summary.coverage_rate, 50.0)
        self.assertEqual(summary.equity_score, 85.0)
        self.assertEqual(summary.gini_coefficient, 0.15)

        # Verify execution data
        self.assertEqual(summary.executed_at, "2024-01-01T00:00:00")
        self.assertEqual(summary.execution_duration_seconds, 1.5)

    def test_run_to_response_conversion_without_details(self):
        """Test conversion of Odoo run to Pydantic response without details."""
        from ..routers.run import _run_to_response

        response = _run_to_response(self.run_completed, include_details=False)

        # Verify basic fields
        self.assertEqual(response.id, self.run_completed.id)
        self.assertEqual(response.scenario_id, self.scenario_ready.id)
        self.assertEqual(response.scenario_name, "Ready Test Scenario")
        self.assertEqual(response.state, "completed")

        # Verify headline metrics
        self.assertEqual(response.beneficiary_count, 5)
        self.assertEqual(response.total_cost, 2500.0)
        self.assertEqual(response.coverage_rate, 50.0)
        self.assertEqual(response.equity_score, 85.0)
        self.assertEqual(response.gini_coefficient, 0.15)
        self.assertEqual(response.total_registry_count, 10)
        self.assertEqual(response.budget_utilization, 50.0)
        self.assertFalse(response.has_disparity)
        self.assertEqual(response.leakage_rate, 0.0)
        self.assertEqual(response.undercoverage_rate, 0.0)

        # Verify execution data
        self.assertEqual(response.executed_at, "2024-01-01T00:00:00")
        self.assertEqual(response.execution_duration_seconds, 1.5)

        # Detailed data should be None
        self.assertIsNone(response.distribution_data)
        self.assertIsNone(response.fairness_data)
        self.assertIsNone(response.geographic_data)
        self.assertIsNone(response.metric_results)

    def test_run_to_response_conversion_with_details(self):
        """Test conversion of Odoo run to Pydantic response with details."""
        # Add distribution data
        self.run_completed.distribution_json = {
            "count": 5,
            "total": 2500.0,
            "minimum": 500.0,
            "maximum": 500.0,
            "mean": 500.0,
            "median": 500.0,
            "standard_deviation": 0.0,
            "gini_coefficient": 0.0,
            "percentiles": {"p25": 500.0, "p50": 500.0, "p75": 500.0},
        }

        # Add fairness data
        self.run_completed.fairness_json = {
            "equity_score": 85.0,
            "has_disparity": False,
            "demographic_breakdown": {"age_group": {"youth": 50, "adult": 50}},
        }

        # Add geographic data
        self.run_completed.geographic_json = [
            {
                "area_id": self.area.id,
                "area_name": "Test Area",
                "beneficiary_count": 5,
                "total_cost": 2500.0,
            }
        ]

        # Add metric results
        self.run_completed.metric_results_json = {
            "total_beneficiaries": {
                "type": "count",
                "value": 5,
            },
            "total_cost": {
                "type": "sum",
                "value": 2500.0,
            },
        }

        # Add scenario snapshot
        self.run_completed.scenario_snapshot_json = {
            "name": "Ready Test Scenario",
            "target_type": "group",
            "targeting_expression": "true",
            "budget_amount": 5000.0,
            "budget_strategy": "none",
            "entitlement_rules": [
                {
                    "amount_mode": "fixed",
                    "amount": 500.0,
                }
            ],
        }

        from ..routers.run import _run_to_response

        response = _run_to_response(self.run_completed, include_details=True)

        # Verify detailed data is present
        self.assertIsNotNone(response.distribution_data)
        self.assertIsNotNone(response.fairness_data)
        self.assertIsNotNone(response.geographic_data)
        self.assertIsNotNone(response.metric_results)
        self.assertIsNotNone(response.scenario_snapshot)

        # Verify distribution data
        self.assertEqual(response.distribution_data.count, 5)
        self.assertEqual(response.distribution_data.total, 2500.0)
        self.assertEqual(response.distribution_data.mean, 500.0)

        # Verify fairness data
        self.assertEqual(response.fairness_data.equity_score, 85.0)
        self.assertFalse(response.fairness_data.has_disparity)

        # Verify geographic data
        self.assertEqual(len(response.geographic_data.areas), 1)

        # Verify metric results
        self.assertIn("total_beneficiaries", response.metric_results)
        self.assertEqual(response.metric_results["total_beneficiaries"].type, "count")
        self.assertEqual(response.metric_results["total_beneficiaries"].value, 5)

        # Verify scenario snapshot
        self.assertEqual(response.scenario_snapshot.name, "Ready Test Scenario")
        self.assertEqual(response.scenario_snapshot.target_type, "group")
        self.assertEqual(response.scenario_snapshot.budget_amount, 5000.0)

    def test_run_response_schema_validation(self):
        """Test RunResponse schema validation."""
        from ..schemas.run import RunResponse

        # Test minimal response
        response = RunResponse(
            id=1,
            scenario_id=1,
            scenario_name="Test Scenario",
            state="completed",
            beneficiary_count=10,
            total_registry_count=100,
            coverage_rate=10.0,
            total_cost=5000.0,
            budget_utilization=50.0,
            gini_coefficient=0.2,
            equity_score=80.0,
            has_disparity=False,
            leakage_rate=0.0,
            undercoverage_rate=0.0,
        )

        self.assertEqual(response.id, 1)
        self.assertEqual(response.state, "completed")
        self.assertEqual(response.beneficiary_count, 10)
        self.assertIsNone(response.distribution_data)

    def test_run_summary_schema(self):
        """Test RunSummary schema."""
        from ..schemas.run import RunSummary

        summary = RunSummary(
            id=1,
            scenario_id=1,
            scenario_name="Test Scenario",
            state="completed",
            beneficiary_count=10,
            total_cost=5000.0,
            coverage_rate=10.0,
            equity_score=85.0,
            gini_coefficient=0.15,
            executed_at="2024-01-01T00:00:00Z",
            execution_duration_seconds=2.5,
        )

        self.assertEqual(summary.id, 1)
        self.assertEqual(summary.beneficiary_count, 10)
        self.assertEqual(summary.executed_at, "2024-01-01T00:00:00Z")

    def test_run_list_response_schema(self):
        """Test RunListResponse schema."""
        from ..schemas.run import RunListResponse, RunSummary

        runs = [
            RunSummary(
                id=1,
                scenario_id=1,
                scenario_name="Scenario 1",
                state="completed",
                beneficiary_count=10,
                total_cost=5000.0,
                coverage_rate=10.0,
                equity_score=85.0,
                gini_coefficient=0.15,
                executed_at="2024-01-01T00:00:00Z",
                execution_duration_seconds=1.5,
            ),
            RunSummary(
                id=2,
                scenario_id=1,
                scenario_name="Scenario 1",
                state="completed",
                beneficiary_count=8,
                total_cost=4000.0,
                coverage_rate=8.0,
                equity_score=90.0,
                gini_coefficient=0.10,
                executed_at="2024-01-02T00:00:00Z",
                execution_duration_seconds=1.2,
            ),
        ]

        response = RunListResponse(
            runs=runs,
            total_count=2,
        )

        self.assertEqual(len(response.runs), 2)
        self.assertEqual(response.total_count, 2)
        self.assertEqual(response.runs[0].beneficiary_count, 10)
        self.assertEqual(response.runs[1].beneficiary_count, 8)

    def test_run_simulation_response_schema(self):
        """Test RunSimulationResponse schema."""
        from ..schemas.run import RunSimulationResponse

        # Success response
        success_response = RunSimulationResponse(
            run_id=1,
            scenario_id=1,
            state="completed",
            message="Simulation completed with 10 beneficiaries",
        )

        self.assertEqual(success_response.run_id, 1)
        self.assertEqual(success_response.state, "completed")
        self.assertIn("completed", success_response.message)

        # Failure response
        failure_response = RunSimulationResponse(
            run_id=2,
            scenario_id=1,
            state="failed",
            message="Simulation failed: Invalid targeting expression",
        )

        self.assertEqual(failure_response.state, "failed")
        self.assertIn("failed", failure_response.message)

    def test_distribution_data_schema(self):
        """Test DistributionData schema."""
        from ..schemas.run import DistributionData

        dist_data = DistributionData(
            count=100,
            total=50000.0,
            minimum=100.0,
            maximum=1000.0,
            mean=500.0,
            median=450.0,
            standard_deviation=150.0,
            gini_coefficient=0.25,
            percentiles={"p25": 300.0, "p50": 450.0, "p75": 600.0},
        )

        self.assertEqual(dist_data.count, 100)
        self.assertEqual(dist_data.mean, 500.0)
        self.assertEqual(dist_data.gini_coefficient, 0.25)
        self.assertIn("p50", dist_data.percentiles)
        self.assertEqual(dist_data.percentiles["p50"], 450.0)

    def test_fairness_data_schema(self):
        """Test FairnessData schema."""
        from ..schemas.run import FairnessData

        fairness_data = FairnessData(
            equity_score=85.0,
            has_disparity=True,
            demographic_breakdown={
                "gender": {"male": 45, "female": 55},
                "age_group": {"youth": 30, "adult": 50, "senior": 20},
            },
        )

        self.assertEqual(fairness_data.equity_score, 85.0)
        self.assertTrue(fairness_data.has_disparity)
        self.assertIn("gender", fairness_data.demographic_breakdown)
        self.assertIn("age_group", fairness_data.demographic_breakdown)

    def test_targeting_efficiency_data_schema(self):
        """Test TargetingEfficiencyData schema."""
        from ..schemas.run import TargetingEfficiencyData

        eff_data = TargetingEfficiencyData(
            true_positives=80,
            false_positives=20,
            false_negatives=10,
            total_simulated=100,
            total_ideal=90,
            leakage_rate=20.0,
            undercoverage_rate=11.1,
        )

        self.assertEqual(eff_data.true_positives, 80)
        self.assertEqual(eff_data.false_positives, 20)
        self.assertEqual(eff_data.false_negatives, 10)
        self.assertEqual(eff_data.leakage_rate, 20.0)
        self.assertEqual(eff_data.undercoverage_rate, 11.1)

    def test_geographic_data_schema(self):
        """Test GeographicData schema."""
        from ..schemas.run import GeographicData

        geo_data = GeographicData(
            areas=[
                {
                    "area_id": 1,
                    "area_name": "Area 1",
                    "beneficiary_count": 50,
                    "total_cost": 25000.0,
                },
                {
                    "area_id": 2,
                    "area_name": "Area 2",
                    "beneficiary_count": 30,
                    "total_cost": 15000.0,
                },
            ]
        )

        self.assertEqual(len(geo_data.areas), 2)
        self.assertEqual(geo_data.areas[0]["area_name"], "Area 1")
        self.assertEqual(geo_data.areas[1]["beneficiary_count"], 30)

    def test_metric_result_schema(self):
        """Test MetricResult schema."""
        from ..schemas.run import MetricResult

        # Count metric
        count_metric = MetricResult(type="count", value=100)
        self.assertEqual(count_metric.type, "count")
        self.assertEqual(count_metric.value, 100)

        # Sum metric
        sum_metric = MetricResult(type="sum", value=50000.0)
        self.assertEqual(sum_metric.type, "sum")
        self.assertEqual(sum_metric.value, 50000.0)

        # Average metric
        avg_metric = MetricResult(type="average", value=500.0)
        self.assertEqual(avg_metric.type, "average")
        self.assertEqual(avg_metric.value, 500.0)

    def test_scenario_snapshot_schema(self):
        """Test ScenarioSnapshot schema."""
        from ..schemas.run import ScenarioSnapshot

        snapshot = ScenarioSnapshot(
            name="Test Scenario",
            target_type="group",
            targeting_expression="true",
            budget_amount=10000.0,
            budget_strategy="cap_total",
            ideal_population_expression="r.is_vulnerable == true",
            entitlement_rules=[
                {
                    "amount_mode": "fixed",
                    "amount": 500.0,
                }
            ],
        )

        self.assertEqual(snapshot.name, "Test Scenario")
        self.assertEqual(snapshot.target_type, "group")
        self.assertEqual(snapshot.budget_amount, 10000.0)
        self.assertEqual(len(snapshot.entitlement_rules), 1)
        self.assertEqual(snapshot.entitlement_rules[0]["amount"], 500.0)

    def test_failed_run_conversion(self):
        """Test conversion of failed run."""
        from ..routers.run import _run_to_response

        response = _run_to_response(self.run_failed, include_details=False)

        self.assertEqual(response.state, "failed")
        self.assertEqual(response.beneficiary_count, 0)
        self.assertEqual(response.total_cost, 0.0)
        self.assertEqual(response.error_message, "Test error message")

    def test_run_with_targeting_efficiency(self):
        """Test run with targeting efficiency data."""
        # Add targeting efficiency data (success case)
        self.run_completed.targeting_efficiency_json = {
            "true_positives": 4,
            "false_positives": 1,
            "false_negatives": 2,
            "total_simulated": 5,
            "total_ideal": 6,
            "leakage_rate": 20.0,
            "undercoverage_rate": 33.3,
        }

        from ..routers.run import _run_to_response

        response = _run_to_response(self.run_completed, include_details=True)

        self.assertIsNotNone(response.targeting_efficiency_data)
        self.assertEqual(response.targeting_efficiency_data.true_positives, 4)
        self.assertEqual(response.targeting_efficiency_data.false_positives, 1)
        self.assertEqual(response.targeting_efficiency_data.false_negatives, 2)
        self.assertEqual(response.targeting_efficiency_data.leakage_rate, 20.0)

    def test_run_with_targeting_efficiency_error(self):
        """Test run with targeting efficiency error is excluded."""
        # Add targeting efficiency data with error
        run_with_error = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario_ready.id,
                "state": "completed",
                "beneficiary_count": 5,
                "total_cost": 2500.0,
                "targeting_efficiency_json": {
                    "error": "Ideal population expression not defined",
                },
            }
        )

        from ..routers.run import _run_to_response

        response = _run_to_response(run_with_error, include_details=True)

        # Should not include targeting efficiency data when there's an error
        self.assertIsNone(response.targeting_efficiency_data)
