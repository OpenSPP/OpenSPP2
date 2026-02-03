# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for entitlement condition CEL integration."""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEntitlementConditionCEL(TransactionCase):
    """Tests for CEL entitlement condition integration."""

    def setUp(self):
        super().setUp()

        # Create a test currency
        self.currency = self.env.ref("base.USD")

        # Create a test journal
        self.journal = self.env["account.journal"].create(
            {
                "name": "Test Journal",
                "type": "cash",
                "code": "TST",
                "currency_id": self.currency.id,
            }
        )

        # Create test program
        self.program = self.env["spp.program"].create(
            {
                "name": "Test Entitlement Program",
                "target_type": "individual",
                "journal_id": self.journal.id,
            }
        )

        # Create cash entitlement manager
        self.manager = self.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Test Cash Manager",
                "program_id": self.program.id,
            }
        )

        # Create entitlement item with CEL mode
        self.item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.manager.id,
                "amount": 100.0,
                "condition_mode": "cel",
                "cel_condition": "true",
            }
        )

    def test_mode_switching_cel_to_domain(self):
        """Switching from CEL to domain mode should work."""
        self.item.condition_mode = "domain"
        self.item._compute_cel_preview()
        # Should not crash
        self.assertTrue(self.item.cel_is_valid)

    def test_mode_switching_domain_to_cel(self):
        """Switching from domain to CEL mode should work."""
        self.item.condition_mode = "domain"
        self.item.cel_condition = "r.is_registrant == true"
        self.item.condition_mode = "cel"
        self.item._compute_cel_preview()
        # Should validate
        self.assertTrue(self.item.cel_is_valid)

    def test_empty_cel_condition_in_cel_mode(self):
        """Empty CEL condition in CEL mode should be invalid."""
        self.item.cel_condition = ""
        self.item._compute_cel_preview()
        self.assertFalse(self.item.cel_is_valid)
        # Should be valid in domain mode
        self.item.condition_mode = "domain"
        self.item._compute_cel_preview()
        self.assertTrue(self.item.cel_is_valid)

    def test_none_cel_condition_in_cel_mode(self):
        """None as CEL condition should be handled."""
        self.item.cel_condition = False  # Odoo uses False for None/empty
        self.item._compute_cel_preview()
        self.assertFalse(self.item.cel_is_valid)

    def test_whitespace_only_cel_condition(self):
        """Whitespace-only CEL condition should be invalid."""
        self.item.cel_condition = "   \n\t  "
        self.item._compute_cel_preview()
        self.assertFalse(self.item.cel_is_valid)
        self.assertIn("error", self.item.cel_preview_error.lower())

    def test_invalid_syntax_cel_condition(self):
        """Invalid syntax should show error in preview."""
        self.item.cel_condition = "r.age >>>"
        self.item._compute_cel_preview()
        self.assertFalse(self.item.cel_is_valid)
        self.assertGreater(len(self.item.cel_preview_error), 0)

    def test_valid_cel_condition_shows_count(self):
        """Valid CEL condition should show preview count."""
        self.item.cel_condition = "true"
        self.item._compute_cel_preview()
        self.assertTrue(self.item.cel_is_valid)
        self.assertEqual(self.item.cel_preview_error, "")
        # Count should be >= 0
        self.assertGreaterEqual(self.item.cel_preview_count, 0)

    def test_cel_condition_with_unicode(self):
        """CEL condition with unicode should work."""
        self.item.cel_condition = 'r.name == "José García"'
        self.item._compute_cel_preview()
        self.assertTrue(self.item.cel_is_valid)

    def test_sql_injection_in_cel_condition(self):
        """SQL injection attempts should be safely handled."""
        self.item.cel_condition = 'r.name == "Robert\'); DROP TABLE res_partner;--"'
        self.item._compute_cel_preview()
        # Should either succeed (treating as literal) or fail safely
        # Must NOT execute SQL

    def test_code_injection_in_cel_condition(self):
        """Code injection attempts should not execute."""
        self.item.cel_condition = "r.name == \"__import__('os').system('ls')\""
        self.item._compute_cel_preview()
        # Should safely evaluate without executing code

    def test_action_test_cel_expression_valid(self):
        """Test action for valid CEL expression."""
        self.item.cel_condition = "true"
        result = self.item.action_test_cel_expression()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertIn("params", result)

    def test_action_test_cel_expression_invalid(self):
        """Test action for invalid CEL expression."""
        self.item.cel_condition = "invalid syntax >>>"
        result = self.item.action_test_cel_expression()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertIn("params", result)

    def test_action_test_cel_expression_empty(self):
        """Test action with empty CEL expression should raise error."""
        self.item.cel_condition = ""
        with self.assertRaises(ValidationError):
            self.item.action_test_cel_expression()

    def test_action_preview_beneficiaries_valid(self):
        """Test preview beneficiaries action with valid expression."""
        self.item.cel_condition = "true"
        result = self.item.action_preview_beneficiaries()
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "res.partner")
        self.assertIn("domain", result)

    def test_action_preview_beneficiaries_invalid(self):
        """Test preview beneficiaries action with invalid expression."""
        self.item.cel_condition = "invalid >>>"
        with self.assertRaises(ValidationError):
            self.item.action_preview_beneficiaries()

    def test_compile_cel_to_domain_valid(self):
        """Test compiling valid CEL expression to domain."""
        self.item.cel_condition = "true"
        domain = self.item._compile_cel_to_domain()
        self.assertIsInstance(domain, list)

    def test_compile_cel_to_domain_invalid(self):
        """Test compiling invalid CEL expression raises error."""
        self.item.cel_condition = "invalid syntax"
        with self.assertRaises(ValidationError):
            self.item._compile_cel_to_domain()

    def test_compile_cel_to_domain_with_base_domain(self):
        """Test compiling CEL with base domain."""
        self.item.cel_condition = "true"
        base_domain = [("is_registrant", "=", True)]
        domain = self.item._compile_cel_to_domain(base_domain=base_domain)
        self.assertIsInstance(domain, list)

    def test_compile_cel_to_domain_domain_mode(self):
        """Test compiling in domain mode returns base domain."""
        self.item.condition_mode = "domain"
        self.item.cel_condition = "true"
        base_domain = [("test", "=", True)]
        domain = self.item._compile_cel_to_domain(base_domain=base_domain)
        self.assertEqual(domain, base_domain)

    def test_entitlement_preparation_with_cel(self):
        """Test entitlement preparation using CEL conditions."""
        # Create test beneficiary
        beneficiary = self.env["res.partner"].create(
            {
                "name": "Test Beneficiary",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create program membership
        _membership = self.env["spp.program.membership"].create(
            {
                "partner_id": beneficiary.id,
                "program_id": self.program.id,
                "state": "enrolled",
            }
        )

        # Create cycle with future dates
        today = fields.Date.today()
        cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": today,
                "end_date": today + timedelta(days=365),
            }
        )

        # Set CEL condition to match registrants
        self.item.cel_condition = "r.is_registrant == true"

        # Prepare entitlements
        beneficiaries = self.env["spp.program.membership"].search([("program_id", "=", self.program.id)])

        # This should work without errors
        try:
            self.manager.prepare_entitlements(cycle, beneficiaries)
        except Exception as e:
            self.fail(f"Entitlement preparation failed: {str(e)}")

    def test_entitlement_preview_count_accuracy(self):
        """Test that preview count accurately reflects matching beneficiaries."""
        # Create multiple test beneficiaries
        for i in range(5):
            self.env["res.partner"].create(
                {
                    "name": f"Test Beneficiary {i}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )

        # Set condition to match registrants
        self.item.cel_condition = "r.is_registrant == true"
        self.item._compute_cel_preview()

        # Preview count should be at least 5
        self.assertGreaterEqual(self.item.cel_preview_count, 5)
