# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Advanced and edge case tests for CEL amount calculation."""

import logging
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestEntitlementAmountCELAdvanced(TransactionCase):
    """Advanced edge case and security tests for CEL amount calculation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Advanced CEL Program",
                "target_type": "individual",
            }
        )

        # Create a journal with a currency
        cls.currency = cls.env.company.currency_id
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Test Journal Advanced",
                "code": "TSTA",
                "type": "bank",
                "currency_id": cls.currency.id,
            }
        )
        cls.program.journal_id = cls.journal.id

        # Create test beneficiary
        cls.beneficiary = cls.env["res.partner"].create(
            {
                "name": "Test Advanced Beneficiary",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Enroll beneficiary
        cls.membership = cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.beneficiary.id,
                "program_id": cls.program.id,
                "state": "enrolled",
            }
        )

        # Create entitlement manager
        cls.entitlement_manager = cls.env["spp.program.entitlement.manager.cash"].create(
            {
                "name": "Test Advanced Manager",
                "program_id": cls.program.id,
            }
        )

        # Create a cycle
        today = fields.Date.today()
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Advanced Cycle",
                "program_id": cls.program.id,
                "start_date": today,
                "end_date": today + timedelta(days=365),
            }
        )

    # ========== Edge Cases: Math Operations ==========

    def test_division_by_zero(self):
        """Test that division by zero raises an error at runtime."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "100 / 0",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_infinity_result(self):
        """Test that infinity results are handled."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "float('inf')",
            }
        )

        # Should either convert to large number or reject
        try:
            result = item._calculate_cel_amount(self.beneficiary)
            # If it succeeds, result should be very large
            self.assertGreater(result, 0)
        except UserError:
            # Also acceptable to reject infinity
            pass

    def test_nan_result(self):
        """Test that NaN results are handled."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "float('nan')",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_very_large_amount(self):
        """Test that very large amounts are handled."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "999999999999999.99",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary)
        self.assertEqual(result, 999999999999999.99)

    def test_float_precision(self):
        """Test float precision handling."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "0.1 + 0.2",  # Famous float precision issue
            }
        )

        result = item._calculate_cel_amount(self.beneficiary)
        # Should be approximately 0.3
        self.assertAlmostEqual(result, 0.3, places=10)

    def test_zero_base_amount(self):
        """Test formula with zero base_amount."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount": 0.0,
                "amount_cel_expression": "base_amount + 100",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary)
        self.assertEqual(result, 100.0)

    # ========== Security: Python Introspection Attacks ==========

    def test_security_class_access(self):
        """Test that __class__ access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "r.__class__",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_dict_access(self):
        """Test that __dict__ access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "r.__dict__",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_bases_access(self):
        """Test that __bases__ access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "r.__class__.__bases__",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_subclasses_access(self):
        """Test that __subclasses__() access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "object.__subclasses__()",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_globals_access(self):
        """Test that globals() access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "globals()",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_locals_access(self):
        """Test that locals() access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "locals()",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_eval_access(self):
        """Test that eval() access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "eval('100')",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_exec_access(self):
        """Test that exec() access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "exec('x=100')",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_compile_access(self):
        """Test that compile() access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "compile('100', '<string>', 'eval')",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_open_file_access(self):
        """Test that open() file access is blocked."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "open('/etc/passwd')",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_security_import_variants(self):
        """Test various __import__ attempts are blocked."""
        variants = [
            "__import__('os')",
            "__import__('sys')",
            "__import__('subprocess')",
        ]

        for expr in variants:
            with self.subTest(expression=expr):
                item = self.env["spp.program.entitlement.manager.cash.item"].create(
                    {
                        "entitlement_id": self.entitlement_manager.id,
                        "amount_cel_expression": expr,
                    }
                )

                with self.assertRaises(UserError):
                    item._calculate_cel_amount(self.beneficiary)

    # ========== Resource Exhaustion ==========

    def test_very_long_expression(self):
        """Test that very long expressions don't cause issues."""
        # Create a 10KB expression
        long_expr = " + ".join(["1"] * 5000)

        # Should either succeed or fail gracefully (at validation or calculation)
        try:
            item = self.env["spp.program.entitlement.manager.cash.item"].create(
                {
                    "entitlement_id": self.entitlement_manager.id,
                    "amount_cel_expression": long_expr,
                }
            )
            result = item._calculate_cel_amount(self.beneficiary)
            self.assertEqual(result, 5000.0)
        except (UserError, ValidationError):
            # Also acceptable to reject very long expressions
            pass

    def test_deeply_nested_expression(self):
        """Test that deeply nested expressions are handled."""
        # Create deeply nested expression
        expr = "1"
        for _ in range(100):
            expr = f"({expr} + 1)"

        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": expr,
            }
        )

        # Should either compute or reject gracefully
        try:
            result = item._calculate_cel_amount(self.beneficiary)
            self.assertGreater(result, 0)
        except (UserError, ValidationError, RecursionError):
            # Also acceptable to reject deeply nested expressions
            pass

    def test_large_list_creation(self):
        """Test that unsupported CEL constructs (Python list comprehensions) are rejected.

        CEL does not support Python-style list comprehensions. The expression
        is expected to fail at validation or runtime.
        """
        # CEL does not support Python list comprehensions; should be rejected
        try:
            item = self.env["spp.program.entitlement.manager.cash.item"].create(
                {
                    "entitlement_id": self.entitlement_manager.id,
                    "amount_cel_expression": "len([i for i in range(10000)])",
                }
            )
            # If creation succeeds, runtime evaluation must raise an error
            with self.assertRaises(UserError):
                item._calculate_cel_amount(self.beneficiary)
        except (UserError, ValidationError):
            # Also acceptable to reject at validation time
            pass

    # ========== SafeBeneficiaryProxy Edge Cases ==========

    def test_proxy_many2one_field_returns_id(self):
        """Test that many2one fields return ID."""
        # Assuming beneficiary has a company_id or similar many2one field
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.id > 0 ? 100 : 0",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary)
        self.assertEqual(result, 100.0)

    def test_proxy_callable_blocked(self):
        """Test that method calls (e.g. copy) are blocked by SafeRecordProxy at runtime."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.copy()",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_proxy_search_blocked(self):
        """Test that search is blocked by SafeRecordProxy at runtime."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.search",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_proxy_browse_blocked(self):
        """Test that browse is blocked by SafeRecordProxy at runtime."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.browse",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_proxy_create_blocked(self):
        """Test that create is blocked by SafeRecordProxy at runtime."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.create",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_proxy_unlink_blocked(self):
        """Test that unlink is blocked by SafeRecordProxy at runtime."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.unlink",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    # ========== Integration Tests ==========

    def test_max_amount_enforcement(self):
        """Test that max_amount is enforced with CEL formulas."""
        # Set max_amount on manager
        self.entitlement_manager.max_amount = 500.0

        # Create item with formula that exceeds max
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "1000",
            }
        )

        # Prepare entitlements
        self.entitlement_manager.prepare_entitlements(self.cycle, self.membership)

        # Check that amount is capped at max_amount
        entitlement = self.env["spp.entitlement"].search(
            [
                ("cycle_id", "=", self.cycle.id),
                ("partner_id", "=", self.beneficiary.id),
            ]
        )

        self.assertEqual(len(entitlement), 1)
        self.assertEqual(entitlement.initial_amount, 500.0)

    def test_formula_failure_caught_at_runtime(self):
        """Test that formulas accessing non-existent fields fail at runtime.

        The ValidationProxy returns None for unknown fields, so validation
        passes. The error surfaces when calculating against a real record.
        """
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.nonexistent_field * 100",
            }
        )

        with self.assertRaises(UserError):
            item._calculate_cel_amount(self.beneficiary)

    def test_zero_amount_not_created(self):
        """Test that zero-amount entitlements are not created."""
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "0",
            }
        )

        # Prepare entitlements
        self.entitlement_manager.prepare_entitlements(self.cycle, self.membership)

        # No entitlement should be created
        entitlements = self.env["spp.entitlement"].search(
            [
                ("cycle_id", "=", self.cycle.id),
                ("partner_id", "=", self.beneficiary.id),
            ]
        )

        self.assertEqual(len(entitlements), 0)

    def test_currency_handling(self):
        """Test that currency is properly set via journal.

        The currency on items and entitlements comes from the program's journal.
        """
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "500",
            }
        )

        # The item's currency is a related field from the journal
        self.assertEqual(item.currency_id, self.currency, "Item currency should come from journal")

        # Prepare entitlements
        self.entitlement_manager.prepare_entitlements(self.cycle, self.membership)

        # Check currency
        entitlement = self.env["spp.entitlement"].search(
            [
                ("cycle_id", "=", self.cycle.id),
                ("partner_id", "=", self.beneficiary.id),
            ]
        )

        self.assertEqual(len(entitlement), 1)
        # The entitlement's currency also comes from the journal
        self.assertEqual(entitlement.currency_id, self.currency)

    def test_multiple_beneficiaries_performance(self):
        """Test preparing entitlements for many beneficiaries."""
        # Create 50 beneficiaries
        beneficiaries = []
        for i in range(50):
            partner = self.env["res.partner"].create(
                {
                    "name": f"Perf Test Beneficiary {i}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            membership = self.env["spp.program.membership"].create(
                {
                    "partner_id": partner.id,
                    "program_id": self.program.id,
                    "state": "enrolled",
                }
            )
            beneficiaries.append(membership)

        # Create item
        self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "100 * me.id",
            }
        )

        # Prepare entitlements
        all_memberships = self.env["spp.program.membership"].browse([m.id for m in beneficiaries])
        self.entitlement_manager.prepare_entitlements(self.cycle, all_memberships)

        # Check that entitlements were created
        entitlements = self.env["spp.entitlement"].search(
            [
                ("cycle_id", "=", self.cycle.id),
            ]
        )

        self.assertGreaterEqual(len(entitlements), 50)

    def test_unicode_in_formula(self):
        """Test that unicode characters in formulas work."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "me.name == 'José García' ? 500 : 300",
            }
        )

        result = item._calculate_cel_amount(self.beneficiary)
        # Should succeed without unicode errors
        self.assertGreaterEqual(result, 0)

    def test_boolean_to_numeric_conversion(self):
        """Test that boolean results are rejected."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "True",
            }
        )

        # Boolean should convert to 1.0 or be rejected
        try:
            result = item._calculate_cel_amount(self.beneficiary)
            self.assertEqual(result, 1.0)
        except UserError:
            # Also acceptable to reject boolean results
            pass

    def test_none_result_rejected(self):
        """Test that None results are rejected."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "None",
            }
        )

        with self.assertRaises(UserError) as context:
            item._calculate_cel_amount(self.beneficiary)

        self.assertIn("number", str(context.exception).lower())

    def test_string_result_rejected(self):
        """Test that string results are rejected."""
        item = self.env["spp.program.entitlement.manager.cash.item"].create(
            {
                "entitlement_id": self.entitlement_manager.id,
                "amount_cel_expression": "'500'",
            }
        )

        with self.assertRaises(UserError) as context:
            item._calculate_cel_amount(self.beneficiary)

        self.assertIn("number", str(context.exception).lower())
