# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Donation Inspection Wizard (DON-002)

Inline-editable single-screen flow:
- Operator sets Condition and Action directly on each row.
- "+ Add split" creates a child row under the parent product for mixed conditions.
- Parent qty mirrors the running sum of child rows; the parent itself carries no
  condition / action — those live on the children.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.constants import (
    DONATION_STATE_INSPECTED,
    VOCAB_DONATION_STATES,
    VOCAB_ITEM_CONDITIONS,
    VOCAB_ITEM_DISPOSITIONS,
)

_logger = logging.getLogger(__name__)


class InspectionWizard(models.TransientModel):
    """Main inspection wizard - inline editing on every row."""

    _name = "spp.drims.inspection.wizard"
    _description = "Donation Inspection Wizard"

    donation_id = fields.Many2one(
        "spp.drims.donation",
        string="Donation",
        required=True,
        readonly=True,
    )
    donation_reference = fields.Char(
        related="donation_id.reference",
        string="Reference",
    )
    line_ids = fields.One2many(
        "spp.drims.inspection.wizard.line",
        "wizard_id",
        string="Inspection Lines",
    )
    notes = fields.Text(
        string="Inspection Notes",
        help="General notes about the inspection",
    )
    # The QtySplitProgressField widget pushes both of these from the
    # editable list whenever any row's qty / condition / disposition
    # changes. They drive the Confirm-button gate in the view.
    # See ``_syncWizardCanConfirm`` in the JS widget.
    can_confirm = fields.Boolean(
        string="Can Confirm",
        default=True,
    )
    confirm_message = fields.Text(
        string="Confirm Blocker",
        help="Human-readable reason(s) why Confirm Inspection is currently disabled.",
    )

    def action_confirm_inspection(self):
        """Confirm inspection and create/update donation lines."""
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("No items to inspect."))

        # Parent rows carry no condition/action; only validate the rows
        # the operator actually filled in.
        lines_to_check = self.line_ids.filtered(lambda line: not line.has_splits)
        uninspected = lines_to_check.filtered(lambda line: not line.is_inspected)
        if uninspected:
            raise UserError(
                _("Please inspect all items first. Uninspected: %s")
                % ", ".join(uninspected.mapped("product_id.display_name"))
            )

        # Group by the original donation line. Two separate donation lines for
        # the same product are independent (each has its own donation_line_id),
        # so they must not be lumped together as if they were splits of each
        # other. Splits of a single donation line share the same
        # ``donation_line_id`` via ``action_add_split``.
        # Parent rows are skipped here — their qty mirrors their children's
        # running total and including them would double-count.
        lines_by_donation = {}
        for line in self.line_ids:
            if line.has_splits:
                continue
            key = line.donation_line_id.id
            if key not in lines_by_donation:
                lines_by_donation[key] = {
                    "name": line.product_id.display_name,
                    "expected": line.quantity_expected,
                    "total": 0.0,
                    "lines": [],
                }
            lines_by_donation[key]["total"] += line.quantity
            lines_by_donation[key]["lines"].append(line)

        # OP#964: only enforce equality when the user has split a donation
        # line into multiple wizard lines. A single line is treated as the
        # user reporting the final received quantity, and
        # ``quantity_received`` on the donation line will be overwritten to
        # match below.
        for data in lines_by_donation.values():
            if len(data["lines"]) <= 1:
                continue
            diff = abs(data["expected"] - data["total"])
            if diff > 0.001:
                raise UserError(
                    _(
                        "Product %(product)s: split quantities total %(total)s but "
                        "received quantity is %(expected)s. Splits must sum to the "
                        "received quantity. Adjust splits or change the Received "
                        "quantity on the donation line first."
                    )
                    % {
                        "product": data["name"],
                        "total": data["total"],
                        "expected": data["expected"],
                    }
                )

        _logger.info(
            "Confirming inspection for donation %s with %d lines",
            self.donation_id.reference,
            len(self.line_ids),
        )

        DonationLine = self.env["spp.drims.donation.line"]
        for data in lines_by_donation.values():
            lines = data["lines"]

            first_line = lines[0]
            original_donation_line = first_line.donation_line_id
            original_donation_line.write(
                {
                    "quantity_received": first_line.quantity,
                    "condition_id": first_line.condition_id.id,
                    "disposition_id": first_line.disposition_id.id,
                    "notes": first_line.notes or original_donation_line.notes,
                }
            )

            for line in lines[1:]:
                if line.quantity <= 0:
                    continue
                DonationLine.create(
                    {
                        "donation_id": self.donation_id.id,
                        "product_id": line.product_id.id,
                        "quantity_pledged": line.quantity,
                        "quantity_received": line.quantity,
                        "uom_id": line.uom_id.id,
                        "unit_value": original_donation_line.unit_value,
                        "condition_id": line.condition_id.id,
                        "disposition_id": line.disposition_id.id,
                        "lot_number": original_donation_line.lot_number,
                        "expiry_date": original_donation_line.expiry_date,
                        "notes": line.notes or _("Split from inspection"),
                    }
                )

        inspected_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", VOCAB_DONATION_STATES),
                ("code", "=", DONATION_STATE_INSPECTED),
            ],
            limit=1,
        )
        self.donation_id.write(
            {
                "state_id": inspected_state.id,
                "notes": (self.donation_id.notes or "")
                + (f"\n\n--- Inspection Notes ({fields.Date.today()}) ---\n{self.notes}" if self.notes else ""),
            }
        )

        return {"type": "ir.actions.act_window_close"}


class InspectionWizardLine(models.TransientModel):
    """Line in the inspection wizard."""

    _name = "spp.drims.inspection.wizard.line"
    _description = "Inspection Wizard Line"
    # Sort so each donation line's rows stay grouped together, with the
    # parent row first (parent_line_id IS NULL) and its split children
    # immediately below it (ordered by creation id).
    _order = "donation_line_id, parent_line_id NULLS FIRST, id"

    wizard_id = fields.Many2one(
        "spp.drims.inspection.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    donation_line_id = fields.Many2one(
        "spp.drims.donation.line",
        string="Donation Line",
        required=True,
    )
    parent_line_id = fields.Many2one(
        "spp.drims.inspection.wizard.line",
        string="Parent Line",
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        required=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
    )
    quantity_expected = fields.Float(
        string="Expected",
        help="Total quantity expected for this product",
    )
    quantity = fields.Float(
        string="Quantity",
        help="Quantity in this condition",
    )
    condition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Condition",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_ITEM_CONDITIONS}')]",
    )
    disposition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Disposition",
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_ITEM_DISPOSITIONS}')]",
    )
    notes = fields.Char(
        string="Notes",
        help="Notes about this portion",
    )
    is_inspected = fields.Boolean(
        string="Inspected",
        compute="_compute_is_inspected",
        help="True once both Condition and Action are filled.",
    )
    is_split = fields.Boolean(
        string="Is Split Line",
        compute="_compute_is_split",
        store=True,
    )
    # ``has_splits`` is a plain Boolean (no compute) because Odoo 19's
    # editable-One2many reactivity does not reliably propagate cross-record
    # depends like ``wizard_id.line_ids.parent_line_id``. action_add_split /
    # action_remove_split write to this field explicitly, which keeps the
    # readonly + visibility logic in the view reactive without round-tripping
    # through a slow compute.
    has_splits = fields.Boolean(
        string="Has Split Lines",
        default=False,
    )
    # Set by both ``action_add_split`` and the OWL widget's useEffect after
    # the running split total catches up to (or exceeds) ``quantity_expected``.
    # Drives the "+ Add split" button visibility on the parent row.
    is_fully_split = fields.Boolean(
        string="Is Fully Split",
        default=False,
    )
    can_mark_all_units = fields.Boolean(
        string="Can Mark All Units",
        compute="_compute_can_mark_all_units",
    )

    @api.depends("parent_line_id")
    def _compute_is_split(self):
        for line in self:
            line.is_split = bool(line.parent_line_id)

    @api.depends("condition_id", "disposition_id")
    def _compute_can_mark_all_units(self):
        for line in self:
            line.can_mark_all_units = bool(line.condition_id and line.disposition_id)

    @api.depends("condition_id", "disposition_id")
    def _compute_is_inspected(self):
        """A row is inspected once both Condition and Action are filled."""
        for line in self:
            line.is_inspected = bool(line.condition_id and line.disposition_id)

    @api.onchange("quantity")
    def _onchange_quantity_update_parent(self):
        """Keep the parent row qty in sync with the running sum of its children.

        No clamping while drafting: the operator can freely adjust split
        quantities (e.g. rebalance 500/500 to 400/600 without having to lower
        one row first). An over- or under-split total is rejected at confirm
        time by ``action_confirm_inspection`` (mirrored client-side by the
        ``can_confirm`` guard), so eager clamping here only gets in the way.
        """
        if not self.parent_line_id:
            return
        siblings = self.wizard_id.line_ids.filtered(
            lambda line: line.parent_line_id == self.parent_line_id and line != self
        )
        others_sum = sum(siblings.mapped("quantity"))
        total = others_sum + (self.quantity or 0.0)
        self.parent_line_id.quantity = total

    def action_all_units(self):
        """No-op handler for the visual "All units" badge in the list view.

        The button is a visual indicator that Condition and Action are set —
        clicking it just refreshes the wizard so any pending onchange values
        are persisted. ``is_inspected`` is already flipped automatically via
        ``_onchange_mark_inspected``.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.drims.inspection.wizard",
            "res_id": self.wizard_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_add_split(self):
        """Create a new split child line under this row and reopen the wizard."""
        self.ensure_one()

        # If the operator clicks "+ Add split" on a line that is itself a child,
        # treat the parent as the root for the new split.
        root_line = self.parent_line_id or self

        # Sum only the existing children — never the parent. On the very first
        # split the parent's qty still mirrors the full expected qty, so adding
        # it would double-count and leave 0 remaining.
        child_lines = self.wizard_id.line_ids.filtered(lambda line: line.parent_line_id == root_line)
        total_in_splits = sum(child_lines.mapped("quantity"))
        remaining = root_line.quantity_expected - total_in_splits

        if remaining <= 0:
            raise UserError(_("No remaining quantity to split. Reduce one of the existing split quantities first."))

        # First split: reset the parent qty to 0 (it will be kept in sync as
        # the running sum of children), mark the parent as split, and clear
        # any Condition / Action the operator may have set before deciding
        # to split — the parent row carries no decision; the children do.
        if not child_lines:
            root_line.quantity = 0
            root_line.condition_id = False
            root_line.disposition_id = False
            root_line.has_splits = True

        # Create the new split with qty=0 so the operator has to enter the
        # split amount explicitly. The "+ Add split" button is then hidden
        # in the UI while any child still has qty=0, forcing the operator
        # to fill the new row before opening another. This avoids the
        # "I added a split but forgot to set its quantity" footgun.
        self.env["spp.drims.inspection.wizard.line"].create(
            {
                "wizard_id": self.wizard_id.id,
                "donation_line_id": root_line.donation_line_id.id,
                "product_id": root_line.product_id.id,
                "uom_id": root_line.uom_id.id,
                "quantity_expected": root_line.quantity_expected,
                "quantity": 0,
                "parent_line_id": root_line.id,
            }
        )

        # Running total is unchanged because the new child contributes 0;
        # the parent still mirrors the sum of existing children.
        root_line.quantity = total_in_splits
        # The new child has qty 0, so by definition the parent is not yet
        # fully split.
        root_line.is_fully_split = False

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.drims.inspection.wizard",
            "res_id": self.wizard_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_remove_split(self):
        """Remove a split child line and refresh the wizard."""
        self.ensure_one()
        if not self.is_split:
            raise UserError(_("Only split lines can be removed this way."))
        wizard_id = self.wizard_id.id
        root_line = self.parent_line_id

        # Identify the children that will remain BEFORE unlinking. Reading the
        # One2many after unlink can hit the still-cached unlinked record and
        # raise MissingError when the lambda touches its fields.
        remaining_children = root_line.wizard_id.line_ids.filtered(
            lambda line: line.parent_line_id == root_line and line != self
        )

        self.unlink()

        if not remaining_children:
            # Reset parent back to the full expected quantity and clear the
            # split flag so the row reverts to a normal (editable) row.
            root_line.quantity = root_line.quantity_expected
            root_line.has_splits = False
        else:
            root_line.quantity = sum(remaining_children.mapped("quantity"))

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.drims.inspection.wizard",
            "res_id": wizard_id,
            "view_mode": "form",
            "target": "new",
        }
