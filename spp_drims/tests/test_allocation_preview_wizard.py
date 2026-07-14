# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import Form, tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsAllocationPreviewWizard(DrimsTestCommon):
    """Allocation Preview Wizard — per-warehouse auto-split (OP#1079)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.warehouse.incident_ids = [(4, cls.incident.id)]

        # Second DRIMS warehouse for split / alternative-stock testing.
        cls.warehouse2 = cls.env["stock.warehouse"].create(
            {
                "name": "Test DRIMS Warehouse 2",
                "code": "WH2",
                "is_drims_warehouse": True,
            }
        )
        cls.warehouse2.incident_ids = [(4, cls.incident.id)]

        cls.state_allocated = cls.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )

        cls.future_date = date.today() + timedelta(days=30)

        product_vals = {
            "name": "Test Stockable Product",
            "type": "consu",
            "standard_price": 100.0,
        }
        if "is_storable" in cls.env["product.product"]._fields:
            product_vals["is_storable"] = True
        cls.stockable_product = cls.env["product.product"].create(product_vals)

    # ── helpers ────────────────────────────────────────────────────────────
    def _create_request_with_lines(self, products_quantities):
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
        return self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "line_ids": line_vals,
            }
        )

    def _seed_stock(self, warehouse, qty, product=None):
        self.env["stock.quant"].create(
            {
                "product_id": (product or self.stockable_product).id,
                "location_id": warehouse.lot_stock_id.id,
                "quantity": qty,
            }
        )

    def _open_wizard(self, request):
        return self.env["spp.drims.allocation.preview.wizard"].create({"request_id": request.id})

    # ── auto-split proposal ──────────────────────────────────────────────────
    def test_auto_split_single_warehouse(self):
        """One warehouse holding enough stock yields a single full row."""
        self._seed_stock(self.warehouse, 100.0)
        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self._open_wizard(request)
        rows = wizard.line_ids.filtered(lambda line: line.product_id == self.stockable_product)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.warehouse_id, self.warehouse)
        self.assertEqual(rows.quantity_to_allocate, 100.0)
        self.assertEqual(wizard.total_to_allocate, 100.0)
        self.assertFalse(wizard.has_shortfall)

    def test_auto_split_across_two_warehouses(self):
        """A line of 70 with 50 @ WH1 + 20 @ WH2 splits into two rows (OP#1079)."""
        self._seed_stock(self.warehouse, 50.0)
        self._seed_stock(self.warehouse2, 20.0)
        request = self._create_request_with_lines([(self.stockable_product, 70)])

        wizard = self._open_wizard(request)
        by_wh = {row.warehouse_id: row.quantity_to_allocate for row in wizard.line_ids}
        self.assertEqual(by_wh.get(self.warehouse), 50.0)
        self.assertEqual(by_wh.get(self.warehouse2), 20.0)
        self.assertEqual(wizard.total_to_allocate, 70.0)
        self.assertFalse(wizard.has_shortfall)

    def test_shortfall_when_insufficient(self):
        """Total stock below requested is a shortfall; only available is proposed."""
        self._seed_stock(self.warehouse, 30.0)
        self._seed_stock(self.warehouse2, 20.0)
        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self._open_wizard(request)
        self.assertEqual(wizard.total_requested, 100.0)
        self.assertEqual(wizard.total_to_allocate, 50.0)
        self.assertTrue(wizard.has_shortfall)

    def test_zero_stock_no_rows(self):
        """No stock anywhere → no split rows, and confirm is rejected."""
        request = self._create_request_with_lines([(self.stockable_product, 100)])
        wizard = self._open_wizard(request)
        self.assertFalse(wizard.line_ids)
        # OP#1079 QA r2: with no stock at all, the "no stock available" flag is
        # raised (not the shortfall / partial flags), so the UI can show a
        # message that makes sense for an empty list.
        self.assertTrue(wizard.no_stock_available)
        self.assertFalse(wizard.has_shortfall)
        self.assertFalse(wizard.is_partial_allocation)
        with self.assertRaises(UserError):
            wizard.action_confirm_allocation()

    def test_partial_allocation_is_not_a_shortfall(self):
        """OP#1079 QA r2: reducing To Allocate below requested when there is
        enough stock is a deliberate partial allocation — not a stock shortfall.
        The stock-shortfall flag must stay off and key off availability."""
        self._seed_stock(self.warehouse, 100.0)
        request = self._create_request_with_lines([(self.stockable_product, 70)])

        wizard = self._open_wizard(request)
        # Auto-split proposes the full 70; stock (100) covers the request.
        self.assertEqual(wizard.total_to_allocate, 70.0)
        self.assertFalse(wizard.has_shortfall)
        self.assertFalse(wizard.is_partial_allocation)

        # User dials the allocation down to 40 — stock is still plentiful.
        wizard.line_ids[0].quantity_to_allocate = 40.0
        self.assertEqual(wizard.total_to_allocate, 40.0)
        self.assertFalse(wizard.has_shortfall, "Enough stock exists — not a shortfall")
        self.assertFalse(wizard.no_stock_available)
        self.assertTrue(wizard.is_partial_allocation, "Under-allocation should flag as partial")

    # ── confirm → allocation records ─────────────────────────────────────────
    def test_confirm_creates_allocation_records(self):
        """Confirming writes per-warehouse allocation records and updates totals."""
        self._seed_stock(self.warehouse, 100.0)
        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self._open_wizard(request)
        result = wizard.action_confirm_allocation()
        self.assertEqual(result["type"], "ir.actions.client")

        line = request.line_ids[0]
        self.assertEqual(len(line.allocation_ids), 1)
        self.assertEqual(line.allocation_ids.warehouse_id, self.warehouse)
        self.assertEqual(line.quantity_allocated, 100.0)
        if self.state_allocated:
            self.assertEqual(request.state_id, self.state_allocated)

    def test_fulfillment_reflects_allocation(self):
        """OP#1079 QA r2: the Fulfillment % tracks allocated / requested, so a
        fully-allocated line reads 100% (it no longer sits at 0 until a delivery
        quantity is entered), and a partial allocation reads pro-rata."""
        self._seed_stock(self.warehouse, 100.0)
        request = self._create_request_with_lines([(self.stockable_product, 100)])
        line = request.line_ids[0]
        self.assertEqual(line.fulfillment_pct, 0.0)

        wizard = self._open_wizard(request)
        # Allocate only 40 of 100 first → 40%.
        wizard.line_ids[0].quantity_to_allocate = 40.0
        wizard.action_confirm_allocation()
        self.assertEqual(line.quantity_allocated, 40.0)
        self.assertEqual(line.fulfillment_pct, 40.0)

        # Allocate the remaining 60 → 100%.
        wizard2 = self._open_wizard(request)
        wizard2.action_confirm_allocation()
        self.assertEqual(line.quantity_allocated, 100.0)
        self.assertEqual(line.fulfillment_pct, 100.0)

    def test_confirm_multi_warehouse_records_and_names(self):
        """A split of 50 + 20 produces two allocation records and a joined
        Source Warehouse(s) label on the request."""
        self._seed_stock(self.warehouse, 50.0)
        self._seed_stock(self.warehouse2, 20.0)
        request = self._create_request_with_lines([(self.stockable_product, 70)])

        wizard = self._open_wizard(request)
        wizard.action_confirm_allocation()

        allocations = request.line_ids.allocation_ids
        self.assertEqual(len(allocations), 2)
        self.assertEqual(request.line_ids.quantity_allocated, 70.0)
        self.assertEqual(
            request.source_warehouse_names,
            ", ".join(sorted([self.warehouse.name, self.warehouse2.name])),
        )

    def test_reallocation_subtracts_pending(self):
        """Re-opening after a partial allocation reflects that the physical
        stock is already committed — available drops to 0 (OP#1033 r2)."""
        self._seed_stock(self.warehouse, 1000.0)
        request = self._create_request_with_lines([(self.stockable_product, 5000)])

        wizard_1 = self._open_wizard(request)
        self.assertEqual(wizard_1.total_to_allocate, 1000.0)
        wizard_1.action_confirm_allocation()
        self.assertEqual(request.line_ids[0].quantity_allocated, 1000.0)

        # No dispatch happened; the 1000 physical units are still committed to
        # this request, so a re-opened wizard must not offer them again.
        wizard_2 = self._open_wizard(request)
        self.assertFalse(wizard_2.line_ids)
        self.assertEqual(wizard_2.total_to_allocate, 0.0)
        self.assertEqual(wizard_2.total_requested, 4000.0)
        with self.assertRaises(UserError):
            wizard_2.action_confirm_allocation()
        self.assertEqual(request.line_ids[0].quantity_allocated, 1000.0)

    def test_change_row_warehouse_recomputes_available(self):
        """Changing a row's warehouse refreshes availability and clamps qty."""
        self._seed_stock(self.warehouse, 40.0)
        self._seed_stock(self.warehouse2, 200.0)
        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard = self._open_wizard(request)
        row = wizard.line_ids.filtered(lambda line: line.warehouse_id == self.warehouse)[:1]
        self.assertTrue(row)
        # Point the WH1 row (40 available) at WH2 (200 available).
        row.warehouse_id = self.warehouse2
        row._onchange_warehouse_id()
        self.assertEqual(row.available_qty, 200.0)

    def test_form_driven_open_and_confirm(self):
        """Opening via Form with default_request_id auto-builds and confirms."""
        self._seed_stock(self.warehouse2, 200.0)
        request = self._create_request_with_lines([(self.stockable_product, 100)])

        wizard_form = Form(self.env["spp.drims.allocation.preview.wizard"].with_context(default_request_id=request.id))
        wizard = wizard_form.save()
        self.assertTrue(wizard.line_ids)
        self.assertEqual(wizard.line_ids[0].product_id, self.stockable_product)

        result = wizard.action_confirm_allocation()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(request.line_ids[0].quantity_allocated, 100.0)
        self.assertEqual(request.line_ids.allocation_ids.warehouse_id, self.warehouse2)
