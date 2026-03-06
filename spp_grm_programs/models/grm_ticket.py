from odoo import api, fields, models


class GRMTicketPrograms(models.Model):
    """Extend GRM Ticket with program-related fields."""

    _inherit = "spp.grm.ticket"

    # Program-related fields
    program_id = fields.Many2one(
        "spp.program",
        string="Related Program",
        help="Program related to this complaint",
        index=True,
    )
    program_membership_id = fields.Many2one(
        "spp.program.membership",
        string="Program Membership",
        help="Specific program enrollment related to this complaint",
        index=True,
    )
    cycle_id = fields.Many2one(
        "spp.cycle",
        string="Program Cycle",
        help="Specific cycle related to this complaint",
        index=True,
    )
    entitlement_id = fields.Many2one(
        "spp.entitlement",
        string="Related Entitlement",
        help="Specific entitlement being disputed",
        index=True,
    )
    payment_id = fields.Many2one(
        "spp.payment",
        string="Related Payment",
        help="Specific payment being disputed",
        index=True,
    )

    # Computed information from related records
    enrollment_status = fields.Char(
        compute="_compute_program_info",
        store=True,
        help="Current status of the program enrollment",
    )
    entitlement_amount = fields.Float(
        compute="_compute_program_info",
        store=True,
        help="Amount of the related entitlement",
    )
    payment_amount = fields.Float(
        compute="_compute_program_info",
        store=True,
        help="Amount of the related payment",
    )

    @api.depends("program_membership_id", "entitlement_id", "payment_id")
    def _compute_program_info(self):
        """Compute program-related information from linked records."""
        for ticket in self:
            # Compute enrollment status
            if ticket.program_membership_id:
                # Get the state selection field
                state_field = ticket.program_membership_id._fields.get("state")
                if state_field and hasattr(state_field, "selection"):
                    selection_dict = dict(state_field.selection)
                    ticket.enrollment_status = selection_dict.get(ticket.program_membership_id.state, "")
                else:
                    ticket.enrollment_status = ticket.program_membership_id.state or ""
            else:
                ticket.enrollment_status = ""

            # Compute entitlement amount
            if ticket.entitlement_id:
                # Check for initial_amount or amount fields
                if hasattr(ticket.entitlement_id, "initial_amount"):
                    ticket.entitlement_amount = ticket.entitlement_id.initial_amount
                elif hasattr(ticket.entitlement_id, "amount"):
                    ticket.entitlement_amount = ticket.entitlement_id.amount
                else:
                    ticket.entitlement_amount = 0.0
            else:
                ticket.entitlement_amount = 0.0

            # Compute payment amount
            if ticket.payment_id:
                # Check for amount_issued or amount fields
                if hasattr(ticket.payment_id, "amount_issued"):
                    ticket.payment_amount = ticket.payment_id.amount_issued
                elif hasattr(ticket.payment_id, "amount"):
                    ticket.payment_amount = ticket.payment_id.amount
                else:
                    ticket.payment_amount = 0.0
            else:
                ticket.payment_amount = 0.0

    @api.onchange("registrant_id", "program_id")
    def _onchange_program_membership(self):
        """Auto-fill membership when registrant and program are set."""
        if self.registrant_id and self.program_id:
            membership = self.env["spp.program.membership"].search(
                [
                    ("partner_id", "=", self.registrant_id.id),
                    ("program_id", "=", self.program_id.id),
                ],
                limit=1,
            )
            if membership:
                self.program_membership_id = membership.id

    @api.onchange("program_membership_id")
    def _onchange_membership(self):
        """Auto-fill program and registrant when membership is set."""
        if self.program_membership_id:
            self.program_id = self.program_membership_id.program_id.id
            # Only set registrant if not already set
            if not self.registrant_id:
                self.registrant_id = self.program_membership_id.partner_id.id

    @api.onchange("cycle_id")
    def _onchange_cycle(self):
        """Auto-fill program and clear downstream fields when cycle changes."""
        self.entitlement_id = False
        self.payment_id = False
        if self.cycle_id and not self.program_id:
            self.program_id = self.cycle_id.program_id.id

    @api.onchange("entitlement_id")
    def _onchange_entitlement(self):
        """Auto-fill related fields when entitlement is set."""
        self.payment_id = False
        if self.entitlement_id:
            # Set cycle and program if available
            if hasattr(self.entitlement_id, "cycle_id") and self.entitlement_id.cycle_id:
                self.cycle_id = self.entitlement_id.cycle_id.id
                if hasattr(self.entitlement_id.cycle_id, "program_id") and not self.program_id:
                    self.program_id = self.entitlement_id.cycle_id.program_id.id

            # Set registrant if available
            if hasattr(self.entitlement_id, "partner_id") and self.entitlement_id.partner_id and not self.registrant_id:
                self.registrant_id = self.entitlement_id.partner_id.id

    @api.onchange("payment_id")
    def _onchange_payment(self):
        """Auto-fill related fields when payment is set."""
        if self.payment_id:
            # Set entitlement if available
            if (
                hasattr(self.payment_id, "entitlement_id")
                and self.payment_id.entitlement_id
                and not self.entitlement_id
            ):
                self.entitlement_id = self.payment_id.entitlement_id.id

            # Set cycle if available
            if hasattr(self.payment_id, "cycle_id") and self.payment_id.cycle_id:
                self.cycle_id = self.payment_id.cycle_id.id

            # Set registrant if available
            if hasattr(self.payment_id, "partner_id") and self.payment_id.partner_id and not self.registrant_id:
                self.registrant_id = self.payment_id.partner_id.id

    def action_view_program(self):
        """Open the related program."""
        self.ensure_one()
        if not self.program_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Program",
            "res_model": "spp.program",
            "res_id": self.program_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_entitlement(self):
        """Open the related entitlement."""
        self.ensure_one()
        if not self.entitlement_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Entitlement",
            "res_model": "spp.entitlement",
            "res_id": self.entitlement_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_payment(self):
        """Open the related payment."""
        self.ensure_one()
        if not self.payment_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Payment",
            "res_model": "spp.payment",
            "res_id": self.payment_id.id,
            "view_mode": "form",
            "target": "current",
        }
