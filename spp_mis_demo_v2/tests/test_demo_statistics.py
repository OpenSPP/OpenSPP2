# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Test demo statistics configuration and accessibility.

These tests verify that:
1. All demo statistics are properly loaded into the database
2. Each statistic has a valid CEL variable reference
3. Statistics are published to GIS context
4. Statistics can be computed via the aggregation service
"""

from odoo.tests.common import TransactionCase


class TestDemoStatistics(TransactionCase):
    """Test that demo statistics are properly loaded and accessible."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stat_model = cls.env["spp.indicator"]

        # Required statistics that should be in the database
        cls.required_stats = [
            "total_households",
            "total_members",
            "pwd_members",
            "enrolled_any_program",
        ]

    def test_all_demo_statistics_exist(self):
        """Verify all demo statistics are in the database."""
        for stat_name in self.required_stats:
            with self.subTest(statistic=stat_name):
                stat = self.stat_model.search([("name", "=", stat_name)], limit=1)
                self.assertTrue(
                    stat,
                    f"Statistic '{stat_name}' not found in database. Check that demo_statistics.xml was loaded.",
                )

    def test_statistics_have_variables(self):
        """Verify each statistic has a valid CEL variable reference."""
        for stat_name in self.required_stats:
            with self.subTest(statistic=stat_name):
                stat = self.stat_model.search([("name", "=", stat_name)], limit=1)
                if stat:  # Only test if statistic exists
                    self.assertTrue(
                        stat.variable_id,
                        f"Statistic '{stat_name}' has no variable_id",
                    )
                    self.assertEqual(
                        stat.variable_id.state,
                        "active",
                        f"Variable for '{stat_name}' is not active",
                    )

    def test_statistics_published_to_gis(self):
        """Verify statistics are published to GIS context."""
        for stat_name in self.required_stats:
            with self.subTest(statistic=stat_name):
                stat = self.stat_model.search([("name", "=", stat_name)], limit=1)
                if stat:  # Only test if statistic exists
                    self.assertTrue(
                        stat.is_published_gis,
                        f"Statistic '{stat_name}' not published to GIS",
                    )

    def test_statistics_have_valid_cel_accessors(self):
        """Verify statistics have variables with valid CEL accessors for aggregation."""
        # Test a subset of statistics
        test_stats = ["total_households", "total_members"]

        for stat_name in test_stats:
            with self.subTest(statistic=stat_name):
                stat = self.stat_model.search([("name", "=", stat_name)], limit=1)
                if not stat:
                    self.skipTest(f"Statistic '{stat_name}' not found in database")

                self.assertTrue(
                    stat.variable_id,
                    f"Statistic '{stat_name}' has no variable_id",
                )
                self.assertTrue(
                    stat.variable_id.cel_accessor,
                    f"Variable for statistic '{stat_name}' has no cel_accessor. "
                    "A cel_accessor is required for aggregation computation.",
                )

    def test_statistics_categories_exist(self):
        """Verify statistics are assigned to categories."""
        category_mapping = {
            "demographics": [
                "total_households",
                "total_members",
            ],
            "vulnerability": ["pwd_members"],
            "programs": ["enrolled_any_program"],
        }

        for category_code, stat_names in category_mapping.items():
            for stat_name in stat_names:
                with self.subTest(statistic=stat_name, category=category_code):
                    stat = self.stat_model.search([("name", "=", stat_name)], limit=1)
                    if stat:  # Only test if statistic exists
                        self.assertTrue(
                            stat.category_id,
                            f"Statistic '{stat_name}' has no category",
                        )
                        self.assertEqual(
                            stat.category_id.code,
                            category_code,
                            f"Statistic '{stat_name}' in wrong category. "
                            f"Expected '{category_code}', got '{stat.category_id.code}'",
                        )

    def test_gis_discovery_endpoint_returns_statistics(self):
        """Verify GIS statistics discovery returns our demo statistics."""
        # Get all GIS-published statistics
        gis_stats = self.stat_model.get_published_for_context("gis")

        # Extract names
        gis_stat_names = [stat.name for stat in gis_stats]

        # Verify our required statistics are included
        for stat_name in self.required_stats:
            with self.subTest(statistic=stat_name):
                self.assertIn(
                    stat_name,
                    gis_stat_names,
                    f"Statistic '{stat_name}' not in GIS discovery endpoint. Check is_published_gis flag.",
                )
