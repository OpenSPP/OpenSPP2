# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import tagged

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
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "pending"),
            ],
            limit=1,
        )
        cls.state_allocated = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
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
