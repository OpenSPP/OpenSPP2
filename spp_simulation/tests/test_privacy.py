# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestPrivacy(SimulationTestCommon):
    """Tests to verify no individual beneficiary data is stored in run records.

    This is a critical privacy requirement: only aggregated counts, percentages,
    and metrics should be persisted. No partner_id, names, or individual amounts.
    """

    def _create_completed_run(self):
        """Create a completed run with full data for privacy inspection."""
        return self.env["spp.simulation.run"].create(
            {
                "scenario_id": self.scenario.id,
                "state": "completed",
                "beneficiary_count": 50,
                "total_registry_count": 500,
                "coverage_rate": 10.0,
                "total_cost": 50000.0,
                "budget_utilization": 100.0,
                "gini_coefficient": 0.12,
                "equity_score": 82.0,
                "has_disparity": False,
                "distribution_json": {
                    "count": 50,
                    "total": 50000.0,
                    "minimum": 800.0,
                    "maximum": 1200.0,
                    "mean": 1000.0,
                    "median": 1000.0,
                    "gini_coefficient": 0.12,
                    "percentiles": {"p10": 850, "p25": 900, "p50": 1000, "p75": 1100, "p90": 1150},
                    "lorenz_deciles": [
                        {"population_share": 10, "income_share": 8.5},
                    ],
                },
                "fairness_json": {
                    "equity_score": 82.0,
                    "has_disparity": False,
                    "attributes": {
                        "gender": {
                            "groups": [
                                {
                                    "key": "female",
                                    "label": "Female",
                                    "population": 250,
                                    "beneficiaries": 26,
                                    "coverage": 10.4,
                                    "disparity_ratio": 1.04,
                                    "status": "fair",
                                },
                            ],
                        },
                    },
                },
                "geographic_json": {
                    "1": {"name": "Test Area", "count": 50, "amount": 50000},
                },
            }
        )

    def test_no_partner_ids_in_run(self):
        """Test that no partner_id field exists on simulation.run."""
        run_model = self.env["spp.simulation.run"]
        self.assertNotIn(
            "partner_id",
            run_model._fields,
            "Run model must NOT have a partner_id field",
        )
        self.assertNotIn(
            "partner_ids",
            run_model._fields,
            "Run model must NOT have a partner_ids field",
        )
        self.assertNotIn(
            "beneficiary_ids",
            run_model._fields,
            "Run model must NOT have a beneficiary_ids field",
        )

    def test_no_individual_data_in_distribution_json(self):
        """Test that distribution JSON contains only aggregated data."""
        run = self._create_completed_run()
        distribution = run.distribution_json
        self.assertIsInstance(distribution, dict)
        # Check that no individual IDs or names appear
        json_str = json.dumps(distribution)
        self.assertNotIn("partner_id", json_str)
        self.assertNotIn("name", json_str.lower().split("scenario")[0])

    def test_no_individual_data_in_fairness_json(self):
        """Test that fairness JSON contains only aggregated counts."""
        run = self._create_completed_run()
        fairness = run.fairness_json
        json_str = json.dumps(fairness)
        self.assertNotIn("partner_id", json_str)
        # Should have counts, not lists of IDs
        for attr_data in fairness.get("attributes", {}).values():
            for group in attr_data.get("groups", []):
                self.assertIsInstance(
                    group.get("beneficiaries", 0),
                    int,
                    "Beneficiary data should be a count, not a list",
                )

    def test_no_individual_data_in_geographic_json(self):
        """Test that geographic JSON contains only aggregated data."""
        run = self._create_completed_run()
        geographic = run.geographic_json
        json_str = json.dumps(geographic)
        self.assertNotIn("partner_id", json_str)

    def test_run_fields_are_scalar(self):
        """Test that headline fields on runs are scalar (not relational)."""
        run = self._create_completed_run()
        # These should all be scalar values, not recordsets
        self.assertIsInstance(run.beneficiary_count, int)
        self.assertIsInstance(run.total_cost, float)
        self.assertIsInstance(run.coverage_rate, float)
        self.assertIsInstance(run.equity_score, float)
        self.assertIsInstance(run.gini_coefficient, float)
