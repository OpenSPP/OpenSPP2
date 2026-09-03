# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Portal grievances can be filed on behalf of a family member.

The portal form offers the live members of the submitter's family, with the
submitter preselected. The chosen individual becomes the ticket's registrant
and their family its household, while the contact stays the submitter so the
own-tickets rule and the confirmation e-mail keep working. Any other id is
rejected server-side.
"""

import html
import re

from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException

GROUP_TYPE_NS = "urn:openspp:vocab:group-type"


@tagged("post_install", "-at_install")
class TestGrmPortalFamily(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.gurung_user = env["res.users"].search([("login", "=", "gurung")], limit=1)
        cls.gurung = cls.gurung_user.partner_id
        cls.family = env["res.partner"].search([("name", "=", "Gurung Family"), ("is_group", "=", True)], limit=1)
        cls.members = (
            env["spp.group.membership"]
            .search([("group", "=", cls.family.id), ("is_ended", "=", False)])
            .mapped("individual")
        )
        cls.child = (cls.members - cls.gurung).sorted("id")[0]
        dahal_family = env["res.partner"].search([("name", "=", "Dahal Family"), ("is_group", "=", True)], limit=1)
        cls.outsider = env["spp.group.membership"].search([("group", "=", dahal_family.id)], limit=1).individual
        cls.category = env.ref("spp_demo_child_benefit.grm_category_other")

    def _login(self):
        self.authenticate("gurung", "Cbp-Parent-Demo-2026!")

    def _open_form(self):
        self._login()
        page = self.url_open("/my/ticket/new")
        self.assertEqual(page.status_code, 200, page.text[:500])
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text)
        self.assertTrue(match, "csrf token not found")
        return page.text, match.group(1)

    def _submit(self, csrf, name, registrant_id=None):
        data = {
            "csrf_token": csrf,
            "ticket_name": name,
            "description": "Filed through the portal",
            "category_id": str(self.category.id),
        }
        if registrant_id is not None:
            data["registrant_id"] = str(registrant_id)
        return self.url_open("/my/ticket/submit", data=data)

    def test_form_lists_family_with_submitter_preselected(self):
        html, _csrf = self._open_form()
        self.assertIn('name="registrant_id"', html)
        options = re.findall(
            r'<option[^>]*value="(\d+)"([^>]*)>', html.split('name="registrant_id"', 1)[1].split("</select>", 1)[0]
        )
        self.assertEqual({int(v) for v, _ in options}, set(self.members.ids))
        selected = [int(v) for v, attrs in options if "selected" in attrs]
        self.assertEqual(selected, [self.gurung.id])
        # First option is the submitter.
        self.assertEqual(int(options[0][0]), self.gurung.id)
        self.assertNotIn(self.outsider.name, html)

    def test_submit_for_a_child_links_registrant_and_household(self):
        _html, csrf = self._open_form()
        resp = self._submit(csrf, "Child's school certificate missing", self.child.id)
        self.assertEqual(resp.status_code, 200, resp.text[:500])
        ticket = self.env["spp.grm.ticket"].search([("name", "=", "Child's school certificate missing")])
        self.assertEqual(len(ticket), 1)
        # Submission lands on the grievance's own page.
        self.assertTrue(resp.url.endswith(f"/my/ticket/{ticket.id}"), resp.url)
        self.assertEqual(ticket.partner_id, self.gurung)
        self.assertEqual(ticket.registrant_id, self.child)
        self.assertEqual(ticket.household_id, self.family)
        self.assertEqual(ticket.channel_id, self.env.ref("spp_grm.grm_ticket_channel_web"))
        # Still the submitter's own ticket in the portal list.
        self.assertEqual(ticket.with_user(self.gurung_user).name, "Child's school certificate missing")
        # And it now shows on the child's and the family's records.
        self.child.invalidate_recordset()
        self.family.invalidate_recordset()
        self.assertIn(ticket, self.child.grm_registrant_ticket_ids)
        self.assertIn(ticket, self.family.grm_household_ticket_ids)

    def test_submit_without_choice_defaults_to_self(self):
        _html, csrf = self._open_form()
        resp = self._submit(csrf, "Payment delayed again")
        self.assertEqual(resp.status_code, 200)
        ticket = self.env["spp.grm.ticket"].search([("name", "=", "Payment delayed again")])
        self.assertEqual(ticket.registrant_id, self.gurung)
        self.assertEqual(ticket.household_id, self.family)

    def test_submit_for_outsider_is_rejected(self):
        _html, csrf = self._open_form()
        for bad in (self.outsider.id, "abc", 999999):
            resp = self._submit(csrf, "Forged registrant", bad)
            self.assertEqual(resp.status_code, 400, f"registrant_id={bad!r} not rejected")
        self.assertFalse(self.env["spp.grm.ticket"].search([("name", "=", "Forged registrant")]))

    def test_ticket_list_shows_who_it_concerns(self):
        _html, csrf = self._open_form()
        self._submit(csrf, "Listed for child", self.child.id)
        page = self.url_open("/my/tickets")
        self.assertEqual(page.status_code, 200)
        self.assertIn(self.child.name, page.text)

    def test_portal_speaks_of_grievances_not_tickets(self):
        self._login()
        home = self.url_open("/my").text
        self.assertIn("Grievances", home)
        page = self.url_open("/my/tickets").text
        for expected in ("Grievances", "New Grievance", "Submitted by", "Concerns"):
            self.assertIn(expected, page)
        for gone in ("Ticket #", "New Ticket", "Your Tickets", ">Channel<", ">Priority<"):
            self.assertNotIn(gone, page)
        form = self.url_open("/my/ticket/new").text
        self.assertIn("New Grievance", form)
        self.assertIn("Submit grievance", form)
        self.assertNotIn("Ticket Name", form)

    def test_grievance_page_shows_details_and_conversation(self):
        self._login()
        mine = self.env["spp.grm.ticket"].search([("partner_id", "=", self.gurung.id)], limit=1)
        self.assertTrue(mine)
        # A message sent from the back office (not an internal note) is part of
        # the conversation the portal user can read.
        officer = self.env["res.users"].search([("login", "=", "officer")], limit=1)
        mine.with_user(officer).message_post(
            body="We have received your grievance and are looking into it.",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        mine.with_user(officer).message_post(body="internal only", message_type="comment", subtype_xmlid="mail.mt_note")
        page = self.url_open(f"/my/ticket/{mine.id}")
        self.assertEqual(page.status_code, 200, page.text[:500])
        text = html.unescape(page.text)
        for expected in (
            mine.number,
            mine.name,
            "o_portal_chatter",
            'data-res_model="spp.grm.ticket"',
            f'data-res_id="{mine.id}"',
        ):
            self.assertIn(expected, text)
        self.assertNotIn("birth_order", text)
        # Breadcrumb: home, Grievances, the reference - and no stock "Tickets" items.
        crumbs = text.split('class="o_portal_submenu', 1)[1].split("</ol>", 1)[0]
        self.assertIn("fa-home", crumbs)
        self.assertIn("Grievances", crumbs)
        self.assertIn(mine.number, crumbs)
        self.assertNotIn(">Tickets<", crumbs)
        self.assertNotIn("New Ticket", crumbs)
        # The conversation as the portal user sees it: the officer's message, not the note.
        data = self.make_jsonrpc_request(
            "/mail/thread/messages", {"thread_model": "spp.grm.ticket", "thread_id": mine.id, "limit": 30}
        )
        store = data.get("data") if isinstance(data.get("data"), dict) else data
        messages = store.get("mail.message", [])
        self.assertTrue(messages, f"no messages in the thread payload: {list(data)[:5]}")
        bodies = " ".join(str(m.get("body", "")) for m in messages if isinstance(m, dict))
        self.assertIn("We have received your grievance", bodies)
        self.assertNotIn("internal only", bodies)
        # Another family's grievance is not reachable.
        other = self.env["spp.grm.ticket"].search([("partner_id", "!=", self.gurung.id)], limit=1)
        self.assertEqual(self.url_open(f"/my/ticket/{other.id}").status_code, 404)

    def test_portal_user_can_reply_on_own_grievance_only(self):
        self._login()
        mine = self.env["spp.grm.ticket"].search([("partner_id", "=", self.gurung.id)], limit=1)
        before = len(mine.message_ids)
        result = self.make_jsonrpc_request(
            "/mail/message/post",
            {
                "thread_model": "spp.grm.ticket",
                "thread_id": mine.id,
                "post_data": {"body": "Thank you, the payment arrived today.", "message_type": "comment"},
            },
        )
        self.assertTrue(result.get("message_id"))
        mine.invalidate_recordset()
        self.assertEqual(len(mine.message_ids), before + 1)
        reply = self.env["mail.message"].browse(result["message_id"])
        self.assertEqual(reply.author_id, self.gurung)
        self.assertEqual(reply.model, "spp.grm.ticket")
        # Not on someone else's grievance.
        other = self.env["spp.grm.ticket"].search([("partner_id", "!=", self.gurung.id)], limit=1)
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request(
                "/mail/message/post",
                {
                    "thread_model": "spp.grm.ticket",
                    "thread_id": other.id,
                    "post_data": {"body": "x", "message_type": "comment"},
                },
            )
