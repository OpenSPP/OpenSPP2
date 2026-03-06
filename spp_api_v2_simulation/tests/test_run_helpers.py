# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for run router helper functions and edge cases."""

from datetime import datetime

from odoo.tests import tagged

from .common import SimulationApiTestCase


@tagged("-at_install", "post_install")
class TestRunHelpers(SimulationApiTestCase):
    """Test run helper functions and edge cases."""

    def test_datetime_to_iso_with_datetime(self):
        """Test _datetime_to_iso with a datetime object."""
        from ..routers.run import _datetime_to_iso

        dt = datetime(2024, 6, 15, 10, 30, 0)
        result = _datetime_to_iso(dt)
        self.assertEqual(result, "2024-06-15T10:30:00")

    def test_datetime_to_iso_with_none(self):
        """Test _datetime_to_iso with None."""
        from ..routers.run import _datetime_to_iso

        self.assertIsNone(_datetime_to_iso(None))

    def test_datetime_to_iso_with_false(self):
        """Test _datetime_to_iso with Odoo False."""
        from ..routers.run import _datetime_to_iso

        self.assertIsNone(_datetime_to_iso(False))

    def test_datetime_to_iso_with_string(self):
        """Test _datetime_to_iso with a string (passthrough)."""
        from ..routers.run import _datetime_to_iso

        result = _datetime_to_iso("2024-01-01T00:00:00Z")
        self.assertEqual(result, "2024-01-01T00:00:00Z")

    def test_run_to_summary_with_no_duration(self):
        """Test run to summary when execution_duration_seconds is 0."""
        from ..routers.run import _run_to_summary

        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario_ready.id,
                "state": "completed",
                "beneficiary_count": 3,
                "total_cost": 1500.0,
                "coverage_rate": 30.0,
                "equity_score": 75.0,
                "gini_coefficient": 0.2,
                "executed_at": datetime(2024, 3, 1, 12, 0, 0),
                "execution_duration_seconds": 0.0,
            }
        )

        summary = _run_to_summary(run)
        self.assertIsNone(summary.execution_duration_seconds)

    def test_run_to_response_failed_with_no_error_message(self):
        """Test response for failed run with no error message."""
        from ..routers.run import _run_to_response

        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario_ready.id,
                "state": "failed",
                "beneficiary_count": 0,
                "total_cost": 0.0,
            }
        )

        response = _run_to_response(run, include_details=False)
        self.assertEqual(response.state, "failed")
        self.assertIsNone(response.error_message)

    def test_run_to_response_details_not_loaded_for_failed(self):
        """Test that include_details=True doesn't load details for failed runs."""
        from ..routers.run import _run_to_response

        self.run_failed.distribution_json = {
            "count": 0,
            "total": 0.0,
        }

        response = _run_to_response(self.run_failed, include_details=True)

        # Details should NOT be loaded for failed runs
        self.assertIsNone(response.distribution_data)
        self.assertIsNone(response.fairness_data)

    def test_run_to_response_with_empty_json_fields(self):
        """Test response when JSON fields are empty dicts/lists."""
        from ..routers.run import _run_to_response

        # Empty JSON fields should not create data objects
        self.run_completed.distribution_json = {}
        self.run_completed.fairness_json = {}
        self.run_completed.geographic_json = []
        self.run_completed.metric_results_json = {}

        response = _run_to_response(self.run_completed, include_details=True)

        # Empty dicts/lists are falsy, so data should be None
        self.assertIsNone(response.distribution_data)
        self.assertIsNone(response.fairness_data)
        self.assertIsNone(response.geographic_data)
        self.assertIsNone(response.metric_results)

    def test_run_to_response_with_scenario_snapshot_no_ideal(self):
        """Test scenario snapshot without ideal_population_expression."""
        from ..routers.run import _run_to_response

        self.run_completed.scenario_snapshot_json = {
            "name": "Test",
            "target_type": "group",
            "targeting_expression": "true",
            "budget_amount": 5000.0,
            "budget_strategy": "none",
            "entitlement_rules": [],
        }

        response = _run_to_response(self.run_completed, include_details=True)

        self.assertIsNotNone(response.scenario_snapshot)
        self.assertEqual(response.scenario_snapshot.name, "Test")
        self.assertIsNone(response.scenario_snapshot.ideal_population_expression)
