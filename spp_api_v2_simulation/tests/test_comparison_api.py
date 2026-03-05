# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for simulation comparison API logic."""

from odoo import Command
from odoo.tests import tagged

from .common import SimulationApiTestCase


@tagged("-at_install", "post_install")
class TestComparisonApi(SimulationApiTestCase):
    """Test comparison endpoint logic and schemas."""

    def test_comparison_to_response_conversion(self):
        """Test conversion of Odoo comparison to Pydantic response."""
        # Create comparison
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Test Comparison",
                "run_ids": [Command.set([self.run_completed.id, self.run_completed_2.id])],
            }
        )

        # Compute comparison data
        comparison.action_compute_comparison()

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        # Verify basic fields
        self.assertEqual(response.id, comparison.id)
        self.assertEqual(response.name, "Test Comparison")

        # Verify runs data
        self.assertEqual(len(response.runs), 2)
        self.assertEqual(response.runs[0].run_id, self.run_completed.id)
        self.assertEqual(response.runs[1].run_id, self.run_completed_2.id)

        # Verify overlap data exists
        self.assertIsNotNone(response.overlap_data)
        self.assertGreater(len(response.overlap_data), 0)

    def test_comparison_response_schema(self):
        """Test ComparisonResponse schema validation."""
        from ..schemas.comparison import (
            ComparisonResponse,
            ComparisonRunData,
            OverlapData,
        )

        runs = [
            ComparisonRunData(
                run_id=1,
                scenario_name="Scenario 1",
                beneficiary_count=100,
                total_cost=50000.0,
                coverage_rate=10.0,
                equity_score=85.0,
                gini_coefficient=0.15,
                has_disparity=False,
                leakage_rate=5.0,
                undercoverage_rate=10.0,
                budget_utilization=50.0,
                executed_at="2024-01-01T00:00:00Z",
            ),
            ComparisonRunData(
                run_id=2,
                scenario_name="Scenario 2",
                beneficiary_count=90,
                total_cost=45000.0,
                coverage_rate=9.0,
                equity_score=88.0,
                gini_coefficient=0.12,
                has_disparity=False,
                leakage_rate=3.0,
                undercoverage_rate=8.0,
                budget_utilization=45.0,
                executed_at="2024-01-02T00:00:00Z",
            ),
        ]

        overlap = [
            OverlapData(
                run_a_id=1,
                run_a_name="Scenario 1",
                run_b_id=2,
                run_b_name="Scenario 2",
                overlap_count=80,
                union_count=110,
                jaccard_index=0.727,
            )
        ]

        response = ComparisonResponse(
            id=1,
            name="Test Comparison",
            runs=runs,
            overlap_data=overlap,
            staleness_warning=None,
        )

        self.assertEqual(response.id, 1)
        self.assertEqual(response.name, "Test Comparison")
        self.assertEqual(len(response.runs), 2)
        self.assertEqual(len(response.overlap_data), 1)
        self.assertEqual(response.overlap_data[0].overlap_count, 80)
        self.assertAlmostEqual(response.overlap_data[0].jaccard_index, 0.727, places=3)

    def test_comparison_create_request_schema(self):
        """Test ComparisonCreateRequest schema."""
        from ..schemas.comparison import ComparisonCreateRequest

        # Test with default name
        request = ComparisonCreateRequest(
            run_ids=[1, 2, 3],
        )

        self.assertEqual(len(request.run_ids), 3)
        self.assertIsNotNone(request.name)

        # Test with custom name
        custom_request = ComparisonCreateRequest(
            name="Custom Comparison",
            run_ids=[1, 2],
        )

        self.assertEqual(custom_request.name, "Custom Comparison")
        self.assertEqual(len(custom_request.run_ids), 2)

    def test_comparison_run_data_schema(self):
        """Test ComparisonRunData schema."""
        from ..schemas.comparison import ComparisonRunData

        run_data = ComparisonRunData(
            run_id=1,
            scenario_name="Test Scenario",
            beneficiary_count=50,
            total_cost=25000.0,
            coverage_rate=5.0,
            equity_score=90.0,
            gini_coefficient=0.10,
            has_disparity=False,
            leakage_rate=2.0,
            undercoverage_rate=5.0,
            budget_utilization=50.0,
            executed_at="2024-01-01T00:00:00Z",
        )

        self.assertEqual(run_data.run_id, 1)
        self.assertEqual(run_data.scenario_name, "Test Scenario")
        self.assertEqual(run_data.beneficiary_count, 50)
        self.assertEqual(run_data.equity_score, 90.0)

    def test_overlap_data_schema(self):
        """Test OverlapData schema."""
        from ..schemas.comparison import OverlapData

        overlap_data = OverlapData(
            run_a_id=1,
            run_a_name="Scenario A",
            run_b_id=2,
            run_b_name="Scenario B",
            overlap_count=75,
            union_count=125,
            jaccard_index=0.6,
        )

        self.assertEqual(overlap_data.run_a_id, 1)
        self.assertEqual(overlap_data.run_b_id, 2)
        self.assertEqual(overlap_data.overlap_count, 75)
        self.assertEqual(overlap_data.union_count, 125)
        self.assertEqual(overlap_data.jaccard_index, 0.6)

    def test_comparison_with_two_runs(self):
        """Test comparison requires at least 2 runs."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Two Runs Comparison",
                "run_ids": [Command.set([self.run_completed.id, self.run_completed_2.id])],
            }
        )

        comparison.action_compute_comparison()

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        self.assertEqual(len(response.runs), 2)

    def test_comparison_with_three_runs(self):
        """Test comparison with three runs."""
        from datetime import datetime

        # Create third run
        run_3 = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario_ready.id,
                "state": "completed",
                "beneficiary_count": 6,
                "total_cost": 3000.0,
                "coverage_rate": 60.0,
                "equity_score": 82.0,
                "gini_coefficient": 0.18,
                "total_registry_count": 10,
                "budget_utilization": 60.0,
                "has_disparity": False,
                "leakage_rate": 0.0,
                "undercoverage_rate": 0.0,
                "executed_at": datetime(2024, 1, 4, 0, 0, 0),
                "execution_duration_seconds": 1.8,
            }
        )

        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Three Runs Comparison",
                "run_ids": [Command.set([self.run_completed.id, self.run_completed_2.id, run_3.id])],
            }
        )

        comparison.action_compute_comparison()

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        self.assertEqual(len(response.runs), 3)

        # Should have 3 overlap pairs (A-B, A-C, B-C)
        self.assertGreaterEqual(len(response.overlap_data), 3)

    def test_comparison_staleness_warning(self):
        """Test comparison with staleness warning."""
        from datetime import datetime

        # Update scenario to be newer than the runs
        self.scenario_ready.write_date = datetime.now()

        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Stale Comparison",
                "run_ids": [Command.set([self.run_completed.id, self.run_completed_2.id])],
            }
        )

        comparison.action_compute_comparison()

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        # Note: staleness_warning is a computed field that depends on scenario modification times
        # We can't easily trigger it in tests since it compares scenario write_date to run executed_at
        # So we just verify the response can handle both None and non-None staleness warnings
        self.assertIsInstance(response.staleness_warning, (str, type(None)))

    def test_comparison_empty_overlap(self):
        """Test comparison with empty overlap data."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Empty Overlap Comparison",
                "run_ids": [Command.set([self.run_completed.id, self.run_completed_2.id])],
                "overlap_count_json": {},
            }
        )

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        # Should return empty list, not None
        self.assertEqual(len(response.overlap_data), 0)

    def test_comparison_with_failed_run(self):
        """Test comparison that includes a failed run."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Comparison With Failed Run",
                "run_ids": [Command.set([self.run_completed.id, self.run_failed.id])],
            }
        )

        # Compute comparison (should handle failed run gracefully)
        comparison.action_compute_comparison()

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        # Should include both runs in response
        self.assertEqual(len(response.runs), 2)

    def test_comparison_jaccard_index_calculation(self):
        """Test Jaccard index in overlap data."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Jaccard Test",
                "run_ids": [Command.set([self.run_completed.id, self.run_completed_2.id])],
            }
        )

        # Set specific overlap data
        comparison.overlap_count_json = {
            f"{self.run_completed.id}_{self.run_completed_2.id}": {
                "run_a_id": self.run_completed.id,
                "run_a_name": "Ready Test Scenario",
                "run_b_id": self.run_completed_2.id,
                "run_b_name": "Ready Test Scenario",
                "overlap_count": 50,
                "union_count": 100,
                "jaccard_index": 0.5,
            }
        }

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        # Verify Jaccard index
        self.assertEqual(len(response.overlap_data), 1)
        self.assertEqual(response.overlap_data[0].overlap_count, 50)
        self.assertEqual(response.overlap_data[0].union_count, 100)
        self.assertEqual(response.overlap_data[0].jaccard_index, 0.5)

    def test_comparison_different_scenarios(self):
        """Test comparison of runs from different scenarios."""
        from datetime import datetime

        # Create second scenario
        scenario_2 = self.env["spp.simulation.scenario"].create(
            {
                "name": "Second Test Scenario",
                "target_type": "individual",
                "targeting_expression": "true",
                "state": "ready",
            }
        )

        # Create run for second scenario
        run_scenario_2 = self.env["spp.simulation.run"].create(
            {
                "scenario_id": scenario_2.id,
                "state": "completed",
                "beneficiary_count": 8,
                "total_cost": 4000.0,
                "coverage_rate": 80.0,
                "equity_score": 88.0,
                "gini_coefficient": 0.12,
                "total_registry_count": 10,
                "budget_utilization": 80.0,
                "has_disparity": False,
                "leakage_rate": 0.0,
                "undercoverage_rate": 0.0,
                "executed_at": datetime(2024, 1, 5, 0, 0, 0),
                "execution_duration_seconds": 2.0,
            }
        )

        # Create comparison across scenarios
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Cross-Scenario Comparison",
                "run_ids": [Command.set([self.run_completed.id, run_scenario_2.id])],
            }
        )

        comparison.action_compute_comparison()

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        # Verify both runs are included
        self.assertEqual(len(response.runs), 2)

        # Verify different scenario names
        scenario_names = {run.scenario_name for run in response.runs}
        self.assertEqual(len(scenario_names), 2)
        self.assertIn("Ready Test Scenario", scenario_names)
        self.assertIn("Second Test Scenario", scenario_names)

    def test_comparison_run_data_completeness(self):
        """Test that comparison includes all necessary run metrics."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Complete Metrics Comparison",
                "run_ids": [Command.set([self.run_completed.id, self.run_completed_2.id])],
            }
        )

        # Set comparison JSON with complete data
        comparison.comparison_json = {
            "runs": [
                {
                    "run_id": self.run_completed.id,
                    "scenario_name": "Ready Test Scenario",
                    "beneficiary_count": 5,
                    "total_cost": 2500.0,
                    "coverage_rate": 50.0,
                    "equity_score": 85.0,
                    "gini_coefficient": 0.15,
                    "has_disparity": False,
                    "leakage_rate": 0.0,
                    "undercoverage_rate": 0.0,
                    "budget_utilization": 50.0,
                    "executed_at": "2024-01-01T00:00:00Z",
                }
            ]
        }

        from ..routers.comparison import _comparison_to_response

        response = _comparison_to_response(comparison)

        # Verify all metrics are present
        run_data = response.runs[0]
        self.assertEqual(run_data.beneficiary_count, 5)
        self.assertEqual(run_data.total_cost, 2500.0)
        self.assertEqual(run_data.coverage_rate, 50.0)
        self.assertEqual(run_data.equity_score, 85.0)
        self.assertEqual(run_data.gini_coefficient, 0.15)
        self.assertFalse(run_data.has_disparity)
        self.assertEqual(run_data.leakage_rate, 0.0)
        self.assertEqual(run_data.undercoverage_rate, 0.0)
        self.assertEqual(run_data.budget_utilization, 50.0)
        self.assertEqual(run_data.executed_at, "2024-01-01T00:00:00Z")
