# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Add Member strategy."""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestAddMemberStrategy(TransactionCase):
    """Tests for Add Member custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.cr_model = cls.env["spp.change.request"]

        # Create test group
        cls.group = cls.partner_model.create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create test individual (for non-group test)
        cls.individual = cls.partner_model.create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Get or create CR type
        cls.cr_type = get_or_create_cr_type(cls.env, "add_member")

    def test_add_member_creates_individual(self):
        """Test adding member creates individual registrant."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        # Fill detail
        detail = cr.get_detail()
        detail.write(
            {
                "given_name": "Maria",
                "family_name": "Santos",
                "member_name": "Maria Santos",
            }
        )

        # Approve and apply
        cr.approval_state = "approved"
        cr.action_apply()

        # Verify individual created
        self.assertTrue(cr.is_applied)
        self.assertTrue(detail.created_individual_id)

        new_member = detail.created_individual_id
        self.assertEqual(new_member.given_name, "Maria")
        self.assertEqual(new_member.family_name, "Santos")
        self.assertTrue(new_member.is_registrant)
        self.assertFalse(new_member.is_group)

    def test_add_member_creates_membership(self):
        """Test membership link created."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "given_name": "Juan",
                "family_name": "Cruz",
                "member_name": "Juan Cruz",
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Check membership exists
        new_member = detail.created_individual_id
        membership = self.env["spp.group.membership"].search(
            [
                ("group", "=", self.group.id),
                ("individual", "=", new_member.id),
            ]
        )
        self.assertTrue(membership, "Membership should be created")

    def test_add_member_to_individual_fails(self):
        """Test adding member to individual registrant fails."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,  # Individual, not group
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "given_name": "Test",
                "family_name": "Member",
                "member_name": "Test Member",
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("group", str(cm.exception).lower())

    def test_add_member_preview(self):
        """Test preview returns expected structure."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "given_name": "Preview",
                "family_name": "Test",
                "member_name": "Preview Test",
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "create_member")
