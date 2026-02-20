# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import SimulationTestCommon


@tagged("-at_install", "post_install")
class TestEntitlementRuleConstraints(SimulationTestCommon):
    """Tests for spp.simulation.entitlement.rule constraints."""

    def test_negative_fixed_amount_raises(self):
        """Test that negative fixed amount raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.entitlement.rule"].create(
                {
                    "scenario_id": self.scenario.id,
                    "amount_mode": "fixed",
                    "amount": -100.0,
                }
            )

    def test_missing_multiplier_field_raises(self):
        """Test that multiplier mode without multiplier_field raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.entitlement.rule"].create(
                {
                    "scenario_id": self.scenario.id,
                    "amount_mode": "multiplier",
                    "multiplier_field": False,  # Missing required field
                }
            )

    def test_missing_cel_expression_raises(self):
        """Test that CEL mode without amount_cel_expression raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.simulation.entitlement.rule"].create(
                {
                    "scenario_id": self.scenario.id,
                    "amount_mode": "cel",
                    "amount_cel_expression": False,  # Missing required field
                }
            )

    def test_valid_fixed_rule_creates(self):
        """Test that valid fixed rule creates successfully."""
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "fixed",
                "amount": 1000.0,
            }
        )
        self.assertTrue(rule.exists())
        self.assertEqual(rule.amount_mode, "fixed")
        self.assertEqual(rule.amount, 1000.0)

    def test_valid_multiplier_rule_creates(self):
        """Test that valid multiplier rule creates successfully."""
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "multiplier",
                "multiplier_field": "household_size",
                "amount": 200.0,
            }
        )
        self.assertTrue(rule.exists())
        self.assertEqual(rule.amount_mode, "multiplier")
        self.assertEqual(rule.multiplier_field, "household_size")

    def test_valid_cel_rule_creates(self):
        """Test that valid CEL rule creates successfully."""
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "cel",
                "amount_cel_expression": "r.income * 0.1",
            }
        )
        self.assertTrue(rule.exists())
        self.assertEqual(rule.amount_mode, "cel")
        self.assertEqual(rule.amount_cel_expression, "r.income * 0.1")

    def test_zero_fixed_amount_allowed(self):
        """Test that zero fixed amount is allowed (negative is not, but zero is)."""
        rule = self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": self.scenario.id,
                "amount_mode": "fixed",
                "amount": 0.0,
            }
        )
        self.assertTrue(rule.exists())
        self.assertEqual(rule.amount, 0.0)
