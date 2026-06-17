# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the redesigned Change Head of Household strategy (OP#873).

The CR now seeds one editable role line per active group member; the member
assigned the Head role becomes the new head. Required documents can be driven
by the chosen reason.
"""

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type, get_or_create_membership_kind


class TestChangeHOHStrategy(TransactionCase):
    """Tests for Change Head of Household custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]
        cls.code_model = cls.env["spp.vocabulary.code"]

        cls.head_kind = cls.code_model.get_code("urn:openspp:vocab:group-membership-type", "head")
        cls.spouse_kind = get_or_create_membership_kind(cls.env, "spouse")

        cls.group = cls.partner_model.create({"name": "Test Household", "is_registrant": True, "is_group": True})
        cls.current_head = cls.partner_model.create({"name": "Current Head", "is_registrant": True, "is_group": False})
        cls.member = cls.partner_model.create({"name": "Member Two", "is_registrant": True, "is_group": False})

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
                "individual": cls.member.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [Command.link(cls.spouse_kind.id)],
            }
        )

        cls.cr_type = get_or_create_cr_type(cls.env, "change_hoh")

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    def _make_cr(self, registrant=None):
        return self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": (registrant or self.group).id,
            }
        )

    def _line_for(self, detail, individual):
        return detail.member_line_ids.filtered(lambda r: r.individual_id == individual)

    # ──────────────────────────────────────────────────────────────────
    # Seeding
    # ──────────────────────────────────────────────────────────────────
    def test_member_lines_seeded_from_active_members(self):
        """One role line is seeded per active member, defaulting each member's
        new role to their current role."""
        detail = self._make_cr().get_detail()
        self.assertEqual(len(detail.member_line_ids), 2)
        self.assertEqual(
            set(detail.member_line_ids.mapped("individual_id")),
            {self.current_head, self.member},
        )
        if self.head_kind:
            head_line = self._line_for(detail, self.current_head)
            self.assertEqual(head_line.new_role_id, self.head_kind)
            self.assertEqual(head_line.old_role_display, self.head_kind.display)
        member_line = self._line_for(detail, self.member)
        self.assertEqual(member_line.new_role_id, self.spouse_kind)

    def test_change_hoh_on_individual_fails(self):
        cr = self._make_cr(registrant=self.current_head)  # an individual, not a group
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("group", str(cm.exception).lower())

    # ──────────────────────────────────────────────────────────────────
    # Apply
    # ──────────────────────────────────────────────────────────────────
    def test_apply_transfers_head(self):
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        cr = self._make_cr()
        detail = cr.get_detail()
        # Step down the current head first to avoid a transient two-heads state,
        # then promote the other member.
        self._line_for(detail, self.current_head).new_role_id = self.spouse_kind
        self._line_for(detail, self.member).new_role_id = self.head_kind

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        self.member_membership.invalidate_recordset()
        self.head_membership.invalidate_recordset()
        self.assertIn(self.head_kind, self.member_membership.membership_type_ids)
        self.assertNotIn(self.head_kind, self.head_membership.membership_type_ids)
        self.assertIn(self.spouse_kind, self.head_membership.membership_type_ids)

    def test_apply_requires_a_head(self):
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        cr = self._make_cr()
        detail = cr.get_detail()
        # Nobody assigned the head role.
        detail.member_line_ids.write({"new_role_id": self.spouse_kind.id})
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("head", str(cm.exception).lower())

    def test_two_heads_blocked_by_constraint(self):
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        detail = self._make_cr().get_detail()
        # current_head's line is already Head; promoting the member too -> 2 heads.
        with self.assertRaises(ValidationError):
            self._line_for(detail, self.member).new_role_id = self.head_kind

    def test_all_reasons_apply(self):
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        for reason in ("deceased", "incapacitated", "left_household", "age_change", "correction", "other"):
            cr = self._make_cr()
            detail = cr.get_detail()
            detail.reason = reason
            self._line_for(detail, self.current_head).new_role_id = self.spouse_kind
            self._line_for(detail, self.member).new_role_id = self.head_kind
            cr.approval_state = "approved"
            cr.action_apply()
            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")

    # ──────────────────────────────────────────────────────────────────
    # Preview / review
    # ──────────────────────────────────────────────────────────────────
    def test_preview_structure_and_members_table(self):
        cr = self._make_cr()
        detail = cr.get_detail()
        detail.reason = "left_household"
        detail.remarks = "Head relocating abroad"

        preview = cr.action_preview_changes()
        self.assertEqual(preview["_action"], "change_head_of_household")
        self.assertEqual(preview["Household"], self.group.display_name)
        self.assertEqual(preview["Reason for Change"], "Head Left Household")
        self.assertEqual(preview["Remarks"], "Head relocating abroad")

        members_tbl = next(t for t in preview["_tables"] if t["title"] == "Members")
        self.assertEqual(members_tbl["columns"], ["Name", "Current Role", "New Role"])
        self.assertEqual(len(members_tbl["rows"]), 2)

        html = cr._generate_review_comparison_html()
        self.assertIn(self.current_head.display_name, html)
        self.assertIn("New Role", html)

    # ──────────────────────────────────────────────────────────────────
    # Item 5: reason-driven required documents
    # ──────────────────────────────────────────────────────────────────
    def test_reason_driven_required_documents(self):
        doc_type = self.code_model.search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:cr_document_type")], limit=1
        )
        if not doc_type:
            self.skipTest("no cr_document_type vocabulary codes present")

        self.cr_type.write(
            {
                "reason_document_ids": [
                    (5, 0, 0),
                    (0, 0, {"reason": "deceased", "required_document_ids": [Command.set(doc_type.ids)]}),
                ],
            }
        )
        cr = self._make_cr()
        detail = cr.get_detail()

        # No reason chosen yet -> falls back to the (empty) flat list -> complete.
        self.assertTrue(cr.documents_complete)

        # Reason with a configured rule -> that rule's documents are required.
        detail.reason = "deceased"
        cr.invalidate_recordset(["documents_complete", "missing_required_document_ids"])
        self.assertIn(doc_type, cr.missing_required_document_ids)
        self.assertFalse(cr.documents_complete)

        # A reason with no rule -> nothing required.
        detail.reason = "other"
        cr.invalidate_recordset(["documents_complete", "missing_required_document_ids"])
        self.assertTrue(cr.documents_complete)
