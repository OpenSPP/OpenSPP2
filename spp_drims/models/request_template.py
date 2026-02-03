# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import Command, _, api, fields, models


class DrimsRequestTemplate(models.Model):
    _name = "spp.drims.request.template"
    _description = "DRIMS Request Template"
    _order = "name"

    name = fields.Char(
        string="Template Name",
        required=True,
    )
    description = fields.Text(string="Description")

    # Ownership
    user_id = fields.Many2one(
        "res.users",
        string="Owner",
        default=lambda self: self.env.user,
    )
    is_shared = fields.Boolean(
        string="Shared",
        default=False,
        help="Make this template available to all users",
    )

    # Template lines
    line_ids = fields.One2many(
        "spp.drims.request.template.line",
        "template_id",
        string="Template Items",
    )
    line_count = fields.Integer(
        string="Items",
        compute="_compute_line_count",
    )

    # Defaults
    priority_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Default Priority",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:priority-levels')]",
    )

    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)

    def action_create_request(self, incident_id=None, destination_area_id=None, date_needed=None):
        """Create a new request from this template.

        Args:
            incident_id: The incident for this request (required)
            destination_area_id: The destination area (required)
            date_needed: When items are needed (required)

        Returns:
            Action to view the created request
        """
        self.ensure_one()
        Request = self.env["spp.drims.request"]

        # Get from context if not provided
        ctx = self.env.context
        incident_id = incident_id or ctx.get("default_incident_id")
        destination_area_id = destination_area_id or ctx.get("default_destination_area_id")
        date_needed = date_needed or ctx.get("default_date_needed")

        # If still no required values, return action to open form for user to complete
        if not incident_id or not destination_area_id or not date_needed:
            # Build line vals for context
            line_vals = [
                Command.create(
                    {
                        "product_id": line.product_id.id,
                        "quantity_requested": line.quantity,
                        "uom_id": line.uom_id.id,
                        "notes": line.notes,
                    }
                )
                for line in self.line_ids
            ]
            return {
                "type": "ir.actions.act_window",
                "name": _("New Request from Template"),
                "res_model": "spp.drims.request",
                "view_mode": "form",
                "target": "current",
                "context": {
                    "default_priority_id": self.priority_id.id if self.priority_id else False,
                    "default_line_ids": line_vals,
                },
            }

        # Create request with all required values
        line_vals = [
            Command.create(
                {
                    "product_id": line.product_id.id,
                    "quantity_requested": line.quantity,
                    "uom_id": line.uom_id.id,
                    "notes": line.notes,
                }
            )
            for line in self.line_ids
        ]

        request = Request.create(
            {
                "incident_id": incident_id,
                "destination_area_id": destination_area_id,
                "date_needed": date_needed,
                "priority_id": self.priority_id.id if self.priority_id else False,
                "line_ids": line_vals,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.drims.request",
            "view_mode": "form",
            "res_id": request.id,
        }

    def action_use_template(self):
        """Open wizard to create request from this template (GAP-REQ-004)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Request from Template"),
            "res_model": "spp.drims.request.from.template.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_template_id": self.id},
        }


class DrimsRequestTemplateLine(models.Model):
    _name = "spp.drims.request.template.line"
    _description = "DRIMS Request Template Line"
    _order = "sequence, id"

    template_id = fields.Many2one(
        "spp.drims.request.template",
        string="Template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )
    quantity = fields.Float(
        string="Quantity",
        required=True,
        default=1.0,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        required=True,
    )
    notes = fields.Char(string="Notes")

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
