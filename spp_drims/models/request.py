# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class DrimsRequest(models.Model):
    _name = "spp.drims.request"
    _description = "DRIMS Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "spp.approval.mixin"]
    _order = "date_needed asc, priority_id desc, id desc"

    # Reference
    reference = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )

    # Core fields
    name = fields.Char(
        string="Description",
        compute="_compute_name",
        store=True,
    )
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        required=True,
        tracking=True,
        index=True,
    )
    cluster_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Humanitarian Cluster",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:ocha:iasc:clusters')]",
        tracking=True,
        index=True,
        help="OCHA/IASC humanitarian cluster this request belongs to",
    )
    destination_area_id = fields.Many2one(
        "spp.area",
        string="Destination Area",
        required=True,
        tracking=True,
        index=True,
    )
    service_point_id = fields.Many2one(
        "spp.service.point",
        string="Service Point",
        help="Specific distribution point within the area",
    )

    # Priority
    priority_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Priority",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:priority-levels')]",
        tracking=True,
        index=True,
    )
    is_life_threatening = fields.Boolean(
        string="Life-Threatening Emergency",
        tracking=True,
        help="Check for immediate life-threatening situations",
    )

    # Dates
    date_requested = fields.Date(
        string="Date Requested",
        default=fields.Date.context_today,
        required=True,
    )
    date_needed = fields.Date(
        string="Date Needed",
        required=True,
        tracking=True,
    )

    # State (from vocabulary)
    state_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Fulfillment State",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:request-states')]",
        tracking=True,
        default=lambda self: self._get_default_state(),
    )
    state = fields.Char(
        related="state_id.code",
        store=True,
        index=True,
    )

    # Population
    affected_population = fields.Integer(
        string="Affected Population",
        help="Estimated number of people to be served",
    )
    justification = fields.Text(
        string="Justification",
        help="Explain why this request is needed",
    )

    # Requester
    requester_id = fields.Many2one(
        "res.users",
        string="Requester",
        default=lambda self: self.env.user,
        tracking=True,
        index=True,
    )

    # Source warehouse for allocation
    source_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Source Warehouse",
        domain="[('is_drims_warehouse', '=', True)]",
        tracking=True,
        help="Warehouse to fulfill request from",
    )
    # Destination warehouse for dispatch
    destination_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Destination Warehouse",
        domain="[('is_drims_warehouse', '=', True), ('area_id', '=', destination_area_id)]",
        tracking=True,
        help="Warehouse in the destination area to receive the dispatch",
    )

    # Contact
    contact_name = fields.Char(string="Contact Name")
    contact_phone = fields.Char(string="Contact Phone")

    # Rejection tracking
    rejection_reason = fields.Text(
        string="Rejection Reason",
        tracking=True,
    )
    revision_notes = fields.Text(
        string="Revision Notes",
        help="Notes from approver requesting changes",
    )

    # SLA Tracking (GAP-REQ-005)
    sla_status = fields.Selection(
        [
            ("on_time", "On Time"),
            ("warning", "At Risk"),
            ("breached", "Breached"),
        ],
        string="SLA Status",
        compute="_compute_sla_status",
        store=True,
    )
    sla_due_datetime = fields.Datetime(
        string="SLA Due",
        compute="_compute_sla_status",
        store=True,
    )
    sla_hours_remaining = fields.Float(
        string="Hours Remaining",
        compute="_compute_sla_hours_remaining",
    )

    # Lines
    line_ids = fields.One2many(
        "spp.drims.request.line",
        "request_id",
        string="Requested Items",
    )

    # Computed totals (stored and indexed for CEL)
    total_value = fields.Float(
        string="Total Value",
        compute="_compute_totals",
        store=True,
        index=True,
    )
    line_count = fields.Integer(
        string="Item Count",
        compute="_compute_totals",
        store=True,
    )
    total_quantity = fields.Float(
        string="Total Quantity",
        compute="_compute_totals",
        store=True,
    )

    # Fulfillment Progress (GAP-REQ-006)
    total_allocated = fields.Float(
        string="Total Allocated",
        compute="_compute_fulfillment_progress",
        store=True,
    )
    total_dispatched = fields.Float(
        string="Total Dispatched",
        compute="_compute_fulfillment_progress",
        store=True,
    )
    total_delivered = fields.Float(
        string="Total Delivered",
        compute="_compute_fulfillment_progress",
        store=True,
    )
    allocation_pct = fields.Float(
        string="Allocation %",
        compute="_compute_fulfillment_progress",
        store=True,
    )
    fulfillment_pct = fields.Float(
        string="Fulfillment %",
        compute="_compute_fulfillment_progress",
        store=True,
    )

    # Stock
    picking_ids = fields.One2many(
        "stock.picking",
        "drims_request_id",
        string="Dispatches",
    )
    picking_count = fields.Integer(
        compute="_compute_picking_count",
    )

    # Notes
    notes = fields.Text(string="Notes")

    # Multi-company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )

    # Constraints
    _reference_uniq = models.Constraint("unique(reference)", "Request reference must be unique!")

    @api.constrains("date_requested", "date_needed")
    def _check_date_needed(self):
        """Ensure date_needed is not before date_requested."""
        for rec in self:
            if rec.date_needed and rec.date_requested and rec.date_needed < rec.date_requested:
                raise ValidationError(_("Date needed cannot be before date requested."))

    @api.model
    def _get_default_state(self):
        return self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "draft"),
            ],
            limit=1,
        )

    @api.depends("reference", "destination_area_id")
    def _compute_name(self):
        for rec in self:
            area = rec.destination_area_id.name or _("Unknown")
            rec.name = f"{rec.reference} - {area}"

    @api.depends("line_ids.value", "line_ids.quantity_requested", "line_ids")
    def _compute_totals(self):
        for rec in self:
            rec.total_value = sum(rec.line_ids.mapped("value"))
            rec.total_quantity = sum(rec.line_ids.mapped("quantity_requested"))
            rec.line_count = len(rec.line_ids)

    @api.depends(
        "line_ids.quantity_requested",
        "line_ids.quantity_allocated",
        "line_ids.quantity_dispatched",
        "line_ids.quantity_delivered",
    )
    def _compute_fulfillment_progress(self):
        """Compute fulfillment progress aggregates (GAP-REQ-006)."""
        for rec in self:
            total_requested = sum(rec.line_ids.mapped("quantity_requested"))
            rec.total_allocated = sum(rec.line_ids.mapped("quantity_allocated"))
            rec.total_dispatched = sum(rec.line_ids.mapped("quantity_dispatched"))
            rec.total_delivered = sum(rec.line_ids.mapped("quantity_delivered"))

            if total_requested > 0:
                rec.allocation_pct = (rec.total_allocated / total_requested) * 100
                rec.fulfillment_pct = (rec.total_delivered / total_requested) * 100
            else:
                rec.allocation_pct = 0
                rec.fulfillment_pct = 0

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.depends("approval_state", "create_date", "priority_id")
    def _compute_sla_status(self):
        """Compute SLA status based on priority and time elapsed (GAP-REQ-005).

        SLA thresholds are configurable via Settings > DRIMS Configuration
        (requires spp_studio_drims module) or System Parameters:
        - drims.sla.hours.critical/high/routine/low
        - drims.sla.warning_threshold_pct
        """
        now = fields.Datetime.now()
        ConfigSettings = self.env["res.config.settings"]

        # Get warning threshold as decimal (e.g., 75 -> 0.75)
        warning_threshold = ConfigSettings.get_approval_sla_warning_pct() / 100.0

        for rec in self:
            # Only compute for pending approval states
            if rec.approval_state not in ("pending", "submitted"):
                rec.sla_status = False
                rec.sla_due_datetime = False
                continue

            # Get SLA hours based on priority using helper method
            priority_code = rec.priority_id.code if rec.priority_id else "routine"
            hours = ConfigSettings.get_approval_sla_hours(priority_code)

            # Calculate SLA due datetime from create_date
            if rec.create_date:
                rec.sla_due_datetime = rec.create_date + timedelta(hours=hours)

                # Calculate elapsed and remaining
                elapsed = (now - rec.create_date).total_seconds() / 3600
                remaining = hours - elapsed

                if remaining <= 0:
                    rec.sla_status = "breached"
                elif remaining <= hours * (1 - warning_threshold):
                    rec.sla_status = "warning"
                else:
                    rec.sla_status = "on_time"
            else:
                rec.sla_due_datetime = False
                rec.sla_status = False

    @api.depends("sla_due_datetime")
    def _compute_sla_hours_remaining(self):
        """Compute hours remaining until SLA breach."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.sla_due_datetime:
                remaining = (rec.sla_due_datetime - now).total_seconds() / 3600
                rec.sla_hours_remaining = max(0, remaining)
            else:
                rec.sla_hours_remaining = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                vals["reference"] = self.env["ir.sequence"].next_by_code("spp.drims.request") or _("New")
        return super().create(vals_list)

    def action_submit(self):
        """Submit request for approval."""
        submitted_state = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "submitted"),
            ],
            limit=1,
        )
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Cannot submit request without items."))
            rec.state_id = submitted_state
            # Trigger approval workflow if configured, otherwise just update state
            try:
                rec.action_submit_for_approval()
            except UserError as e:
                if "No approval workflow configured" in str(e):
                    # No approval workflow - mark as pending manually
                    rec.approval_state = "pending"
                else:
                    raise

    def _on_approve(self):
        """Called when approval is complete."""
        approved_state = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "approved"),
            ],
            limit=1,
        )
        self.state_id = approved_state

    def _on_reject(self):
        """Called when request is rejected."""
        rejected_state = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "rejected"),
            ],
            limit=1,
        )
        self.state_id = rejected_state

    def action_approve(self):
        """Approve the request (for direct approval without workflow)."""
        for rec in self:
            if rec.approval_state not in ("pending", "submitted"):
                raise UserError(_("Only pending requests can be approved."))
            rec.approval_state = "approved"
            rec._on_approve()
        return True

    def action_reject(self, reason=None):
        """Reject the request."""
        for rec in self:
            if rec.approval_state not in ("pending", "submitted"):
                raise UserError(_("Only pending requests can be rejected."))
            if reason:
                rec.rejection_reason = reason
            rec.approval_state = "rejected"
            rec._on_reject()
        return True

    def action_open_reject_wizard(self):
        """Open the reject wizard to collect a required rejection reason (OP#966).

        The Reject button on the form previously called ``action_reject``
        directly and the user had no way to enter a reason, so the audit
        trail lost the rationale. This action opens a small wizard that
        collects a required reason text and then invokes ``action_reject``
        with it.
        """
        self.ensure_one()
        if self.approval_state not in ("pending", "submitted"):
            raise UserError(_("Only pending requests can be rejected."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Reject Request"),
            "res_model": "spp.drims.request.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_request_id": self.id},
        }

    def action_request_revision(self, notes=None):
        """Request changes from the requester."""
        revision_state = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "draft"),
            ],
            limit=1,
        )
        for rec in self:
            if rec.approval_state not in ("pending", "submitted"):
                raise UserError(_("Only pending requests can be sent for revision."))
            if notes:
                rec.revision_notes = notes
            rec.approval_state = "revision"
            rec.state_id = revision_state
        return True

    def action_reset_to_draft(self):
        """Reset rejected request to draft for resubmission."""
        draft_state = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "draft"),
            ],
            limit=1,
        )
        for rec in self:
            if rec.approval_state != "rejected":
                raise UserError(_("Only rejected requests can be reset to draft."))
            rec.approval_state = "draft"
            rec.state_id = draft_state
            rec.rejection_reason = False
        return True

    def action_allocate(self):
        """Allocate stock to fulfill this request using FEFO.

        For UI, use action_open_allocation_wizard() to preview before allocating.

        OP#1032: if the source warehouse has zero available stock for every
        requested item, the FIFO loop is a no-op and the request would
        silently advance to Ready for Dispatch with 0 allocated. Instead,
        check the total allocated quantity after the run; if it's still 0
        across all lines, raise so the state stays at Ready for Allocation
        and the user is forced to pick a warehouse that actually has stock.
        """
        for rec in self:
            if rec.approval_state != "approved":
                raise UserError(_("Only approved requests can be allocated."))
            if not rec.source_warehouse_id:
                raise UserError(_("Please select a source warehouse before allocation."))
            rec._allocate_stock_fifo()
            total_allocated = sum(rec.line_ids.mapped("quantity_allocated"))
            if total_allocated <= 0:
                raise UserError(
                    _(
                        "No stock available in the selected warehouse. "
                        "Please ensure the source warehouse has sufficient items "
                        "before allocating."
                    )
                )
            # Update state to allocated
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
                rec.state_id = allocated_state
        return True

    def action_open_allocation_wizard(self):
        """Open allocation preview wizard (GAP-DIS-001).

        Allows users to preview stock availability and confirm allocation
        before committing changes.
        """
        self.ensure_one()
        if self.approval_state != "approved":
            raise UserError(_("Only approved requests can be allocated."))

        # Create wizard with pre-populated lines
        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": self.id,
                "warehouse_id": self.source_warehouse_id.id if self.source_warehouse_id else False,
            }
        )
        if wizard.warehouse_id:
            wizard._populate_lines()

        return {
            "type": "ir.actions.act_window",
            "name": _("Allocation Preview"),
            "res_model": "spp.drims.allocation.preview.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _allocate_stock_fifo(self):
        """Allocate stock using First-In First-Out (FIFO) logic.

        Quants are ordered by in_date ascending, so oldest stock is allocated first.
        """
        self.ensure_one()
        Quant = self.env["stock.quant"]
        for line in self.line_ids:
            remaining = line.quantity_requested - line.quantity_allocated
            if remaining <= 0:
                continue
            # Find available quants ordered by date (FIFO)
            quants = Quant.search(
                [
                    ("product_id", "=", line.product_id.id),
                    (
                        "location_id",
                        "child_of",
                        self.source_warehouse_id.lot_stock_id.id,
                    ),
                    ("quantity", ">", 0),
                ],
                order="in_date asc",
            )
            allocated = 0
            for quant in quants:
                available = quant.quantity - quant.reserved_quantity
                if available <= 0:
                    continue
                to_allocate = min(remaining - allocated, available)
                allocated += to_allocate
                if allocated >= remaining:
                    break
            line.quantity_allocated = line.quantity_allocated + allocated
        return True

    def action_create_dispatch(self):
        """Create a dispatch picking for the not-yet-dispatched balance of this
        request (GAP-REQ-003, OP#1033 — partial dispatches).

        Each call creates a picking covering only the **remaining** allocated
        quantity per line (``quantity_allocated - quantity_dispatched``). The
        request state only advances to ``dispatched`` once every line has
        ``quantity_dispatched >= quantity_requested`` — until then it stays at
        ``allocated`` (Ready for Dispatch) so the button can be clicked again
        when more stock is allocated.

        Returns:
            dict: Action to view the created picking.

        Raises:
            UserError: If request is not allocated, source warehouse missing,
                       outgoing picking type missing, or nothing remains to
                       dispatch on the current allocation.
        """
        self.ensure_one()
        if self.state != "allocated":
            raise UserError(_("Only allocated requests can be dispatched."))
        if not self.source_warehouse_id:
            raise UserError(_("Please select a source warehouse."))

        # Lines that still have allocated stock not yet committed to a picking.
        lines_to_dispatch = self.line_ids.filtered(lambda line: line.quantity_allocated - line.quantity_dispatched > 0)
        if not lines_to_dispatch:
            raise UserError(
                _(
                    "Nothing left to dispatch on this request. Allocate additional "
                    "stock first before creating another dispatch."
                )
            )

        # Get picking type for outgoing deliveries
        picking_type = self.env["stock.picking.type"].search(
            [
                ("warehouse_id", "=", self.source_warehouse_id.id),
                ("code", "=", "outgoing"),
            ],
            limit=1,
        )

        if not picking_type:
            raise UserError(_("No delivery picking type found for warehouse %s") % self.source_warehouse_id.name)

        # Get DRIMS dispatch type
        drims_type = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:drims-types",
                ),
                ("code", "=", "request_dispatch"),
            ],
            limit=1,
        )

        # Determine destination location
        if self.destination_warehouse_id:
            location_dest_id = self.destination_warehouse_id.lot_stock_id.id
        else:
            location_dest_id = self.env.ref("stock.stock_location_customers").id

        # Create picking
        picking_vals = {
            "picking_type_id": picking_type.id,
            "location_id": self.source_warehouse_id.lot_stock_id.id,
            "location_dest_id": location_dest_id,
            "drims_request_id": self.id,
            "drims_type_id": drims_type.id if drims_type else False,
            "incident_id": self.incident_id.id,
            "origin": self.reference,
            "scheduled_date": self.date_needed,
            "beneficiary_area_id": self.destination_area_id.id,
        }
        picking = self.env["stock.picking"].create(picking_vals)

        # Create moves for each line's not-yet-dispatched balance, and track
        # the running total on the request line.
        Move = self.env["stock.move"]
        for line in lines_to_dispatch:
            qty_remaining = line.quantity_allocated - line.quantity_dispatched
            Move.create(
                {
                    "product_id": line.product_id.id,
                    "product_uom_qty": qty_remaining,
                    "product_uom": line.uom_id.id,
                    "picking_id": picking.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "drims_request_line_id": line.id,
                }
            )
            # OP#974: Warehouse Staff hold read-only ACL on requests/lines. The
            # dispatch workflow advances the tracking quantity on their behalf,
            # so write this controlled field with elevated rights.
            line.sudo().quantity_dispatched = (  # nosemgrep: odoo-sudo-without-context
                line.quantity_dispatched + qty_remaining
            )

        # Confirm the picking
        picking.action_confirm()

        # Only advance to ``dispatched`` once every line is fully dispatched
        # against its requested quantity. Otherwise the request stays at
        # ``allocated`` so the user can allocate more and dispatch again.
        # nosemgrep: odoo-sudo-without-context
        if all(line.quantity_dispatched >= line.quantity_requested for line in self.sudo().line_ids):
            dispatched_state = self.env["spp.vocabulary.code"].search(
                [
                    (
                        "vocabulary_id.namespace_uri",
                        "=",
                        "urn:openspp:vocab:drims:request-states",
                    ),
                    ("code", "=", "dispatched"),
                ],
                limit=1,
            )
            if dispatched_state:
                # OP#974: state transition on behalf of read-only Warehouse Staff.
                self.sudo().state_id = dispatched_state  # nosemgrep: odoo-sudo-without-context

        # Open the picking form
        return {
            "type": "ir.actions.act_window",
            "name": _("Dispatch"),
            "res_model": "stock.picking",
            "view_mode": "form",
            "res_id": picking.id,
        }

    def action_view_pickings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dispatches"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("drims_request_id", "=", self.id)],
        }
