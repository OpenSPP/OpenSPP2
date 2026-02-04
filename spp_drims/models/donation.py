# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .constants import (
    DONATION_STATE_ANNOUNCED,
    DONATION_STATE_CANCELLED,
    DONATION_STATE_INSPECTED,
    DONATION_STATE_RECEIVED,
    DONATION_STATE_REJECTED,
    DONATION_STATE_STOCKED,
    DRIMS_TYPE_DONATION_RECEIPT,
    VOCAB_DONATION_STATES,
    VOCAB_DONOR_TYPES,
    VOCAB_DRIMS_TYPES,
    VOCAB_ITEM_CONDITIONS,
    VOCAB_ITEM_DISPOSITIONS,
    VOCAB_RESTRICTIONS,
)

_logger = logging.getLogger(__name__)

# Valid state transitions: {from_state: [allowed_to_states]}
DONATION_STATE_TRANSITIONS = {
    DONATION_STATE_ANNOUNCED: [DONATION_STATE_RECEIVED, DONATION_STATE_CANCELLED],
    DONATION_STATE_RECEIVED: [DONATION_STATE_INSPECTED, DONATION_STATE_CANCELLED],
    DONATION_STATE_INSPECTED: [
        DONATION_STATE_STOCKED,
        DONATION_STATE_REJECTED,
        DONATION_STATE_CANCELLED,
    ],
    DONATION_STATE_STOCKED: [],  # Terminal state
    DONATION_STATE_CANCELLED: [],  # Terminal state
    DONATION_STATE_REJECTED: [],  # Terminal state
}


class DrimsDonation(models.Model):
    _name = "spp.drims.donation"
    _description = "DRIMS Donation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_announced desc, id desc"

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
    donor_id = fields.Many2one(
        "res.partner",
        string="Donor",
        tracking=True,
    )
    donor_name = fields.Char(
        string="Donor Name",
        help="Use when donor is not in system",
    )
    source_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Donor Type",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_DONOR_TYPES}')]",
        tracking=True,
    )
    restriction_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Restriction",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_RESTRICTIONS}')]",
        tracking=True,
        help="E.g., 'Food only for District X', 'Medical supplies only'",
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Receiving Warehouse",
        required=True,
        tracking=True,
    )

    # Dates
    date_announced = fields.Date(
        string="Date Announced",
        default=fields.Date.context_today,
    )
    date_expected = fields.Date(
        string="Expected Arrival",
    )
    date_received = fields.Date(
        string="Date Received",
    )

    # State
    state_id = fields.Many2one(
        "spp.vocabulary.code",
        string="State",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_DONATION_STATES}')]",
        tracking=True,
        default=lambda self: self._get_default_state(),
    )
    state = fields.Char(
        related="state_id.code",
        store=True,
        index=True,
    )

    # Lines
    line_ids = fields.One2many(
        "spp.drims.donation.line",
        "donation_id",
        string="Donation Items",
    )

    # Computed
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

    # Stock
    picking_ids = fields.One2many(
        "stock.picking",
        "drims_donation_id",
        string="Stock Transfers",
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
    _reference_uniq = models.Constraint("unique(reference)", "Donation reference must be unique!")

    @api.constrains("state_id")
    def _check_state_transition(self):
        """Validate that state transitions follow allowed paths.

        This constraint prevents invalid state changes like going from
        'stocked' back to 'announced' or skipping the 'inspected' step.
        """
        for rec in self:
            if not rec.state:
                continue
            # Get the previous state from the context (set by write method)
            previous_state = self.env.context.get("_donation_previous_state", {}).get(rec.id)
            if previous_state and previous_state != rec.state:
                allowed = DONATION_STATE_TRANSITIONS.get(previous_state, [])
                if rec.state not in allowed:
                    raise ValidationError(
                        _(
                            "Invalid state transition for donation %(ref)s: "
                            "cannot go from '%(from_state)s' to '%(to_state)s'. "
                            "Allowed transitions: %(allowed)s"
                        )
                        % {
                            "ref": rec.reference,
                            "from_state": previous_state,
                            "to_state": rec.state,
                            "allowed": ", ".join(allowed) if allowed else "none (terminal state)",
                        }
                    )

    def write(self, vals):
        """Override write to track state changes for constraint validation."""
        if "state_id" in vals:
            # Store previous states in context for constraint validation
            previous_states = {rec.id: rec.state for rec in self}
            self = self.with_context(_donation_previous_state=previous_states)
        result = super().write(vals)
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(self)
        return result

    @api.model
    def _get_default_state(self):
        return self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_DONATION_STATES),
                ("code", "=", DONATION_STATE_ANNOUNCED),
            ],
            limit=1,
        )

    @api.depends("donor_id", "donor_name", "reference")
    def _compute_name(self):
        for rec in self:
            donor = rec.donor_id.name or rec.donor_name or _("Unknown Donor")
            rec.name = f"{rec.reference} - {donor}"

    @api.depends("line_ids.value", "line_ids")
    def _compute_totals(self):
        for rec in self:
            rec.total_value = sum(rec.line_ids.mapped("value"))
            rec.line_count = len(rec.line_ids)

    @api.depends("picking_ids")
    def _compute_picking_count(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", _("New")) == _("New"):
                vals["reference"] = self.env["ir.sequence"].next_by_code("spp.drims.donation") or _("New")
        records = super().create(vals_list)
        # Invalidate KPI cache for affected incidents
        self._invalidate_incident_kpi_cache(records)
        return records

    def action_mark_received(self):
        """Mark donation as received and create stock picking.

        This action:
        1. Updates the donation state to 'received'
        2. Sets the date_received to today
        3. Sets quantity_received = quantity_pledged for all lines without received qty
        4. Creates a stock.picking (incoming) for receiving items into warehouse

        Raises:
            UserError: If no incoming picking type found for the warehouse.
        """
        received_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_DONATION_STATES),
                ("code", "=", DONATION_STATE_RECEIVED),
            ],
            limit=1,
        )
        drims_type = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_DRIMS_TYPES),
                ("code", "=", DRIMS_TYPE_DONATION_RECEIPT),
            ],
            limit=1,
        )
        for rec in self:
            rec.state_id = received_state
            rec.date_received = fields.Date.context_today(self)
            # Mark all lines as received with pledged quantity
            for line in rec.line_ids:
                if line.quantity_received == 0:
                    line.quantity_received = line.quantity_pledged
            # Create stock picking for receipt
            rec._create_receipt_picking(drims_type)

    def _create_receipt_picking(self, drims_type):
        """Create a stock.picking for receiving donation items.

        Creates an incoming picking from supplier location to the donation's
        warehouse stock location. Stock moves are created for each donation line
        with quantity_received > 0.

        Args:
            drims_type: The spp.vocabulary.code record for 'donation_receipt' type.

        Returns:
            stock.picking: The created picking record, or None if no lines.

        Raises:
            UserError: If no incoming picking type found for the warehouse.
        """
        self.ensure_one()
        if not self.line_ids:
            return
        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        # Get picking type for receipts
        picking_type = self.env["stock.picking.type"].search(
            [
                ("warehouse_id", "=", self.warehouse_id.id),
                ("code", "=", "incoming"),
            ],
            limit=1,
        )
        if not picking_type:
            raise UserError(_("No incoming picking type found for warehouse %s") % self.warehouse_id.name)
        # Create picking
        picking_vals = {
            "picking_type_id": picking_type.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.warehouse_id.lot_stock_id.id,
            "drims_donation_id": self.id,
            "drims_type_id": drims_type.id if drims_type else False,
            "incident_id": self.incident_id.id,
            "origin": self.reference,
            "scheduled_date": fields.Datetime.now(),
        }
        picking = Picking.create(picking_vals)
        # Create moves for each line
        for line in self.line_ids:
            if line.quantity_received <= 0:
                continue
            move_vals = {
                "product_id": line.product_id.id,
                "product_uom_qty": line.quantity_received,
                "product_uom": line.uom_id.id,
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
                "drims_donation_line_id": line.id,
            }
            Move.create(move_vals)
        # Confirm the picking
        picking.action_confirm()
        return picking

    def action_inspect(self):
        """Mark donation as inspected after quality check.

        Transitions the donation from 'received' to 'inspected' state.
        Quality inspection should verify items match pledged quantities
        and meet quality standards.

        Raises:
            UserError: If donation is not in 'received' state.
        """
        inspected_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_DONATION_STATES),
                ("code", "=", DONATION_STATE_INSPECTED),
            ],
            limit=1,
        )
        for rec in self:
            if rec.state != DONATION_STATE_RECEIVED:
                raise UserError(_("Only received donations can be inspected."))
            rec.state_id = inspected_state

    def action_open_inspection_wizard(self):
        """Open the inspection wizard with pre-created records.

        This method creates the wizard and all line records BEFORE opening
        the wizard form. This is the standard Odoo pattern for wizards with
        interactive One2many fields - it ensures all records have database IDs
        so that buttons on lines work properly.

        All items default to 'New/Accept' status. Users can click 'Edit' on
        any row to modify condition/disposition for exceptions.

        Returns:
            dict: Action to open the wizard form.

        Raises:
            UserError: If donation is not in 'received' state.
        """
        self.ensure_one()

        if self.state != DONATION_STATE_RECEIVED:
            raise UserError(_("Only received donations can be inspected."))

        # Get default condition (new) and disposition (accept)
        condition_new = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_ITEM_CONDITIONS),
                ("code", "=", "new"),
            ],
            limit=1,
        )
        disposition_accept = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_ITEM_DISPOSITIONS),
                ("code", "=", "accept"),
            ],
            limit=1,
        )

        # Create the wizard record first
        wizard = self.env["spp.drims.inspection.wizard"].create(
            {
                "donation_id": self.id,
            }
        )

        # Create all line records with default values (New/Accept)
        line_vals = []
        for donation_line in self.line_ids:
            line_vals.append(
                {
                    "wizard_id": wizard.id,
                    "donation_line_id": donation_line.id,
                    "product_id": donation_line.product_id.id,
                    "uom_id": donation_line.uom_id.id,
                    "quantity_expected": donation_line.quantity_received,
                    "quantity": donation_line.quantity_received,
                    "condition_id": condition_new.id if condition_new else False,
                    "disposition_id": disposition_accept.id if disposition_accept else False,
                    "is_inspected": True,  # Default to inspected (New/Accept)
                }
            )

        if line_vals:
            self.env["spp.drims.inspection.wizard.line"].create(line_vals)

        # Return action to open the saved wizard
        return {
            "type": "ir.actions.act_window",
            "name": _("Inspect Donation"),
            "res_model": "spp.drims.inspection.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_stock(self):
        """Mark donation as stocked after items are put away.

        This action:
        1. Transitions the donation from 'inspected' to 'stocked' state
        2. Validates all pending stock pickings (assigns and confirms moves)
        3. Items become available in warehouse inventory

        Raises:
            UserError: If donation is not in 'inspected' state.
        """
        stocked_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_DONATION_STATES),
                ("code", "=", DONATION_STATE_STOCKED),
            ],
            limit=1,
        )
        for rec in self:
            if rec.state != DONATION_STATE_INSPECTED:
                raise UserError(_("Only inspected donations can be marked as stocked."))
            rec.state_id = stocked_state
            # Validate the picking to complete the receipt
            for picking in rec.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")):
                picking.action_assign()
                for move in picking.move_ids:
                    move.quantity = move.product_uom_qty
                picking.button_validate()

    def _change_state_and_cancel_pickings(self, new_state_code):
        """Helper to transition state and cancel pending pickings.

        Args:
            new_state_code: The vocabulary code for the new state

        Returns:
            The vocabulary code record for the new state
        """
        new_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_DONATION_STATES),
                ("code", "=", new_state_code),
            ],
            limit=1,
        )
        for rec in self:
            rec.state_id = new_state
            # Cancel any pending pickings
            rec.picking_ids.filtered(lambda p: p.state not in ("done", "cancel")).action_cancel()
        return new_state

    def action_reject(self):
        """Reject donation after inspection.

        Transitions the donation from 'inspected' to 'rejected' state.
        Rejected donations will not be stocked into inventory.

        Raises:
            UserError: If donation is not in 'inspected' state.
        """
        for rec in self:
            if rec.state != DONATION_STATE_INSPECTED:
                raise UserError(_("Only inspected donations can be rejected."))
        self._change_state_and_cancel_pickings(DONATION_STATE_REJECTED)

    def action_cancel(self):
        """Cancel the donation before stocking (GAP-DON-002).

        Transitions the donation to 'cancelled' state. Can only be cancelled
        from announced, received, or inspected states.

        Raises:
            UserError: If donation is already stocked or rejected.
        """
        for rec in self:
            if rec.state in (DONATION_STATE_STOCKED, DONATION_STATE_REJECTED):
                raise UserError(_("Cannot cancel a donation that is already stocked or rejected."))
        self._change_state_and_cancel_pickings(DONATION_STATE_CANCELLED)

    def action_view_pickings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Stock Transfers"),
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("drims_donation_id", "=", self.id)],
        }

    def _invalidate_incident_kpi_cache(self, records):
        """Invalidate KPI cache for incidents related to these donation records.

        This method is called after creating or updating donations to ensure
        that cached KPI values (like drims_donation_value) are refreshed to
        reflect the latest donation data.

        Args:
            records: Recordset of spp.drims.donation records to process.
        """
        incident_ids = list(set(rec.incident_id.id for rec in records if rec.incident_id))
        if incident_ids:
            DataValue = self.env["spp.data.value"]
            # Delete stale cache entries for donation KPI
            DataValue.search(
                [
                    ("variable_name", "=", "drims_donation_value"),
                    ("subject_model", "=", "spp.hazard.incident"),
                    ("subject_id", "in", incident_ids),
                ]
            ).unlink()
