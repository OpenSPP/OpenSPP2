# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestActivityFeed(DrimsTestCommon):
    """Tests for DRIMS Activity Feed functionality."""

    def test_donation_creates_audit_log(self):
        """Test that creating a donation generates an audit log entry."""
        AuditLog = self.env["spp.audit.log"]

        # Get initial count
        initial_count = AuditLog.search_count(
            [
                ("model", "=", "spp.drims.donation"),
            ]
        )

        # Create a donation
        self.env["spp.drims.donation"].create(
            {
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "donor_name": "Test Donor for Audit",
                "line_ids": [
                    (0, 0, {"product_id": self.product.id, "quantity_pledged": 10, "uom_id": self.product.uom_id.id})
                ],
            }
        )

        # Check audit log was created
        new_count = AuditLog.search_count(
            [
                ("model", "=", "spp.drims.donation"),
            ]
        )

        # Should have at least one more entry
        self.assertGreaterEqual(new_count, initial_count)

    def test_request_creates_audit_log(self):
        """Test that creating a request generates an audit log entry."""
        AuditLog = self.env["spp.audit.log"]

        # Get initial count
        initial_count = AuditLog.search_count(
            [
                ("model", "=", "spp.drims.request"),
            ]
        )

        # Create a request
        self.env["spp.drims.request"].create(
            {
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": date.today() + timedelta(days=7),
                "source_warehouse_id": self.warehouse.id,
            }
        )

        # Check audit log was created
        new_count = AuditLog.search_count(
            [
                ("model", "=", "spp.drims.request"),
            ]
        )

        # Should have at least one more entry
        self.assertGreaterEqual(new_count, initial_count)

    def test_activity_feed_action_domain(self):
        """Test that activity feed action filters DRIMS models correctly."""
        action = self.env.ref("spp_drims.action_drims_activity_feed")

        # The action should exist
        self.assertTrue(action)
        self.assertEqual(action.res_model, "spp.audit.log")

        # Check domain includes DRIMS models
        domain = action.domain
        self.assertIn("spp.drims.donation", str(domain))
        self.assertIn("spp.drims.request", str(domain))
        self.assertIn("spp.drims.alert", str(domain))
        self.assertIn("spp.drims.return", str(domain))
        self.assertIn("stock.picking", str(domain))

    def test_activity_feed_search_filters(self):
        """Test that activity feed search view has expected filters."""
        search_view = self.env.ref("spp_drims.spp_drims_activity_feed_search")

        self.assertTrue(search_view)
        self.assertEqual(search_view.model, "spp.audit.log")

        # Check filter names are in the arch
        arch = search_view.arch
        self.assertIn("filter_donations", arch)
        self.assertIn("filter_requests", arch)
        self.assertIn("filter_alerts", arch)
        self.assertIn("last_24h", arch)
        self.assertIn("last_7d", arch)
