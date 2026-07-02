# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the redesigned Split Household strategy (OP#877).

Moving a member is a relational update (member + role only, no per-member edits);
the new household uses the Create-Group field set; at most one moved member may be
Head and a head is not mandatory; and the split reason can drive required documents
(reusing the #873 mechanism).
"""

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

from .common import get_or_create_cr_type


class TestSplitHouseholdStrategy(TransactionCase):
    """Tests for Split Household custom strategy."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.membership_model = cls.env["spp.group.membership"]
        cls.cr_model = cls.env["spp.change.request"]
        cls.code_model = cls.env["spp.vocabulary.code"]

        cls.head_kind = cls.code_model.get_code("urn:openspp:vocab:group-membership-type", "head")
        cls.member_kind = cls.code_model.get_code("urn:openspp:vocab:group-membership-type", "member")

        cls.source_group = cls.partner_model.create(
            {"name": "Original Household", "is_registrant": True, "is_group": True}
        )
        cls.head = cls.partner_model.create({"name": "The Head", "is_registrant": True, "is_group": False})
        cls.m2 = cls.partner_model.create({"name": "Member Two", "is_registrant": True, "is_group": False})
        cls.m3 = cls.partner_model.create({"name": "Member Three", "is_registrant": True, "is_group": False})

        cls.membership_model.create(
            {
                "group": cls.source_group.id,
                "individual": cls.head.id,
                "start_date": fields.Datetime.now(),
                "membership_type_ids": [Command.link(cls.head_kind.id)] if cls.head_kind else [],
            }
        )
        for member in (cls.m2, cls.m3):
            cls.membership_model.create(
                {"group": cls.source_group.id, "individual": member.id, "start_date": fields.Datetime.now()}
            )

        cls.cr_type = get_or_create_cr_type(cls.env, "split_household")

    # ──────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────
    def _make_cr(self, **detail_vals):
        cr = self.cr_model.create({"request_type_id": self.cr_type.id, "registrant_id": self.source_group.id})
        if detail_vals:
            cr.get_detail().write(detail_vals)
        return cr

    def _line(self, individual, **edits):
        vals = {"individual_id": individual.id}
        vals.update(edits)
        return (0, 0, vals)

    def _active_membership(self, group, individual):
        return self.membership_model.search(
            [("group", "=", group.id), ("individual", "=", individual.id), ("status", "=", "active")]
        )

    # ──────────────────────────────────────────────────────────────────
    # Core flow
    # ──────────────────────────────────────────────────────────────────
    def test_split_creates_new_group_and_moves_members(self):
        cr = self._make_cr(
            new_group_name="Split Household",
            split_reason="independence",
            member_line_ids=[self._line(self.m3)],
        )
        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        new_group = cr.get_detail().created_group_id
        self.assertTrue(new_group)
        self.assertEqual(new_group.name, "Split Household")
        self.assertTrue(new_group.is_group)
        # m3 now active in the new group, no longer active in the source.
        self.assertTrue(self._active_membership(new_group, self.m3))
        self.assertFalse(self._active_membership(self.source_group, self.m3))
        # head + m2 remain in the source.
        self.assertTrue(self._active_membership(self.source_group, self.head))

    def test_role_assigned_in_new_group(self):
        if not self.member_kind:
            self.skipTest("member role code not present")
        cr = self._make_cr(
            new_group_name="Roled Split",
            member_line_ids=[self._line(self.m3, membership_type_id=self.member_kind.id)],
        )
        cr.approval_state = "approved"
        cr.action_apply()
        membership = self._active_membership(cr.get_detail().created_group_id, self.m3)
        self.assertIn(self.member_kind, membership.membership_type_ids)

    def test_head_not_mandatory(self):
        """A new household can be created without designating a head (per spec)."""
        cr = self._make_cr(new_group_name="Headless Split", member_line_ids=[self._line(self.m3)])
        cr.approval_state = "approved"
        cr.action_apply()
        self.assertTrue(cr.is_applied)

    def test_blank_cr_role_leaves_role_blank(self):
        """A blank role on the CR line yields no role in the new group.

        The member's role in the source household must NOT be carried over - the
        new membership follows the CR line's role exactly, even when empty.
        """
        if not self.member_kind:
            self.skipTest("member role code not present")
        # Give m3 a role in the source household.
        self._active_membership(self.source_group, self.m3).membership_type_ids = [Command.set(self.member_kind.ids)]
        cr = self._make_cr(
            new_group_name="Blank Role Split",
            member_line_ids=[self._line(self.m3)],  # no role on the CR line
        )
        cr.approval_state = "approved"
        cr.action_apply()
        new_membership = self._active_membership(cr.get_detail().created_group_id, self.m3)
        self.assertTrue(new_membership)
        self.assertFalse(new_membership.membership_type_ids)

    # ──────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────
    def test_minimum_one_member_remains(self):
        """Moving every member is rejected (at least one must remain)."""
        with self.assertRaises(ValidationError):
            self._make_cr(
                new_group_name="Empties Source",
                member_line_ids=[self._line(self.head), self._line(self.m2), self._line(self.m3)],
            )

    def test_available_members_exclude_head(self):
        """The source head is not offered as a movable member."""
        available = self._make_cr().get_detail().available_member_ids
        self.assertIn(self.m2, available)
        self.assertIn(self.m3, available)
        if self.head_kind:
            self.assertNotIn(self.head, available)

    def test_only_one_head_among_moved_members(self):
        """Two moved members cannot both be Head of the new household."""
        if not self.head_kind:
            self.skipTest("head role code not present")
        with self.assertRaises(ValidationError):
            self._make_cr(
                new_group_name="Two Heads",
                member_line_ids=[
                    self._line(self.m2, membership_type_id=self.head_kind.id),
                    self._line(self.m3, membership_type_id=self.head_kind.id),
                ],
            )

    def test_no_duplicate_member(self):
        """The same member cannot be added on more than one move line."""
        with self.assertRaises(ValidationError):
            self._make_cr(
                new_group_name="Dup Member",
                member_line_ids=[self._line(self.m3), self._line(self.m3)],
            )

    def test_single_head_allowed(self):
        """One moved member as Head is accepted."""
        if not self.head_kind:
            self.skipTest("head role code not present")
        cr = self._make_cr(
            new_group_name="One Head",
            member_line_ids=[
                self._line(self.m2, membership_type_id=self.head_kind.id),
                self._line(self.m3),
            ],
        )
        cr.approval_state = "approved"
        cr.action_apply()
        self.assertTrue(cr.is_applied)

    # ──────────────────────────────────────────────────────────────────
    # Preview / review page
    # ──────────────────────────────────────────────────────────────────
    def test_preview_header_and_tables(self):
        cr = self._make_cr(
            new_group_name="Preview Split",
            split_reason="marriage",
            member_line_ids=[self._line(self.m2), self._line(self.m3)],
        )
        preview = cr.action_preview_changes()
        self.assertEqual(preview["_action"], "split_household")
        self.assertIn("new household will be created", (preview.get("_header") or "").lower())
        self.assertEqual(preview["New Household Name"], "Preview Split")
        titles = [t["title"] for t in preview["_tables"]]
        self.assertIn("Members to Move", titles)
        self.assertNotIn("Member Edits", titles)
        html = cr._generate_review_comparison_html()
        self.assertIn("new household will be created", html.lower())

    # ──────────────────────────────────────────────────────────────────
    # Phase C: reason-for-split -> required documents (reuses #873)
    # ──────────────────────────────────────────────────────────────────
    def test_split_reason_drives_required_documents(self):
        doc_type = self.code_model.search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:cr_document_type")], limit=1
        )
        if not doc_type:
            self.skipTest("no cr_document_type vocabulary codes present")
        self.cr_type.write(
            {
                "reason_document_ids": [
                    (5, 0, 0),
                    (0, 0, {"reason": "marriage", "required_document_ids": [Command.set(doc_type.ids)]}),
                ],
            }
        )
        cr = self._make_cr(new_group_name="Docs Split", member_line_ids=[self._line(self.m3)])

        # No reason yet -> falls back to the (empty) flat list -> complete.
        self.assertTrue(cr.documents_complete)
        # Split reason with a rule -> the rule's docs are required.
        cr.get_detail().split_reason = "marriage"
        cr.invalidate_recordset(["documents_complete", "missing_required_document_ids"])
        self.assertIn(doc_type, cr.missing_required_document_ids)
        self.assertFalse(cr.documents_complete)
        # A reason without a rule -> nothing required.
        cr.get_detail().split_reason = "relocation"
        cr.invalidate_recordset(["documents_complete", "missing_required_document_ids"])
        self.assertTrue(cr.documents_complete)
