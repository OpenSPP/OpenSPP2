# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Split Household strategy."""

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestSplitHouseholdStrategy(TransactionCase):
    """Tests for Split Household custom strategy."""

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

        # Create source group with address
        cls.source_group = cls.partner_model.create(
            {
                "name": "Original Household",
                "is_registrant": True,
                "is_group": True,
                "group_type_id": cls.group_kind.id,
                "street": "100 Original St",
                "city": "Original City",
                "phone": "+63111111111",
            }
        )

        # Create members
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
        cls.member3 = cls.partner_model.create(
            {
                "name": "Member Three",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.member4 = cls.partner_model.create(
            {
                "name": "Member Four",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create memberships
        cls.membership1 = cls.membership_model.create(
            {
                "group": cls.source_group.id,
                "individual": cls.member1.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [Command.link(cls.head_kind.id)] if cls.head_kind else [],
            }
        )
        cls.membership2 = cls.membership_model.create(
            {
                "group": cls.source_group.id,
                "individual": cls.member2.id,
                "start_date": fields.Datetime.now(),
            }
        )
        cls.membership3 = cls.membership_model.create(
            {
                "group": cls.source_group.id,
                "individual": cls.member3.id,
                "start_date": fields.Datetime.now(),
            }
        )
        cls.membership4 = cls.membership_model.create(
            {
                "group": cls.source_group.id,
                "individual": cls.member4.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Get CR type
        cls.cr_type = cls.env.ref(
            "spp_change_request_v2.cr_type_split_household",
            raise_if_not_found=False,
        )

    def test_split_creates_new_group(self):
        """Test splitting creates new group."""
        if not self.cr_type:
            self.skipTest("Split household CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "members_to_split_ids": [(6, 0, [self.membership3.id, self.membership4.id])],
                "new_head_membership_id": self.membership3.id,
                "new_group_name": "Split Household",
                "split_reason": "independence",
                "effective_date": fields.Date.today(),
                "copy_address": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify new group created
        self.assertTrue(cr.is_applied)
        self.assertTrue(detail.created_group_id)

        new_group = detail.created_group_id
        self.assertEqual(new_group.name, "Split Household")
        self.assertTrue(new_group.is_registrant)
        self.assertTrue(new_group.is_group)

    def test_split_copies_address(self):
        """Test splitting copies address from source."""
        if not self.cr_type:
            self.skipTest("Split household CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "members_to_split_ids": [(6, 0, [self.membership3.id])],
                "new_head_membership_id": self.membership3.id,
                "new_group_name": "Address Copy Test",
                "split_reason": "marriage",
                "effective_date": fields.Date.today(),
                "copy_address": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify address copied
        new_group = detail.created_group_id
        self.assertEqual(new_group.street, self.source_group.street)
        self.assertEqual(new_group.city, self.source_group.city)
        self.assertEqual(new_group.phone, self.source_group.phone)

    def test_split_transfers_members(self):
        """Test splitting transfers selected members."""
        if not self.cr_type:
            self.skipTest("Split household CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "members_to_split_ids": [(6, 0, [self.membership3.id, self.membership4.id])],
                "new_head_membership_id": self.membership3.id,
                "new_group_name": "Transfer Test",
                "split_reason": "separation",
                "effective_date": fields.Date.today(),
                "copy_address": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify old memberships ended
        self.assertTrue(self.membership3.ended_date)
        self.assertTrue(self.membership4.ended_date)

        # Verify new memberships created
        new_group = detail.created_group_id
        new_memberships = self.membership_model.search(
            [
                ("group", "=", new_group.id),
                ("status", "=", "active"),
            ]
        )
        self.assertEqual(len(new_memberships), 2)

        members = new_memberships.mapped("individual")
        self.assertIn(self.member3, members)
        self.assertIn(self.member4, members)

    def test_split_assigns_head_role(self):
        """Test splitting assigns head role to new head."""
        if not self.cr_type or not self.head_kind:
            self.skipTest("Split household CR type or head kind not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "members_to_split_ids": [(6, 0, [self.membership3.id])],
                "new_head_membership_id": self.membership3.id,
                "new_group_name": "Head Role Test",
                "split_reason": "relocation",
                "effective_date": fields.Date.today(),
                "copy_address": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify new head has head role
        new_group = detail.created_group_id
        new_head_membership = self.membership_model.search(
            [
                ("group", "=", new_group.id),
                ("individual", "=", self.member3.id),
                ("status", "=", "active"),
            ]
        )
        self.assertIn(self.head_kind, new_head_membership.membership_type_ids)

    def test_split_cannot_move_all_members(self):
        """Test cannot move all members from source group."""
        if not self.cr_type:
            self.skipTest("Split household CR type not found")

        # Create group with only 2 members
        small_group = self.partner_model.create(
            {
                "name": "Small Group",
                "is_registrant": True,
                "is_group": True,
            }
        )
        m1 = self.partner_model.create({"name": "M1", "is_registrant": True, "is_group": False})
        m2 = self.partner_model.create({"name": "M2", "is_registrant": True, "is_group": False})
        mem1 = self.membership_model.create(
            {
                "group": small_group.id,
                "individual": m1.id,
                "start_date": fields.Datetime.now(),
            }
        )
        mem2 = self.membership_model.create(
            {
                "group": small_group.id,
                "individual": m2.id,
                "start_date": fields.Datetime.now(),
            }
        )

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": small_group.id,
            }
        )

        detail = cr.get_detail()

        with self.assertRaises(ValidationError):
            detail.write(
                {
                    "members_to_split_ids": [(6, 0, [mem1.id, mem2.id])],  # All members
                    "new_head_membership_id": mem1.id,
                    "new_group_name": "Invalid Split",
                    "split_reason": "other",
                    "effective_date": fields.Date.today(),
                }
            )

    def test_split_head_must_be_in_split(self):
        """Test new head must be in members to split."""
        if not self.cr_type:
            self.skipTest("Split household CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()

        with self.assertRaises(ValidationError):
            detail.write(
                {
                    "members_to_split_ids": [(6, 0, [self.membership3.id])],
                    "new_head_membership_id": self.membership4.id,  # Not in split list
                    "new_group_name": "Invalid Head",
                    "split_reason": "other",
                    "effective_date": fields.Date.today(),
                }
            )

    def test_split_all_reasons(self):
        """Test all split reasons work."""
        if not self.cr_type:
            self.skipTest("Split household CR type not found")

        reasons = ["marriage", "separation", "independence", "relocation", "correction", "other"]

        for reason in reasons:
            # Create fresh group for each test
            group = self.partner_model.create(
                {
                    "name": f"Group {reason}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
            m1 = self.partner_model.create(
                {
                    "name": f"M1 {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            m2 = self.partner_model.create(
                {
                    "name": f"M2 {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            mem1 = self.membership_model.create(
                {
                    "group": group.id,
                    "individual": m1.id,
                    "start_date": fields.Datetime.now(),
                }
            )
            mem2 = self.membership_model.create(
                {
                    "group": group.id,
                    "individual": m2.id,
                    "start_date": fields.Datetime.now(),
                }
            )

            cr = self.cr_model.create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": group.id,
                }
            )

            detail = cr.get_detail()
            detail.write(
                {
                    "members_to_split_ids": [(6, 0, [mem2.id])],
                    "new_head_membership_id": mem2.id,
                    "new_group_name": f"New {reason}",
                    "split_reason": reason,
                    "effective_date": fields.Date.today(),
                    "copy_address": True,
                }
            )

            cr.approval_state = "approved"
            cr.action_apply()

            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")

    def test_split_preview(self):
        """Test preview returns expected structure."""
        if not self.cr_type:
            self.skipTest("Split household CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.source_group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "members_to_split_ids": [(6, 0, [self.membership3.id, self.membership4.id])],
                "new_head_membership_id": self.membership3.id,
                "new_group_name": "Preview Split",
                "split_reason": "marriage",
                "effective_date": fields.Date.today(),
                "copy_address": True,
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "split_household")
        self.assertEqual(preview["members_count"], 2)
