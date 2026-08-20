# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DRIMS per-warehouse allocation record (OP#1079).

A request line can be fulfilled from more than one warehouse (e.g. a line for
70 units filled 50 from WH1 + 20 from WH2). Each ``spp.drims.request.allocation``
row captures the quantity allocated from a single warehouse for a single request
line, and how much of it has already been committed to a dispatch picking. The
request line's ``quantity_allocated`` / ``quantity_dispatched`` totals are the
sums of its allocation rows, so these records are the source of truth for the
allocation split, the on-request display, and the per-warehouse dispatch.
"""

from odoo import api, fields, models


class DrimsRequestAllocation(models.Model):
    _name = "spp.drims.request.allocation"
    _description = "DRIMS Request Allocation"
    _order = "request_line_id, warehouse_id, id"

    request_line_id = fields.Many2one(
        "spp.drims.request.line",
        string="Request Line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    # Stored related so it can serve as the One2many inverse on the request and
    # be grouped/searched at the request level for dispatch and the list column.
    request_id = fields.Many2one(
        "spp.drims.request",
        string="Request",
        related="request_line_id.request_id",
        store=True,
        index=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        related="request_line_id.product_id",
        store=True,
        readonly=True,
        index=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        related="product_id.uom_id",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Source Warehouse",
        required=True,
        domain="[('is_drims_warehouse', '=', True)]",
        index=True,
    )
    quantity_allocated = fields.Float(
        string="Quantity Allocated",
        required=True,
        default=0.0,
    )
    quantity_dispatched = fields.Float(
        string="Quantity Dispatched",
        default=0.0,
        help="Quantity from this warehouse already committed to a dispatch picking.",
    )
    quantity_remaining = fields.Float(
        string="To Dispatch",
        compute="_compute_quantity_remaining",
        help="Allocated quantity from this warehouse not yet committed to a picking.",
    )

    @api.depends("quantity_allocated", "quantity_dispatched")
    def _compute_quantity_remaining(self):
        for rec in self:
            rec.quantity_remaining = max(0.0, rec.quantity_allocated - rec.quantity_dispatched)
