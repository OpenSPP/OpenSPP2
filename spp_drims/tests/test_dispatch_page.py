# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1150: the dispatch form should put the DRIMS work where you look first.

The tab moves to second place and is renamed, "Delivery Address" gives way to
the destination location, and the destination has to actually be populated.
"""

from datetime import date, timedelta

from lxml import etree

from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsDispatchPage(DrimsTestCommon):
    """Structure of the inherited stock.picking form."""

    def setUp(self):
        super().setUp()
        self.future_date = date.today() + timedelta(days=30)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _form_arch(self):
        view = self.env["stock.picking"].get_view(self.env.ref("stock.view_picking_form").id, "form")
        return etree.fromstring(view["arch"])

    def _hidden_for(self, node, **record):
        """Evaluate a node's ``invisible`` expression against field values."""
        return bool(safe_eval(node.get("invisible", "False"), dict(record)))

    def _dispatch_with_destination(self, with_destination_warehouse=True):
        destination = self.env["stock.warehouse"].create(
            {"name": "DP Destination WH", "code": "DPD", "is_drims_warehouse": True}
        )
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": 50,
            }
        )
        vals = {
            "incident_id": self.incident.id,
            "destination_area_id": self.area.id,
            "date_needed": self.future_date,
            "source_warehouse_id": self.warehouse.id,
            "line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "quantity_requested": 50,
                        "uom_id": self.product.uom_id.id,
                    },
                )
            ],
        }
        if with_destination_warehouse:
            vals["destination_warehouse_id"] = destination.id
        request = self.env["spp.drims.request"].create(vals)
        request.action_submit()
        request.action_approve()
        request.action_allocate()
        request.action_create_dispatch()
        return request, request.picking_ids, destination

    # ------------------------------------------------------------------
    # the tab
    # ------------------------------------------------------------------

    def test_drims_tab_is_second_and_renamed(self):
        pages = self._form_arch().xpath("//notebook/page")
        labels = [(p.get("name"), p.get("string")) for p in pages]

        self.assertGreaterEqual(len(labels), 2, f"unexpected notebook layout: {labels}")
        self.assertEqual(
            labels[0][0],
            "operations",
            f"Operations should still lead the notebook, got {labels}",
        )
        self.assertEqual(
            labels[1],
            ("drims", "Dispatch & Delivery"),
            f"the DRIMS tab should sit second and be renamed, got {labels}",
        )

    def test_drims_tab_still_hidden_on_non_drims_pickings(self):
        """Renaming and moving it must not make it show up on plain transfers."""
        page = self._form_arch().xpath("//notebook/page[@name='drims']")[0]

        self.assertTrue(self._hidden_for(page, drims_type_id=False))
        self.assertFalse(self._hidden_for(page, drims_type_id=1))

    # ------------------------------------------------------------------
    # Delivery Address out, Destination Location in
    # ------------------------------------------------------------------

    def test_delivery_address_hidden_only_for_dispatches(self):
        arch = self._form_arch()
        field = arch.xpath("//field[@name='partner_id'][@nolabel='1']")[0]
        label_block = arch.xpath("//div[@class='o_td_label'][label[@for='partner_id']]")[0]

        for node, what in ((field, "field"), (label_block, "label")):
            self.assertTrue(
                self._hidden_for(node, drims_type="request_dispatch"),
                f"Delivery Address {what} should be hidden on a dispatch",
            )
            # Receipts, transfers, returns and plain stock pickings keep it.
            self.assertFalse(
                self._hidden_for(node, drims_type="donation_receipt"),
                f"Delivery Address {what} should remain on a donation receipt",
            )
            self.assertFalse(
                self._hidden_for(node, drims_type=False),
                f"Delivery Address {what} should remain on a non-DRIMS picking",
            )

    def test_destination_location_shown_only_for_dispatches(self):
        candidates = self._form_arch().xpath("//field[@name='location_dest_id'][@string='Destination Location']")
        self.assertEqual(len(candidates), 1, "expected exactly one DRIMS destination field")
        field = candidates[0]

        self.assertFalse(self._hidden_for(field, drims_type="request_dispatch"))
        self.assertTrue(self._hidden_for(field, drims_type="donation_receipt"))
        self.assertTrue(self._hidden_for(field, drims_type=False))
        self.assertEqual(field.get("readonly"), "1", "the destination is set by the request")

    # ------------------------------------------------------------------
    # "ensure that field is properly populated"
    # ------------------------------------------------------------------

    def test_destination_is_the_request_destination_warehouse(self):
        _request, picking, destination = self._dispatch_with_destination()

        self.assertEqual(picking.location_dest_id, destination.lot_stock_id)
        self.assertTrue(picking.location_dest_id.complete_name)

    def test_destination_falls_back_when_no_destination_warehouse(self):
        """Without a destination warehouse the dispatch still names a location."""
        _request, picking, _destination = self._dispatch_with_destination(with_destination_warehouse=False)

        self.assertTrue(
            picking.location_dest_id,
            "a dispatch must always have a destination location to print and display",
        )
