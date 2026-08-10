# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

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

    def test_1164_link_warehouses_from_incident_side(self):
        """OP#1164: editing drims_warehouse_ids on the incident links/unlinks the
        warehouse both ways (via stock.warehouse.incident_ids)."""
        self.warehouse.is_drims_warehouse = True
        # Link from the incident side.
        self.incident.drims_warehouse_ids = [(4, self.warehouse.id)]
        self.assertIn(self.incident, self.warehouse.incident_ids)
        self.incident.invalidate_recordset()
        self.assertIn(self.warehouse, self.incident.drims_warehouse_ids)
        # Unlink from the incident side.
        self.incident.drims_warehouse_ids = [(3, self.warehouse.id)]
        self.assertNotIn(self.incident, self.warehouse.incident_ids)

    def test_1164_donation_allowed_warehouses_respects_filter(self):
        """OP#1164: donation warehouse choices = the incident's warehouses when
        filtering is on; all DRIMS warehouses when off."""
        self.warehouse.is_drims_warehouse = True
        other = self.env["stock.warehouse"].create(
            {"name": "Other WH 1164", "code": "O1164", "is_drims_warehouse": True}
        )
        self.incident.drims_warehouse_ids = [(6, 0, [self.warehouse.id])]
        donation = self.env["spp.drims.donation"].create(
            {"incident_id": self.incident.id, "warehouse_id": self.warehouse.id, "donor_name": "D"}
        )
        # Filter ON (default): only the incident's warehouse.
        self.assertIn(self.warehouse, donation.allowed_warehouse_ids)
        self.assertNotIn(other, donation.allowed_warehouse_ids)
        # Filter OFF: all DRIMS warehouses.
        self.env["ir.config_parameter"].sudo().set_param("drims.warehouse.filter_by_incident", "False")
        donation.invalidate_recordset(["allowed_warehouse_ids"])
        self.assertIn(other, donation.allowed_warehouse_ids)

    def test_1164_allowed_warehouses_fallback_when_incident_has_none(self):
        """OP#1164: with filtering on but no warehouses linked, fall back to all
        DRIMS warehouses (so donation/request creation isn't locked out)."""
        self.warehouse.is_drims_warehouse = True
        self.incident.drims_warehouse_ids = [(5, 0, 0)]  # ensure none linked
        donation = self.env["spp.drims.donation"].create(
            {"incident_id": self.incident.id, "warehouse_id": self.warehouse.id, "donor_name": "D"}
        )
        self.assertIn(self.warehouse, donation.allowed_warehouse_ids)

    def test_1157_flag_as_alert(self):
        """OP#1157: action_set_alert moves the incident into the Alert state."""
        self.assertNotEqual(self.incident.status, "alert")
        self.incident.action_set_alert()
        self.assertEqual(self.incident.status, "alert")

    def test_1094_stock_kpi_refreshes_on_warehouse_link(self):
        """OP#1094: linking a warehouse to an incident refreshes the stock KPI,
        even when the stock existed before the link (cache was populated with 0)."""
        wh = self.env["stock.warehouse"].create({"name": "KPI WH 1094", "code": "K1094", "is_drims_warehouse": True})
        self.product.standard_price = 25.0
        self.env["stock.quant"].create(
            {"product_id": self.product.id, "location_id": wh.lot_stock_id.id, "quantity": 100}
        )
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "KPI Incident 1094",
                "code": "KPI-1094",
                "category_id": self.hazard_category.id,
                "start_date": "2024-01-01",
                "status": "active",
            }
        )
        # Not linked yet -> stock KPI is 0 (and this stores 0).
        self.assertEqual(incident.drims_stock_value, 0.0)

        # Link the warehouse AFTER stock already exists.
        wh.write({"incident_ids": [(4, incident.id)]})
        self.env.flush_all()
        incident.invalidate_recordset()
        self.assertEqual(incident.drims_stock_value, 2500.0)  # 100 * 25

        # Unlinking refreshes back to 0.
        wh.write({"incident_ids": [(3, incident.id)]})
        self.env.flush_all()
        incident.invalidate_recordset()
        self.assertEqual(incident.drims_stock_value, 0.0)

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

    # ── OP#1160: Units/Products = incident-related stock (stocked − allocated) ──
    def _drims_type(self, code):
        return self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:drims-types"),
                ("code", "=", code),
            ],
            limit=1,
        )

    def _stock_in_receipt(self, qty):
        """Create + validate a done donation-receipt picking into the warehouse."""
        drims_type = self._drims_type("donation_receipt")
        if not drims_type:
            self.skipTest("donation_receipt vocabulary code not found")
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.in_type_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "incident_id": self.incident.id,
                "drims_type_id": drims_type.id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "product_uom": self.product.uom_id.id,
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
        )
        picking.action_confirm()
        move.quantity = qty
        picking.button_validate()
        return picking

    def _request_with_allocation(self, requested, allocated):
        return self.env["spp.drims.request"].create(
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
                            "quantity_allocated": allocated,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )

    def test_incident_units_net_of_allocation(self):
        """Units/Products = stocked-in from this incident's donations minus what
        its requests have allocated (OP#1160)."""
        self._stock_in_receipt(100)
        self._request_with_allocation(requested=100, allocated=30)
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_total_stock_units, 70.0)
        self.assertEqual(self.incident.drims_stock_item_count, 1)

    def test_incident_units_zero_when_fully_allocated(self):
        """A product fully allocated away drops out of the incident stock count."""
        self._stock_in_receipt(50)
        self._request_with_allocation(requested=50, allocated=50)
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_total_stock_units, 0.0)
        self.assertEqual(self.incident.drims_stock_item_count, 0)

    def test_incident_distributed_net_of_returns(self):
        """Distributed value is reduced by returned items (OP#1160)."""
        # Dispatch 10 @ 25 = 250 distributed (mirrors the dispatch test).
        drims_type = self._drims_type("request_dispatch")
        if not drims_type:
            self.skipTest("request_dispatch vocabulary code not found")
        self.product.standard_price = 25.0
        dispatch = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.out_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "incident_id": self.incident.id,
                "drims_type_id": drims_type.id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 10,
                "product_uom": self.product.uom_id.id,
                "picking_id": dispatch.id,
                "location_id": dispatch.location_id.id,
                "location_dest_id": dispatch.location_dest_id.id,
            }
        )
        dispatch.action_confirm()
        move.quantity = 10
        dispatch.beneficiary_count = 50
        dispatch.beneficiary_area_id = self.area.id
        dispatch.button_validate()

        # A draft return does not yet reduce distributed.
        return_rec = self.env["spp.drims.return"].create(
            {
                "incident_id": self.incident.id,
                "original_picking_id": dispatch.id,
                "warehouse_id": self.warehouse.id,
                "line_ids": [(0, 0, {"product_id": self.product.id, "quantity_returned": 4})],
            }
        )
        self.assertEqual(return_rec.total_value, 100.0)  # 4 * 25
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_distributed_value, 250.0)

        # Once the return is active, 100 of the 250 is no longer distributed.
        return_rec.state = "confirmed"
        self.incident.invalidate_recordset()
        self.assertEqual(self.incident.drims_distributed_value, 150.0)

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

    # ── OP#1157 QA round 1: header button order and Alert entry state ──

    def _incident_form_buttons(self):
        """Header action buttons of the incident form, in rendered order."""
        view = self.env["spp.hazard.incident"].get_view(self.env.ref("spp_hazard.view_hazard_incident_form").id, "form")
        tree = etree.fromstring(view["arch"])
        return [b.get("name") for b in tree.xpath("//header/button[@name]")]

    def test_flag_as_alert_is_the_leftmost_header_button(self):
        """QA asked for Flag As Alert · Start Recovery · Close Incident.

        It was inserted before the statusbar, which put it last. Anchoring it
        on the first base button puts it where the workflow starts.
        """
        buttons = self._incident_form_buttons()

        self.assertIn("action_set_alert", buttons, "Flag As Alert is missing from the header")
        self.assertEqual(
            buttons[0],
            "action_set_alert",
            f"Flag As Alert should lead the header, got {buttons}",
        )
        # The rest keep their base order behind it.
        self.assertLess(buttons.index("action_set_recovery"), buttons.index("action_close"))

    def test_close_incident_hidden_only_outside_the_open_states(self):
        """QA asked to confirm Close shows only for alert / active / recovery."""
        view = self.env["spp.hazard.incident"].get_view(self.env.ref("spp_hazard.view_hazard_incident_form").id, "form")
        tree = etree.fromstring(view["arch"])
        close = tree.xpath("//header/button[@name='action_close']")[0]
        condition = close.get("invisible")

        for status in ("alert", "active", "recovery"):
            self.assertFalse(
                safe_eval(condition, {"status": status}),
                f"Close Incident should be offered while {status}",
            )
        self.assertTrue(safe_eval(condition, {"status": "closed"}))

    def test_new_drims_incident_starts_in_alert(self):
        """The entry state, seen from DRIMS rather than the base module."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "DRIMS Fresh Incident",
                "code": "DRIMS-ALERT-1157",
                "category_id": self.hazard_category.id,
                "start_date": "2026-08-01",
            }
        )
        self.assertEqual(incident.status, "alert")

    def test_flag_as_alert_returns_an_incident_to_alert(self):
        """The button itself still does its job from active and recovery."""
        self.incident.action_set_active()
        self.incident.action_set_alert()
        self.assertEqual(self.incident.status, "alert")

        self.incident.action_set_active()
        self.incident.action_set_recovery()
        self.incident.action_set_alert()
        self.assertEqual(self.incident.status, "alert")


@tagged("post_install", "-at_install")
class TestDrimsIncidentClosedGuards(DrimsTestCommon):
    """OP#1158: limit DRIMS operations on incidents in the 'closed' state."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)
        cls.closed_incident = cls.env["spp.hazard.incident"].create(
            {
                "name": "Closed Incident 1158",
                "code": "CLOSED-1158",
                "category_id": cls.hazard_category.id,
                "start_date": "2024-01-01",
                "status": "closed",
            }
        )

    def _new_request(self, incident):
        return self.env["spp.drims.request"].create(
            {
                "incident_id": incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity_requested": 10, "uom_id": self.product.uom_id.id})
                ],
            }
        )

    # ── requests: submit / approve / allocate blocked on a closed incident ──
    def test_1158_submit_blocked_when_closed(self):
        req = self._new_request(self.closed_incident)
        with self.assertRaises(UserError):
            req.action_submit()

    def test_1158_approve_blocked_when_closed(self):
        req = self._new_request(self.closed_incident)
        with self.assertRaises(UserError):
            req.action_approve()

    def test_1158_allocate_blocked_when_closed(self):
        req = self._new_request(self.closed_incident)
        with self.assertRaises(UserError):
            req.action_allocate()

    def test_1158_submit_allowed_when_open(self):
        """Sanity: the guard does not block an open incident."""
        req = self._new_request(self.incident)  # common incident is active
        req.action_submit()  # should not raise
        self.assertIn(req.approval_state, ("pending", "submitted"))

    # ── donations: no new donations accepted on a closed incident ──
    def test_1158_donation_blocked_when_closed(self):
        with self.assertRaises(UserError):
            self.env["spp.drims.donation"].create(
                {
                    "incident_id": self.closed_incident.id,
                    "warehouse_id": self.warehouse.id,
                    "donor_name": "Closed Donor",
                    "line_ids": [
                        (0, 0, {"product_id": self.product.id, "quantity_pledged": 5, "uom_id": self.product.uom_id.id})
                    ],
                }
            )

    def test_1158_donation_allowed_when_open(self):
        donation = self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Open Donor",
                "line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity_pledged": 5, "uom_id": self.product.uom_id.id})
                ],
            }
        )
        self.assertTrue(donation.exists())

    # ── personnel: cannot deploy to a closed incident ──
    def test_1158_personnel_blocked_when_closed(self):
        with self.assertRaises(UserError):
            self.env["spp.drims.personnel"].create(
                {"name": "Closed Deployment", "incident_id": self.closed_incident.id}
            )

    def test_1158_personnel_allowed_when_open(self):
        person = self.env["spp.drims.personnel"].create({"name": "Open Deployment", "incident_id": self.incident.id})
        self.assertTrue(person.exists())
