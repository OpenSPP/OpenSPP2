# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Create Group strategy."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestCreateGroupStrategy(TransactionCase):
    """Tests for Create Group custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]

        # Get head membership kind from vocabulary
        cls.head_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")

        # Get group type from vocabulary
        cls.group_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-type", "household")

        # Create existing individual for head
        cls.existing_head = cls.partner_model.create(
            {
                "name": "Existing Head",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Get CR type - use a dummy registrant since create_group creates the actual group
        cls.dummy_group = cls.partner_model.create(
            {
                "name": "Placeholder",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.cr_type = cls.env.ref(
            "spp_change_request_v2.cr_type_create_group",
            raise_if_not_found=False,
        )

    def test_create_group_basic(self):
        """Test creating new group."""
        if not self.cr_type:
            self.skipTest("Create group CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.dummy_group.id,  # Placeholder
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "group_name": "New Household",
                "group_type_id": self.group_kind.id,
                "address_line1": "123 Main St",
                "city": "Manila",
                "phone": "+63912345678",
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify group created
        self.assertTrue(cr.is_applied)
        self.assertTrue(detail.created_group_id)

        new_group = detail.created_group_id
        self.assertEqual(new_group.name, "New Household")
        self.assertTrue(new_group.is_registrant)
        self.assertTrue(new_group.is_group)
        self.assertEqual(new_group.street, "123 Main St")
        self.assertEqual(new_group.city, "Manila")

    def test_create_group_with_existing_head(self):
        """Test creating group with existing individual as head."""
        if not self.cr_type:
            self.skipTest("Create group CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.dummy_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "group_name": "Group with Head",
                "head_individual_id": self.existing_head.id,
                "create_new_head": False,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify group and membership
        self.assertTrue(cr.is_applied)
        new_group = detail.created_group_id

        membership = self.membership_model.search(
            [
                ("group", "=", new_group.id),
                ("individual", "=", self.existing_head.id),
            ]
        )
        self.assertTrue(membership, "Head should be member of new group")

        if self.head_kind:
            self.assertIn(self.head_kind, membership.membership_type_ids, "Head should have head role")

    def test_create_group_with_new_head(self):
        """Test creating group with new individual as head."""
        if not self.cr_type:
            self.skipTest("Create group CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.dummy_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "group_name": "Group with New Head",
                "create_new_head": True,
                "head_given_name": "Juan",
                "head_family_name": "Dela Cruz",
                "head_name": "Juan Dela Cruz",
                "head_phone": "+63987654321",
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify group and new individual
        self.assertTrue(cr.is_applied)
        new_group = detail.created_group_id

        # Find the new head
        membership = self.membership_model.search(
            [
                ("group", "=", new_group.id),
                ("status", "=", "active"),
            ]
        )
        self.assertTrue(membership)

        new_head = membership.individual
        self.assertEqual(new_head.name, "Juan Dela Cruz")
        self.assertEqual(new_head.given_name, "Juan")
        self.assertEqual(new_head.family_name, "Dela Cruz")
        self.assertTrue(new_head.is_registrant)
        self.assertFalse(new_head.is_group)

    def test_create_group_without_name_fails(self):
        """Test creating group without name fails."""
        if not self.cr_type:
            self.skipTest("Create group CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.dummy_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                # No group_name
                "city": "Manila",
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("name", str(cm.exception).lower())

    def test_create_group_new_head_requires_name(self):
        """Test creating new head requires name."""
        if not self.cr_type:
            self.skipTest("Create group CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.dummy_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "group_name": "Group Without Head Name",
                "create_new_head": True,
                # No head_name
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("head", str(cm.exception).lower())

    def test_create_group_preview(self):
        """Test preview returns expected structure."""
        if not self.cr_type:
            self.skipTest("Create group CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.dummy_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "group_name": "Preview Group",
                "group_type_id": self.group_kind.id,
                "create_new_head": True,
                "head_name": "Head Name",
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "create_group")
        self.assertEqual(preview["group_name"], "Preview Group")
        self.assertTrue(preview["create_new_head"])
