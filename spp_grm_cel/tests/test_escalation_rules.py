# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestEscalationRules(TransactionCase):
    """Test GRM escalation rules with CEL expressions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.EscalationRule = cls.env["spp.grm.escalation.rule"]
        cls.Ticket = cls.env["spp.grm.ticket"]
        cls.Team = cls.env["spp.grm.team"]
        cls.User = cls.env["res.users"]
        cls.Partner = cls.env["res.partner"]
        cls.Stage = cls.env["spp.grm.ticket.stage"]

        # Create test teams
        cls.team1 = cls.Team.create(
            {
                "name": "Regular Support Team",
            }
        )
        cls.team2 = cls.Team.create(
            {
                "name": "Escalation Team",
            }
        )

        # Create test user for escalation target
        cls.escalation_user = cls.User.create(
            {
                "name": "Escalation Manager",
                "login": "escalation_manager_test",
                "email": "escalation@test.com",
            }
        )

        # Create test partner
        cls.partner = cls.Partner.create(
            {
                "name": "Test Complainant",
            }
        )

        # Get or create test stage
        cls.stage = cls.Stage.search([], limit=1)
        if not cls.stage:
            cls.stage = cls.Stage.create(
                {
                    "name": "Open",
                    "sequence": 1,
                }
            )

    def _create_ticket(self, **kwargs):
        """Helper to create a ticket with default values."""
        defaults = {
            "name": "Test Ticket",
            "description": "<p>Test description</p>",
            "severity": "low",
            "stage_id": self.stage.id,
            "partner_id": self.partner.id,
        }
        defaults.update(kwargs)
        return self.Ticket.create(defaults)

    # =====================================================
    # UNIT TESTS - Test individual components
    # =====================================================

    def test_escalation_rule_creation(self):
        """Test escalation rule can be created with proper defaults."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate SLA Breached",
                "condition_cel": "sla_status == 'breached'",
                "escalate_to_team_id": self.team2.id,
            }
        )
        self.assertTrue(rule.active)
        self.assertEqual(rule.escalation_count, 0)
        self.assertEqual(rule.sequence, 10)

    def test_escalation_rule_negative_hours_constraint(self):
        """Test that negative trigger_after_hours raises error."""
        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.EscalationRule.create(
                {
                    "name": "Invalid Rule",
                    "trigger_after_hours": -5,
                }
            )

    def test_expression_evaluation_with_and_or(self):
        """Test CEL expression evaluation with AND/OR operators."""
        rule = self.EscalationRule.create(
            {
                "name": "Complex Condition",
                "condition_cel": "severity == 'critical'",
            }
        )

        # Test AND
        context = {"severity": "critical", "is_escalated": False}
        result = rule._evaluate_expression("severity == 'critical' and not is_escalated", context)
        self.assertTrue(result)

        # Test OR
        context = {"severity": "low", "sla_status": "breached"}
        result = rule._evaluate_expression("severity == 'critical' or sla_status == 'breached'", context)
        self.assertTrue(result)

    # =====================================================
    # INTEGRATION TESTS - Verify escalation actually works
    # =====================================================

    def test_apply_escalation_sets_escalated_flag(self):
        """Test apply_escalation() marks ticket as escalated."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate to Team",
                "condition_cel": "",  # Always matches
                "escalate_to_team_id": self.team2.id,
            }
        )

        ticket = self._create_ticket(severity="high", team_id=self.team1.id)
        self.assertFalse(ticket.is_escalated)

        # Apply escalation
        result = rule.apply_escalation(ticket)

        self.assertTrue(result, "apply_escalation should return True")
        self.assertTrue(ticket.is_escalated, "Ticket should be marked as escalated")
        self.assertTrue(ticket.escalation_date, "Escalation date should be set")
        self.assertEqual(rule.escalation_count, 1, "Escalation count should increment")

    def test_apply_escalation_changes_team(self):
        """Test apply_escalation() reassigns ticket to escalation team."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate to Escalation Team",
                "condition_cel": "",
                "escalate_to_team_id": self.team2.id,
            }
        )

        ticket = self._create_ticket(team_id=self.team1.id)
        self.assertEqual(ticket.team_id, self.team1)

        rule.apply_escalation(ticket)

        self.assertEqual(ticket.team_id, self.team2, "Ticket should be reassigned to escalation team")

    def test_apply_escalation_changes_user(self):
        """Test apply_escalation() reassigns ticket to escalation user."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate to Manager",
                "condition_cel": "",
                "escalate_to_user_id": self.escalation_user.id,
            }
        )

        ticket = self._create_ticket()

        rule.apply_escalation(ticket)

        self.assertEqual(ticket.user_id, self.escalation_user, "Ticket should be assigned to escalation user")
        self.assertEqual(ticket.escalated_to_id, self.escalation_user, "escalated_to_id should be set")

    def test_apply_escalation_changes_severity(self):
        """Test apply_escalation() can escalate severity."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate Severity",
                "condition_cel": "",
                "escalate_severity": "critical",
            }
        )

        ticket = self._create_ticket(severity="low")
        self.assertEqual(ticket.severity, "low")

        rule.apply_escalation(ticket)

        self.assertEqual(ticket.severity, "critical", "Severity should be escalated to critical")

    def test_apply_escalation_changes_priority(self):
        """Test apply_escalation() can escalate priority."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate Priority",
                "condition_cel": "",
                "escalate_priority": "3",  # Very High
            }
        )

        ticket = self._create_ticket(priority="0")  # Low
        self.assertEqual(ticket.priority, "0")

        rule.apply_escalation(ticket)

        self.assertEqual(ticket.priority, "3", "Priority should be escalated to Very High")

    def test_apply_escalation_sets_reason(self):
        """Test apply_escalation() sets escalation reason."""
        rule = self.EscalationRule.create(
            {
                "name": "My Test Rule",
                "condition_cel": "",
            }
        )

        ticket = self._create_ticket()

        rule.apply_escalation(ticket)

        self.assertIn("My Test Rule", ticket.escalation_reason, "Escalation reason should contain rule name")

    def test_apply_escalation_tracks_rule(self):
        """Test apply_escalation() tracks which rule was applied."""
        rule = self.EscalationRule.create(
            {
                "name": "Track This Rule",
                "condition_cel": "",
            }
        )

        ticket = self._create_ticket()

        rule.apply_escalation(ticket)

        self.assertIn(rule, ticket.escalation_rule_ids, "Ticket should track applied escalation rule")

    def test_apply_escalations_matches_condition(self):
        """Test apply_escalations() only applies matching rules."""
        rule_critical = self.EscalationRule.create(
            {
                "name": "Escalate Critical Only",
                "condition_cel": "severity == 'critical'",
                "escalate_to_team_id": self.team2.id,
            }
        )

        # Create a low severity ticket - should NOT match
        ticket_low = self._create_ticket(severity="low")
        result = self.EscalationRule.apply_escalations(ticket_low)

        self.assertFalse(result, "Should not match low severity ticket")
        self.assertFalse(ticket_low.is_escalated)
        self.assertEqual(rule_critical.escalation_count, 0)

        # Create a critical severity ticket - SHOULD match
        ticket_critical = self._create_ticket(severity="critical", name="Critical Ticket")
        result = self.EscalationRule.apply_escalations(ticket_critical)

        self.assertTrue(result, "Should match critical severity ticket")
        self.assertTrue(ticket_critical.is_escalated)
        self.assertEqual(ticket_critical.team_id, self.team2)
        self.assertEqual(rule_critical.escalation_count, 1)

    def test_apply_escalations_multiple_rules(self):
        """Test that multiple escalation rules can apply to same ticket."""
        rule1 = self.EscalationRule.create(
            {
                "name": "Rule 1 - Set Severity",
                "sequence": 10,
                "condition_cel": "severity == 'high'",
                "escalate_severity": "critical",
            }
        )
        rule2 = self.EscalationRule.create(
            {
                "name": "Rule 2 - Set Team",
                "sequence": 20,
                "condition_cel": "severity == 'critical'",  # Matches after rule1 changes severity
                "escalate_to_team_id": self.team2.id,
            }
        )

        ticket = self._create_ticket(severity="high")

        # Apply all matching escalations
        result = self.EscalationRule.apply_escalations(ticket)

        self.assertTrue(result)
        # First rule should have matched and escalated severity
        self.assertEqual(ticket.severity, "critical")
        self.assertEqual(rule1.escalation_count, 1)
        # Second rule should also match (since severity is now critical)
        self.assertEqual(ticket.team_id, self.team2)
        self.assertEqual(rule2.escalation_count, 1)

    def test_apply_escalations_inactive_rules_skipped(self):
        """Test that inactive escalation rules are not applied."""
        rule = self.EscalationRule.create(
            {
                "name": "Inactive Rule",
                "active": False,
                "condition_cel": "",  # Would always match if active
                "escalate_to_team_id": self.team2.id,
            }
        )

        ticket = self._create_ticket()

        result = self.EscalationRule.apply_escalations(ticket)

        self.assertFalse(result, "No rules should match when only inactive rules exist")
        self.assertFalse(ticket.is_escalated)
        self.assertEqual(rule.escalation_count, 0)

    def test_time_trigger_not_met(self):
        """Test escalation rule with time trigger that hasn't been met."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate After 24 Hours",
                "trigger_after_hours": 24,
                "condition_cel": "",
                "escalate_to_team_id": self.team2.id,
            }
        )

        # Create a fresh ticket (created just now)
        ticket = self._create_ticket()

        # Time trigger shouldn't be met yet
        result = rule.evaluate(ticket)

        self.assertFalse(result, "Time trigger should not be met for new ticket")

    def test_time_trigger_met(self):
        """Test escalation rule with time trigger that has been met."""
        rule = self.EscalationRule.create(
            {
                "name": "Escalate After 1 Hour",
                "trigger_after_hours": 1,
                "condition_cel": "",
                "escalate_to_team_id": self.team2.id,
            }
        )

        # Create ticket with old create_date
        ticket = self._create_ticket()
        # Manually set create_date to 2 hours ago
        old_date = fields.Datetime.now() - timedelta(hours=2)
        ticket.write({"create_date": old_date})

        # Time trigger should be met
        result = rule.evaluate(ticket)

        self.assertTrue(result, "Time trigger should be met for 2-hour old ticket with 1-hour trigger")

    def test_check_escalations_cron(self):
        """Test the cron job check_escalations() processes tickets."""
        # Create a rule that matches high severity
        self.EscalationRule.create(
            {
                "name": "Escalate High Severity",
                "condition_cel": "severity == 'high'",
                "escalate_to_team_id": self.team2.id,
            }
        )

        # Create some tickets
        ticket_low = self._create_ticket(severity="low", name="Low Priority")
        ticket_high = self._create_ticket(severity="high", name="High Priority")

        # Run the cron job
        escalated_count = self.EscalationRule.check_escalations()

        # Only the high severity ticket should be escalated
        self.assertEqual(escalated_count, 1)
        self.assertFalse(ticket_low.is_escalated)
        self.assertTrue(ticket_high.is_escalated)
        self.assertEqual(ticket_high.team_id, self.team2)
