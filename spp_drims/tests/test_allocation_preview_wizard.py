# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import new_test_user, tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsAllocationPreviewWizard(DrimsTestCommon):
    """Test cases for DRIMS Allocation Preview Wizard functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Link warehouse to incident
        cls.warehouse.incident_ids = [(4, cls.incident.id)]

        # Create a second warehouse for alternative stock testing
        cls.warehouse2 = cls.env["stock.warehouse"].create(
            {
                "name": "Test DRIMS Warehouse 2",
                "code": "WH2",
                "is_drims_warehouse": True,
            }
        )
        cls.warehouse2.incident_ids = [(4, cls.incident.id)]

        # Get state vocabulary codes
        cls.state_pending = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "pending"),
            ],
            limit=1,
        )
        cls.state_allocated = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )

        cls.future_date = date.today() + timedelta(days=30)

        # Create a stockable product for quant tests (consumables can't have quants in Odoo 19)
        product_vals = {
            "name": "Test Stockable Product",
            "type": "consu",
            "standard_price": 100.0,
        }
        if "is_storable" in cls.env["product.product"]._fields:
            product_vals["is_storable"] = True
        cls.stockable_product = cls.env["product.product"].create(product_vals)

        # OP#974 (#14): a Warehouse Staff user (read-only on requests) scoped to
        # the base warehouse, used to prove the allocate/dispatch workflow runs
        # for them despite the read-only request ACL.
        cls.warehouse_user = new_test_user(
            cls.env,
            login="drims_wh_dispatch_t",
            groups="base.group_user,spp_drims.group_drims_warehouse_worker",
        )
        cls.warehouse.area_id = cls.area
        cls.warehouse_user.drims_warehouse_ids = cls.warehouse

    def _create_request_with_lines(self, products_quantities):
        """Helper to create a request with specified products and quantities."""
        line_vals = []
        for product, quantity in products_quantities:
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity_requested": quantity,
                        "uom_id": product.uom_id.id,
                    },
                )
            )

        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "line_ids": line_vals,
            }
        )
        return request

    def test_wizard_initialization(self):
        """Test wizard lines populated from request lines."""
        request = self._create_request_with_lines([(self.product, 100)])

        # Create wizard
        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()

        # Verify wizard is initialized correctly
        self.assertEqual(wizard.request_id, request)
        self.assertEqual(wizard.warehouse_id, self.warehouse)

        # Verify lines are populated from request
        self.assertEqual(len(wizard.line_ids), 1)
        line = wizard.line_ids[0]
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.quantity_requested, 100.0)

    def test_insufficient_stock_detection(self):
        """Test request more than available, verify shortfall computed."""
        # Add some stock to warehouse (less than requested)
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 50.0,
            }
        )

        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()

        # Verify shortfall is detected
        line = wizard.line_ids[0]
        self.assertEqual(line.quantity_requested, 100.0)
        self.assertEqual(line.available_qty, 50.0)
        self.assertEqual(line.quantity_to_allocate, 50.0)  # Can only allocate what's available
        self.assertEqual(line.shortfall, 50.0)
        self.assertEqual(line.allocation_status, "partial")
        self.assertTrue(wizard.has_shortfall)

    def test_alternative_warehouse_discovery(self):
        """Test shortage in A, stock in B, verify B suggested."""
        # No stock in warehouse1, stock in warehouse2
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse2.lot_stock_id.id,
                "quantity": 150.0,
            }
        )

        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()

        # Verify warehouse2 is suggested as alternative
        self.assertTrue(wizard.has_shortfall)
        self.assertIn(self.warehouse2, wizard.alternative_warehouse_ids)

    def test_allocation_confirmation(self):
        """Test apply allocation, verify request updated."""
        # Add stock to warehouse
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 100.0,
            }
        )

        request = self._create_request_with_lines([(self.stockable_product, 100)])
        initial_allocated = request.line_ids[0].quantity_allocated

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()

        # Confirm allocation
        result = wizard.action_confirm_allocation()

        # Verify result is a notification
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")

        # Verify request was updated
        self.assertEqual(request.source_warehouse_id, self.warehouse)
        self.assertEqual(request.line_ids[0].quantity_allocated, initial_allocated + 100.0)

        # Verify state changed to allocated
        if self.state_allocated:
            self.assertEqual(request.state_id, self.state_allocated)

    def test_zero_stock_handling(self):
        """Test no stock available, verify allocation_status = 'none'."""
        # No stock in any warehouse
        request = self._create_request_with_lines([(self.product, 100)])

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()

        # Verify allocation status is "none"
        line = wizard.line_ids[0]
        self.assertEqual(line.available_qty, 0.0)
        self.assertEqual(line.quantity_to_allocate, 0.0)
        self.assertEqual(line.shortfall, 100.0)
        self.assertEqual(line.allocation_status, "none")

    def test_confirm_blocked_when_zero_stock(self):
        """OP#1032: action_confirm_allocation refuses to advance the
        request to allocated when the wizard's total quantity_to_allocate
        is 0. Previously the wizard would silently confirm, set
        quantity_allocated to 0 across all lines, and still advance the
        request to Ready for Dispatch.
        """
        request = self._create_request_with_lines([(self.product, 100)])
        initial_state = request.state

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()
        # No stock seeded — every line's quantity_to_allocate is 0.
        with self.assertRaises(UserError):
            wizard.action_confirm_allocation()
        self.assertEqual(request.line_ids[0].quantity_allocated, 0)
        self.assertEqual(request.state, initial_state)

    def test_partial_allocation(self):
        """Test partial allocation when stock is less than requested."""
        # Add partial stock
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 30.0,
            }
        )

        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()

        # Verify partial allocation
        line = wizard.line_ids[0]
        self.assertEqual(line.allocation_status, "partial")
        self.assertEqual(line.quantity_to_allocate, 30.0)
        self.assertEqual(line.shortfall, 70.0)

    def test_full_allocation(self):
        """Test full allocation when stock exceeds requested amount."""
        # Add more than enough stock
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 200.0,
            }
        )

        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._populate_lines()

        # Verify full allocation
        line = wizard.line_ids[0]
        self.assertEqual(line.allocation_status, "full")
        self.assertEqual(line.quantity_to_allocate, 100.0)
        self.assertEqual(line.shortfall, 0.0)
        self.assertFalse(wizard.has_shortfall)

    def test_reallocation_subtracts_already_allocated(self):
        """OP#1033 r2 regression: re-opening the allocation wizard after a
        partial allocation should subtract the pending allocation from the
        available qty — otherwise the operator can keep allocating until
        ``quantity_allocated == quantity_requested`` while physical stock
        has not moved.
        """
        # Warehouse has 1000 units; request is for 5000.
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 1000.0,
            }
        )
        request = self._create_request_with_lines([(self.stockable_product, 5000)])

        # First allocation — uses up the 1000 physical units.
        wizard_1 = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard_1._populate_lines()
        self.assertEqual(wizard_1.line_ids[0].available_qty, 1000.0)
        self.assertEqual(wizard_1.line_ids[0].quantity_to_allocate, 1000.0)
        wizard_1.action_confirm_allocation()
        self.assertEqual(request.line_ids[0].quantity_allocated, 1000.0)

        # Re-open the wizard without any dispatch happening. The shortfall
        # should remain 4000 and available should now report 0, NOT another
        # 1000 (the physical stock is still in place but it's already
        # committed to this request).
        wizard_2 = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard_2._populate_lines()
        self.assertEqual(wizard_2.line_ids[0].available_qty, 0.0)
        self.assertEqual(wizard_2.line_ids[0].quantity_to_allocate, 0.0)
        self.assertEqual(wizard_2.line_ids[0].shortfall, 4000.0)
        # Confirming with nothing to allocate must raise.
        with self.assertRaises(UserError):
            wizard_2.action_confirm_allocation()
        # request.quantity_allocated must NOT have been bumped up.
        self.assertEqual(request.line_ids[0].quantity_allocated, 1000.0)

    def test_warehouse_staff_can_allocate_and_dispatch(self):
        """OP#974 (#14): Warehouse Staff hold read-only ACL on requests/lines,
        but Allocate Stock + Create Dispatch are gated to them. The controlled
        state/quantity writes run with elevated rights, so a warehouse user can
        complete both steps without an AccessError.
        """
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 100.0,
            }
        )
        request = self._create_request_with_lines([(self.stockable_product, 100)])

        # Allocate as the warehouse user — previously raised AccessError because
        # the wizard wrote request.state_id / line.quantity_allocated directly.
        wizard = (
            self.env["spp.drims.allocation.preview.wizard"]
            .with_user(self.warehouse_user)
            .create({"request_id": request.id, "warehouse_id": self.warehouse.id})
        )
        wizard._populate_lines()
        wizard.action_confirm_allocation()

        self.assertEqual(request.line_ids[0].quantity_allocated, 100.0)
        if self.state_allocated:
            self.assertEqual(request.state_id, self.state_allocated)

        # Create the dispatch as the same warehouse user.
        request.with_user(self.warehouse_user).action_create_dispatch()
        picking = self.env["stock.picking"].search([("drims_request_id", "=", request.id)])
        self.assertTrue(picking, "warehouse staff should be able to create a dispatch picking")
        self.assertEqual(request.line_ids[0].quantity_dispatched, 100.0)

    def test_empty_allocation_error(self):
        """Test that confirming allocation with no items raises error."""
        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self.env["spp.drims.allocation.preview.wizard"].create(
            {
                "request_id": request.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        # Populate lines but then clear them to simulate empty allocation
        wizard._populate_lines()
        wizard.line_ids = [(5, 0, 0)]  # Clear all lines

        with self.assertRaises(UserError) as context:
            wizard.action_confirm_allocation()
        self.assertIn("No items to allocate", str(context.exception))
