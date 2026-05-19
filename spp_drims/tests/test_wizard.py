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
        self.assertEqual(
            request.rejection_reason, "Out of scope for this funding cycle"
        )

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

    def test_inspection_wizard_defaults_to_accepted(self):
        """Test wizard pre-creates lines with New/Accept defaults."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)

        # Lines should be pre-created with defaults (New/Accept, already inspected)
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertTrue(wizard.line_ids[0].is_inspected)
        self.assertEqual(wizard.line_ids[0].condition_id, self.condition_new)
        self.assertEqual(wizard.line_ids[0].disposition_id, self.disposition_accept)
        self.assertTrue(wizard.is_valid)

        # Can confirm immediately without any additional action
        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")
        self.assertEqual(donation.line_ids[0].condition_id, self.condition_new)

    def test_inspection_wizard_edit_item(self):
        """Test Edit button opens popup wizard for individual item."""
        donation = self._create_received_donation(quantity=500)
        wizard = self._open_inspection_wizard(donation)

        # Click Edit on first line
        line = wizard.line_ids[0]
        action = line.action_edit_item()

        self.assertEqual(action["res_model"], "spp.drims.inspection.item.wizard")
        self.assertEqual(action["target"], "new")
        self.assertEqual(action["context"]["default_quantity"], 500)
        self.assertEqual(action["context"]["default_quantity_expected"], 500)

    def test_inspection_item_wizard_save(self):
        """Test item popup Save action updates the main wizard line."""
        if not self.condition_damaged or not self.disposition_return:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=100)
        wizard = self._open_inspection_wizard(donation)

        line = wizard.line_ids[0]
        # Line starts inspected with defaults, we change it to damaged
        self.assertTrue(line.is_inspected)

        # Create item wizard and save with different condition
        item_wizard = self.env["spp.drims.inspection.item.wizard"].create(
            {
                "inspection_line_id": line.id,
                "wizard_id": wizard.id,
                "product_id": self.product.id,
                "uom_id": self.product.uom_id.id,
                "quantity_expected": 100,
                "quantity": 100,
                "condition_id": self.condition_damaged.id,
                "disposition_id": self.disposition_return.id,
                "notes": "All items damaged",
            }
        )
        item_wizard.action_save()

        # Line should be updated with new condition
        self.assertTrue(line.is_inspected)
        self.assertEqual(line.condition_id, self.condition_damaged)
        self.assertEqual(line.disposition_id, self.disposition_return)
        self.assertEqual(line.notes, "All items damaged")

    def test_inspection_item_wizard_split(self):
        """Test Save & Add Split creates a new line for remaining quantity."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)

        line = wizard.line_ids[0]
        self.assertEqual(len(wizard.line_ids), 1)

        # Create item wizard with reduced quantity and split
        item_wizard = self.env["spp.drims.inspection.item.wizard"].create(
            {
                "inspection_line_id": line.id,
                "wizard_id": wizard.id,
                "product_id": self.product.id,
                "uom_id": self.product.uom_id.id,
                "quantity_expected": 1000,
                "quantity": 800,  # Only 800, remaining 200
                "condition_id": self.condition_new.id,
                "disposition_id": self.disposition_accept.id,
            }
        )

        # Should show remaining qty
        self.assertEqual(item_wizard.remaining_qty, 200)
        self.assertTrue(item_wizard.show_split_warning)

        # Save and split
        action = item_wizard.action_save_and_split()

        # Should have 2 lines now
        self.assertEqual(len(wizard.line_ids), 2)
        # First line is inspected with 800
        self.assertTrue(line.is_inspected)
        self.assertEqual(line.quantity, 800)
        # New line has remaining 200, not yet inspected
        new_line = wizard.line_ids.filtered(lambda ln: ln.id != line.id)
        self.assertEqual(new_line.quantity, 200)
        self.assertFalse(new_line.is_inspected)

        # Action should open popup for new line
        self.assertEqual(action["res_model"], "spp.drims.inspection.item.wizard")

    def test_inspection_wizard_validation_uninspected(self):
        """Test validation fails if items are not inspected."""
        donation = self._create_received_donation(quantity=100)
        wizard = self._open_inspection_wizard(donation)

        # Lines start as inspected, manually mark as not inspected
        wizard.line_ids[0].write({"is_inspected": False})

        # Not inspected
        self.assertFalse(wizard.is_valid)

        # Should fail confirmation
        with self.assertRaises(UserError) as cm:
            wizard.action_confirm_inspection()
        self.assertIn("inspect all items", str(cm.exception))

    def test_inspection_wizard_single_line_quantity_overrides_received(self):
        """OP#964: a single inspection line is treated as the user reporting
        the final received quantity. Confirming with a different quantity
        than the wizard's expected hint should succeed and update
        ``quantity_received`` on the donation line accordingly.
        """
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        wizard = self._open_inspection_wizard(donation)

        wizard.line_ids[0].write({"quantity": 800})

        self.assertTrue(wizard.is_valid, "single-line wizard should always be valid")
        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")
        self.assertEqual(donation.line_ids[0].quantity_received, 800)

    def test_inspection_wizard_split_mismatch_still_raises(self):
        """OP#964: when the user splits a product across multiple lines,
        the totals must still sum to the expected quantity — that
        safety net is preserved.
        """
        if not self.condition_new or not self.condition_damaged:
            self.skipTest("Required vocabulary codes not found")
        if not self.disposition_accept or not self.disposition_return:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        original_line = donation.line_ids[0]
        wizard = self._open_inspection_wizard(donation)

        # Two lines that sum to 950 ≠ 1000 received → should raise
        wizard.line_ids[0].write({"quantity": 800})
        self.env["spp.drims.inspection.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "donation_line_id": original_line.id,
                "product_id": self.product.id,
                "uom_id": self.product.uom_id.id,
                "quantity_expected": 1000,
                "quantity": 150,  # 800 + 150 = 950 ≠ 1000
                "condition_id": self.condition_damaged.id,
                "disposition_id": self.disposition_return.id,
                "is_inspected": True,
            }
        )

        self.assertFalse(wizard.is_valid)
        with self.assertRaises(UserError) as cm:
            wizard.action_confirm_inspection()
        self.assertIn("Splits must sum", str(cm.exception))

    def test_inspection_wizard_quantity_received_zero_uses_pledged(self):
        """OP#964: when a donation line has quantity_received = 0 (e.g., it
        was added after action_mark_received ran, or pledged was 0), the
        wizard should fall back to quantity_pledged so the user can
        still finalize inspection. Reproduces the bug from the original
        screenshot.
        """
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=500)
        # Simulate the bug: line added with pledged=500 but received=0
        # (because action_mark_received already ran for the original lines).
        donation.line_ids[0].quantity_received = 0

        wizard = self._open_inspection_wizard(donation)
        # Wizard line should pick up pledged (500), not received (0)
        self.assertEqual(wizard.line_ids[0].quantity_expected, 500)
        self.assertTrue(wizard.is_valid)

        wizard.action_confirm_inspection()
        self.assertEqual(donation.state, "inspected")
        self.assertEqual(donation.line_ids[0].quantity_received, 500)

    def test_inspection_wizard_only_received_donations(self):
        """Test that only received donations can be inspected."""
        # Create a donation without marking as received
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

        # Should raise error when trying to open inspection wizard
        with self.assertRaises(UserError):
            donation.action_open_inspection_wizard()

    def test_inspection_wizard_condition_display(self):
        """Test condition_display computed field."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=100)
        wizard = self._open_inspection_wizard(donation)

        line = wizard.line_ids[0]

        # Starts inspected with defaults
        self.assertIn(self.condition_new.display, line.condition_display)
        self.assertIn(self.disposition_accept.display, line.condition_display)

        # After marking as not inspected
        line.write({"is_inspected": False})
        self.assertEqual(line.condition_display, "Not inspected")

    def test_inspection_confirms_and_creates_splits(self):
        """Test full flow: inspect with splits and confirm."""
        if not self.condition_new or not self.condition_damaged:
            self.skipTest("Required vocabulary codes not found")
        if not self.disposition_accept or not self.disposition_return:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=1000)
        original_line = donation.line_ids[0]

        wizard = self._open_inspection_wizard(donation)

        # Change first line: 800 good (already defaults to New/Accept)
        wizard.line_ids[0].write(
            {
                "quantity": 800,
            }
        )

        # Add second line: 200 damaged
        self.env["spp.drims.inspection.wizard.line"].create(
            {
                "wizard_id": wizard.id,
                "donation_line_id": original_line.id,
                "product_id": self.product.id,
                "uom_id": self.product.uom_id.id,
                "quantity_expected": 1000,
                "quantity": 200,
                "condition_id": self.condition_damaged.id,
                "disposition_id": self.disposition_return.id,
                "is_inspected": True,
            }
        )

        # Validation should pass
        self.assertTrue(wizard.is_valid)

        # Confirm
        wizard.action_confirm_inspection()

        # Donation should be inspected
        self.assertEqual(donation.state, "inspected")

        # Should have 2 lines now
        self.assertEqual(len(donation.line_ids), 2)
        lines = donation.line_ids.sorted("quantity_received", reverse=True)
        self.assertEqual(lines[0].quantity_received, 800)
        self.assertEqual(lines[0].condition_id, self.condition_new)
        self.assertEqual(lines[1].quantity_received, 200)
        self.assertEqual(lines[1].condition_id, self.condition_damaged)

    def test_inspection_notes_appended(self):
        """Test that inspection notes are appended to donation notes."""
        if not self.condition_new or not self.disposition_accept:
            self.skipTest("Required vocabulary codes not found")

        donation = self._create_received_donation(quantity=100)
        donation.notes = "Original notes"

        wizard = self._open_inspection_wizard(donation)
        # Lines already default to inspected/accepted
        wizard.notes = "Inspection completed successfully"

        wizard.action_confirm_inspection()

        self.assertIn("Original notes", donation.notes)
        self.assertIn("Inspection completed successfully", donation.notes)
        self.assertIn("Inspection Notes", donation.notes)
