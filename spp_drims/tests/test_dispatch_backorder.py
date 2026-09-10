# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsDispatchBackorder(DrimsTestCommon):
    """OP#1087: a dispatch validated short must not bypass the DRIMS request.

    Odoo builds a backorder with ``picking.copy()``, which used to carry the
    parent's per-shipment facts (beneficiary count, departure, driver, POD) onto
    goods still sitting in the warehouse, leave the request reading as fully
    ``dispatched``, and tell nobody.
    """

    def setUp(self):
        super().setUp()
        self.future_date = date.today() + timedelta(days=30)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _stock_up(self, quantity):
        """Put ``quantity`` of the test product into the DRIMS warehouse."""
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": quantity,
            }
        )

    def _allocate(self, line, quantity, warehouse=None):
        """Record a per-warehouse allocation for ``line``.

        OP#1079 replaced the writable ``quantity_allocated`` on the request line
        with a stored compute over ``allocation_ids``, so allocation has to be
        expressed as a row against a warehouse.
        """
        return self.env["spp.drims.request.allocation"].create(
            {
                "request_line_id": line.id,
                "warehouse_id": (warehouse or self.warehouse).id,
                "quantity_allocated": quantity,
            }
        )

    def _dispatch_for(self, requested=100, allocated=100):
        """Return an allocated request plus its confirmed dispatch picking."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
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
        self._allocate(request.line_ids[0], allocated)
        request.state_id = request._get_state_by_code("allocated")
        request.action_create_dispatch()
        picking = request.picking_ids
        self.assertEqual(len(picking), 1)
        # Fill what button_validate() demands of a DRIMS dispatch, and record a
        # departure so we can prove it does not leak onto the backorder.
        picking.write(
            {
                "beneficiary_count": 500,
                "beneficiary_area_id": self.area.id,
                "driver_name": "Test Driver",
            }
        )
        picking.action_confirm_departure()
        return request, picking

    def _validate_short(self, picking, quantity):
        """Validate ``picking`` for ``quantity`` only, choosing Create Backorder."""
        picking.move_ids.write({"quantity": quantity, "picked": True})
        action = picking.button_validate()
        self.assertIsInstance(action, dict, "expected the Create Backorder wizard")
        self.assertEqual(action["res_model"], "stock.backorder.confirmation")
        wizard = (
            self.env["stock.backorder.confirmation"]
            .with_context(**action["context"])
            .create(
                {
                    "pick_ids": [(6, 0, picking.ids)],
                    "backorder_confirmation_line_ids": [(0, 0, {"to_backorder": True, "picking_id": picking.id})],
                }
            )
        )
        wizard.with_context(**action["context"]).process()
        backorder = self.env["stock.picking"].search([("backorder_id", "=", picking.id)])
        self.assertEqual(len(backorder), 1)
        return backorder

    # ------------------------------------------------------------------
    # per-shipment facts must not be inherited
    # ------------------------------------------------------------------

    def test_backorder_does_not_inherit_beneficiary_count(self):
        """The parent's beneficiary count must not be attributed to the backorder.

        ``spp.hazard.incident.drims_beneficiaries_served`` sums beneficiary_count
        over every done dispatch, so an inherited value double-counts the same
        people once the backorder is validated too.
        """
        self._stock_up(100)
        _request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)

        self.assertEqual(picking.beneficiary_count, 500)
        self.assertFalse(backorder.beneficiary_count)

    def test_backorder_does_not_inherit_departure_or_driver(self):
        """A backorder has not departed, whatever the parent recorded."""
        self._stock_up(100)
        _request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)

        self.assertTrue(picking.date_departed)
        self.assertFalse(backorder.date_departed)
        self.assertFalse(backorder.date_arrived)
        self.assertFalse(backorder.driver_name)
        self.assertFalse(backorder.is_pod_confirmed)

    def test_backorder_validation_requires_its_own_beneficiary_count(self):
        """The beneficiary guard must fire on the backorder, not be pre-satisfied."""
        self._stock_up(100)
        _request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)

        backorder.move_ids.write({"quantity": 10, "picked": True})
        with self.assertRaises(UserError) as cm:
            backorder.button_validate()
        self.assertIn("beneficiaries served", str(cm.exception))

    def test_backorder_keeps_request_link_and_gets_own_waybill(self):
        """Identity that *should* carry, carries; the waybill is still unique."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)

        self.assertEqual(backorder.drims_request_id, request)
        self.assertEqual(backorder.drims_type, "request_dispatch")
        self.assertEqual(backorder.incident_id, self.incident)
        self.assertEqual(request.picking_count, 2)
        self.assertTrue(backorder.waybill_number)
        self.assertNotEqual(backorder.waybill_number, picking.waybill_number)
        # Per-line attribution survives the move split.
        self.assertEqual(backorder.move_ids.drims_request_line_id, request.line_ids)

    # ------------------------------------------------------------------
    # request state must account for the outstanding backorder
    # ------------------------------------------------------------------

    def test_backorder_reopens_request_from_dispatched(self):
        """The request must not read as dispatched while a backorder is pending."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        self.assertEqual(request.state, "dispatched")

        backorder = self._validate_short(picking, 90)

        self.assertEqual(request.state, "allocated")
        self.assertEqual(backorder.state, "assigned")

    def test_validating_the_backorder_returns_request_to_dispatched(self):
        """Once the balance ships, the request advances again."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)
        self.assertEqual(request.state, "allocated")

        backorder.write({"beneficiary_count": 40, "beneficiary_area_id": self.area.id})
        backorder.move_ids.write({"quantity": 10, "picked": True})
        backorder.button_validate()

        self.assertEqual(backorder.state, "done")
        self.assertEqual(request.state, "dispatched")

    def test_backorder_validated_outside_the_web_client_still_advances(self):
        """The re-advance hangs off _action_done, not the Validate button.

        A backorder released through the API, the barcode flow or a direct
        _action_done reconciles its quantities through the move hook; when the
        state sync hung off button_validate, none of those paths re-advanced the
        request, leaving it at "allocated" with everything already shipped
        (OP#1087 review).
        """
        self._stock_up(100)
        request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)
        self.assertEqual(request.state, "allocated")

        backorder.write({"beneficiary_count": 40, "beneficiary_area_id": self.area.id})
        backorder.move_ids.write({"quantity": 10, "picked": True})
        # Deliberately not button_validate(): this is the path a non-UI caller
        # takes into the same transfer.
        backorder._action_done()

        self.assertEqual(backorder.state, "done")
        self.assertEqual(request.state, "dispatched")

    def test_the_backorder_note_names_who_shipped_short(self):
        """The note is posted through sudo, so OdooBot authors it.

        Without naming the acting user in the body, the audit trail records that
        a dispatch went short but not who validated it (OP#1087 review).
        """
        self._stock_up(100)
        request, picking = self._dispatch_for()
        self._validate_short(picking, 90)

        notes = request.message_ids.filtered(lambda m: "short of its demand" in (m.body or ""))
        self.assertTrue(notes, "the short dispatch should be announced on the request")
        self.assertIn(self.env.user.display_name, notes[0].body)

    def test_incident_beneficiaries_are_not_double_counted(self):
        """The whole point: 100 units to 500 people stays 500, not 1000."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)

        backorder.write({"beneficiary_count": 40, "beneficiary_area_id": self.area.id})
        backorder.move_ids.write({"quantity": 10, "picked": True})
        backorder.button_validate()

        self.incident.invalidate_recordset(["drims_beneficiaries_served"])
        # 500 recorded on the parent plus the 40 the officer entered for the
        # balance — not the parent's 500 counted twice.
        self.assertEqual(self.incident.drims_beneficiaries_served, 540)
        self.assertEqual(request.state, "dispatched")

    # ------------------------------------------------------------------
    # a cancelled balance must be released, not left counted as dispatched
    # ------------------------------------------------------------------

    def test_cancelling_the_backorder_releases_the_quantity(self):
        """A cancelled backorder must leave the request dispatchable again."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        backorder = self._validate_short(picking, 90)
        self.assertEqual(request.line_ids[0].quantity_dispatched, 100)

        backorder.action_cancel()

        self.assertEqual(backorder.state, "cancel")
        self.assertEqual(request.state, "allocated")
        # The 10 units never shipped, so they are available to dispatch again.
        self.assertEqual(request.line_ids[0].quantity_dispatched, 90)
        self._assert_released(request, dispatched=90, remaining=10)
        request.action_create_dispatch()
        new_dispatch = request.picking_ids - picking - backorder
        self.assertEqual(len(new_dispatch), 1)
        self.assertEqual(new_dispatch.move_ids.product_uom_qty, 10)

    def _assert_released(self, request, dispatched, remaining):
        """The release has to land on the allocation rows, not just the line.

        The line's quantity_dispatched is a stored compute over those rows
        (OP#1079). Writing it directly persists until something retriggers the
        compute, so a test that only checks the line can pass while the
        allocation underneath is still wrong — and it is the allocation that
        decides how much stock is free to allocate again.
        """
        allocations = request.line_ids.allocation_ids
        self.assertTrue(allocations, "the request line should have allocation rows")
        self.assertEqual(sum(allocations.mapped("quantity_dispatched")), dispatched)
        self.assertEqual(sum(allocations.mapped("quantity_remaining")), remaining)

    def test_declining_the_backorder_releases_the_quantity(self):
        """Answering "No" to Create Backorder cancels the balance, not ships it."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        picking.move_ids.write({"quantity": 90, "picked": True})
        action = picking.button_validate()
        wizard = (
            self.env["stock.backorder.confirmation"]
            .with_context(**action["context"])
            .create({"pick_ids": [(6, 0, picking.ids)]})
        )
        wizard.with_context(**action["context"]).process_cancel_backorder()

        self.assertEqual(picking.state, "done")
        self.assertFalse(self.env["stock.picking"].search([("backorder_id", "=", picking.id)]))
        # Only 90 shipped, so the request must not read as fully dispatched.
        self.assertEqual(request.line_ids[0].quantity_dispatched, 90)
        self.assertEqual(request.state, "allocated")
        self._assert_released(request, dispatched=90, remaining=10)

    def test_cancelling_the_whole_dispatch_releases_everything(self):
        """Cancelling an unvalidated dispatch returns the full quantity."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        self.assertEqual(request.line_ids[0].quantity_dispatched, 100)

        picking.action_cancel()

        self.assertEqual(picking.state, "cancel")
        self.assertEqual(request.line_ids[0].quantity_dispatched, 0)
        self.assertEqual(request.state, "allocated")
        self._assert_released(request, dispatched=0, remaining=100)

    # ------------------------------------------------------------------
    # coordinator visibility
    # ------------------------------------------------------------------

    def test_backorder_notifies_the_area_coordinator(self):
        """A coordinator for the destination area gets a note and a to-do."""
        coordinator = self.env["res.users"].create(
            {
                "name": "Area Coordinator",
                "login": "op1087_coordinator",
                "group_ids": [(4, self.env.ref("spp_drims.group_drims_coordinator_supervisor").id)],
                "drims_area_ids": [(6, 0, self.area.ids)],
            }
        )
        self._stock_up(100)
        request, picking = self._dispatch_for()
        messages_before = len(request.message_ids)

        backorder = self._validate_short(picking, 90)

        self.assertGreater(len(request.message_ids), messages_before)
        note = request.message_ids[0]
        self.assertIn(backorder.name, note.body)
        self.assertIn(coordinator.partner_id, note.partner_ids)

        activity = self.env["mail.activity"].search(
            [
                ("res_model", "=", "spp.drims.request"),
                ("res_id", "=", request.id),
                ("user_id", "=", coordinator.id),
            ]
        )
        self.assertEqual(len(activity), 1)
        self.assertIn(backorder.name, activity.summary)

    def test_backorder_without_any_coordinator_still_logs(self):
        """No coordinator configured must not break validation."""
        self._stock_up(100)
        request, picking = self._dispatch_for()
        messages_before = len(request.message_ids)

        backorder = self._validate_short(picking, 90)

        self.assertGreater(len(request.message_ids), messages_before)
        self.assertIn(backorder.name, request.message_ids[0].body)
