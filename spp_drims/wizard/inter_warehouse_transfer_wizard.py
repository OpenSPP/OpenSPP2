# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Inter-Warehouse Transfer Wizard (GAP-INV-002)

Provides an easy way to transfer stock between DRIMS warehouses with
incident context. Standard Odoo internal transfers don't have DRIMS context.
"""

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class DrimsInterWarehouseTransfer(models.TransientModel):
    _name = "spp.drims.inter.warehouse.transfer"
    _description = "Inter-Warehouse Transfer"

    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        help="Incident context for this transfer",
    )
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Source Warehouse",
        required=True,
        domain="[('is_drims_warehouse', '=', True)]",
    )
    dest_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Destination Warehouse",
        required=True,
        domain="[('is_drims_warehouse', '=', True), ('id', '!=', source_warehouse_id)]",
    )
    reason = fields.Text(
        string="Reason",
        help="Explain why this transfer is needed",
    )
    scheduled_date = fields.Datetime(
        string="Scheduled Date",
        default=fields.Datetime.now,
        required=True,
    )
    line_ids = fields.One2many(
        "spp.drims.inter.warehouse.transfer.line",
        "wizard_id",
        string="Transfer Lines",
    )

    @api.constrains("source_warehouse_id", "dest_warehouse_id")
    def _check_different_warehouses(self):
        for rec in self:
            if rec.source_warehouse_id == rec.dest_warehouse_id:
                raise UserError(_("Source and destination warehouses must be different."))

    @api.onchange("source_warehouse_id")
    def _onchange_source_warehouse(self):
        """Clear lines when source warehouse changes."""
        if self.source_warehouse_id:
            self.line_ids = [Command.clear()]

    def action_create_transfer(self):
        """Create an internal transfer picking with DRIMS tracking.

        Creates a stock.picking for internal transfer from source to
        destination warehouse with DRIMS context (incident, type).
        """
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Please add at least one product to transfer."))

        # Validate quantities
        for line in self.line_ids:
            if line.quantity <= 0:
                raise UserError(_("Quantity must be positive for %s.") % line.product_id.display_name)
            if line.quantity > line.available_qty:
                raise UserError(
                    _("Insufficient stock for %s. Available: %s, Requested: %s")
                    % (line.product_id.display_name, line.available_qty, line.quantity)
                )

        # Get picking type for internal transfers
        picking_type = self.env["stock.picking.type"].search(
            [
                ("warehouse_id", "=", self.source_warehouse_id.id),
                ("code", "=", "internal"),
            ],
            limit=1,
        )

        if not picking_type:
            raise UserError(_("No internal picking type found for warehouse %s") % self.source_warehouse_id.name)

        # Get DRIMS transfer type
        drims_type = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:drims-types",
                ),
                ("code", "=", "transfer"),
            ],
            limit=1,
        )

        # Create picking
        picking_vals = {
            "picking_type_id": picking_type.id,
            "location_id": self.source_warehouse_id.lot_stock_id.id,
            "location_dest_id": self.dest_warehouse_id.lot_stock_id.id,
            "drims_type_id": drims_type.id if drims_type else False,
            "incident_id": self.incident_id.id,
            "origin": _("DRIMS Transfer: %s") % self.incident_id.name,
            "scheduled_date": self.scheduled_date,
            "note": self.reason,
        }
        picking = self.env["stock.picking"].create(picking_vals)

        # Create moves for each line
        Move = self.env["stock.move"]
        for line in self.line_ids:
            Move.create(
                {
                    "name": line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.quantity,
                    "product_uom": line.uom_id.id,
                    "picking_id": picking.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                }
            )

        # Confirm the picking
        picking.action_confirm()

        # Log to activity feed
        self._log_transfer_activity(picking)

        # Open the picking form
        return {
            "type": "ir.actions.act_window",
            "name": _("Internal Transfer"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": picking.id,
        }

    def _log_transfer_activity(self, picking):
        """Log the transfer in DRIMS activity feed."""
        ActivityFeed = self.env.get("spp.drims.activity.feed")
        if ActivityFeed is None:
            return

        ActivityFeed.create(
            {
                "incident_id": self.incident_id.id,
                "activity_type": "stock_transfer",
                "description": _("Inter-warehouse transfer created: %(source)s → %(dest)s (%(count)d items)")
                % {
                    "source": self.source_warehouse_id.name,
                    "dest": self.dest_warehouse_id.name,
                    "count": len(self.line_ids),
                },
                "user_id": self.env.user.id,
                "related_model": "stock.picking",
                "related_id": picking.id,
            }
        )


class DrimsInterWarehouseTransferLine(models.TransientModel):
    _name = "spp.drims.inter.warehouse.transfer.line"
    _description = "Inter-Warehouse Transfer Line"

    wizard_id = fields.Many2one(
        "spp.drims.inter.warehouse.transfer",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        domain="[('type', '=', 'product')]",
    )
    available_qty = fields.Float(
        string="Available",
        compute="_compute_available_qty",
    )
    quantity = fields.Float(
        string="Quantity",
        required=True,
    )
    uom_id = fields.Many2one(
        related="product_id.uom_id",
        string="UoM",
    )

    @api.depends("product_id", "wizard_id.source_warehouse_id")
    def _compute_available_qty(self):
        StockQuant = self.env["stock.quant"]
        for line in self:
            if line.product_id and line.wizard_id.source_warehouse_id:
                quants = StockQuant.search(
                    [
                        ("product_id", "=", line.product_id.id),
                        (
                            "location_id",
                            "child_of",
                            line.wizard_id.source_warehouse_id.lot_stock_id.id,
                        ),
                    ]
                )
                line.available_qty = sum(q.quantity - q.reserved_quantity for q in quants)
            else:
                line.available_qty = 0
