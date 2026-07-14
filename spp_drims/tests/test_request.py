# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsRequest(DrimsTestCommon):
    """Tests for DRIMS Request model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Use future dates relative to today
        cls.future_date = date.today() + timedelta(days=30)

    def test_create_request(self):
        """Test basic request creation."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "priority_id": self.priority_routine.id,
            }
        )
        self.assertTrue(request.reference.startswith("REQ-"))
        self.assertEqual(request.state, "draft")
        self.assertEqual(request.approval_state, "draft")

    def test_request_with_lines(self):
        """Test request with line items and computed values."""
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
                            "quantity_requested": 50,
                            "uom_id": self.product.uom_id.id,
                            "unit_value": 100.0,
                        },
                    )
                ],
            }
        )
        self.assertEqual(request.line_count, 1)
        self.assertEqual(request.total_value, 5000.0)
        self.assertEqual(request.total_quantity, 50)

    def test_submit_without_lines_fails(self):
        """Test that submitting without lines raises error."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        with self.assertRaises(UserError):
            request.action_submit()

    def test_submit_with_lines(self):
        """Test successful submission with lines."""
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
                            "quantity_requested": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        self.assertEqual(request.state, "submitted")

    def test_life_threatening_flag(self):
        """Test life-threatening emergency flag."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "is_life_threatening": True,
            }
        )
        self.assertTrue(request.is_life_threatening)

    def test_date_needed_validation(self):
        """Test that date_needed cannot be before date_requested."""
        past_date = date.today() - timedelta(days=5)
        with self.assertRaises(ValidationError):
            self.env["spp.drims.request"].create(
                {
                    "incident_id": self.incident.id,
                    "destination_area_id": self.area.id,
                    "date_needed": past_date,
                }
            )

    def test_request_line_quantity_validation(self):
        """Test that line quantity must be positive."""
        with self.assertRaises(ValidationError):
            self.env["spp.drims.request"].create(
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
                                "quantity_requested": -10,
                                "uom_id": self.product.uom_id.id,
                            },
                        )
                    ],
                }
            )

    def test_approve_request(self):
        """Test approving a pending request."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        self.assertEqual(request.approval_state, "approved")
        self.assertEqual(request.state, "approved")

    def test_reject_request(self):
        """Test rejecting a pending request."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_reject(reason="Budget constraints")
        self.assertEqual(request.approval_state, "rejected")
        self.assertEqual(request.rejection_reason, "Budget constraints")

    def test_request_revision(self):
        """Test requesting revision from approver."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_request_revision(notes="Please add justification")
        self.assertEqual(request.approval_state, "revision")
        self.assertEqual(request.revision_notes, "Please add justification")

    def test_reset_to_draft(self):
        """Test resetting rejected request to draft."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_reject(reason="Test rejection")
        request.action_reset_to_draft()
        self.assertEqual(request.approval_state, "draft")
        self.assertFalse(request.rejection_reason)

    def test_cannot_approve_draft_request(self):
        """Test that draft requests cannot be approved."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        with self.assertRaises(UserError):
            request.action_approve()

    def test_request_requester_default(self):
        """Test that requester defaults to current user."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        self.assertEqual(request.requester_id, self.env.user)

    def test_fulfillment_percentage(self):
        """Test fulfillment percentage computation."""
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
                            "quantity_requested": 100,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        line = request.line_ids[0]
        self.assertEqual(line.fulfillment_pct, 0.0)
        # OP#1079: fulfillment tracks allocated / requested, so drive it through
        # per-warehouse allocation records rather than a delivered quantity.
        alloc = self.env["spp.drims.request.allocation"].create(
            {
                "request_line_id": line.id,
                "warehouse_id": self.warehouse.id,
                "quantity_allocated": 50,
            }
        )
        self.assertEqual(line.fulfillment_pct, 50.0)
        alloc.quantity_allocated = 100
        self.assertEqual(line.fulfillment_pct, 100.0)

    def test_line_quantity_tracking(self):
        """Test tracking of approved, allocated, dispatched, delivered quantities."""
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
                            "quantity_requested": 100,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        line = request.line_ids[0]
        # Simulate workflow. quantity_allocated / quantity_dispatched are now
        # sums of the per-warehouse allocation records (OP#1079), so drive
        # them through an allocation row rather than writing them directly.
        line.quantity_approved = 80
        self.env["spp.drims.request.allocation"].create(
            {
                "request_line_id": line.id,
                "warehouse_id": self.warehouse.id,
                "quantity_allocated": 75,
                "quantity_dispatched": 70,
            }
        )
        line.quantity_delivered = 70
        self.assertEqual(line.quantity_approved, 80)
        self.assertEqual(line.quantity_allocated, 75)
        self.assertEqual(line.quantity_dispatched, 70)
        # OP#1079: fulfillment now tracks allocated / requested (75 / 100).
        self.assertEqual(line.fulfillment_pct, 75.0)

    def test_request_unique_reference(self):
        """Test that request references are unique."""
        request1 = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        # Verify reference was generated
        self.assertTrue(request1.reference)
        self.assertNotEqual(request1.reference, "New")
        # Create second request and verify different reference
        request2 = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        self.assertNotEqual(request1.reference, request2.reference)

    def _seed_stock(self, warehouse, qty, product=None):
        self.env["stock.quant"].create(
            {
                "product_id": (product or self.product).id,
                "location_id": warehouse.lot_stock_id.id,
                "quantity": qty,
            }
        )

    def _add_alloc(self, request, qty, warehouse=None, line=None):
        """Create/top up a per-warehouse allocation record for a request line."""
        return request._add_allocation(line or request.line_ids[0], warehouse or self.warehouse, qty)

    def _mark_allocated(self, request):
        request._set_state_by_code("allocated")

    def test_allocate_auto_splits_from_stock(self):
        """action_allocate fills each line from the DRIMS warehouses that hold
        stock, creating per-warehouse allocation records (OP#1079)."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        self._seed_stock(self.warehouse, 25.0)
        request.action_allocate()
        self.assertEqual(request.state, "allocated")
        self.assertEqual(request.total_allocated, 10)
        self.assertEqual(request.line_ids.allocation_ids.warehouse_id, self.warehouse)

    def test_allocate_blocked_when_no_stock(self):
        """OP#1032/OP#1079: action_allocate refuses to advance the state when
        no DRIMS warehouse has available stock for any requested line.
        """
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        with self.assertRaises(UserError):
            request.action_allocate()
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.total_allocated, 0)

    def test_create_dispatch_not_allocated(self):
        """Test that dispatch requires allocated state (GAP-REQ-003)."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        # Not allocated yet - should fail
        with self.assertRaises(UserError):
            request.action_create_dispatch()

    def test_create_dispatch_workflow(self):
        """Test full dispatch creation workflow (GAP-REQ-003)."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        # Allocate 10 from the warehouse, then mark allocated.
        self._add_alloc(request, 10)
        self._mark_allocated(request)

        # Now dispatch should work
        action = request.action_create_dispatch()
        self.assertEqual(action["res_model"], "stock.picking")

        # Verify picking was created
        self.assertEqual(request.picking_count, 1)
        picking = request.picking_ids[0]
        self.assertEqual(picking.drims_request_id, request)
        self.assertEqual(picking.incident_id, self.incident)
        self.assertEqual(picking.drims_type, "request_dispatch")
        self.assertEqual(len(picking.move_ids), 1)

        # Verify request state updated
        self.assertEqual(request.state, "dispatched")

    def test_dispatch_creates_one_picking_per_warehouse(self):
        """OP#1079: a request allocated across two warehouses dispatches as one
        picking per source warehouse, each moving that warehouse's quantity."""
        warehouse2 = self.env["stock.warehouse"].create(
            {"name": "Dispatch WH2", "code": "DWH2", "is_drims_warehouse": True}
        )
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
                            "quantity_requested": 70,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        self._add_alloc(request, 50, warehouse=self.warehouse)
        self._add_alloc(request, 20, warehouse=warehouse2)
        self._mark_allocated(request)

        request.action_create_dispatch()

        self.assertEqual(request.picking_count, 2)
        qty_by_wh = {p.location_id.warehouse_id: sum(p.move_ids.mapped("product_uom_qty")) for p in request.picking_ids}
        self.assertEqual(qty_by_wh.get(self.warehouse), 50)
        self.assertEqual(qty_by_wh.get(warehouse2), 20)
        self.assertEqual(request.line_ids.quantity_dispatched, 70)
        self.assertEqual(request.state, "dispatched")

    def test_create_dispatch_no_allocated_lines(self):
        """Test that dispatch fails without allocations (GAP-REQ-003)."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        self._mark_allocated(request)
        # No allocations created - should fail
        with self.assertRaises(UserError):
            request.action_create_dispatch()

    # ---------- OP#1033: partial dispatches ----------

    def _setup_allocated_request(self, requested=5000, allocated=2000):
        """Build a request in ``allocated`` state with a single-warehouse
        allocation of ``allocated`` units."""
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
        self._add_alloc(request, allocated)
        self._mark_allocated(request)
        return request

    def test_partial_dispatch_keeps_state_allocated(self):
        """OP#1033: dispatching less than requested stays at allocated."""
        request = self._setup_allocated_request(requested=5000, allocated=2000)

        request.action_create_dispatch()

        self.assertEqual(request.state, "allocated")
        self.assertEqual(request.line_ids[0].quantity_dispatched, 2000)
        self.assertEqual(request.picking_count, 1)

    def test_second_dispatch_after_top_up_advances_to_dispatched(self):
        """OP#1033: a second Create Dispatch after extra allocation
        creates a new picking and flips the state to dispatched.
        """
        request = self._setup_allocated_request(requested=5000, allocated=2000)
        request.action_create_dispatch()
        self.assertEqual(request.state, "allocated")

        # Operator allocates the remaining 3000 (same warehouse) and dispatches.
        self._add_alloc(request, 3000)
        request.action_create_dispatch()

        self.assertEqual(request.state, "dispatched")
        self.assertEqual(request.line_ids[0].quantity_dispatched, 5000)
        self.assertEqual(request.picking_count, 2)
        # Both pickings remain linked to the request.
        for picking in request.picking_ids:
            self.assertEqual(picking.drims_request_id, request)

    def test_second_dispatch_picking_only_covers_remainder(self):
        """OP#1033: the second picking moves only the newly-allocated qty."""
        request = self._setup_allocated_request(requested=5000, allocated=2000)
        request.action_create_dispatch()
        first_picking = request.picking_ids[0]
        self.assertEqual(first_picking.move_ids[0].product_uom_qty, 2000)

        self._add_alloc(request, 3000)
        request.action_create_dispatch()
        second_picking = request.picking_ids - first_picking
        self.assertEqual(len(second_picking), 1)
        self.assertEqual(second_picking.move_ids[0].product_uom_qty, 3000)

    def test_dispatch_blocked_when_nothing_remaining(self):
        """OP#1033: clicking Create Dispatch with no remainder raises."""
        request = self._setup_allocated_request(requested=5000, allocated=2000)
        request.action_create_dispatch()

        # No further allocation happened — the second call has nothing to do.
        with self.assertRaises(UserError) as cm:
            request.action_create_dispatch()
        self.assertIn("Nothing left to dispatch", str(cm.exception))


@tagged("post_install", "-at_install")
class TestDrimsRequestUIFields(DrimsTestCommon):
    """OP#1075: destination-type selector + allocation shortfall indicators."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)

    def _request(self, qty_req=50, qty_alloc=0, approval_state=None):
        req = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "priority_id": self.priority_routine.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_requested": qty_req,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        if qty_alloc:
            self._set_alloc(req, qty_alloc)
        if approval_state:
            req.approval_state = approval_state
        return req

    def _set_alloc(self, req, qty):
        """Set the request line's total allocated qty via its allocation row."""
        line = req.line_ids[0]
        alloc = line.allocation_ids[:1]
        if alloc:
            alloc.quantity_allocated = qty
        elif qty:
            req._add_allocation(line, self.warehouse, qty)

    def test_destination_type_defaults_to_warehouse(self):
        req = self._request()
        self.assertEqual(req.destination_type, "warehouse")

    def test_is_fully_allocated(self):
        # Nothing allocated yet.
        req = self._request(qty_req=50, qty_alloc=0)
        self.assertFalse(req.is_fully_allocated)
        # Partially allocated.
        self._set_alloc(req, 20)
        self.assertFalse(req.is_fully_allocated)
        # Fully allocated.
        self._set_alloc(req, 50)
        self.assertTrue(req.is_fully_allocated)

    def test_line_allocation_short_only_after_approval(self):
        # Draft with 0 allocated -> not flagged (allocation hasn't started).
        req = self._request(qty_req=50, qty_alloc=0)
        self.assertFalse(req.line_ids.is_allocation_short)
        # Approved but under-allocated -> flagged.
        req.approval_state = "approved"
        self._set_alloc(req, 20)
        self.assertTrue(req.line_ids.is_allocation_short)
        # Approved and fully allocated -> not flagged.
        self._set_alloc(req, 50)
        self.assertFalse(req.line_ids.is_allocation_short)
