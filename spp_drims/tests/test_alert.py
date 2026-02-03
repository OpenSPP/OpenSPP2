# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsAlert(DrimsTestCommon):
    """Tests for DRIMS Alert model and engine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)
        cls.past_date = date.today() - timedelta(days=5)
        cls.AlertType = cls.env["spp.vocabulary.code"]

        # Get or create alert types
        cls.alert_type_low_stock = cls.AlertType.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:alert-types"),
                ("code", "=", "low_stock"),
            ],
            limit=1,
        )
        cls.alert_type_sla = cls.AlertType.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:alert-types"),
                ("code", "=", "sla_breach"),
            ],
            limit=1,
        )

    def test_create_alert(self):
        """Test basic alert creation."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Test Low Stock Alert",
                "priority": "medium",
                "incident_id": self.incident.id,
                "warehouse_id": self.warehouse.id,
                "product_id": self.product.id,
            }
        )
        self.assertTrue(alert.reference.startswith("ALT-"))
        self.assertEqual(alert.state, "active")
        self.assertEqual(alert.priority, "medium")

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Test Alert",
                "priority": "high",
            }
        )
        self.assertEqual(alert.state, "active")
        alert.action_acknowledge()
        self.assertEqual(alert.state, "acknowledged")

    def test_resolve_alert(self):
        """Test resolving an alert."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Test Alert",
                "priority": "medium",
            }
        )
        alert.action_resolve(notes="Stock replenished")
        self.assertEqual(alert.state, "resolved")
        self.assertEqual(alert.resolved_by_id, self.env.user)
        self.assertTrue(alert.resolved_at)
        self.assertEqual(alert.resolution_notes, "Stock replenished")

    def test_alert_priority_levels(self):
        """Test different priority levels."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        for priority in ["low", "medium", "high", "critical"]:
            alert = self.env["spp.drims.alert"].create(
                {
                    "alert_type_id": self.alert_type_low_stock.id,
                    "title": f"Test {priority.capitalize()} Alert",
                    "priority": priority,
                }
            )
            self.assertEqual(alert.priority, priority)

    def test_alert_with_metrics(self):
        """Test alert with current and threshold values."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Low Stock Alert",
                "priority": "high",
                "current_value": 10.0,
                "threshold_value": 50.0,
                "warehouse_id": self.warehouse.id,
                "product_id": self.product.id,
            }
        )
        self.assertEqual(alert.current_value, 10.0)
        self.assertEqual(alert.threshold_value, 50.0)

    def test_alert_with_days_until(self):
        """Test alert with days until deadline."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "SLA Warning",
                "priority": "high",
                "days_until": 2,
            }
        )
        self.assertEqual(alert.days_until, 2)

    def test_cron_check_sla_with_overdue_request(self):
        """Test SLA check cron finds overdue requests."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        # Create a request with valid date first
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

        # Update date_needed to past date directly (bypassing ORM constraint)
        self.env.cr.execute("UPDATE spp_drims_request SET date_needed = %s WHERE id = %s", (self.past_date, request.id))
        request.invalidate_recordset()

        # Run SLA check
        self.env["spp.drims.alert"]._cron_check_sla()

        # Check if alert was created
        alerts = self.env["spp.drims.alert"].search(
            [
                ("request_id", "=", request.id),
                ("state", "=", "active"),
            ]
        )
        self.assertTrue(len(alerts) >= 1)

    def test_unique_alert_reference(self):
        """Test that alert references are unique."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert1 = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Alert 1",
                "priority": "low",
            }
        )
        alert2 = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Alert 2",
                "priority": "low",
            }
        )
        self.assertNotEqual(alert1.reference, alert2.reference)

    def test_alert_linked_to_incident(self):
        """Test alert properly linked to incident."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Incident Alert",
                "priority": "critical",
                "incident_id": self.incident.id,
            }
        )
        self.assertEqual(alert.incident_id, self.incident)

    # ============================================
    # UX Enhancement Tests (ALT-001/002)
    # ============================================

    def test_urgency_state_overdue(self):
        """Test urgency state is 'overdue' when days_until is negative."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "Overdue Alert",
                "priority": "high",
                "days_until": -3,
            }
        )
        self.assertEqual(alert.urgency_state, "overdue")
        self.assertIn("overdue", alert.urgency_label.lower())

    def test_urgency_state_urgent(self):
        """Test urgency state is 'urgent' when days_until is 0-2."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "Urgent Alert",
                "priority": "high",
                "days_until": 1,
            }
        )
        self.assertEqual(alert.urgency_state, "urgent")

    def test_urgency_state_soon(self):
        """Test urgency state is 'soon' when days_until is 3-7."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "Soon Alert",
                "priority": "medium",
                "days_until": 5,
            }
        )
        self.assertEqual(alert.urgency_state, "soon")

    def test_urgency_state_normal(self):
        """Test urgency state is 'normal' when days_until is 8+."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "Normal Alert",
                "priority": "low",
                "days_until": 15,
            }
        )
        self.assertEqual(alert.urgency_state, "normal")

    def test_urgency_state_resolved(self):
        """Test urgency state is 'normal' when alert is resolved."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "Resolved Alert",
                "priority": "high",
                "days_until": -5,  # Would be overdue if active
            }
        )
        alert.action_resolve()
        self.assertEqual(alert.urgency_state, "normal")

    def test_alert_type_color_low_stock(self):
        """Test alert type color for low stock (red = 1)."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Low Stock Alert",
                "priority": "high",
            }
        )
        self.assertEqual(alert.alert_type_color, 1)  # Red

    def test_alert_type_color_sla_breach(self):
        """Test alert type color for SLA breach (red = 1)."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "SLA Breach Alert",
                "priority": "critical",
            }
        )
        self.assertEqual(alert.alert_type_color, 1)  # Red

    def test_deadline_date_computed(self):
        """Test deadline_date is computed from days_until and create_date."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "Deadline Alert",
                "priority": "high",
                "days_until": 5,
            }
        )
        expected_deadline = date.today() + timedelta(days=5)
        self.assertEqual(alert.deadline_date, expected_deadline)

    def test_deadline_date_when_days_until_set(self):
        """Test deadline_date is computed correctly when days_until is set."""
        if not self.alert_type_sla:
            self.skipTest("SLA alert type not found")
        # Create alert with explicit days_until
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_sla.id,
                "title": "Deadline Alert",
                "priority": "medium",
                "days_until": 10,
            }
        )
        # Should compute deadline as create_date + 10 days
        expected_date = date.today() + timedelta(days=10)
        self.assertEqual(alert.deadline_date, expected_date)

    def test_age_label_computed(self):
        """Test age_label is computed from create_date."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Age Test Alert",
                "priority": "low",
            }
        )
        # Just created, should show minutes or hours ago
        self.assertTrue(alert.age_label)
        # Allow small negative values due to timing (computed after create)
        self.assertGreaterEqual(alert.age_hours, -0.01)

    def test_assigned_to_field(self):
        """Test alert can be assigned to a user."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alert = self.env["spp.drims.alert"].create(
            {
                "alert_type_id": self.alert_type_low_stock.id,
                "title": "Assigned Alert",
                "priority": "medium",
                "assigned_to_id": self.env.user.id,
            }
        )
        self.assertEqual(alert.assigned_to_id, self.env.user)

    def test_bulk_acknowledge_alerts(self):
        """Test bulk acknowledging multiple alerts."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alerts = self.env["spp.drims.alert"]
        for i in range(3):
            alerts |= self.env["spp.drims.alert"].create(
                {
                    "alert_type_id": self.alert_type_low_stock.id,
                    "title": f"Bulk Alert {i}",
                    "priority": "medium",
                }
            )
        # All should be active
        self.assertTrue(all(a.state == "active" for a in alerts))
        # Acknowledge all
        alerts.action_acknowledge()
        # All should be acknowledged
        self.assertTrue(all(a.state == "acknowledged" for a in alerts))

    def test_bulk_resolve_alerts(self):
        """Test bulk resolving multiple alerts."""
        if not self.alert_type_low_stock:
            self.skipTest("Alert type not found")
        alerts = self.env["spp.drims.alert"]
        for i in range(3):
            alerts |= self.env["spp.drims.alert"].create(
                {
                    "alert_type_id": self.alert_type_low_stock.id,
                    "title": f"Bulk Resolve Alert {i}",
                    "priority": "low",
                }
            )
        # Resolve all
        alerts.action_resolve(notes="Bulk resolved")
        # All should be resolved
        self.assertTrue(all(a.state == "resolved" for a in alerts))
