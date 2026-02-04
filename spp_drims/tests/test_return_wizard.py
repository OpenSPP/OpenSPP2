# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsReturnWizard(DrimsTestCommon):
    """Test cases for DRIMS Return Wizard functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Link warehouse to incident
        cls.warehouse.incident_ids = [(4, cls.incident.id)]

        # Get return condition vocabulary codes
        cls.condition_good = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:return-conditions",
                ),
                ("code", "=", "good"),
            ],
            limit=1,
        )
        cls.condition_damaged = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:return-conditions",
                ),
                ("code", "=", "damaged"),
            ],
            limit=1,
        )

        # Get drims type for dispatch
        cls.drims_type_dispatch = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:drims-types",
                ),
                ("code", "=", "request_dispatch"),
            ],
            limit=1,
        )

        # Create a stockable product for dispatch tests
        product_vals = {
            "name": "Test Stockable Relief Item",
            "type": "consu",
            "standard_price": 100.0,
        }
        if "is_storable" in cls.env["product.product"]._fields:
            product_vals["is_storable"] = True
        cls.stockable_product = cls.env["product.product"].create(product_vals)

    def _create_completed_dispatch(self):
        """Helper to create a completed dispatch picking."""
        # Get outgoing picking type
        picking_type = self.env["stock.picking.type"].search(
            [
                ("warehouse_id", "=", self.warehouse.id),
                ("code", "=", "outgoing"),
            ],
            limit=1,
        )

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "incident_id": self.incident.id,
                "drims_type_id": self.drims_type_dispatch.id,
            }
        )

        # Create stock move
        move_vals = {
            "product_id": self.stockable_product.id,
            "product_uom_qty": 50.0,
            "product_uom": self.stockable_product.uom_id.id,
            "picking_id": picking.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        }
        if "description_picking" in self.env["stock.move"]._fields:
            move_vals["description_picking"] = self.stockable_product.name
        self.env["stock.move"].create(move_vals)

        # Add stock to warehouse
        self.env["stock.quant"].create(
            {
                "product_id": self.stockable_product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 100.0,
            }
        )

        # Confirm and validate picking
        picking.action_confirm()
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        # Add required beneficiary tracking fields
        picking.beneficiary_count = 25
        picking.beneficiary_area_id = self.area.id
        picking.button_validate()

        return picking

    def test_wizard_initialization(self):
        """Test wizard opens with correct picking and lines populated."""
        dispatch = self._create_completed_dispatch()

        # Create wizard
        wizard = self.env["spp.drims.create.return.wizard"].create(
            {
                "picking_id": dispatch.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._onchange_picking_id()

        # Verify wizard is initialized correctly
        self.assertEqual(wizard.picking_id, dispatch)
        self.assertEqual(wizard.incident_id, self.incident)
        self.assertEqual(wizard.warehouse_id, self.warehouse)

        # Verify lines are populated from dispatch moves
        self.assertEqual(len(wizard.line_ids), 1)
        line = wizard.line_ids[0]
        self.assertEqual(line.product_id, self.stockable_product)
        self.assertEqual(line.quantity_dispatched, 50.0)
        self.assertEqual(line.quantity_to_return, 50.0)

    def test_partial_return_creation(self):
        """Test creating return with some items, verify only selected items appear."""
        dispatch = self._create_completed_dispatch()

        # Create wizard
        wizard = self.env["spp.drims.create.return.wizard"].create(
            {
                "picking_id": dispatch.id,
                "warehouse_id": self.warehouse.id,
                "return_reason": "Excess supplies",
                "returned_by": "Field Officer John",
            }
        )
        wizard._onchange_picking_id()

        # Set partial return quantity
        wizard.line_ids[0].quantity_to_return = 20.0
        wizard.line_ids[0].condition_id = self.condition_good.id

        # Create return
        result = wizard.action_create_return()

        # Verify return was created
        self.assertEqual(result["res_model"], "spp.drims.return")
        drims_return = self.env["spp.drims.return"].browse(result["res_id"])

        self.assertEqual(drims_return.incident_id, self.incident)
        self.assertEqual(drims_return.warehouse_id, self.warehouse)
        self.assertEqual(drims_return.return_reason, "Excess supplies")
        self.assertEqual(drims_return.returned_by, "Field Officer John")

        # Verify only selected quantity appears in return
        self.assertEqual(len(drims_return.line_ids), 1)
        return_line = drims_return.line_ids[0]
        self.assertEqual(return_line.product_id, self.stockable_product)
        self.assertEqual(return_line.quantity_dispatched, 50.0)
        self.assertEqual(return_line.quantity_returned, 20.0)
        self.assertEqual(return_line.condition_id, self.condition_good)

    def test_quantity_validation(self):
        """Test quantity > dispatched caps to dispatched, quantity < 0 caps to 0."""
        dispatch = self._create_completed_dispatch()

        wizard = self.env["spp.drims.create.return.wizard"].create(
            {
                "picking_id": dispatch.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._onchange_picking_id()

        line = wizard.line_ids[0]

        # Test quantity > dispatched gets capped
        line.quantity_to_return = 100.0
        line._onchange_quantity_to_return()
        self.assertEqual(line.quantity_to_return, 50.0)  # Should be capped to dispatched quantity

        # Test negative quantity gets capped to 0
        line.quantity_to_return = -5.0
        line._onchange_quantity_to_return()
        self.assertEqual(line.quantity_to_return, 0.0)

    def test_duplicate_return_prevention(self):
        """Test second return from same dispatch raises UserError."""
        dispatch = self._create_completed_dispatch()

        # Create first return
        wizard1 = self.env["spp.drims.create.return.wizard"].create(
            {
                "picking_id": dispatch.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard1._onchange_picking_id()
        wizard1.action_create_return()

        # Try to create second return - should fail
        wizard2 = self.env["spp.drims.create.return.wizard"].create(
            {
                "picking_id": dispatch.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard2._onchange_picking_id()

        with self.assertRaises(UserError) as context:
            wizard2.action_create_return()
        self.assertIn("already exists", str(context.exception))

    def test_empty_selection_error(self):
        """Test all quantities = 0 raises UserError."""
        dispatch = self._create_completed_dispatch()

        wizard = self.env["spp.drims.create.return.wizard"].create(
            {
                "picking_id": dispatch.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        wizard._onchange_picking_id()

        # Set all quantities to 0
        for line in wizard.line_ids:
            line.quantity_to_return = 0.0

        with self.assertRaises(UserError) as context:
            wizard.action_create_return()
        self.assertIn("at least one item", str(context.exception))
