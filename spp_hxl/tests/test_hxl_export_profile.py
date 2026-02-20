import logging

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestHxlExportProfile(TransactionCase):
    """Test cases for HXL Export Profile models"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ExportProfile = cls.env["spp.hxl.export.profile"]
        cls.ExportColumn = cls.env["spp.hxl.export.profile.column"]
        cls.HxlTag = cls.env["spp.hxl.tag"]
        cls.HxlAttribute = cls.env["spp.hxl.attribute"]
        cls.IrModel = cls.env["ir.model"]

        # Get a model to use for testing
        cls.test_model = cls.IrModel.search([("model", "=", "res.partner")], limit=1)

        # Get some standard tags and attributes
        cls.tag_org = cls.HxlTag.search([("hashtag", "=", "#org")], limit=1)
        cls.tag_contact = cls.HxlTag.search([("hashtag", "=", "#contact")], limit=1)
        cls.attr_name = cls.HxlAttribute.search([("code", "=", "+name")], limit=1)
        cls.attr_code = cls.HxlAttribute.search([("code", "=", "+code")], limit=1)

    def test_create_export_profile(self):
        """Test creating a basic export profile"""
        profile = self.ExportProfile.create(
            {
                "name": "Test Profile",
                "code": "test_profile",
                "model_id": self.test_model.id,
            }
        )
        self.assertTrue(profile)
        self.assertEqual(profile.code, "test_profile")
        self.assertEqual(profile.model_name, "res.partner")

    def test_profile_code_uniqueness(self):
        """Test that profile code must be unique"""
        self.ExportProfile.create(
            {
                "name": "Profile 1",
                "code": "unique_profile",
                "model_id": self.test_model.id,
            }
        )
        with self.assertRaises(Exception):  # noqa: B017
            # Should raise constraint violation
            self.ExportProfile.create(
                {
                    "name": "Profile 2",
                    "code": "unique_profile",
                    "model_id": self.test_model.id,
                }
            )

    def test_profile_code_validation(self):
        """Test that profile code can only contain valid characters"""
        # Valid code
        valid_profile = self.ExportProfile.create(
            {
                "name": "Valid Profile",
                "code": "valid_profile_123",
                "model_id": self.test_model.id,
            }
        )
        self.assertTrue(valid_profile)

        # Invalid code with special characters
        with self.assertRaises(ValidationError):
            self.ExportProfile.create(
                {
                    "name": "Invalid Profile",
                    "code": "invalid@profile",
                    "model_id": self.test_model.id,
                }
            )

    def test_profile_default_values(self):
        """Test default values for export profile"""
        profile = self.ExportProfile.create(
            {
                "name": "Default Test",
                "code": "default_test",
                "model_id": self.test_model.id,
            }
        )
        self.assertTrue(profile.include_hxl_row)
        self.assertEqual(profile.date_format, "%Y-%m-%d")
        self.assertTrue(profile.active)
        self.assertEqual(profile.sequence, 10)

    def test_create_profile_with_columns(self):
        """Test creating profile with columns"""
        profile = self.ExportProfile.create(
            {
                "name": "Profile with Columns",
                "code": "profile_cols",
                "model_id": self.test_model.id,
                "column_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Organization Name",
                            "field_path": "name",
                            "hxl_tag": "#org+name",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Organization Code",
                            "field_path": "ref",
                            "hxl_tag": "#org+code",
                        },
                    ),
                ],
            }
        )
        self.assertEqual(len(profile.column_ids), 2)

    def test_column_hxl_tag_manual(self):
        """Test column with manual HXL tag entry"""
        profile = self.ExportProfile.create(
            {
                "name": "Manual Tag Profile",
                "code": "manual_tag",
                "model_id": self.test_model.id,
            }
        )
        column = self.ExportColumn.create(
            {
                "profile_id": profile.id,
                "name": "Test Column",
                "field_path": "name",
                "hxl_tag": "#org+impl+name",
            }
        )
        self.assertEqual(column.computed_hxl_tag, "#org+impl+name")

    def test_column_hxl_tag_from_components(self):
        """Test column with HXL tag built from hashtag and attributes"""
        if not self.tag_org or not self.attr_name or not self.attr_code:
            self.skipTest("Required HXL tags or attributes not found")

        profile = self.ExportProfile.create(
            {
                "name": "Component Tag Profile",
                "code": "component_tag",
                "model_id": self.test_model.id,
            }
        )
        column = self.ExportColumn.create(
            {
                "profile_id": profile.id,
                "name": "Organization",
                "field_path": "name",
                "hxl_hashtag_id": self.tag_org.id,
                "hxl_attribute_ids": [(6, 0, [self.attr_name.id, self.attr_code.id])],
            }
        )
        # Should compute tag from components
        self.assertTrue(column.computed_hxl_tag)
        self.assertIn("#org", column.computed_hxl_tag)
        self.assertIn("+name", column.computed_hxl_tag)
        self.assertIn("+code", column.computed_hxl_tag)

    def test_column_hxl_tag_manual_precedence(self):
        """Test that manual HXL tag takes precedence over components"""
        if not self.tag_org or not self.attr_name:
            self.skipTest("Required HXL tags or attributes not found")

        profile = self.ExportProfile.create(
            {
                "name": "Precedence Profile",
                "code": "precedence",
                "model_id": self.test_model.id,
            }
        )
        column = self.ExportColumn.create(
            {
                "profile_id": profile.id,
                "name": "Test",
                "field_path": "name",
                "hxl_tag": "#manual+tag",
                "hxl_hashtag_id": self.tag_org.id,
                "hxl_attribute_ids": [(6, 0, [self.attr_name.id])],
            }
        )
        # Manual tag should take precedence
        self.assertEqual(column.computed_hxl_tag, "#manual+tag")

    def test_column_sequence(self):
        """Test column sequencing"""
        profile = self.ExportProfile.create(
            {
                "name": "Sequence Profile",
                "code": "sequence_test",
                "model_id": self.test_model.id,
                "column_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Column 1",
                            "field_path": "name",
                            "sequence": 20,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Column 2",
                            "field_path": "email",
                            "sequence": 10,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Column 3",
                            "field_path": "phone",
                            "sequence": 30,
                        },
                    ),
                ],
            }
        )
        # Should be ordered by sequence
        columns = profile.column_ids.sorted("sequence")
        self.assertEqual(columns[0].name, "Column 2")
        self.assertEqual(columns[1].name, "Column 1")
        self.assertEqual(columns[2].name, "Column 3")

    def test_search_profiles_by_model(self):
        """Test searching profiles by model"""
        self.ExportProfile.create(
            {
                "name": "Partner Profile 1",
                "code": "partner_1",
                "model_id": self.test_model.id,
            }
        )
        self.ExportProfile.create(
            {
                "name": "Partner Profile 2",
                "code": "partner_2",
                "model_id": self.test_model.id,
            }
        )

        profiles = self.ExportProfile.search([("model_id", "=", self.test_model.id)])
        self.assertTrue(len(profiles) >= 2)

    def test_archive_profile(self):
        """Test archiving a profile"""
        profile = self.ExportProfile.create(
            {
                "name": "Archive Test",
                "code": "archive_test",
                "model_id": self.test_model.id,
            }
        )
        profile.active = False
        self.assertFalse(profile.active)

        # Archived profiles should not appear in default search
        active_profiles = self.ExportProfile.search([("code", "=", "archive_test")])
        self.assertEqual(len(active_profiles), 0)

    def test_column_update_tag_components(self):
        """Test updating column tag components"""
        if not self.tag_org or not self.tag_contact or not self.attr_name:
            self.skipTest("Required HXL tags or attributes not found")

        profile = self.ExportProfile.create(
            {
                "name": "Update Profile",
                "code": "update_test",
                "model_id": self.test_model.id,
            }
        )
        column = self.ExportColumn.create(
            {
                "profile_id": profile.id,
                "name": "Test Column",
                "field_path": "name",
                "hxl_hashtag_id": self.tag_org.id,
            }
        )

        # Initial tag
        self.assertEqual(column.computed_hxl_tag, "#org")

        # Add attributes
        column.write({"hxl_attribute_ids": [(6, 0, [self.attr_name.id])]})
        self.assertIn("+name", column.computed_hxl_tag)

        # Change hashtag
        column.write({"hxl_hashtag_id": self.tag_contact.id})
        self.assertIn("#contact", column.computed_hxl_tag)
