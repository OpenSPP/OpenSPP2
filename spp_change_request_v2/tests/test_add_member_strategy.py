# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the redesigned Add Member strategy (OP#871)."""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestAddMemberStrategy(TransactionCase):
    """Tests for Add Member custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]

        cls.head_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
        cls.member_kind = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "member")

        cls.group = cls.partner_model.create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.lone_individual = cls.partner_model.create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.cr_type = get_or_create_cr_type(cls.env, "add_member")
        cls.cr_type.write({"requires_head": False})

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    def _make_cr(self, registrant=None, **detail_vals):
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": (registrant or self.group).id,
            }
        )
        cr.get_detail().write(detail_vals)
        return cr

    # ──────────────────────────────────────────────────────────────────
    # Basic creation
    # ──────────────────────────────────────────────────────────────────
    def test_add_member_creates_individual(self):
        cr = self._make_cr(given_name="Maria", family_name="Santos")
        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        detail = cr.get_detail()
        self.assertTrue(detail.created_individual_id)
        new_member = detail.created_individual_id
        self.assertEqual(new_member.given_name, "Maria")
        self.assertEqual(new_member.family_name, "Santos")
        self.assertTrue(new_member.is_registrant)
        self.assertFalse(new_member.is_group)

    def test_add_member_creates_membership(self):
        cr = self._make_cr(
            given_name="Juan",
            family_name="Cruz",
            membership_type_id=self.member_kind.id if self.member_kind else False,
        )
        cr.approval_state = "approved"
        cr.action_apply()

        new_member = cr.get_detail().created_individual_id
        membership = self.membership_model.search([("group", "=", self.group.id), ("individual", "=", new_member.id)])
        self.assertTrue(membership, "Membership should be created")
        if self.member_kind:
            self.assertIn(self.member_kind, membership.membership_type_ids)

    # ──────────────────────────────────────────────────────────────────
    # Computed full name (FAMILY, GIVEN MIDDLE)
    # ──────────────────────────────────────────────────────────────────
    def test_member_name_compute_with_middle(self):
        cr = self._make_cr(
            given_name="Juan",
            family_name="Dela Cruz",
            middle_name="Pablo",
        )
        detail = cr.get_detail()
        self.assertEqual(detail.member_name, "DELA CRUZ, Juan Pablo")

    def test_member_name_compute_without_middle(self):
        cr = self._make_cr(given_name="Maria", family_name="Santos")
        self.assertEqual(cr.get_detail().member_name, "SANTOS, Maria")

    # ──────────────────────────────────────────────────────────────────
    # Age compute
    # ──────────────────────────────────────────────────────────────────
    def test_age_computed_from_birthdate(self):
        from datetime import date

        thirty_years_ago = date(date.today().year - 30, 1, 1)
        cr = self._make_cr(given_name="A", family_name="B", birthdate=thirty_years_ago)
        # Could be 29 or 30 depending on whether the test runs before Jan 1;
        # accept both.
        self.assertIn(cr.get_detail().age, (29, 30))

    def test_age_zero_without_birthdate(self):
        cr = self._make_cr(given_name="A", family_name="B")
        self.assertEqual(cr.get_detail().age, 0)

    # ──────────────────────────────────────────────────────────────────
    # Validation: names required, head requirement
    # ──────────────────────────────────────────────────────────────────
    def test_missing_names_blocks_apply(self):
        cr = self._make_cr(given_name="Only")
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("name", str(cm.exception).lower())

    def test_add_member_to_non_group_blocks(self):
        cr = self._make_cr(registrant=self.lone_individual, given_name="A", family_name="B")
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("group", str(cm.exception).lower())

    def test_requires_head_forces_role_choice(self):
        self.cr_type.write({"requires_head": True})
        cr = self._make_cr(given_name="A", family_name="B")  # no role
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("role", str(cm.exception).lower())
        # restore for subsequent tests
        self.cr_type.write({"requires_head": False})

    # ──────────────────────────────────────────────────────────────────
    # Head demotion
    # ──────────────────────────────────────────────────────────────────
    def test_adding_head_demotes_existing_head(self):
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        # Seed: existing head on the group.
        old_head = self.partner_model.create({"name": "Old Head", "is_registrant": True, "is_group": False})
        old_membership = self.membership_model.create(
            {
                "group": self.group.id,
                "individual": old_head.id,
                "start_date": "2020-01-01",
                "membership_type_ids": [Command.link(self.head_kind.id)],
            }
        )
        self.assertIn(self.head_kind, old_membership.membership_type_ids)

        # Add new member as head.
        cr = self._make_cr(
            given_name="New",
            family_name="Head",
            membership_type_id=self.head_kind.id,
        )
        cr.approval_state = "approved"
        cr.action_apply()

        new_member = cr.get_detail().created_individual_id
        new_membership = self.membership_model.search(
            [("group", "=", self.group.id), ("individual", "=", new_member.id)]
        )
        self.assertIn(self.head_kind, new_membership.membership_type_ids)
        # Old head's membership had `head` removed.
        self.assertNotIn(self.head_kind, old_membership.membership_type_ids)

    # ──────────────────────────────────────────────────────────────────
    # Sub-record attachers
    # ──────────────────────────────────────────────────────────────────
    def test_phones_banks_id_docs_attached(self):
        id_type = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:id-type")],
            limit=1,
        )
        cr = self._make_cr(
            given_name="Multi",
            family_name="Attachments",
            phone_line_ids=[
                (0, 0, {"phone_no": "+63912000000", "is_primary": True}),
                (0, 0, {"phone_no": "+63912111111"}),
            ],
            bank_line_ids=[
                (0, 0, {"acc_number": "ACCT-12345", "acc_holder_name": "Multi Attachments"}),
            ],
            id_doc_line_ids=([(0, 0, {"id_type_id": id_type.id, "value": "ID-001"})] if id_type else []),
        )
        cr.approval_state = "approved"
        cr.action_apply()

        new_member = cr.get_detail().created_individual_id
        self.assertEqual(new_member.phone, "+63912000000", "primary phone written to header")
        spp_phones = self.env["spp.phone.number"].search([("partner_id", "=", new_member.id)])
        self.assertEqual(len(spp_phones), 2)
        banks = self.env["res.partner.bank"].search([("partner_id", "=", new_member.id)])
        self.assertEqual(len(banks), 1)
        if id_type:
            reg_ids = self.env["spp.registry.id"].search([("partner_id", "=", new_member.id)])
            self.assertEqual(len(reg_ids), 1)

    # ──────────────────────────────────────────────────────────────────
    # Preview shape
    # ──────────────────────────────────────────────────────────────────
    def test_preview_returns_create_member_action(self):
        cr = self._make_cr(given_name="Preview", family_name="Test")
        preview = cr.action_preview_changes()
        self.assertIn("_action", preview)
        self.assertEqual(preview["_action"], "create_member")
        # The review banner header is sourced from the preview (OP#871 QA round 1).
        self.assertIn("individual", (preview.get("_header") or "").lower())

    def test_add_member_writes_single_address(self):
        """The single Address field maps to the registry's res.partner.address
        on apply, matching how the registry stores it (OP#871 QA round 1)."""
        cr = self._make_cr(
            given_name="Lola",
            family_name="Reyes",
            address="55 Aurora Blvd, Manila",
        )
        cr.approval_state = "approved"
        cr.action_apply()
        new_member = cr.get_detail().created_individual_id
        self.assertEqual(new_member.address, "55 Aurora Blvd, Manila")
