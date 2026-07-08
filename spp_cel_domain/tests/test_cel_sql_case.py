# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for to_sql_case() CEL-to-SQL CASE WHEN compilation."""

from odoo.tests import TransactionCase, tagged
from odoo.tools.sql import SQL

from ..services import cel_parser as P


@tagged("post_install", "-at_install")
class TestToSqlCase(TransactionCase):
    """Test CelTranslator.to_sql_case() for CEL-to-SQL value expression compilation."""

    def setUp(self):
        super().setUp()
        self.translator = self.env["spp.cel.translator"]

    def _sql_to_str(self, sql_obj):
        """Convert SQL object to string for assertion checking."""
        return str(sql_obj)

    def test_simple_ternary(self):
        """Test ternary compiles to CASE WHEN."""
        expr = 'r.is_group == true ? "group" : "individual"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = self._sql_to_str(result)
        self.assertIn("CASE WHEN", sql_str)
        self.assertIn("THEN", sql_str)
        self.assertIn("ELSE", sql_str)
        self.assertIn("END", sql_str)

    def test_null_comparison(self):
        """Test field == null compiles to IS NULL."""
        expr = 'r.birthdate == null ? "unknown" : "known"'
        result = self.translator.to_sql_case(expr, "res.partner", "ind")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("IS NULL", sql_str)

    def test_null_ne_comparison(self):
        """Test field != null compiles to IS NOT NULL."""
        expr = 'r.birthdate != null ? "known" : "unknown"'
        result = self.translator.to_sql_case(expr, "res.partner", "ind")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("IS NOT NULL", sql_str)

    def test_age_years_less_than(self):
        """Test age_years(r.birthdate) < N compiles to date arithmetic."""
        expr = 'age_years(r.birthdate) < 18 ? "child" : "adult"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("CASE WHEN", sql_str)
        self.assertIn("CURRENT_DATE", sql_str)
        self.assertIn("18 years", sql_str)
        # age < 18 => birthdate > cutoff (younger)
        self.assertIn(">", sql_str)

    def test_age_years_greater_equal(self):
        """Test age_years(r.birthdate) >= N."""
        expr = 'age_years(r.birthdate) >= 60 ? "elderly" : "not_elderly"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("60 years", sql_str)
        # age >= 60 => birthdate <= cutoff
        self.assertIn("<=", sql_str)

    def test_nested_ternary(self):
        """Test nested ternary compiles to nested CASE WHEN."""
        expr = (
            'r.birthdate == null ? "unknown" : '
            'age_years(r.birthdate) < 18 ? "child" : '
            'age_years(r.birthdate) < 60 ? "adult" : "elderly"'
        )
        result = self.translator.to_sql_case(expr, "res.partner", "ind")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        # Should be a single flattened CASE with multiple WHEN clauses
        self.assertEqual(sql_str.count("CASE"), 1)
        self.assertIn("IS NULL", sql_str)
        self.assertIn("18 years", sql_str)
        self.assertIn("60 years", sql_str)

    def test_field_comparison(self):
        """Test simple field comparison compiles to SQL."""
        expr = 'r.is_group == true ? "group" : "individual"'
        result = self.translator.to_sql_case(expr, "res.partner", "t")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("is_group", sql_str)

    def test_literal_string(self):
        """Test string literals compile to SQL parameters."""
        # A simple ternary with string results
        expr = 'r.active == true ? "active" : "inactive"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)

    def test_unsupported_expression_returns_none(self):
        """Test unsupported CEL expressions return None (Python fallback)."""
        # BinOp (arithmetic) is unsupported
        expr = "r.age + 1"
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_unsupported_function_returns_none(self):
        """Test unsupported function calls return None."""
        # standalone age_years() as a value (not in a comparison) is unsupported
        expr = "age_years(r.birthdate)"
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_invalid_expression_returns_none(self):
        """Test invalid CEL expressions return None."""
        result = self.translator.to_sql_case("???invalid!!!", "res.partner", "p")
        self.assertIsNone(result)

    def test_age_years_eq(self):
        """Test age_years(r.birthdate) == N compiles to range check."""
        expr = 'age_years(r.birthdate) == 25 ? "exactly_25" : "other"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        # EQ uses range: birthdate in (cutoff_{n+1}, cutoff_n]
        self.assertIn("25 years", sql_str)
        self.assertIn("26 years", sql_str)

    def test_boolean_connectives(self):
        """Test And/Or/Not in conditions compile to SQL."""
        expr = 'r.is_group == true && r.active == true ? "active_group" : "other"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("AND", sql_str)

    def test_or_connective(self):
        """Test || in conditions compiles to SQL OR."""
        expr = 'r.is_group == true || r.active == true ? "either" : "neither"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("OR", sql_str)

    def test_not_expression(self):
        """Test ! compiles to SQL NOT."""
        # '!' is greedy in CEL, so it wraps the whole ternary; the compiled
        # SQL negates the CASE expression.
        expr = '! r.active == true ? "inactive" : "active"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("NOT", sql_str)
        self.assertIn("CASE WHEN", sql_str)

    def test_not_unsupported_operand_returns_none(self):
        """Test NOT over an unsupported expression returns None."""
        expr = "!(r.color + 1 > 2)"
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_and_unsupported_operand_returns_none(self):
        """Test && with an uncompilable operand falls back to None."""
        expr = 'r.color + 1 > 2 && r.active == true ? "a" : "b"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_or_unsupported_operand_returns_none(self):
        """Test || with an uncompilable operand falls back to None."""
        expr = 'r.color + 1 > 2 || r.active == true ? "a" : "b"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_null_value_in_result(self):
        """Test null as a ternary result compiles to SQL NULL."""
        expr = 'r.active == true ? null : "inactive"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("NULL", sql_str)

    def test_numeric_literal_comparison(self):
        """Test comparison against a numeric literal compiles to SQL."""
        expr = 'r.color > 5 ? "big" : "small"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("color", sql_str)

    def test_bare_field_ident(self):
        """Test a bare field name (no r. prefix) resolves to a column."""
        expr = 'active == true ? "on" : "off"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("active", sql_str)

    def test_bare_r_returns_none(self):
        """Test 'r' alone is not a value expression and returns None."""
        expr = 'r == null ? "a" : "b"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_list_literal_returns_none(self):
        """Test a list literal as a ternary result returns None."""
        expr = 'r.active == true ? [1] : "x"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_unsupported_then_returns_none(self):
        """Test an uncompilable THEN branch falls back to None."""
        expr = 'r.active == true ? r.color + 1 : "x"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_unsupported_else_returns_none(self):
        """Test an uncompilable ELSE branch falls back to None."""
        expr = 'r.active == true ? "x" : r.color + 1'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_null_on_left_eq(self):
        """Test null == field compiles to IS NULL."""
        expr = 'null == r.birthdate ? "unknown" : "known"'
        result = self.translator.to_sql_case(expr, "res.partner", "ind")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("IS NULL", sql_str)

    def test_null_on_left_ne(self):
        """Test null != field compiles to IS NOT NULL."""
        expr = 'null != r.birthdate ? "known" : "unknown"'
        result = self.translator.to_sql_case(expr, "res.partner", "ind")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("IS NOT NULL", sql_str)

    def test_null_ordering_comparison_returns_none(self):
        """Test ordering comparisons against null are not compilable."""
        for expr in (
            'r.birthdate > null ? "a" : "b"',
            'null < r.birthdate ? "a" : "b"',
        ):
            result = self.translator.to_sql_case(expr, "res.partner", "p")
            self.assertIsNone(result, f"Expected None for {expr}")

    def test_null_compared_to_unsupported_operand_returns_none(self):
        """Test null compared to an uncompilable operand returns None."""
        expr = 'null == r.gender_id.code ? "a" : "b"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_nested_attr_returns_none(self):
        """Test nested relational field access (r.a.b) is unsupported."""
        expr = 'r.gender_id.code == "F" ? "female" : "other"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_age_years_less_equal(self):
        """Test age_years(r.birthdate) <= N inverts to >= cutoff."""
        expr = 'age_years(r.birthdate) <= 17 ? "minor" : "adult"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("17 years", sql_str)
        # age <= 17 => birthdate >= cutoff
        self.assertIn(">=", sql_str)

    def test_age_years_greater_than(self):
        """Test age_years(r.birthdate) > N inverts to < cutoff."""
        expr = 'age_years(r.birthdate) > 59 ? "senior" : "other"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("59 years", sql_str)
        # age > 59 => birthdate < cutoff
        self.assertIn("<", sql_str)

    def test_age_years_ne(self):
        """Test age_years(r.birthdate) != N compiles to an OR of two bounds."""
        expr = 'age_years(r.birthdate) != 30 ? "not_30" : "is_30"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNotNone(result)
        sql_str = self._sql_to_str(result)
        self.assertIn("30 years", sql_str)
        self.assertIn("31 years", sql_str)
        self.assertIn("OR", sql_str)

    def test_age_years_non_literal_bound_returns_none(self):
        """Test age_years() compared to a non-literal returns None."""
        expr = 'age_years(r.birthdate) < r.color ? "a" : "b"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)

    def test_age_years_uncompilable_field_returns_none(self):
        """Test age_years() over a nested field returns None."""
        expr = 'age_years(r.parent_id.birthdate) < 18 ? "a" : "b"'
        result = self.translator.to_sql_case(expr, "res.partner", "p")
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestAstToSqlExprDefensiveBranches(TransactionCase):
    """Cover defensive AST branches unreachable through the CEL parser.

    The parser lexes true/false to boolean Literals and never emits
    Literal(None) or Compare ops outside the six relational kinds, but
    _ast_to_sql_expr guards those shapes for callers constructing ASTs
    directly.
    """

    def setUp(self):
        super().setUp()
        self.translator = self.env["spp.cel.translator"]

    def _expr(self, node):
        return self.translator._ast_to_sql_expr(node, "res.partner", "p", {}, {})

    def test_literal_none(self):
        """Test Literal(None) compiles to SQL NULL."""
        result = self._expr(P.Literal(None))
        self.assertIsNotNone(result)
        self.assertIn("NULL", str(result))

    def test_ident_true_false(self):
        """Test Ident('true')/Ident('false') compile to TRUE/FALSE."""
        self.assertIn("TRUE", str(self._expr(P.Ident("true"))))
        self.assertIn("FALSE", str(self._expr(P.Ident("false"))))

    def test_not_none_operand(self):
        """Test Not over an uncompilable node returns None."""
        node = P.Not(P.BinOp("ADD", P.Attr(P.Ident("r"), "color"), P.Literal(1)))
        self.assertIsNone(self._expr(node))

    def test_compare_unsupported_op_returns_none(self):
        """Test a Compare node with an unknown op returns None."""
        node = P.Compare("IN", P.Attr(P.Ident("r"), "color"), P.Literal(1))
        self.assertIsNone(self._expr(node))

    def test_age_years_unsupported_op_returns_none(self):
        """Test age_years comparison with an unknown op returns None."""
        call = P.Call(P.Ident("age_years"), [P.Attr(P.Ident("r"), "birthdate")])
        node = P.Compare("XX", call, P.Literal(5))
        self.assertIsNone(self._expr(node))


@tagged("post_install", "-at_install")
class TestSQLBuilderCaseWhen(TransactionCase):
    """Test SQLBuilder.case_when() and comparison() methods."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_cel_domain.models.cel_sql_builder import SQLBuilder

        self.builder = SQLBuilder(self.env)

    def test_case_when(self):
        """Test case_when produces CASE WHEN ... THEN ... ELSE ... END."""
        result = self.builder.case_when(
            SQL("x IS NULL"),
            SQL("%s", "unknown"),
            SQL("%s", "known"),
        )
        sql_str = str(result)
        self.assertIn("CASE WHEN", sql_str)
        self.assertIn("THEN", sql_str)
        self.assertIn("ELSE", sql_str)
        self.assertIn("END", sql_str)

    def test_comparison_valid_ops(self):
        """Test comparison with valid operators."""
        for op in ("=", "!=", ">", ">=", "<", "<="):
            result = self.builder.comparison(SQL("a"), op, SQL("b"))
            self.assertIsNotNone(result, f"Operator {op} should be supported")

    def test_comparison_invalid_op(self):
        """Test comparison with invalid operator returns None."""
        result = self.builder.comparison(SQL("a"), "LIKE", SQL("b"))
        self.assertIsNone(result)

    def test_comparison_double_equals(self):
        """Test == is normalized to =."""
        result = self.builder.comparison(SQL("a"), "==", SQL("b"))
        self.assertIsNotNone(result)
