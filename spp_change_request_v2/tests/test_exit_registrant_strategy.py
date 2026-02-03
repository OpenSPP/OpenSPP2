# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Exit Registrant strategy."""

from odoo import fields
from odoo.tests import TransactionCase


class TestExitRegistrantStrategy(TransactionCase):
    """Tests for Exit Registrant custom strategy."""

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
        cls.individual = cls.partner_model.create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )
        cls.individual_with_membership = cls.partner_model.create(
            {
                "name": "Member Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create membership
        cls.membership = cls.membership_model.create(
            {
                "group": cls.group.id,
                "individual": cls.individual_with_membership.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Get CR type
        cls.cr_type = cls.env.ref(
            "spp_change_request_v2.cr_type_exit_registrant",
            raise_if_not_found=False,
        )

    def test_exit_individual_deactivates(self):
        """Test exiting individual sets disabled date."""
        if not self.cr_type:
            self.skipTest("Exit registrant CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "exit_reason": "deceased",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": False,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify disabled
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.individual.disabled)

    def test_exit_individual_ends_memberships(self):
        """Test exiting individual ends active memberships."""
        if not self.cr_type:
            self.skipTest("Exit registrant CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual_with_membership.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "exit_reason": "deceased",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify membership ended
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.membership.ended_date)
        self.assertEqual(self.membership.status, "inactive")

    def test_exit_group_deactivates(self):
        """Test exiting group sets disabled date."""
        if not self.cr_type:
            self.skipTest("Exit registrant CR type not found")

        # Create new group to test
        group = self.partner_model.create(
            {
                "name": "Group to Exit",
                "is_registrant": True,
                "is_group": True,
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
                "exit_reason": "ineligible",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": False,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify disabled
        self.assertTrue(cr.is_applied)
        self.assertTrue(group.disabled)

    def test_exit_group_ends_all_memberships(self):
        """Test exiting group ends all member memberships."""
        if not self.cr_type:
            self.skipTest("Exit registrant CR type not found")

        # Create group with members
        group = self.partner_model.create(
            {
                "name": "Group to Exit",
                "is_registrant": True,
                "is_group": True,
            }
        )
        member1 = self.partner_model.create(
            {
                "name": "Member 1",
                "is_registrant": True,
                "is_group": False,
            }
        )
        member2 = self.partner_model.create(
            {
                "name": "Member 2",
                "is_registrant": True,
                "is_group": False,
            }
        )
        membership1 = self.membership_model.create(
            {
                "group": group.id,
                "individual": member1.id,
                "start_date": fields.Datetime.now(),
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
                "exit_reason": "fraud",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": True,
            }
        )

        cr.approval_state = "approved"
        cr.action_apply()

        # Verify all memberships ended
        self.assertTrue(cr.is_applied)
        self.assertEqual(membership1.status, "inactive")
        self.assertEqual(membership2.status, "inactive")

    def test_exit_all_reasons(self):
        """Test all exit reasons work correctly."""
        if not self.cr_type:
            self.skipTest("Exit registrant CR type not found")

        reasons = ["deceased", "emigrated", "duplicate", "ineligible", "voluntary", "fraud", "other"]

        for reason in reasons:
            individual = self.partner_model.create(
                {
                    "name": f"Individual {reason}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )

            cr = self.cr_model.create(
                {
                    "request_type_id": self.cr_type.id,
                    "registrant_id": individual.id,
                }
            )

            detail = cr.get_detail()
            detail.write(
                {
                    "exit_reason": reason,
                    "exit_date": fields.Date.today(),
                    "is_end_active_memberships": False,
                }
            )

            cr.approval_state = "approved"
            cr.action_apply()

            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")
            self.assertTrue(individual.disabled)

    def test_exit_preview(self):
        """Test preview returns expected structure."""
        if not self.cr_type:
            self.skipTest("Exit registrant CR type not found")

        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.individual.id,
            }
        )

        detail = cr.get_detail()
        detail.write(
            {
                "exit_reason": "emigrated",
                "exit_date": fields.Date.today(),
                "is_end_active_memberships": True,
            }
        )

        preview = cr.action_preview_changes()

        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "exit_registrant")
        self.assertEqual(preview["reason"], "emigrated")
