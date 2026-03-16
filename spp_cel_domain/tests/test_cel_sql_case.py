# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for to_sql_case() CEL-to-SQL CASE WHEN compilation."""

from odoo.tests import TransactionCase, tagged
from odoo.tools.sql import SQL


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
        # Should have nested CASE WHEN
        self.assertGreater(sql_str.count("CASE WHEN"), 1)
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
