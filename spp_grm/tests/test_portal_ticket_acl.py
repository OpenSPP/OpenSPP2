# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: portal users must only reach their OWN grievance tickets.

Regression test for #380: spp.grm.ticket granted base.group_portal read/write/create
with NO ir.rule targeting portal, so a portal user could read and rewrite every
grievance in the system over RPC. The controller's partner_id scoping is
presentation-only. Fix: a portal record rule scoping to the user's own partner, and
the portal ACL row reduced to read-only (portal submission runs through the sudo'd
controller, which needs no direct model write/create).
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPortalTicketAcl(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"]
        cls.portal_a = Users.create(
            {
                "name": "Portal A",
                "login": "grm_portal_a",
                "group_ids": [Command.link(cls.env.ref("base.group_portal").id)],
            }
        )
        cls.portal_b = Users.create(
            {
                "name": "Portal B",
                "login": "grm_portal_b",
                "group_ids": [Command.link(cls.env.ref("base.group_portal").id)],
            }
        )
        Ticket = cls.env["spp.grm.ticket"]
        cls.ticket_a = Ticket.create(
            {
                "name": "A's grievance",
                "description": "Private to A",
                "partner_id": cls.portal_a.partner_id.id,
            }
        )
        cls.ticket_b = Ticket.create(
            {
                "name": "B's grievance",
                "description": "Private to B",
                "partner_id": cls.portal_b.partner_id.id,
            }
        )

    def test_portal_can_read_own_ticket(self):
        """A portal user reads their own grievance (controller-created)."""
        own = self.ticket_a.with_user(self.portal_a)
        self.assertEqual(own.name, "A's grievance")

    def test_portal_cannot_read_others_ticket(self):
        """A portal user must NOT be able to read another user's grievance."""
        with self.assertRaises(AccessError):
            self.ticket_b.with_user(self.portal_a).read(["name"])

    def test_portal_cannot_search_others_ticket(self):
        """search must not surface other users' grievances to a portal user."""
        visible = self.env["spp.grm.ticket"].with_user(self.portal_a).search([])
        self.assertIn(self.ticket_a, visible)
        self.assertNotIn(self.ticket_b, visible)

    def test_portal_cannot_write_any_ticket(self):
        """Portal ACL is read-only: no write on own or others' tickets over RPC
        (edits go through the controller, not direct model writes)."""
        with self.assertRaises(AccessError):
            self.ticket_a.with_user(self.portal_a).write({"name": "tampered"})
        with self.assertRaises(AccessError):
            self.ticket_b.with_user(self.portal_a).write({"name": "hijacked"})

    def test_portal_cannot_create_ticket_directly(self):
        """Portal ACL is read-only: direct model create is denied (submission is
        controller-mediated via sudo)."""
        with self.assertRaises(AccessError):
            self.env["spp.grm.ticket"].with_user(self.portal_a).create(
                {
                    "name": "direct",
                    "description": "bypass controller",
                    "partner_id": self.portal_a.partner_id.id,
                }
            )
