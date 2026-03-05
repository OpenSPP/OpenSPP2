# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class GRMTicketCaseLink(models.Model):
    """Extend GRM Ticket with Case Management integration."""

    _inherit = "spp.grm.ticket"

    case_id = fields.Many2one(
        "spp.case",
        string="Related Case",
        help="Case created from this ticket",
        tracking=True,
        ondelete="restrict",
    )
    case_count = fields.Integer(
        string="Case Count",
        compute="_compute_case_count",
        help="Number of cases linked to this ticket",
    )

    @api.depends("case_id")
    def _compute_case_count(self):
        """Compute count of related cases."""
        for ticket in self:
            ticket.case_count = 1 if ticket.case_id else 0

    def action_escalate_to_case(self):
        """Open wizard to escalate ticket to case."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Escalate to Case",
            "res_model": "spp.grm.escalate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_ticket_id": self.id,
            },
        }

    def action_view_case(self):
        """View related case."""
        self.ensure_one()
        if not self.case_id:
            return {}

        return {
            "type": "ir.actions.act_window",
            "name": "Related Case",
            "res_model": "spp.case",
            "view_mode": "form",
            "res_id": self.case_id.id,
            "target": "current",
        }
