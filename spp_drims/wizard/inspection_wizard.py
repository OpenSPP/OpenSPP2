# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Donation Inspection Wizard (DON-002)

Batch Accept with Exceptions design:
- Main wizard shows readonly list of items
- "Accept All as New" button for 90% of cases (one-click)
- "Edit" button per row opens popup to modify individual items
- Supports splitting items with mixed conditions
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
    """Main inspection wizard - shows items and allows batch accept or per-item edit."""

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
    is_valid = fields.Boolean(
        string="Is Valid",
        compute="_compute_is_valid",
    )

    @api.depends("line_ids.is_inspected", "line_ids.quantity", "line_ids.quantity_expected")
    def _compute_is_valid(self):
        """Check if all items are inspected and quantities match."""
        for wizard in self:
            if not wizard.line_ids:
                wizard.is_valid = False
                continue

            # Check all lines are inspected
            all_inspected = all(line.is_inspected for line in wizard.line_ids)
            if not all_inspected:
                wizard.is_valid = False
                continue

            # Check quantities match per product
            products = {}
            for line in wizard.line_ids:
                product_id = line.product_id.id
                if product_id not in products:
                    products[product_id] = {
                        "expected": line.quantity_expected,
                        "total": 0.0,
                    }
                products[product_id]["total"] += line.quantity

            quantities_match = all(abs(data["expected"] - data["total"]) < 0.001 for data in products.values())
            wizard.is_valid = quantities_match

    def action_accept_all(self):
        """Accept all items as New/Accept - one click for simple cases."""
        self.ensure_one()

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

        if not condition_new or not disposition_accept:
            raise UserError(_("Vocabulary codes for 'new' condition or 'accept' disposition not found."))

        # Mark all lines as inspected with default values
        for line in self.line_ids:
            line.write(
                {
                    "condition_id": condition_new.id,
                    "disposition_id": disposition_accept.id,
                    "is_inspected": True,
                }
            )

        # Return to same wizard (refreshed)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_confirm_inspection(self):
        """Confirm inspection and create/update donation lines."""
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("No items to inspect."))

        # Validate all items are inspected
        uninspected = self.line_ids.filtered(lambda line: not line.is_inspected)
        if uninspected:
            raise UserError(
                _("Please inspect all items first. Uninspected: %s")
                % ", ".join(uninspected.mapped("product_id.display_name"))
            )

        # Validate quantities per product
        products = {}
        for line in self.line_ids:
            product_id = line.product_id.id
            if product_id not in products:
                products[product_id] = {
                    "name": line.product_id.display_name,
                    "expected": line.quantity_expected,
                    "total": 0.0,
                    "lines": [],
                }
            products[product_id]["total"] += line.quantity
            products[product_id]["lines"].append(line)

        for _product_id, data in products.items():
            diff = abs(data["expected"] - data["total"])
            if diff > 0.001:
                raise UserError(
                    _(
                        "Product %(product)s: Total inspected (%(total)s) must equal "
                        "expected (%(expected)s). Difference: %(diff)s"
                    )
                    % {
                        "product": data["name"],
                        "total": data["total"],
                        "expected": data["expected"],
                        "diff": diff,
                    }
                )

        _logger.info(
            "Confirming inspection for donation %s with %d lines",
            self.donation_id.reference,
            len(self.line_ids),
        )

        # Process each product group
        DonationLine = self.env["spp.drims.donation.line"]
        for _product_id, data in products.items():
            lines = data["lines"]

            # First line updates the original donation line
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

            # Additional lines create new donation lines (splits)
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

        # Transition donation to inspected state
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
    """Line in the inspection wizard - one per item/condition combination."""

    _name = "spp.drims.inspection.wizard.line"
    _description = "Inspection Wizard Line"

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
        default=False,
        help="Whether this item has been inspected",
    )
    condition_display = fields.Char(
        string="Status",
        compute="_compute_condition_display",
    )

    @api.depends("is_inspected", "condition_id", "disposition_id")
    def _compute_condition_display(self):
        """Compute display string for condition/disposition."""
        for line in self:
            if not line.is_inspected:
                line.condition_display = _("Not inspected")
            elif line.condition_id and line.disposition_id:
                line.condition_display = f"{line.condition_id.display} / {line.disposition_id.display}"
            else:
                line.condition_display = _("Incomplete")

    def action_edit_item(self):
        """Open popup to edit this item."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Inspect Item: %s") % self.product_id.display_name,
            "res_model": "spp.drims.inspection.item.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_inspection_line_id": self.id,
                "default_wizard_id": self.wizard_id.id,
                "default_product_id": self.product_id.id,
                "default_uom_id": self.uom_id.id,
                "default_quantity_expected": self.quantity_expected,
                "default_quantity": self.quantity,
                "default_condition_id": self.condition_id.id if self.condition_id else False,
                "default_disposition_id": self.disposition_id.id if self.disposition_id else False,
                "default_notes": self.notes or "",
            },
        }


class InspectionItemWizard(models.TransientModel):
    """Popup wizard to edit a single inspection item."""

    _name = "spp.drims.inspection.item.wizard"
    _description = "Inspect Item Wizard"

    inspection_line_id = fields.Many2one(
        "spp.drims.inspection.wizard.line",
        string="Inspection Line",
        required=True,
    )
    wizard_id = fields.Many2one(
        "spp.drims.inspection.wizard",
        string="Main Wizard",
        required=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Product",
        readonly=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit",
        readonly=True,
    )
    quantity_expected = fields.Float(
        string="Expected Quantity",
        readonly=True,
    )
    quantity = fields.Float(
        string="Quantity",
        required=True,
        help="Quantity in this condition. Reduce if splitting.",
    )
    condition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Condition",
        required=True,
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_ITEM_CONDITIONS}')]",
    )
    disposition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Disposition",
        required=True,
        domain=f"[('vocabulary_id.namespace_uri', '=', '{VOCAB_ITEM_DISPOSITIONS}')]",
    )
    notes = fields.Char(
        string="Notes",
        help="Notes about this item (e.g., 'water damaged', 'expired batch')",
    )
    remaining_qty = fields.Float(
        string="Remaining to Allocate",
        compute="_compute_remaining_qty",
        help="Quantity not yet allocated (for splitting)",
    )
    show_split_warning = fields.Boolean(
        compute="_compute_remaining_qty",
    )

    @api.depends("quantity", "quantity_expected")
    def _compute_remaining_qty(self):
        """Compute remaining quantity for this product."""
        InspectionLine = self.env["spp.drims.inspection.wizard.line"]
        for item in self:
            # Sum all lines for this product in the main wizard
            other_lines = InspectionLine.browse()
            for line in item.wizard_id.line_ids:
                if line.product_id == item.product_id and line.id != item.inspection_line_id.id:
                    other_lines |= line
            other_total = sum(other_lines.mapped("quantity"))
            item.remaining_qty = item.quantity_expected - item.quantity - other_total
            item.show_split_warning = item.remaining_qty > 0.001

    def action_save(self):
        """Save changes and return to main wizard."""
        self.ensure_one()

        if self.quantity < 0:
            raise UserError(_("Quantity cannot be negative."))

        # Update the inspection line
        self.inspection_line_id.write(
            {
                "quantity": self.quantity,
                "condition_id": self.condition_id.id,
                "disposition_id": self.disposition_id.id,
                "notes": self.notes,
                "is_inspected": True,
            }
        )

        # Return to main wizard
        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.drims.inspection.wizard",
            "res_id": self.wizard_id.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_save_and_split(self):
        """Save changes and create a new line for remaining quantity."""
        self.ensure_one()

        if self.quantity < 0:
            raise UserError(_("Quantity cannot be negative."))

        if self.remaining_qty <= 0:
            raise UserError(_("No remaining quantity to split. Adjust the quantity first."))

        # Update current line
        self.inspection_line_id.write(
            {
                "quantity": self.quantity,
                "condition_id": self.condition_id.id,
                "disposition_id": self.disposition_id.id,
                "notes": self.notes,
                "is_inspected": True,
            }
        )

        # Create new line for remaining quantity
        new_line = self.env["spp.drims.inspection.wizard.line"].create(
            {
                "wizard_id": self.wizard_id.id,
                "donation_line_id": self.inspection_line_id.donation_line_id.id,
                "product_id": self.product_id.id,
                "uom_id": self.uom_id.id,
                "quantity_expected": self.quantity_expected,
                "quantity": self.remaining_qty,
                "is_inspected": False,  # New split needs to be inspected
            }
        )

        # Open edit popup for the new split
        return new_line.action_edit_item()
