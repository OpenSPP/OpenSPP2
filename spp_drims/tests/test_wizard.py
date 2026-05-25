# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsWizard(DrimsTestCommon):
    """Tests for DRIMS Wizard models."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)

    def _create_pending_request(self):
        """Helper to create a pending request."""
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
        request.action_submit()
        return request

    def test_bulk_approve_wizard_summary(self):
        """Test bulk approve wizard summary computation."""
        request1 = self._create_pending_request()
        request2 = self._create_pending_request()
        wizard = self.env["spp.drims.bulk.approve.wizard"].create(
            {
                "request_ids": [(6, 0, [request1.id, request2.id])],
            }
        )
        self.assertEqual(wizard.request_count, 2)
        self.assertEqual(wizard.total_value, request1.total_value + request2.total_value)
        self.assertTrue(wizard.summary)  # HTML summary generated

    def test_bulk_approve_action(self):
        """Test bulk approval action."""
        request1 = self._create_pending_request()
        request2 = self._create_pending_request()
        wizard = self.env["spp.drims.bulk.approve.wizard"].create(
            {
                "request_ids": [(6, 0, [request1.id, request2.id])],
            }
        )
        result = wizard.action_approve()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        # Verify requests were approved
        self.assertEqual(request1.approval_state, "approved")
        self.assertEqual(request2.approval_state, "approved")

    def test_bulk_approve_no_requests(self):
        """Test bulk approve with no requests raises error."""
        wizard = self.env["spp.drims.bulk.approve.wizard"].create(
            {
                "request_ids": [(6, 0, [])],
            }
        )
        with self.assertRaises(UserError):
            wizard.action_approve()

    def test_bulk_approve_skips_non_pending(self):
        """Test bulk approve skips already approved requests."""
        request = self._create_pending_request()
        request.action_approve()  # Pre-approve
        wizard = self.env["spp.drims.bulk.approve.wizard"].create(
            {
                "request_ids": [(6, 0, [request.id])],
            }
        )
        # Should complete without error but approve 0 requests
        result = wizard.action_approve()
        self.assertIn("0 requests", result["params"]["message"])

    def test_bulk_reject_wizard(self):
        """Test bulk reject wizard."""
        request1 = self._create_pending_request()
        request2 = self._create_pending_request()
        wizard = self.env["spp.drims.bulk.reject.wizard"].create(
            {
                "request_ids": [(6, 0, [request1.id, request2.id])],
                "reason": "Budget constraints",
            }
        )
        result = wizard.action_reject()
        self.assertEqual(result["type"], "ir.actions.client")
        # Verify requests were rejected
        self.assertEqual(request1.approval_state, "rejected")
        self.assertEqual(request2.approval_state, "rejected")
        self.assertEqual(request1.rejection_reason, "Budget constraints")

    def test_bulk_reject_requires_reason(self):
        """Test bulk reject requires rejection reason."""
        request = self._create_pending_request()
        wizard = self.env["spp.drims.bulk.reject.wizard"].create(
            {
                "request_ids": [(6, 0, [request.id])],
                "reason": "",  # Empty reason
            }
        )
        with self.assertRaises(UserError):
            wizard.action_reject()

    def test_bulk_approve_to_reject_flow(self):
        """Test flow from approve wizard to reject wizard."""
        request = self._create_pending_request()
        approve_wizard = self.env["spp.drims.bulk.approve.wizard"].create(
            {
                "request_ids": [(6, 0, [request.id])],
            }
        )
        action = approve_wizard.action_reject()
        self.assertEqual(action["res_model"], "spp.drims.bulk.reject.wizard")
        self.assertEqual(action["target"], "new")
        self.assertIn("default_request_ids", action["context"])

    # ---------- OP#966: single-record reject wizard ----------

    def test_action_open_reject_wizard_returns_act_window(self):
        """OP#966: action_open_reject_wizard returns the wizard action."""
        request = self._create_pending_request()
        action = request.action_open_reject_wizard()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.drims.request.reject.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_request_id"], request.id)

    def test_action_open_reject_wizard_only_pending(self):
        """OP#966: opening the wizard on a non-pending request raises."""
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
        # Still in draft, never submitted
        with self.assertRaises(UserError):
            request.action_open_reject_wizard()

    def test_request_reject_wizard_writes_reason_and_rejects(self):
        """OP#966: the wizard writes rejection_reason and rejects the request."""
        request = self._create_pending_request()
        wizard = self.env["spp.drims.request.reject.wizard"].create(
            {
                "request_id": request.id,
                "reason": "Out of scope for this funding cycle",
            }
        )
        wizard.action_reject()
        self.assertEqual(request.approval_state, "rejected")
        self.assertEqual(request.rejection_reason, "Out of scope for this funding cycle")

    def test_request_reject_wizard_blank_reason_raises(self):
        """OP#966: whitespace-only reason raises UserError."""
        request = self._create_pending_request()
        wizard = self.env["spp.drims.request.reject.wizard"].create(
            {
                "request_id": request.id,
                "reason": "   ",
            }
        )
        with self.assertRaises(UserError):
            wizard.action_reject()
        # Request stays pending
        self.assertEqual(request.approval_state, "pending")


@tagged("post_install", "-at_install")
class TestInspectionWizard(DrimsTestCommon):
    """Tests for DRIMS Inspection Wizard (Batch Accept with Exceptions design)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Get vocabulary codes for inspection
        cls.state_received = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:donation-states",
                ),
                ("code", "=", "received"),
            ],
            limit=1,
        )
        cls.condition_new = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:item-conditions",
                ),
                ("code", "=", "new"),
            ],
            limit=1,
        )
        cls.condition_damaged = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:item-conditions",
                ),
                ("code", "=", "damaged"),
            ],
            limit=1,
        )
        cls.disposition_accept = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:item-dispositions",
                ),
                ("code", "=", "accept"),
            ],
            limit=1,
        )
        cls.disposition_return = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:item-dispositions",
                ),
                ("code", "=", "return"),
            ],
            limit=1,
        )

    def _create_received_donation(self, quantity=100):
        """Helper to create a received donation."""
        donation = self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_pledged": quantity,
                            "uom_id": self.product.uom_id.id,
                        },
                    )
                ],
            }
        )
        donation.action_mark_received()
        return donation

    def _open_inspection_wizard(self, donation):
        """Helper to open inspection wizard using the new pattern."""
        action = donation.action_open_inspection_wizard()
        wizard_id = action["res_id"]
        return self.env["spp.drims.inspection.wizard"].browse(wizard_id)

    def _set_inspection(self, line, condition=None, disposition=None):
        """Helper: write Condition + Action; ``is_inspected`` is computed."""
        vals = {}
        if condition is not None:
            vals["condition_id"] = condition.id
        if disposition is not None:
            vals["disposition_id"] = disposition.id
        line.write(vals)

    def test_inspection_wizard_no_pre_fill(self):
        """OP#963: wizard lines open blank — operator must set both fields."""
        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)

        self.assertEqual(len(wizard.line_ids), 1)
        line = wizard.line_ids[0]
        self.assertFalse(line.condition_id)
        self.assertFalse(line.disposition_id)
        self.assertFalse(line.is_inspected)
        with self.assertRaises(UserError):
            wizard.action_confirm_inspection()

    def test_is_inspected_tracks_both_fields(self):
        """OP#963: is_inspected is True only when both Condition and Action are set."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=100)
        wizard = self._open_inspection_wizard(donation)
        line = wizard.line_ids[0]

        line.condition_id = self.condition_new
        self.assertFalse(line.is_inspected, "needs both fields")

        line.disposition_id = self.disposition_accept
        self.assertTrue(line.is_inspected)

    def test_can_mark_all_units_toggles_with_both_fields(self):
        """OP#963: badge enable/disable mirrors condition+action presence."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=100)
        wizard = self._open_inspection_wizard(donation)
        line = wizard.line_ids[0]

        self.assertFalse(line.can_mark_all_units)
        line.condition_id = self.condition_new
        self.assertFalse(line.can_mark_all_units)
        line.disposition_id = self.disposition_accept
        self.assertTrue(line.can_mark_all_units)

    def test_inspection_confirm_full_acceptance(self):
        """OP#963: filling Condition + Action on every row makes the wizard
        valid and confirming writes the chosen values to the donation lines.
        """
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        line = wizard.line_ids[0]

        self._set_inspection(line, self.condition_new, self.disposition_accept)

        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")
        self.assertEqual(donation.line_ids[0].condition_id, self.condition_new)
        self.assertEqual(donation.line_ids[0].disposition_id, self.disposition_accept)

    def test_inspection_wizard_validation_uninspected(self):
        """Confirm refuses to advance when any row is missing its decision."""
        donation = self._create_received_donation(quantity=100)
        wizard = self._open_inspection_wizard(donation)

        with self.assertRaises(UserError) as cm:
            wizard.action_confirm_inspection()
        self.assertIn("inspect all items", str(cm.exception))

    def test_inspection_wizard_single_line_quantity_overrides_received(self):
        """OP#964: a single inspection line is treated as the user reporting
        the final received quantity.
        """
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        line = wizard.line_ids[0]
        self._set_inspection(line, self.condition_new, self.disposition_accept)
        line.quantity = 800

        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")
        self.assertEqual(donation.line_ids[0].quantity_received, 800)

    def test_inspection_wizard_split_mismatch_still_raises(self):
        """OP#964: split quantities must still sum to expected."""
        if not self.condition_new or not self.condition_damaged:
            self.skipTest("Required vocabulary codes not found")
        if not self.disposition_accept or not self.disposition_return:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        # Create a split via the real button so parent/child wiring is correct.
        parent.action_add_split()
        children = wizard.line_ids.filtered("is_split")
        self.assertEqual(len(children), 1)
        child_a = children[0]

        # Deliberately make the totals not match expected.
        child_a.quantity = 800
        InspectionLine = self.env["spp.drims.inspection.wizard.line"]
        child_b = InspectionLine.create(
            {
                "wizard_id": wizard.id,
                "donation_line_id": parent.donation_line_id.id,
                "product_id": parent.product_id.id,
                "uom_id": parent.uom_id.id,
                "quantity_expected": parent.quantity_expected,
                "quantity": 150,  # 800 + 150 = 950 ≠ 1000
                "parent_line_id": parent.id,
            }
        )
        self._set_inspection(child_a, self.condition_new, self.disposition_accept)
        self._set_inspection(child_b, self.condition_damaged, self.disposition_return)

        with self.assertRaises(UserError) as cm:
            wizard.action_confirm_inspection()
        self.assertIn("Splits must sum", str(cm.exception))

    def test_inspection_wizard_quantity_received_zero_uses_pledged(self):
        """OP#964: fall back to quantity_pledged when quantity_received is 0."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=500)
        donation.line_ids[0].quantity_received = 0

        wizard = self._open_inspection_wizard(donation)
        line = wizard.line_ids[0]
        self.assertEqual(line.quantity_expected, 500)

        self._set_inspection(line, self.condition_new, self.disposition_accept)

        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")
        self.assertEqual(donation.line_ids[0].quantity_received, 500)

    def test_inspection_wizard_only_received_donations(self):
        """Test that only received donations can be inspected."""
        donation = self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
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
        with self.assertRaises(UserError):
            donation.action_open_inspection_wizard()

    def test_add_split_creates_child_line(self):
        """OP#963: action_add_split creates a child with parent_line_id set
        and resets the parent qty to mirror the children."""
        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        parent.action_add_split()
        self.assertEqual(len(wizard.line_ids), 2)

        children = wizard.line_ids.filtered("is_split")
        self.assertEqual(len(children), 1)
        child = children[0]
        self.assertEqual(child.parent_line_id, parent)
        # First child gets the full remaining (= expected on first split).
        self.assertEqual(child.quantity, 1000)
        # Parent qty mirrors the child running total.
        self.assertEqual(parent.quantity, 1000)
        self.assertTrue(parent.has_splits)

    def test_add_split_remaining_quantity(self):
        """OP#963: subsequent splits get expected - already-allocated."""
        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        parent.action_add_split()
        children = wizard.line_ids.filtered("is_split")
        children[0].quantity = 700  # leaves 300 remaining

        parent.action_add_split()
        children = wizard.line_ids.filtered("is_split")
        self.assertEqual(len(children), 2)
        new_child = children.sorted(key=lambda line: line.id)[-1]
        self.assertEqual(new_child.quantity, 300)

    def test_add_split_blocks_when_nothing_remaining(self):
        """OP#963: splitting again with no remaining qty raises."""
        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        parent.action_add_split()
        # The single child already covers the full expected qty.
        with self.assertRaises(UserError) as cm:
            parent.action_add_split()
        self.assertIn("No remaining quantity to split", str(cm.exception))

    def test_remove_split_resets_parent_qty(self):
        """OP#963: removing the last child resets parent.quantity to expected."""
        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        parent.action_add_split()
        children = wizard.line_ids.filtered("is_split")
        self.assertEqual(len(children), 1)
        children[0].action_remove_split()

        # Parent is the only line left, back to expected qty.
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(parent.quantity, 1000)
        self.assertFalse(parent.has_splits)

    def test_has_splits_true_when_child_exists(self):
        """OP#963: ``has_splits`` flips True on the parent once a child exists."""
        donation = self._create_received_donation(quantity=500)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        self.assertFalse(parent.has_splits)
        parent.action_add_split()
        self.assertTrue(parent.has_splits)

    def test_confirm_ignores_parent_row_when_splits_exist(self):
        """OP#963: the parent row carries no condition/action — Confirm must
        still gate on the children, not on the parent.
        """
        if not self.condition_new or not self.condition_damaged:
            self.skipTest("Required vocabulary codes not found")
        if not self.disposition_accept or not self.disposition_return:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        parent.action_add_split()
        children = wizard.line_ids.filtered("is_split")
        child_a = children[0]
        child_a.quantity = 700

        InspectionLine = self.env["spp.drims.inspection.wizard.line"]
        child_b = InspectionLine.create(
            {
                "wizard_id": wizard.id,
                "donation_line_id": parent.donation_line_id.id,
                "product_id": parent.product_id.id,
                "uom_id": parent.uom_id.id,
                "quantity_expected": parent.quantity_expected,
                "quantity": 300,
                "parent_line_id": parent.id,
            }
        )

        # Parent has no condition/action; children do — Confirm must succeed.
        self._set_inspection(child_a, self.condition_new, self.disposition_accept)
        self._set_inspection(child_b, self.condition_damaged, self.disposition_return)
        self.assertFalse(parent.is_inspected)
        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")

    def test_inspection_confirms_and_creates_splits(self):
        """OP#963: full split flow via action_add_split produces both donation
        lines downstream of confirm.
        """
        if not self.condition_new or not self.condition_damaged:
            self.skipTest("Required vocabulary codes not found")
        if not self.disposition_accept or not self.disposition_return:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)
        parent = wizard.line_ids[0]

        parent.action_add_split()
        children = wizard.line_ids.filtered("is_split")
        child_a = children[0]
        child_a.quantity = 800

        InspectionLine = self.env["spp.drims.inspection.wizard.line"]
        child_b = InspectionLine.create(
            {
                "wizard_id": wizard.id,
                "donation_line_id": parent.donation_line_id.id,
                "product_id": parent.product_id.id,
                "uom_id": parent.uom_id.id,
                "quantity_expected": parent.quantity_expected,
                "quantity": 200,
                "parent_line_id": parent.id,
            }
        )
        self._set_inspection(child_a, self.condition_new, self.disposition_accept)
        self._set_inspection(child_b, self.condition_damaged, self.disposition_return)

        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")

        self.assertEqual(len(donation.line_ids), 2)
        lines = donation.line_ids.sorted("quantity_received", reverse=True)
        self.assertEqual(lines[0].quantity_received, 800)
        self.assertEqual(lines[0].condition_id, self.condition_new)
        self.assertEqual(lines[1].quantity_received, 200)
        self.assertEqual(lines[1].condition_id, self.condition_damaged)

    def test_inspection_notes_appended(self):
        """Inspection notes are appended to donation notes."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=100)
        donation.notes = "Original notes"

        wizard = self._open_inspection_wizard(donation)
        self._set_inspection(wizard.line_ids[0], self.condition_new, self.disposition_accept)
        wizard.notes = "Inspection completed successfully"

        wizard.action_confirm_inspection()

        self.assertIn("Original notes", donation.notes)
        self.assertIn("Inspection completed successfully", donation.notes)
        self.assertIn("Inspection Notes", donation.notes)
