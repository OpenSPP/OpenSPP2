# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsStock(DrimsTestCommon):
    """Tests for DRIMS Stock extensions."""

    def test_warehouse_drims_flag(self):
        """Test DRIMS warehouse configuration."""
        self.assertTrue(self.warehouse.is_drims_warehouse)

    def test_picking_waybill_generation(self):
        """Test waybill number auto-generation."""
        drims_type = self.vocab_code.search(
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

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "drims_type_id": drims_type.id,
                "incident_id": self.incident.id,
            }
        )
        self.assertTrue(picking.waybill_number)
        self.assertTrue(picking.waybill_number.startswith("WB-"))

    def test_pod_confirmation(self):
        """Test proof of delivery confirmation."""
        drims_type = self.vocab_code.search(
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

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "drims_type_id": drims_type.id,
                "pod_received_by": "Test Receiver",
            }
        )
        # OP#1088: delivery cannot be confirmed before departure is recorded.
        picking.action_confirm_departure()
        picking.action_confirm_pod()
        self.assertTrue(picking.is_pod_confirmed)
        self.assertTrue(picking.date_arrived)

    def test_stock_allocation_fefo(self):
        """Test FEFO (First Expired First Out) stock allocation."""
        # Skip if product_expiry module not installed (expiration_date not available)
        if "expiration_date" not in self.env["stock.lot"]._fields:
            self.skipTest("product_expiry module not installed")

        future_date = date.today() + timedelta(days=30)

        # Create stock with lots having different expiry dates
        lot_early = self.env["stock.lot"].create(
            {
                "name": "EARLY-EXP",
                "product_id": self.product.id,
                "expiration_date": date.today() + timedelta(days=10),
            }
        )
        lot_later = self.env["stock.lot"].create(
            {
                "name": "LATER-EXP",
                "product_id": self.product.id,
                "expiration_date": date.today() + timedelta(days=60),
            }
        )

        # Create quants (inventory)
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "lot_id": lot_early.id,
                "quantity": 50,
            }
        )
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "lot_id": lot_later.id,
                "quantity": 100,
            }
        )

        # Create and approve a request
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": future_date,
                "source_warehouse_id": self.warehouse.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_requested": 30,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )

        # Simulate approval and allocation
        request.approval_state = "approved"
        request.action_allocate()

        # Verify allocation happened
        self.assertEqual(request.line_ids[0].quantity_allocated, 30)

    def test_warehouse_incident_linking(self):
        """Test that warehouses can be linked to incidents."""
        self.warehouse.incident_ids = [(4, self.incident.id)]
        self.assertIn(self.incident, self.warehouse.incident_ids)
        self.assertIn(self.warehouse, self.incident.drims_warehouse_ids)

    def test_picking_drims_fields(self):
        """Test picking DRIMS tracking fields and move association."""
        drims_type = self.vocab_code.search(
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

        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "drims_type_id": drims_type.id,
                "incident_id": self.incident.id,
            }
        )

        # Verify picking has DRIMS fields set correctly
        self.assertEqual(picking.incident_id, self.incident)
        self.assertEqual(picking.drims_type, "request_dispatch")
        self.assertTrue(picking.waybill_number)

        # Create move with only required fields (Odoo 19 compatible)
        move_vals = {
            "product_id": self.product.id,
            "product_uom_qty": 10,
            "product_uom": self.product.uom_id.id,
            "picking_id": picking.id,
            "location_id": picking.location_id.id,
            "location_dest_id": picking.location_dest_id.id,
        }
        # Add description field based on what's available in Odoo 19
        if "description_picking" in self.env["stock.move"]._fields:
            move_vals["description_picking"] = self.product.name
        move = self.env["stock.move"].create(move_vals)

        # Move should be linked to picking
        self.assertEqual(move.picking_id, picking)
        # Move can access incident through picking
        self.assertEqual(move.picking_id.incident_id, self.incident)

    def test_warehouse_health_good_no_alerts(self):
        """Test warehouse health is 'good' when no active alerts."""
        # Ensure no alerts exist for this warehouse
        self.env["spp.drims.alert"].search(
            [
                ("warehouse_id", "=", self.warehouse.id),
            ]
        ).unlink()

        # Force recompute
        self.warehouse.invalidate_recordset()

        self.assertEqual(self.warehouse.drims_stock_health, "good")
        self.assertEqual(self.warehouse.drims_active_alert_count, 0)

    def test_warehouse_health_warning_one_alert(self):
        """Test warehouse health is 'warning' with 1-2 alerts."""
        alert_type = self.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:alert-types",
                ),
                ("code", "=", "low_stock"),
            ],
            limit=1,
        )

        if not alert_type:
            self.skipTest("Alert type not found")

        # Create one alert
        self.env["spp.drims.alert"].create(
            {
                "alert_type_id": alert_type.id,
                "title": "Test Low Stock Alert",
                "warehouse_id": self.warehouse.id,
                "incident_id": self.incident.id,
                "priority": "medium",
            }
        )

        # Force recompute
        self.warehouse.invalidate_recordset()

        self.assertEqual(self.warehouse.drims_stock_health, "warning")
        self.assertEqual(self.warehouse.drims_active_alert_count, 1)

    def test_warehouse_health_critical_many_alerts(self):
        """Test warehouse health is 'critical' with 3+ alerts."""
        alert_type = self.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:alert-types",
                ),
                ("code", "=", "low_stock"),
            ],
            limit=1,
        )

        if not alert_type:
            self.skipTest("Alert type not found")

        # Create 3 alerts
        for i in range(3):
            self.env["spp.drims.alert"].create(
                {
                    "alert_type_id": alert_type.id,
                    "title": f"Test Alert {i + 1}",
                    "warehouse_id": self.warehouse.id,
                    "incident_id": self.incident.id,
                    "priority": "high",
                }
            )

        # Force recompute
        self.warehouse.invalidate_recordset()

        self.assertEqual(self.warehouse.drims_stock_health, "critical")
        self.assertEqual(self.warehouse.drims_active_alert_count, 3)

    def test_action_view_active_alerts(self):
        """Test smart button action to view active alerts."""
        alert_type = self.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:alert-types",
                ),
                ("code", "=", "low_stock"),
            ],
            limit=1,
        )

        if not alert_type:
            self.skipTest("Alert type not found")

        # Create an alert
        self.env["spp.drims.alert"].create(
            {
                "alert_type_id": alert_type.id,
                "title": "Test Alert for Action",
                "warehouse_id": self.warehouse.id,
                "incident_id": self.incident.id,
                "priority": "medium",
            }
        )

        # Call the action
        action = self.warehouse.action_view_active_alerts()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.drims.alert")
        self.assertIn(("warehouse_id", "=", self.warehouse.id), action["domain"])
