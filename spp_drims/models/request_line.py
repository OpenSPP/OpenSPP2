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
    # OP#1079: allocation is now recorded per source warehouse. The totals
    # below are the sums of the per-warehouse allocation rows, which are the
    # source of truth (see spp.drims.request.allocation).
    allocation_ids = fields.One2many(
        "spp.drims.request.allocation",
        "request_line_id",
        string="Allocations",
    )
    quantity_allocated = fields.Float(
        string="Quantity Allocated",
        compute="_compute_allocation_totals",
        store=True,
        help="Total quantity allocated across all source warehouses",
    )
    quantity_dispatched = fields.Float(
        string="Quantity Dispatched",
        compute="_compute_allocation_totals",
        store=True,
        help="Total quantity sent out for delivery across all source warehouses",
    )

    @api.depends("allocation_ids.quantity_allocated", "allocation_ids.quantity_dispatched")
    def _compute_allocation_totals(self):
        for line in self:
            line.quantity_allocated = sum(line.allocation_ids.mapped("quantity_allocated"))
            line.quantity_dispatched = sum(line.allocation_ids.mapped("quantity_dispatched"))

    # OP#1075: flag a line where, after the request is approved, less has been
    # allocated than requested — used to show the shortfall in red on the form.
    is_allocation_short = fields.Boolean(
        string="Allocation Short",
        compute="_compute_is_allocation_short",
    )

    @api.depends("quantity_requested", "quantity_allocated", "request_id.approval_state")
    def _compute_is_allocation_short(self):
        for line in self:
            line.is_allocation_short = (
                line.request_id.approval_state == "approved" and line.quantity_allocated < line.quantity_requested
            )

    # OP#1075: outstanding quantity still to allocate — shown in the request's
    # "Not Allocated" section.
    quantity_short = fields.Float(
        string="Short",
        compute="_compute_quantity_short",
        help="Requested quantity that has not been allocated yet.",
    )

    @api.depends("quantity_requested", "quantity_allocated")
    def _compute_quantity_short(self):
        for line in self:
            line.quantity_short = max(0.0, line.quantity_requested - line.quantity_allocated)

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

    @api.depends("product_id", "quantity_requested")
    def _compute_display_name(self):
        """OP#1079: a readable label for the allocation wizard's Item picker
        (e.g. "Rice 25kg Bag (500 requested)") instead of the raw model,id."""
        for line in self:
            if line.product_id:
                line.display_name = f"{line.product_id.display_name} ({line.quantity_requested:g} requested)"
            else:
                line.display_name = _("Request Line")

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

    # OP#1079: fulfillment tracks how much of the requested quantity has been
    # allocated (stock committed across source warehouses), so the bar moves in
    # step with the "Fully Allocated" state instead of staying at 0 until a
    # separate delivery figure is entered. Capped at 100% for a sane bar.
    @api.depends("quantity_requested", "quantity_allocated")
    def _compute_fulfillment(self):
        for line in self:
            if line.quantity_requested:
                line.fulfillment_pct = min(100.0, (line.quantity_allocated / line.quantity_requested) * 100)
            else:
                line.fulfillment_pct = 0.0

    def _reconcile_quantity_dispatched(self):
        """Recompute ``quantity_dispatched`` from the dispatch moves that still stand.

        ``quantity_dispatched`` counts quantity committed to a dispatch picking,
        which ``spp.drims.request.action_create_dispatch`` increments when the
        picking is created rather than when it ships. Once moves are validated or
        cancelled that running total can drift from reality, so it is rebuilt
        here (OP#1087):

        - a cancelled move never shipped and no longer counts at all;
        - a done move counts what actually moved, not what was demanded, which is
          what makes declining "Create Backorder" release the balance;
        - a move still in progress keeps counting its demand, so a pending
          backorder stays committed to the request.

        ``quantity`` and ``product_uom_qty`` are both expressed in the move's
        ``product_uom``, which the dispatch sets to this line's ``uom_id``, so
        the two are directly comparable.

        Runs sudo: warehouse staff validating or cancelling a dispatch need not
        have write access to the request under the area record rules, and this is
        system bookkeeping rather than a user edit.
        """
        Move = self.env["stock.move"].sudo()
        for line in self.sudo():
            dispatched = 0.0
            for move in Move.search(
                [
                    ("drims_request_line_id", "=", line.id),
                    ("state", "!=", "cancel"),
                ]
            ):
                dispatched += move.quantity if move.state == "done" else move.product_uom_qty
            line.quantity_dispatched = dispatched
        self.sudo().request_id._reopen_if_not_fully_dispatched()

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
