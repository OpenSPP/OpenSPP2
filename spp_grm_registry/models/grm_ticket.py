from odoo import api, fields, models


class GRMTicketRegistry(models.Model):
    _inherit = "spp.grm.ticket"

    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        domain="[('is_registrant', '=', True), ('is_group', '=', False),"
        " ('individual_membership_ids.group', '=', household_id)]",
        help="Individual registrant filing complaint",
        index=True,
    )
    household_id = fields.Many2one(
        "res.partner",
        string="Household",
        domain="[('is_registrant', '=', True), ('is_group', '=', True)]",
        help="Household related to complaint",
        index=True,
    )
    area_id = fields.Many2one(
        "spp.area",
        string="Geographic Area",
        help="Area of the registrant",
        index=True,
    )

    # Repeat ticket detection
    repeat_count = fields.Integer(
        compute="_compute_repeat_count",
        store=True,
        help="Number of tickets from same registrant in last 6 months",
    )
    previous_ticket_ids = fields.Many2many(
        "spp.grm.ticket",
        "spp_grm_ticket_previous_rel",
        "ticket_id",
        "previous_ticket_id",
        string="Previous Tickets",
        compute="_compute_previous_tickets",
    )
    is_repeat = fields.Boolean(
        string="Is Repeat Ticket",
        compute="_compute_repeat_count",
        store=True,
        help="True if registrant has filed other tickets in last 6 months",
    )

    @api.depends("registrant_id", "create_date")
    def _compute_repeat_count(self):
        """Count previous tickets from same registrant."""
        six_months_ago = fields.Date.subtract(fields.Date.today(), months=6)
        for ticket in self:
            if ticket.registrant_id:
                count = self.search_count(
                    [
                        ("registrant_id", "=", ticket.registrant_id.id),
                        ("id", "!=", ticket.id),
                        ("create_date", ">=", six_months_ago),
                    ]
                )
                ticket.repeat_count = count
                ticket.is_repeat = count > 0
            else:
                ticket.repeat_count = 0
                ticket.is_repeat = False

    @api.depends("registrant_id", "create_date")
    def _compute_previous_tickets(self):
        """Get previous tickets from same registrant."""
        six_months_ago = fields.Date.subtract(fields.Date.today(), months=6)
        for ticket in self:
            if ticket.registrant_id:
                previous_tickets = self.search(
                    [
                        ("registrant_id", "=", ticket.registrant_id.id),
                        ("id", "!=", ticket.id),
                        ("create_date", ">=", six_months_ago),
                    ],
                    order="create_date desc",
                )
                ticket.previous_ticket_ids = previous_tickets
            else:
                ticket.previous_ticket_ids = False

    @api.onchange("registrant_id")
    def _onchange_registrant_id(self):
        """Auto-fill fields from registrant."""
        if self.registrant_id:
            # Fill partner_id with registrant
            self.partner_id = self.registrant_id.id

            # Fill area if available
            if hasattr(self.registrant_id, "area_id") and self.registrant_id.area_id:
                self.area_id = self.registrant_id.area_id.id

    @api.onchange("household_id")
    def _onchange_household_id(self):
        """Clear registrant when household changes."""
        self.registrant_id = False

    def action_view_previous_tickets(self):
        """View previous tickets from same registrant."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Previous Tickets",
            "res_model": "spp.grm.ticket",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", self.previous_ticket_ids.ids)],
            "context": self.env.context,
        }
