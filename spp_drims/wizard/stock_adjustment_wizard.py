# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Stock Adjustment Wizard (GAP-INV-001)

Provides a DRIMS-specific way to adjust stock with incident tracking.
Standard Odoo inventory adjustment doesn't capture DRIMS context
(incident, reason, authorization).
"""

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class DrimsStockAdjustmentWizard(models.TransientModel):
    _name = "spp.drims.stock.adjustment.wizard"
    _description = "DRIMS Stock Adjustment"

    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        help="Incident context for this adjustment",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Warehouse",
        required=True,
        domain="[('is_drims_warehouse', '=', True)]",
    )
    reason = fields.Selection(
        [
            ("damage", "Damaged"),
            ("loss", "Lost"),
            ("theft", "Theft"),
            ("expired", "Expired"),
            ("error", "Counting Error"),
            ("other", "Other"),
        ],
        string="Reason",
        required=True,
    )
    notes = fields.Text(string="Notes")
    authorized_by_id = fields.Many2one(
        "res.users",
        string="Authorized By",
        default=lambda self: self.env.user,
    )
    line_ids = fields.One2many(
        "spp.drims.stock.adjustment.wizard.line",
        "wizard_id",
        string="Adjustment Lines",
    )

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        """Clear lines when warehouse changes."""
        if self.warehouse_id:
            self.line_ids = [Command.clear()]

    def action_add_products(self):
        """Open a view to select products to adjust."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Select Products"),
            "res_model": "product.product",
            "view_mode": "list",
            "target": "new",
            "domain": [("type", "=", "product")],
            "context": {
                "adjustment_wizard_id": self.id,
                "warehouse_id": self.warehouse_id.id,
            },
        }

    def action_apply_adjustment(self):
        """Apply the stock adjustment.

        Creates inventory adjustments for each line with DRIMS tracking.
        Logs activity in the DRIMS activity feed.
        """
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Please add at least one product to adjust."))

        StockQuant = self.env["stock.quant"]
        location = self.warehouse_id.lot_stock_id

        for line in self.line_ids:
            # Apply the adjustment using Odoo's inventory adjustment
            # nosemgrep: odoo-sudo-without-context
            StockQuant.with_context(inventory_mode=True).sudo()._update_available_quantity(
                line.product_id,
                location,
                line.adjustment_qty,
            )

        # Log to activity feed
        self._log_adjustment_activity()

        # Optionally create alert for significant losses
        if self.reason in ("theft", "loss") and sum(abs(line.adjustment_qty) for line in self.line_ids) > 100:
            self._create_loss_alert()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Stock Adjusted"),
                "message": _("Successfully adjusted %d product(s).") % len(self.line_ids),
                "type": "success",
            },
        }

    def _log_adjustment_activity(self):
        """Log the adjustment in DRIMS activity feed."""
        ActivityFeed = self.env.get("spp.drims.activity.feed")
        if ActivityFeed is None:
            return

        for line in self.line_ids:
            ActivityFeed.create(
                {
                    "incident_id": self.incident_id.id,
                    "activity_type": "stock_adjustment",
                    "description": _("Stock adjustment: %(product)s adjusted by %(qty)s (%(reason)s)")
                    % {
                        "product": line.product_id.display_name,
                        "qty": line.adjustment_qty,
                        "reason": dict(self._fields["reason"].selection).get(self.reason, self.reason),
                    },
                    "user_id": self.env.user.id,
                }
            )

    def _create_loss_alert(self):
        """Create alert for significant stock losses."""
        Alert = self.env.get("spp.drims.alert")
        if Alert is None:
            return

        alert_type = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:alert-types",
                ),
                ("code", "=", "stock_loss"),
            ],
            limit=1,
        )

        if alert_type:
            Alert.create(
                {
                    "incident_id": self.incident_id.id,
                    "alert_type_id": alert_type.id,
                    "title": _("Significant Stock Loss"),
                    "description": _("Stock adjustment recorded for %s items due to: %s")
                    % (len(self.line_ids), self.reason),
                }
            )


class DrimsStockAdjustmentWizardLine(models.TransientModel):
    _name = "spp.drims.stock.adjustment.wizard.line"
    _description = "DRIMS Stock Adjustment Line"

    wizard_id = fields.Many2one(
        "spp.drims.stock.adjustment.wizard",
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
    current_qty = fields.Float(
        string="Current Qty",
        compute="_compute_current_qty",
    )
    adjustment_qty = fields.Float(
        string="Adjustment",
        required=True,
        help="Positive to add, negative to remove",
    )
    new_qty = fields.Float(
        string="New Qty",
        compute="_compute_new_qty",
    )
    uom_id = fields.Many2one(
        related="product_id.uom_id",
        string="UoM",
    )

    @api.depends("product_id", "wizard_id.warehouse_id")
    def _compute_current_qty(self):
        StockQuant = self.env["stock.quant"]
        for line in self:
            if line.product_id and line.wizard_id.warehouse_id:
                quant = StockQuant.search(
                    [
                        ("product_id", "=", line.product_id.id),
                        (
                            "location_id",
                            "=",
                            line.wizard_id.warehouse_id.lot_stock_id.id,
                        ),
                    ],
                    limit=1,
                )
                line.current_qty = quant.quantity if quant else 0
            else:
                line.current_qty = 0

    @api.depends("current_qty", "adjustment_qty")
    def _compute_new_qty(self):
        for line in self:
            line.new_qty = line.current_qty + line.adjustment_qty
