# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Transfer Member strategy."""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type, get_or_create_membership_kind


class TestTransferMemberStrategy(TransactionCase):
    """Tests for Transfer Member custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]

        # Get or create membership kind from vocabulary
        cls.member_kind = get_or_create_membership_kind(cls.env, "other")

        # Create source group
        cls.source_group = cls.partner_model.create(
            {
                "name": "Source Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create target group
        cls.target_group = cls.partner_model.create(
            {
                "name": "Target Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create test individual
        cls.individual = cls.partner_model.create(
            {
                "name": "Transfer Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create membership in source group
        cls.membership = cls.membership_model.create(
            {
                "group": cls.source_group.id,
                "individual": cls.individual.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Get or create CR type
        cls.cr_type = get_or_create_cr_type(cls.env, "transfer_member")

    def test_transfer_member_creates_new_membership(self):
        """Test transferring member creates membership in target group."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": self.membership.id,
                "target_group_id": self.target_group.id,
                "transfer_reason": "marriage",
                "transfer_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify transfer
        self.assertTrue(cr.is_applied)

        # Old membership ended
        self.assertTrue(self.membership.ended_date)
        self.assertEqual(self.membership.status, "inactive")

        # New membership created
        new_membership = self.membership_model.search(
            [
                ("group", "=", self.target_group.id),
                ("individual", "=", self.individual.id),
                ("status", "=", "active"),
            ]
        )
        self.assertTrue(new_membership, "New membership should exist in target group")

    def test_transfer_member_with_role(self):
        """Test transferring member assigns new role."""

        # Create new member
        individual = self.partner_model.create(
            {
                "name": "Role Transfer",
                "is_registrant": True,
                "is_group": False,
            }
        )
        membership = self.membership_model.create(
            {
                "group": self.source_group.id,
                "individual": individual.id,
                "start_date": fields.Datetime.now(),
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": membership.id,
                "target_group_id": self.target_group.id,
                "new_role_id": self.member_kind.id,
                "transfer_reason": "relocation",
                "transfer_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify new membership has role
        new_membership = self.membership_model.search(
            [
                ("group", "=", self.target_group.id),
                ("individual", "=", individual.id),
                ("status", "=", "active"),
            ]
        )
        self.assertIn(self.member_kind, new_membership.membership_type_ids)

    def test_transfer_to_same_group_fails(self):
        """Test cannot transfer to same group."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()

        with self.assertRaises(Exception):  # ValidationError
            detail.write(
                {
                    "membership_id": self.membership.id,
                    "target_group_id": self.source_group.id,  # Same group
                    "transfer_reason": "other",
                    "transfer_date": fields.Date.today(),
                }
            )

    def test_transfer_existing_member_fails(self):
        """Test cannot transfer if already member of target group."""

        # Create individual already in target group
        individual = self.partner_model.create(
            {
                "name": "Already Member",
                "is_registrant": True,
                "is_group": False,
            }
        )
        # Membership in source
        source_membership = self.membership_model.create(
            {
                "group": self.source_group.id,
                "individual": individual.id,
                "start_date": fields.Datetime.now(),
            }
        )
        # Membership in target
        self.membership_model.create(
            {
                "group": self.target_group.id,
                "individual": individual.id,
                "start_date": fields.Datetime.now(),
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": source_membership.id,
                "target_group_id": self.target_group.id,
                "transfer_reason": "other",
                "transfer_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("already", str(cm.exception).lower())

    def test_transfer_inactive_membership_fails(self):
        """Test cannot transfer inactive membership."""

        # Create and end membership
        individual = self.partner_model.create(
            {
                "name": "Inactive Member",
                "is_registrant": True,
                "is_group": False,
            }
        )
        membership = self.membership_model.create(
            {
                "group": self.source_group.id,
                "individual": individual.id,
                "start_date": fields.Datetime.now(),
                "ended_date": fields.Datetime.now(),  # Already ended
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": membership.id,
                "target_group_id": self.target_group.id,
                "transfer_reason": "other",
                "transfer_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("inactive", str(cm.exception).lower())

    def test_transfer_all_reasons(self):
        """Test all transfer reasons work."""

        reasons = [
            "marriage",
            "separation",
            "relocation",
            "household_split",
            "correction",
            "other",
        ]

        for reason in reasons:
            individual = self.partner_model.create(
                {
                    "name": f"Transfer {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            membership = self.membership_model.create(
                {
                    "group": self.source_group.id,
                    "individual": individual.id,
                    "start_date": fields.Datetime.now(),
                }
            )
            target = self.partner_model.create(
                {
                    "name": f"Target {reason}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )

            cr = self.cr_model.create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.source_group.id,
                }
            )

            detail = cr.get_detail()
            detail.write(
                {
                    "membership_id": membership.id,
                    "target_group_id": target.id,
                    "transfer_reason": reason,
                    "transfer_date": fields.Date.today(),
                }
            )

            cr.approval_state = "approved"
            cr.action_apply()

            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")

    def test_transfer_preview(self):
        """Test preview returns expected structure."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": self.membership.id,
                "target_group_id": self.target_group.id,
                "transfer_reason": "marriage",
                "transfer_date": fields.Date.today(),
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "transfer_member")
