# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestSimulationComparison(SimulationTestCommon):
    """Tests for spp.simulation.comparison model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.run_a = cls.env["spp.simulation.run"].create(
            {
                "scenario_id": cls.scenario.id,
                "state": "completed",
                "beneficiary_count": 100,
                "total_registry_count": 1000,
                "coverage_rate": 10.0,
                "total_cost": 100000.0,
                "equity_score": 85.0,
            }
        )
        # Create a second scenario for comparison
        cls.scenario_b = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Test Scenario B",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        cls.run_b = cls.env["spp.simulation.run"].create(
            {
                "scenario_id": cls.scenario_b.id,
                "state": "completed",
                "beneficiary_count": 200,
                "total_registry_count": 1000,
                "coverage_rate": 20.0,
                "total_cost": 200000.0,
                "equity_score": 72.0,
            }
        )

    def test_create_comparison(self):
        """Test creating a valid comparison."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Test Comparison",
                "run_ids": [Command.set([self.run_a.id, self.run_b.id])],
            }
        )
        self.assertEqual(len(comparison.run_ids), 2)

    def test_comparison_requires_minimum_runs(self):
        """Test that comparison requires at least 2 runs."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.comparison"].create(
                {
                    "name": "Invalid Comparison",
                    "run_ids": [Command.set([self.run_a.id])],
                }
            )

    def test_compute_comparison(self):
        """Test computing comparison data."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Test Comparison",
                "run_ids": [Command.set([self.run_a.id, self.run_b.id])],
            }
        )
        comparison.action_compute_comparison()
        self.assertTrue(comparison.comparison_json)
        data = comparison.comparison_json
        self.assertEqual(len(data["runs"]), 2)

    def test_staleness_warning(self):
        """Test staleness warning for runs from different dates."""
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Staleness Test",
                "run_ids": [Command.set([self.run_a.id, self.run_b.id])],
            }
        )
        # Both runs are from now, so no staleness warning expected
        self.assertFalse(comparison.staleness_warning)

    def test_compare_wizard(self):
        """Test the compare wizard."""
        wizard = self.env["spp.simulation.compare.wizard"].create(
            {
                "run_ids": [Command.set([self.run_a.id, self.run_b.id])],
            }
        )
        result = wizard.action_compare()
        self.assertEqual(result["res_model"], "spp.simulation.comparison")

    def test_compare_wizard_insufficient_runs(self):
        """Test wizard raises error with less than 2 runs."""
        wizard = self.env["spp.simulation.compare.wizard"].create(
            {
                "run_ids": [Command.set([self.run_a.id])],
            }
        )
        with self.assertRaises(ValidationError):
            wizard.action_compare()

    def test_overlap_same_scenario_is_100_percent(self):
        """Test that two runs of the same scenario show 100% overlap."""
        # Execute actual simulations (not just create runs with fake data)
        service = self.env["spp.simulation.service"].with_user(self.user_officer)
        run_1 = service.execute_simulation(self.scenario)
        run_2 = service.execute_simulation(self.scenario)

        # Both should have same beneficiary count since same targeting expression
        self.assertEqual(
            run_1.beneficiary_count,
            run_2.beneficiary_count,
            "Same scenario should produce same beneficiary count",
        )

        # Create comparison and compute overlap
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": "Same Scenario Overlap Test",
                "run_ids": [Command.set([run_1.id, run_2.id])],
            }
        )
        comparison.action_compute_comparison()

        # Check overlap data
        self.assertTrue(comparison.overlap_count_json, "Overlap data should be computed")
        overlap_data = list(comparison.overlap_count_json.values())[0]

        # Overlap should equal union (100% similarity) for same scenario
        self.assertEqual(
            overlap_data["overlap_count"],
            overlap_data["union_count"],
            "Same scenario runs should have 100% overlap",
        )
        self.assertAlmostEqual(
            overlap_data["jaccard_index"],
            1.0,
            places=2,
            msg="Jaccard index should be 1.0 (100% similarity) for same scenario",
        )
