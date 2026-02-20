# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestSimulationRun(SimulationTestCommon):
    """Tests for spp.simulation.run model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a completed run for testing
        cls.completed_run = cls.env["spp.simulation.run"].create(
            {
                "scenario_id": cls.scenario.id,
                "state": "completed",
                "beneficiary_count": 100,
                "total_registry_count": 1000,
                "coverage_rate": 10.0,
                "total_cost": 100000.0,
                "budget_utilization": 80.0,
                "gini_coefficient": 0.15,
                "equity_score": 85.0,
                "has_disparity": False,
                "distribution_json": {
                    "count": 100,
                    "total": 100000.0,
                    "minimum": 500.0,
                    "maximum": 1500.0,
                    "mean": 1000.0,
                    "median": 1000.0,
                    "gini_coefficient": 0.15,
                },
                "fairness_json": {
                    "equity_score": 85.0,
                    "has_disparity": False,
                    "attributes": {},
                },
            }
        )

    def test_run_creation(self):
        """Test that runs are created with correct defaults."""
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
            }
        )
        self.assertEqual(run.state, "running")
        self.assertTrue(run.executed_at)

    def test_run_not_deletable(self):
        """Test that runs cannot be deleted (audit compliance)."""
        with self.assertRaises(UserError):
            self.completed_run.unlink()

    def test_summary_html_generated(self):
        """Test that summary_html is computed for completed runs."""
        self.assertTrue(self.completed_run.summary_html)
        self.assertIn("100", self.completed_run.summary_html)
        self.assertIn("Test Scenario", self.completed_run.summary_html)

    def test_distribution_summary_html_generated(self):
        """Test that distribution_summary_html is computed."""
        self.assertTrue(self.completed_run.distribution_summary_html)
        self.assertIn("nearly equal", self.completed_run.distribution_summary_html)

    def test_summary_not_generated_for_running(self):
        """Test that summary is not generated for non-completed runs."""
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "running",
            }
        )
        self.assertFalse(run.summary_html)

    def test_latest_run_computed_on_scenario(self):
        """Test that latest run is correctly computed on scenario."""
        self.assertEqual(self.scenario.latest_run_id, self.completed_run)
        self.assertEqual(self.scenario.latest_beneficiary_count, 100)
        self.assertEqual(self.scenario.latest_equity_score, 85.0)
        self.assertEqual(self.scenario.run_count, 1)

    def test_compare_with_previous_no_previous(self):
        """Test comparing when no previous run exists."""
        with self.assertRaises(UserError):
            self.completed_run.action_compare_with_previous()

    def test_open_comparison_wizard(self):
        """Test opening the comparison wizard action."""
        result = self.completed_run.action_open_comparison_wizard()
        self.assertEqual(result["res_model"], "spp.simulation.compare.wizard")
        self.assertEqual(result["target"], "new")
