# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for CEL expression parsing in spp_mis_demo_v2.

Verifies that the CEL parser can handle all the expression types used
in demo program eligibility and benefit calculations.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCELParserArithmetic(TransactionCase):
    """Test that the CEL parser supports arithmetic expressions."""

    def test_cel_parser_addition(self):
        """Test CEL parser supports addition operator."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("1 + 2")
        result = evaluate(ast, {})
        self.assertEqual(result, 3)

    def test_cel_parser_subtraction(self):
        """Test CEL parser supports subtraction operator."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("5 - 3")
        result = evaluate(ast, {})
        self.assertEqual(result, 2)

    def test_cel_parser_multiplication(self):
        """Test CEL parser supports multiplication operator."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("4 * 3")
        result = evaluate(ast, {})
        self.assertEqual(result, 12)

    def test_cel_parser_division(self):
        """Test CEL parser supports division operator."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("10 / 2")
        result = evaluate(ast, {})
        self.assertEqual(result, 5.0)

    def test_cel_parser_modulo(self):
        """Test CEL parser supports modulo operator."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("10 % 3")
        result = evaluate(ast, {})
        self.assertEqual(result, 1)

    def test_cel_parser_operator_precedence(self):
        """Test CEL parser respects operator precedence."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        # Multiplication should be evaluated before addition
        ast = parse("2 + 3 * 4")
        result = evaluate(ast, {})
        self.assertEqual(result, 14)  # Not 20

    def test_cel_parser_parentheses(self):
        """Test CEL parser handles parentheses correctly."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("(2 + 3) * 4")
        result = evaluate(ast, {})
        self.assertEqual(result, 20)

    def test_cel_parser_ternary_true(self):
        """Test CEL parser supports ternary operator with true condition."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("true ? 1 : 0")
        result = evaluate(ast, {})
        self.assertEqual(result, 1)

    def test_cel_parser_ternary_false(self):
        """Test CEL parser supports ternary operator with false condition."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("false ? 1 : 0")
        result = evaluate(ast, {})
        self.assertEqual(result, 0)

    def test_cel_parser_ternary_with_expression(self):
        """Test CEL parser supports ternary with expressions."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("5 > 3 ? 10 : 20")
        result = evaluate(ast, {})
        self.assertEqual(result, 10)

    def test_cel_parser_nested_ternary(self):
        """Test CEL parser supports nested ternary operators."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("true ? (false ? 1 : 2) : 3")
        result = evaluate(ast, {})
        self.assertEqual(result, 2)

    def test_cel_parser_double_ampersand_and(self):
        """Test CEL parser supports && as AND operator."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("true && true")
        result = evaluate(ast, {})
        self.assertTrue(result)

        ast = parse("true && false")
        result = evaluate(ast, {})
        self.assertFalse(result)

    def test_cel_parser_double_pipe_or(self):
        """Test CEL parser supports || as OR operator."""
        from odoo.addons.spp_cel_domain.services.cel_parser import evaluate, parse

        ast = parse("true || false")
        result = evaluate(ast, {})
        self.assertTrue(result)

        ast = parse("false || false")
        result = evaluate(ast, {})
        self.assertFalse(result)

    def test_cel_parser_complex_arithmetic_expression(self):
        """Test CEL parser with complex arithmetic from demo formula."""
        from odoo.addons.spp_cel_domain.services.cel_parser import (
            evaluate,
            get_default_functions,
            parse,
        )

        # Simplified version of CHILD_BENEFIT_CALC formula
        ast = parse("150.0 + (2 * 50.0) * 1.2")
        result = evaluate(ast, get_default_functions())
        self.assertAlmostEqual(result, 270.0)

    def test_cel_parser_ternary_in_arithmetic(self):
        """Test CEL parser with ternary inside arithmetic expression."""
        from odoo.addons.spp_cel_domain.services.cel_parser import (
            evaluate,
            get_default_functions,
            parse,
        )

        # Simplified version of CHILD_BENEFIT_CALC formula pattern
        ast = parse("150.0 + (2 * 50.0) * (true ? 1.2 : 1.0)")
        result = evaluate(ast, get_default_functions())
        self.assertAlmostEqual(result, 270.0)

        ast = parse("150.0 + (2 * 50.0) * (false ? 1.2 : 1.0)")
        result = evaluate(ast, get_default_functions())
        self.assertAlmostEqual(result, 250.0)

    def test_cel_parser_min_function(self):
        """Test CEL parser supports min function."""
        from odoo.addons.spp_cel_domain.services.cel_parser import (
            evaluate,
            get_default_functions,
            parse,
        )

        context = get_default_functions()
        ast = parse("min(10, 5)")
        result = evaluate(ast, context)
        self.assertEqual(result, 5)

        ast = parse("min(40, 25)")
        result = evaluate(ast, context)
        self.assertEqual(result, 25)

    def test_cel_parser_max_function(self):
        """Test CEL parser supports max function."""
        from odoo.addons.spp_cel_domain.services.cel_parser import (
            evaluate,
            get_default_functions,
            parse,
        )

        context = get_default_functions()
        ast = parse("max(10, 5)")
        result = evaluate(ast, context)
        self.assertEqual(result, 10)


@tagged("post_install", "-at_install")
class TestDemoFormulaCELParsing(TransactionCase):
    """Test that demo formula CEL expressions can be parsed.

    These tests verify that the CEL expressions used in demo formulas
    are syntactically correct and can be parsed by the CEL parser.
    """

    def test_pmt_eligible_cel_expression(self):
        """Test PMT_ELIGIBLE CEL expression pattern can be parsed."""
        from odoo.addons.spp_cel_domain.services.cel_parser import parse

        # Expression pattern used in PMT_ELIGIBLE formula
        ast = parse("household.pmt_score < 45.0 && household.member_count > 0")
        self.assertIsNotNone(ast)

    def test_elderly_eligible_cel_expression(self):
        """Test ELDERLY_ELIGIBLE CEL expression pattern can be parsed."""
        from odoo.addons.spp_cel_domain.services.cel_parser import parse

        # Expression pattern used in ELDERLY_ELIGIBLE formula
        ast = parse("individual.age >= 65")
        self.assertIsNotNone(ast)

    def test_child_benefit_calc_cel_expression(self):
        """Test CHILD_BENEFIT_CALC CEL expression pattern can be parsed."""
        from odoo.addons.spp_cel_domain.services.cel_parser import parse

        # Expression pattern used in CHILD_BENEFIT_CALC formula
        ast = parse("150.0 + (household.child_count * 50.0) * (household.is_rural ? 1.2 : 1.0)")
        self.assertIsNotNone(ast)

    def test_vulnerability_score_cel_expression(self):
        """Test VULNERABILITY_SCORE CEL expression pattern can be parsed."""
        from odoo.addons.spp_cel_domain.services.cel_parser import parse

        # Expression pattern used in VULNERABILITY_SCORE formula
        expression = (
            "(household.is_female_headed ? 20 : 0) + "
            "(household.has_disabled_member ? 25 : 0) + "
            "min(40, (100 - household.pmt_score) * 0.5)"
        )
        ast = parse(expression)
        self.assertIsNotNone(ast)

    def test_emergency_priority_cel_expression(self):
        """Test EMERGENCY_PRIORITY CEL expression pattern can be parsed."""
        from odoo.addons.spp_cel_domain.services.cel_parser import parse

        # Expression pattern used in EMERGENCY_PRIORITY formula
        expression = "(household.is_displaced ? 40 : 0) + " "(household.days_since_registration < 30 ? 20 : 0) + 40"
        ast = parse(expression)
        self.assertIsNotNone(ast)
