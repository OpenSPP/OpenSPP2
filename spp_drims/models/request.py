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
    # OP#1075: choose whether the destination is a warehouse or a service point;
    # the matching field is shown conditionally in the form.
    destination_type = fields.Selection(
        [
            ("warehouse", "Warehouse"),
            ("service_point", "Service Point"),
        ],
        string="Destination Type",
        default="warehouse",
        tracking=True,
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

    # OP#1079: allocation is recorded per source warehouse in the Allocate
    # Stock wizard (there is no single source warehouse on the request any
    # more). These rows drive the on-request split display, the "Source
    # Warehouse(s)" list column and the per-warehouse dispatch.
    allocation_ids = fields.One2many(
        "spp.drims.request.allocation",
        "request_id",
        string="Allocations",
    )
    source_warehouse_names = fields.Char(
        string="Source Warehouse(s)",
        compute="_compute_source_warehouse_names",
        store=True,
        help="Warehouses stock has been allocated from for this request.",
    )

    @api.depends("allocation_ids.warehouse_id", "allocation_ids.quantity_allocated")
    def _compute_source_warehouse_names(self):
        for rec in self:
            warehouses = rec.allocation_ids.filtered(lambda a: a.quantity_allocated > 0).mapped("warehouse_id")
            rec.source_warehouse_names = ", ".join(sorted(warehouses.mapped("name"))) if warehouses else ""

    # Destination warehouse for dispatch
    destination_warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Destination Warehouse",
        domain="[('id', 'in', allowed_warehouse_ids), ('area_id', '=', destination_area_id)]",
        tracking=True,
        help="Warehouse in the destination area to receive the dispatch",
    )
    # OP#1164: warehouses selectable for this request — the incident's linked
    # warehouses when incident-filtering is enabled, otherwise all DRIMS
    # warehouses. Used to domain the source/destination warehouse fields.
    allowed_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        compute="_compute_allowed_warehouse_ids",
        string="Allowed Warehouses",
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
    # OP#1075: True when every requested line is fully allocated. Drives the
    # shortfall flag and disables the Allocate Stock button once nothing remains.
    is_fully_allocated = fields.Boolean(
        string="Fully Allocated",
        compute="_compute_is_fully_allocated",
    )

    @api.depends("line_ids.quantity_requested", "line_ids.quantity_allocated")
    def _compute_is_fully_allocated(self):
        for rec in self:
            lines = rec.line_ids
            rec.is_fully_allocated = bool(lines) and all(
                line.quantity_allocated >= line.quantity_requested for line in lines
            )

    # OP#1075: requested lines still short once the request is approved — drives
    # the "Not Allocated" section on the form (paired with allocation_ids, which
    # drives the "Allocated" section).
    unallocated_line_ids = fields.One2many(
        "spp.drims.request.line",
        compute="_compute_unallocated_line_ids",
        string="Not Allocated",
    )

    @api.depends("line_ids.is_allocation_short")
    def _compute_unallocated_line_ids(self):
        for rec in self:
            rec.unallocated_line_ids = rec.line_ids.filtered("is_allocation_short")

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

    @api.depends("incident_id", "incident_id.drims_warehouse_ids")
    def _compute_allowed_warehouse_ids(self):
        """OP#1164: selectable warehouses = the incident's warehouses when
        incident-filtering is on (and the incident has any), else all DRIMS
        warehouses. The fallback avoids locking out allocation/dispatch when an
        incident has no warehouses linked yet."""
        Warehouse = self.env["stock.warehouse"]
        filter_on = self.env["res.config.settings"].is_warehouse_filter_by_incident_enabled()
        all_drims = Warehouse.search([("is_drims_warehouse", "=", True)])
        for rec in self:
            incident_whs = rec.incident_id.drims_warehouse_ids
            rec.allowed_warehouse_ids = incident_whs if (filter_on and incident_whs) else all_drims

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
            rec.incident_id._drims_ensure_open(_("submit a request"))  # OP#1158
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
            rec.incident_id._drims_ensure_open(_("approve a request"))  # OP#1158
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

    def action_open_revision_wizard(self):
        """Open the request-changes wizard to collect required reviewer notes (OP#1161).

        The "Request Changes" button previously called ``action_request_revision``
        directly with no notes, so the submitter was sent back to revision with
        no explanation. This opens a small wizard (mirroring the Reject wizard)
        that collects a required notes text and then invokes
        ``action_request_revision(notes=...)``.
        """
        self.ensure_one()
        if self.approval_state not in ("pending", "submitted"):
            raise UserError(_("Only pending requests can be sent for revision."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Request Changes"),
            "res_model": "spp.drims.request.revision.wizard",
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

    def action_resubmit(self):
        """OP#1162: one-click resubmit of a revision-requested request.

        "Request Changes" moves the request to ``revision``; the submitter's
        "Resubmit for Approval" button lands here. Flip it back to ``draft`` and
        run the normal submit flow (``draft`` -> ``pending``). ``action_submit``
        cannot be called directly from ``revision`` because the approval mixin's
        submit guard (``_check_can_submit``) only accepts ``draft``.
        """
        for rec in self:
            if rec.approval_state != "revision":
                raise UserError(_("Only requests with requested changes can be resubmitted."))
            # A revision-requested request can still carry the original pending
            # approval review; mark it rejected so the fresh submission below
            # can create a new one without hitting the unique-pending constraint.
            rec.approval_review_ids.filtered(lambda r: r.status == "pending").write({"status": "rejected"})
            rec.approval_state = "draft"
        # Persist the review-status change now: action_submit creates the new
        # review via a sudo() env, which flushes independently — without this the
        # INSERT can run while the old review is still 'pending' in the DB and
        # trip the unique-pending exclusion constraint.
        self.env.flush_all()
        self.action_submit()
        return True

    def _set_state_by_code(self, code):
        """Set the request state to the vocab code, if it exists."""
        self.ensure_one()
        state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", code),
            ],
            limit=1,
        )
        if state:
            self.state_id = state
        return state

    def action_allocate(self):
        """Allocate stock across DRIMS warehouses to fulfill this request.

        For UI, use action_open_allocation_wizard() to preview and adjust the
        per-warehouse split before allocating. This programmatic path fills
        each line greedily from every DRIMS warehouse that holds stock
        (OP#1079).

        OP#1032: if no DRIMS warehouse has available stock for any requested
        item the auto-split is a no-op and the request must not silently
        advance to Ready for Dispatch with 0 allocated — raise instead so the
        state stays at Ready for Allocation.
        """
        for rec in self:
            rec.incident_id._drims_ensure_open(_("allocate a request"))  # OP#1158
            if rec.approval_state != "approved":
                raise UserError(_("Only approved requests can be allocated."))
            rec._auto_allocate()
            total_allocated = sum(rec.line_ids.mapped("quantity_allocated"))
            if total_allocated <= 0:
                raise UserError(
                    _(
                        "No stock available in any DRIMS warehouse for the "
                        "requested items. Please ensure stock exists before "
                        "allocating."
                    )
                )
            rec._set_state_by_code("allocated")
        return True

    def action_open_allocation_wizard(self):
        """Open allocation preview wizard (GAP-DIS-001).

        Allows users to preview stock availability and confirm allocation
        before committing changes.
        """
        self.ensure_one()
        if self.approval_state != "approved":
            raise UserError(_("Only approved requests can be allocated."))

        # Create wizard — it auto-populates a per-warehouse split from
        # availability in default_get (OP#1079).
        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": self.id,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Allocation Preview"),
            "res_model": "spp.drims.allocation.preview.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _drims_available_quantity(self, product, warehouse):
        """Net available quantity of ``product`` in ``warehouse`` for allocation.

        Physical on-hand (minus stock.quant reservations) minus the DRIMS
        allocations already committed against this warehouse but not yet
        dispatched. Physical stock is only moved at dispatch, so without
        subtracting pending allocations the same stock would be promised again
        on every re-open / to every request (OP#1033, OP#1079).
        """
        quants = self.env["stock.quant"].search(
            [
                ("product_id", "=", product.id),
                ("location_id", "child_of", warehouse.lot_stock_id.id),
            ]
        )
        physical = sum(q.quantity - q.reserved_quantity for q in quants)
        pending_allocations = self.env["spp.drims.request.allocation"].search(
            [
                ("product_id", "=", product.id),
                ("warehouse_id", "=", warehouse.id),
            ]
        )
        pending = sum(max(0.0, a.quantity_allocated - a.quantity_dispatched) for a in pending_allocations)
        return max(0.0, physical - pending)

    def _add_allocation(self, line, warehouse, qty):
        """Create or top up the (line, warehouse) allocation record by ``qty``."""
        if qty <= 0:
            return self.env["spp.drims.request.allocation"]
        existing = line.allocation_ids.filtered(lambda a: a.warehouse_id == warehouse)[:1]
        if existing:
            existing.quantity_allocated += qty
            return existing
        return self.env["spp.drims.request.allocation"].create(
            {
                "request_line_id": line.id,
                "warehouse_id": warehouse.id,
                "quantity_allocated": qty,
            }
        )

    def _auto_allocate(self):
        """Greedily allocate the unfilled balance of each line across DRIMS
        warehouses that hold net available stock (OP#1079).

        For each line the requested-but-unallocated quantity is filled from
        each DRIMS warehouse in turn (70 → 50 @ WH1 + 20 @ WH2) by creating
        per-warehouse allocation records, until the line is fully allocated or
        stock runs out.
        """
        self.ensure_one()
        warehouses = self.env["stock.warehouse"].search([("is_drims_warehouse", "=", True)])
        for line in self.line_ids:
            remaining = line.quantity_requested - line.quantity_allocated
            for warehouse in warehouses:
                if remaining <= 0:
                    break
                available = self._drims_available_quantity(line.product_id, warehouse)
                take = min(remaining, available)
                if take <= 0:
                    continue
                self._add_allocation(line, warehouse, take)
                remaining -= take
        return True

    def action_create_dispatch(self):
        """Create dispatch pickings for the not-yet-dispatched allocation
        balance of this request — **one picking per source warehouse**
        (GAP-REQ-003, OP#1033 partial dispatches, OP#1079 multi-warehouse).

        Each call covers only the **remaining** allocated quantity of each
        per-warehouse allocation record (``quantity_allocated -
        quantity_dispatched``) and groups those into one picking per warehouse
        the stock is coming from. The request state only advances to
        ``dispatched`` once every line is fully dispatched against its
        requested quantity — until then it stays at ``allocated`` so the
        button can be clicked again when more stock is allocated.

        Returns:
            dict: Action to view the created picking(s).

        Raises:
            UserError: If request is not allocated, an outgoing picking type is
                       missing for a source warehouse, or nothing remains to
                       dispatch on the current allocation.
        """
        self.ensure_one()
        if self.state != "allocated":
            raise UserError(_("Only allocated requests can be dispatched."))

        # Allocation records with stock not yet committed to a picking.
        pending_allocations = self.allocation_ids.filtered(lambda a: a.quantity_remaining > 0)
        if not pending_allocations:
            raise UserError(
                _(
                    "Nothing left to dispatch on this request. Allocate additional "
                    "stock first before creating another dispatch."
                )
            )

        # DRIMS dispatch type (shared across the pickings).
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

        # Determine destination location.
        if self.destination_warehouse_id:
            location_dest_id = self.destination_warehouse_id.lot_stock_id.id
        else:
            location_dest_id = self.env.ref("stock.stock_location_customers").id

        Move = self.env["stock.move"]
        pickings = self.env["stock.picking"]

        # One picking per source warehouse.
        for warehouse in pending_allocations.mapped("warehouse_id"):
            wh_allocations = pending_allocations.filtered(lambda a, wh=warehouse: a.warehouse_id == wh)

            picking_type = self.env["stock.picking.type"].search(
                [
                    ("warehouse_id", "=", warehouse.id),
                    ("code", "=", "outgoing"),
                ],
                limit=1,
            )
            if not picking_type:
                raise UserError(_("No delivery picking type found for warehouse %s") % warehouse.name)

            picking = self.env["stock.picking"].create(
                {
                    "picking_type_id": picking_type.id,
                    "location_id": warehouse.lot_stock_id.id,
                    "location_dest_id": location_dest_id,
                    "drims_request_id": self.id,
                    "drims_type_id": drims_type.id if drims_type else False,
                    "incident_id": self.incident_id.id,
                    "origin": self.reference,
                    "scheduled_date": self.date_needed,
                    "beneficiary_area_id": self.destination_area_id.id,
                }
            )

            # One move per allocation record's undispatched balance.
            for allocation in wh_allocations:
                qty_remaining = allocation.quantity_remaining
                Move.create(
                    {
                        "product_id": allocation.product_id.id,
                        "product_uom_qty": qty_remaining,
                        "product_uom": allocation.uom_id.id,
                        "picking_id": picking.id,
                        "location_id": picking.location_id.id,
                        "location_dest_id": picking.location_dest_id.id,
                        "drims_request_line_id": allocation.request_line_id.id,
                        "drims_allocation_id": allocation.id,
                    }
                )
                allocation.quantity_dispatched = allocation.quantity_dispatched + qty_remaining

            picking.action_confirm()
            pickings |= picking

        # Only advance to ``dispatched`` once every line is fully dispatched
        # against its requested quantity. Otherwise the request stays at
        # ``allocated`` so the user can allocate more and dispatch again.
        if all(line.quantity_dispatched >= line.quantity_requested for line in self.line_ids):
            self._set_state_by_code("dispatched")

        # Open the created picking(s).
        if len(pickings) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Dispatch"),
                "res_model": "stock.picking",
                "view_mode": "form",
                "res_id": pickings.id,
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Dispatches"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", pickings.ids)],
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
