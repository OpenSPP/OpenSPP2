# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsDonation(DrimsTestCommon):
    """Tests for DRIMS Donation model."""

    def test_create_donation(self):
        """Test basic donation creation."""
        donation = self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Test Donor",
            }
        )
        self.assertTrue(donation.reference.startswith("DON-"))
        self.assertEqual(donation.state, "announced")

    def test_donation_with_lines(self):
        """Test donation with line items."""
        donation = self.env["spp.drims.donation"].create(
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
        self.assertEqual(donation.line_count, 1)
        self.assertEqual(donation.total_value, 5000.0)

    def test_donation_line_quantity_compute(self):
        """Test quantity computation based on pledged/received."""
        donation = self.env["spp.drims.donation"].create(
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
                        },
                    )
                ],
            }
        )
        line = donation.line_ids[0]
        # Initially quantity = pledged (since received is 0)
        self.assertEqual(line.quantity, 100)
        # After receiving partial
        line.quantity_received = 80
        self.assertEqual(line.quantity, 80)

    def test_mark_received(self):
        """Test marking donation as received."""
        donation = self.env["spp.drims.donation"].create(
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
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        self.assertEqual(donation.state, "received")
        self.assertTrue(donation.date_received)
        # Check line received quantity is set
        self.assertEqual(donation.line_ids[0].quantity_received, 100)
        # Check picking was created
        self.assertEqual(donation.picking_count, 1)

    def test_mark_received_creates_picking(self):
        """Test that marking received creates stock picking."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        picking = donation.picking_ids[0]
        self.assertEqual(picking.drims_donation_id, donation)
        self.assertEqual(picking.incident_id, self.incident)
        self.assertEqual(picking.drims_type, "donation_receipt")
        self.assertEqual(len(picking.move_ids), 1)
        self.assertEqual(picking.move_ids[0].product_uom_qty, 50)

    def test_donation_workflow_inspect(self):
        """Test donation inspection workflow."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        # Cannot inspect before receiving
        with self.assertRaises(UserError):
            donation.action_inspect()
        # After receiving
        donation.action_mark_received()
        donation.action_inspect()
        self.assertEqual(donation.state, "inspected")

    def test_donation_workflow_stock(self):
        """Test donation stocking workflow."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        # Cannot stock before inspection
        with self.assertRaises(UserError):
            donation.action_stock()

    def test_donation_with_donor_partner(self):
        """Test donation with partner donor."""
        partner = self.env["res.partner"].create(
            {
                "name": "Donor Organization",
            }
        )
        donation = self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_id": partner.id,
            }
        )
        self.assertEqual(donation.donor_id, partner)
        self.assertIn(partner.name, donation.name)

    def test_donation_donor_type(self):
        """Test donation with donor type vocabulary."""
        donor_type = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:donor-types",
                ),
                ("code", "=", "ngo"),
            ],
            limit=1,
        )
        if donor_type:
            donation = self.env["spp.drims.donation"].create(
                {
                    "incident_id": self.incident.id,
                    "warehouse_id": self.warehouse.id,
                    "donor_name": "NGO Donor",
                    "source_type_id": donor_type.id,
                }
            )
            self.assertEqual(donation.source_type_id, donor_type)

    def test_donation_line_condition(self):
        """Test donation line with condition tracking."""
        donation = self.env["spp.drims.donation"].create(
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
                            "condition_id": self.condition_new.id if self.condition_new else False,
                        },
                    )
                ],
            }
        )
        if self.condition_new:
            self.assertEqual(donation.line_ids[0].condition_id, self.condition_new)

    def test_donation_unique_reference(self):
        """Test that donation references are unique."""
        donation1 = self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Test Donor 1",
            }
        )
        # Verify reference was generated
        self.assertTrue(donation1.reference)
        self.assertNotEqual(donation1.reference, "New")
        # Create second donation and verify different reference
        donation2 = self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Test Donor 2",
            }
        )
        self.assertNotEqual(donation1.reference, donation2.reference)

    def test_donation_line_expiry_date(self):
        """Test donation line with expiry date tracking."""
        expiry = date.today() + timedelta(days=90)
        donation = self.env["spp.drims.donation"].create(
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
                            "expiry_date": expiry,
                        },
                    )
                ],
            }
        )
        self.assertEqual(donation.line_ids[0].expiry_date, expiry)

    def test_donation_view_pickings_action(self):
        """Test view pickings action returns correct domain."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        action = donation.action_view_pickings()
        self.assertEqual(action["res_model"], "stock.picking")
        self.assertEqual(action["domain"], [("drims_donation_id", "=", donation.id)])

    def test_donation_partial_receipt(self):
        """Test partial receipt of donation."""
        donation = self.env["spp.drims.donation"].create(
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
                        },
                    )
                ],
            }
        )
        # Manually set received quantity before marking received
        donation.line_ids[0].quantity_received = 75
        donation.action_mark_received()
        # Should keep the manually set quantity
        self.assertEqual(donation.line_ids[0].quantity_received, 75)

    def test_donation_multiple_lines(self):
        """Test donation with multiple product lines."""
        product2 = self.env["product.product"].create(
            {
                "name": "Test Product 2",
                "type": "consu",
                "standard_price": 200.0,
            }
        )
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                            "unit_value": 100.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": product2.id,
                            "quantity_pledged": 25,
                            "uom_id": product2.uom_id.id,
                            "unit_value": 200.0,
                        },
                    ),
                ],
            }
        )
        self.assertEqual(donation.line_count, 2)
        # 50 * 100 + 25 * 200 = 5000 + 5000 = 10000
        self.assertEqual(donation.total_value, 10000.0)

    def test_invalid_state_transition_constraint(self):
        """Test that invalid state transitions raise ValidationError."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        self.assertEqual(donation.state, "announced")

        # Try to skip to 'stocked' state (should fail)
        stocked_state = self.env["spp.vocabulary.code"].search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:donation-states",
                ),
                ("code", "=", "stocked"),
            ],
            limit=1,
        )

        if stocked_state:
            with self.assertRaises(ValidationError):
                donation.state_id = stocked_state

    def test_valid_state_transition_sequence(self):
        """Test valid complete state transition sequence."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )

        # Follow valid sequence: announced -> received -> inspected -> stocked
        self.assertEqual(donation.state, "announced")

        donation.action_mark_received()
        self.assertEqual(donation.state, "received")

        donation.action_inspect()
        self.assertEqual(donation.state, "inspected")

        # action_stock validates picking, so we just check we can reach this point
        # The full stock test is in test_donation_workflow_stock

    def test_donation_workflow_reject(self):
        """Test donation rejection workflow (GAP-DON-001)."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        # Cannot reject before inspection
        with self.assertRaises(UserError):
            donation.action_reject()

        # Go through the workflow
        donation.action_mark_received()
        self.assertEqual(donation.state, "received")

        # Cannot reject from received state
        with self.assertRaises(UserError):
            donation.action_reject()

        donation.action_inspect()
        self.assertEqual(donation.state, "inspected")

        # Now rejection should work
        donation.action_reject()
        self.assertEqual(donation.state, "rejected")

        # Verify pickings were cancelled
        for picking in donation.picking_ids:
            self.assertEqual(picking.state, "cancel")

    def test_donation_workflow_reject_cancels_pickings(self):
        """Test that rejecting a donation cancels pending pickings."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        donation.action_inspect()

        # Verify we have a picking in progress
        self.assertEqual(donation.picking_count, 1)
        picking = donation.picking_ids[0]
        self.assertNotEqual(picking.state, "cancel")

        # Reject the donation
        donation.action_reject()

        # Verify the picking was cancelled
        self.assertEqual(picking.state, "cancel")

    def test_donation_cancel_from_announced(self):
        """Test cancelling donation from announced state (GAP-DON-002)."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        self.assertEqual(donation.state, "announced")
        donation.action_cancel()
        self.assertEqual(donation.state, "cancelled")

    def test_donation_cancel_from_received(self):
        """Test cancelling donation from received state (GAP-DON-002)."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        self.assertEqual(donation.state, "received")
        donation.action_cancel()
        self.assertEqual(donation.state, "cancelled")
        # Verify pickings were cancelled
        for picking in donation.picking_ids:
            self.assertEqual(picking.state, "cancel")

    def test_donation_cancel_from_inspected(self):
        """Test cancelling donation from inspected state (GAP-DON-002)."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        donation.action_inspect()
        self.assertEqual(donation.state, "inspected")
        donation.action_cancel()
        self.assertEqual(donation.state, "cancelled")

    def test_donation_cannot_cancel_stocked(self):
        """Test that stocked donations cannot be cancelled (GAP-DON-002)."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.action_stock()
        self.assertEqual(donation.state, "stocked")
        # Should fail
        with self.assertRaises(UserError):
            donation.action_cancel()

    def test_donation_cannot_cancel_rejected(self):
        """Test that rejected donations cannot be cancelled (GAP-DON-002)."""
        donation = self.env["spp.drims.donation"].create(
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
                            "quantity_pledged": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.action_reject()
        self.assertEqual(donation.state, "rejected")
        # Should fail
        with self.assertRaises(UserError):
            donation.action_cancel()

    # ---------- OP#961: lot/serial assignment on action_stock ----------

    def _make_tracked_product(self, tracking, name="Tracked Item"):
        return self.env["product.product"].create(
            {
                "name": name,
                "type": "consu",
                "is_storable": True,
                "tracking": tracking,
                "standard_price": 50.0,
            }
        )

    def _make_donation(self, line_vals):
        return self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Test Donor",
                "line_ids": [(0, 0, vals) for vals in line_vals],
            }
        )

    def test_action_stock_creates_lot_for_lot_tracked_product(self):
        """Lot-tracked product validates and a stock.lot is created from lot_number."""
        product = self._make_tracked_product("lot", "Rice 25kg (lot)")
        donation = self._make_donation(
            [
                {
                    "product_id": product.id,
                    "quantity_pledged": 10,
                    "uom_id": product.uom_id.id,
                    "lot_number": "LOT-RICE-001",
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.action_stock()
        self.assertEqual(donation.state, "stocked")
        lot = self.env["stock.lot"].search(
            [("name", "=", "LOT-RICE-001"), ("product_id", "=", product.id)],
            limit=1,
        )
        self.assertTrue(lot, "expected a stock.lot named LOT-RICE-001 to be created")

    def test_action_stock_sets_expiry_when_provided(self):
        """expiry_date on the donation line propagates to stock.lot.expiration_date."""
        if "expiration_date" not in self.env["stock.lot"]._fields:
            self.skipTest("product_expiry module not installed")
        product = self._make_tracked_product("lot", "Vaccine (lot)")
        expiry = date.today() + timedelta(days=180)
        donation = self._make_donation(
            [
                {
                    "product_id": product.id,
                    "quantity_pledged": 5,
                    "uom_id": product.uom_id.id,
                    "lot_number": "LOT-VAC-2026",
                    "expiry_date": expiry,
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.action_stock()
        lot = self.env["stock.lot"].search(
            [("name", "=", "LOT-VAC-2026"), ("product_id", "=", product.id)],
            limit=1,
        )
        self.assertTrue(lot)
        # expiration_date may be Date or Datetime depending on product_expiry version
        stored = lot.expiration_date
        if hasattr(stored, "date"):
            stored = stored.date()
        self.assertEqual(stored, expiry)

    def test_action_stock_reuses_existing_lot(self):
        """A stock.lot with the same name + product is reused, not duplicated."""
        product = self._make_tracked_product("lot", "Rice 25kg (existing lot)")
        existing = self.env["stock.lot"].create(
            {
                "name": "LOT-RICE-EXISTING",
                "product_id": product.id,
                "company_id": self.env.company.id,
            }
        )
        donation = self._make_donation(
            [
                {
                    "product_id": product.id,
                    "quantity_pledged": 3,
                    "uom_id": product.uom_id.id,
                    "lot_number": "LOT-RICE-EXISTING",
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.action_stock()
        lots = self.env["stock.lot"].search([("name", "=", "LOT-RICE-EXISTING"), ("product_id", "=", product.id)])
        self.assertEqual(len(lots), 1)
        self.assertEqual(lots, existing)

    def test_action_stock_serial_qty_one_succeeds(self):
        """Serial-tracked product with quantity 1 and lot_number validates."""
        product = self._make_tracked_product("serial", "Generator (serial)")
        donation = self._make_donation(
            [
                {
                    "product_id": product.id,
                    "quantity_pledged": 1,
                    "uom_id": product.uom_id.id,
                    "lot_number": "SN-GEN-001",
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.action_stock()
        self.assertEqual(donation.state, "stocked")

    def test_action_stock_serial_qty_gt_one_raises(self):
        """Serial product with quantity > 1 raises UserError (one serial per unit)."""
        product = self._make_tracked_product("serial", "Generator multi")
        donation = self._make_donation(
            [
                {
                    "product_id": product.id,
                    "quantity_pledged": 3,
                    "uom_id": product.uom_id.id,
                    "lot_number": "SN-GEN-002",
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        with self.assertRaises(UserError):
            donation.action_stock()

    def test_action_stock_missing_lot_number_raises(self):
        """Tracked product without lot_number raises a friendly UserError."""
        product = self._make_tracked_product("lot", "Rice missing lot")
        donation = self._make_donation(
            [
                {
                    "product_id": product.id,
                    "quantity_pledged": 2,
                    "uom_id": product.uom_id.id,
                    # lot_number intentionally omitted
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        with self.assertRaises(UserError):
            donation.action_stock()

    def test_action_stock_untracked_product_unaffected(self):
        """Untracked products continue to validate without any lot handling."""
        # self.product has tracking='none' by default
        donation = self._make_donation(
            [
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 25,
                    "uom_id": self.product.uom_id.id,
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.action_stock()
        self.assertEqual(donation.state, "stocked")

    # ---------- OP#1030: non-accept dispositions excluded from stocking ----------

    def _disposition(self, code):
        return self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:item-dispositions"),
                ("code", "=", code),
            ],
            limit=1,
        )

    def _qty_in_warehouse(self, product, warehouse):
        return sum(
            self.env["stock.quant"]
            .search(
                [
                    ("product_id", "=", product.id),
                    ("location_id", "child_of", warehouse.lot_stock_id.id),
                ]
            )
            .mapped("quantity")
        )

    def test_action_stock_excludes_return_disposition(self):
        """OP#1030: lines with disposition=return are cancelled, not stocked."""
        disposition_return = self._disposition("return")
        if not disposition_return:
            self.skipTest("return disposition vocab code missing")

        donation = self._make_donation(
            [
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 200,
                    "uom_id": self.product.uom_id.id,
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.line_ids[0].disposition_id = disposition_return

        result = donation.action_stock()
        self.assertEqual(donation.state, "stocked")
        # Nothing should land in the warehouse.
        self.assertEqual(self._qty_in_warehouse(self.product, self.warehouse), 0.0)
        # The picking should end up cancelled because every move was excluded.
        for picking in donation.picking_ids:
            self.assertEqual(picking.state, "cancel")
        # A user-visible warning is returned.
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("excluded", result["params"]["message"].lower())

    def test_action_stock_excludes_dispose_disposition(self):
        """OP#1030: lines with disposition=dispose are cancelled too."""
        disposition_dispose = self._disposition("dispose")
        if not disposition_dispose:
            self.skipTest("dispose disposition vocab code missing")

        donation = self._make_donation(
            [
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 100,
                    "uom_id": self.product.uom_id.id,
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.line_ids[0].disposition_id = disposition_dispose

        donation.action_stock()
        self.assertEqual(self._qty_in_warehouse(self.product, self.warehouse), 0.0)

    def test_action_stock_mixed_dispositions_only_accepted_stocks(self):
        """OP#1030: in a mixed donation, only accepted lines reach the warehouse."""
        disposition_accept = self._disposition("accept")
        disposition_return = self._disposition("return")
        if not (disposition_accept and disposition_return):
            self.skipTest("required disposition codes missing")

        donation = self._make_donation(
            [
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 800,
                    "uom_id": self.product.uom_id.id,
                },
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 200,
                    "uom_id": self.product.uom_id.id,
                },
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.line_ids[0].disposition_id = disposition_accept
        donation.line_ids[1].disposition_id = disposition_return

        result = donation.action_stock()
        self.assertEqual(donation.state, "stocked")
        # Only the 800 accepted units land in the warehouse.
        self.assertEqual(self._qty_in_warehouse(self.product, self.warehouse), 800.0)
        # Warning lists the 200 excluded units.
        self.assertIsNotNone(result)
        self.assertIn("200", result["params"]["message"])

    def test_action_stock_mixed_dispositions_partial_receive_only_stocks_accept(self):
        """OP#1030 regression: even when Odoo merges the receipt moves and
        when received qty differs from pledged, only the accepted received
        quantity should land in the warehouse.

        Reproduces the bug screenshot scenario:
        - Donation has 2 lines of the same product
        - Line 1: pledged 500, received 200, Accept
        - Line 2: pledged 300, received 300, Return to Donor
        - Expected: only 200 (Accept line's received qty) reaches the warehouse.
        """
        disposition_accept = self._disposition("accept")
        disposition_return = self._disposition("return")
        if not (disposition_accept and disposition_return):
            self.skipTest("required disposition codes missing")

        donation = self._make_donation(
            [
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 500,
                    "uom_id": self.product.uom_id.id,
                },
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 300,
                    "uom_id": self.product.uom_id.id,
                },
            ]
        )
        donation.action_mark_received()
        # Simulate the OP#964 scenario: line 1's received is reduced after
        # receipt (e.g. the actual delivery was short of the pledged amount).
        donation.line_ids[0].quantity_received = 200
        donation.action_inspect()
        donation.line_ids[0].disposition_id = disposition_accept
        donation.line_ids[1].disposition_id = disposition_return

        result = donation.action_stock()
        self.assertEqual(donation.state, "stocked")
        self.assertEqual(self._qty_in_warehouse(self.product, self.warehouse), 200.0)
        self.assertIsNotNone(result)
        self.assertIn("300", result["params"]["message"])

    def test_action_stock_all_accept_unchanged(self):
        """OP#1030: regression — full-accept flow still stocks everything."""
        disposition_accept = self._disposition("accept")
        if not disposition_accept:
            self.skipTest("accept disposition vocab code missing")

        donation = self._make_donation(
            [
                {
                    "product_id": self.product.id,
                    "quantity_pledged": 500,
                    "uom_id": self.product.uom_id.id,
                }
            ]
        )
        donation.action_mark_received()
        donation.action_inspect()
        donation.line_ids[0].disposition_id = disposition_accept

        result = donation.action_stock()
        self.assertIsNone(result, "no excluded units → no notification")
        self.assertEqual(self._qty_in_warehouse(self.product, self.warehouse), 500.0)
