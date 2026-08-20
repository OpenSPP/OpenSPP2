# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DRIMS Donation Receive Wizard (OP#1163).

"Mark Received" used to fail with a plain error when the received quantities
had not been entered yet. This wizard (mirroring the Inspect Items flow) opens
a single screen listing the donation's items with an editable Received column
pre-filled from the pledged quantity, then writes the entered quantities back
and marks the donation received.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class DrimsReceiveWizard(models.TransientModel):
    _name = "spp.drims.receive.wizard"
    _description = "DRIMS Donation Receive Wizard"

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
        "spp.drims.receive.wizard.line",
        "wizard_id",
        string="Received Items",
    )

    def action_confirm_received(self):
        """Write the entered received quantities back to the donation lines,
        then mark the donation received."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No items to receive."))
        for wl in self.line_ids:
            wl.donation_line_id.quantity_received = wl.quantity_received
        # action_mark_received validates that at least one item has a received
        # quantity > 0, sets the state and creates the receipt picking.
        self.donation_id.action_mark_received()
        return {"type": "ir.actions.act_window_close"}


class DrimsReceiveWizardLine(models.TransientModel):
    _name = "spp.drims.receive.wizard.line"
    _description = "DRIMS Donation Receive Wizard Line"
    _order = "id"

    wizard_id = fields.Many2one(
        "spp.drims.receive.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    donation_line_id = fields.Many2one(
        "spp.drims.donation.line",
        string="Donation Line",
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="Unit", readonly=True)
    quantity_pledged = fields.Float(string="Pledged", readonly=True)
    quantity_received = fields.Float(string="Received")
