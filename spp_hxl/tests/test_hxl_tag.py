import logging

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestHxlTag(TransactionCase):
    """Test cases for HXL Tag model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HxlTag = cls.env["spp.hxl.tag"]

    def test_create_hxl_tag(self):
        """Test creating a basic HXL tag"""
        tag = self.HxlTag.create(
            {
                "hashtag": "#test_tag",
                "name": "Test Tag",
                "category": "metadata",
                "data_type": "text",
                "is_standard": False,
            }
        )
        self.assertTrue(tag)
        self.assertEqual(tag.hashtag, "#test_tag")
        self.assertEqual(tag.name, "Test Tag")
        self.assertEqual(tag.category, "metadata")

    def test_hashtag_uniqueness(self):
        """Test that hashtag must be unique"""
        self.HxlTag.create(
            {
                "hashtag": "#unique_tag",
                "name": "Unique Tag",
            }
        )
        with self.assertRaises(Exception):  # noqa: B017
            # Should raise constraint violation
            self.HxlTag.create(
                {
                    "hashtag": "#unique_tag",
                    "name": "Duplicate Tag",
                }
            )

    def test_hashtag_format_validation(self):
        """Test that hashtag must start with #"""
        with self.assertRaises(ValidationError):
            self.HxlTag.create(
                {
                    "hashtag": "invalid_tag",  # Missing #
                    "name": "Invalid Tag",
                }
            )

    def test_hashtag_character_validation(self):
        """Test that hashtag can only contain valid characters"""
        # Valid characters: alphanumeric, underscore, dash
        valid_tag = self.HxlTag.create(
            {
                "hashtag": "#valid_tag-123",
                "name": "Valid Tag",
            }
        )
        self.assertTrue(valid_tag)

        # Invalid characters
        with self.assertRaises(ValidationError):
            self.HxlTag.create(
                {
                    "hashtag": "#invalid@tag",  # Contains @
                    "name": "Invalid Tag",
                }
            )

    def test_default_values(self):
        """Test default values for HXL tag"""
        tag = self.HxlTag.create(
            {
                "hashtag": "#default_test",
                "name": "Default Test",
            }
        )
        self.assertTrue(tag.is_standard)
        self.assertTrue(tag.active)
        self.assertEqual(tag.data_type, "text")

    def test_search_by_category(self):
        """Test searching tags by category"""
        self.HxlTag.create(
            {
                "hashtag": "#geo_tag",
                "name": "Geographic Tag",
                "category": "geographic",
            }
        )
        self.HxlTag.create(
            {
                "hashtag": "#pop_tag",
                "name": "Population Tag",
                "category": "population",
            }
        )

        geo_tags = self.HxlTag.search([("category", "=", "geographic")])
        self.assertTrue(len(geo_tags) >= 1)
        self.assertTrue(all(tag.category == "geographic" for tag in geo_tags))

    def test_archive_tag(self):
        """Test archiving a tag"""
        tag = self.HxlTag.create(
            {
                "hashtag": "#archive_test",
                "name": "Archive Test",
            }
        )
        tag.active = False
        self.assertFalse(tag.active)

        # Archived tags should not appear in default search
        active_tags = self.HxlTag.search([("hashtag", "=", "#archive_test")])
        self.assertEqual(len(active_tags), 0)

        # But should be findable with active_test=False
        all_tags = self.HxlTag.with_context(active_test=False).search([("hashtag", "=", "#archive_test")])
        self.assertEqual(len(all_tags), 1)

    def test_standard_tags_loaded(self):
        """Test that standard HXL tags are loaded from data"""
        # Check for some standard tags that should be loaded
        affected_tag = self.HxlTag.search([("hashtag", "=", "#affected")])
        self.assertTrue(affected_tag)
        self.assertTrue(affected_tag.is_standard)
        self.assertEqual(affected_tag.category, "population")

        adm2_tag = self.HxlTag.search([("hashtag", "=", "#adm2")])
        self.assertTrue(adm2_tag)
        self.assertTrue(adm2_tag.is_standard)
        self.assertEqual(adm2_tag.category, "geographic")
