# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the redesigned Add Member strategy (OP#871).

Add Member now searches for an existing individual registrant and adds them to
the group with a role (the create-a-new-individual flow was replaced).
"""

from odoo import Command
from odoo.exceptions import UserError, ValidationError
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

        cls.group = cls.partner_model.create({"name": "Test Household", "is_registrant": True, "is_group": True})
        # An existing individual not yet in the group (the one we add).
        cls.candidate = cls.partner_model.create({"name": "Maria Santos", "is_registrant": True, "is_group": False})
        cls.lone_individual = cls.partner_model.create(
            {"name": "Lone Individual", "is_registrant": True, "is_group": False}
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
        if detail_vals:
            cr.get_detail().write(detail_vals)
        return cr

    def _add_existing_head(self, group):
        head = self.partner_model.create({"name": "Existing Head", "is_registrant": True, "is_group": False})
        self.membership_model.create(
            {
                "group": group.id,
                "individual": head.id,
                "membership_type_ids": [Command.link(self.head_kind.id)] if self.head_kind else [],
            }
        )
        return head

    # ──────────────────────────────────────────────────────────────────
    # Basic flow: add an existing individual
    # ──────────────────────────────────────────────────────────────────
    def test_add_existing_individual_creates_membership(self):
        cr = self._make_cr(
            individual_id=self.candidate.id,
            membership_type_id=self.member_kind.id if self.member_kind else False,
        )
        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        membership = self.membership_model.search(
            [("group", "=", self.group.id), ("individual", "=", self.candidate.id)]
        )
        self.assertTrue(membership, "An active membership should be created for the selected individual")
        self.assertEqual(membership.status, "active")
        if self.member_kind:
            self.assertIn(self.member_kind, membership.membership_type_ids)

    def test_no_new_partner_is_created(self):
        """The selected existing individual is reused — no new partner."""
        before = self.partner_model.search_count([])
        cr = self._make_cr(individual_id=self.candidate.id)
        cr.approval_state = "approved"
        cr.action_apply()
        self.assertEqual(self.partner_model.search_count([]), before, "Add Member must not create a new partner")

    # ──────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────
    def test_missing_individual_blocks_apply(self):
        cr = self._make_cr()  # no individual selected
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("individual", str(cm.exception).lower())

    def test_add_member_to_non_group_blocks(self):
        cr = self._make_cr(registrant=self.lone_individual, individual_id=self.candidate.id)
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("group", str(cm.exception).lower())

    def test_already_member_blocks_apply(self):
        # Seed the candidate as an existing active member.
        self.membership_model.create({"group": self.group.id, "individual": self.candidate.id})
        cr = self._make_cr(individual_id=self.candidate.id)
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("already", str(cm.exception).lower())

    def test_requires_head_forces_role_choice(self):
        self.cr_type.write({"requires_head": True})
        cr = self._make_cr(individual_id=self.candidate.id)  # no role
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("role", str(cm.exception).lower())
        self.cr_type.write({"requires_head": False})

    # ──────────────────────────────────────────────────────────────────
    # Picker domain + role restriction
    # ──────────────────────────────────────────────────────────────────
    def test_individual_domain_excludes_active_members(self):
        """The picker domain excludes individuals already in the group."""
        self.membership_model.create({"group": self.group.id, "individual": self.candidate.id})
        detail = self._make_cr().get_detail()
        domain = detail.individual_domain
        self.assertIn("not in", domain)
        # The already-member candidate id is in the excluded list.
        self.assertIn(str(self.candidate.id), domain)

    def test_adding_head_when_group_has_head_raises(self):
        """OP#871: the Head role is no longer hidden; choosing Head for a group
        that already has an active head raises a validation error at save/submit
        time (a model constraint, uniform with the other CRs)."""
        if not self.head_kind:
            self.skipTest("head membership-type code not present")
        group_with_head = self.partner_model.create(
            {"name": "Group With Head", "is_registrant": True, "is_group": True}
        )
        self._add_existing_head(group_with_head)
        candidate = self.partner_model.create({"name": "Wannabe Head", "is_registrant": True, "is_group": False})

        # The constraint fires when the detail is written (i.e. on submit), not
        # only on apply.
        with self.assertRaises(ValidationError) as cm:
            self._make_cr(
                registrant=group_with_head,
                individual_id=candidate.id,
                membership_type_id=self.head_kind.id,
            )
        self.assertIn("head", str(cm.exception).lower())

    def test_adding_head_when_group_has_no_head_is_allowed(self):
        """Choosing Head is fine when the group has no active head."""
        if not self.head_kind:
            self.skipTest("head membership-type code not present")
        headless = self.partner_model.create({"name": "Headless Group", "is_registrant": True, "is_group": True})
        candidate = self.partner_model.create({"name": "New Head", "is_registrant": True, "is_group": False})
        cr = self._make_cr(
            registrant=headless,
            individual_id=candidate.id,
            membership_type_id=self.head_kind.id,
        )
        cr.approval_state = "approved"
        cr.action_apply()
        self.assertTrue(cr.is_applied)

    # ──────────────────────────────────────────────────────────────────
    # Preview / review page
    # ──────────────────────────────────────────────────────────────────
    def test_preview_returns_add_member_action_and_header(self):
        cr = self._make_cr(
            individual_id=self.candidate.id,
            membership_type_id=self.member_kind.id if self.member_kind else False,
        )
        preview = cr.action_preview_changes()
        self.assertEqual(preview["_action"], "add_member")
        self.assertIn("added to the group", (preview.get("_header") or "").lower())
        self.assertEqual(preview["Name"], self.candidate.display_name)
        if self.member_kind:
            self.assertEqual(preview["Role"], self.member_kind.display)
        # Fields are present even when the individual has no value (render as "-").
        self.assertIn("Email", preview)
        self.assertIn("Date of Birth", preview)

    def test_review_html_names_the_individual(self):
        cr = self._make_cr(individual_id=self.candidate.id)
        html = cr._generate_review_comparison_html()
        self.assertIn("Maria Santos", html)
        self.assertIn("added to the group", html.lower())
