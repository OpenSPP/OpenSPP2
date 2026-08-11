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
        # contains(@class, ...) rather than Odoo's hasclass(), which is an Odoo
        # XPath extension and is not available to plain lxml here.
        label_block = arch.xpath("//div[contains(@class, 'o_td_label')][label[@for='partner_id']]")[0]

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

    # ------------------------------------------------------------------
    # round 2: what a dispatch must not let you change
    # ------------------------------------------------------------------

    def _readonly_for(self, node, **record):
        """Evaluate a node's ``readonly`` expression against field values."""
        return bool(safe_eval(node.get("readonly", "False"), dict(record)))

    def _outside_list(self, arch, name):
        """The header copy of a field, ignoring the moves-list copies.

        Core declares picking_type_id and location_id in the list as well, so a
        bare //field[@name=...] is ambiguous.
        """
        nodes = [
            n for n in arch.xpath(f"//field[@name='{name}']") if not any(a.tag == "list" for a in n.iterancestors())
        ]
        self.assertEqual(len(nodes), 1, f"expected one header {name}, found {len(nodes)}")
        return nodes[0]

    def test_header_fields_are_locked_on_a_dispatch(self):
        """Operation Type, Source Location and Source Document are set by the
        request, so a dispatch must not offer them for editing (OP#1150)."""
        # Source Location only renders for multi-location users; core keeps a
        # complementary invisible copy for everyone else, so exactly one of the
        # two survives into the arch and this decides which.
        self.env.user.group_ids = [(4, self.env.ref("stock.group_stock_multi_locations").id)]
        arch = self._form_arch()

        for name in ("picking_type_id", "location_id", "origin"):
            with self.subTest(field=name):
                node = self._outside_list(arch, name)
                self.assertTrue(
                    self._readonly_for(node, state="assigned", drims_type="request_dispatch"),
                    f"{name} is still editable on a dispatch",
                )
                self.assertFalse(
                    self._readonly_for(node, state="assigned", drims_type=False),
                    f"{name} must stay editable on an ordinary transfer",
                )

    def test_source_location_lock_lands_on_the_visible_field(self):
        """Guard the xpath, not just the outcome.

        Core declares location_id three times — an invisible copy for
        single-location installs, the visible Source Location, and one in the
        moves list. An unqualified xpath takes the first, which is the invisible
        copy, and the lock would silently do nothing.
        """
        self.env.user.group_ids = [(4, self.env.ref("stock.group_stock_multi_locations").id)]
        node = self._outside_list(self._form_arch(), "location_id")

        self.assertNotEqual(node.get("invisible"), "1", "the lock landed on the hidden copy")
        self.assertIn("request_dispatch", node.get("readonly") or "")

    def test_dispatch_product_is_locked_but_quantity_is_not(self):
        """The line-up is the request's; the quantity shipped is not.

        Entering less than Demand is how a partial dispatch and its backorder
        are produced (OP#1087), so quantity has to stay editable.
        """
        arch = self._form_arch()
        moves = arch.xpath("//page[@name='operations']/field[@name='move_ids']/list")
        self.assertEqual(len(moves), 1)

        product = moves[0].xpath("./field[@name='product_id']")
        self.assertEqual(len(product), 1)
        self.assertIn(
            "parent.drims_type == 'request_dispatch'",
            product[0].get("readonly") or "",
            "the product can still be swapped on a dispatch",
        )

        for qty_field in ("quantity", "product_uom_qty"):
            for node in moves[0].xpath(f"./field[@name='{qty_field}']"):
                self.assertNotIn(
                    "drims_type",
                    node.get("readonly") or "",
                    f"{qty_field} must stay editable — short shipment drives the backorder",
                )

    def test_drims_information_is_read_only_on_a_dispatch(self):
        """Every field in that group is written by the system, not the user."""
        arch = self._form_arch()
        group = arch.xpath("//group[@name='drims_info']")
        self.assertEqual(len(group), 1)

        for name in ("drims_type_id", "waybill_number", "drims_request_id", "incident_id"):
            with self.subTest(field=name):
                nodes = group[0].xpath(f"./field[@name='{name}']")
                self.assertEqual(len(nodes), 1, f"{name} missing from DRIMS Information")
                self.assertTrue(
                    self._readonly_for(nodes[0], drims_type="request_dispatch"),
                    f"{name} is still editable on a dispatch",
                )
                self.assertFalse(
                    self._readonly_for(nodes[0], drims_type="donation_receipt"),
                    f"{name} must stay editable on a donation receipt",
                )
