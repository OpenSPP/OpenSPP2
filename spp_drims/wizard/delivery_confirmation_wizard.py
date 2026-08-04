# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DRIMS Delivery Confirmation Wizard (OP#1088).

Collects proof of delivery in one popup off the dispatch's Confirm Delivery
button, instead of expecting the officer to have typed the receiver's details
into the form beforehand and then press a button that refuses if they had not.

It also records what was actually delivered per line. Nothing in the module
wrote ``spp.drims.request.line.quantity_delivered`` before this, so a request's
``total_delivered`` and ``fulfillment_pct`` sat at 0 however much had arrived,
and ``spp.drims.alert`` kept reporting the full requested quantity as still
needed. Confirming delivery is the point at which that number is known.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class DeliveryConfirmationWizard(models.TransientModel):
    _name = "spp.drims.delivery.confirmation.wizard"
    _description = "Confirm DRIMS Delivery"

    picking_id = fields.Many2one(
        "stock.picking",
        string="Dispatch",
        required=True,
        readonly=True,
        domain="[('drims_type', '=', 'request_dispatch')]",
    )
    request_id = fields.Many2one(
        related="picking_id.drims_request_id",
        string="Request",
    )
    date_departed = fields.Datetime(
        related="picking_id.date_departed",
        string="Departed At",
    )
    date_arrived = fields.Datetime(
        string="Arrived At",
        required=True,
        default=fields.Datetime.now,
        help="When the consignment reached the destination",
    )

    # Receiver
    pod_received_by = fields.Char(
        string="Received By",
        required=True,
        help="Name of the person who took receipt of the consignment",
    )
    pod_receiver_title = fields.Char(string="Receiver Title")
    pod_receiver_id_number = fields.Char(string="Receiver ID Number")
    pod_status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Delivery Status",
        required=True,
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:pod-statuses')]",
        help="Complete, partial, damaged or not received",
    )

    # Evidence
    pod_signature = fields.Binary(string="Receiver Signature")
    pod_photo_ids = fields.Many2many("ir.attachment", string="Delivery Photos")
    pod_gps_latitude = fields.Float(string="GPS Latitude", digits=(10, 6))
    pod_gps_longitude = fields.Float(string="GPS Longitude", digits=(10, 6))

    # Narrative
    pod_notes = fields.Text(string="Delivery Notes")
    discrepancy_notes = fields.Text(
        string="Discrepancy Notes",
        help="Anything short, damaged or otherwise not as dispatched",
    )

    line_ids = fields.One2many(
        "spp.drims.delivery.confirmation.wizard.line",
        "wizard_id",
        string="Delivered Items",
    )

    @api.constrains("pod_gps_latitude", "pod_gps_longitude")
    def _check_gps_coordinates(self):
        """Reject coordinates outside the valid range.

        ``stock.picking._compute_pod_gps_point`` silently drops out-of-range
        values with a log warning, which would lose the delivery location
        without telling the officer.
        """
        for wizard in self:
            if wizard.pod_gps_latitude and not -90 <= wizard.pod_gps_latitude <= 90:
                raise ValidationError(_("GPS latitude must be between -90 and 90."))
            if wizard.pod_gps_longitude and not -180 <= wizard.pod_gps_longitude <= 180:
                raise ValidationError(_("GPS longitude must be between -180 and 180."))

    @api.model
    def _prepare_line_commands(self, picking):
        """Build the delivered-items rows from what the dispatch actually moved."""
        commands = []
        for move in picking.move_ids.filtered(lambda m: m.state == "done"):
            commands.append(
                (
                    0,
                    0,
                    {
                        "move_id": move.id,
                        "request_line_id": move.drims_request_line_id.id,
                        "product_id": move.product_id.id,
                        "uom_id": move.product_uom.id,
                        "quantity_dispatched": move.quantity,
                        # Default to "all of it arrived" — the common case, and the
                        # officer only has to touch the lines that fell short.
                        "quantity_delivered": move.quantity,
                    },
                )
            )
        return commands

    @api.model
    def default_get(self, fields_list):
        """Pre-populate the lines so the popup opens with quantities ready to edit."""
        res = super().default_get(fields_list)
        picking_id = res.get("picking_id") or self.env.context.get("default_picking_id")
        if not picking_id or "line_ids" not in fields_list:
            return res
        res["line_ids"] = self._prepare_line_commands(self.env["stock.picking"].browse(picking_id))
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """Fill the lines for any wizard created without them.

        ``default_get`` only runs for fields *absent* from the values, so a caller
        that passes ``picking_id`` in the values rather than in the context — the
        obvious way to do it from a script or over RPC — would otherwise get a
        wizard with no lines, silently record no delivered quantities, and leave
        fulfillment reading 0. Populate here as well so every path behaves.
        """
        for vals in vals_list:
            if vals.get("picking_id") and not vals.get("line_ids"):
                picking = self.env["stock.picking"].browse(vals["picking_id"])
                vals["line_ids"] = self._prepare_line_commands(picking)
        return super().create(vals_list)

    def action_confirm(self):
        """Write the proof of delivery onto the dispatch and its request."""
        self.ensure_one()
        picking = self.picking_id

        if not picking.date_departed:
            raise UserError(
                _("Dispatch %s has not departed yet. Confirm departure before confirming delivery.") % picking.name
            )
        if picking.is_pod_confirmed:
            raise UserError(_("Delivery for dispatch %s is already confirmed.") % picking.name)
        if self.date_arrived < picking.date_departed:
            raise UserError(_("The arrival time cannot be before the departure time."))

        picking.write(
            {
                "date_arrived": self.date_arrived,
                "pod_received_by": self.pod_received_by,
                "pod_receiver_title": self.pod_receiver_title,
                "pod_receiver_id_number": self.pod_receiver_id_number,
                "pod_status_id": self.pod_status_id.id,
                "pod_signature": self.pod_signature,
                "pod_photo_ids": [(6, 0, self.pod_photo_ids.ids)],
                "pod_gps_latitude": self.pod_gps_latitude,
                "pod_gps_longitude": self.pod_gps_longitude,
                "pod_notes": self.pod_notes,
                "discrepancy_notes": self.discrepancy_notes,
                "is_pod_confirmed": True,
            }
        )

        self._record_delivered_quantities()

        _logger.info(
            "DRIMS delivery confirmed for %s by %s (%s)",
            picking.name,
            self.pod_received_by,
            self.pod_status_id.code,
        )
        return {"type": "ir.actions.act_window_close"}

    def _record_delivered_quantities(self):
        """Add the delivered quantities to their request lines.

        Accumulated rather than assigned: a request can be filled by several
        dispatches, so each confirmation contributes its share.
        """
        self.ensure_one()
        for line in self.line_ids.filtered(lambda line: line.request_line_id):
            request_line = line.request_line_id
            request_line.quantity_delivered = request_line.quantity_delivered + line.quantity_delivered


class DeliveryConfirmationWizardLine(models.TransientModel):
    _name = "spp.drims.delivery.confirmation.wizard.line"
    _description = "Confirm DRIMS Delivery Line"

    wizard_id = fields.Many2one(
        "spp.drims.delivery.confirmation.wizard",
        required=True,
        ondelete="cascade",
    )
    move_id = fields.Many2one("stock.move", string="Stock Move", readonly=True)
    request_line_id = fields.Many2one(
        "spp.drims.request.line",
        string="Request Line",
        readonly=True,
    )
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    uom_id = fields.Many2one("uom.uom", string="Unit", readonly=True)
    quantity_dispatched = fields.Float(string="Dispatched", readonly=True)
    quantity_delivered = fields.Float(string="Delivered")

    @api.constrains("quantity_delivered")
    def _check_quantity_delivered(self):
        """Delivered has to be between nothing and what was dispatched."""
        for line in self:
            if line.quantity_delivered < 0:
                raise ValidationError(_("Delivered quantity cannot be negative."))
            if line.uom_id.compare(line.quantity_delivered, line.quantity_dispatched) > 0:
                raise ValidationError(
                    _(
                        "Cannot deliver more %(product)s than was dispatched "
                        "(%(delivered)s delivered vs %(dispatched)s dispatched).",
                        product=line.product_id.display_name,
                        delivered=line.quantity_delivered,
                        dispatched=line.quantity_dispatched,
                    )
                )
