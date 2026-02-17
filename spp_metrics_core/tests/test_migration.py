# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMigration(TransactionCase):
    """Test migration from spp.statistic.category to spp.metric.category."""

    def test_metric_category_table_exists(self):
        """Test that spp_metric_category table exists."""
        self.env.cr.execute(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'spp_metric_category'
            )
        """
        )
        exists = self.env.cr.fetchone()[0]
        self.assertTrue(exists, "spp_metric_category table should exist")

    def test_metric_category_sequence_exists(self):
        """Test that spp_metric_category_id_seq sequence exists."""
        self.env.cr.execute(
            """
            SELECT EXISTS (
                SELECT FROM pg_class
                WHERE relname = 'spp_metric_category_id_seq'
                AND relkind = 'S'
            )
        """
        )
        exists = self.env.cr.fetchone()[0]
        self.assertTrue(exists, "spp_metric_category_id_seq sequence should exist")

    def test_default_categories_loaded(self):
        """Test that default metric categories are loaded."""
        categories = self.env["spp.metric.category"].search([])

        # Check for expected default categories
        category_codes = categories.mapped("code")

        expected_codes = ["population", "coverage", "targeting", "distribution"]
        for code in expected_codes:
            self.assertIn(
                code,
                category_codes,
                f"Default category '{code}' should be loaded",
            )
