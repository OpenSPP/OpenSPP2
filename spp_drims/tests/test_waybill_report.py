# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1151: the waybill has to survive wkhtmltopdf and say the right things.

Content is asserted against the rendered QWeb HTML, which is fast and stable.
The PDF layout itself — columns sitting side by side, the document fitting on one
page, the barcode appearing as an embedded image — was verified by rendering the
real PDF and inspecting it with pdfimages/pdftotext; that is not repeated here
because driving wkhtmltopdf in a test is slow and brittle.
"""

from datetime import date, timedelta

from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsWaybillReport(DrimsTestCommon):
    """Rendered content of the waybill, plus the embedded barcode helper."""

    def setUp(self):
        super().setUp()
        self.future_date = date.today() + timedelta(days=30)
        self.dest_warehouse = self.env["stock.warehouse"].create(
            {
                "name": "Waybill Destination WH",
                "code": "WBD",
                "is_drims_warehouse": True,
            }
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _vocab(self, namespace, code):
        return self.vocab_code.search(
            [
                ("vocabulary_id.namespace_uri", "=", f"urn:openspp:vocab:drims:{namespace}"),
                ("code", "=", code),
            ],
            limit=1,
        )

    def _dispatch(self, requested=200, shipped=180):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": requested,
            }
        )
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "destination_warehouse_id": self.dest_warehouse.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_requested": requested,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        # OP#1079: quantity_allocated is a stored compute over per-warehouse
        # allocation rows, so allocating means recording a row.
        self.env["spp.drims.request.allocation"].create(
            {
                "request_line_id": request.line_ids[0].id,
                "warehouse_id": self.warehouse.id,
                "quantity_allocated": requested,
            }
        )
        request.state_id = self._vocab("request-states", "allocated")
        request.action_create_dispatch()
        picking = request.picking_ids
        picking.write(
            {
                "beneficiary_count": 320,
                "beneficiary_area_id": self.area.id,
                "distribution_type_id": self.env["spp.vocabulary.code"]
                .search(
                    [
                        (
                            "vocabulary_id.namespace_uri",
                            "=",
                            "urn:openspp:vocab:drims:distribution-types",
                        )
                    ],
                    limit=1,
                )
                .id,
                "transport_mode_id": self._vocab("transport-modes", "road").id,
                "vehicle_registration": "ABC-1234",
                "driver_name": "Juan Dela Cruz",
                "note": "<p>NOTE_MUST_NOT_APPEAR</p>",
            }
        )
        move = picking.move_ids[0]
        move.quantity = shipped
        move.picked = True
        return request, picking

    def _render(self, picking):
        html = self.env["ir.actions.report"]._render_qweb_html("spp_drims.report_waybill", picking.ids)[0]
        return html.decode() if isinstance(html, bytes) else html

    # ------------------------------------------------------------------
    # layout: no flexbox, because wkhtmltopdf cannot render it
    # ------------------------------------------------------------------

    def test_layout_uses_no_bootstrap_grid_or_card(self):
        """Guards the reason this template is table-based.

        wkhtmltopdf 0.12 is a WebKit build with no flexbox, so Bootstrap's `row`,
        `col-*` and `card` all collapse and every column stacks — which used to
        push the signature row onto a second page. Anyone reintroducing them will
        not see the damage in the browser preview, only in the PDF, so fail here
        instead.
        """
        _request, picking = self._dispatch()
        html = self._render(picking)

        body = html.split('<div class="page">', 1)[-1]
        for banned in ('class="row', 'class="col-', 'class="card'):
            self.assertNotIn(
                banned,
                body,
                f'{banned}" reintroduced into the waybill; it will stack in the PDF',
            )

    # ------------------------------------------------------------------
    # content that had to go
    # ------------------------------------------------------------------

    def test_total_items_footer_is_gone(self):
        """It counted move lines, not quantity — 1 for a 200-unit consignment."""
        _request, picking = self._dispatch()
        self.assertNotIn("Total Items", self._render(picking))

    def test_picking_note_is_not_printed(self):
        _request, picking = self._dispatch()
        self.assertNotIn("NOTE_MUST_NOT_APPEAR", self._render(picking))

    # ------------------------------------------------------------------
    # content that had to change
    # ------------------------------------------------------------------

    def test_shipped_quantity_is_shown_alongside_demand(self):
        """The waybill accompanies the goods, so it must state what is on board."""
        _request, picking = self._dispatch(requested=200, shipped=180)
        html = self._render(picking)

        self.assertIn("Shipped", html)
        self.assertIn("Demand", html)
        self.assertIn("180.00", html, "picked quantity missing from the waybill")
        self.assertIn("200.00", html, "demand should remain for reconciliation")

    def test_destination_falls_back_to_the_location(self):
        """partner_id is normally blank on a dispatch, which left TO empty."""
        _request, picking = self._dispatch()
        self.assertFalse(picking.partner_id, "precondition: no delivery address is set")

        html = self._render(picking)

        self.assertIn("TO (Destination)", html)
        self.assertIn("Waybill Destination WH", html)
        self.assertIn(picking.location_dest_id.complete_name, html)

    def test_distribution_details_are_printed(self):
        _request, picking = self._dispatch()
        html = self._render(picking)

        self.assertIn("Distribution Area", html)
        self.assertIn(self.area.name, html)
        self.assertIn("320", html, "estimated beneficiaries missing")
        self.assertIn("Distribution Type", html)

    def test_transaction_type_is_printed(self):
        """One template serves dispatches and donation receipts; say which."""
        _request, picking = self._dispatch()
        self.assertIn(picking.drims_type_id.display, self._render(picking))

    def test_vehicle_and_driver_rows_survive_being_empty(self):
        """They are labels to write on, so the row must print regardless."""
        _request, picking = self._dispatch()
        picking.write({"vehicle_registration": False, "driver_name": False})

        html = self._render(picking)

        self.assertIn("Vehicle:", html)
        self.assertIn("Driver:", html)

    def test_request_row_shown_and_donation_row_hidden_for_a_dispatch(self):
        """Only the one that applies to this transaction type."""
        _request, picking = self._dispatch()
        html = self._render(picking)

        self.assertIn("Request:", html)
        self.assertNotIn("Donation:", html)

    # ------------------------------------------------------------------
    # barcode
    # ------------------------------------------------------------------

    def test_barcode_is_embedded_not_fetched(self):
        """Embedded so it does not depend on web.base.url being reachable.

        A relative /report/barcode/ URL requires wkhtmltopdf to fetch over HTTP
        from inside the rendering process, where web.base.url usually points at an
        external host and port that cannot be reached — the barcode then vanishes
        with no error.
        """
        _request, picking = self._dispatch()
        html = self._render(picking)

        self.assertNotIn("/report/barcode/", html, "barcode is being fetched over HTTP again")
        self.assertIn("data:image/png;base64,", html)

    def test_barcode_helper_returns_a_png_data_uri(self):
        _request, picking = self._dispatch()

        uri = picking._get_waybill_barcode_data_uri()

        self.assertTrue(uri.startswith("data:image/png;base64,"))
        self.assertGreater(len(uri), 200, "barcode payload looks empty")

    def test_barcode_helper_is_falsy_without_a_waybill_number(self):
        _request, picking = self._dispatch()
        picking.waybill_number = False

        self.assertFalse(picking._get_waybill_barcode_data_uri())

    def test_waybill_still_renders_when_the_barcode_cannot_be_built(self):
        """A missing renderPM backend must not stop a waybill printing."""
        _request, picking = self._dispatch()

        def boom(*args, **kwargs):
            raise OSError("cannot import desired renderPM backend rlPyCairo")

        self.patch(type(self.env["ir.actions.report"]), "barcode", boom)

        self.assertFalse(picking._get_waybill_barcode_data_uri())
        html = self._render(picking)
        self.assertIn("WAYBILL", html)
        self.assertIn(picking.waybill_number, html)
