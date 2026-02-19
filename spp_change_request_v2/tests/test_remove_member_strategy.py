# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Remove Member strategy."""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestRemoveMemberStrategy(TransactionCase):
    """Tests for Remove Member custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]

        # Create test group
        cls.group = cls.partner_model.create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create test individuals
        cls.member1 = cls.partner_model.create(
            {
                "name": "Member One",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.member2 = cls.partner_model.create(
            {
                "name": "Member Two",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create memberships
        cls.membership1 = cls.membership_model.create(
            {
                "group": cls.group.id,
                "individual": cls.member1.id,
                "start_date": fields.Datetime.now(),
            }
        )
        cls.membership2 = cls.membership_model.create(
            {
                "group": cls.group.id,
                "individual": cls.member2.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Get or create CR type
        cls.cr_type = get_or_create_cr_type(cls.env, "remove_member")

    def test_remove_member_ends_membership(self):
        """Test removing member sets ended_date on membership."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": self.membership1.id,
                "end_date": fields.Date.today(),
                "end_reason": "left_household",
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify membership ended
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.membership1.ended_date)
        self.assertEqual(self.membership1.status, "inactive")

    def test_remove_member_inactive_fails(self):
        """Test removing already inactive member fails."""

        # End membership first
        self.membership2.write({"ended_date": fields.Datetime.now()})

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": self.membership2.id,
                "end_date": fields.Date.today(),
                "end_reason": "other",
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("inactive", str(cm.exception).lower())

    def test_remove_member_from_individual_fails(self):
        """Test cannot remove member from individual registrant."""

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.member1.id,  # Individual, not group
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "membership_id": self.membership1.id,
                "end_date": fields.Date.today(),
                "end_reason": "other",
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("group", str(cm.exception).lower())

    def test_remove_member_preview(self):
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
                "membership_id": self.membership1.id,
                "end_date": fields.Date.today(),
                "end_reason": "deceased",
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "remove_member")
        self.assertEqual(preview["reason"], "deceased")

    def test_remove_member_all_reasons(self):
        """Test all removal reasons work correctly."""

        reasons = [
            "left_household",
            "deceased",
            "married_out",
            "migrated",
            "correction",
            "other",
        ]

        for reason in reasons:
            # Create new member for each test
            member = self.partner_model.create(
                {
                    "name": f"Member {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            membership = self.membership_model.create(
                {
                    "group": self.group.id,
                    "individual": member.id,
                    "start_date": fields.Datetime.now(),
                }
            )

            cr = self.cr_model.create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": self.group.id,
                }
            )

            detail = cr.get_detail()
            detail.write(
                {
                    "membership_id": membership.id,
                    "end_date": fields.Date.today(),
                    "end_reason": reason,
                }
            )

            cr.approval_state = "approved"
            cr.action_apply()

            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")
            self.assertEqual(membership.status, "inactive")
