# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Change Head of Household strategy."""

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestChangeHOHStrategy(TransactionCase):
    """Tests for Change Head of Household custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]

        # Get head membership kind from vocabulary
        cls.head_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")

        # Get spouse kind from vocabulary
        cls.spouse_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "spouse")

        # Create test group
        cls.group = cls.partner_model.create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create test individuals
        cls.current_head = cls.partner_model.create(
            {
                "name": "Current Head",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.new_head = cls.partner_model.create(
            {
                "name": "New Head",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create memberships
        cls.head_membership = cls.membership_model.create(
            {
                "group": cls.group.id,
                "individual": cls.current_head.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [Command.link(cls.head_kind.id)] if cls.head_kind else [],
            }
        )
        cls.member_membership = cls.membership_model.create(
            {
                "group": cls.group.id,
                "individual": cls.new_head.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Get CR type
        cls.cr_type = cls.env.ref(
            "spp_change_request_v2.cr_type_change_hoh",
            raise_if_not_found=False,
        )

    def test_change_hoh_transfers_role(self):
        """Test changing HOH transfers head role."""
        if not self.cr_type or not self.head_kind:
            self.skipTest("Change HOH CR type or head kind not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "new_head_membership_id": self.member_membership.id,
                "reason": "voluntary",
                "effective_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify role transferred
        self.assertTrue(cr.is_applied)
        self.assertIn(
            self.head_kind,
            self.member_membership.membership_type_ids,
            "New head should have head role",
        )
        self.assertNotIn(
            self.head_kind,
            self.head_membership.membership_type_ids,
            "Old head should not have head role",
        )

    def test_change_hoh_assigns_new_role_to_previous(self):
        """Test previous head gets new role assigned."""
        if not self.cr_type or not self.head_kind:
            self.skipTest("Change HOH CR type or head kind not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "new_head_membership_id": self.member_membership.id,
                "previous_head_new_role_id": self.spouse_kind.id,
                "reason": "voluntary",
                "effective_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify previous head has new role
        self.assertIn(
            self.spouse_kind,
            self.head_membership.membership_type_ids,
            "Previous head should have spouse role",
        )

    def test_change_hoh_on_individual_fails(self):
        """Test cannot change HOH on individual registrant."""
        if not self.cr_type:
            self.skipTest("Change HOH CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.current_head.id,  # Individual, not group
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "new_head_membership_id": self.member_membership.id,
                "reason": "other",
                "effective_date": fields.Date.today(),
            }
        )

        cr.approval_state = "approved"

        with self.assertRaises(UserError) as cm:
            cr.action_apply()

        self.assertIn("group", str(cm.exception).lower())

    def test_change_hoh_all_reasons(self):
        """Test all change reasons work."""
        if not self.cr_type:
            self.skipTest("Change HOH CR type not found")

        reasons = [
            "deceased",
            "incapacitated",
            "left_household",
            "age_change",
            "voluntary",
            "correction",
            "other",
        ]

        for _i, reason in enumerate(reasons):
            # Create new group and members for each test
            group = self.partner_model.create(
                {
                    "name": f"Group {reason}",
                    "is_registrant": True,
                    "is_group": True,
                }
            )
            member1 = self.partner_model.create(
                {
                    "name": f"Member1 {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            member2 = self.partner_model.create(
                {
                    "name": f"Member2 {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            self.membership_model.create(
                {
                    "group": group.id,
                    "individual": member1.id,
                    "start_date": fields.Datetime.now(),
                    "membership_type_ids": [Command.link(self.head_kind.id)] if self.head_kind else [],
                }
            )
            membership2 = self.membership_model.create(
                {
                    "group": group.id,
                    "individual": member2.id,
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
                    "new_head_membership_id": membership2.id,
                    "reason": reason,
                    "effective_date": fields.Date.today(),
                }
            )

            cr.approval_state = "approved"
            cr.action_apply()

            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")

    def test_change_hoh_preview(self):
        """Test preview returns expected structure."""
        if not self.cr_type:
            self.skipTest("Change HOH CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.group.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "new_head_membership_id": self.member_membership.id,
                "reason": "voluntary",
                "effective_date": fields.Date.today(),
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "change_head_of_household")
