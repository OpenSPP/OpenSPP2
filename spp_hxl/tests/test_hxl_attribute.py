# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Test cases for HXL Attribute model."""

import logging

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestHxlAttribute(TransactionCase):
    """Test cases for HXL Attribute model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HxlAttribute = cls.env["spp.hxl.attribute"]

    def test_create_hxl_attribute(self):
        """Test creating a basic HXL attribute"""
        attr = self.HxlAttribute.create(
            {
                "code": "+test_attr",
                "name": "Test Attribute",
                "category": "data_type",
                "is_standard": False,
            }
        )
        self.assertTrue(attr)
        self.assertEqual(attr.code, "+test_attr")
        self.assertEqual(attr.name, "Test Attribute")
        self.assertEqual(attr.category, "data_type")

    def test_code_uniqueness(self):
        """Test that attribute code must be unique"""
        self.HxlAttribute.create(
            {
                "code": "+unique_attr",
                "name": "Unique Attribute",
            }
        )
        with self.assertRaises(Exception):
            # Should raise constraint violation
            self.HxlAttribute.create(
                {
                    "code": "+unique_attr",
                    "name": "Duplicate Attribute",
                }
            )

    def test_code_format_validation_must_start_with_plus(self):
        """Test that attribute code must start with +"""
        with self.assertRaises(ValidationError):
            self.HxlAttribute.create(
                {
                    "code": "invalid_attr",  # Missing +
                    "name": "Invalid Attribute",
                }
            )

    def test_code_character_validation(self):
        """Test that attribute code can only contain valid characters"""
        # Valid characters: alphanumeric, underscore, dash
        valid_attr = self.HxlAttribute.create(
            {
                "code": "+valid_attr-123",
                "name": "Valid Attribute",
            }
        )
        self.assertTrue(valid_attr)

        # Invalid characters
        with self.assertRaises(ValidationError):
            self.HxlAttribute.create(
                {
                    "code": "+invalid@attr",  # Contains @
                    "name": "Invalid Attribute",
                }
            )

    def test_code_empty_after_plus_raises_error(self):
        """Test that code with only + raises error"""
        with self.assertRaises(ValidationError):
            self.HxlAttribute.create(
                {
                    "code": "+",  # Only +
                    "name": "Empty Attribute",
                }
            )

    def test_default_values(self):
        """Test default values for HXL attribute"""
        attr = self.HxlAttribute.create(
            {
                "code": "+default_test",
                "name": "Default Test",
            }
        )
        self.assertTrue(attr.is_standard)
        self.assertTrue(attr.active)

    def test_search_by_category(self):
        """Test searching attributes by category"""
        self.HxlAttribute.create(
            {
                "code": "+gender_test",
                "name": "Gender Test",
                "category": "gender",
            }
        )
        self.HxlAttribute.create(
            {
                "code": "+age_test",
                "name": "Age Test",
                "category": "age",
            }
        )

        gender_attrs = self.HxlAttribute.search([("category", "=", "gender")])
        self.assertTrue(len(gender_attrs) >= 1)
        self.assertTrue(all(attr.category == "gender" for attr in gender_attrs))

    def test_archive_attribute(self):
        """Test archiving an attribute"""
        attr = self.HxlAttribute.create(
            {
                "code": "+archive_test",
                "name": "Archive Test",
            }
        )
        attr.active = False
        self.assertFalse(attr.active)

        # Archived attributes should not appear in default search
        active_attrs = self.HxlAttribute.search([("code", "=", "+archive_test")])
        self.assertEqual(len(active_attrs), 0)

        # But should be findable with active_test=False
        all_attrs = self.HxlAttribute.with_context(active_test=False).search([("code", "=", "+archive_test")])
        self.assertEqual(len(all_attrs), 1)

    def test_standard_attributes_loaded(self):
        """Test that standard HXL attributes are loaded from data"""
        # Check for some standard attributes that should be loaded
        female_attr = self.HxlAttribute.search([("code", "=", "+f")])
        self.assertTrue(female_attr)
        self.assertTrue(female_attr.is_standard)
        self.assertEqual(female_attr.category, "gender")

        children_attr = self.HxlAttribute.search([("code", "=", "+children")])
        self.assertTrue(children_attr)
        self.assertTrue(children_attr.is_standard)
        self.assertEqual(children_attr.category, "age")

    def test_code_update_after_creation(self):
        """Test that updating code maintains uniqueness constraint"""
        attr1 = self.HxlAttribute.create(
            {
                "code": "+attr_one",
                "name": "Attribute One",
            }
        )
        attr2 = self.HxlAttribute.create(
            {
                "code": "+attr_two",
                "name": "Attribute Two",
            }
        )

        # Should be able to update to a unique value
        attr1.code = "+attr_one_updated"
        self.assertEqual(attr1.code, "+attr_one_updated")

        # Should not be able to update to an existing value
        with self.assertRaises(Exception):
            attr2.code = "+attr_one_updated"

    def test_attribute_with_special_characters_fails(self):
        """Test that special characters in attribute code raise error"""
        invalid_codes = ["+test!", "+test#", "+test$", "+test%", "+test^"]
        for code in invalid_codes:
            with self.assertRaises(ValidationError):
                self.HxlAttribute.create(
                    {
                        "code": code,
                        "name": f"Invalid {code}",
                    }
                )

    def test_description_field_stored_correctly(self):
        """Test that description field stores correctly"""
        description = "This is a detailed description of the attribute."
        attr = self.HxlAttribute.create(
            {
                "code": "+desc_test",
                "name": "Description Test",
                "description": description,
            }
        )
        self.assertEqual(attr.description, description)
