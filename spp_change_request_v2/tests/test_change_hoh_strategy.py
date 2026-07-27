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
        """One role line is seeded per active member; the Current Role is shown
        but the New Role is left BLANK (not prefilled) — OP#873 QA."""
        detail = self._make_cr().get_detail()
        self.assertEqual(len(detail.member_line_ids), 2)
        self.assertEqual(
            set(detail.member_line_ids.mapped("individual_id")),
            {self.current_head, self.member},
        )
        # New Role is blank for every seeded line.
        self.assertFalse(any(detail.member_line_ids.mapped("new_role_id")))
        if self.head_kind:
            head_line = self._line_for(detail, self.current_head)
            self.assertEqual(head_line.old_role_display, self.head_kind.display)

    def test_change_hoh_on_individual_fails(self):
        cr = self._make_cr(registrant=self.current_head)  # an individual, not a group
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("group", str(cm.exception).lower())

    # ──────────────────────────────────────────────────────────────────
    # Apply
    # ──────────────────────────────────────────────────────────────────
    def test_apply_follows_new_role_blank_clears(self):
        """OP#873 QA: the CR follows the New Role column exactly. Designating the
        new head (and leaving the outgoing head blank) hands over the role; a
        blank New Role clears that member's roles entirely."""
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        cr = self._make_cr()
        detail = cr.get_detail()
        # Only the new head is designated; the current head's row stays blank.
        self._line_for(detail, self.member).new_role_id = self.head_kind

        cr.approval_state = "approved"
        cr.action_apply()

        self.assertTrue(cr.is_applied)
        self.member_membership.invalidate_recordset()
        self.head_membership.invalidate_recordset()
        # New head holds Head; the previous head's blank row cleared all roles.
        self.assertIn(self.head_kind, self.member_membership.membership_type_ids)
        self.assertFalse(self.head_membership.membership_type_ids)
        # Exactly one active head remains in the group.
        heads = self.membership_model.search(
            [
                ("group", "=", self.group.id),
                ("status", "=", "active"),
                ("membership_type_ids", "in", self.head_kind.ids),
            ]
        )
        self.assertEqual(len(heads), 1)

    def test_apply_requires_a_head(self):
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        cr = self._make_cr()
        detail = cr.get_detail()
        # Nobody assigned the head role (all set to a non-head role).
        detail.member_line_ids.write({"new_role_id": self.spouse_kind.id})
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("head", str(cm.exception).lower())

    def test_two_heads_blocked_by_constraint(self):
        """Designating two (non-current-head) members as Head is rejected."""
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        # A second non-head member so we can set two heads without touching the
        # current head (which has its own dedicated validation).
        member2 = self.partner_model.create({"name": "Member Three", "is_registrant": True, "is_group": False})
        self.membership_model.create(
            {"group": self.group.id, "individual": member2.id, "start_date": fields.Datetime.now()}
        )
        detail = self._make_cr().get_detail()
        self._line_for(detail, self.member).new_role_id = self.head_kind
        with self.assertRaises(ValidationError):
            self._line_for(detail, member2).new_role_id = self.head_kind

    def test_current_head_cannot_be_set_as_head(self):
        """The current Head of Household may not be reassigned Head in this CR."""
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        detail = self._make_cr().get_detail()
        with self.assertRaises(ValidationError) as cm:
            self._line_for(detail, self.current_head).new_role_id = self.head_kind
        self.assertIn("current head", str(cm.exception).lower())

    def test_all_reasons_apply(self):
        if not self.head_kind:
            self.skipTest("head membership-type code not present in the vocabulary")
        for reason in ("deceased", "incapacitated", "left_household", "age_change", "correction", "other"):
            # Fresh group + head + member each iteration (applying changes the
            # head, so reusing one group would make the next iteration try to
            # re-assign the now-current head).
            grp = self.partner_model.create({"name": f"G {reason}", "is_registrant": True, "is_group": True})
            head = self.partner_model.create({"name": f"Head {reason}", "is_registrant": True, "is_group": False})
            new_head = self.partner_model.create({"name": f"New {reason}", "is_registrant": True, "is_group": False})
            self.membership_model.create(
                {
                    "group": grp.id,
                    "individual": head.id,
                    "start_date": fields.Datetime.now(),
                    "membership_type_ids": [Command.link(self.head_kind.id)],
                }
            )
            self.membership_model.create(
                {"group": grp.id, "individual": new_head.id, "start_date": fields.Datetime.now()}
            )
            cr = self._make_cr(registrant=grp)
            detail = cr.get_detail()
            detail.reason = reason
            self._line_for(detail, new_head).new_role_id = self.head_kind
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
