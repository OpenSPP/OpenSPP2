# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import UserError

VOCAB_RETURN_CONDITIONS = "urn:openspp:vocab:drims:return-conditions"


class DrimsReturn(models.Model):
    """DRIMS Item Return.

    Tracks returns of items from distribution points back to warehouses.
    Supports any product type (consumables and non-consumables).
    """

    _name = "spp.drims.return"
    _description = "DRIMS Item Return"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "reference"

    reference = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        tracking=True,
        index=True,
    )
    original_picking_id = fields.Many2one(
        "stock.picking",
        string="Original Dispatch",
        help="The original dispatch picking this return is for",
        domain="[('drims_type', '=', 'request_dispatch'), ('state', '=', 'done')]",
        index=True,
    )
    original_request_id = fields.Many2one(
        "spp.drims.request",
        string="Original Request",
        related="original_picking_id.drims_request_id",
        store=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Return To Warehouse",
        required=True,
        tracking=True,
        domain="[('is_drims_warehouse', '=', True)]",
        index=True,
    )
    return_date = fields.Date(
        string="Return Date",
        default=fields.Date.today,
        required=True,
    )

    # State machine
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("received", "Received"),
            ("inspected", "Inspected"),
            ("restocked", "Restocked"),
            ("cancelled", "Cancelled"),
        ],
        string="State",
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )

    # Return details
    return_reason = fields.Text(
        string="Return Reason",
        help="Explanation of why items are being returned",
    )
    returned_by = fields.Char(
        string="Returned By",
        help="Name of person returning the items",
    )
    returned_by_phone = fields.Char(string="Phone")

    # Lines
    line_ids = fields.One2many(
        "spp.drims.return.line",
        "return_id",
        string="Return Items",
    )

    # Stock picking for receipt
    picking_ids = fields.One2many(
        "stock.picking",
        "drims_return_id",
        string="Stock Receipts",
    )
    picking_count = fields.Integer(
        string="Receipt Count",
        compute="_compute_picking_count",
    )

    # Totals
    total_quantity = fields.Float(
        string="Total Quantity",
        compute="_compute_totals",
        store=True,
    )
    total_value = fields.Float(
        string="Total Value",
        compute="_compute_totals",
        store=True,
    )
    line_count = fields.Integer(
        string="Item Count",
        compute="_compute_totals",
        store=True,
    )

    # Multi-company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                vals["reference"] = self.env["ir.sequence"].next_by_code("spp.drims.return") or _("New")
        records = super().create(vals_list)
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(records)
        return records

    def write(self, vals):
        result = super().write(vals)
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(self)
        return result

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.depends("line_ids", "line_ids.quantity_returned", "line_ids.value")
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids
            rec.line_count = len(lines)
            rec.total_quantity = sum(lines.mapped("quantity_returned"))
            rec.total_value = sum(lines.mapped("value"))

    def action_confirm(self):
        """Confirm the return and create incoming stock picking."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft returns can be confirmed."))
            if not rec.line_ids:
                raise UserError(_("Please add items to return before confirming."))

            # Create incoming picking
            rec._create_return_picking()
            rec.state = "confirmed"
        return True

    def action_receive(self):
        """Mark items as received at warehouse."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(_("Only confirmed returns can be received."))
            rec.state = "received"
        return True

    def action_inspect(self):
        """Mark items as inspected."""
        for rec in self:
            if rec.state != "received":
                raise UserError(_("Only received returns can be inspected."))
            rec.state = "inspected"
        return True

    def action_restock(self):
        """Restock good items and complete the return."""
        for rec in self:
            if rec.state != "inspected":
                raise UserError(_("Only inspected returns can be restocked."))

            # Validate the stock picking to add items back to inventory
            for picking in rec.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")):
                picking.action_assign()
                for move in picking.move_ids:
                    move.quantity = move.product_uom_qty
                picking.button_validate()

            rec.state = "restocked"
        return True

    def action_cancel(self):
        """Cancel the return."""
        for rec in self:
            if rec.state == "restocked":
                raise UserError(_("Cannot cancel a restocked return."))
            # Cancel any pending pickings
            rec.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")).action_cancel()
            rec.state = "cancelled"
        return True

    def action_reset_to_draft(self):
        """Reset cancelled return to draft."""
        for rec in self:
            if rec.state != "cancelled":
                raise UserError(_("Only cancelled returns can be reset to draft."))
            rec.state = "draft"
        return True

    def _create_return_picking(self):
        """Create incoming stock picking for the return."""
        self.ensure_one()
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]

        # Get return location (customer location as source)
        customer_location = self.env.ref("stock.stock_location_customers")
        dest_location = self.warehouse_id.lot_stock_id

        # Get incoming picking type
        picking_type = self.env["stock.picking.type"].search(
            [
                ("warehouse_id", "=", self.warehouse_id.id),
                ("code", "=", "incoming"),
            ],
            limit=1,
        )

        if not picking_type:
            raise UserError(_("No incoming picking type found for warehouse %s") % self.warehouse_id.name)

        picking = Picking.create(
            {
                "picking_type_id": picking_type.id,
                "location_id": customer_location.id,
                "location_dest_id": dest_location.id,
                "origin": self.reference,
                "incident_id": self.incident_id.id,
                "drims_return_id": self.id,
                "drims_type_id": self._get_drims_type_return().id,
            }
        )

        # Create moves for each line
        for line in self.line_ids:
            move_vals = {
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity_returned,
                "product_uom": line.product_id.uom_id.id,
                "picking_id": picking.id,
                "location_id": customer_location.id,
                "location_dest_id": dest_location.id,
            }
            # Add description field for Odoo 19 compatibility
            if "description_picking" in Move._fields:
                move_vals["description_picking"] = line.product_id.name
            Move.create(move_vals)

        return picking

    def _get_drims_type_return(self):
        """Get or create the 'return' DRIMS type vocabulary code."""
        VocabCode = self.env["spp.vocabulary.code"]
        return_type = VocabCode.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:drims-types"),
                ("code", "=", "return"),
            ],
            limit=1,
        )
        if not return_type:
            # Fallback: search for any drims type
            return_type = VocabCode.search(
                [
                    ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:drims-types"),
                ],
                limit=1,
            )
        return return_type

    def action_view_pickings(self):
        """Open related stock pickings."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Receipts"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("drims_return_id", "=", self.id)],
        }

    def _invalidate_incident_kpi_cache(self, records):
        """Invalidate KPI cache for incidents related to these return records.

        This method is called after creating or updating returns to ensure
        that cached KPI values (like drims_return_value) are refreshed to
        reflect the latest return data.

        Args:
            records: Recordset of spp.drims.return records to process.
        """
        incident_ids = list(set(rec.incident_id.id for rec in records if rec.incident_id))
        if incident_ids:
            DataValue = self.env["spp.data.value"]
            # Delete stale cache entries for return KPI
            DataValue.search(
                [
                    ("variable_name", "=", "drims_return_value"),
                    ("subject_model", "=", "spp.hazard.incident"),
                    ("subject_id", "in", incident_ids),
                ]
            ).unlink()


class DrimsReturnLine(models.Model):
    """DRIMS Return Line.

    Individual items being returned.
    """

    _name = "spp.drims.return.line"
    _description = "DRIMS Return Line"
    _order = "sequence, id"

    return_id = fields.Many2one(
        "spp.drims.return",
        string="Return",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
        index=True,
    )
    quantity_dispatched = fields.Float(
        string="Originally Dispatched",
        help="Quantity that was originally dispatched",
    )
    quantity_returned = fields.Float(
        string="Quantity Returned",
        required=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        related="product_id.uom_id",
    )

    # Condition tracking
    condition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Condition",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_RETURN_CONDITIONS}')]",
        help="Condition of returned items (good, damaged, unusable)",
    )
    condition = fields.Char(
        related="condition_id.code",
        store=True,
    )

    # Disposition (GAP-RET-002)
    disposition = fields.Selection(
        [
            ("restock", "Restock"),
            ("repair", "Send for Repair"),
            ("dispose", "Dispose"),
        ],
        string="Disposition",
        default="restock",
        help="What to do with the returned items",
    )
    disposition_notes = fields.Char(
        string="Disposition Notes",
        help="Additional notes about disposition decision",
    )

    # Value
    unit_value = fields.Float(
        string="Unit Value",
        related="product_id.standard_price",
    )
    value = fields.Float(
        string="Total Value",
        compute="_compute_value",
        store=True,
    )

    notes = fields.Text(string="Notes")

    @api.depends("quantity_returned", "unit_value")
    def _compute_value(self):
        for line in self:
            line.value = line.quantity_returned * (line.unit_value or 0.0)

    @api.onchange("product_id", "return_id")
    def _onchange_product(self):
        """Auto-fill dispatched quantity from original picking if available."""
        if self.product_id and self.return_id.original_picking_id:
            original_move = self.return_id.original_picking_id.move_ids.filtered(
                lambda m: m.product_id == self.product_id
            )
            if original_move:
                self.quantity_dispatched = sum(original_move.mapped("quantity"))

    @api.onchange("condition_id")
    def _onchange_condition_id(self):
        """Auto-suggest disposition based on condition (GAP-RET-002)."""
        if not self.condition_id:
            return
        condition_code = self.condition_id.code
        # Map conditions to dispositions
        disposition_map = {
            "good": "restock",
            "new": "restock",
            "minor_damage": "repair",
            "damaged": "repair",
            "unusable": "dispose",
            "expired": "dispose",
            "contaminated": "dispose",
        }
        suggested = disposition_map.get(condition_code, "restock")
        self.disposition = suggested

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(records)
        return records

    def write(self, vals):
        result = super().write(vals)
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(self)
        return result

    def _invalidate_incident_kpi_cache(self, records):
        """Invalidate KPI cache for incidents related to these return line records.

        This method is called after creating or updating return lines to ensure
        that cached KPI values (like drims_return_value) are refreshed to
        reflect the latest return line data.

        Args:
            records: Recordset of spp.drims.return.line records to process.
        """
        incident_ids = list(
            set(rec.return_id.incident_id.id for rec in records if rec.return_id and rec.return_id.incident_id)
        )
        if incident_ids:
            DataValue = self.env["spp.data.value"]
            # Delete stale cache entries for return KPI
            DataValue.search(
                [
                    ("variable_name", "=", "drims_return_value"),
                    ("subject_model", "=", "spp.hazard.incident"),
                    ("subject_id", "in", incident_ids),
                ]
            ).unlink()
