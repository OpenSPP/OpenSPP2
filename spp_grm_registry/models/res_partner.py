from odoo import api, fields, models


class ResPartnerGRM(models.Model):
    _inherit = "res.partner"

    # GRM tickets where this partner is the registrant
    grm_registrant_ticket_ids = fields.One2many(
        "spp.grm.ticket",
        "registrant_id",
        string="GRM Tickets (Registrant)",
        help="Tickets where this partner is the registrant",
    )
    grm_registrant_ticket_count = fields.Integer(
        string="Total GRM Tickets",
        compute="_compute_grm_registrant_tickets",
        help="Total number of tickets filed by this registrant",
    )
    grm_registrant_open_count = fields.Integer(
        string="Open GRM Tickets",
        compute="_compute_grm_registrant_tickets",
        help="Number of open tickets filed by this registrant",
    )
    grm_household_ticket_ids = fields.One2many(
        "spp.grm.ticket",
        "household_id",
        string="GRM Tickets (Household)",
        help="Tickets related to this household",
    )
    grm_household_ticket_count = fields.Integer(
        string="Household GRM Tickets",
        compute="_compute_grm_household_tickets",
        help="Total number of tickets related to this household",
    )

    @api.depends("grm_registrant_ticket_ids", "grm_registrant_ticket_ids.is_closed")
    def _compute_grm_registrant_tickets(self):
        """Compute ticket counts for registrant."""
        for partner in self:
            tickets = partner.grm_registrant_ticket_ids
            partner.grm_registrant_ticket_count = len(tickets)
            partner.grm_registrant_open_count = len(tickets.filtered(lambda t: not t.is_closed))

    @api.depends("grm_household_ticket_ids")
    def _compute_grm_household_tickets(self):
        """Compute ticket counts for household."""
        for partner in self:
            partner.grm_household_ticket_count = len(partner.grm_household_ticket_ids)

    def action_view_grm_registrant_tickets(self):
        """View tickets where this partner is the registrant."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "GRM Tickets (Registrant)",
            "res_model": "spp.grm.ticket",
            "view_mode": "list,form,kanban",
            "domain": [("registrant_id", "=", self.id)],
            "context": {"default_registrant_id": self.id},
        }

    def action_view_grm_household_tickets(self):
        """View tickets where this partner is the household."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "GRM Tickets (Household)",
            "res_model": "spp.grm.ticket",
            "view_mode": "list,form,kanban",
            "domain": [("household_id", "=", self.id)],
            "context": {"default_household_id": self.id},
        }
