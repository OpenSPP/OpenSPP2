# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import models


class GrmTicketPortalChatter(models.Model):
    """Let a portal user reply on a grievance they can read.

    mail.thread requires write access on a record to post on it; the portal
    holds read-only access to its own grievances (own-tickets rule), so the
    portal chatter could show the conversation but not answer. Posting on a
    readable grievance is what the citizen-facing thread needs.
    """

    _inherit = "spp.grm.ticket"
    _mail_post_access = "read"
