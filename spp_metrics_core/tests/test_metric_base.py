# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMetricBase(TransactionCase):
    """Test the unified metric base model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env["spp.metric.category"].create(
            {
                "name": "Test Category",
                "code": "test_category",
                "sequence": 10,
            }
        )

    def test_metric_base_fields_exist(self):
        """Test that base model shared fields are defined."""
        # Skip if spp_statistic is not installed
        if "spp.statistic" not in self.env:
            self.skipTest("spp_statistic module not installed")

        # Get a concrete model that inherits from metric.base
        # We'll use spp.statistic which should inherit from it
        fields = self.env["spp.statistic"]._fields

        # Identity fields (from base)
        self.assertIn("name", fields, "name field should exist")
        self.assertIn("label", fields, "label field should exist")
        self.assertIn("description", fields, "description field should exist")

        # Presentation fields (from base)
        self.assertIn("unit", fields, "unit field should exist")
        self.assertIn("decimal_places", fields, "decimal_places field should exist")

        # Categorization (from base)
        self.assertIn("category_id", fields, "category_id field should exist")

        # Flags (from base)
        self.assertIn("active", fields, "active field should exist")

        # Metadata (from base)
        self.assertIn("sequence", fields, "sequence field should exist")

        # Note: metric_type, cel_expression, aggregation, format are NOT in base
        # They are defined by concrete models with model-specific selections

    def test_metric_base_inherited_by_statistic(self):
        """Test that spp.statistic inherits from spp.metric.base."""
        # Skip if spp_statistic is not installed
        if "spp.statistic" not in self.env:
            self.skipTest("spp_statistic module not installed")

        # Check if spp.metric.base is in the inheritance chain
        stat_model = self.env["spp.statistic"]
        self.assertIn(
            "spp.metric.base",
            stat_model._inherit if isinstance(stat_model._inherit, list) else [stat_model._inherit],
            "spp.statistic should inherit from spp.metric.base",
        )

    def test_metric_base_default_values(self):
        """Test default field values from base model."""
        # Skip if spp_statistic is not installed
        if "spp.statistic" not in self.env:
            self.skipTest("spp_statistic module not installed")

        # Create a minimal statistic to test defaults
        # We need a CEL variable first
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_var",
                "label": "Test Variable",
                "source_type": "computed",
                "state": "active",
                "expression": "1 + 1",
            }
        )

        stat = self.env["spp.statistic"].create(
            {
                "name": "test_metric",
                "label": "Test Metric",
                "variable_id": variable.id,
            }
        )

        # Test defaults from base model
        self.assertTrue(stat.active, "active should default to True")
        self.assertEqual(stat.sequence, 10, "sequence should default to 10")
        self.assertEqual(stat.decimal_places, 0, "decimal_places should default to 0")

    def test_metric_base_category_assignment(self):
        """Test that metrics can be assigned to categories."""
        # Skip if spp_statistic is not installed
        if "spp.statistic" not in self.env:
            self.skipTest("spp_statistic module not installed")

        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_var_2",
                "label": "Test Variable 2",
                "source_type": "computed",
                "state": "active",
                "expression": "2 + 2",
            }
        )

        stat = self.env["spp.statistic"].create(
            {
                "name": "test_metric_2",
                "label": "Test Metric 2",
                "variable_id": variable.id,
                "category_id": self.category.id,
            }
        )

        self.assertEqual(
            stat.category_id,
            self.category,
            "Metric should be assigned to category",
        )
