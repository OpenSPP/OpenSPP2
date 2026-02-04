# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsIncident(DrimsTestCommon):
    """Tests for DRIMS Incident KPIs and extensions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)

    def test_incident_drims_donation_count(self):
        """Test donation count KPI on incident."""
        # Initially zero
        self.assertEqual(self.incident.drims_donation_count, 0)
        # Create donation
        self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Test Donor",
            }
        )
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_donation_count, 1)

    def test_incident_drims_donation_value(self):
        """Test donation value KPI on incident."""
        self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Test Donor",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_pledged": 100,
                            "uom_id": self.product.uom_id.id,
                            "unit_value": 50.0,
                        },
                    )
                ],
            }
        )
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_donation_value, 5000.0)

    def test_incident_drims_request_count(self):
        """Test request count KPI on incident."""
        self.assertEqual(self.incident.drims_request_count, 0)
        self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_request_count, 1)

    def test_incident_drims_pending_requests(self):
        """Test pending request count KPI on incident."""
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
        self.incident.invalidate_recordset()
        # Draft = pending in filter
        self.assertEqual(self.incident.drims_request_pending, 1)
        # Submit and approve
        request.action_submit()
        request.action_approve()
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_request_pending, 0)

    def test_incident_view_donations_action(self):
        """Test view donations action returns correct domain."""
        action = self.incident.action_view_drims_donations()
        self.assertEqual(action["res_model"], "spp.drims.donation")
        self.assertEqual(action["domain"], [("incident_id", "=", self.incident.id)])
        self.assertEqual(action["context"]["default_incident_id"], self.incident.id)

    def test_incident_view_requests_action(self):
        """Test view requests action returns correct domain."""
        action = self.incident.action_view_drims_requests()
        self.assertEqual(action["res_model"], "spp.drims.request")
        self.assertEqual(action["domain"], [("incident_id", "=", self.incident.id)])
        self.assertEqual(action["context"]["default_incident_id"], self.incident.id)

    def test_incident_multiple_donations_value(self):
        """Test multiple donations aggregate value."""
        self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Donor 1",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                            "unit_value": 100.0,
                        },
                    )
                ],
            }
        )
        self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Donor 2",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_pledged": 25,
                            "uom_id": self.product.uom_id.id,
                            "unit_value": 200.0,
                        },
                    )
                ],
            }
        )
        self.incident.invalidate_recordset()
        # 50*100 + 25*200 = 5000 + 5000 = 10000
        self.assertEqual(self.incident.drims_donation_value, 10000.0)
        self.assertEqual(self.incident.drims_donation_count, 2)

    def test_incident_drims_warehouses_computed(self):
        """Test DRIMS warehouses are computed correctly."""
        # Link warehouse to incident
        self.warehouse.incident_ids = [(4, self.incident.id)]
        self.incident.invalidate_recordset()
        self.assertIn(self.warehouse, self.incident.drims_warehouse_ids)

    def test_incident_stock_value_initially_zero(self):
        """Test stock value is zero when no warehouse linked."""
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_stock_value, 0.0)

    def test_incident_distributed_value_initially_zero(self):
        """Test distributed value is zero when no dispatches."""
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_distributed_value, 0.0)

    def test_incident_distributed_value_from_dispatch(self):
        """Test distributed value computed from completed dispatches."""
        # Get the request_dispatch vocabulary code
        drims_type = self.env["spp.vocabulary.code"].search(
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
        if not drims_type:
            self.skipTest("request_dispatch vocabulary code not found")

        # Create a picking linked to incident with drims_type
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "incident_id": self.incident.id,
                "drims_type_id": drims_type.id,
            }
        )
        # Add stock move - set product cost
        self.product.standard_price = 25.0
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 10,
                "product_uom": self.product.uom_id.id,
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
        )
        # Confirm and complete picking
        picking.action_confirm()
        move.quantity = 10
        # Add required beneficiary tracking fields for dispatch validation
        picking.beneficiary_count = 50
        picking.beneficiary_area_id = self.area.id
        picking.button_validate()

        self.incident.invalidate_recordset()
        # 10 * 25 = 250
        self.assertEqual(self.incident.drims_distributed_value, 250.0)

    def test_incident_picking_ids_relation(self):
        """Test incident has access to related pickings."""
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "incident_id": self.incident.id,
            }
        )
        self.assertIn(picking, self.incident.drims_picking_ids)
