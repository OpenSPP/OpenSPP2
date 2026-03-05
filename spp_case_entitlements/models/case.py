"""Extend Case model with entitlement integration."""

from odoo import api, fields, models


class CaseEntitlements(models.Model):
    """Extend spp.case with entitlement tracking and management."""

    _inherit = "spp.case"

    # Entitlement Relations
    entitlement_ids = fields.Many2many(
        "spp.entitlement",
        "spp_case_entitlement_rel",
        "case_id",
        "entitlement_id",
        string="Entitlements",
        help="Program entitlements related to this case",
    )

    # Computed Entitlement Info
    entitlement_count = fields.Integer(
        string="Entitlement Count",
        compute="_compute_entitlement_info",
        store=True,
        help="Number of entitlements related to this case",
    )

    has_entitlements = fields.Boolean(
        string="Has Entitlements",
        compute="_compute_entitlement_info",
        store=True,
        help="Whether this case has any related entitlements",
    )

    approved_entitlement_count = fields.Integer(
        string="Approved Entitlements",
        compute="_compute_entitlement_info",
        store=True,
        help="Number of approved entitlements",
    )

    pending_entitlement_count = fields.Integer(
        string="Pending Entitlements",
        compute="_compute_entitlement_info",
        store=True,
        help="Number of pending entitlements",
    )

    total_entitlement_amount = fields.Monetary(
        string="Total Entitlement Value",
        compute="_compute_entitlement_info",
        store=False,
        currency_field="currency_id",
        help="Total value of all approved entitlements",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    @api.depends("entitlement_ids", "entitlement_ids.state", "entitlement_ids.initial_amount")
    def _compute_entitlement_info(self):
        """Compute entitlement-related information."""
        for case in self:
            entitlements = case.entitlement_ids
            case.entitlement_count = len(entitlements)
            case.has_entitlements = bool(entitlements)

            # Count by state
            approved = entitlements.filtered(lambda e: e.state == "approved")
            pending = entitlements.filtered(lambda e: e.state == "pending_validation")

            case.approved_entitlement_count = len(approved)
            case.pending_entitlement_count = len(pending)

            # Calculate total amount for approved entitlements
            total_amount = sum(approved.mapped("initial_amount"))
            case.total_entitlement_amount = total_amount

    @api.onchange("partner_id")
    def _onchange_partner_entitlements(self):
        """Load entitlements when client/partner is selected."""
        if self.partner_id:
            # Search for all entitlements for this partner
            entitlements = self.env["spp.entitlement"].search([("partner_id", "=", self.partner_id.id)])
            self.entitlement_ids = entitlements
        else:
            self.entitlement_ids = False

    def action_view_entitlements(self):
        """Open entitlements in a new window."""
        self.ensure_one()

        return {
            "name": "Entitlements",
            "type": "ir.actions.act_window",
            "res_model": "spp.entitlement",
            "view_mode": "list,form",
            "domain": [("id", "in", self.entitlement_ids.ids)],
            "context": {
                "create": False,
                "default_partner_id": self.partner_id.id,
            },
        }

    def action_view_approved_entitlements(self):
        """Open only approved entitlements."""
        self.ensure_one()

        approved_ids = self.entitlement_ids.filtered(lambda e: e.state == "approved").ids

        return {
            "name": "Approved Entitlements",
            "type": "ir.actions.act_window",
            "res_model": "spp.entitlement",
            "view_mode": "list,form",
            "domain": [("id", "in", approved_ids)],
            "context": {
                "create": False,
                "default_partner_id": self.partner_id.id,
            },
        }

    def action_view_pending_entitlements(self):
        """Open only pending entitlements."""
        self.ensure_one()

        pending_ids = self.entitlement_ids.filtered(lambda e: e.state == "pending_validation").ids

        return {
            "name": "Pending Entitlements",
            "type": "ir.actions.act_window",
            "res_model": "spp.entitlement",
            "view_mode": "list,form",
            "domain": [("id", "in", pending_ids)],
            "context": {
                "create": False,
                "default_partner_id": self.partner_id.id,
            },
        }
