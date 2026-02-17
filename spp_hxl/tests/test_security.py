# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security tests for HXL module access control."""

import logging

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "security")
class TestHxlSecurity(TransactionCase):
    """Test access control for HXL models"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.HxlTag = cls.env["spp.hxl.tag"]
        cls.HxlAttribute = cls.env["spp.hxl.attribute"]
        cls.HxlProfile = cls.env["spp.hxl.export.profile"]

        # Create test users with different access levels
        cls.user_regular = cls.env["res.users"].create(
            {
                "name": "Regular User",
                "login": "hxl_regular_user",
                "email": "regular@test.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

        # Admin user - try to find OpenSPP admin group, fall back to base system admin
        admin_group = cls.env.ref("spp_security.group_spp_admin", raise_if_not_found=False)
        if not admin_group:
            admin_group = cls.env.ref("base.group_system")

        cls.user_admin = cls.env["res.users"].create(
            {
                "name": "Admin User",
                "login": "hxl_admin_user",
                "email": "admin@test.com",
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            admin_group.id,
                        ],
                    )
                ],
            }
        )

        # Create test data
        cls.test_tag = cls.HxlTag.create(
            {
                "hashtag": "#security_test",
                "name": "Security Test Tag",
            }
        )
        cls.test_attr = cls.HxlAttribute.create(
            {
                "code": "+sectest",
                "name": "Security Test Attr",
            }
        )

    def test_regular_user_can_read_tags(self):
        """Test that regular users can read HXL tags"""
        tags = self.HxlTag.with_user(self.user_regular).search([])
        self.assertTrue(len(tags) >= 1)

    def test_regular_user_can_read_attributes(self):
        """Test that regular users can read HXL attributes"""
        attrs = self.HxlAttribute.with_user(self.user_regular).search([])
        self.assertTrue(len(attrs) >= 1)

    def test_regular_user_can_read_profiles(self):
        """Test that regular users can read export profiles"""
        profiles = self.HxlProfile.with_user(self.user_regular).search([])
        # May be empty if no profiles created, but shouldn't raise AccessError
        self.assertIsNotNone(profiles)

    def test_regular_user_cannot_write_tags(self):
        """Test that regular users cannot write to HXL tags"""
        with self.assertRaises(AccessError):
            self.test_tag.with_user(self.user_regular).write({"name": "Modified Name"})

    def test_regular_user_cannot_create_tags(self):
        """Test that regular users cannot create HXL tags"""
        with self.assertRaises(AccessError):
            self.HxlTag.with_user(self.user_regular).create(
                {
                    "hashtag": "#user_created",
                    "name": "User Created Tag",
                }
            )

    def test_regular_user_cannot_delete_tags(self):
        """Test that regular users cannot delete HXL tags"""
        with self.assertRaises(AccessError):
            self.test_tag.with_user(self.user_regular).unlink()

    def test_regular_user_cannot_write_attributes(self):
        """Test that regular users cannot write to HXL attributes"""
        with self.assertRaises(AccessError):
            self.test_attr.with_user(self.user_regular).write({"name": "Modified Name"})

    def test_regular_user_cannot_create_attributes(self):
        """Test that regular users cannot create HXL attributes"""
        with self.assertRaises(AccessError):
            self.HxlAttribute.with_user(self.user_regular).create(
                {
                    "code": "+user_attr",
                    "name": "User Created Attribute",
                }
            )

    def test_admin_has_full_access_to_tags(self):
        """Test that admin users have full CRUD access to tags"""
        # Create
        tag = self.HxlTag.with_user(self.user_admin).create(
            {
                "hashtag": "#admin_tag",
                "name": "Admin Created Tag",
            }
        )
        self.assertTrue(tag)

        # Read
        read_tag = self.HxlTag.with_user(self.user_admin).browse(tag.id)
        self.assertEqual(read_tag.name, "Admin Created Tag")

        # Write
        tag.with_user(self.user_admin).write({"name": "Admin Modified Tag"})
        self.assertEqual(tag.name, "Admin Modified Tag")

        # Delete
        tag.with_user(self.user_admin).unlink()
        self.assertFalse(tag.exists())

    def test_admin_has_full_access_to_attributes(self):
        """Test that admin users have full CRUD access to attributes"""
        # Create
        attr = self.HxlAttribute.with_user(self.user_admin).create(
            {
                "code": "+admin_attr",
                "name": "Admin Created Attr",
            }
        )
        self.assertTrue(attr)

        # Read
        read_attr = self.HxlAttribute.with_user(self.user_admin).browse(attr.id)
        self.assertEqual(read_attr.name, "Admin Created Attr")

        # Write
        attr.with_user(self.user_admin).write({"name": "Admin Modified Attr"})
        self.assertEqual(attr.name, "Admin Modified Attr")

        # Delete
        attr.with_user(self.user_admin).unlink()
        self.assertFalse(attr.exists())

    def test_admin_can_manage_profiles(self):
        """Test that admin users can manage export profiles"""
        # Get an IR model for the profile
        ir_model = self.env["ir.model"].search([("model", "=", "spp.hxl.tag")], limit=1)

        # Create profile
        profile = self.HxlProfile.with_user(self.user_admin).create(
            {
                "name": "Admin Profile",
                "code": "admin_profile",
                "model_id": ir_model.id,
            }
        )
        self.assertTrue(profile)

        # Write
        profile.with_user(self.user_admin).write({"name": "Modified Profile"})
        self.assertEqual(profile.name, "Modified Profile")

        # Delete
        profile.with_user(self.user_admin).unlink()
        self.assertFalse(profile.exists())
