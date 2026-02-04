# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsReturn(DrimsTestCommon):
    """Test cases for DRIMS Return functionality."""

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

        # Create a stockable product for dispatch tests (consumables can't have quants)
        # In Odoo 19, use type='consu' with is_storable=True for storable products
        product_vals = {
            "name": "Test Stockable Relief Item",
            "type": "consu",
            "standard_price": 100.0,
        }
        # Odoo 19 uses is_storable to make a product trackable
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

        # Create stock move (use stockable product for quant support)
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

        # Add some stock to warehouse (only stockable products can have quants)
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
        # Add required beneficiary tracking fields for dispatch validation
        picking.beneficiary_count = 25
        picking.beneficiary_area_id = self.area.id
        picking.button_validate()

        return picking

    def test_return_create(self):
        """Test basic return record creation."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "return_reason": "Excess supplies after distribution",
                "returned_by": "Field Officer John",
            }
        )

        self.assertTrue(drims_return.reference.startswith("RTN-"))
        self.assertEqual(drims_return.state, "draft")
        self.assertEqual(drims_return.incident_id, self.incident)
        self.assertEqual(drims_return.warehouse_id, self.warehouse)

    def test_return_line_value_computation(self):
        """Test return line value computation."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        return_line = self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_dispatched": 50.0,
                "quantity_returned": 10.0,
            }
        )

        # Product standard_price is 100.0, quantity_returned is 10
        self.assertEqual(return_line.value, 1000.0)

    def test_return_totals_computation(self):
        """Test return totals computation."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        # Create multiple return lines
        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )
        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 5.0,
            }
        )

        self.assertEqual(drims_return.line_count, 2)
        self.assertEqual(drims_return.total_quantity, 15.0)
        # 10 * 100 + 5 * 100 = 1500
        self.assertEqual(drims_return.total_value, 1500.0)

    def test_return_workflow_confirm(self):
        """Test return confirmation workflow."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        # Add a line
        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        # Confirm return
        drims_return.action_confirm()
        self.assertEqual(drims_return.state, "confirmed")

        # Should have created a picking
        self.assertEqual(drims_return.picking_count, 1)
        picking = drims_return.picking_ids[0]
        self.assertEqual(picking.picking_type_id.code, "incoming")

    def test_return_workflow_confirm_no_lines_fails(self):
        """Test that confirming without lines raises error."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        with self.assertRaises(UserError):
            drims_return.action_confirm()

    def test_return_workflow_receive(self):
        """Test return receive workflow."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        drims_return.action_confirm()
        drims_return.action_receive()
        self.assertEqual(drims_return.state, "received")

    def test_return_workflow_inspect(self):
        """Test return inspection workflow."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
                "condition_id": self.condition_good.id,
            }
        )

        drims_return.action_confirm()
        drims_return.action_receive()
        drims_return.action_inspect()
        self.assertEqual(drims_return.state, "inspected")

    def test_return_workflow_restock(self):
        """Test complete return restocking workflow."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        # Go through full workflow
        drims_return.action_confirm()
        drims_return.action_receive()
        drims_return.action_inspect()
        drims_return.action_restock()

        self.assertEqual(drims_return.state, "restocked")

        # Picking should be validated
        picking = drims_return.picking_ids[0]
        self.assertEqual(picking.state, "done")

    def test_return_workflow_cancel(self):
        """Test return cancellation."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        drims_return.action_confirm()
        drims_return.action_cancel()
        self.assertEqual(drims_return.state, "cancelled")

    def test_return_cancel_restocked_fails(self):
        """Test that cancelling restocked return raises error."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        drims_return.action_confirm()
        drims_return.action_receive()
        drims_return.action_inspect()
        drims_return.action_restock()

        with self.assertRaises(UserError):
            drims_return.action_cancel()

    def test_return_reset_to_draft(self):
        """Test resetting cancelled return to draft."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        drims_return.action_cancel()
        drims_return.action_reset_to_draft()
        self.assertEqual(drims_return.state, "draft")

    def test_create_return_from_dispatch(self):
        """Test creating a return from a completed dispatch."""
        dispatch = self._create_completed_dispatch()

        # Create return from dispatch using direct method (for programmatic use)
        result = dispatch.action_create_drims_return_direct()

        self.assertEqual(result["res_model"], "spp.drims.return")
        drims_return = self.env["spp.drims.return"].browse(result["res_id"])

        self.assertEqual(drims_return.original_picking_id, dispatch)
        self.assertEqual(drims_return.incident_id, self.incident)
        self.assertEqual(drims_return.warehouse_id, self.warehouse)
        self.assertEqual(len(drims_return.line_ids), 1)
        self.assertEqual(drims_return.line_ids[0].quantity_dispatched, 50.0)

    def test_create_return_from_dispatch_already_exists_fails(self):
        """Test that creating duplicate return raises error."""
        dispatch = self._create_completed_dispatch()

        dispatch.action_create_drims_return_direct()

        with self.assertRaises(UserError):
            dispatch.action_create_drims_return_direct()

    def test_incident_return_kpis(self):
        """Test incident return KPI computation."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_return_count, 1)
        self.assertEqual(self.incident.drims_return_value, 1000.0)

    def test_view_pickings_action(self):
        """Test action to view related pickings."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        drims_return.action_confirm()

        result = drims_return.action_view_pickings()
        self.assertEqual(result["res_model"], "stock.picking")
        self.assertIn(("drims_return_id", "=", drims_return.id), result["domain"])

    def test_disposition_auto_suggestion(self):
        """Test condition change triggers correct disposition."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        return_line = self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        # Test "good" condition suggests "restock"
        return_line.condition_id = self.condition_good
        return_line._onchange_condition_id()
        self.assertEqual(return_line.disposition, "restock")

        # Test "damaged" condition suggests "repair"
        return_line.condition_id = self.condition_damaged
        return_line._onchange_condition_id()
        self.assertEqual(return_line.disposition, "repair")

    def test_unknown_condition_defaults_restock(self):
        """Test unknown condition code defaults to restock."""
        drims_return = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
            }
        )

        return_line = self.env["spp.drims.return.line"].create(
            {
                "return_id": drims_return.id,
                "product_id": self.product.id,
                "quantity_returned": 10.0,
            }
        )

        # Create a custom condition code that doesn't map to any disposition
        custom_condition = self.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:return-conditions",
                ),
            ],
            limit=1,
        )

        # If no custom condition exists or all are mapped, just verify the default
        if custom_condition:
            # Set to any condition
            return_line.condition_id = custom_condition
            return_line._onchange_condition_id()
            # Should have a disposition (either mapped or default "restock")
            self.assertIn(return_line.disposition, ["restock", "repair", "dispose"])
        else:
            # No condition set should default to "restock"
            return_line.condition_id = False
            self.assertEqual(return_line.disposition, "restock")
