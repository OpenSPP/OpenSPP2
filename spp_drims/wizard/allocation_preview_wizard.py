# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Allocation Preview Wizard (GAP-DIS-001, OP#1079)

Proposes a per-warehouse allocation split for a request. On open it fills each
requested line greedily from the DRIMS warehouses that hold stock (70 → 50 @
WH1 + 20 @ WH2), showing one editable row per (line, warehouse). The user can
adjust the quantities or warehouses before confirming; confirming writes one
``spp.drims.request.allocation`` record per row so the split is captured on the
request and can be dispatched per warehouse.
"""

import logging

from odoo import _, api, fields, models
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
    line_ids = fields.One2many(
        "spp.drims.allocation.preview.wizard.line",
        "wizard_id",
        string="Allocation Lines",
    )
    has_shortfall = fields.Boolean(
        compute="_compute_totals",
        string="Has Shortfall",
    )
    total_requested = fields.Float(
        compute="_compute_totals",
        string="Total Requested",
        help="Total quantity still to allocate across all requested items.",
    )
    total_available = fields.Float(
        compute="_compute_totals",
        string="Total Available",
    )
    total_to_allocate = fields.Float(
        compute="_compute_totals",
        string="Total to Allocate",
    )

    @api.depends(
        "request_id",
        "line_ids.available_qty",
        "line_ids.quantity_to_allocate",
        "request_id.line_ids.quantity_requested",
        "request_id.line_ids.quantity_allocated",
    )
    def _compute_totals(self):
        for wizard in self:
            # Requested is counted once per request line (its unallocated
            # balance), not once per wizard row — a line split across two
            # warehouses still only "needs" its remaining quantity.
            remaining = 0.0
            for req_line in wizard.request_id.line_ids:
                remaining += max(0.0, req_line.quantity_requested - req_line.quantity_allocated)
            wizard.total_requested = remaining
            wizard.total_available = sum(wizard.line_ids.mapped("available_qty"))
            wizard.total_to_allocate = sum(wizard.line_ids.mapped("quantity_to_allocate"))
            wizard.has_shortfall = wizard.total_to_allocate < remaining

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not res.get("request_id") and self.env.context.get("active_model") == "spp.drims.request":
            res["request_id"] = self.env.context.get("active_id")
        return res

    @api.model_create_multi
    def create(self, vals_list):
        wizards = super().create(vals_list)
        for wizard in wizards:
            # Auto-build the per-warehouse split proposal once the request is
            # known and the caller hasn't supplied its own lines.
            if wizard.request_id and not wizard.line_ids:
                wizard.line_ids = wizard._build_split_lines(wizard.request_id)
        return wizards

    def _build_split_lines(self, request):
        """Build a greedy per-warehouse split proposal for ``request`` as
        One2many create commands (OP#1079).

        For each request line with an unallocated balance, fill it from each
        DRIMS warehouse that has net available stock. A local ``used`` map
        decrements availability as it is promised so the same stock is never
        proposed to two lines of the same product.
        """
        commands = []
        warehouses = self.env["stock.warehouse"].search([("is_drims_warehouse", "=", True)])
        used = {}
        for req_line in request.line_ids:
            remaining = req_line.quantity_requested - req_line.quantity_allocated
            if remaining <= 0:
                continue
            for warehouse in warehouses:
                if remaining <= 0:
                    break
                key = (req_line.product_id.id, warehouse.id)
                available = request._drims_available_quantity(req_line.product_id, warehouse) - used.get(key, 0.0)
                if available <= 0:
                    continue
                take = min(remaining, available)
                commands.append(
                    (
                        0,
                        0,
                        {
                            "request_line_id": req_line.id,
                            "warehouse_id": warehouse.id,
                            "quantity_requested": req_line.quantity_requested - req_line.quantity_allocated,
                            "available_qty": available,
                            "quantity_to_allocate": take,
                        },
                    )
                )
                used[key] = used.get(key, 0.0) + take
                remaining -= take
        return commands

    def action_confirm_allocation(self):
        """Apply the previewed split by creating per-warehouse allocations."""
        self.ensure_one()

        rows = self.line_ids.filtered(lambda line: line.quantity_to_allocate > 0)
        if not rows:
            raise UserError(
                _(
                    "Nothing to allocate. Set a quantity against at least one "
                    "warehouse, or ensure a DRIMS warehouse has stock for the "
                    "requested items."
                )
            )
        missing_wh = rows.filtered(lambda line: not line.warehouse_id)
        if missing_wh:
            raise UserError(_("Please select a source warehouse for every allocation row."))

        _logger.info(
            "Applying allocation for request %s across %d warehouse row(s)",
            self.request_id.reference,
            len(rows),
        )

        for row in rows:
            self.request_id._add_allocation(row.request_line_id, row.warehouse_id, row.quantity_to_allocate)

        self.request_id._set_state_by_code("allocated")

        warehouse_names = ", ".join(sorted(set(rows.mapped("warehouse_id.name"))))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Allocation Complete"),
                "message": _("Allocated %(qty)s unit(s) from %(wh)s.")
                % {
                    "qty": sum(rows.mapped("quantity_to_allocate")),
                    "wh": warehouse_names,
                },
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }


class DrimsAllocationPreviewWizardLine(models.TransientModel):
    _name = "spp.drims.allocation.preview.wizard.line"
    _description = "Allocation Preview Line"
    _order = "product_id, warehouse_id, id"

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
    # Derived from the request line so it never has to be supplied by the web
    # client. As a stored related field the server fills it from
    # request_line_id, so recreated rows persist without a "Missing required
    # value for Product" error.
    product_id = fields.Many2one(
        "product.product",
        related="request_line_id.product_id",
        string="Product",
        store=True,
        readonly=True,
    )
    uom_id = fields.Many2one(
        related="product_id.uom_id",
        string="UoM",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Source Warehouse",
        domain="[('is_drims_warehouse', '=', True)]",
    )
    quantity_requested = fields.Float(
        string="Still Needed",
        readonly=True,
        help="Quantity of this item still to be allocated on the request.",
    )
    available_qty = fields.Float(
        string="Available",
        readonly=True,
        help="Net stock available for this item in the selected warehouse.",
    )
    quantity_to_allocate = fields.Float(
        string="To Allocate",
    )

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        """Refresh availability when the row's warehouse changes."""
        if self.warehouse_id and self.product_id and self.request_line_id:
            available = self.request_line_id.request_id._drims_available_quantity(self.product_id, self.warehouse_id)
            self.available_qty = available
            if self.quantity_to_allocate > available:
                self.quantity_to_allocate = available
        else:
            self.available_qty = 0.0
            self.quantity_to_allocate = 0.0

    @api.onchange("quantity_to_allocate")
    def _onchange_quantity_to_allocate(self):
        """Clamp the allocation quantity to what is available."""
        if self.quantity_to_allocate < 0:
            self.quantity_to_allocate = 0
        elif self.quantity_to_allocate > self.available_qty:
            self.quantity_to_allocate = self.available_qty
