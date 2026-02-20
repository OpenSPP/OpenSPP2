# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestMetricConstraints(SimulationTestCommon):
    """Tests for spp.simulation.metric constraints."""

    def test_aggregate_metric_without_expression_raises(self):
        """Test that aggregate metric without cel_expression raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.metric"].create(
                {
                    "name": "test_aggregate_metric",
                    "label": "Test Aggregate Metric",
                    "metric_type": "aggregate",
                    "cel_expression": False,  # Missing required field
                    "aggregation": "sum",
                }
            )

    def test_coverage_metric_without_expression_raises(self):
        """Test that coverage metric without cel_expression raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.metric"].create(
                {
                    "name": "test_coverage_metric",
                    "label": "Test Coverage Metric",
                    "metric_type": "coverage",
                    "cel_expression": False,  # Missing required field
                }
            )

    def test_ratio_metric_without_numerator_raises(self):
        """Test that ratio metric without numerator_expression raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.metric"].create(
                {
                    "name": "test_ratio_metric",
                    "label": "Test Ratio Metric",
                    "metric_type": "ratio",
                    "numerator_expression": False,  # Missing required field
                    "denominator_expression": "r.total_population",
                }
            )

    def test_ratio_metric_without_denominator_raises(self):
        """Test that ratio metric without denominator_expression raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.metric"].create(
                {
                    "name": "test_ratio_metric",
                    "label": "Test Ratio Metric",
                    "metric_type": "ratio",
                    "numerator_expression": "r.beneficiary_count",
                    "denominator_expression": False,  # Missing required field
                }
            )

    def test_valid_aggregate_metric_creates(self):
        """Test that valid aggregate metric creates successfully."""
        metric = self.env["spp.simulation.metric"].create(
            {
                "name": "test_aggregate_metric",
                "label": "Test Aggregate Metric",
                "metric_type": "aggregate",
                "cel_expression": "r.income",
                "aggregation": "sum",
            }
        )
        self.assertTrue(metric.exists())
        self.assertEqual(metric.metric_type, "aggregate")
        self.assertEqual(metric.cel_expression, "r.income")
        self.assertEqual(metric.aggregation, "sum")

    def test_valid_coverage_metric_creates(self):
        """Test that valid coverage metric creates successfully."""
        metric = self.env["spp.simulation.metric"].create(
            {
                "name": "test_coverage_metric",
                "label": "Test Coverage Metric",
                "metric_type": "coverage",
                "cel_expression": "r.is_eligible == true",
            }
        )
        self.assertTrue(metric.exists())
        self.assertEqual(metric.metric_type, "coverage")
        self.assertEqual(metric.cel_expression, "r.is_eligible == true")

    def test_valid_ratio_metric_creates(self):
        """Test that valid ratio metric creates successfully."""
        metric = self.env["spp.simulation.metric"].create(
            {
                "name": "test_ratio_metric",
                "label": "Test Ratio Metric",
                "metric_type": "ratio",
                "numerator_expression": "r.beneficiary_count",
                "denominator_expression": "r.total_population",
            }
        )
        self.assertTrue(metric.exists())
        self.assertEqual(metric.metric_type, "ratio")
        self.assertEqual(metric.numerator_expression, "r.beneficiary_count")
        self.assertEqual(metric.denominator_expression, "r.total_population")

    def test_metric_archive(self):
        """Test that metric can be archived."""
        metric = self.env["spp.simulation.metric"].create(
            {
                "name": "test_metric",
                "label": "Test Metric",
                "metric_type": "aggregate",
                "cel_expression": "r.value",
            }
        )
        metric.active = False
        self.assertFalse(metric.active)
