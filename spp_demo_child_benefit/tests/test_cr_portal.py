# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Portal change requests: a citizen files an "Edit Individual Information"
request for themselves or a family member; the manager approves it in the
back office; the citizen tracks its status on the portal."""

import re

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestChangeRequestPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.gurung_user = env["res.users"].search([("login", "=", "gurung")], limit=1)
        cls.gurung = cls.gurung_user.partner_id
        cls.family = env["res.partner"].search([("name", "=", "Gurung Family"), ("is_group", "=", True)], limit=1)
        members = env["spp.group.membership"].search([("group", "=", cls.family.id)]).mapped("individual")
        cls.child = (members - cls.gurung).sorted("id")[0]
        dahal = env["res.partner"].search([("name", "=", "Dahal Family"), ("is_group", "=", True)], limit=1)
        cls.outsider = env["spp.group.membership"].search([("group", "=", dahal.id)], limit=1).individual
        cls.manager = env["res.users"].search([("login", "=", "manager")], limit=1)

    def _login(self):
        self.authenticate("gurung", "Cbp-Parent-Demo-2026!")

    def _csrf(self, html):
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
        self.assertTrue(match, "csrf token not found")
        return match.group(1)

    def _submit(self, csrf, registrant_id=None, **fields):
        data = {"csrf_token": csrf, "reason": "Moved house", **fields}
        if registrant_id is not None:
            data["registrant_id"] = str(registrant_id)
        return self.url_open("/my/change-requests/submit", data=data)

    def test_new_form_prefills_current_values(self):
        self._login()
        self.gurung.sudo().write({"phone": "+000 11 000 001", "city": "Old Town"})
        page = self.url_open("/my/change-requests/new")
        self.assertEqual(page.status_code, 200, page.text[:500])
        self.assertIn('name="registrant_id"', page.text)
        self.assertIn('value="+000 11 000 001"', page.text)
        self.assertIn('value="Old Town"', page.text)
        for name in ("given_name", "family_name", "birthdate", "gender_id", "email", "postal_code"):
            self.assertIn(f'name="{name}"', page.text)
        # Picking a family member prefills that member instead.
        page = self.url_open(f"/my/change-requests/new?registrant_id={self.child.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.child.given_name, page.text)
        self.assertEqual(self.url_open(f"/my/change-requests/new?registrant_id={self.outsider.id}").status_code, 400)

    def test_submit_creates_pending_request_master_untouched(self):
        self._login()
        old_name = self.gurung.given_name
        csrf = self._csrf(self.url_open("/my/change-requests/new").text)
        resp = self._submit(csrf, phone="+000 22 333 444", address_line1="5 Hill Road", city="New Town")
        self.assertEqual(resp.status_code, 200, resp.text[:500])
        cr = self.env["spp.change.request"].search([("applicant_id", "=", self.gurung.id)], order="id desc", limit=1)
        self.assertTrue(cr)
        self.assertTrue(resp.url.endswith(f"/my/change-requests/{cr.id}"), resp.url)
        self.assertEqual(cr.approval_state, "pending")
        self.assertEqual(cr.request_type_id.code, "edit_individual")
        self.assertEqual(cr.registrant_id, self.gurung)
        self.assertEqual(cr.source_reference, "portal")
        self.assertEqual(cr.create_uid, self.gurung_user)
        self.assertTrue(cr.approval_review_ids.filtered(lambda r: r.status == "pending"))
        detail = cr.get_detail()
        self.assertEqual(detail.phone, "+000 22 333 444")
        self.assertEqual(detail.city, "New Town")
        # Prefill kept the untouched identity fields.
        self.assertEqual(detail.given_name, old_name)
        # Master record untouched until approval.
        self.assertNotEqual(self.gurung.phone, "+000 22 333 444")
        self.assertIn("Pending Approval", resp.text)
        self.assertIn("+000 22 333 444", resp.text)

    def test_manager_approval_applies_and_portal_shows_it(self):
        self._login()
        old_birthdate = self.gurung.birthdate
        csrf = self._csrf(self.url_open("/my/change-requests/new").text)
        self._submit(csrf, email="elan@example.test")
        cr = self.env["spp.change.request"].search([("applicant_id", "=", self.gurung.id)], order="id desc", limit=1)
        cr.with_user(self.manager).action_approve()
        self.assertEqual(cr.approval_state, "approved")
        self.gurung.invalidate_recordset()
        self.assertEqual(self.gurung.email, "elan@example.test")
        self.assertEqual(self.gurung.birthdate, old_birthdate)
        page = self.url_open(f"/my/change-requests/{cr.id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Approved", page.text)

    def test_approving_from_the_approvals_app_applies_too(self):
        """The Approvals app approves the review record; the request must
        follow (approved, applied), exactly as from its own form."""
        self._login()
        csrf = self._csrf(self.url_open("/my/change-requests/new").text)
        self._submit(csrf, phone="+000 44 555 666")
        cr = self.env["spp.change.request"].search([("applicant_id", "=", self.gurung.id)], order="id desc", limit=1)
        review = cr.approval_review_ids.filtered(lambda r: r.status == "pending")
        self.assertEqual(len(review), 1)
        review.with_user(self.manager).action_approve(comment="ok from the approvals list")
        review.invalidate_recordset()
        cr.invalidate_recordset()
        self.assertEqual(review.status, "approved")
        self.assertEqual(review.reviewer_id, self.manager)
        self.assertEqual(cr.approval_state, "approved")
        self.assertTrue(cr.is_applied)
        self.gurung.invalidate_recordset()
        self.assertEqual(self.gurung.phone, "+000 44 555 666")
        # One review, marked once: no duplicate processing from the delegation.
        self.assertEqual(len(cr.approval_review_ids), 1)

    def test_rejecting_from_the_approvals_app_rejects_the_request(self):
        self._login()
        csrf = self._csrf(self.url_open("/my/change-requests/new").text)
        self._submit(csrf, city="Nowhere")
        cr = self.env["spp.change.request"].search([("applicant_id", "=", self.gurung.id)], order="id desc", limit=1)
        review = cr.approval_review_ids.filtered(lambda r: r.status == "pending")
        review.with_user(self.manager).action_reject(comment="not enough evidence")
        review.invalidate_recordset()
        cr.invalidate_recordset()
        self.assertEqual(review.status, "rejected")
        self.assertEqual(cr.approval_state, "rejected")
        self.assertFalse(cr.is_applied)
        self.gurung.invalidate_recordset()
        self.assertNotEqual(self.gurung.city, "Nowhere")

    def test_submit_for_child_and_rejections(self):
        self._login()
        csrf = self._csrf(self.url_open("/my/change-requests/new").text)
        resp = self._submit(csrf, registrant_id=self.child.id, phone="+000 55 555 555")
        self.assertEqual(resp.status_code, 200)
        cr = self.env["spp.change.request"].search([("applicant_id", "=", self.gurung.id)], order="id desc", limit=1)
        self.assertEqual(cr.registrant_id, self.child)
        self.assertEqual(cr.applicant_id, self.gurung)
        before = self.env["spp.change.request"].search_count([])
        self.assertEqual(self._submit(csrf, registrant_id=self.outsider.id, phone="1").status_code, 400)
        self.assertEqual(self._submit(csrf, birthdate="not-a-date").status_code, 400)
        self.assertEqual(self._submit(csrf, gender_id="999999").status_code, 400)
        self.assertEqual(self.env["spp.change.request"].search_count([]), before)

    def test_list_and_detail_are_scoped_to_the_applicant(self):
        self._login()
        page = self.url_open("/my/change-requests")
        self.assertEqual(page.status_code, 200)
        # The officer-seeded request belongs to Mother One, not to this user.
        seeded = self.env["spp.change.request"].search([("registrant_id.name", "=", "Mother One")], limit=1)
        self.assertTrue(seeded)
        self.assertNotIn(seeded.name, page.text)
        self.assertEqual(self.url_open(f"/my/change-requests/{seeded.id}").status_code, 404)
        # Mother One's own login sees it.
        self.authenticate("parent", "Cbp-Parent-Demo-2026!")
        page = self.url_open("/my/change-requests")
        self.assertIn(seeded.name, page.text)
        self.assertEqual(self.url_open(f"/my/change-requests/{seeded.id}").status_code, 200)
        home = self.url_open("/my")
        self.assertIn("/my/change-requests", home.text)
        # Portal home: welcome header naming the organisation, and the three
        # demo cards living in one card row.
        self.assertIn("o_spp_page_header", home.text)
        self.assertIn(self.env.company.name, home.text)
        row = home.text.split('id="portal_benefit_category"', 1)[1].split("portal_common_category", 1)[0]
        for url in ("/my/benefits", "/my/change-requests", "/my/tickets"):
            self.assertIn(url, row, f"{url} card not in the benefit card row")
