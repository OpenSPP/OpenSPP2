# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from lxml import etree

from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsDispatchStatusbar(DrimsTestCommon):
    """OP#1086: a request dispatch should not advertise states it never sits in.

    Core renders two statusbars for stock.picking, split on picking_type_code. A
    dispatch is outgoing, so it picks up the non-incoming one
    (draft,confirmed,assigned,done). spp_drims narrows that one to exclude
    dispatches and adds a dispatch-only bar, rather than editing the shared
    statusbar_visible — which would drop Draft from every non-incoming transfer.
    """

    def setUp(self):
        super().setUp()
        self.future_date = date.today() + timedelta(days=30)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _statusbars(self):
        """The state statusbar fields in the combined stock.picking form arch."""
        view = self.env["stock.picking"].get_view(self.env.ref("stock.view_picking_form").id, "form")
        tree = etree.fromstring(view["arch"])
        return tree.xpath("//header/field[@name='state'][@widget='statusbar']")

    def _stock_up(self, quantity):
        self.env["stock.quant"].create(
            {
                "product_id": self.product.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "quantity": quantity,
            }
        )

    def _allocated_request(self, requested=100):
        request = self.env["spp.drims.request"].create(
            {
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
                            "quantity_requested": requested,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        request.action_submit()
        request.action_approve()
        return request

    # ------------------------------------------------------------------
    # the statusbar arch
    # ------------------------------------------------------------------

    def test_dispatch_statusbar_shows_only_ready_and_done(self):
        """A dispatch-only statusbar exists, listing just Ready and Done."""
        bars = [b for b in self._statusbars() if b.get("statusbar_visible") == "assigned,done"]
        self.assertEqual(len(bars), 1, "expected exactly one dispatch statusbar")
        condition = bars[0].get("invisible")
        self.assertIn("drims_type != 'request_dispatch'", condition)
        self.assertIn("picking_type_code == 'incoming'", condition)

    def test_other_picking_types_keep_the_full_statusbar(self):
        """AC: no regression for receipts, returns or internal transfers.

        Core's two bars must survive untouched apart from the added exclusion, so
        anything that is not a request dispatch still shows Draft and Waiting.
        """
        by_visible = {b.get("statusbar_visible"): b for b in self._statusbars()}

        # Incoming bar: completely untouched.
        self.assertIn("draft,assigned,done", by_visible)
        self.assertEqual(by_visible["draft,assigned,done"].get("invisible"), "picking_type_code != 'incoming'")

        # Non-incoming bar: still lists Draft and Waiting, now skipped only for dispatches.
        self.assertIn("draft,confirmed,assigned,done", by_visible)
        non_incoming = by_visible["draft,confirmed,assigned,done"].get("invisible")
        self.assertIn("drims_type == 'request_dispatch'", non_incoming)

    def _visible_statusbars(self, **record):
        """statusbar_visible of every bar whose ``invisible`` is falsy for ``record``.

        The attributes are ordinary Python expressions over field values, so
        evaluate them rather than pattern-matching the strings.
        """
        visible = []
        for bar in self._statusbars():
            if not safe_eval(bar.get("invisible", "False"), dict(record)):
                visible.append(bar.get("statusbar_visible"))
        return visible

    def test_exactly_one_statusbar_applies_per_picking(self):
        """The three bars must be mutually exclusive, or the form renders two.

        Also pins the actual outcome per picking kind, which is the AC.
        """
        self.assertEqual(
            self._visible_statusbars(picking_type_code="outgoing", drims_type="request_dispatch"),
            ["assigned,done"],
            "a request dispatch should show only Ready and Done",
        )
        self.assertEqual(
            self._visible_statusbars(picking_type_code="outgoing", drims_type=False),
            ["draft,confirmed,assigned,done"],
            "a plain delivery keeps the full bar",
        )
        self.assertEqual(
            self._visible_statusbars(picking_type_code="incoming", drims_type="donation_receipt"),
            ["draft,assigned,done"],
            "a DRIMS donation receipt keeps core's incoming bar",
        )
        self.assertEqual(
            self._visible_statusbars(picking_type_code="internal", drims_type="internal_transfer"),
            ["draft,confirmed,assigned,done"],
            "a DRIMS internal transfer keeps the full bar",
        )

    # ------------------------------------------------------------------
    # the premise behind hiding those states
    # ------------------------------------------------------------------

    def test_dispatch_is_confirmed_on_creation_never_draft(self):
        """Why Draft is safe to hide: action_create_dispatch confirms immediately."""
        self._stock_up(100)
        request = self._allocated_request()
        request.line_ids[0].quantity_allocated = 100
        request.state_id = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )
        request.action_create_dispatch()

        self.assertNotEqual(request.picking_ids.state, "draft")
        self.assertIn(request.picking_ids.state, ("confirmed", "assigned"))

    def test_waiting_state_is_reachable_for_a_dispatch(self):
        """Waiting is NOT unreachable, contrary to the ticket's rationale.

        DRIMS allocation only writes ``quantity_allocated`` on the request line —
        it creates no Odoo reservation. So two requests can allocate the same
        units, and whichever dispatches second has nothing to reserve and lands
        in ``confirmed`` (Waiting). That is why Waiting is only hidden as a
        *future* step: the statusbar widget always renders the current value even
        when it is excluded from statusbar_visible, so a short dispatch still
        shows Waiting.
        """
        self._stock_up(100)
        allocated_state = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:request-states"),
                ("code", "=", "allocated"),
            ],
            limit=1,
        )
        first, second = self._allocated_request(), self._allocated_request()
        # Both allocate before either dispatches — allocation reserves nothing.
        first.action_allocate()
        second.action_allocate()
        self.assertEqual(first.line_ids[0].quantity_allocated, 100)
        self.assertEqual(second.line_ids[0].quantity_allocated, 100)

        first.state_id = allocated_state
        second.state_id = allocated_state
        first.action_create_dispatch()
        second.action_create_dispatch()

        self.assertEqual(first.picking_ids.state, "assigned")
        self.assertEqual(second.picking_ids.state, "confirmed")
