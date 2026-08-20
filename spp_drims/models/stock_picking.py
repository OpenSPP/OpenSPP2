# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import base64
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # DRIMS Type
    drims_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="DRIMS Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:drims-types')]",
        index=True,
    )
    drims_type = fields.Char(
        related="drims_type_id.code",
        store=True,
    )

    # Link to DRIMS records
    drims_donation_id = fields.Many2one(
        "spp.drims.donation",
        string="DRIMS Donation",
        index=True,
    )
    drims_request_id = fields.Many2one(
        "spp.drims.request",
        string="DRIMS Request",
        index=True,
    )
    drims_return_id = fields.Many2one(
        "spp.drims.return",
        string="DRIMS Return",
        index=True,
        copy=False,
    )
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        index=True,
    )

    # Beneficiary tracking
    beneficiary_area_id = fields.Many2one(
        "spp.area",
        string="Distribution Area",
        help="Geographic area where items were distributed",
    )
    beneficiary_count = fields.Integer(
        string="Estimated Beneficiaries Reached",
        copy=False,
        help="Estimated number of beneficiaries who received items (exact counts often unknown in emergencies)",
    )
    distribution_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Distribution Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:distribution-types')]",
        help="Individual, household, or group distribution",
    )

    # Return tracking
    return_reason_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Return Reason",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:return-reasons')]",
        help="Why items were returned to stock",
    )
    return_condition_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Return Condition",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:return-conditions')]",
        help="Condition of returned items",
    )

    # Waybill
    waybill_number = fields.Char(
        string="Waybill Number",
        copy=False,
        index=True,
    )

    # Transport
    # Every field below records what happened on one physical shipment, so none
    # of them may be carried onto a copy of the picking. Odoo builds a backorder
    # with ``picking.copy()`` (``stock.picking._create_backorder_picking``), so
    # without ``copy=False`` a backorder inherits the parent's departure
    # timestamp, driver, POD and beneficiary count — claiming a delivery for
    # goods still sitting in the warehouse, and double-counting the parent's
    # beneficiaries in ``spp.hazard.incident.drims_beneficiaries_served``
    # (OP#1087). The same applies to the Duplicate action.
    transport_mode_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Transport Mode",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:transport-modes')]",
        copy=False,
    )
    vehicle_registration = fields.Char(string="Vehicle Registration", copy=False)
    driver_name = fields.Char(string="Driver Name", copy=False)
    driver_phone = fields.Char(string="Driver Phone", copy=False)

    # Proof of Delivery (POD)
    pod_status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="POD Status",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:drims:pod-statuses')]",
        copy=False,
    )
    is_pod_confirmed = fields.Boolean(
        string="POD Confirmed",
        default=False,
        copy=False,
    )
    pod_received_by = fields.Char(string="Received By", copy=False)
    pod_receiver_title = fields.Char(string="Receiver Title", copy=False)
    pod_receiver_id_number = fields.Char(string="Receiver ID Number", copy=False)
    pod_signature = fields.Binary(string="Signature", copy=False)
    pod_photo_ids = fields.Many2many(
        "ir.attachment",
        string="Delivery Photos",
        copy=False,
    )
    pod_gps_latitude = fields.Float(string="GPS Latitude", digits=(10, 6), copy=False)
    pod_gps_longitude = fields.Float(string="GPS Longitude", digits=(10, 6), copy=False)
    pod_gps_point = fields.GeoPointField(
        string="POD GPS Point",
        compute="_compute_pod_gps_point",
        store=True,
        help="Computed geographic point from POD GPS coordinates for GIS mapping",
    )
    pod_notes = fields.Text(string="POD Notes", copy=False)

    # Dates
    date_departed = fields.Datetime(string="Departed At", copy=False)
    date_arrived = fields.Datetime(string="Arrived At", copy=False)

    # Discrepancy
    discrepancy_notes = fields.Text(string="Discrepancy Notes", copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("drims_type_id") and not vals.get("waybill_number"):
                vals["waybill_number"] = self.env["ir.sequence"].next_by_code("spp.drims.waybill")
        return super().create(vals_list)

    @api.depends("pod_gps_latitude", "pod_gps_longitude")
    def _compute_pod_gps_point(self):
        """Compute the GeoPointField from POD GPS coordinates."""
        for rec in self:
            if rec.pod_gps_latitude and rec.pod_gps_longitude:
                if -90 <= rec.pod_gps_latitude <= 90 and -180 <= rec.pod_gps_longitude <= 180:
                    rec.pod_gps_point = json.dumps(
                        {
                            "type": "Point",
                            "coordinates": [
                                rec.pod_gps_longitude,
                                rec.pod_gps_latitude,
                            ],
                        }
                    )
                else:
                    _logger.warning(
                        "Invalid GPS coordinates for picking %s: lat=%s, lon=%s",
                        rec.name,
                        rec.pod_gps_latitude,
                        rec.pod_gps_longitude,
                    )
                    rec.pod_gps_point = False
            else:
                rec.pod_gps_point = False

    def action_open_gis_map(self):
        """Open the unified DRIMS Operations Map."""
        return self.env.ref("spp_drims.action_drims_operations_map").read()[0]

    def _get_waybill_barcode_data_uri(self, width=300, height=50):
        """Return the waybill number as an embedded Code128 ``data:`` URI (OP#1151).

        The waybill template used to point an ``<img>`` at ``/report/barcode/``.
        That makes the barcode depend on wkhtmltopdf being able to fetch a URL
        from inside the rendering process, so it silently vanished whenever
        ``web.base.url`` was not reachable there — which is the normal state of a
        containerised deployment where Odoo listens on 8069 internally but
        ``web.base.url`` holds an external host and port. Embedding the image
        removes the network round trip, so the barcode renders the same in dev,
        CI and production.

        Requires reportlab's renderPM backend (``rlPyCairo``) to be installed;
        see ``docker/requirements.txt``. Returns ``False`` rather than raising if
        the barcode cannot be produced, since a missing barcode must not stop a
        waybill printing.

        Returns:
            str | bool: ``data:image/png;base64,...`` or ``False``.
        """
        self.ensure_one()
        if not self.waybill_number:
            return False
        try:
            png = self.env["ir.actions.report"].barcode(
                "Code128",
                self.waybill_number,
                width=width,
                height=height,
                humanreadable=0,
            )
        except Exception:  # noqa: BLE001 - never let a barcode break the document
            _logger.warning(
                "Could not render the Code128 barcode for waybill %s; printing without it. Is rlPyCairo installed?",
                self.waybill_number,
                exc_info=True,
            )
            return False
        return "data:image/png;base64," + base64.b64encode(png).decode()

    def action_confirm_departure(self):
        """Confirm dispatch departure."""
        for rec in self:
            rec.date_departed = fields.Datetime.now()

    def action_confirm_pod(self):
        """Confirm proof of delivery."""
        for rec in self:
            if not rec.pod_received_by:
                raise UserError(_("Please enter the receiver's name."))
            rec.is_pod_confirmed = True
            rec.date_arrived = fields.Datetime.now()

    def action_create_drims_return(self):
        """Open wizard to create a DRIMS return from a completed dispatch (GAP-RET-001)."""
        self.ensure_one()
        if self.drims_type != "request_dispatch":
            raise UserError(_("Returns can only be created from dispatch pickings."))
        if self.state != "done":
            raise UserError(_("Returns can only be created from completed dispatches."))
        if self.drims_return_id:
            raise UserError(_("A return already exists for this dispatch."))

        # Create wizard with pre-populated lines
        wizard = self.env["spp.drims.create.return.wizard"].create(
            {
                "picking_id": self.id,
                "warehouse_id": self.picking_type_id.warehouse_id.id,
            }
        )
        wizard._onchange_picking_id()

        return {
            "type": "ir.actions.act_window",
            "name": _("Create Return"),
            "res_model": "spp.drims.create.return.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_drims_return_direct(self):
        """Create a DRIMS return directly without wizard (for programmatic use)."""
        self.ensure_one()
        if self.drims_type != "request_dispatch":
            raise UserError(_("Returns can only be created from dispatch pickings."))
        if self.state != "done":
            raise UserError(_("Returns can only be created from completed dispatches."))
        if self.drims_return_id:
            raise UserError(_("A return already exists for this dispatch."))

        Return = self.env["spp.drims.return"]

        # Get source warehouse from picking type
        warehouse = self.picking_type_id.warehouse_id

        # Create return record
        return_vals = {
            "incident_id": self.incident_id.id,
            "original_picking_id": self.id,
            "warehouse_id": warehouse.id,
        }
        drims_return = Return.create(return_vals)

        # Create return lines from dispatch moves
        ReturnLine = self.env["spp.drims.return.line"]
        for move in self.move_ids.filtered(lambda m: m.state == "done"):
            ReturnLine.create(
                {
                    "return_id": drims_return.id,
                    "product_id": move.product_id.id,
                    "quantity_dispatched": move.quantity,
                    "quantity_returned": 0.0,
                }
            )

        # Link return to picking
        self.drims_return_id = drims_return.id

        # Open the return form
        return {
            "type": "ir.actions.act_window",
            "name": _("Return"),
            "res_model": "spp.drims.return",
            "view_mode": "form",
            "res_id": drims_return.id,
        }

    def action_view_drims_return(self):
        """View the linked DRIMS return."""
        self.ensure_one()
        if not self.drims_return_id:
            raise UserError(_("No return linked to this picking."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Return"),
            "res_model": "spp.drims.return",
            "view_mode": "form",
            "res_id": self.drims_return_id.id,
        }

    def _check_drims_dispatch_matches_request(self):
        """Refuse to dispatch anything the request did not approve (OP#1057).

        A dispatch is generated from an approved request, but the Operations tab
        stays editable in Ready state, so two things could still be smuggled past
        the approval workflow:

        1. **Extra products.** "Add a Product" attaches a move that no request
           line asked for. Note this is keyed on ``drims_request_line_id`` rather
           than Odoo's ``additional`` flag: ``additional`` is only set when a line
           is added through the form, so a move created over RPC or by an import
           has ``additional = False`` and would slip past a check based on it.

        2. **Inflated quantities.** Unlocking the picking makes Demand editable
           again, so an approved line can be raised above what was allocated.
           Allocation is itself capped at the requested quantity by
           ``_allocate_stock_fifo``, so comparing against ``quantity_allocated``
           transitively enforces the approved amount.

        Raises:
            UserError: naming the offending products, if either check fails.
        """
        for picking in self:
            if picking.drims_type != "request_dispatch" or not picking.drims_request_id:
                continue

            live_moves = picking.move_ids.filtered(lambda m: m.state != "cancel")
            live_move_ids = set(live_moves.ids)
            approved_line_ids = set(picking.drims_request_id.line_ids.ids)

            # 1. Every move has to trace back to a line of *this* request.
            unapproved_products = sorted(
                {m.product_id.display_name for m in live_moves if m.drims_request_line_id.id not in approved_line_ids}
            )
            if unapproved_products:
                raise UserError(
                    _(
                        "Dispatch %(picking)s contains items that are not part of "
                        "request %(request)s: %(products)s.\n\n"
                        "A dispatch may only ship what the request had approved and "
                        "allocated. Remove these lines, or raise a new request for "
                        "them and have it approved.",
                        picking=picking.name,
                        request=picking.drims_request_id.reference,
                        products=", ".join(unapproved_products),
                    )
                )

            # 2. Nothing may ship beyond what the request line had allocated,
            #    counting what earlier dispatches already shipped for that line.
            over_dispatched = []
            for line in live_moves.drims_request_line_id:
                line_moves = self.env["stock.move"].search(
                    [
                        ("drims_request_line_id", "=", line.id),
                        ("state", "!=", "cancel"),
                    ]
                )
                already_shipped = sum(m.quantity for m in line_moves if m.state == "done")
                about_to_ship = sum(m.quantity for m in line_moves if m.id in live_move_ids)
                if line.uom_id.compare(already_shipped + about_to_ship, line.quantity_allocated) > 0:
                    over_dispatched.append(
                        _(
                            "%(product)s: dispatching %(total)s but only %(allocated)s is allocated",
                            product=line.product_id.display_name,
                            total=already_shipped + about_to_ship,
                            allocated=line.quantity_allocated,
                        )
                    )
            if over_dispatched:
                raise UserError(
                    _(
                        "Dispatch %(picking)s would ship more than request "
                        "%(request)s allocated:\n\n%(details)s\n\n"
                        "Reduce the quantities, or allocate more stock to the "
                        "request first.",
                        picking=picking.name,
                        request=picking.drims_request_id.reference,
                        details="\n".join(over_dispatched),
                    )
                )

    def button_validate(self):
        """Override button_validate to enforce beneficiary validation and invalidate cache.

        When a request_dispatch picking is validated, this:
        1. Refuses items or quantities the request never approved (OP#1057)
        2. Validates that beneficiary tracking fields are filled (beneficiary_count, beneficiary_area_id)
        3. Invalidates the cached KPI values to ensure dashboard shows current data
        """
        self._check_drims_dispatch_matches_request()

        # Validate beneficiary tracking for DRIMS dispatches
        for picking in self:
            if picking.drims_type == "request_dispatch":
                if not picking.beneficiary_count or picking.beneficiary_count <= 0:
                    raise UserError(
                        _(
                            "Please enter the number of beneficiaries served for "
                            "dispatch %s under the DRIMS tab. This is required for "
                            "DRIMS distribution tracking."
                        )
                        % picking.name
                    )
                if not picking.beneficiary_area_id:
                    raise UserError(
                        _(
                            "Please select the distribution area for dispatch %s "
                            "under the DRIMS tab. This is required for DRIMS "
                            "geographic reporting."
                        )
                        % picking.name
                    )

        # Get incidents before validation changes state
        incident_ids = list(set(p.incident_id.id for p in self if p.incident_id and p.drims_type == "request_dispatch"))

        result = super().button_validate()

        # Invalidate affected caches
        if incident_ids:
            self._invalidate_drims_kpi_cache(incident_ids)

        return result

    def _action_done(self):
        """Settle the request's state once a dispatch is really done.

        This used to hang off button_validate, which only covers the web
        client's Validate button: a backorder released through the API, the
        barcode flow or a direct _action_done reconciled its quantities through
        the move hook but never re-advanced the request, leaving it at
        "allocated" with everything already shipped (OP#1087 review).

        _action_done is the point every path goes through, and calling it after
        super() means Odoo has already split off any backorder — which is what
        _sync_state_after_dispatch_done inspects before advancing.
        """
        result = super()._action_done()

        requests = self.filtered(lambda p: p.drims_type == "request_dispatch").drims_request_id
        if requests:
            requests._sync_state_after_dispatch_done()

        return result

    def _create_backorder(self, backorder_moves=None):
        """Surface DRIMS dispatch backorders on their request (OP#1087).

        Odoo creates the backorder picking silently, so on its own a partially
        validated dispatch leaves the coordinator with no notification and the
        request still reading as fully dispatched.
        """
        backorders = super()._create_backorder(backorder_moves=backorder_moves)
        for backorder in backorders:
            if backorder.drims_type == "request_dispatch" and backorder.drims_request_id:
                backorder.drims_request_id._on_dispatch_backorder_created(backorder)
        return backorders

    def _invalidate_drims_kpi_cache(self, incident_ids):
        """Invalidate DRIMS KPI cache for distributed and stock values.

        This method is called after validating a dispatch picking to ensure
        that cached KPI values are refreshed to reflect the latest stock
        movements.

        Args:
            incident_ids: List of incident IDs to invalidate cache for.
        """
        DataValue = self.env["spp.data.value"]
        for var in ["drims_distributed_value", "drims_stock_value"]:
            DataValue.search(
                [
                    ("variable_name", "=", var),
                    ("subject_model", "=", "spp.hazard.incident"),
                    ("subject_id", "in", incident_ids),
                ]
            ).unlink()
