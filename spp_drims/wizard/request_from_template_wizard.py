# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Request from Template Wizard (GAP-REQ-004)

Allows users to create requests from templates with:
- Template selection
- Incident context
- Destination area and date needed
- Editable line quantities
"""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class RequestFromTemplateWizard(models.TransientModel):
    _name = "spp.drims.request.from.template.wizard"
    _description = "Create Request from Template"

    template_id = fields.Many2one(
        "spp.drims.request.template",
        string="Template",
        required=True,
        domain="['|', ('is_shared', '=', True), ('user_id', '=', uid)]",
    )
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        domain="[('status', '=', 'active')]",
    )
    destination_area_id = fields.Many2one(
        "spp.area",
        string="Destination Area",
        required=True,
    )
    date_needed = fields.Date(
        string="Date Needed",
        required=True,
        default=fields.Date.context_today,
    )
    priority_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Priority",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:priority-levels')]",
    )
    notes = fields.Text(string="Notes")
    line_ids = fields.One2many(
        "spp.drims.request.from.template.wizard.line",
        "wizard_id",
        string="Request Items",
    )

    @api.onchange("template_id")
    def _onchange_template_id(self):
        """Populate lines from template."""
        if not self.template_id:
            self.line_ids = [Command.clear()]
            return

        # Set default priority from template
        if self.template_id.priority_id and not self.priority_id:
            self.priority_id = self.template_id.priority_id

        # Populate lines from template
        lines = []
        for template_line in self.template_id.line_ids:
            lines.append(
                Command.create(
                    {
                        "product_id": template_line.product_id.id,
                        "quantity": template_line.quantity,
                        "uom_id": template_line.uom_id.id,
                        "notes": template_line.notes,
                    }
                )
            )
        self.line_ids = [Command.clear()] + lines

    def action_create_request(self):
        """Create request with wizard values."""
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("Please add at least one item to the request."))

        # Build line values
        line_vals = []
        for line in self.line_ids:
            if line.quantity <= 0:
                continue
            line_vals.append(
                Command.create(
                    {
                        "product_id": line.product_id.id,
                        "quantity_requested": line.quantity,
                        "uom_id": line.uom_id.id,
                        "notes": line.notes,
                    }
                )
            )

        if not line_vals:
            raise UserError(_("All items have zero quantity. Please adjust quantities."))

        _logger.info(
            "Creating request from template %s for incident %s with %d lines",
            self.template_id.name,
            self.incident_id.name,
            len(line_vals),
        )

        # Create the request
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident_id.id,
                "destination_area_id": self.destination_area_id.id,
                "date_needed": self.date_needed,
                "priority_id": self.priority_id.id if self.priority_id else False,
                "notes": self.notes,
                "line_ids": line_vals,
            }
        )

        # Return action to open the new request
        return {
            "type": "ir.actions.act_window",
            "name": _("Request"),
            "res_model": "spp.drims.request",
            "view_mode": "form",
            "res_id": request.id,
        }

    def action_preview(self):
        """Preview the request before creation."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": {"preview_mode": True},
        }


class RequestFromTemplateWizardLine(models.TransientModel):
    _name = "spp.drims.request.from.template.wizard.line"
    _description = "Request from Template Wizard Line"

    wizard_id = fields.Many2one(
        "spp.drims.request.from.template.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
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
        if self.product_id and not self.uom_id:
            self.uom_id = self.product_id.uom_id
