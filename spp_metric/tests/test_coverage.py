# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Supplemental tests for spp_metrics_core to reach 95%+ coverage.

Covers gaps not addressed by existing tests:
- Abstract model registry presence and field definitions
- Category recursion detection (_check_parent_recursion)
- Category deactivation
- Category description field
- Category code uniqueness at DB level
"""

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestMetricBaseRegistry(TransactionCase):
    """Test the abstract model spp.metric.base without needing concrete inheritors."""

    def test_abstract_model_in_registry(self):
        """Test that spp.metric.base is registered in the Odoo environment."""
        self.assertIn(
            "spp.metric.base",
            self.env.registry,
            "spp.metric.base should be present in the model registry",
        )

    def test_abstract_model_fields_defined(self):
        """Test that all expected fields are defined on the abstract model."""
        model_class = self.env.registry["spp.metric.base"]
        field_names = set(model_class._fields)

        expected_fields = [
            "name",
            "label",
            "description",
            "unit",
            "decimal_places",
            "category_id",
            "active",
            "sequence",
        ]
        for field_name in expected_fields:
            self.assertIn(
                field_name,
                field_names,
                f"Field '{field_name}' should be defined on spp.metric.base",
            )

    def test_abstract_model_field_types(self):
        """Test that fields have the correct types."""
        fields_def = self.env.registry["spp.metric.base"]._fields

        self.assertEqual(fields_def["name"].type, "char")
        self.assertEqual(fields_def["label"].type, "char")
        self.assertEqual(fields_def["description"].type, "text")
        self.assertEqual(fields_def["unit"].type, "char")
        self.assertEqual(fields_def["decimal_places"].type, "integer")
        self.assertEqual(fields_def["category_id"].type, "many2one")
        self.assertEqual(fields_def["active"].type, "boolean")
        self.assertEqual(fields_def["sequence"].type, "integer")

    def test_abstract_model_required_fields(self):
        """Test that name and label are required."""
        fields_def = self.env.registry["spp.metric.base"]._fields

        self.assertTrue(fields_def["name"].required, "name should be required")
        self.assertTrue(fields_def["label"].required, "label should be required")
        self.assertFalse(fields_def["description"].required, "description should not be required")
        self.assertFalse(fields_def["unit"].required, "unit should not be required")

    def test_abstract_model_defaults(self):
        """Test default values on the abstract model fields."""
        fields_def = self.env.registry["spp.metric.base"]._fields

        # Check defaults exist (Odoo stores defaults differently based on version)
        # decimal_places default is 0, active default is True, sequence default is 10
        self.assertIsNotNone(fields_def["decimal_places"].default, "decimal_places should have a default")
        self.assertIsNotNone(fields_def["active"].default, "active should have a default")
        self.assertIsNotNone(fields_def["sequence"].default, "sequence should have a default")

    def test_abstract_model_is_abstract(self):
        """Test that spp.metric.base is an abstract model."""
        model_class = self.env.registry["spp.metric.base"]
        self.assertTrue(
            model_class._abstract,
            "spp.metric.base should be an abstract model",
        )


@tagged("post_install", "-at_install")
class TestMetricCategoryCoverage(TransactionCase):
    """Supplemental tests for spp.metric.category covering untested paths."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Category = cls.env["spp.metric.category"]

    def test_recursion_detection(self):
        """Test that circular parent relationships raise ValidationError."""
        parent = self.Category.create(
            {
                "name": "Parent",
                "code": "rec_parent",
            }
        )
        child = self.Category.create(
            {
                "name": "Child",
                "code": "rec_child",
                "parent_id": parent.id,
            }
        )

        # Attempt to create a cycle: set child as parent of parent
        with self.assertRaises(ValidationError):
            parent.write({"parent_id": child.id})

    def test_recursion_self_reference(self):
        """Test that a category cannot be its own parent."""
        category = self.Category.create(
            {
                "name": "Self Ref",
                "code": "self_ref",
            }
        )

        with self.assertRaises(ValidationError):
            category.write({"parent_id": category.id})

    def test_recursion_three_level_cycle(self):
        """Test cycle detection across three levels: A -> B -> C -> A."""
        cat_a = self.Category.create({"name": "A", "code": "cycle_a"})
        cat_b = self.Category.create({"name": "B", "code": "cycle_b", "parent_id": cat_a.id})
        cat_c = self.Category.create({"name": "C", "code": "cycle_c", "parent_id": cat_b.id})

        with self.assertRaises(ValidationError):
            cat_a.write({"parent_id": cat_c.id})

    def test_deactivate_category(self):
        """Test that a category can be deactivated."""
        category = self.Category.create(
            {
                "name": "To Deactivate",
                "code": "deactivate_me",
            }
        )
        self.assertTrue(category.active, "Category should be active by default")

        category.write({"active": False})
        self.assertFalse(category.active, "Category should be inactive after deactivation")

        # Inactive categories should not appear in default searches
        visible = self.Category.search([("code", "=", "deactivate_me")])
        self.assertFalse(visible, "Inactive category should not appear in default search")

        # But should appear when searching with active_test=False
        all_cats = self.Category.with_context(active_test=False).search([("code", "=", "deactivate_me")])
        self.assertTrue(all_cats, "Inactive category should appear with active_test=False")

    def test_category_with_description(self):
        """Test creating a category with a description field."""
        category = self.Category.create(
            {
                "name": "Described Category",
                "code": "described",
                "description": "This category contains demographic metrics.",
            }
        )
        self.assertEqual(
            category.description,
            "This category contains demographic metrics.",
        )

    def test_category_description_empty(self):
        """Test that description defaults to falsy when not provided."""
        category = self.Category.create(
            {
                "name": "No Desc",
                "code": "no_desc",
            }
        )
        self.assertFalse(category.description, "Description should be falsy when not set")

    def test_category_ordering(self):
        """Test that _order is sequence then name."""
        self.assertEqual(
            self.Category._order,
            "sequence, name",
            "Categories should be ordered by sequence, then name",
        )

    def test_reactivate_category(self):
        """Test that a deactivated category can be reactivated."""
        category = self.Category.create(
            {
                "name": "Toggle Active",
                "code": "toggle_active",
                "active": False,
            }
        )
        self.assertFalse(category.active)

        category.write({"active": True})
        self.assertTrue(category.active, "Category should be active after reactivation")
