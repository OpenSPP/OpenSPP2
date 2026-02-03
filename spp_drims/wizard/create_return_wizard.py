# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Return Creation Wizard (GAP-RET-001)

Allows creating partial returns from completed dispatches with:
- Selection of items to return
- Editable quantities
- Condition per line
- Return reason capture
"""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CreateReturnWizard(models.TransientModel):
    _name = "spp.drims.create.return.wizard"
    _description = "Create DRIMS Return"

    picking_id = fields.Many2one(
        "stock.picking",
        string="Dispatch",
        required=True,
        readonly=True,
        domain="[('drims_type', '=', 'request_dispatch'), ('state', '=', 'done')]",
    )
    incident_id = fields.Many2one(
        related="picking_id.incident_id",
        string="Incident",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Return To",
        required=True,
        domain="[('is_drims_warehouse', '=', True)]",
    )
    return_reason = fields.Text(
        string="Return Reason",
        help="Explain why items are being returned",
    )
    returned_by = fields.Char(
        string="Returned By",
        help="Name of person returning the items",
    )
    line_ids = fields.One2many(
        "spp.drims.create.return.wizard.line",
        "wizard_id",
        string="Items to Return",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "stock.picking":
            picking_id = self.env.context.get("active_id")
            if picking_id:
                picking = self.env["stock.picking"].browse(picking_id)
                res["picking_id"] = picking_id
                res["warehouse_id"] = picking.picking_type_id.warehouse_id.id
        return res

    @api.onchange("picking_id")
    def _onchange_picking_id(self):
        """Populate lines from dispatch moves."""
        if not self.picking_id:
            self.line_ids = [Command.clear()]
            return

        lines = []
        for move in self.picking_id.move_ids.filtered(lambda m: m.state == "done"):
            lines.append(
                Command.create(
                    {
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "quantity_dispatched": move.quantity,
                        "quantity_to_return": move.quantity,
                    }
                )
            )
        self.line_ids = [Command.clear()] + lines

    def action_create_return(self):
        """Create the return with selected items."""
        self.ensure_one()

        # Check if any items to return
        lines_to_return = self.line_ids.filtered(lambda line: line.quantity_to_return > 0)
        if not lines_to_return:
            raise UserError(_("Please select at least one item to return."))

        # Check if return already exists
        if self.picking_id.drims_return_id:
            raise UserError(_("A return already exists for this dispatch."))

        _logger.info("Creating return from dispatch ID %s with %d lines", self.picking_id.id, len(lines_to_return))

        # Create return record
        Return = self.env["spp.drims.return"]
        return_vals = {
            "incident_id": self.picking_id.incident_id.id,
            "original_picking_id": self.picking_id.id,
            "warehouse_id": self.warehouse_id.id,
            "return_reason": self.return_reason,
            "returned_by": self.returned_by,
        }
        drims_return = Return.create(return_vals)

        # Create return lines
        ReturnLine = self.env["spp.drims.return.line"]
        for line in lines_to_return:
            ReturnLine.create(
                {
                    "return_id": drims_return.id,
                    "product_id": line.product_id.id,
                    "quantity_dispatched": line.quantity_dispatched,
                    "quantity_returned": line.quantity_to_return,
                    "condition_id": line.condition_id.id if line.condition_id else False,
                }
            )

        # Link return to picking
        self.picking_id.drims_return_id = drims_return.id

        # Open the return form
        return {
            "type": "ir.actions.act_window",
            "name": _("Return"),
            "res_model": "spp.drims.return",
            "view_mode": "form",
            "res_id": drims_return.id,
        }


class CreateReturnWizardLine(models.TransientModel):
    _name = "spp.drims.create.return.wizard.line"
    _description = "Create Return Wizard Line"

    wizard_id = fields.Many2one(
        "spp.drims.create.return.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    move_id = fields.Many2one(
        "stock.move",
        string="Original Move",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )
    uom_id = fields.Many2one(
        related="product_id.uom_id",
        string="UoM",
    )
    quantity_dispatched = fields.Float(
        string="Dispatched",
        readonly=True,
    )
    quantity_to_return = fields.Float(
        string="Return Qty",
    )
    condition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Condition",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:return-conditions')]",
    )
    is_return_this = fields.Boolean(
        string="Return",
        compute="_compute_is_return_this",
        store=True,
    )

    @api.depends("quantity_to_return")
    def _compute_is_return_this(self):
        for line in self:
            line.is_return_this = line.quantity_to_return > 0

    @api.onchange("quantity_to_return")
    def _onchange_quantity_to_return(self):
        """Validate and adjust return quantity with user feedback."""
        if self.quantity_to_return < 0:
            self.quantity_to_return = 0
            return {
                "warning": {
                    "title": _("Invalid Quantity"),
                    "message": _("Quantity cannot be negative. Set to 0."),
                }
            }
        elif self.quantity_to_return > self.quantity_dispatched:
            self.quantity_to_return = self.quantity_dispatched
            return {
                "warning": {
                    "title": _("Quantity Adjusted"),
                    "message": _("Return quantity cannot exceed dispatched quantity (%s).") % self.quantity_dispatched,
                }
            }
