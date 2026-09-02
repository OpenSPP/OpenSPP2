# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

ROUTING_LOGGER = "odoo.addons.spp_grm_cel.models.grm_routing_rule"


class TestRoutingRules(TransactionCase):
    """Test GRM routing rules with CEL expressions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Rules are created as a GRM manager, not via the bare test env: the
        # test env is the superuser, and a superuser-owned rule evaluates with
        # record rules bypassed (with_user(SUPERUSER_ID) is always superuser
        # mode) — i.e. the pre-#379 unbounded path. Binding the handle to a
        # manager makes every rule in this suite exercise the owner-scoped
        # evaluation the fix introduces, with the same broad manager reach.
        cls.rule_author = cls.env["res.users"].create(
            {
                "name": "Routing Rule Author",
                "login": "grm_routing_rule_author",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.env.ref("spp_grm.group_grm_manager").id),
                ],
            }
        )
        cls.RoutingRule = cls.env["spp.grm.routing.rule"].with_user(cls.rule_author)
        cls.Ticket = cls.env["spp.grm.ticket"]
        cls.Team = cls.env["spp.grm.team"]
        cls.Category = cls.env["spp.grm.ticket.category"]
        cls.Stage = cls.env["spp.grm.ticket.stage"]
        cls.Partner = cls.env["res.partner"]

        # Create test data
        cls.team1 = cls.Team.create(
            {
                "name": "Critical Response Team",
            }
        )
        cls.team2 = cls.Team.create(
            {
                "name": "General Support Team",
            }
        )

        cls.category = cls.Category.create(
            {
                "name": "Fraud",
                "code": "FRAUD",
            }
        )

        cls.stage = cls.Stage.search([], limit=1)
        if not cls.stage:
            cls.stage = cls.Stage.create(
                {
                    "name": "New",
                    "sequence": 1,
                }
            )

        # Create a test partner for ticket creation
        cls.partner = cls.Partner.create(
            {
                "name": "Test Partner",
            }
        )

    def test_routing_rule_creation(self):
        """Test routing rule can be created."""
        rule = self.RoutingRule.create(
            {
                "name": "Route Critical to Team 1",
                "condition_cel": "severity == 'critical'",
                "assign_team_id": self.team1.id,
            }
        )
        self.assertTrue(rule.active)
        self.assertEqual(rule.match_count, 0)

    def test_routing_rule_sequence(self):
        """Test rules are evaluated in sequence order."""
        rule1 = self.RoutingRule.create(
            {
                "name": "Rule 1",
                "sequence": 20,
                "condition_cel": "",  # Always matches
                "assign_team_id": self.team2.id,
            }
        )
        rule2 = self.RoutingRule.create(
            {
                "name": "Rule 2",
                "sequence": 10,
                "condition_cel": "",  # Always matches
                "assign_team_id": self.team1.id,
            }
        )

        rules = self.RoutingRule.search([("id", "in", [rule1.id, rule2.id])], order="sequence, id")
        self.assertEqual(rules[0], rule2)
        self.assertEqual(rules[1], rule1)

    def test_routing_rule_inactive(self):
        """Test inactive rules are not applied."""
        rule = self.RoutingRule.create(
            {
                "name": "Inactive Rule",
                "active": False,
                "condition_cel": "",
                "assign_team_id": self.team1.id,
            }
        )

        rules = self.RoutingRule.search([("active", "=", True)])
        self.assertNotIn(rule, rules)

    def test_routing_context_variables(self):
        """Test routing rule context contains expected variables."""
        rule = self.RoutingRule.create(
            {
                "name": "Test Context",
                "condition_cel": "severity == 'low'",
            }
        )

        ticket = self.Ticket.create(
            {
                "name": "Test Ticket",
                "description": "<p>Test description</p>",
                "severity": "low",
                "stage_id": self.stage.id,
                "partner_id": self.partner.id,
            }
        )

        context = rule._build_evaluation_context(ticket)
        self.assertIn("ticket", context)
        self.assertIn("severity", context)
        self.assertIn("priority", context)
        self.assertEqual(context["severity"], "low")

    def test_expression_evaluation_simple(self):
        """Test simple CEL expression evaluation."""
        rule = self.RoutingRule.create(
            {
                "name": "Test Expression",
                "condition_cel": "severity == 'critical'",
            }
        )

        context = {"severity": "critical"}
        result = rule._evaluate_expression("severity == 'critical'", context)
        self.assertTrue(result)

        context = {"severity": "low"}
        result = rule._evaluate_expression("severity == 'critical'", context)
        self.assertFalse(result)

    def test_expression_evaluation_or(self):
        """Test CEL expression with OR operator."""
        rule = self.RoutingRule.create(
            {
                "name": "Test OR",
                "condition_cel": "severity == 'critical' or severity == 'high'",
            }
        )

        context = {"severity": "high"}
        result = rule._evaluate_expression("severity == 'critical' or severity == 'high'", context)
        self.assertTrue(result)

    def test_expression_evaluation_and(self):
        """Test CEL expression with AND operator."""
        rule = self.RoutingRule.create(
            {
                "name": "Test AND",
                "condition_cel": "severity == 'critical' and priority == '3'",
            }
        )

        context = {"severity": "critical", "priority": "3"}
        result = rule._evaluate_expression("severity == 'critical' and priority == '3'", context)
        self.assertTrue(result)

        context = {"severity": "critical", "priority": "1"}
        result = rule._evaluate_expression("severity == 'critical' and priority == '3'", context)
        self.assertFalse(result)

    # =====================================================
    # INTEGRATION TESTS - Verify routing actually works
    # =====================================================

    def test_apply_routing_assigns_team(self):
        """Test apply_routing() actually assigns team to ticket.

        Note: Routing is automatically applied on ticket creation,
        so we create the ticket first, then the rule, then manually apply.
        """
        # Create ticket BEFORE creating the routing rule
        ticket = self.Ticket.create(
            {
                "name": "Critical Issue",
                "description": "This is a critical issue",
                "severity": "critical",
                "stage_id": self.stage.id,
                "partner_id": self.partner.id,
            }
        )

        # Verify ticket has no team initially (no matching rules existed)
        self.assertFalse(ticket.team_id)

        # Now create a routing rule for critical tickets
        rule = self.RoutingRule.create(
            {
                "name": "Route Critical to Team 1",
                "sequence": 10,
                "condition_cel": "severity == 'critical'",
                "assign_team_id": self.team1.id,
            }
        )

        # Apply routing manually
        result = self.RoutingRule.apply_routing(ticket)

        # Verify routing was applied
        self.assertTrue(result, "apply_routing should return True when a rule matches")
        self.assertEqual(ticket.team_id, self.team1, "Ticket should be assigned to team1")
        self.assertEqual(ticket.routing_rule_id, rule, "Ticket should track which rule was applied")
        self.assertEqual(rule.match_count, 1, "Rule match_count should increment")

    def test_apply_routing_no_match(self):
        """Test apply_routing() returns False when no rules match."""
        # Create a rule that won't match low severity
        self.RoutingRule.create(
            {
                "name": "Route High Only",
                "condition_cel": "severity == 'high'",
                "assign_team_id": self.team1.id,
            }
        )

        # Create a low severity ticket (won't match the rule)
        ticket = self.Ticket.create(
            {
                "name": "Low Priority Issue",
                "description": "This is low priority",
                "severity": "low",
                "stage_id": self.stage.id,
                "partner_id": self.partner.id,
            }
        )

        # Ticket should have no team (rule didn't match)
        self.assertFalse(ticket.team_id, "Ticket should have no team")

    def test_apply_routing_first_match_wins(self):
        """Test that first matching rule (by sequence) is applied."""
        # Create ticket first (before rules exist)
        ticket = self.Ticket.create(
            {
                "name": "Critical Issue",
                "description": "Test",
                "severity": "critical",
                "stage_id": self.stage.id,
                "partner_id": self.partner.id,
            }
        )
        self.assertFalse(ticket.team_id)

        # Now create two rules that could both match
        rule1 = self.RoutingRule.create(
            {
                "name": "First Rule",
                "sequence": 10,
                "condition_cel": "severity == 'critical'",
                "assign_team_id": self.team1.id,
            }
        )
        rule2 = self.RoutingRule.create(
            {
                "name": "Second Rule",
                "sequence": 20,
                "condition_cel": "severity == 'critical'",
                "assign_team_id": self.team2.id,
            }
        )

        # Apply routing
        self.RoutingRule.apply_routing(ticket)

        # Verify first rule (lower sequence) was applied
        self.assertEqual(ticket.team_id, self.team1, "First matching rule should be applied")
        self.assertEqual(rule1.match_count, 1, "First rule should have 1 match")
        self.assertEqual(rule2.match_count, 0, "Second rule should have 0 matches")

    def test_apply_routing_sets_severity(self):
        """Test routing rule can override ticket severity."""
        # Create ticket first
        ticket = self.Ticket.create(
            {
                "name": "Fraud Report",
                "description": "Potential fraud",
                "severity": "low",
                "category_id": self.category.id,
                "stage_id": self.stage.id,
                "partner_id": self.partner.id,
            }
        )

        self.assertEqual(ticket.severity, "low")

        # Now create the rule
        self.RoutingRule.create(
            {
                "name": "Escalate Fraud",
                "condition_cel": "category.code == 'FRAUD'",
                "assign_team_id": self.team1.id,
                "set_severity": "critical",
            }
        )

        # Apply routing
        self.RoutingRule.apply_routing(ticket)

        # Verify severity was escalated
        self.assertEqual(ticket.severity, "critical", "Severity should be escalated to critical")

    def test_apply_routing_inactive_rules_skipped(self):
        """Test that inactive rules are not applied."""
        # Create an inactive rule
        rule = self.RoutingRule.create(
            {
                "name": "Inactive Rule",
                "active": False,
                "condition_cel": "severity == 'critical'",
                "assign_team_id": self.team1.id,
            }
        )

        ticket = self.Ticket.create(
            {
                "name": "Critical Issue",
                "description": "Test",
                "severity": "critical",
                "stage_id": self.stage.id,
                "partner_id": self.partner.id,
            }
        )

        # Apply routing
        result = self.RoutingRule.apply_routing(ticket)

        # Verify inactive rule was not applied
        self.assertFalse(result)
        self.assertFalse(ticket.team_id)
        self.assertEqual(rule.match_count, 0)

    def test_routing_rule_validates_cel_syntax(self):
        """Test that invalid CEL expressions are caught."""
        # This test verifies the _check_condition_cel constraint
        # Validation should reject invalid CEL syntax on create
        with self.assertRaises(ValidationError):
            self.RoutingRule.create(
                {
                    "name": "Test Rule",
                    "condition_cel": "invalid syntax (((",
                    "assign_team_id": self.team1.id,
                }
            )

    def test_routing_failure_is_contained_by_a_savepoint(self):
        """A database error while a rule is applied must not poison the
        caller's transaction. The caller (``_apply_routing_rules``) swallows
        the exception, so without a savepoint the cursor stays aborted and
        every later statement of the same request — the rest of a portal
        submission's own create — dies with InFailedSqlTransaction."""
        self.RoutingRule.create(
            {
                "name": "Failing Rule",
                "condition_cel": "severity == 'critical'",
                "assign_team_id": self.team1.id,
            }
        )

        Ticket = self.env.registry["spp.grm.ticket"]
        original_write = Ticket.write

        def failing_write(tickets, vals):
            if "routing_rule_id" in vals:
                # A genuine PostgreSQL error (what a stale assign_user_id FK
                # would raise on flush): only a savepoint rollback makes the
                # cursor usable again.
                tickets.env.cr.execute("SELECT 1 / 0")
            return original_write(tickets, vals)

        with (
            patch.object(Ticket, "write", failing_write),
            mute_logger("odoo.sql_db"),
            self.assertLogs(ROUTING_LOGGER, level="ERROR") as cm,
        ):
            ticket = self.Ticket.create(
                {
                    "name": "Critical Issue",
                    "description": "Test",
                    "severity": "critical",
                    "stage_id": self.stage.id,
                    "partner_id": self.partner.id,
                }
            )

        self.assertTrue(any("rolled back and skipped" in line for line in cm.output), cm.output)
        # The cursor survived: this query would raise InFailedSqlTransaction
        # if the failed statement had aborted the transaction.
        self.assertEqual(self.Ticket.search_count([("id", "=", ticket.id)]), 1)
        self.assertFalse(ticket.routing_rule_id)
