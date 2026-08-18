# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the Remove Member strategy (OP#872).

End Date and Member Name fields removed; "Married Out" reason dropped; the
review shows a header + Additional Information; the removal reason can drive
required documents (reuses the #873 mechanism).
"""

from odoo import Command, fields
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
        cls.code_model = cls.env["spp.vocabulary.code"]

        cls.group = cls.partner_model.create({"name": "Test Household", "is_registrant": True, "is_group": True})
        cls.member1 = cls.partner_model.create({"name": "Member One", "is_registrant": True, "is_group": False})
        cls.member2 = cls.partner_model.create({"name": "Member Two", "is_registrant": True, "is_group": False})

        cls.membership1 = cls.membership_model.create(
            {"group": cls.group.id, "individual": cls.member1.id, "start_date": fields.Datetime.now()}
        )
        cls.membership2 = cls.membership_model.create(
            {"group": cls.group.id, "individual": cls.member2.id, "start_date": fields.Datetime.now()}
        )

        cls.cr_type = get_or_create_cr_type(cls.env, "remove_member")

    def _make_cr(self, registrant=None, **detail_vals):
        cr = self.cr_model.create({"request_type_id": self.cr_type.id, "registrant_id": (registrant or self.group).id})
        if detail_vals:
            cr.get_detail().write(detail_vals)
        return cr

    # ──────────────────────────────────────────────────────────────────
    # Apply
    # ──────────────────────────────────────────────────────────────────
    def test_remove_member_ends_membership(self):
        cr = self._make_cr(
            individual_id=self.member1.id, membership_id=self.membership1.id, end_reason="left_household"
        )
        cr.approval_state = "approved"
        cr.action_apply()
        self.assertTrue(cr.is_applied)
        self.assertTrue(self.membership1.ended_date)
        self.assertEqual(self.membership1.status, "inactive")

    def test_remove_member_inactive_fails(self):
        self.membership2.write({"ended_date": fields.Datetime.now()})
        cr = self._make_cr(membership_id=self.membership2.id, end_reason="other")
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("inactive", str(cm.exception).lower())

    def test_remove_member_from_individual_fails(self):
        cr = self._make_cr(registrant=self.member1, membership_id=self.membership1.id, end_reason="other")
        cr.approval_state = "approved"
        with self.assertRaises(UserError) as cm:
            cr.action_apply()
        self.assertIn("group", str(cm.exception).lower())

    # ──────────────────────────────────────────────────────────────────
    # Field/reason changes (OP#872)
    # ──────────────────────────────────────────────────────────────────
    def test_married_out_reason_removed(self):
        detail = self._make_cr().get_detail()
        codes = dict(detail.fields_get(["end_reason"])["end_reason"]["selection"])
        self.assertNotIn("married_out", codes)
        self.assertIn("left_household", codes)

    def test_end_date_field_removed(self):
        self.assertNotIn("end_date", self.env["spp.cr.detail.remove_member"]._fields)

    def test_remove_member_reasons_apply(self):
        for reason in ("left_household", "deceased", "migrated", "correction", "other"):
            member = self.partner_model.create({"name": f"M {reason}", "is_registrant": True, "is_group": False})
            membership = self.membership_model.create(
                {"group": self.group.id, "individual": member.id, "start_date": fields.Datetime.now()}
            )
            cr = self._make_cr(individual_id=member.id, membership_id=membership.id, end_reason=reason)
            cr.approval_state = "approved"
            cr.action_apply()
            self.assertTrue(cr.is_applied, f"Failed for reason: {reason}")
            self.assertEqual(membership.status, "inactive")

    # ──────────────────────────────────────────────────────────────────
    # Review / preview
    # ──────────────────────────────────────────────────────────────────
    def test_remove_member_preview(self):
        cr = self._make_cr(
            individual_id=self.member1.id,
            membership_id=self.membership1.id,
            end_reason="deceased",
            remarks="Passed away last month",
        )
        preview = cr.action_preview_changes()
        self.assertEqual(preview["_action"], "remove_member")
        self.assertIn("to be removed", (preview.get("_header") or "").lower())
        self.assertEqual(preview["Member"], self.member1.display_name)
        self.assertEqual(preview["Reason for Removal"], "Deceased")
        self.assertEqual(preview["Additional Information"], "Passed away last month")
        # No removed keys leak into the review.
        for removed in ("member_name", "end_date"):
            self.assertNotIn(removed, preview)
        html = cr._generate_review_comparison_html()
        self.assertIn("to be removed", html.lower())

    # ──────────────────────────────────────────────────────────────────
    # Reason -> required documents (reuses #873)
    # ──────────────────────────────────────────────────────────────────
    def test_removal_reason_drives_required_documents(self):
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
        cr = self._make_cr(individual_id=self.member1.id, membership_id=self.membership1.id)
        self.assertTrue(cr.documents_complete)
        cr.get_detail().end_reason = "deceased"
        cr.invalidate_recordset(["documents_complete", "missing_required_document_ids"])
        self.assertIn(doc_type, cr.missing_required_document_ids)
        self.assertFalse(cr.documents_complete)
        cr.get_detail().end_reason = "migrated"
        cr.invalidate_recordset(["documents_complete", "missing_required_document_ids"])
        self.assertTrue(cr.documents_complete)
