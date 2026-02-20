# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestCustomMetrics(SimulationTestCommon):
    """Tests for spp.simulation.metric model."""

    def test_create_aggregate_metric(self):
        """Test creating an aggregate metric."""
        metric = self.env["spp.simulation.metric"].create(
            {
                "name": "test_aggregate",
                "label": "Test Aggregate",
                "metric_type": "aggregate",
                "cel_expression": "r.age >= 60",
                "aggregation": "count",
            }
        )
        self.assertEqual(metric.metric_type, "aggregate")
        self.assertTrue(metric.active)

    def test_create_coverage_metric(self):
        """Test creating a coverage metric."""
        metric = self.env["spp.simulation.metric"].create(
            {
                "name": "test_coverage",
                "label": "Test Coverage",
                "metric_type": "coverage",
                "cel_expression": "r.gender == 'Female'",
            }
        )
        self.assertEqual(metric.metric_type, "coverage")

    def test_create_ratio_metric(self):
        """Test creating a ratio metric."""
        metric = self.env["spp.simulation.metric"].create(
            {
                "name": "test_ratio",
                "label": "Test Ratio",
                "metric_type": "ratio",
                "numerator_expression": "r.gender == 'Female'",
                "denominator_expression": "true",
            }
        )
        self.assertEqual(metric.metric_type, "ratio")

    def test_aggregate_requires_expression(self):
        """Test that aggregate metrics require a CEL expression."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.metric"].create(
                {
                    "name": "invalid_aggregate",
                    "label": "Invalid Aggregate",
                    "metric_type": "aggregate",
                    "cel_expression": False,
                }
            )

    def test_ratio_requires_both_expressions(self):
        """Test that ratio metrics require both numerator and denominator."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.metric"].create(
                {
                    "name": "invalid_ratio",
                    "label": "Invalid Ratio",
                    "metric_type": "ratio",
                    "numerator_expression": "true",
                    "denominator_expression": False,
                }
            )

    def test_all_aggregation_types(self):
        """Test all aggregation types can be set."""
        aggregation_types = ["count", "sum", "avg", "min", "max"]
        for agg in aggregation_types:
            metric = self.env["spp.simulation.metric"].create(
                {
                    "name": f"test_{agg}",
                    "label": f"Test {agg}",
                    "metric_type": "aggregate",
                    "cel_expression": "true",
                    "aggregation": agg,
                }
            )
            self.assertEqual(metric.aggregation, agg)
