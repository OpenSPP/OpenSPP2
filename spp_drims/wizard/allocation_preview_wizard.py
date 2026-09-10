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
    # Total Requested is stable (it comes from the request, not the editable
    # wizard rows), so it stays a plain compute. The volatile totals/flags below
    # are regular fields refreshed by _sync_flags on create and on every line
    # edit (via _onchange_line_ids): a *non-stored compute* over editable x2many
    # rows does not refresh reliably in the form — that is what made the header
    # "Total to Allocate" disagree with the row sum (OP#1079 round 4).
    total_requested = fields.Float(
        compute="_compute_total_requested",
        string="Total Requested",
        help="Total quantity still to allocate across all requested items.",
    )
    total_available = fields.Float(string="Total Available")
    total_to_allocate = fields.Float(string="Total to Allocate")
    has_shortfall = fields.Boolean(
        string="Has Shortfall",
        help="Some stock exists but less than the requested quantity.",
    )
    no_stock_available = fields.Boolean(
        string="No Stock Available",
        help="No DRIMS warehouse holds any stock for the requested items.",
    )
    is_partial_allocation = fields.Boolean(
        string="Partial Allocation",
        help="Enough stock exists, but the user chose to allocate less than requested.",
    )
    over_allocated = fields.Boolean(
        string="Over Allocated",
        help="A requested item has more allocated across its warehouse rows than was requested.",
    )

    @api.depends("request_id.line_ids.quantity_requested", "request_id.line_ids.quantity_allocated")
    def _compute_total_requested(self):
        for wizard in self:
            wizard.total_requested = sum(
                max(0.0, line.quantity_requested - line.quantity_allocated) for line in wizard.request_id.line_ids
            )

    @api.onchange("line_ids")
    def _onchange_line_ids(self):
        """Refresh the totals + warning flags whenever a row is added, edited or
        removed. Done via onchange (not a compute) because a non-stored compute
        over editable wizard rows does not refresh reliably in the form."""
        self._sync_flags()

    def _sync_flags(self):
        """Recompute the volatile totals and warning flags from the current rows.

        `remaining` is the still-unallocated balance summed once per request line
        (a line split across warehouses only "needs" its remaining quantity). The
        stock-based flags key off AVAILABLE stock, never off the user-editable To
        Allocate, so lowering To Allocate reads as a deliberate partial rather
        than a stock shortfall.
        """
        for wizard in self:
            remaining = sum(
                max(0.0, line.quantity_requested - line.quantity_allocated) for line in wizard.request_id.line_ids
            )
            wizard.total_available = sum(wizard.line_ids.mapped("available_qty"))
            wizard.total_to_allocate = sum(wizard.line_ids.mapped("quantity_to_allocate"))
            wizard.no_stock_available = remaining > 0 and wizard.total_available <= 0
            wizard.has_shortfall = remaining > 0 and 0 < wizard.total_available < remaining
            wizard.is_partial_allocation = (
                remaining > 0 and wizard.total_available >= remaining and wizard.total_to_allocate < remaining
            )
            over = False
            for req_line in wizard.request_id.line_ids:
                rows_qty = sum(row.quantity_to_allocate for row in wizard.line_ids if row.request_line_id == req_line)
                if req_line.quantity_allocated + rows_qty > req_line.quantity_requested + 1e-6:
                    over = True
            wizard.over_allocated = over

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
            # Seed the totals/flags so they are correct when the form first opens
            # (there is no line onchange on initial render).
            wizard._sync_flags()
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

        # OP#1079: never allocate a request line beyond its requested quantity
        # (rows can be added by hand; the wizard's over_allocated warning flags
        # this live, and this is the hard stop at confirm).
        for req_line in self.request_id.line_ids:
            proposed = sum(row.quantity_to_allocate for row in rows if row.request_line_id == req_line)
            if req_line.quantity_allocated + proposed > req_line.quantity_requested + 1e-6:
                raise UserError(
                    _(
                        "Cannot allocate more than requested for %(product)s "
                        "(requested %(req)g, already allocated %(alloc)g, this run %(now)g)."
                    )
                    % {
                        "product": req_line.product_id.display_name,
                        "req": req_line.quantity_requested,
                        "alloc": req_line.quantity_allocated,
                        "now": proposed,
                    }
                )

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
    # OP#1079: the warehouses actually offered for this row — DRIMS warehouses
    # that hold net stock for this item and aren't already used by another row.
    # Drives the row's Source Warehouse domain so adding a warehouse scales to
    # any number of warehouses (only stocked, unused ones appear in the picker).
    candidate_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        compute="_compute_candidate_warehouse_ids",
        string="Warehouses with Stock",
    )
    available_qty = fields.Float(
        string="Available",
        readonly=True,
        help="Net stock available for this item in the selected warehouse.",
    )
    quantity_to_allocate = fields.Float(
        string="To Allocate",
    )

    @api.depends(
        "request_line_id",
        "warehouse_id",
        "wizard_id.line_ids.warehouse_id",
        "wizard_id.line_ids.request_line_id",
    )
    def _compute_candidate_warehouse_ids(self):
        """OP#1079: offer only DRIMS warehouses that hold net stock for this
        row's item and aren't already used by another row (so you can't build a
        duplicate product+warehouse row). The row's own current warehouse always
        stays selectable. Until an item is picked, all DRIMS warehouses show."""
        warehouses = self.env["stock.warehouse"].search([("is_drims_warehouse", "=", True)])
        for line in self:
            product = line.request_line_id.product_id
            request = line.request_line_id.request_id
            if not product or not request:
                line.candidate_warehouse_ids = warehouses
                continue
            used_ids = {
                row.warehouse_id.id
                for row in line.wizard_id.line_ids
                if row.id != line.id and row.warehouse_id and row.request_line_id.product_id == product
            }
            candidate_ids = [
                wh.id
                for wh in warehouses
                if wh.id not in used_ids and request._drims_available_quantity(product, wh) > 0
            ]
            line.candidate_warehouse_ids = warehouses.browse(candidate_ids) | line.warehouse_id

    @api.onchange("warehouse_id")
    def _onchange_warehouse_id(self):
        """Refresh availability when the row's warehouse changes; clamp the
        quantity to what that warehouse has available."""
        if self.warehouse_id and self.product_id and self.request_line_id:
            self.available_qty = self.request_line_id.request_id._drims_available_quantity(
                self.product_id, self.warehouse_id
            )
            if self.quantity_to_allocate > self.available_qty:
                self.quantity_to_allocate = self.available_qty
        else:
            self.available_qty = 0.0
            self.quantity_to_allocate = 0.0

    @api.onchange("quantity_to_allocate")
    def _onchange_quantity_to_allocate(self):
        """Clamp the quantity to what this row's warehouse has available.

        The per-line rule (a line's rows must not exceed the requested quantity)
        is enforced at the wizard level via `over_allocated` (a live warning) and
        re-checked in `action_confirm_allocation`. It is deliberately NOT done
        here from sibling rows: a line reading its siblings during onchange sees
        stale values, which caused a freshly-edited row to snap back to 0."""
        if self.quantity_to_allocate < 0:
            self.quantity_to_allocate = 0.0
        elif self.quantity_to_allocate > self.available_qty:
            self.quantity_to_allocate = self.available_qty
