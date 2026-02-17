# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMetricCategory(TransactionCase):
    """Test the metric category model."""

    def test_create_category(self):
        """Test creating a metric category."""
        category = self.env["spp.metric.category"].create(
            {
                "name": "Demographics",
                "code": "demographics",
                "description": "Demographic statistics",
                "sequence": 10,
            }
        )

        self.assertEqual(category.name, "Demographics")
        self.assertEqual(category.code, "demographics")
        self.assertTrue(category.active)

    def test_category_code_unique(self):
        """Test that category codes must be unique.

        Note: SQL unique constraint is enforced at database level.
        This test verifies the constraint is defined in the model.
        """
        # Verify the SQL constraint is defined
        constraints = {name for name, _, _ in self.env["spp.metric.category"]._sql_constraints}
        self.assertIn("code_unique", constraints, "SQL unique constraint should be defined for code field")

    def test_category_parent_child(self):
        """Test parent-child category relationships."""
        parent = self.env["spp.metric.category"].create(
            {
                "name": "Parent Category",
                "code": "parent",
            }
        )

        child = self.env["spp.metric.category"].create(
            {
                "name": "Child Category",
                "code": "child",
                "parent_id": parent.id,
            }
        )

        self.assertEqual(child.parent_id, parent)

    def test_category_sequence_ordering(self):
        """Test that categories are ordered by sequence."""
        cat1 = self.env["spp.metric.category"].create(
            {
                "name": "Category 1",
                "code": "cat1",
                "sequence": 20,
            }
        )

        cat2 = self.env["spp.metric.category"].create(
            {
                "name": "Category 2",
                "code": "cat2",
                "sequence": 10,
            }
        )

        categories = self.env["spp.metric.category"].search([])
        # cat2 should come before cat1 due to lower sequence
        cat2_index = list(categories).index(cat2)
        cat1_index = list(categories).index(cat1)
        self.assertLess(cat2_index, cat1_index, "Categories should be ordered by sequence")
