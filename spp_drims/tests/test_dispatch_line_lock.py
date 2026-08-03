# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsDispatchLineLock(DrimsTestCommon):
    """OP#1057: a dispatch may only ship what its request approved.

    The Operations tab stays editable while a dispatch is Ready, so products
    could be added and quantities inflated past the approval workflow. These
    tests cover the model-side guard, which is what protects RPC and imports —
    the view attributes only stop the UI inviting the mistake.
    """

    def setUp(self):
        super().setUp()
        self.future_date = date.today() + timedelta(days=30)
        self.rogue_product = self.env["product.product"].create(
            {
                "name": "Unapproved Item",
                "type": "consu",
                "is_storable": True,
                "standard_price": 999.0,
            }
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _stock_up(self, product, quantity):
        self.env["stock.quant"].create(
            {
                "product_id": product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": quantity,
            }
        )

    def _dispatch_for(self, requested=100, allocated=100):
        """An allocated request plus its confirmed dispatch, ready to validate."""
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
        request.line_ids[0].quantity_allocated = allocated
        request.state_id = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )
        request.action_create_dispatch()
        picking = request.picking_ids
        picking.write({"beneficiary_count": 500, "beneficiary_area_id": self.area.id})
        return request, picking

    def _pick_everything(self, picking):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.move_ids.picked = True

    # ------------------------------------------------------------------
    # extra products
    # ------------------------------------------------------------------

    def test_added_product_blocks_validation(self):
        """A product the request never asked for must stop the dispatch."""
        self._stock_up(self.product, 100)
        self._stock_up(self.rogue_product, 100)
        _request, picking = self._dispatch_for()

        self.env["stock.move"].create(
            {
                "picking_id": picking.id,
                "product_id": self.rogue_product.id,
                "product_uom_qty": 50.0,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
        )
        self._pick_everything(picking)

        with self.assertRaises(UserError) as cm:
            picking.button_validate()
        self.assertIn("Unapproved Item", str(cm.exception))
        self.assertNotEqual(picking.state, "done")

    def test_guard_is_not_keyed_on_the_additional_flag(self):
        """The check must catch moves Odoo never flagged as ``additional``.

        ``additional`` is only set when a line is added through the form, so a
        move created over RPC or by an import leaves it False. Keying the guard on
        it would leave exactly that hole.
        """
        self._stock_up(self.product, 100)
        self._stock_up(self.rogue_product, 100)
        _request, picking = self._dispatch_for()

        rogue_move = self.env["stock.move"].create(
            {
                "picking_id": picking.id,
                "product_id": self.rogue_product.id,
                "product_uom_qty": 50.0,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
        )
        self.assertFalse(rogue_move.additional, "precondition: RPC-created moves are not 'additional'")
        self._pick_everything(picking)

        with self.assertRaises(UserError):
            picking.button_validate()

    def test_move_from_another_request_blocks_validation(self):
        """A move linked to a different request's line is still not approved here.

        The message names the dispatch's own request — the one whose approval was
        bypassed — rather than the request the line was borrowed from.
        """
        self._stock_up(self.product, 300)
        request_a, picking_a = self._dispatch_for()
        _request_b, picking_b = self._dispatch_for()

        # Smuggle B's move onto A's dispatch.
        picking_b.move_ids[0].picking_id = picking_a.id
        self._pick_everything(picking_a)

        with self.assertRaises(UserError) as cm:
            picking_a.button_validate()
        message = str(cm.exception)
        self.assertIn(request_a.reference, message)
        self.assertIn(self.product.display_name, message)
        self.assertNotEqual(picking_a.state, "done")

    # ------------------------------------------------------------------
    # inflated quantities
    # ------------------------------------------------------------------

    def test_demand_raised_above_allocation_blocks_validation(self):
        """Unlocking and raising Demand must not ship more than was allocated."""
        self._stock_up(self.product, 300)
        _request, picking = self._dispatch_for(requested=100, allocated=100)

        picking.is_locked = False
        move = picking.move_ids[0]
        self.assertTrue(move.is_initial_demand_editable, "precondition: unlocking frees Demand")
        move.product_uom_qty = 150.0
        self._pick_everything(picking)

        with self.assertRaises(UserError) as cm:
            picking.button_validate()
        self.assertIn("more than", str(cm.exception))
        self.assertNotEqual(picking.state, "done")

    def test_picked_quantity_above_allocation_blocks_validation(self):
        """Over-picking beyond the allocation is refused even with Demand intact."""
        self._stock_up(self.product, 300)
        _request, picking = self._dispatch_for(requested=100, allocated=100)

        move = picking.move_ids[0]
        move.quantity = 130.0
        move.picked = True

        with self.assertRaises(UserError):
            picking.button_validate()

    # ------------------------------------------------------------------
    # legitimate flows must be untouched
    # ------------------------------------------------------------------

    def test_full_dispatch_validates(self):
        """The ordinary case still works."""
        self._stock_up(self.product, 100)
        _request, picking = self._dispatch_for()
        self._pick_everything(picking)

        picking.button_validate()

        self.assertEqual(picking.state, "done")

    def test_partial_dispatch_validates(self):
        """Shipping less than Demand must stay allowed.

        This is how a partial dispatch and its backorder are produced (OP#1087),
        so the guard must not treat under-picking as a violation.
        """
        self._stock_up(self.product, 100)
        _request, picking = self._dispatch_for()
        move = picking.move_ids[0]
        move.quantity = 90.0
        move.picked = True

        # No UserError from the DRIMS guard; Odoo asks about the backorder.
        action = picking.button_validate()
        self.assertIsInstance(action, dict)
        self.assertEqual(action["res_model"], "stock.backorder.confirmation")

    def test_second_dispatch_after_top_up_validates(self):
        """The cumulative check must not false-positive across dispatches."""
        self._stock_up(self.product, 5000)
        request, first = self._dispatch_for(requested=5000, allocated=2000)
        self._pick_everything(first)
        first.button_validate()
        self.assertEqual(first.state, "done")

        # Allocate the rest and dispatch again.
        request.line_ids[0].quantity_allocated = 5000
        request.action_create_dispatch()
        second = request.picking_ids - first
        second.write({"beneficiary_count": 200, "beneficiary_area_id": self.area.id})
        self._pick_everything(second)

        second.button_validate()

        self.assertEqual(second.state, "done")
        self.assertEqual(request.line_ids[0].quantity_dispatched, 5000)

    def test_non_drims_picking_is_unaffected(self):
        """The guard must only apply to DRIMS request dispatches."""
        self._stock_up(self.rogue_product, 50)
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.rogue_product.id,
                            "product_uom_qty": 10.0,
                            "location_id": self.warehouse.lot_stock_id.id,
                            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        self._pick_everything(picking)

        picking.button_validate()

        self.assertEqual(picking.state, "done")
