# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class GrmTicketPortalChatter(models.Model):
    """Make the grievance conversation work for the citizen on the portal.

    - mail.thread requires write access on a record to post on it; the portal
      holds read-only access to its own grievances (own-tickets rule), so the
      portal chatter could show the conversation but not answer. Posting on a
      readable grievance is what the citizen-facing thread needs.
    - The contact who raised the grievance follows it, so a message sent from
      the back office proposes them as recipient and notifies them. Internal
      notes stay internal regardless of followers.
    """

    _inherit = "spp.grm.ticket"
    _mail_post_access = "read"

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            if ticket.partner_id:
                ticket.message_subscribe(partner_ids=ticket.partner_id.ids)
        return tickets
