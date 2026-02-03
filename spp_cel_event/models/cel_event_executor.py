# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""CEL Executor extension for event data queries.

This module extends the CEL executor to support efficient querying of event data
through optimized SQL paths when possible, with Python fallback for complex cases.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from odoo import models
from odoo.tools.sql import SQL

from .cel_event_queryplan import EventExists, EventsAggregate, EventValueCompare

_logger = logging.getLogger(__name__)


class CelEventExecutor(models.AbstractModel):
    """CEL executor extension for event data integration."""

    _inherit = "spp.cel.executor"

    # Maximum number of partner IDs to return from a single query
    # This prevents memory exhaustion from overly broad queries
    MAX_QUERY_RESULTS = 100000

    def _execute_plan(self, model: str, plan: Any, metrics_info: list[dict[str, Any]] | None = None) -> list[int]:
        """Execute query plan with event data support.

        Extends base executor to handle EventValueCompare, EventExists, and EventsAggregate nodes.
        """
        if isinstance(plan, EventValueCompare):
            return self._exec_event_value(model, plan)
        if isinstance(plan, EventExists):
            return self._exec_event_exists(model, plan)
        if isinstance(plan, EventsAggregate):
            return self._exec_event_aggregate(model, plan)
        return super()._execute_plan(model, plan, metrics_info)

    # ══════════════════════════════════════════════════════════════════════════════
    # EventValueCompare Execution
    # ══════════════════════════════════════════════════════════════════════════════

    def _exec_event_value(self, model: str, plan: EventValueCompare) -> list[int]:
        """Execute EventValueCompare plan.

        Compares a field value from a registrant's event against a target value.
        Uses SQL fast path when possible, falls back to Python for complex cases.

        Args:
            model: Target model name (e.g., 'res.partner')
            plan: EventValueCompare query plan node

        Returns:
            List of matching record IDs
        """
        try:
            # Try SQL fast path first
            if self._can_use_sql_path(plan):
                return self._exec_event_value_sql(model, plan)
        except Exception as e:
            _logger.warning(
                "SQL path failed for EventValueCompare, falling back to Python: %s",
                e,
                exc_info=True,
            )

        # Fall back to Python path
        return self._exec_event_value_python(model, plan)

    def _can_use_sql_path(self, plan: EventValueCompare) -> bool:
        """Check if SQL fast path can be used for this plan.

        SQL path is possible when:
        - Comparison operator is supported (==, !=, >, >=, <, <=)
        - RHS is a scalar value (int, float, str, bool)
        - No complex default handling needed
        """
        # Check operator support
        if plan.op not in {"==", "!=", ">", ">=", "<", "<="}:
            return False

        # Check RHS type
        if not isinstance(plan.rhs, int | float | str | bool | None):
            return False

        # Default handling requires Python for now
        if plan.default is not None:
            return False

        return True

    def _exec_event_value_sql(self, model: str, plan: EventValueCompare) -> list[int]:
        """Execute EventValueCompare using optimized SQL.

        Builds a subquery that:
        1. Filters events by type, state, and temporal constraints
        2. Selects the appropriate event based on selection mode
        3. Extracts and compares the field value
        4. Returns matching partner IDs
        """
        # Build temporal filter SQL
        temporal_clause, temporal_args = self._build_temporal_filter(plan)

        # Build state filter SQL
        state_clause, state_args = self._build_state_filter(plan)

        # Build selection SQL (DISTINCT ON for latest/first, simple filter for active/any)
        selection_sql, selection_wrapper = self._build_selection_sql(plan)

        # Build field comparison SQL
        comparison_sql, comparison_args = self._build_field_comparison_sql(plan)

        # Assemble the complete query
        if selection_wrapper:
            # For latest/first selection modes, we need a subquery with DISTINCT ON
            sql = SQL(
                f"""
                SELECT DISTINCT latest_event.partner_id
                FROM (
                    SELECT DISTINCT ON (e.partner_id) e.*
                    FROM spp_event_data e
                    WHERE e.event_type_code = %s
                      {state_clause}
                      {temporal_clause}
                    ORDER BY e.partner_id, {selection_sql}
                ) latest_event
                WHERE {comparison_sql}
                LIMIT %s
                """,
                plan.event_type,
                *state_args,
                *temporal_args,
                *comparison_args,
                self.MAX_QUERY_RESULTS,
            )
        else:
            # For active/any modes, simpler query without subquery
            # Need to use 'e.' prefix for simple queries (no latest_event alias)
            simple_comparison_sql = comparison_sql.replace("latest_event.", "e.")
            sql = SQL(
                f"""
                SELECT DISTINCT e.partner_id
                FROM spp_event_data e
                WHERE e.event_type_code = %s
                  {state_clause}
                  {temporal_clause}
                  AND {simple_comparison_sql}
                LIMIT %s
                """,
                plan.event_type,
                *state_args,
                *temporal_args,
                *comparison_args,
                self.MAX_QUERY_RESULTS,
            )

        # Execute query
        self.env.cr.execute(sql)
        partner_ids = [row[0] for row in self.env.cr.fetchall()]

        # Warn if limit was reached
        if len(partner_ids) >= self.MAX_QUERY_RESULTS:
            _logger.warning(
                "[CEL EVENT] Query hit result limit (%d). Results may be truncated. "
                "Consider using more specific filters.",
                self.MAX_QUERY_RESULTS,
            )

        # Log operation at INFO level without PII
        _logger.info(
            "[CEL EVENT] EventValueCompare SQL: event_type=%s field=%s matches=%d",
            plan.event_type,
            plan.field_name,
            len(partner_ids),
        )
        # Log full details at DEBUG level (not shown in production)
        _logger.debug(
            "[CEL EVENT] EventValueCompare SQL details: op=%s rhs=%r",
            plan.op,
            plan.rhs,
        )

        return partner_ids

    def _exec_event_value_python(self, model: str, plan: EventValueCompare) -> list[int]:
        """Execute EventValueCompare using Python evaluation.

        Fallback path for cases where SQL is not feasible.
        """
        # Get candidate registrants
        cfg = self.env.context.get("cel_cfg") or {}
        base_domain = cfg.get("base_domain", [])
        candidate_ids = self.env[model].search(base_domain).ids

        matching_ids = []

        for partner_id in candidate_ids:
            try:
                # Find matching events
                event_domain = self._build_event_domain_python(partner_id, plan)
                events = self.env["spp.event.data"].search(event_domain)

                if not events:
                    # No matching event - check default
                    if plan.default is not None:
                        if self._compare_value(plan.default, plan.op, plan.rhs):
                            matching_ids.append(partner_id)
                    continue

                # Select appropriate event based on selection mode
                event = self._select_event(events, plan.select)
                if not event:
                    continue

                # Extract field value
                value = event.get_data_value(plan.field_name)

                # Compare
                if self._compare_value(value, plan.op, plan.rhs):
                    matching_ids.append(partner_id)

            except Exception as e:
                _logger.warning(
                    "Error evaluating EventValueCompare for partner %s: %s",
                    partner_id,
                    e,
                )
                continue

        # Log operation at INFO level without PII
        _logger.info(
            "[CEL EVENT] EventValueCompare Python: event_type=%s field=%s matches=%d",
            plan.event_type,
            plan.field_name,
            len(matching_ids),
        )
        # Log full details at DEBUG level (not shown in production)
        _logger.debug(
            "[CEL EVENT] EventValueCompare Python details: op=%s rhs=%r",
            plan.op,
            plan.rhs,
        )

        return matching_ids

    # ══════════════════════════════════════════════════════════════════════════════
    # EventExists Execution
    # ══════════════════════════════════════════════════════════════════════════════

    def _exec_event_exists(self, model: str, plan: EventExists) -> list[int]:
        """Execute EventExists plan.

        Checks if registrants have events matching the criteria.
        Always uses SQL for optimal performance.
        """
        # Build temporal filter SQL
        temporal_clause, temporal_args = self._build_temporal_filter(plan)

        # Build state filter SQL
        state_clause, state_args = self._build_state_filter(plan)

        # Simple EXISTS query
        sql = SQL(
            f"""
            SELECT DISTINCT e.partner_id
            FROM spp_event_data e
            WHERE e.event_type_code = %s
              {state_clause}
              {temporal_clause}
            LIMIT %s
            """,
            plan.event_type,
            *state_args,
            *temporal_args,
            self.MAX_QUERY_RESULTS,
        )

        # Execute query
        self.env.cr.execute(sql)
        partner_ids = [row[0] for row in self.env.cr.fetchall()]

        # Warn if limit was reached
        if len(partner_ids) >= self.MAX_QUERY_RESULTS:
            _logger.warning(
                "[CEL EVENT] Query hit result limit (%d). Results may be truncated. "
                "Consider using more specific filters.",
                self.MAX_QUERY_RESULTS,
            )

        _logger.info(
            "[CEL EVENT] EventExists SQL: event_type=%s matches=%d",
            plan.event_type,
            len(partner_ids),
        )

        return partner_ids

    # ══════════════════════════════════════════════════════════════════════════════
    # EventsAggregate Execution
    # ══════════════════════════════════════════════════════════════════════════════

    def _exec_event_aggregate(self, model: str, plan: EventsAggregate) -> list[int]:
        """Execute EventsAggregate plan.

        Aggregates values across multiple events (count, sum, avg, min, max)
        and compares against a target value.
        """
        try:
            # Try SQL path for supported aggregations
            if self._can_use_sql_aggregate(plan):
                return self._exec_event_aggregate_sql(model, plan)
        except Exception as e:
            _logger.warning(
                "SQL path failed for EventsAggregate, falling back to Python: %s",
                e,
                exc_info=True,
            )

        # Fall back to Python
        return self._exec_event_aggregate_python(model, plan)

    def _can_use_sql_aggregate(self, plan: EventsAggregate) -> bool:
        """Check if SQL path can be used for aggregation.

        SQL path is possible when:
        - Aggregation function is supported (count, sum, avg, min, max)
        - No complex where_predicate (or simple JSON field comparisons only)
        - Field type is numeric for sum/avg
        """
        # Only support basic aggregations in SQL for now
        if plan.agg not in {"count", "sum", "avg", "min", "max"}:
            return False

        # Complex where predicates need Python evaluation
        if plan.where_predicate:
            # TODO: Could support simple predicates in SQL in the future
            return False

        return True

    def _exec_event_aggregate_sql(self, model: str, plan: EventsAggregate) -> list[int]:
        """Execute EventsAggregate using optimized SQL with GROUP BY and HAVING."""
        # Build temporal filter SQL
        temporal_clause, temporal_args = self._build_temporal_filter(plan)

        # Build state filter SQL
        state_clause, state_args = self._build_state_filter(plan)

        # Build aggregation SQL
        if plan.agg == "count":
            agg_expr = "COUNT(*)"
        elif plan.field_name:
            # Validate field name to prevent SQL injection
            validated_field_name = self._validate_field_name(plan.field_name)
            # Extract field as numeric for numeric aggregations
            field_expr = f"(e.data_json->>'{validated_field_name}')::numeric"
            agg_map = {
                "sum": f"SUM({field_expr})",
                "avg": f"AVG({field_expr})",
                "min": f"MIN({field_expr})",
                "max": f"MAX({field_expr})",
            }
            agg_expr = agg_map.get(plan.agg, "COUNT(*)")
        else:
            # Field required for non-count aggregations
            agg_expr = "COUNT(*)"

        # Build HAVING clause
        op_map = {"==": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
        sql_op = op_map.get(plan.op, "=")

        # Assemble query with GROUP BY and HAVING
        sql = SQL(
            f"""
            SELECT e.partner_id
            FROM spp_event_data e
            WHERE e.event_type_code = %s
              {state_clause}
              {temporal_clause}
            GROUP BY e.partner_id
            HAVING {agg_expr} {sql_op} %s
            LIMIT %s
            """,
            plan.event_type,
            *state_args,
            *temporal_args,
            plan.rhs,
            self.MAX_QUERY_RESULTS,
        )

        # Execute query
        self.env.cr.execute(sql)
        partner_ids = [row[0] for row in self.env.cr.fetchall()]

        # Warn if limit was reached
        if len(partner_ids) >= self.MAX_QUERY_RESULTS:
            _logger.warning(
                "[CEL EVENT] Query hit result limit (%d). Results may be truncated. "
                "Consider using more specific filters.",
                self.MAX_QUERY_RESULTS,
            )

        # Log operation at INFO level without PII
        _logger.info(
            "[CEL EVENT] EventsAggregate SQL: event_type=%s agg=%s field=%s matches=%d",
            plan.event_type,
            plan.agg,
            plan.field_name,
            len(partner_ids),
        )
        # Log full details at DEBUG level (not shown in production)
        _logger.debug(
            "[CEL EVENT] EventsAggregate SQL details: op=%s rhs=%r",
            plan.op,
            plan.rhs,
        )

        return partner_ids

    def _exec_event_aggregate_python(self, model: str, plan: EventsAggregate) -> list[int]:
        """Execute EventsAggregate using Python evaluation.

        Fallback path for complex aggregations with where predicates.
        """
        # Get candidate registrants
        cfg = self.env.context.get("cel_cfg") or {}
        base_domain = cfg.get("base_domain", [])
        candidate_ids = self.env[model].search(base_domain).ids

        matching_ids = []

        for partner_id in candidate_ids:
            try:
                # Find matching events
                event_domain = self._build_event_domain_python(partner_id, plan)
                events = self.env["spp.event.data"].search(event_domain)

                if not events:
                    # No events - aggregation result depends on function
                    if plan.agg == "count":
                        agg_value = 0
                    else:
                        continue  # No value for sum/avg/min/max
                else:
                    # Apply where predicate if present
                    if plan.where_predicate:
                        # TODO: Evaluate where_predicate on events
                        # For now, skip events with predicates in Python path
                        _logger.warning(
                            "where_predicate not yet implemented in Python path: %s",
                            plan.where_predicate,
                        )
                        continue

                    # Compute aggregation
                    agg_value = self._compute_aggregation(events, plan.agg, plan.field_name)

                # Compare result
                if self._compare_value(agg_value, plan.op, plan.rhs):
                    matching_ids.append(partner_id)

            except Exception as e:
                _logger.warning(
                    "Error evaluating EventsAggregate for partner %s: %s",
                    partner_id,
                    e,
                )
                continue

        _logger.info(
            "[CEL EVENT] EventsAggregate Python: event_type=%s agg=%s field=%s matches=%d",
            plan.event_type,
            plan.agg,
            plan.field_name,
            len(matching_ids),
        )

        return matching_ids

    # ══════════════════════════════════════════════════════════════════════════════
    # SQL Building Helpers
    # ══════════════════════════════════════════════════════════════════════════════

    def _build_temporal_filter(self, plan: EventValueCompare | EventExists | EventsAggregate) -> tuple[str, list[Any]]:
        """Build SQL temporal filter clause and arguments.

        Returns:
            Tuple of (sql_clause, args_list)
            sql_clause: SQL fragment like "AND e.collection_date >= %s"
            args_list: List of argument values
        """
        clauses = []
        args = []

        # Handle after
        if plan.after:
            clauses.append("AND e.collection_date >= %s")
            args.append(plan.after)

        # Handle before
        if plan.before:
            clauses.append("AND e.collection_date <= %s")
            args.append(plan.before)

        # Handle within_days
        if plan.within_days:
            clauses.append("AND e.collection_date >= CURRENT_DATE - INTERVAL '%s days'")
            args.append(plan.within_days)

        # Handle within_months
        if plan.within_months:
            clauses.append("AND e.collection_date >= CURRENT_DATE - INTERVAL '%s months'")
            args.append(plan.within_months)

        # Handle period (named periods like '2024', '2024-Q1')
        if plan.period:
            period_start, period_end = self._parse_period(plan.period)
            if period_start:
                clauses.append("AND e.collection_date >= %s")
                args.append(period_start)
            if period_end:
                clauses.append("AND e.collection_date <= %s")
                args.append(period_end)

        return " ".join(clauses), args

    def _build_state_filter(self, plan: EventValueCompare | EventExists | EventsAggregate) -> tuple[str, list[Any]]:
        """Build SQL state filter clause and arguments.

        Returns:
            Tuple of (sql_clause, args_list)
        """
        if plan.states:
            # Explicit states
            placeholders = ", ".join(["%s"] * len(plan.states))
            return f"AND e.state IN ({placeholders})", list(plan.states)

        # Default states based on selection mode
        if isinstance(plan, EventValueCompare):
            default_states = self._get_default_states(plan.select)
        else:
            # For EventExists and EventsAggregate, default to active only
            default_states = ["active"]

        placeholders = ", ".join(["%s"] * len(default_states))
        return f"AND e.state IN ({placeholders})", default_states

    def _build_selection_sql(self, plan: EventValueCompare) -> tuple[str, bool]:
        """Build SQL for event selection mode.

        Returns:
            Tuple of (order_clause, needs_wrapper)
            order_clause: SQL ORDER BY clause
            needs_wrapper: True if DISTINCT ON subquery needed
        """
        select_mode = plan.select if plan.select != "auto" else self._resolve_select_mode(plan.event_type)

        if select_mode == "latest":
            return "e.collection_date DESC, e.id DESC", True
        elif select_mode == "latest_active":
            return "e.collection_date DESC, e.id DESC", True
        elif select_mode == "first":
            return "e.collection_date ASC, e.id ASC", True
        elif select_mode in ("active", "any"):
            # No ordering needed, simple filter
            return "", False

        # Default to latest
        return "e.collection_date DESC, e.id DESC", True

    def _build_field_comparison_sql(self, plan: EventValueCompare) -> tuple[str, list[Any]]:
        """Build SQL for field value comparison.

        Returns:
            Tuple of (comparison_clause, args_list)
        """
        # Validate field name to prevent SQL injection
        field_name = self._validate_field_name(plan.field_name)
        op = plan.op
        rhs = plan.rhs

        # Map operators
        op_map = {"==": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
        sql_op = op_map.get(op, "=")

        # Handle different value types
        if isinstance(rhs, bool):
            # Boolean comparison
            clause = f"(latest_event.data_json->>'{field_name}')::boolean {sql_op} %s"
            return clause, [rhs]
        elif isinstance(rhs, int | float):
            # Numeric comparison
            clause = f"(latest_event.data_json->>'{field_name}')::numeric {sql_op} %s"
            return clause, [rhs]
        elif isinstance(rhs, str):
            # String comparison
            clause = f"(latest_event.data_json->>'{field_name}') {sql_op} %s"
            return clause, [rhs]
        elif rhs is None:
            # NULL comparison
            if op == "==":
                clause = f"(latest_event.data_json->>'{field_name}') IS NULL"
            else:
                clause = f"(latest_event.data_json->>'{field_name}') IS NOT NULL"
            return clause, []

        # Fallback
        clause = f"(latest_event.data_json->>'{field_name}') {sql_op} %s::text"
        return clause, [str(rhs)]

    # ══════════════════════════════════════════════════════════════════════════════
    # Python Evaluation Helpers
    # ══════════════════════════════════════════════════════════════════════════════

    def _build_event_domain_python(
        self, partner_id: int, plan: EventValueCompare | EventExists | EventsAggregate
    ) -> list[Any]:
        """Build Odoo domain for finding matching events.

        Args:
            partner_id: Registrant partner ID
            plan: Query plan node

        Returns:
            Odoo domain as list
        """
        domain = [
            ("partner_id", "=", partner_id),
            ("event_type_code", "=", plan.event_type),
        ]

        # State filter
        if plan.states:
            domain.append(("state", "in", plan.states))
        elif isinstance(plan, EventValueCompare):
            default_states = self._get_default_states(plan.select)
            domain.append(("state", "in", default_states))
        else:
            domain.append(("state", "=", "active"))

        # Temporal filters
        if plan.after:
            domain.append(("collection_date", ">=", plan.after))
        if plan.before:
            domain.append(("collection_date", "<=", plan.before))
        if plan.within_days:
            cutoff = date.today() - timedelta(days=plan.within_days)
            domain.append(("collection_date", ">=", cutoff))
        if plan.within_months:
            # Approximate: 30 days per month
            cutoff = date.today() - timedelta(days=plan.within_months * 30)
            domain.append(("collection_date", ">=", cutoff))
        if plan.period:
            period_start, period_end = self._parse_period(plan.period)
            if period_start:
                domain.append(("collection_date", ">=", period_start))
            if period_end:
                domain.append(("collection_date", "<=", period_end))

        return domain

    def _select_event(self, events, select_mode: str):
        """Select appropriate event from recordset based on selection mode.

        Args:
            events: Recordset of spp.event.data
            select_mode: Selection mode string

        Returns:
            Single event record or False
        """
        if not events:
            return False

        if select_mode == "auto":
            select_mode = "latest"  # Default

        if select_mode == "active":
            # Return first active (should be only one)
            active = events.filtered(lambda e: e.state == "active")
            return active[0] if active else False
        elif select_mode == "latest":
            # Most recent by collection_date
            return events.sorted(lambda e: (e.collection_date, e.id), reverse=True)[0]
        elif select_mode == "latest_active":
            # Most recent among active
            active = events.filtered(lambda e: e.state == "active")
            if active:
                return active.sorted(lambda e: (e.collection_date, e.id), reverse=True)[0]
            return False
        elif select_mode == "first":
            # Earliest by collection_date
            return events.sorted(lambda e: (e.collection_date, e.id))[0]
        elif select_mode == "any":
            # Any event (first in recordset)
            return events[0]

        # Default: latest
        return events.sorted(lambda e: (e.collection_date, e.id), reverse=True)[0]

    def _compute_aggregation(self, events, agg: str, field_name: str | None) -> Any:
        """Compute aggregation over events.

        Args:
            events: Recordset of spp.event.data
            agg: Aggregation function name
            field_name: Field to aggregate (None for count)

        Returns:
            Aggregated value
        """
        if agg == "count":
            return len(events)

        if not field_name:
            return 0

        # Extract field values
        values = []
        for event in events:
            val = event.get_data_value(field_name)
            if val is not None:
                try:
                    # Try to convert to numeric
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass

        if not values:
            return 0

        if agg == "sum":
            return sum(values)
        elif agg == "avg":
            return sum(values) / len(values)
        elif agg == "min":
            return min(values)
        elif agg == "max":
            return max(values)

        return 0

    def _compare_value(self, a: Any, op: str, b: Any) -> bool:
        """Compare two values with given operator.

        Args:
            a: Left-hand side value
            b: Right-hand side value
            op: Comparison operator

        Returns:
            True if comparison holds, False otherwise
        """
        # Handle None
        if a is None:
            return (op == "==" and b is None) or (op == "!=" and b is not None)

        # Try numeric comparison first
        try:
            a_num = float(a) if not isinstance(a, bool) else a
            b_num = float(b) if not isinstance(b, bool) else b
            ops = {
                "==": lambda x, y: x == y,
                "!=": lambda x, y: x != y,
                ">": lambda x, y: x > y,
                ">=": lambda x, y: x >= y,
                "<": lambda x, y: x < y,
                "<=": lambda x, y: x <= y,
            }
            return ops[op](a_num, b_num)
        except (ValueError, TypeError, KeyError):
            pass

        # Fall back to string comparison
        try:
            ops = {
                "==": lambda x, y: x == y,
                "!=": lambda x, y: x != y,
            }
            return ops.get(op, lambda x, y: False)(str(a), str(b))
        except Exception:
            return False

    # ══════════════════════════════════════════════════════════════════════════════
    # Utility Helpers
    # ══════════════════════════════════════════════════════════════════════════════

    def _validate_field_name(self, field_name: str) -> str:
        """Validate and sanitize field name to prevent SQL injection.

        Args:
            field_name: The field name to validate

        Returns:
            The validated field name

        Raises:
            ValueError: If field name is invalid
        """
        import re

        if not field_name or not isinstance(field_name, str):
            raise ValueError("Field name must be a non-empty string")

        # Only allow valid identifier characters
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", field_name):
            raise ValueError(f"Invalid field name: {field_name!r}. Only alphanumeric and underscore allowed.")

        return field_name

    def _get_default_states(self, select_mode: str) -> list[str]:
        """Get default states for a selection mode.

        Args:
            select_mode: Selection mode string

        Returns:
            List of state strings
        """
        if select_mode in ("active", "latest_active"):
            return ["active"]
        elif select_mode in ("latest", "first"):
            return ["active", "superseded", "expired"]
        elif select_mode == "any":
            return ["active"]

        # Default: include historical states
        return ["active", "superseded", "expired"]

    def _resolve_select_mode(self, event_type_code: str) -> str:
        """Resolve 'auto' select mode to actual mode based on event type config.

        Args:
            event_type_code: Event type code

        Returns:
            Resolved selection mode
        """
        try:
            event_type = self.env["spp.event.type"].search([("code", "=", event_type_code)], limit=1)
            if event_type and event_type.is_one_active_per_registrant:
                return "active"
        except Exception as e:
            _logger.warning("Error resolving select mode for event type %s: %s", event_type_code, e)

        # Default to latest
        return "latest"

    def _parse_period(self, period: str) -> tuple[date | None, date | None]:
        """Parse named period to date range.

        Args:
            period: Period string (e.g., '2024', '2024-Q1', '2024-03')

        Returns:
            Tuple of (start_date, end_date)
        """
        try:
            # Full year: YYYY
            if len(period) == 4 and period.isdigit():
                year = int(period)
                return date(year, 1, 1), date(year, 12, 31)

            # Quarter: YYYY-QN
            if len(period) == 7 and period[4] == "-" and period[5] == "Q":
                year = int(period[:4])
                quarter = int(period[6])
                if quarter == 1:
                    return date(year, 1, 1), date(year, 3, 31)
                elif quarter == 2:
                    return date(year, 4, 1), date(year, 6, 30)
                elif quarter == 3:
                    return date(year, 7, 1), date(year, 9, 30)
                elif quarter == 4:
                    return date(year, 10, 1), date(year, 12, 31)

            # Month: YYYY-MM
            if len(period) == 7 and period[4] == "-":
                year = int(period[:4])
                month = int(period[5:7])
                # Calculate last day of month
                if month == 12:
                    next_month = date(year + 1, 1, 1)
                else:
                    next_month = date(year, month + 1, 1)
                last_day = next_month - timedelta(days=1)
                return date(year, month, 1), last_day

            # TODO: Support more formats (YYYY-HN, YYYY-WNN)

        except Exception as e:
            _logger.warning("Error parsing period '%s': %s", period, e)

        return None, None
