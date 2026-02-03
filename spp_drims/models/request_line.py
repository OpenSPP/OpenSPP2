# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DrimsRequestLine(models.Model):
    _name = "spp.drims.request.line"
    _description = "DRIMS Request Line"
    _order = "sequence, id"

    request_id = fields.Many2one(
        "spp.drims.request",
        string="Request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)

    # Product
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )

    # Quantities
    quantity_requested = fields.Float(
        string="Quantity Requested",
        required=True,
        default=1.0,
    )
    quantity_approved = fields.Float(
        string="Quantity Approved",
        default=0.0,
        help="Quantity approved by approver (may differ from requested)",
    )
    quantity_allocated = fields.Float(
        string="Quantity Allocated",
        default=0.0,
        help="Quantity allocated from warehouse stock",
    )
    quantity_dispatched = fields.Float(
        string="Quantity Dispatched",
        default=0.0,
        help="Quantity sent out for delivery",
    )
    quantity_delivered = fields.Float(
        string="Quantity Delivered",
        default=0.0,
        help="Quantity confirmed delivered at destination",
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        required=True,
    )

    # Valuation
    unit_value = fields.Float(
        string="Unit Value",
    )
    value = fields.Float(
        string="Total Value",
        compute="_compute_value",
        store=True,
    )

    # Fulfillment status
    fulfillment_pct = fields.Float(
        string="Fulfillment %",
        compute="_compute_fulfillment",
        store=True,
    )

    notes = fields.Text(string="Notes")

    @api.constrains("quantity_requested")
    def _check_quantity_positive(self):
        """Ensure quantity is positive."""
        for line in self:
            if line.quantity_requested <= 0:
                raise ValidationError(_("Quantity must be positive."))

    @api.depends("quantity_requested", "unit_value")
    def _compute_value(self):
        for line in self:
            line.value = line.quantity_requested * line.unit_value

    @api.depends("quantity_requested", "quantity_delivered")
    def _compute_fulfillment(self):
        for line in self:
            if line.quantity_requested:
                line.fulfillment_pct = (line.quantity_delivered / line.quantity_requested) * 100
            else:
                line.fulfillment_pct = 0.0

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
            self.unit_value = self.product_id.standard_price

    @api.model_create_multi
    def create(self, vals_list):
        """Set uom_id from product if not provided."""
        for vals in vals_list:
            if not vals.get("uom_id") and vals.get("product_id"):
                product = self.env["product.product"].browse(vals["product_id"])
                vals["uom_id"] = product.uom_id.id
        return super().create(vals_list)
