# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import AlertsTestCommon


@tagged("post_install", "-at_install")
class TestAlertRule(AlertsTestCommon):
    """Tests for spp.alert.rule model.

    Covers alert rule creation, activation/deactivation, model linking,
    threshold configuration, and security/access control.
    """

    def test_create_alert_rule_basic(self):
        """Test basic alert rule creation with required fields."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Test Low Stock Rule",
            alert_type_id=self.alert_type_threshold.id,
            priority="high",
        )

        self.assertEqual(rule.name, "Test Low Stock Rule")
        self.assertEqual(rule.alert_type_id, self.alert_type_threshold)
        self.assertEqual(rule.priority, "high")
        self.assertTrue(rule.active)

    def test_create_alert_rule_with_all_fields(self):
        """Test alert rule creation with all optional fields."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Complete Alert Rule",
            alert_type_id=self.alert_type_threshold.id,
            model_id=self.test_model.id,
            priority="critical",
            active=True,
            sequence=5,
            threshold_value=100.0,
            days_before=7,
            description="Rule for monitoring stock levels",
            company_id=self.company_main.id,
        )

        self.assertEqual(rule.name, "Complete Alert Rule")
        self.assertEqual(rule.model_id, self.test_model)
        self.assertEqual(rule.priority, "critical")
        self.assertTrue(rule.active)
        self.assertEqual(rule.sequence, 5)
        self.assertEqual(rule.threshold_value, 100.0)
        self.assertEqual(rule.days_before, 7)
        self.assertEqual(rule.description, "Rule for monitoring stock levels")
        self.assertEqual(rule.company_id, self.company_main)

    def test_rule_default_values(self):
        """Test that alert rule gets correct default values."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self.env["spp.alert.rule"].create(
            {
                "name": "Minimal Rule",
                "alert_type_id": self.alert_type_threshold.id,
            }
        )

        # Default priority should be medium
        self.assertEqual(rule.priority, "medium")
        # Default active should be True
        self.assertTrue(rule.active)
        # Default sequence should be 10
        self.assertEqual(rule.sequence, 10)
        # Default days_before should be 0
        self.assertEqual(rule.days_before, 0)
        # Default company should be current company
        self.assertEqual(rule.company_id, self.env.company)

    def test_rule_activation_deactivation(self):
        """Test activating and deactivating alert rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Test Activation Rule",
            active=True,
        )

        self.assertTrue(rule.active)

        # Deactivate the rule
        rule.write({"active": False})
        self.assertFalse(rule.active)

        # Reactivate the rule
        rule.write({"active": True})
        self.assertTrue(rule.active)

    def test_rule_model_linking(self):
        """Test linking alert rule to specific Odoo model."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        # Use res.partner model which is always available
        partner_model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        rule = self._create_test_alert_rule(
            name="Partner Model Rule",
            model_id=partner_model.id,
        )

        self.assertEqual(rule.model_id, partner_model)
        self.assertEqual(rule.model_id.model, "res.partner")

    def test_rule_without_model(self):
        """Test that alert rule can be created without model_id."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Generic Rule",
            model_id=False,
        )

        self.assertFalse(rule.model_id)

    def test_rule_priority_levels(self):
        """Test creating rules with different priority levels."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        priorities = ["low", "medium", "high", "critical"]

        for priority in priorities:
            rule = self._create_test_alert_rule(
                name=f"Rule {priority.capitalize()}",
                priority=priority,
            )
            self.assertEqual(rule.priority, priority)

    def test_rule_sequence_ordering(self):
        """Test that rules are ordered by sequence and name."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule_high_seq = self._create_test_alert_rule(
            name="High Sequence",
            sequence=100,
        )
        rule_low_seq = self._create_test_alert_rule(
            name="Low Sequence",
            sequence=1,
        )
        rule_mid_seq = self._create_test_alert_rule(
            name="Mid Sequence",
            sequence=50,
        )

        # Search all test rules
        rules = self.env["spp.alert.rule"].search([("id", "in", [rule_high_seq.id, rule_low_seq.id, rule_mid_seq.id])])

        # Should be ordered by sequence (ascending)
        self.assertEqual(rules[0], rule_low_seq)
        self.assertEqual(rules[-1], rule_high_seq)

    def test_rule_threshold_value_configuration(self):
        """Test configuring threshold_value for different alert types."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        # Threshold rule for low stock (e.g., minimum stock level)
        rule = self._create_test_alert_rule(
            name="Low Stock Threshold",
            threshold_value=50.0,
            description="Alert when stock falls below 50 units",
        )

        self.assertEqual(rule.threshold_value, 50.0)

    def test_rule_threshold_value_zero(self):
        """Test that threshold_value can be set to zero."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Zero Threshold",
            threshold_value=0.0,
        )

        self.assertEqual(rule.threshold_value, 0.0)

    def test_rule_threshold_value_negative(self):
        """Test that threshold_value can be negative if needed."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Negative Threshold",
            threshold_value=-10.0,
        )

        self.assertEqual(rule.threshold_value, -10.0)

    def test_rule_days_before_positive(self):
        """Test days_before for advance warning (positive values)."""
        if not self.alert_type_expiry:
            self.skipTest("Alert type expiry not found")

        rule = self._create_test_alert_rule(
            name="Expiry Warning 30 Days",
            alert_type_id=self.alert_type_expiry.id,
            days_before=30,
            description="Alert 30 days before item expiry",
        )

        self.assertEqual(rule.days_before, 30)

    def test_rule_days_before_zero(self):
        """Test days_before set to zero (alert at exact deadline)."""
        if not self.alert_type_deadline:
            self.skipTest("Alert type deadline not found")

        rule = self._create_test_alert_rule(
            name="Deadline Today",
            alert_type_id=self.alert_type_deadline.id,
            days_before=0,
            description="Alert on the deadline day",
        )

        self.assertEqual(rule.days_before, 0)

    def test_rule_multi_company_main(self):
        """Test rule specific to main company."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Main Company Rule",
            company_id=self.company_main.id,
        )

        self.assertEqual(rule.company_id, self.company_main)

    def test_rule_multi_company_secondary(self):
        """Test rule specific to secondary company."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Secondary Company Rule",
            company_id=self.company_secondary.id,
        )

        self.assertEqual(rule.company_id, self.company_secondary)

    def test_rule_all_alert_types(self):
        """Test creating rules with each available alert type."""
        alert_types = [
            (self.alert_type_threshold, "Threshold Rule"),
            (self.alert_type_expiry, "Expiry Rule"),
            (self.alert_type_deadline, "Deadline Rule"),
            (self.alert_type_manual, "Manual Rule"),
            (self.alert_type_system, "System Rule"),
        ]

        for alert_type_rec, rule_name in alert_types:
            if not alert_type_rec:
                continue

            rule = self._create_test_alert_rule(
                name=rule_name,
                alert_type_id=alert_type_rec.id,
            )

            self.assertEqual(rule.alert_type_id, alert_type_rec)

    def test_rule_search_active_only(self):
        """Test searching for only active rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        active_rule = self._create_test_alert_rule(
            name="Active Rule",
            active=True,
        )
        inactive_rule = self._create_test_alert_rule(
            name="Inactive Rule",
            active=False,
        )

        # Search for active rules
        active_rules = self.env["spp.alert.rule"].search(
            [
                ("id", "in", [active_rule.id, inactive_rule.id]),
                ("active", "=", True),
            ]
        )

        self.assertIn(active_rule, active_rules)
        self.assertNotIn(inactive_rule, active_rules)

    def test_rule_search_inactive(self):
        """Test searching for inactive rules (including in search)."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        active_rule = self._create_test_alert_rule(
            name="Active Rule 2",
            active=True,
        )
        inactive_rule = self._create_test_alert_rule(
            name="Inactive Rule 2",
            active=False,
        )

        # Search with active_test=False to include inactive records
        all_rules = (
            self.env["spp.alert.rule"]
            .with_context(active_test=False)
            .search(
                [
                    ("id", "in", [active_rule.id, inactive_rule.id]),
                ]
            )
        )

        self.assertIn(active_rule, all_rules)
        self.assertIn(inactive_rule, all_rules)

    def test_security_viewer_can_read_rules(self):
        """Test that viewer can read alert rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(name="Security Test Rule")

        # Viewer should be able to read rules
        rule_as_viewer = rule.with_user(self.user_viewer)
        self.assertTrue(rule_as_viewer.exists())
        self.assertEqual(rule_as_viewer.name, "Security Test Rule")

    def test_security_officer_cannot_modify_rules(self):
        """Test that officer cannot modify alert rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(name="Officer Test Rule")

        # Officer should not be able to modify rules
        rule_as_officer = rule.with_user(self.user_officer)
        with self.assertRaises(AccessError):
            rule_as_officer.write({"threshold_value": 100.0})

    def test_security_officer_cannot_create_rules(self):
        """Test that officer cannot create alert rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        # Officer should not be able to create rules
        with self.assertRaises(AccessError):
            self.env["spp.alert.rule"].with_user(self.user_officer).create(
                {
                    "name": "Officer Created Rule",
                    "alert_type_id": self.alert_type_threshold.id,
                }
            )

    def test_security_manager_can_create_rules(self):
        """Test that manager can create alert rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        # Manager should be able to create rules
        rule = (
            self.env["spp.alert.rule"]
            .with_user(self.user_manager)
            .create(
                {
                    "name": "Manager Created Rule",
                    "alert_type_id": self.alert_type_threshold.id,
                    "priority": "high",
                }
            )
        )

        self.assertTrue(rule.exists())
        self.assertEqual(rule.name, "Manager Created Rule")

    def test_security_manager_can_modify_rules(self):
        """Test that manager can modify alert rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(name="Manager Test Rule")

        # Manager should be able to modify rules
        rule_as_manager = rule.with_user(self.user_manager)
        rule_as_manager.write(
            {
                "threshold_value": 75.0,
                "priority": "critical",
            }
        )

        self.assertEqual(rule.threshold_value, 75.0)
        self.assertEqual(rule.priority, "critical")

    def test_security_manager_can_deactivate_rules(self):
        """Test that manager can deactivate alert rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="Deactivation Test",
            active=True,
        )

        # Manager should be able to deactivate
        rule_as_manager = rule.with_user(self.user_manager)
        rule_as_manager.write({"active": False})

        self.assertFalse(rule.active)

    def test_rule_description_optional(self):
        """Test that description field is optional."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_test_alert_rule(
            name="No Description Rule",
            description=False,
        )

        self.assertEqual(rule.name, "No Description Rule")
        self.assertFalse(rule.description)

    def test_rule_with_long_description(self):
        """Test rule with detailed description."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        long_description = """This is a detailed alert rule that monitors stock levels.
        When stock falls below the configured threshold, an alert will be created.
        The alert will include information about:
        - Current stock level
        - Minimum threshold
        - Product details
        - Warehouse location
        """

        rule = self._create_test_alert_rule(
            name="Detailed Rule",
            description=long_description,
        )

        self.assertEqual(rule.description, long_description)

    def test_multiple_rules_same_type(self):
        """Test creating multiple rules for the same alert type."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule1 = self._create_test_alert_rule(
            name="Low Stock Rule 50",
            alert_type_id=self.alert_type_threshold.id,
            threshold_value=50.0,
        )
        rule2 = self._create_test_alert_rule(
            name="Low Stock Rule 100",
            alert_type_id=self.alert_type_threshold.id,
            threshold_value=100.0,
        )
        rule3 = self._create_test_alert_rule(
            name="Low Stock Rule 25",
            alert_type_id=self.alert_type_threshold.id,
            threshold_value=25.0,
        )

        # All rules should exist with different thresholds
        self.assertEqual(rule1.threshold_value, 50.0)
        self.assertEqual(rule2.threshold_value, 100.0)
        self.assertEqual(rule3.threshold_value, 25.0)
