"""SQL Builder module for CEL Domain SQL generation.

This module provides composable SQL query building utilities using Odoo's SQL class.
All methods return SQL objects or None if conversion is not possible.
All subqueries use expression.expression() to include record rules automatically.

Per SPEC_SQL_SCALABILITY.md v2.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from odoo.tools.sql import SQL

if TYPE_CHECKING:
    from odoo.api import Environment

_logger = logging.getLogger("odoo.addons.spp_cel_domain.sql_builder")

# Operators supported for SQL term generation
SUPPORTED_COMPARISON_OPS = {"=", "!=", ">", ">=", "<", "<=", "=="}
SUPPORTED_LIST_OPS = {"in", "not in"}
UNSUPPORTED_OPS = {"like", "ilike", "=like", "=ilike", "child_of", "parent_of"}


class SQLBuilder:
    """Composable SQL query builder using Odoo's SQL class.

    All methods return SQL objects or None if conversion not possible.
    All subqueries use expression.expression() to include record rules.
    """

    def __init__(self, env: Environment):
        self.env = env

    # =========================================================================
    # Term Builder
    # =========================================================================

    def term(self, alias: str, field: str, op: str, value: Any) -> SQL | None:
        """Convert a single comparison to SQL.

        Supported operators: =, !=, >, >=, <, <=, in, not in
        NULL handling: = None becomes IS NULL, != None becomes IS NOT NULL

        Returns None for unsupported operators (like, ilike, child_of).

        Examples:
            term("m", "is_ended", "=", False)    -> SQL("m.is_ended = %s", False)
            term("m", "status", "!=", "ended")   -> SQL("m.status != %s", "ended")
            term("m", "count", ">=", 5)          -> SQL("m.count >= %s", 5)
            term("m", "field", "=", None)        -> SQL("m.field IS NULL")
            term("m", "ids", "in", [1,2,3])      -> SQL("m.ids IN %s", (1,2,3))
            term("m", "name", "like", "%x%")     -> None (unsupported)
        """
        # Normalize operator
        normalized_op = "=" if op == "==" else op

        # Check for unsupported operators
        if normalized_op in UNSUPPORTED_OPS:
            return None

        # Validate operator is one we support
        if normalized_op not in SUPPORTED_COMPARISON_OPS and normalized_op not in SUPPORTED_LIST_OPS:
            return None

        # Build the qualified field reference
        field_ref = SQL("%s.%s", SQL.identifier(alias), SQL.identifier(field))

        # Handle NULL comparisons
        if value is None:
            if normalized_op == "=":
                return SQL("%s IS NULL", field_ref)
            elif normalized_op == "!=":
                return SQL("%s IS NOT NULL", field_ref)
            else:
                # Other ops with NULL don't make sense
                return None

        # Handle list operators
        if normalized_op == "in":
            if not value:
                # Empty list: no records match
                return SQL("1=0")
            # Convert to tuple for SQL IN clause
            return SQL("%s IN %s", field_ref, tuple(value))

        if normalized_op == "not in":
            if not value:
                # Empty list: all records match
                return SQL("1=1")
            return SQL("%s NOT IN %s", field_ref, tuple(value))

        # Handle regular comparison operators
        op_sql_map = {
            "=": "=",
            "!=": "!=",
            ">": ">",
            ">=": ">=",
            "<": "<",
            "<=": "<=",
        }

        sql_op = op_sql_map.get(normalized_op)
        if sql_op is None:
            return None

        return SQL("%s " + sql_op + " %s", field_ref, value)

    # =========================================================================
    # WHERE Clause Builder
    # =========================================================================

    def where_and(self, conditions: list[SQL]) -> SQL:
        """Combine conditions with AND.

        Empty list returns SQL("1=1").
        Single condition returns that condition.
        Multiple conditions combined with AND.
        """
        if not conditions:
            return SQL("1=1")

        if len(conditions) == 1:
            return conditions[0]

        result = conditions[0]
        for cond in conditions[1:]:
            result = SQL("%s AND %s", result, cond)
        return result

    def where_or(self, conditions: list[SQL]) -> SQL:
        """Combine conditions with OR.

        Empty list returns SQL("1=0") (nothing matches).
        Single condition returns that condition.
        Multiple conditions combined with OR.
        """
        if not conditions:
            return SQL("1=0")

        if len(conditions) == 1:
            return conditions[0]

        result = conditions[0]
        for cond in conditions[1:]:
            result = SQL("(%s OR %s)", result, cond)
        return result

    # =========================================================================
    # SELECT Builders
    # =========================================================================

    def select_ids_from_domain(self, model: str, domain: list[Any]) -> SQL | None:
        """Generate SELECT id FROM model WHERE domain.

        Uses expression.expression() to include record rules.
        Uses Query.select() to include all necessary JOINs (e.g. for
        related field lookups like gender_id.uri).
        Returns None if domain cannot be converted.

        This is the PRIMARY method for generating subqueries.
        All other methods should use this for model references.
        """
        try:
            from odoo.osv import expression as osv_expression

            Model = self.env[model]
            table = Model._table

            # Build the expression (applies record rules even for empty domain)
            expr = osv_expression.expression(model=Model, domain=domain or [])
            query = expr.query

            # Use query.select() to get the full SQL including FROM clause
            # with all JOINs (needed for related field domains like gender_id.uri)
            select_sql = query.select(SQL.identifier(table, "id"))

            return SQL("(%s)", select_sql)
        except Exception as e:
            _logger.debug("[SQLBuilder] Failed to convert domain to SQL: %s", e)
            return None

    def select_distinct_column(self, table: str, alias: str, column: str, where: SQL) -> SQL:
        """SELECT DISTINCT column FROM table WHERE ...

        Used for ExistsThrough to get parent IDs.
        """
        return SQL(
            "(SELECT DISTINCT %s.%s FROM %s %s WHERE %s)",
            SQL.identifier(alias),
            SQL.identifier(column),
            SQL.identifier(table),
            SQL.identifier(alias),
            where,
        )

    def select_grouped_count(
        self,
        table: str,
        alias: str,
        group_col: str,
        where: SQL,
        having_op: str,
        having_value: int,
    ) -> SQL:
        """SELECT with GROUP BY and HAVING COUNT(*).

        Used for CountThrough.

        Example:
            select_grouped_count(
                "spp_group_membership", "m", "group",
                where=SQL("m.is_ended = false"),
                having_op=">=", having_value=2
            )
            -> SELECT m.group FROM spp_group_membership m
               WHERE m.is_ended = false
               GROUP BY m.group
               HAVING COUNT(*) >= 2
        """
        # Normalize operator
        op_map = {
            "==": "=",
            "=": "=",
            "!=": "!=",
            ">": ">",
            ">=": ">=",
            "<": "<",
            "<=": "<=",
        }
        sql_op = op_map.get(having_op)
        if sql_op is None:
            raise ValueError(f"Unsupported operator for HAVING: {having_op}")

        return SQL(
            "(SELECT %s.%s FROM %s %s WHERE %s GROUP BY %s.%s HAVING COUNT(*) %s %s)",
            SQL.identifier(alias),
            SQL.identifier(group_col),
            SQL.identifier(table),
            SQL.identifier(alias),
            where,
            SQL.identifier(alias),
            SQL.identifier(group_col),
            SQL(sql_op),
            having_value,
        )

    def select_grouped_aggregate(
        self,
        through_table: str,
        through_alias: str,
        child_subquery: SQL,
        parent_col: str,
        link_col: str,
        agg_func: str,
        agg_field: str,
        child_table: str,
        having_op: str,
        having_value: float | int,
        where: SQL | None = None,
    ) -> SQL:
        """SELECT with aggregate function on joined data.

        Used for FieldAggregateThrough (sum, avg, min, max).

        IMPORTANT: child_subquery must come from select_ids_from_domain()
        to ensure record rules are applied.

        Uses CTE pattern for clarity and correctness:
            WITH allowed_members AS (
                SELECT id, {agg_field} FROM {child_table}
                WHERE id IN {child_subquery}
            )
            SELECT m.{parent_col} FROM {through_table} m
            JOIN allowed_members c ON c.id = m.{link_col}
            WHERE {where}
            GROUP BY m.{parent_col}
            HAVING {agg_func}(c.{agg_field}) {having_op} {having_value}
        """
        # Validate aggregate function
        agg_func = agg_func.upper()
        if agg_func not in {"SUM", "AVG", "MIN", "MAX", "COUNT"}:
            raise ValueError(f"Unsupported aggregate function: {agg_func}")

        # Normalize operator
        op_map = {
            "==": "=",
            "=": "=",
            "!=": "!=",
            ">": ">",
            ">=": ">=",
            "<": "<",
            "<=": "<=",
        }
        sql_op = op_map.get(having_op)
        if sql_op is None:
            raise ValueError(f"Unsupported operator for HAVING: {having_op}")

        # Build WHERE clause for through table
        where_clause = where if where else SQL("1=1")

        # Use CTE pattern for cleaner SQL and correct record rule application
        # COALESCE handles NULL values from aggregate functions (e.g., SUM(NULL) = NULL)
        return SQL(
            """(WITH allowed_children AS (
                SELECT id, %s FROM %s WHERE id IN %s
            )
            SELECT %s.%s FROM %s %s
            JOIN allowed_children c ON c.id = %s.%s
            WHERE %s
            GROUP BY %s.%s
            HAVING COALESCE(%s(c.%s), 0) %s %s)""",
            SQL.identifier(agg_field),
            SQL.identifier(child_table),
            child_subquery,
            SQL.identifier(through_alias),
            SQL.identifier(parent_col),
            SQL.identifier(through_table),
            SQL.identifier(through_alias),
            SQL.identifier(through_alias),
            SQL.identifier(link_col),
            where_clause,
            SQL.identifier(through_alias),
            SQL.identifier(parent_col),
            SQL(agg_func),
            SQL.identifier(agg_field),
            SQL(sql_op),
            having_value,
        )

    # =========================================================================
    # Set Operations
    # =========================================================================

    def intersect(self, queries: list[SQL]) -> SQL:
        """Combine queries with INTERSECT (for AND)."""
        if not queries:
            raise ValueError("Cannot INTERSECT empty list of queries")

        if len(queries) == 1:
            return queries[0]

        result = queries[0]
        for query in queries[1:]:
            result = SQL("(%s INTERSECT %s)", result, query)
        return result

    def union(self, queries: list[SQL]) -> SQL:
        """Combine queries with UNION (for OR)."""
        if not queries:
            raise ValueError("Cannot UNION empty list of queries")

        if len(queries) == 1:
            return queries[0]

        result = queries[0]
        for query in queries[1:]:
            result = SQL("(%s UNION %s)", result, query)
        return result

    # =========================================================================
    # CASE WHEN Builder
    # =========================================================================

    def case_when(self, condition: SQL, then_expr: SQL, else_expr: SQL) -> SQL:
        """Build a CASE WHEN ... THEN ... ELSE ... END expression.

        Args:
            condition: SQL boolean expression for the WHEN clause
            then_expr: SQL expression for the THEN result
            else_expr: SQL expression for the ELSE result

        Returns:
            SQL CASE expression
        """
        return SQL("CASE WHEN %s THEN %s ELSE %s END", condition, then_expr, else_expr)

    def comparison(self, left: SQL, op: str, right: SQL) -> SQL | None:
        """Build a SQL comparison expression from two SQL operands.

        Uses operator whitelist to prevent injection (same pattern as term()).

        Args:
            left: Left-hand SQL expression
            op: Comparison operator (=, !=, >, >=, <, <=)
            right: Right-hand SQL expression

        Returns:
            SQL comparison or None if operator is unsupported
        """
        op_sql_map = {"=": "=", "==": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
        sql_op = op_sql_map.get(op)
        if sql_op is None:
            return None
        return SQL("%s " + sql_op + " %s", left, right)

    # =========================================================================
    # Helpers for Default Domain Processing
    # =========================================================================

    def build_default_domain_sql(self, alias: str, default_domain: list[Any] | None) -> tuple[list[SQL], bool]:
        """Convert default_domain list to SQL terms.

        Returns:
            (list of SQL terms, success flag)
            If success is False, caller should fall back to Python path.
        """
        if not default_domain:
            return [], True

        terms: list[SQL] = []
        for item in default_domain:
            if isinstance(item, tuple | list) and len(item) == 3:
                field, op, value = item
                term_sql = self.term(alias, field, op, value)
                if term_sql is None:
                    # Unsupported operator
                    return [], False
                terms.append(term_sql)
            elif item in ("&", "|", "!"):
                # Domain operators - we only support simple AND chains
                if item != "&":
                    return [], False
            else:
                # Unknown format
                return [], False

        return terms, True
