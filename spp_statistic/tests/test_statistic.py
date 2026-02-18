# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for publishable statistics module."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestStatisticCategory(TransactionCase):
    """Test statistic category model integration.

    Note: Category model tests are in spp_metrics_core/tests/test_metric_category.py
    This class tests the integration between statistics and categories.
    """

    def test_create_category(self):
        """Test creating a metric category (used by statistics)."""
        Category = self.env["spp.metric.category"]

        category = Category.create(
            {
                "name": "Test Category",
                "code": "test_category",
                "description": "A test category",
                "sequence": 100,
            }
        )

        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.code, "test_category")
        self.assertTrue(category.active)

    def test_statistic_uses_metric_category(self):
        """Test that statistics can use metric categories."""
        Category = self.env["spp.metric.category"]

        category = Category.create({"name": "Test", "code": "test_cat"})

        # Verify we can assign this category to a statistic
        variable = self.env["spp.cel.variable"].create(
            {
                "name": "test_var",
                "cel_accessor": "test_var",
                "source_type": "computed",
                "cel_expression": "true",
                "state": "active",
            }
        )

        stat = self.env["spp.statistic"].create(
            {
                "name": "test_stat",
                "label": "Test Stat",
                "variable_id": variable.id,
                "category_id": category.id,
            }
        )

        self.assertEqual(stat.category_id, category)


class TestStatistic(TransactionCase):
    """Test statistic model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create a CEL variable for testing
        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "test_cel_var",
                "cel_accessor": "test_var",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",
                "value_type": "number",
                "applies_to": "group",
                "state": "active",
            }
        )

        # Create a category
        cls.category = cls.env["spp.metric.category"].create(
            {
                "name": "Test Category",
                "code": "test",
            }
        )

    def test_create_statistic(self):
        """Test creating a statistic."""
        Statistic = self.env["spp.statistic"]

        stat = Statistic.create(
            {
                "name": "test_stat",
                "label": "Test Statistic",
                "variable_id": self.cel_variable.id,
                "format": "count",
                "category_id": self.category.id,
                "is_published_gis": True,
                "is_published_dashboard": True,
            }
        )

        self.assertEqual(stat.name, "test_stat")
        self.assertEqual(stat.label, "Test Statistic")
        self.assertTrue(stat.is_published_gis)
        self.assertTrue(stat.is_published_dashboard)
        self.assertFalse(stat.is_published_api)

    def test_name_format_validation(self):
        """Test that statistic names must be snake_case."""
        Statistic = self.env["spp.statistic"]

        # Valid names
        stat = Statistic.create(
            {
                "name": "valid_name_123",
                "label": "Valid",
                "variable_id": self.cel_variable.id,
            }
        )
        self.assertTrue(stat.id)

        # Invalid: uppercase
        with self.assertRaises(ValidationError):
            Statistic.create(
                {
                    "name": "Invalid_Name",
                    "label": "Invalid",
                    "variable_id": self.cel_variable.id,
                }
            )

        # Invalid: starts with number
        with self.assertRaises(ValidationError):
            Statistic.create(
                {
                    "name": "123_invalid",
                    "label": "Invalid",
                    "variable_id": self.cel_variable.id,
                }
            )

    def test_get_published_for_context(self):
        """Test querying statistics by context."""
        Statistic = self.env["spp.statistic"]

        # Create statistics with different publication flags
        stat_gis = Statistic.create(
            {
                "name": "gis_only",
                "label": "GIS Only",
                "variable_id": self.cel_variable.id,
                "is_published_gis": True,
            }
        )
        stat_dashboard = Statistic.create(
            {
                "name": "dashboard_only",
                "label": "Dashboard Only",
                "variable_id": self.cel_variable.id,
                "is_published_dashboard": True,
            }
        )
        stat_both = Statistic.create(
            {
                "name": "both_contexts",
                "label": "Both",
                "variable_id": self.cel_variable.id,
                "is_published_gis": True,
                "is_published_dashboard": True,
            }
        )

        # Query GIS statistics
        gis_stats = Statistic.get_published_for_context("gis")
        self.assertIn(stat_gis, gis_stats)
        self.assertIn(stat_both, gis_stats)
        self.assertNotIn(stat_dashboard, gis_stats)

        # Query dashboard statistics
        dashboard_stats = Statistic.get_published_for_context("dashboard")
        self.assertIn(stat_dashboard, dashboard_stats)
        self.assertIn(stat_both, dashboard_stats)
        self.assertNotIn(stat_gis, dashboard_stats)

    def test_get_published_by_category(self):
        """Test grouping statistics by category."""
        Statistic = self.env["spp.statistic"]

        cat2 = self.env["spp.metric.category"].create({"name": "Second", "code": "second"})

        Statistic.create(
            {
                "name": "cat1_stat",
                "label": "Cat 1 Stat",
                "variable_id": self.cel_variable.id,
                "category_id": self.category.id,
                "is_published_gis": True,
            }
        )
        Statistic.create(
            {
                "name": "cat2_stat",
                "label": "Cat 2 Stat",
                "variable_id": self.cel_variable.id,
                "category_id": cat2.id,
                "is_published_gis": True,
            }
        )

        grouped = Statistic.get_published_by_category("gis")

        self.assertIn("test", grouped)
        self.assertIn("second", grouped)

    def test_to_dict(self):
        """Test dictionary conversion for API."""
        Statistic = self.env["spp.statistic"]

        stat = Statistic.create(
            {
                "name": "dict_test",
                "label": "Dict Test",
                "description": "Test description",
                "variable_id": self.cel_variable.id,
                "format": "count",
                "unit": "people",
                "category_id": self.category.id,
            }
        )

        data = stat.to_dict()

        self.assertEqual(data["name"], "dict_test")
        self.assertEqual(data["label"], "Dict Test")
        self.assertEqual(data["format"], "count")
        self.assertEqual(data["unit"], "people")
        self.assertEqual(data["category"], "test")


class TestStatisticContext(TransactionCase):
    """Test statistic context configuration."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.cel_variable = cls.env["spp.cel.variable"].create(
            {
                "name": "context_test_var",
                "cel_accessor": "context_test",
                "source_type": "computed",
                "cel_expression": "true",
                "value_type": "number",
                "state": "active",
            }
        )

        cls.statistic = cls.env["spp.statistic"].create(
            {
                "name": "context_test_stat",
                "label": "Default Label",
                "variable_id": cls.cel_variable.id,
                "format": "count",
                "is_published_gis": True,
                "is_published_dashboard": True,
            }
        )

    def test_context_override(self):
        """Test that context-specific config overrides defaults."""
        Context = self.env["spp.statistic.context"]

        # Create GIS-specific override
        Context.create(
            {
                "statistic_id": self.statistic.id,
                "context": "gis",
                "label": "GIS Label",
                "format": "sum",
                "group": "custom_group",
            }
        )

        # Get GIS config - should use override
        gis_config = self.statistic.get_context_config("gis")
        self.assertEqual(gis_config["label"], "GIS Label")
        self.assertEqual(gis_config["format"], "sum")
        self.assertEqual(gis_config["group"], "custom_group")

        # Get dashboard config - should use defaults
        dashboard_config = self.statistic.get_context_config("dashboard")
        self.assertEqual(dashboard_config["label"], "Default Label")
        self.assertEqual(dashboard_config["format"], "count")

    def test_context_unique_constraint(self):
        """Test that each statistic can only have one config per context."""
        Context = self.env["spp.statistic.context"]

        Context.create(
            {
                "statistic_id": self.statistic.id,
                "context": "gis",
            }
        )

        # Second context for same statistic should fail due to unique constraint
        # Use a savepoint to avoid polluting the transaction log with expected errors
        with self.assertRaises(Exception) as context_manager:
            with self.env.cr.savepoint():
                Context.create(
                    {
                        "statistic_id": self.statistic.id,
                        "context": "gis",
                    }
                )

        # Verify it was a constraint error
        error_msg = str(context_manager.exception).lower()
        self.assertTrue(
            "unique" in error_msg or "duplicate" in error_msg,
            f"Expected unique constraint error, got: {context_manager.exception}",
        )
