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
        line.quantity_delivered = 50
        self.assertEqual(line.fulfillment_pct, 50.0)
        line.quantity_delivered = 100
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
        # Simulate workflow
        line.quantity_approved = 80
        line.quantity_allocated = 75
        line.quantity_dispatched = 70
        line.quantity_delivered = 70
        self.assertEqual(line.quantity_approved, 80)
        self.assertEqual(line.quantity_allocated, 75)
        self.assertEqual(line.quantity_dispatched, 70)
        self.assertEqual(line.fulfillment_pct, 70.0)

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

    def test_allocate_without_warehouse(self):
        """Test that allocation requires source warehouse (GAP-REQ-001/002)."""
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
        # No source warehouse - should fail
        with self.assertRaises(UserError):
            request.action_allocate()

    def test_allocate_with_warehouse(self):
        """Test allocation workflow with source warehouse (GAP-REQ-001/002)."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        # Now allocation should work
        request.action_allocate()
        self.assertEqual(request.state, "allocated")

    def test_create_dispatch_not_allocated(self):
        """Test that dispatch requires allocated state (GAP-REQ-003)."""
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
                "source_warehouse_id": self.warehouse.id,
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
        # Manually set allocated quantity for testing
        request.line_ids[0].quantity_allocated = 10
        # Set state to allocated
        allocated_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )
        if allocated_state:
            request.state_id = allocated_state

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

    def test_create_dispatch_no_allocated_lines(self):
        """Test that dispatch fails without allocated lines (GAP-REQ-003)."""
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
                            "quantity_requested": 10,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        # Set state to allocated but don't allocate any lines
        allocated_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )
        if allocated_state:
            request.state_id = allocated_state
        # No lines allocated - should fail
        with self.assertRaises(UserError):
            request.action_create_dispatch()
