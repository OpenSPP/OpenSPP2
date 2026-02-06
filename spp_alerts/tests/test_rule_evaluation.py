# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import AlertsTestCommon


@tagged("post_install", "-at_install")
class TestRuleEvaluation(AlertsTestCommon):
    """Tests for alert rule evaluation engine.

    Covers threshold rules, date rules, duplicate prevention,
    cron evaluation, validation constraints, and error handling.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get ir.model for res.partner (always available)
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

        # Get numeric field: credit_limit on res.partner
        cls.field_credit_limit = cls.env["ir.model.fields"].search(
            [("model_id", "=", cls.partner_model.id), ("name", "=", "credit_limit")],
            limit=1,
        )

        # Get date field: date on res.partner
        cls.field_date = cls.env["ir.model.fields"].search(
            [("model_id", "=", cls.partner_model.id), ("name", "=", "date")],
            limit=1,
        )

        # Create test partners with known values
        cls.partner_low = cls.env["res.partner"].create(
            {
                "name": "Test Partner Low Credit",
                "credit_limit": 10.0,
                "date": fields.Date.today() + timedelta(days=5),
            }
        )
        cls.partner_mid = cls.env["res.partner"].create(
            {
                "name": "Test Partner Mid Credit",
                "credit_limit": 50.0,
                "date": fields.Date.today() + timedelta(days=30),
            }
        )
        cls.partner_high = cls.env["res.partner"].create(
            {
                "name": "Test Partner High Credit",
                "credit_limit": 200.0,
                "date": fields.Date.today() + timedelta(days=90),
            }
        )

        # Domain that only matches our test partners
        cls.test_domain = (
            f'[("id", "in", [{cls.partner_low.id}, {cls.partner_mid.id}, {cls.partner_high.id}])]'
        )

    def _create_threshold_rule(self, **kwargs):
        """Helper to create a threshold rule for res.partner."""
        vals = {
            "name": "Test Threshold Rule",
            "alert_type_id": self.alert_type_threshold.id,
            "model_id": self.partner_model.id,
            "rule_type": "threshold",
            "monitored_field_id": self.field_credit_limit.id,
            "comparison": "lt",
            "threshold_value": 100.0,
            "domain_filter": self.test_domain,
            "priority": "medium",
        }
        vals.update(kwargs)
        return self.env["spp.alert.rule"].create(vals)

    def _create_date_rule(self, **kwargs):
        """Helper to create a date rule for res.partner."""
        vals = {
            "name": "Test Date Rule",
            "alert_type_id": self.alert_type_deadline.id,
            "model_id": self.partner_model.id,
            "rule_type": "date",
            "date_field_id": self.field_date.id,
            "days_before": 14,
            "domain_filter": self.test_domain,
            "priority": "high",
        }
        vals.update(kwargs)
        return self.env["spp.alert.rule"].create(vals)

    # -------------------------------------------------------------------------
    # Threshold Rule Tests
    # -------------------------------------------------------------------------

    def test_threshold_rule_creates_alerts(self):
        """Test that threshold rule creates alerts for matching records."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=100.0, comparison="lt")
        count = rule._evaluate_rule()

        # partner_low (10) and partner_mid (50) are < 100, partner_high (200) is not
        self.assertEqual(count, 2)

        alerts = self.env["spp.alert"].search([("rule_id", "=", rule.id)])
        self.assertEqual(len(alerts), 2)

    def test_threshold_rule_gt_comparison(self):
        """Test greater-than comparison."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=100.0, comparison="gt")
        count = rule._evaluate_rule()

        # Only partner_high (200) is > 100
        self.assertEqual(count, 1)

    def test_threshold_rule_eq_comparison(self):
        """Test equal comparison."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=50.0, comparison="eq")
        count = rule._evaluate_rule()

        # Only partner_mid (50) equals 50
        self.assertEqual(count, 1)

    def test_threshold_rule_lte_comparison(self):
        """Test less-than-or-equal comparison."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=50.0, comparison="lte")
        count = rule._evaluate_rule()

        # partner_low (10) and partner_mid (50) are <= 50
        self.assertEqual(count, 2)

    def test_threshold_rule_gte_comparison(self):
        """Test greater-than-or-equal comparison."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=50.0, comparison="gte")
        count = rule._evaluate_rule()

        # partner_mid (50) and partner_high (200) are >= 50
        self.assertEqual(count, 2)

    def test_threshold_alert_values(self):
        """Test that created alerts have correct field values."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=15.0, comparison="lt")
        rule._evaluate_rule()

        alert = self.env["spp.alert"].search([("rule_id", "=", rule.id)])
        self.assertEqual(len(alert), 1)
        self.assertEqual(alert.rule_id, rule)
        self.assertEqual(alert.res_model, "res.partner")
        self.assertEqual(alert.res_id, self.partner_low.id)
        self.assertEqual(alert.current_value, 10.0)
        self.assertEqual(alert.threshold_value, 15.0)
        self.assertEqual(alert.priority, "medium")
        self.assertEqual(alert.alert_type_id, self.alert_type_threshold)

    # -------------------------------------------------------------------------
    # Date Rule Tests
    # -------------------------------------------------------------------------

    def test_date_rule_creates_alerts(self):
        """Test that date rule creates alerts for records within days_before."""
        if not self.alert_type_deadline or not self.field_date:
            self.skipTest("Required alert type or field not found")

        rule = self._create_date_rule(days_before=14)
        count = rule._evaluate_rule()

        # partner_low date is 5 days out (<= 14), others are 30 and 90 days out
        self.assertEqual(count, 1)

        alert = self.env["spp.alert"].search([("rule_id", "=", rule.id)])
        self.assertEqual(alert.res_id, self.partner_low.id)
        self.assertEqual(alert.days_until, 5)

    def test_date_rule_wide_window(self):
        """Test date rule with a wide window that catches more records."""
        if not self.alert_type_deadline or not self.field_date:
            self.skipTest("Required alert type or field not found")

        rule = self._create_date_rule(days_before=60)
        count = rule._evaluate_rule()

        # partner_low (5 days) and partner_mid (30 days) are <= 60
        self.assertEqual(count, 2)

    def test_date_rule_alert_values(self):
        """Test that date alerts have correct days_until value."""
        if not self.alert_type_deadline or not self.field_date:
            self.skipTest("Required alert type or field not found")

        rule = self._create_date_rule(days_before=100)
        rule._evaluate_rule()

        alerts = self.env["spp.alert"].search([("rule_id", "=", rule.id)], order="days_until asc")
        # All 3 partners should match (5, 30, 90 days <= 100)
        self.assertEqual(len(alerts), 3)
        self.assertEqual(alerts[0].days_until, 5)
        self.assertEqual(alerts[1].days_until, 30)
        self.assertEqual(alerts[2].days_until, 90)

    # -------------------------------------------------------------------------
    # Duplicate Prevention Tests
    # -------------------------------------------------------------------------

    def test_duplicate_prevention(self):
        """Test that running evaluation twice does not create duplicates."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=100.0, comparison="lt")

        count1 = rule._evaluate_rule()
        count2 = rule._evaluate_rule()

        self.assertEqual(count1, 2)
        self.assertEqual(count2, 0)

        alerts = self.env["spp.alert"].search([("rule_id", "=", rule.id)])
        self.assertEqual(len(alerts), 2)

    def test_duplicate_allows_after_resolve(self):
        """Test that resolved alerts allow new alerts for same record."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=15.0, comparison="lt")

        # First run creates 1 alert (partner_low)
        count1 = rule._evaluate_rule()
        self.assertEqual(count1, 1)

        # Resolve the alert
        alert = self.env["spp.alert"].search([("rule_id", "=", rule.id)])
        alert.write({"resolution_notes": "Test resolution"})
        alert.action_resolve(notes="Test resolution")

        # Second run should create a new alert (old one is resolved)
        count2 = rule._evaluate_rule()
        self.assertEqual(count2, 1)

        all_alerts = self.env["spp.alert"].search([("rule_id", "=", rule.id)])
        self.assertEqual(len(all_alerts), 2)

    # -------------------------------------------------------------------------
    # Cron Tests
    # -------------------------------------------------------------------------

    def test_cron_evaluate_rules(self):
        """Test that cron evaluates only active, configured rules."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        # Active rule with type — should be evaluated
        active_rule = self._create_threshold_rule(name="Active Rule", threshold_value=15.0)

        # Inactive rule — should be skipped
        self._create_threshold_rule(name="Inactive Rule", active=False)

        # Rule without type — should be skipped
        self.env["spp.alert.rule"].create(
            {
                "name": "No Type Rule",
                "alert_type_id": self.alert_type_threshold.id,
                "model_id": self.partner_model.id,
                "priority": "medium",
            }
        )

        self.env["spp.alert.rule"]._cron_evaluate_rules()

        # Only the active rule should have created alerts
        alerts = self.env["spp.alert"].search([("rule_id", "=", active_rule.id)])
        self.assertEqual(len(alerts), 1)

    def test_cron_continues_on_error(self):
        """Test that cron continues if one rule fails."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        # Rule with invalid domain — should fail gracefully
        self._create_threshold_rule(
            name="Bad Domain Rule",
            domain_filter="INVALID DOMAIN",
        )

        # Valid rule — should still succeed
        good_rule = self._create_threshold_rule(
            name="Good Rule",
            threshold_value=15.0,
        )

        self.env["spp.alert.rule"]._cron_evaluate_rules()

        alerts = self.env["spp.alert"].search([("rule_id", "=", good_rule.id)])
        self.assertEqual(len(alerts), 1)

    # -------------------------------------------------------------------------
    # Validation Tests
    # -------------------------------------------------------------------------

    def test_validation_threshold_without_field(self):
        """Test that threshold rule without monitored field raises error."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        with self.assertRaises(ValidationError):
            self.env["spp.alert.rule"].create(
                {
                    "name": "Invalid Rule",
                    "alert_type_id": self.alert_type_threshold.id,
                    "model_id": self.partner_model.id,
                    "rule_type": "threshold",
                    "priority": "medium",
                }
            )

    def test_validation_date_without_field(self):
        """Test that date rule without date field raises error."""
        if not self.alert_type_deadline:
            self.skipTest("Alert type deadline not found")

        with self.assertRaises(ValidationError):
            self.env["spp.alert.rule"].create(
                {
                    "name": "Invalid Date Rule",
                    "alert_type_id": self.alert_type_deadline.id,
                    "model_id": self.partner_model.id,
                    "rule_type": "date",
                    "priority": "medium",
                }
            )

    def test_validation_rule_type_without_model(self):
        """Test that rule type without model raises error."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        with self.assertRaises(ValidationError):
            self.env["spp.alert.rule"].create(
                {
                    "name": "No Model Rule",
                    "alert_type_id": self.alert_type_threshold.id,
                    "rule_type": "threshold",
                    "monitored_field_id": self.field_credit_limit.id,
                    "priority": "medium",
                }
            )

    # -------------------------------------------------------------------------
    # Action / Error Handling Tests
    # -------------------------------------------------------------------------

    def test_action_evaluate_returns_notification(self):
        """Test that action_evaluate returns a notification action."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(threshold_value=15.0)
        result = rule.action_evaluate()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("message", result["params"])

    def test_action_evaluate_no_type_raises(self):
        """Test that action_evaluate raises UserError when no rule_type."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self.env["spp.alert.rule"].create(
            {
                "name": "No Type Rule",
                "alert_type_id": self.alert_type_threshold.id,
                "priority": "medium",
            }
        )

        with self.assertRaises(UserError):
            rule.action_evaluate()

    def test_rule_without_type_returns_zero(self):
        """Test that _evaluate_rule returns 0 when no rule_type."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self.env["spp.alert.rule"].create(
            {
                "name": "No Type Rule",
                "alert_type_id": self.alert_type_threshold.id,
                "model_id": self.partner_model.id,
                "priority": "medium",
            }
        )

        self.assertEqual(rule._evaluate_rule(), 0)

    def test_invalid_domain_returns_zero(self):
        """Test that invalid domain logs error and returns 0."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(domain_filter="NOT A VALID DOMAIN")
        count = rule._evaluate_rule()

        self.assertEqual(count, 0)

    def test_no_matching_records_returns_zero(self):
        """Test that rule returns 0 when no records match domain."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(
            domain_filter='[("id", "=", -1)]',
            threshold_value=100.0,
        )
        count = rule._evaluate_rule()

        self.assertEqual(count, 0)

    def test_rule_propagates_company(self):
        """Test that company_id from rule is propagated to alerts."""
        if not self.alert_type_threshold:
            self.skipTest("Alert type threshold not found")

        rule = self._create_threshold_rule(
            threshold_value=15.0,
            company_id=self.company_main.id,
        )
        rule._evaluate_rule()

        alert = self.env["spp.alert"].search([("rule_id", "=", rule.id)])
        self.assertEqual(alert.company_id, self.company_main)
