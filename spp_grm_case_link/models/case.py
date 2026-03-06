# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class CaseGRMLink(models.Model):
    """Extend Case with GRM ticket integration."""

    _inherit = "spp.case"

    source_grm_ticket_id = fields.Many2one(
        "spp.grm.ticket",
        string="Source GRM Ticket",
        help="Ticket that initiated this case",
        tracking=True,
        ondelete="restrict",
    )
    grm_ticket_ids = fields.One2many(
        "spp.grm.ticket",
        "case_id",
        string="Related Tickets",
        help="GRM tickets linked to this case",
    )
    grm_ticket_count = fields.Integer(
        string="GRM Ticket Count",
        compute="_compute_grm_ticket_count",
        store=True,
        help="Number of GRM tickets linked to this case",
    )

    @api.depends("grm_ticket_ids")
    def _compute_grm_ticket_count(self):
        """Compute count of related GRM tickets."""
        for case in self:
            case.grm_ticket_count = len(case.grm_ticket_ids)

    def action_create_grm_ticket(self):
        """Create follow-up GRM ticket from case."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Create GRM Ticket",
            "res_model": "spp.grm.ticket",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_case_id": self.id,
                "default_name": f"Follow-up for Case {self.name}",
                "default_description": (
                    f"<p>Follow-up ticket for case <strong>{self.name}</strong></p>"
                    f"<p>Case Type: {self.case_type_id.name}</p>"
                    f"<p>Presenting Issue: {self.presenting_issue or ''}</p>"
                ),
            },
        }

    def action_view_grm_tickets(self):
        """View related GRM tickets."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Related GRM Tickets",
            "res_model": "spp.grm.ticket",
            "view_mode": "tree,form",
            "domain": [("case_id", "=", self.id)],
            "context": {
                "default_case_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }

        # If only one ticket, open it in form view
        if self.grm_ticket_count == 1:
            action["view_mode"] = "form"
            action["res_id"] = self.grm_ticket_ids[0].id

        return action
