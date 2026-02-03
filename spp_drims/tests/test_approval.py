# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsApproval(DrimsTestCommon):
    """Tests for DRIMS Approval workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)

    def test_approval_states(self):
        """Test approval state transitions."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "priority_id": self.priority_routine.id,
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

        # Initial state
        self.assertEqual(request.approval_state, "draft")

        # Submit
        request.action_submit()
        self.assertIn(request.approval_state, ["pending", "submitted"])

    def test_total_value_for_cel(self):
        """Test total_value computed field for CEL routing."""
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
                            "quantity_requested": 100,
                            "uom_id": self.product.uom_id.id,
                            "unit_value": 1000.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity_requested": 50,
                            "uom_id": self.product.uom_id.id,
                            "unit_value": 2000.0,
                        },
                    ),
                ],
            }
        )
        # 100 * 1000 + 50 * 2000 = 200,000
        self.assertEqual(request.total_value, 200000.0)

    def test_direct_approval(self):
        """Test direct approval without workflow."""
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
        request.action_approve()
        self.assertEqual(request.approval_state, "approved")
        self.assertEqual(request.state, "approved")

    def test_rejection_with_reason(self):
        """Test rejection with reason."""
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
        request.action_reject(reason="Insufficient stock available")

        self.assertEqual(request.approval_state, "rejected")
        self.assertEqual(request.rejection_reason, "Insufficient stock available")

    def test_revision_request(self):
        """Test revision request workflow."""
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
        request.action_request_revision(notes="Please provide justification")

        self.assertEqual(request.approval_state, "revision")
        self.assertEqual(request.revision_notes, "Please provide justification")

    def test_reset_to_draft(self):
        """Test resetting rejected request to draft."""
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
        request.action_reject(reason="Invalid request")
        self.assertEqual(request.approval_state, "rejected")

        # Reset to draft
        request.action_reset_to_draft()
        self.assertEqual(request.approval_state, "draft")
        self.assertFalse(request.rejection_reason)

    def test_cannot_approve_draft(self):
        """Test that draft requests cannot be approved."""
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

        # Should fail - cannot approve draft
        with self.assertRaises(UserError):
            request.action_approve()

    def test_cannot_submit_without_items(self):
        """Test that requests cannot be submitted without items."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )

        # Should fail - no items
        with self.assertRaises(UserError):
            request.action_submit()

    def test_life_threatening_priority(self):
        """Test life-threatening emergency flag."""
        request = self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "is_life_threatening": True,
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

        self.assertTrue(request.is_life_threatening)
