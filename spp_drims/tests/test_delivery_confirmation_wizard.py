# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsDeliveryConfirmation(DrimsTestCommon):
    """OP#1088: Confirm Delivery collects proof of delivery in one popup.

    Also the first thing in the module to write
    ``spp.drims.request.line.quantity_delivered`` — until now nothing did, so a
    request's ``total_delivered`` and ``fulfillment_pct`` stayed at 0 however
    much had arrived.
    """

    def setUp(self):
        super().setUp()
        self.future_date = date.today() + timedelta(days=30)
        self.pod_complete = self.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:pod-statuses"),
                ("code", "=", "complete"),
            ],
            limit=1,
        )
        self.pod_partial = self.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:pod-statuses"),
                ("code", "=", "partial"),
            ],
            limit=1,
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _delivered_dispatch(self, requested=100, shipped=None):
        """A validated dispatch that has departed, ready for delivery confirmation."""
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": requested,
            }
        )
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "source_warehouse_id": self.warehouse.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_requested": requested,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        request.line_ids[0].quantity_allocated = requested
        request.state_id = self.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )
        request.action_create_dispatch()
        picking = request.picking_ids
        picking.write({"beneficiary_count": 300, "beneficiary_area_id": self.area.id})
        move = picking.move_ids[0]
        move.quantity = shipped if shipped is not None else requested
        move.picked = True
        picking.with_context(skip_backorder=True).button_validate()
        picking.action_confirm_departure()
        return request, picking

    def _wizard_for(self, picking, **overrides):
        vals = {
            "pod_received_by": "Barangay Captain Reyes",
            "pod_receiver_title": "Barangay Captain",
            "pod_status_id": self.pod_complete.id,
        }
        vals.update(overrides)
        return (
            self.env["spp.drims.delivery.confirmation.wizard"].with_context(default_picking_id=picking.id).create(vals)
        )

    # ------------------------------------------------------------------
    # opening the popup
    # ------------------------------------------------------------------

    def test_button_opens_the_wizard_once_departed(self):
        _request, picking = self._delivered_dispatch()

        action = picking.action_open_delivery_confirmation()

        self.assertEqual(action["res_model"], "spp.drims.delivery.confirmation.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_picking_id"], picking.id)

    def test_cannot_confirm_delivery_before_departure(self):
        """The order is enforced on the model, not only by hiding the button."""
        _request, picking = self._delivered_dispatch()
        picking.date_departed = False

        with self.assertRaises(UserError) as cm:
            picking.action_open_delivery_confirmation()
        self.assertIn("has not departed", str(cm.exception))

        # The direct API is guarded too, so RPC cannot bypass the ordering.
        picking.pod_received_by = "Someone"
        with self.assertRaises(UserError):
            picking.action_confirm_pod()

    def test_cannot_confirm_delivery_twice(self):
        _request, picking = self._delivered_dispatch()
        self._wizard_for(picking).action_confirm()

        with self.assertRaises(UserError) as cm:
            picking.action_open_delivery_confirmation()
        self.assertIn("already confirmed", str(cm.exception))

    def test_wizard_rejects_non_dispatch_pickings(self):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            }
        )
        with self.assertRaises(UserError):
            picking.action_open_delivery_confirmation()

    # ------------------------------------------------------------------
    # what the wizard pre-fills
    # ------------------------------------------------------------------

    def test_lines_default_to_what_was_dispatched(self):
        """Lines come from the done moves, defaulting to everything arriving."""
        request, picking = self._delivered_dispatch(requested=100)

        wizard = self._wizard_for(picking)

        self.assertEqual(len(wizard.line_ids), 1)
        line = wizard.line_ids
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.quantity_dispatched, 100)
        self.assertEqual(line.quantity_delivered, 100)
        self.assertEqual(line.request_line_id, request.line_ids)

    def test_lines_are_filled_when_picking_comes_in_the_values(self):
        """Lines must not depend on picking_id arriving via the context.

        ``default_get`` only runs for fields absent from the values, so passing
        ``picking_id`` in the values — the obvious way from a script or over RPC —
        used to produce a wizard with no lines that silently recorded no
        delivered quantities.
        """
        request, picking = self._delivered_dispatch(requested=100)

        wizard = self.env["spp.drims.delivery.confirmation.wizard"].create(
            {
                "picking_id": picking.id,
                "pod_received_by": "Direct Caller",
                "pod_status_id": self.pod_complete.id,
            }
        )

        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.quantity_delivered, 100)

        wizard.action_confirm()
        self.assertEqual(request.total_delivered, 100)

    # ------------------------------------------------------------------
    # confirming
    # ------------------------------------------------------------------

    def test_confirm_writes_the_proof_of_delivery(self):
        _request, picking = self._delivered_dispatch()
        arrival = fields.Datetime.now()

        self._wizard_for(
            picking,
            date_arrived=arrival,
            pod_receiver_id_number="ID-4471",
            pod_notes="Handed over at the covered court.",
            pod_gps_latitude=14.5995,
            pod_gps_longitude=120.9842,
        ).action_confirm()

        self.assertTrue(picking.is_pod_confirmed)
        self.assertEqual(picking.pod_received_by, "Barangay Captain Reyes")
        self.assertEqual(picking.pod_receiver_title, "Barangay Captain")
        self.assertEqual(picking.pod_receiver_id_number, "ID-4471")
        self.assertEqual(picking.pod_status_id, self.pod_complete)
        self.assertEqual(picking.date_arrived, arrival)
        self.assertEqual(picking.pod_notes, "Handed over at the covered court.")
        self.assertAlmostEqual(picking.pod_gps_latitude, 14.5995, places=4)
        # The GeoPoint compute picks the coordinates up for GIS reporting.
        self.assertTrue(picking.pod_gps_point)

    def test_confirm_records_delivered_quantities_on_the_request(self):
        """The point of the lines table: fulfillment stops reading 0."""
        request, picking = self._delivered_dispatch(requested=100)
        self.assertEqual(request.total_delivered, 0)
        self.assertEqual(request.fulfillment_pct, 0)

        self._wizard_for(picking).action_confirm()

        self.assertEqual(request.line_ids[0].quantity_delivered, 100)
        self.assertEqual(request.total_delivered, 100)
        self.assertEqual(request.fulfillment_pct, 100)

    def test_short_delivery_records_only_what_arrived(self):
        request, picking = self._delivered_dispatch(requested=100)
        wizard = self._wizard_for(picking, pod_status_id=self.pod_partial.id)
        wizard.line_ids.quantity_delivered = 80
        wizard.discrepancy_notes = "20 units water-damaged in transit."

        wizard.action_confirm()

        self.assertEqual(request.total_delivered, 80)
        self.assertEqual(request.fulfillment_pct, 80)
        self.assertEqual(picking.discrepancy_notes, "20 units water-damaged in transit.")

    def test_delivered_quantities_accumulate_across_dispatches(self):
        """A request filled by two shipments must total, not overwrite.

        Shipping 60 of 100 leaves a backorder for the balance, which is the
        request's second dispatch. Both confirmations contribute.
        """
        request, first = self._delivered_dispatch(requested=100, shipped=60)
        self._wizard_for(first).action_confirm()
        self.assertEqual(request.total_delivered, 60)

        second = self.env["stock.picking"].search([("backorder_id", "=", first.id)])
        self.assertEqual(len(second), 1, "partial validation should leave a backorder")
        self.assertEqual(second.drims_request_id, request)

        # Set the beneficiary fields explicitly rather than relying on whatever
        # the backorder inherited from its parent.
        second.write({"beneficiary_count": 100, "beneficiary_area_id": self.area.id})
        second.move_ids.quantity = 40
        second.move_ids.picked = True
        second.with_context(skip_backorder=True).button_validate()
        second.action_confirm_departure()
        self._wizard_for(second).action_confirm()

        self.assertEqual(second.state, "done")
        self.assertEqual(request.total_delivered, 100)
        self.assertEqual(request.fulfillment_pct, 100)

    # ------------------------------------------------------------------
    # validation
    # ------------------------------------------------------------------

    def test_cannot_deliver_more_than_was_dispatched(self):
        _request, picking = self._delivered_dispatch(requested=100)
        wizard = self._wizard_for(picking)

        with self.assertRaises(ValidationError) as cm:
            wizard.line_ids.quantity_delivered = 120
        self.assertIn("more", str(cm.exception))

    def test_cannot_deliver_a_negative_quantity(self):
        _request, picking = self._delivered_dispatch()
        wizard = self._wizard_for(picking)

        with self.assertRaises(ValidationError):
            wizard.line_ids.quantity_delivered = -5

    def test_arrival_cannot_precede_departure(self):
        _request, picking = self._delivered_dispatch()
        wizard = self._wizard_for(picking, date_arrived=picking.date_departed - timedelta(hours=2))

        with self.assertRaises(UserError) as cm:
            wizard.action_confirm()
        self.assertIn("cannot be before", str(cm.exception))

    def test_out_of_range_gps_is_rejected(self):
        """Out-of-range coordinates must raise, not be silently dropped.

        ``_compute_pod_gps_point`` logs a warning and stores nothing, which would
        lose the delivery location without telling anyone.
        """
        _request, picking = self._delivered_dispatch()

        with self.assertRaises(ValidationError):
            self._wizard_for(picking, pod_gps_latitude=95.0)

    def test_departure_cannot_be_re_recorded_after_delivery(self):
        _request, picking = self._delivered_dispatch()
        self._wizard_for(picking).action_confirm()

        with self.assertRaises(UserError):
            picking.action_confirm_departure()
