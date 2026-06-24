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
        domain="[('is_drims_warehouse', '=', True)]",
        help="Warehouse to allocate from. Leave empty to see which warehouses "
        "currently hold stock for the requested items, then pick one.",
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

    @api.depends("warehouse_id", "request_id", "line_ids.shortfall", "has_shortfall")
    def _compute_alternative_warehouses(self):
        """Suggest DRIMS warehouses that hold stock for the requested items.

        OP#1079 — the suggestion depends on whether a source warehouse has
        been picked yet:

        * No warehouse selected (scenario 1): list every DRIMS warehouse that
          currently has stock for any requested item, so the user can choose
          where to allocate from before committing.
        * Warehouse selected but some items short (scenario 3): list the OTHER
          warehouses that hold stock for the short items.
        * Warehouse selected and stock sufficient (scenario 2): nothing to
          suggest.
        """
        for wizard in self:
            if not wizard.warehouse_id:
                products = wizard.request_id.line_ids.mapped("product_id")
                wizard.alternative_warehouse_ids = wizard._warehouses_with_stock(products)
                continue

            if not wizard.has_shortfall:
                wizard.alternative_warehouse_ids = False
                continue

            shortfall_products = wizard.line_ids.filtered(lambda line: line.shortfall > 0).mapped("product_id")
            wizard.alternative_warehouse_ids = wizard._warehouses_with_stock(
                shortfall_products, exclude=wizard.warehouse_id
            )

    def _warehouses_with_stock(self, products, exclude=None):
        """Return DRIMS warehouses with net available stock for any ``products``.

        Availability is the same net figure the wizard would actually be able
        to allocate (physical on-hand minus reservations and pending DRIMS
        allocations — see ``_get_available_quantity``), so a warehouse is only
        suggested when picking it would genuinely help.
        """
        self.ensure_one()
        if not products:
            return self.env["stock.warehouse"]
        domain = [("is_drims_warehouse", "=", True)]
        if exclude:
            domain.append(("id", "!=", exclude.id))
        result = self.env["stock.warehouse"]
        for wh in self.env["stock.warehouse"].search(domain):
            if any(self._get_available_quantity(product, wh) > 0 for product in products):
                result |= wh
        return result

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
        """Recalculate available quantities when the warehouse changes.

        When the warehouse is cleared, drop the lines too — otherwise stale
        availability from the previous warehouse lingers (e.g. "Total
        Available 500" with no warehouse selected). OP#1079.
        """
        if self.warehouse_id and self.request_id:
            self._populate_lines()
        else:
            self.line_ids = [Command.clear()]

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
                        # product_id is a stored related field off
                        # request_line_id, so it is derived server-side.
                        "request_line_id": request_line.id,
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

        # OP#1079: the source warehouse is optional when opening the wizard so
        # the user can first see where stock is available, but allocating from
        # nowhere is meaningless — require it at confirm time.
        if not self.warehouse_id:
            raise UserError(_("Please select a source warehouse to allocate from."))

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
    # Derived from the request line so it never has to be supplied by the web
    # client. When the source warehouse is changed the lines are recreated via
    # onchange as new client-side records; if product_id were a required input
    # the readonly column would be omitted from the save payload and the
    # record would fail to persist ("Missing required value for Product").
    # As a stored related field the server fills it from request_line_id.
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
