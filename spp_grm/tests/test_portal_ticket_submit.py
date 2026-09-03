# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Portal grievance submission still works end to end with a read-only portal ACL.

The portal access-control entry on ``spp.grm.ticket`` grants read only (#380);
submission goes through the sudo'd ``/my/ticket/submit`` controller. This pins
that route: the form page loads for a portal user (non-sudo category/channel
lookups), the POST creates the ticket for the submitter's partner on the web
channel, and the submitter can read it back.
"""

import re

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPortalTicketSubmit(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.portal = cls.env["res.users"].create(
            {
                "name": "Portal Submitter",
                "login": "grm_portal_submit",
                "password": "grm_portal_submit_pw",
                "group_ids": [Command.link(cls.env.ref("base.group_portal").id)],
            }
        )
        cls.category = cls.env["spp.grm.ticket.category"].create({"name": "Portal Cat"})

    def test_portal_submit_route_creates_own_ticket(self):
        self.authenticate("grm_portal_submit", "grm_portal_submit_pw")
        page = self.url_open("/my/ticket/new")
        self.assertEqual(page.status_code, 200, page.text[:500])
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text)
        self.assertTrue(match, "csrf token not found in /my/ticket/new form")
        resp = self.url_open(
            "/my/ticket/submit",
            data={
                "csrf_token": match.group(1),
                "ticket_name": "Portal grievance",
                "description": "Submitted through the portal",
                "category_id": str(self.category.id),
            },
        )
        self.assertEqual(resp.status_code, 200, resp.text[:500])
        self.assertTrue(resp.url.endswith("/my/tickets"), resp.url)
        ticket = self.env["spp.grm.ticket"].search([("name", "=", "Portal grievance")])
        self.assertEqual(len(ticket), 1)
        self.assertEqual(ticket.partner_id, self.portal.partner_id)
        self.assertEqual(ticket.channel_id, self.env.ref("spp_grm.grm_ticket_channel_web"))
        self.assertEqual(ticket.category_id, self.category)
        # The submitter can read their own ticket back over the model layer.
        self.assertEqual(ticket.with_user(self.portal).name, "Portal grievance")
