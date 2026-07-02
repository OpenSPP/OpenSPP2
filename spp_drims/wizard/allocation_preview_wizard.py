# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Allocation Preview Wizard (GAP-DIS-001)

Provides a preview of stock allocation before committing. Shows stock
availability per product and highlights items with insufficient stock.
"""

import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DrimsAllocationPreviewWizard(models.TransientModel):
    _name = "spp.drims.allocation.preview.wizard"
    _description = "Allocation Preview"

    request_id = fields.Many2one(
        "spp.drims.request",
        string="Request",
        required=True,
        readonly=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Source Warehouse",
        required=True,
        domain="[('is_drims_warehouse', '=', True)]",
    )
    line_ids = fields.One2many(
        "spp.drims.allocation.preview.wizard.line",
        "wizard_id",
        string="Allocation Lines",
    )
    has_shortfall = fields.Boolean(
        compute="_compute_has_shortfall",
        string="Has Shortfall",
    )
    total_requested = fields.Float(
        compute="_compute_totals",
        string="Total Requested",
    )
    total_available = fields.Float(
        compute="_compute_totals",
        string="Total Available",
    )
    total_to_allocate = fields.Float(
        compute="_compute_totals",
        string="Total to Allocate",
    )
    alternative_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        string="Alternative Warehouses",
        compute="_compute_alternative_warehouses",
    )

    @api.depends("line_ids.shortfall")
    def _compute_has_shortfall(self):
        for wizard in self:
            wizard.has_shortfall = any(line.shortfall > 0 for line in wizard.line_ids)

    @api.depends(
        "line_ids.quantity_requested",
        "line_ids.available_qty",
        "line_ids.quantity_to_allocate",
    )
    def _compute_totals(self):
        for wizard in self:
            wizard.total_requested = sum(wizard.line_ids.mapped("quantity_requested"))
            wizard.total_available = sum(wizard.line_ids.mapped("available_qty"))
            wizard.total_to_allocate = sum(wizard.line_ids.mapped("quantity_to_allocate"))

    @api.depends("warehouse_id", "line_ids.shortfall")
    def _compute_alternative_warehouses(self):
        """Find warehouses that have stock for items with shortfall."""
        for wizard in self:
            if not wizard.has_shortfall:
                wizard.alternative_warehouse_ids = False
                continue

            shortfall_products = wizard.line_ids.filtered(lambda line: line.shortfall > 0).mapped("product_id")

            if not shortfall_products:
                wizard.alternative_warehouse_ids = False
                continue

            # Find other DRIMS warehouses with stock
            other_warehouses = self.env["stock.warehouse"].search(
                [
                    ("is_drims_warehouse", "=", True),
                    ("id", "!=", wizard.warehouse_id.id),
                ]
            )

            alternatives = self.env["stock.warehouse"]
            for wh in other_warehouses:
                quants = self.env["stock.quant"].search(
                    [
                        ("product_id", "in", shortfall_products.ids),
                        ("location_id", "child_of", wh.lot_stock_id.id),
                        ("quantity", ">", 0),
                    ]
                )
                if quants:
                    alternatives |= wh

            wizard.alternative_warehouse_ids = alternatives

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") == "spp.drims.request":
            request_id = self.env.context.get("active_id")
            if request_id:
                request = self.env["spp.drims.request"].browse(request_id)
                res["request_id"] = request_id
                res["warehouse_id"] = request.source_warehouse_id.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            if wizard.warehouse_id and wizard.request_id and not wizard.line_ids:
                wizard._populate_lines()
        return wizards

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        """Recalculate available quantities when warehouse changes."""
        if self.warehouse_id and self.request_id:
            self._populate_lines()

    def _populate_lines(self):
        """Populate allocation lines from request lines."""
        self.ensure_one()
        lines = []
        for request_line in self.request_id.line_ids:
            remaining = request_line.quantity_requested - request_line.quantity_allocated
            if remaining <= 0:
                continue

            # Get available stock
            available = self._get_available_quantity(
                request_line.product_id,
                self.warehouse_id,
            )

            to_allocate = min(remaining, available)

            lines.append(
                Command.create(
                    {
                        "request_line_id": request_line.id,
                        "product_id": request_line.product_id.id,
                        "quantity_requested": remaining,
                        "available_qty": available,
                        "quantity_to_allocate": to_allocate,
                    }
                )
            )

        self.line_ids = [Command.clear()] + lines

    def _get_available_quantity(self, product, warehouse):
        """Net available quantity of ``product`` in ``warehouse``.

        Equals physical on-hand (minus stock.quant reservations) minus the
        DRIMS allocations that have been committed but not yet dispatched.
        Without this subtraction the wizard would happily over-allocate:
        physical stock isn't touched at allocation time, only at dispatch,
        so the same warehouse stock would appear "available" on every
        wizard re-open even though prior allocations had already consumed
        it logically (OP#1033 round 2).
        """
        quants = self.env["stock.quant"].search(
            [
                ("product_id", "=", product.id),
                ("location_id", "child_of", warehouse.lot_stock_id.id),
            ]
        )
        physical = sum(q.quantity - q.reserved_quantity for q in quants)

        # Pending DRIMS allocations against this warehouse for this product
        # — anything allocated but not yet dispatched is a logical reservation
        # we should not promise again.
        pending_lines = self.env["spp.drims.request.line"].search(
            [
                ("product_id", "=", product.id),
                ("request_id.source_warehouse_id", "=", warehouse.id),
            ]
        )
        pending = sum(max(0.0, line.quantity_allocated - line.quantity_dispatched) for line in pending_lines)
        return max(0.0, physical - pending)

    def action_confirm_allocation(self):
        """Apply the previewed allocation."""
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("No items to allocate."))

        # OP#1032: refuse to confirm an empty allocation. Without this guard
        # a user could pick a warehouse with zero available stock, the
        # wizard would show 0 across all lines, and confirming would still
        # advance the request to Ready for Dispatch with 0 allocated.
        total_to_allocate = sum(self.line_ids.mapped("quantity_to_allocate"))
        if total_to_allocate <= 0:
            raise UserError(
                _(
                    "No stock available in the selected warehouse. "
                    "Please ensure the source warehouse has sufficient items "
                    "before allocating."
                )
            )

        _logger.info(
            "Applying allocation for request %s from warehouse %s with %d lines",
            self.request_id.reference,
            self.warehouse_id.name,
            len(self.line_ids.filtered(lambda line: line.quantity_to_allocate > 0)),
        )

        # Update request source warehouse
        self.request_id.source_warehouse_id = self.warehouse_id

        # Apply allocations to request lines
        for line in self.line_ids:
            if line.quantity_to_allocate > 0:
                line.request_line_id.quantity_allocated = (
                    line.request_line_id.quantity_allocated + line.quantity_to_allocate
                )

        # Update request state to allocated
        allocated_state = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )
        if allocated_state:
            self.request_id.state_id = allocated_state

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Allocation Complete"),
                "message": _("Successfully allocated %d item(s) from %s.")
                % (
                    len(self.line_ids.filtered(lambda line: line.quantity_to_allocate > 0)),
                    self.warehouse_id.name,
                ),
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_change_warehouse(self):
        """Refresh the wizard with new warehouse selection."""
        self.ensure_one()
        self._populate_lines()
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class DrimsAllocationPreviewWizardLine(models.TransientModel):
    _name = "spp.drims.allocation.preview.wizard.line"
    _description = "Allocation Preview Line"

    wizard_id = fields.Many2one(
        "spp.drims.allocation.preview.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    request_line_id = fields.Many2one(
        "spp.drims.request.line",
        string="Request Line",
        required=True,
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
    quantity_requested = fields.Float(
        string="Requested",
        readonly=True,
    )
    available_qty = fields.Float(
        string="Available",
        readonly=True,
    )
    quantity_to_allocate = fields.Float(
        string="To Allocate",
    )
    shortfall = fields.Float(
        compute="_compute_shortfall",
        string="Shortfall",
    )
    allocation_status = fields.Selection(
        [
            ("full", "Full"),
            ("partial", "Partial"),
            ("none", "None"),
        ],
        compute="_compute_allocation_status",
        string="Status",
    )

    @api.depends("quantity_requested", "quantity_to_allocate")
    def _compute_shortfall(self):
        for line in self:
            line.shortfall = max(0, line.quantity_requested - line.quantity_to_allocate)

    @api.depends("quantity_requested", "quantity_to_allocate")
    def _compute_allocation_status(self):
        for line in self:
            if line.quantity_to_allocate >= line.quantity_requested:
                line.allocation_status = "full"
            elif line.quantity_to_allocate > 0:
                line.allocation_status = "partial"
            else:
                line.allocation_status = "none"

    @api.onchange("quantity_to_allocate")
    def _onchange_quantity_to_allocate(self):
        """Validate allocation quantity."""
        if self.quantity_to_allocate < 0:
            self.quantity_to_allocate = 0
        elif self.quantity_to_allocate > self.available_qty:
            self.quantity_to_allocate = self.available_qty
