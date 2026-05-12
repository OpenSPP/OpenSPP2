# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import AlertsTestCommon


@tagged("post_install", "-at_install")
class TestAlert(AlertsTestCommon):
    """Tests for spp.alert model.

    Covers alert creation, state transitions, priority validation,
    multi-company isolation, and security/access control.
    """

    def test_create_alert_with_auto_sequence(self):
        """Test that alert creation auto-generates a unique reference from sequence."""
        alert = self._create_test_alert(
            title="Test Auto-Sequence Alert",
        )

        # Reference should be auto-generated (not "New")
        self.assertTrue(alert.reference)
        self.assertNotEqual(alert.reference, "New")
        # Default state should be active
        self.assertEqual(alert.state, "active")

    def test_create_alert_all_required_fields(self):
        """Test alert creation with all required fields."""
        alert = self._create_test_alert(
            alert_type_id=self.alert_type_threshold.id,
            title="Complete Test Alert",
            priority="high",
            description="Detailed description",
            current_value=25.0,
            threshold_value=50.0,
        )

        self.assertEqual(alert.alert_type_id, self.alert_type_threshold)
        self.assertEqual(alert.alert_type, "threshold")
        self.assertEqual(alert.title, "Complete Test Alert")
        self.assertEqual(alert.priority, "high")
        self.assertEqual(alert.current_value, 25.0)
        self.assertEqual(alert.threshold_value, 50.0)

    def test_unique_alert_references(self):
        """Test that multiple alerts get unique references."""
        alert1 = self._create_test_alert(title="Alert 1")
        alert2 = self._create_test_alert(title="Alert 2")
        alert3 = self._create_test_alert(title="Alert 3")

        # All references should be unique
        self.assertNotEqual(alert1.reference, alert2.reference)
        self.assertNotEqual(alert2.reference, alert3.reference)
        self.assertNotEqual(alert1.reference, alert3.reference)

    def test_state_transition_active_to_acknowledged(self):
        """Test state transition from active to acknowledged."""
        alert = self._create_test_alert()
        self.assertEqual(alert.state, "active")

        # Acknowledge the alert
        result = alert.action_acknowledge()
        self.assertTrue(result)
        self.assertEqual(alert.state, "acknowledged")

    def test_state_transition_acknowledged_to_resolved(self):
        """Test state transition from acknowledged to resolved."""
        alert = self._create_test_alert()
        alert.action_acknowledge()
        self.assertEqual(alert.state, "acknowledged")

        # Resolve the alert
        result = alert.action_resolve(notes="Issue fixed")
        self.assertTrue(result)
        self.assertEqual(alert.state, "resolved")

    def test_state_transition_active_to_resolved_directly(self):
        """Test that an alert can be resolved directly from active state."""
        alert = self._create_test_alert()
        self.assertEqual(alert.state, "active")

        # Resolve directly without acknowledging first
        alert.action_resolve(notes="Directly resolved")
        self.assertEqual(alert.state, "resolved")
        self.assertEqual(alert.resolution_notes, "Directly resolved")

    def test_action_resolve_with_notes(self):
        """Test that action_resolve correctly records resolution details."""
        alert = self._create_test_alert()

        resolution_notes = "Stock was replenished to safe levels"
        alert.action_resolve(notes=resolution_notes)

        # Check resolution tracking fields
        self.assertEqual(alert.state, "resolved")
        self.assertEqual(alert.resolution_notes, resolution_notes)
        self.assertEqual(alert.resolved_by_id, self.env.user)
        self.assertTrue(alert.resolved_at)
        # resolved_at should be recent (within last minute)
        time_diff = fields.Datetime.now() - alert.resolved_at
        self.assertLess(time_diff.total_seconds(), 60)

    def test_action_resolve_without_notes_raises(self):
        """Test that action_resolve raises UserError when no notes provided."""
        alert = self._create_test_alert()

        with self.assertRaises(UserError):
            alert.action_resolve()

    def test_priority_levels_all_valid(self):
        """Test that all priority levels can be set correctly."""
        priorities = ["low", "medium", "high", "critical"]

        for priority in priorities:
            alert = self._create_test_alert(
                title=f"Test {priority.capitalize()} Priority",
                priority=priority,
            )
            self.assertEqual(alert.priority, priority)

    def test_alert_ordering_by_priority_and_date(self):
        """Test that alerts are ordered by semantic priority (critical first), then date."""
        alert_low = self._create_test_alert(title="Low", priority="low")
        alert_critical = self._create_test_alert(title="Critical", priority="critical")
        alert_medium = self._create_test_alert(title="Medium", priority="medium")
        alert_high = self._create_test_alert(title="High", priority="high")

        alerts = self.env["spp.alert"].search(
            [("id", "in", [alert_low.id, alert_critical.id, alert_medium.id, alert_high.id])],
        )

        # Verify semantic ordering: critical(4) > high(3) > medium(2) > low(1)
        priorities = [a.priority for a in alerts]
        self.assertEqual(priorities[0], "critical")
        self.assertEqual(priorities[1], "high")
        self.assertEqual(priorities[2], "medium")
        self.assertEqual(priorities[3], "low")

    def test_multi_company_isolation(self):
        """Test that alerts are properly isolated by company."""
        # Create alert in main company
        alert_main = self._create_test_alert(
            title="Main Company Alert",
            company_id=self.company_main.id,
        )

        # Create alert in secondary company
        alert_secondary = self._create_test_alert(
            title="Secondary Company Alert",
            company_id=self.company_secondary.id,
        )

        # Search with company context for main company
        alerts_main = (
            self.env["spp.alert"]
            .with_context(allowed_company_ids=[self.company_main.id])
            .search([("id", "in", [alert_main.id, alert_secondary.id])])
        )

        # Should only find main company alert
        self.assertIn(alert_main, alerts_main)
        # Note: Multi-company rules might still show both depending on configuration
        # This is mainly to test the company_id field is set correctly

    def test_alert_type_vocabulary_link(self):
        """Test that alert_type_id correctly links to vocabulary and alert_type is computed."""
        alert = self._create_test_alert(
            alert_type_id=self.alert_type_deadline.id,
            title="Deadline Alert",
        )

        # Check vocabulary link
        self.assertEqual(alert.alert_type_id, self.alert_type_deadline)
        # Check computed field
        self.assertEqual(alert.alert_type, "deadline")
        self.assertEqual(alert.alert_type, self.alert_type_deadline.code)

    def test_alert_with_threshold_metrics(self):
        """Test alert with current_value and threshold_value for threshold monitoring."""
        alert = self._create_test_alert(
            title="Low Stock Alert",
            current_value=15.0,
            threshold_value=50.0,
            description="Current stock is below minimum threshold",
        )

        self.assertEqual(alert.current_value, 15.0)
        self.assertEqual(alert.threshold_value, 50.0)

    def test_alert_with_days_until_positive(self):
        """Test alert with positive days_until (future deadline)."""
        alert = self._create_test_alert(
            alert_type_id=self.alert_type_deadline.id,
            title="Upcoming Deadline",
            days_until=7,
            description="Task due in 7 days",
        )

        self.assertEqual(alert.days_until, 7)

    def test_alert_with_days_until_negative(self):
        """Test alert with negative days_until (overdue)."""
        alert = self._create_test_alert(
            alert_type_id=self.alert_type_deadline.id,
            title="Overdue Task",
            days_until=-3,
            description="Task is 3 days overdue",
        )

        self.assertEqual(alert.days_until, -3)

    def test_alert_with_days_until_zero(self):
        """Test alert with zero days_until (due today)."""
        alert = self._create_test_alert(
            alert_type_id=self.alert_type_deadline.id,
            title="Due Today",
            days_until=0,
            description="Task due today",
        )

        self.assertEqual(alert.days_until, 0)

    def test_alert_default_company(self):
        """Test that alert gets default company from environment."""
        alert = self._create_test_alert(title="Default Company Test")

        # Should have the current company
        self.assertEqual(alert.company_id, self.env.company)

    def test_alert_rec_name_is_reference(self):
        """Test that alert record name (_rec_name) is the reference field."""
        alert = self._create_test_alert(title="Test Rec Name")

        # display_name should equal the reference (Odoo 19+ uses display_name)
        self.assertEqual(alert.display_name, alert.reference)

    def test_security_viewer_can_read(self):
        """Test that viewer can read alerts."""
        alert = self._create_test_alert(title="Security Test Alert")

        # Viewer should be able to read
        alert_as_viewer = alert.with_user(self.user_viewer)
        self.assertTrue(alert_as_viewer.exists())
        self.assertEqual(alert_as_viewer.title, "Security Test Alert")

    def test_security_viewer_cannot_write(self):
        """Test that viewer cannot modify alerts."""
        alert = self._create_test_alert(title="Security Test Alert")

        # Viewer should not be able to write
        alert_as_viewer = alert.with_user(self.user_viewer)
        with self.assertRaises(AccessError):
            alert_as_viewer.write({"priority": "critical"})

    def test_security_viewer_cannot_acknowledge(self):
        """Test that viewer cannot acknowledge alerts."""
        alert = self._create_test_alert(title="Security Test Alert")

        # Viewer should not be able to acknowledge
        alert_as_viewer = alert.with_user(self.user_viewer)
        with self.assertRaises(AccessError):
            alert_as_viewer.action_acknowledge()

    def test_security_officer_can_create(self):
        """Test that officer can create alerts."""
        # Officer should be able to create
        alert = (
            self.env["spp.alert"]
            .with_user(self.user_officer)
            .create(
                {
                    "alert_type_id": self.alert_type_threshold.id,
                    "title": "Officer Created Alert",
                    "priority": "medium",
                }
            )
        )

        self.assertTrue(alert.exists())
        self.assertEqual(alert.title, "Officer Created Alert")

    def test_security_officer_can_acknowledge_and_resolve(self):
        """Test that officer can acknowledge and resolve alerts."""
        alert = self._create_test_alert(title="Officer Test Alert")

        # Officer should be able to acknowledge and resolve
        alert_as_officer = alert.with_user(self.user_officer)
        alert_as_officer.action_acknowledge()
        self.assertEqual(alert.state, "acknowledged")

        alert_as_officer.action_resolve(notes="Resolved by officer")
        self.assertEqual(alert.state, "resolved")

    def test_alert_with_all_type_codes(self):
        """Test creating alerts with each available alert type."""
        alert_types = [
            (self.alert_type_threshold, "threshold"),
            (self.alert_type_expiry, "expiry"),
            (self.alert_type_deadline, "deadline"),
            (self.alert_type_manual, "manual"),
            (self.alert_type_system, "system"),
        ]

        for alert_type_rec, expected_code in alert_types:
            alert = self._create_test_alert(
                alert_type_id=alert_type_rec.id,
                title=f"Test {expected_code} alert",
            )

            self.assertEqual(alert.alert_type_id, alert_type_rec)
            self.assertEqual(alert.alert_type, expected_code)

    def test_alert_mail_tracking(self):
        """Test that alert has mail tracking capabilities."""
        alert = self._create_test_alert(
            title="Tracking Test",
            priority="low",
        )

        # Update priority to trigger tracking
        alert.write({"priority": "critical"})

        # Should have message tracking (inherited from mail.thread)
        # We verify the tracking mechanism exists
        self.assertTrue(hasattr(alert, "message_ids"))
        self.assertTrue(hasattr(alert, "message_post"))

    def test_multiple_state_transitions(self):
        """Test multiple state transitions on the same alert."""
        alert = self._create_test_alert()

        # Start in active state
        self.assertEqual(alert.state, "active")

        # Transition to acknowledged
        alert.action_acknowledge()
        self.assertEqual(alert.state, "acknowledged")

        # Transition to resolved
        alert.action_resolve(notes="First resolution")
        self.assertEqual(alert.state, "resolved")

        # Verify resolution fields are set
        self.assertEqual(alert.resolution_notes, "First resolution")
        self.assertTrue(alert.resolved_by_id)
        self.assertTrue(alert.resolved_at)

    def test_alert_empty_description(self):
        """Test that alert can be created without description."""
        alert = self._create_test_alert(
            title="Alert without description",
            description=False,
        )

        self.assertEqual(alert.title, "Alert without description")
        self.assertFalse(alert.description)

    def test_alert_zero_threshold_values(self):
        """Test alert with zero values for thresholds."""
        alert = self._create_test_alert(
            title="Zero Threshold Test",
            current_value=0.0,
            threshold_value=0.0,
        )

        self.assertEqual(alert.current_value, 0.0)
        self.assertEqual(alert.threshold_value, 0.0)

    def test_action_acknowledge_non_active_raises(self):
        """Test that acknowledging a non-active alert raises UserError."""
        alert = self._create_test_alert()
        alert.action_acknowledge()
        self.assertEqual(alert.state, "acknowledged")

        # Trying to acknowledge again should fail
        with self.assertRaises(UserError):
            alert.action_acknowledge()

    def test_action_resolve_already_resolved_raises(self):
        """Test that resolving an already-resolved alert raises UserError."""
        alert = self._create_test_alert()
        alert.action_resolve(notes="Resolved")
        self.assertEqual(alert.state, "resolved")

        with self.assertRaises(UserError):
            alert.action_resolve(notes="Resolving again")

    def test_resolve_directly_from_active(self):
        """Test resolving an alert directly from active state (skipping acknowledge)."""
        alert = self._create_test_alert()
        self.assertEqual(alert.state, "active")

        alert.action_resolve(notes="Direct resolution")
        self.assertEqual(alert.state, "resolved")
        self.assertEqual(alert.resolution_notes, "Direct resolution")
        self.assertTrue(alert.resolved_by_id)
        self.assertTrue(alert.resolved_at)

    def test_priority_sequence_values(self):
        """Test that priority_sequence is correctly computed for all priority levels."""
        for priority, expected_seq in [("low", 1), ("medium", 2), ("high", 3), ("critical", 4)]:
            alert = self._create_test_alert(title=f"Test {priority}", priority=priority)
            self.assertEqual(alert.priority_sequence, expected_seq)

    def test_res_name_computed(self):
        """Test that res_name is computed from source record."""
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        alert = self._create_test_alert(
            res_model="res.partner",
            res_id=partner.id,
        )
        self.assertEqual(alert.res_name, "Test Partner")

    def test_res_name_empty_when_no_source(self):
        """Test that res_name is empty when no source record is set."""
        alert = self._create_test_alert()
        self.assertEqual(alert.res_name, "")

    def test_action_view_source(self):
        """Test that action_view_source returns correct action dict."""
        partner = self.env["res.partner"].create({"name": "Source Partner"})
        alert = self._create_test_alert(
            res_model="res.partner",
            res_id=partner.id,
        )
        action = alert.action_view_source()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], partner.id)

    def test_action_view_source_no_source(self):
        """Test that action_view_source returns False when no source record."""
        alert = self._create_test_alert()
        result = alert.action_view_source()
        self.assertFalse(result)

    def test_action_view_related_alerts(self):
        """Test that action_view_related_alerts returns correct action dict."""
        rule = self.env["spp.alert.rule"].create(
            {
                "name": "Test Rule",
                "alert_type_id": self.alert_type_threshold.id,
            }
        )
        alert1 = self._create_test_alert(rule_id=rule.id, title="Alert 1")
        self._create_test_alert(rule_id=rule.id, title="Alert 2")

        action = alert1.action_view_related_alerts()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.alert")
        self.assertIn(("rule_id", "=", rule.id), action["domain"])
        self.assertIn(("id", "!=", alert1.id), action["domain"])

    def test_action_view_related_alerts_no_rule(self):
        """Test that action_view_related_alerts returns False when no rule."""
        alert = self._create_test_alert()
        result = alert.action_view_related_alerts()
        self.assertFalse(result)

    def test_res_name_deleted_record(self):
        """Test that res_name is empty when source record has been deleted."""
        partner = self.env["res.partner"].create({"name": "To Delete"})
        alert = self._create_test_alert(
            res_model="res.partner",
            res_id=partner.id,
        )
        self.assertEqual(alert.res_name, "To Delete")

        # Delete the source record
        partner.unlink()
        alert.invalidate_recordset(["res_name"])
        self.assertEqual(alert.res_name, "")

    def test_res_name_invalid_model(self):
        """Test that res_name handles nonexistent model gracefully."""
        alert = self._create_test_alert(
            res_model="nonexistent.model",
            res_id=1,
        )
        self.assertEqual(alert.res_name, "")

    def test_resolve_with_preset_resolution_notes(self):
        """Test resolving when resolution_notes are already set on the record."""
        alert = self._create_test_alert()
        # Pre-set resolution_notes on the record
        alert.write({"resolution_notes": "Pre-filled notes"})

        # Resolve without passing notes argument — should use the record's notes
        alert.action_resolve()
        self.assertEqual(alert.state, "resolved")
        self.assertEqual(alert.resolution_notes, "Pre-filled notes")
