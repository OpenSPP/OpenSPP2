# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unit tests for SQLBuilder class.

Tests cover term generation, WHERE clause building, and SELECT query building
as per SPEC_SQL_SCALABILITY.md v2.0 section 8.1.
"""

from odoo.tests import TransactionCase, tagged
from odoo.tools.sql import SQL

from ..models.cel_sql_builder import SQLBuilder


@tagged("post_install", "-at_install")
class TestSQLBuilderTerm(TransactionCase):
    """Test SQLBuilder.term() method for various operators and values."""

    def setUp(self):
        super().setUp()
        self.builder = SQLBuilder(self.env)

    def test_term_equals_value(self):
        """Test term("m", "field", "=", "value")."""
        result = self.builder.term("m", "field", "=", "value")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        # Verify the SQL string contains the expected pattern
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("field", sql_str)
        self.assertIn("=", sql_str)

    def test_term_equals_false(self):
        """Test term("m", "is_ended", "=", False)."""
        result = self.builder.term("m", "is_ended", "=", False)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("is_ended", sql_str)
        self.assertIn("=", sql_str)

    def test_term_equals_none_is_null(self):
        """Test term("m", "field", "=", None) returns IS NULL."""
        result = self.builder.term("m", "field", "=", None)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("IS NULL", sql_str)
        self.assertNotIn("= NULL", sql_str)  # Should not use = NULL

    def test_term_not_equals_value(self):
        """Test term("m", "field", "!=", "value")."""
        result = self.builder.term("m", "field", "!=", "value")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("field", sql_str)
        self.assertIn("!=", sql_str)

    def test_term_not_equals_none_is_not_null(self):
        """Test term("m", "field", "!=", None) returns IS NOT NULL."""
        result = self.builder.term("m", "field", "!=", None)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("IS NOT NULL", sql_str)
        self.assertNotIn("!= NULL", sql_str)  # Should not use != NULL

    def test_term_greater_than(self):
        """Test term("m", "count", ">", 5)."""
        result = self.builder.term("m", "count", ">", 5)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("count", sql_str)
        self.assertIn(">", sql_str)

    def test_term_greater_equal(self):
        """Test term("m", "count", ">=", 5)."""
        result = self.builder.term("m", "count", ">=", 5)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("count", sql_str)
        self.assertIn(">=", sql_str)

    def test_term_less_than(self):
        """Test term("m", "count", "<", 5)."""
        result = self.builder.term("m", "count", "<", 5)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("count", sql_str)
        self.assertIn("<", sql_str)

    def test_term_less_equal(self):
        """Test term("m", "count", "<=", 5)."""
        result = self.builder.term("m", "count", "<=", 5)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("count", sql_str)
        self.assertIn("<=", sql_str)

    def test_term_in_list(self):
        """Test term("m", "id", "in", [1,2,3])."""
        result = self.builder.term("m", "id", "in", [1, 2, 3])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("id", sql_str)
        self.assertIn("IN", sql_str)

    def test_term_in_empty_list_returns_false(self):
        """Test term("m", "id", "in", []) returns SQL("1=0")."""
        result = self.builder.term("m", "id", "in", [])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        # Empty IN list should return false condition
        self.assertIn("1=0", sql_str)

    def test_term_not_in_list(self):
        """Test term("m", "id", "not in", [1,2,3])."""
        result = self.builder.term("m", "id", "not in", [1, 2, 3])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("m", sql_str)
        self.assertIn("id", sql_str)
        self.assertIn("NOT IN", sql_str)

    def test_term_not_in_empty_list_returns_true(self):
        """Test term("m", "id", "not in", []) returns SQL("1=1")."""
        result = self.builder.term("m", "id", "not in", [])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        # Empty NOT IN list should return true condition
        self.assertIn("1=1", sql_str)

    def test_term_like_returns_none(self):
        """Test term("m", "name", "like", "%x%") returns None."""
        result = self.builder.term("m", "name", "like", "%x%")
        self.assertIsNone(result)

    def test_term_ilike_returns_none(self):
        """Test term("m", "name", "ilike", "%x%") returns None."""
        result = self.builder.term("m", "name", "ilike", "%x%")
        self.assertIsNone(result)

    def test_term_double_equals_normalizes(self):
        """Test that == is normalized to =."""
        result = self.builder.term("m", "field", "==", "value")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        # Should produce same result as single =
        sql_str = str(result)
        self.assertIn("=", sql_str)

    def test_term_child_of_returns_none(self):
        """Test that child_of operator returns None."""
        result = self.builder.term("m", "parent_id", "child_of", 5)
        self.assertIsNone(result)

    def test_term_parent_of_returns_none(self):
        """Test that parent_of operator returns None."""
        result = self.builder.term("m", "child_id", "parent_of", 5)
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestSQLBuilderWhereAnd(TransactionCase):
    """Test SQLBuilder.where_and() method for combining conditions."""

    def setUp(self):
        super().setUp()
        self.builder = SQLBuilder(self.env)

    def test_where_and_empty_list(self):
        """Empty list returns SQL("1=1")."""
        result = self.builder.where_and([])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("1=1", sql_str)

    def test_where_and_single_condition(self):
        """Single condition returns that condition."""
        cond = SQL("m.status = %s", "active")
        result = self.builder.where_and([cond])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        # Should return the same condition
        self.assertEqual(str(cond), str(result))

    def test_where_and_multiple_conditions(self):
        """Multiple conditions combined with AND."""
        cond1 = SQL("m.status = %s", "active")
        cond2 = SQL("m.is_ended = %s", False)
        cond3 = SQL("m.count > %s", 0)
        result = self.builder.where_and([cond1, cond2, cond3])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        # Should contain AND operators
        self.assertIn("AND", sql_str)

    def test_where_and_two_conditions(self):
        """Two conditions combined with single AND."""
        cond1 = SQL("m.field1 = %s", "value1")
        cond2 = SQL("m.field2 = %s", "value2")
        result = self.builder.where_and([cond1, cond2])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("AND", sql_str)


@tagged("post_install", "-at_install")
class TestSQLBuilderWhereOr(TransactionCase):
    """Test SQLBuilder.where_or() method for combining conditions."""

    def setUp(self):
        super().setUp()
        self.builder = SQLBuilder(self.env)

    def test_where_or_empty_list(self):
        """Empty list returns SQL("1=0") (nothing matches)."""
        result = self.builder.where_or([])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("1=0", sql_str)

    def test_where_or_single_condition(self):
        """Single condition returns that condition."""
        cond = SQL("m.status = %s", "active")
        result = self.builder.where_or([cond])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        # Should return the same condition
        self.assertEqual(str(cond), str(result))

    def test_where_or_multiple_conditions(self):
        """Multiple conditions combined with OR."""
        cond1 = SQL("m.status = %s", "active")
        cond2 = SQL("m.status = %s", "pending")
        result = self.builder.where_or([cond1, cond2])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        # Should contain OR operators
        self.assertIn("OR", sql_str)


@tagged("post_install", "-at_install")
class TestSQLBuilderSelect(TransactionCase):
    """Test SQLBuilder SELECT query building methods.

    Note: Some tests require database fixtures and actual model data.
    """

    def setUp(self):
        super().setUp()
        self.builder = SQLBuilder(self.env)

    def test_select_distinct_column(self):
        """Test select_distinct_column generates correct SQL structure."""
        where = SQL("m.is_ended = %s", False)
        result = self.builder.select_distinct_column("spp_group_membership", "m", "group", where)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        # Should contain SELECT DISTINCT
        self.assertIn("SELECT DISTINCT", sql_str.upper())
        self.assertIn("m", sql_str)
        self.assertIn("group", sql_str)
        self.assertIn("spp_group_membership", sql_str)

    def test_select_grouped_count(self):
        """Test select_grouped_count generates correct SQL with GROUP BY and HAVING."""
        where = SQL("m.is_ended = %s", False)
        result = self.builder.select_grouped_count(
            "spp_group_membership",
            "m",
            "group",
            where,
            ">=",
            2,
        )
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        # Should contain GROUP BY and HAVING clauses
        self.assertIn("GROUP BY", sql_str.upper())
        self.assertIn("HAVING", sql_str.upper())
        self.assertIn("COUNT(*)", sql_str.upper())
        self.assertIn(">=", sql_str)

    def test_select_grouped_count_different_operators(self):
        """Test select_grouped_count with different operators."""
        where = SQL("1=1")

        # Test with = operator
        result = self.builder.select_grouped_count("test_table", "t", "group_col", where, "=", 3)
        self.assertIn("COUNT(*) =", str(result).upper())

        # Test with > operator
        result = self.builder.select_grouped_count("test_table", "t", "group_col", where, ">", 5)
        self.assertIn("COUNT(*) >", str(result).upper())

        # Test with < operator
        result = self.builder.select_grouped_count("test_table", "t", "group_col", where, "<", 10)
        self.assertIn("COUNT(*) <", str(result).upper())

    def test_select_grouped_count_normalizes_double_equals(self):
        """Test that == is normalized to = in HAVING clause."""
        where = SQL("1=1")
        result = self.builder.select_grouped_count("test_table", "t", "group_col", where, "==", 2)
        self.assertIsNotNone(result)
        sql_str = str(result)
        self.assertIn("HAVING", sql_str.upper())

    def test_select_ids_from_domain_empty_domain(self):
        """Test select_ids_from_domain with empty domain."""
        # Use a real model that exists in Odoo
        result = self.builder.select_ids_from_domain("res.partner", [])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        # Should contain SELECT and the table name
        self.assertIn("SELECT", sql_str.upper())
        self.assertIn("res_partner", sql_str)

    def test_select_ids_from_domain_simple_domain(self):
        """Test select_ids_from_domain with simple domain."""
        # Use a real model and a simple domain
        result = self.builder.select_ids_from_domain("res.partner", [("active", "=", True)])
        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("SELECT", sql_str.upper())
        self.assertIn("res_partner", sql_str)

    def test_select_grouped_aggregate_sum(self):
        """Test select_grouped_aggregate with SUM function."""
        child_sql = SQL("(SELECT id FROM res_partner WHERE active = true)")
        where = SQL("m.is_ended = %s", False)

        result = self.builder.select_grouped_aggregate(
            through_table="spp_group_membership",
            through_alias="m",
            child_subquery=child_sql,
            parent_col="group",
            link_col="individual",
            agg_func="SUM",
            agg_field="income",
            child_table="res_partner",
            having_op=">=",
            having_value=10000,
            where=where,
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)

        # Should contain WITH clause (CTE)
        self.assertIn("WITH", sql_str.upper())
        # Should contain JOIN
        self.assertIn("JOIN", sql_str.upper())
        # Should contain GROUP BY and HAVING
        self.assertIn("GROUP BY", sql_str.upper())
        self.assertIn("HAVING", sql_str.upper())
        # Should contain SUM
        self.assertIn("SUM", sql_str.upper())

    def test_select_grouped_aggregate_avg(self):
        """Test select_grouped_aggregate with AVG function."""
        child_sql = SQL("(SELECT id FROM res_partner)")
        result = self.builder.select_grouped_aggregate(
            through_table="test_table",
            through_alias="m",
            child_subquery=child_sql,
            parent_col="parent_id",
            link_col="child_id",
            agg_func="AVG",
            agg_field="score",
            child_table="child_table",
            having_op=">",
            having_value=75.0,
        )

        self.assertIsNotNone(result)
        sql_str = str(result)
        self.assertIn("AVG", sql_str.upper())
        self.assertIn("HAVING", sql_str.upper())

    def test_select_grouped_aggregate_min_max(self):
        """Test select_grouped_aggregate with MIN and MAX functions."""
        child_sql = SQL("(SELECT id FROM test_model)")

        # Test MIN
        result_min = self.builder.select_grouped_aggregate(
            through_table="test_table",
            through_alias="m",
            child_subquery=child_sql,
            parent_col="group_id",
            link_col="item_id",
            agg_func="MIN",
            agg_field="value",
            child_table="child_table",
            having_op=">=",
            having_value=0,
        )
        self.assertIn("MIN", str(result_min).upper())

        # Test MAX
        result_max = self.builder.select_grouped_aggregate(
            through_table="test_table",
            through_alias="m",
            child_subquery=child_sql,
            parent_col="group_id",
            link_col="item_id",
            agg_func="MAX",
            agg_field="value",
            child_table="child_table",
            having_op="<=",
            having_value=100,
        )
        self.assertIn("MAX", str(result_max).upper())

    def test_select_grouped_aggregate_without_where(self):
        """Test select_grouped_aggregate without WHERE clause."""
        child_sql = SQL("(SELECT id FROM res_partner)")
        result = self.builder.select_grouped_aggregate(
            through_table="test_table",
            through_alias="m",
            child_subquery=child_sql,
            parent_col="parent_id",
            link_col="child_id",
            agg_func="COUNT",
            agg_field="id",
            child_table="child_table",
            having_op=">=",
            having_value=1,
            where=None,  # No WHERE clause
        )

        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        # Should still generate valid SQL with 1=1 as default WHERE
        sql_str = str(result)
        self.assertIn("SELECT", sql_str.upper())


@tagged("post_install", "-at_install")
class TestSQLBuilderSetOperations(TransactionCase):
    """Test SQLBuilder set operations (INTERSECT, UNION)."""

    def setUp(self):
        super().setUp()
        self.builder = SQLBuilder(self.env)

    def test_intersect_two_queries(self):
        """Test INTERSECT with two queries."""
        query1 = SQL("(SELECT id FROM table1)")
        query2 = SQL("(SELECT id FROM table2)")
        result = self.builder.intersect([query1, query2])

        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("INTERSECT", sql_str.upper())

    def test_intersect_multiple_queries(self):
        """Test INTERSECT with multiple queries."""
        query1 = SQL("(SELECT id FROM table1)")
        query2 = SQL("(SELECT id FROM table2)")
        query3 = SQL("(SELECT id FROM table3)")
        result = self.builder.intersect([query1, query2, query3])

        self.assertIsNotNone(result)
        sql_str = str(result)
        # Should have multiple INTERSECT operations
        self.assertIn("INTERSECT", sql_str.upper())
        # Count INTERSECT occurrences - should be 2 for 3 queries
        self.assertEqual(sql_str.upper().count("INTERSECT"), 2)

    def test_intersect_single_returns_single(self):
        """Test INTERSECT with single query returns that query."""
        query = SQL("(SELECT id FROM table1)")
        result = self.builder.intersect([query])

        self.assertIsNotNone(result)
        # Should return the same query
        self.assertEqual(str(query), str(result))

    def test_intersect_empty_raises_error(self):
        """Test INTERSECT with empty list raises ValueError."""
        with self.assertRaises(ValueError):
            self.builder.intersect([])

    def test_union_two_queries(self):
        """Test UNION with two queries."""
        query1 = SQL("(SELECT id FROM table1)")
        query2 = SQL("(SELECT id FROM table2)")
        result = self.builder.union([query1, query2])

        self.assertIsNotNone(result)
        self.assertIsInstance(result, SQL)
        sql_str = str(result)
        self.assertIn("UNION", sql_str.upper())

    def test_union_multiple_queries(self):
        """Test UNION with multiple queries."""
        query1 = SQL("(SELECT id FROM table1)")
        query2 = SQL("(SELECT id FROM table2)")
        query3 = SQL("(SELECT id FROM table3)")
        result = self.builder.union([query1, query2, query3])

        self.assertIsNotNone(result)
        sql_str = str(result)
        self.assertIn("UNION", sql_str.upper())
        # Should have 2 UNION operations for 3 queries
        self.assertEqual(sql_str.upper().count("UNION"), 2)

    def test_union_single_returns_single(self):
        """Test UNION with single query returns that query."""
        query = SQL("(SELECT id FROM table1)")
        result = self.builder.union([query])

        self.assertIsNotNone(result)
        # Should return the same query
        self.assertEqual(str(query), str(result))

    def test_union_empty_raises_error(self):
        """Test UNION with empty list raises ValueError."""
        with self.assertRaises(ValueError):
            self.builder.union([])


@tagged("post_install", "-at_install")
class TestSQLBuilderHelpers(TransactionCase):
    """Test SQLBuilder helper methods."""

    def setUp(self):
        super().setUp()
        self.builder = SQLBuilder(self.env)

    def test_build_default_domain_sql_empty(self):
        """Test build_default_domain_sql with empty domain."""
        terms, success = self.builder.build_default_domain_sql("m", None)
        self.assertTrue(success)
        self.assertEqual([], terms)

        terms, success = self.builder.build_default_domain_sql("m", [])
        self.assertTrue(success)
        self.assertEqual([], terms)

    def test_build_default_domain_sql_simple_terms(self):
        """Test build_default_domain_sql with simple terms."""
        domain = [("is_ended", "=", False), ("status", "!=", "cancelled")]
        terms, success = self.builder.build_default_domain_sql("m", domain)

        self.assertTrue(success)
        self.assertEqual(2, len(terms))
        # Each term should be a SQL object
        for term in terms:
            self.assertIsInstance(term, SQL)

    def test_build_default_domain_sql_with_and_operator(self):
        """Test build_default_domain_sql with & operator."""
        domain = ["&", ("field1", "=", "value1"), ("field2", "=", "value2")]
        terms, success = self.builder.build_default_domain_sql("m", domain)

        # Should succeed - & is allowed
        self.assertTrue(success)
        # Should have 2 terms (the & operator is skipped)
        self.assertEqual(2, len(terms))

    def test_build_default_domain_sql_with_or_operator_fails(self):
        """Test build_default_domain_sql with | operator fails."""
        domain = ["|", ("field1", "=", "value1"), ("field2", "=", "value2")]
        terms, success = self.builder.build_default_domain_sql("m", domain)

        # Should fail - | is not supported
        self.assertFalse(success)
        self.assertEqual([], terms)

    def test_build_default_domain_sql_with_not_operator_fails(self):
        """Test build_default_domain_sql with ! operator fails."""
        domain = ["!", ("field1", "=", "value1")]
        terms, success = self.builder.build_default_domain_sql("m", domain)

        # Should fail - ! is not supported
        self.assertFalse(success)
        self.assertEqual([], terms)

    def test_build_default_domain_sql_unsupported_operator_fails(self):
        """Test build_default_domain_sql with unsupported operator fails."""
        domain = [("name", "like", "%test%")]
        terms, success = self.builder.build_default_domain_sql("m", domain)

        # Should fail - like is not supported
        self.assertFalse(success)
        self.assertEqual([], terms)

    def test_build_default_domain_sql_invalid_format_fails(self):
        """Test build_default_domain_sql with invalid format fails."""
        # Invalid tuple - only 2 elements
        domain = [("field", "=")]
        terms, success = self.builder.build_default_domain_sql("m", domain)

        self.assertFalse(success)
        self.assertEqual([], terms)


@tagged("post_install", "-at_install")
class TestSQLBuilderEdgeCases(TransactionCase):
    """Test edge cases and error handling."""

    def setUp(self):
        super().setUp()
        self.builder = SQLBuilder(self.env)

    def test_term_with_special_field_names(self):
        """Test term with field names that need escaping."""
        # Field names with special characters should be properly escaped
        result = self.builder.term("m", "field-name", "=", "value")
        self.assertIsNotNone(result)

    def test_select_grouped_aggregate_invalid_function(self):
        """Test select_grouped_aggregate with invalid aggregate function."""
        child_sql = SQL("(SELECT id FROM test)")
        with self.assertRaises(ValueError):
            self.builder.select_grouped_aggregate(
                through_table="test",
                through_alias="m",
                child_subquery=child_sql,
                parent_col="parent",
                link_col="child",
                agg_func="INVALID_FUNC",
                agg_field="value",
                child_table="test",
                having_op=">=",
                having_value=0,
            )

    def test_select_grouped_count_invalid_operator(self):
        """Test select_grouped_count with invalid HAVING operator."""
        where = SQL("1=1")
        with self.assertRaises(ValueError):
            self.builder.select_grouped_count(
                "test_table",
                "t",
                "group_col",
                where,
                "like",  # Invalid for HAVING
                5,
            )

    def test_select_grouped_aggregate_invalid_having_operator(self):
        """Test select_grouped_aggregate with invalid HAVING operator."""
        child_sql = SQL("(SELECT id FROM test)")
        with self.assertRaises(ValueError):
            self.builder.select_grouped_aggregate(
                through_table="test",
                through_alias="m",
                child_subquery=child_sql,
                parent_col="parent",
                link_col="child",
                agg_func="SUM",
                agg_field="value",
                child_table="test",
                having_op="child_of",  # Invalid operator
                having_value=0,
            )
