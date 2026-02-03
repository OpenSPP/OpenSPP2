# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""CEL Translator Extension for Event Data Integration.

This module extends the base CEL translator to handle event-related functions,
enabling CEL expressions to query and filter based on event data.

Supported Functions:
    - event(): Access event data with selection and filtering
    - has_event(): Check event existence
    - events_count(): Count matching events
    - events_sum/avg/min/max(): Aggregate event field values
    - Period helpers: this_year(), last_year(), this_quarter(), etc.
"""

import logging
from datetime import date
from typing import Any

from odoo import api, fields, models

from odoo.addons.spp_cel_domain.services import cel_parser as P

from . import cel_event_functions as event_funcs
from .cel_event_queryplan import (
    EventExists,
    EventFieldRef,
    EventsAggregate,
    EventValueCompare,
)

_logger = logging.getLogger(__name__)


class CelEventTranslator(models.AbstractModel):
    """CEL Translator extension for event data integration.

    Extends the base CEL translator to handle event-related functions by
    intercepting function calls and translating them to event-specific
    query plan nodes.
    """

    _inherit = "spp.cel.translator"

    def _to_plan(self, model: str, node: Any, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Translate CEL AST to query plan, handling event functions.

        This override intercepts event-related function calls before delegating
        to the parent translator for standard operations.

        Args:
            model: Target model name
            node: CEL AST node
            cfg: Configuration with symbols and settings
            ctx: Translation context

        Returns:
            Tuple of (plan_node, explanation_string)
        """
        # Handle comparisons involving event field references or aggregates
        if isinstance(node, P.Compare):
            # Check if left side is an event field reference
            if self._is_event_field_access(node.left):
                return self._handle_event_field_compare(model, node, cfg, ctx)

            # Check if left side is an aggregate function
            if isinstance(node.left, P.Call) and isinstance(node.left.func, P.Ident):
                func_name = node.left.func.name
                if func_name in ("events_count", "events_sum", "events_avg", "events_min", "events_max"):
                    return self._handle_aggregate_compare(model, node, cfg, ctx)

        # Handle function calls
        if isinstance(node, P.Call) and isinstance(node.func, P.Ident):
            func_name = node.func.name

            # Event data access functions
            if func_name == "event":
                return self._handle_event_call(model, node, cfg, ctx)
            elif func_name == "has_event":
                return self._handle_has_event(model, node, cfg, ctx)

            # Event aggregation functions (when used alone, not in comparison)
            elif func_name in ("events_count", "events_sum", "events_avg", "events_min", "events_max"):
                return self._handle_events_aggregate(model, node, cfg, ctx)

            # Period helper functions
            elif func_name in (
                "this_year",
                "last_year",
                "this_quarter",
                "last_quarter",
                "this_month",
                "last_month",
                "quarters_ago",
                "months_ago",
            ):
                return self._handle_period_function(model, node, cfg, ctx)

        # Delegate to parent translator for non-event operations
        return super()._to_plan(model, node, cfg, ctx)

    def _is_event_field_access(self, node: Any) -> bool:
        """Check if node represents event field access (event().field or event('type', 'field')).

        Args:
            node: CEL AST node

        Returns:
            True if node is an event field access pattern
        """
        # Pattern 1: event('type').field or event('type', ...).field
        if isinstance(node, P.Attr) and isinstance(node.obj, P.Call):
            if isinstance(node.obj.func, P.Ident) and node.obj.func.name == "event":
                return True

        # Pattern 2: event('type', 'field')
        if isinstance(node, P.Call) and isinstance(node.func, P.Ident):
            if node.func.name == "event" and len(node.args) >= 2:
                # Second arg is a field name string
                if isinstance(node.args[1], P.Literal) and isinstance(node.args[1].value, str):
                    return True

        return False

    def _handle_event_call(self, model: str, node: P.Call, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Handle event() function call.

        Syntax:
            event(type, field?, select=..., after=..., before=..., within_days=...,
                  within_months=..., period=..., states=..., default=...)

        Args:
            model: Target model name
            node: Call node for event()
            cfg: Configuration
            ctx: Translation context

        Returns:
            Tuple of (EventFieldRef, explanation) if no field specified yet,
            or delegates to comparison handler if complete
        """
        if not node.args:
            raise ValueError("event() requires at least an event type argument")

        # Parse arguments
        event_type = self._eval_literal(node.args[0], ctx)
        if not isinstance(event_type, str):
            raise TypeError(f"event() type must be string, got {type(event_type)}")

        field_name = None
        if len(node.args) >= 2:
            # Check if second arg is a field name (string literal)
            if isinstance(node.args[1], P.Literal) and isinstance(node.args[1].value, str):
                field_name = node.args[1].value

        # Parse named parameters (if any)
        params = self._extract_event_parameters(node, ctx, start_index=2 if field_name else 1)

        # Build EventFieldRef as intermediate representation
        event_ref = EventFieldRef(
            event_type=event_type,
            field_name=field_name,
            select=params.get("select", "auto"),
            after=params.get("after"),
            before=params.get("before"),
            within_days=params.get("within_days"),
            within_months=params.get("within_months"),
            period=params.get("period"),
            states=params.get("states"),
            default=params.get("default"),
        )

        # Store in context for later use if attribute access follows
        explain = f"event({event_type}"
        if field_name:
            explain += f", {field_name}"
        if params:
            explain += f", {params}"
        explain += ")"

        return event_ref, explain

    def _handle_event_field_compare(self, model: str, cmp: P.Compare, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Handle comparison with event field reference.

        Converts: event('type').field > value
        Into: EventValueCompare

        Args:
            model: Target model name
            cmp: Compare node
            cfg: Configuration
            ctx: Translation context

        Returns:
            Tuple of (EventValueCompare, explanation)
        """
        left = cmp.left
        field_name = None
        event_ref = None

        # Pattern 1: event('type').field
        if isinstance(left, P.Attr) and isinstance(left.obj, P.Call):
            if isinstance(left.obj.func, P.Ident) and left.obj.func.name == "event":
                # Get the event reference
                event_ref, _ = self._handle_event_call(model, left.obj, cfg, ctx)
                field_name = left.name

        # Pattern 2: event('type', 'field')
        elif isinstance(left, P.Call) and isinstance(left.func, P.Ident):
            if left.func.name == "event":
                event_ref, _ = self._handle_event_call(model, left, cfg, ctx)
                if isinstance(event_ref, EventFieldRef) and event_ref.field_name:
                    field_name = event_ref.field_name

        if not event_ref or not field_name:
            # Not an event field comparison, delegate to parent
            return super()._to_plan(model, cmp, cfg, ctx)

        # Evaluate right-hand side
        rhs = self._eval_literal(cmp.right, ctx)

        # Map operator
        op_map = {"EQ": "==", "NE": "!=", "GT": ">", "GE": ">=", "LT": "<", "LE": "<="}
        op = op_map.get(cmp.op, cmp.op)

        # Build EventValueCompare plan
        plan = EventValueCompare(
            event_type=event_ref.event_type,
            field_name=field_name,
            op=op,
            rhs=rhs,
            select=event_ref.select,
            after=event_ref.after,
            before=event_ref.before,
            within_days=event_ref.within_days,
            within_months=event_ref.within_months,
            period=event_ref.period,
            states=event_ref.states,
            default=event_ref.default,
        )

        explain = f"event({event_ref.event_type}).{field_name} {op} {rhs}"
        return plan, explain

    def _handle_has_event(self, model: str, node: P.Call, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Handle has_event() function.

        Syntax:
            has_event(type, after=..., before=..., within_days=..., within_months=..., period=..., states=...)

        Args:
            model: Target model name
            node: Call node for has_event()
            cfg: Configuration
            ctx: Translation context

        Returns:
            Tuple of (EventExists, explanation)
        """
        if not node.args:
            raise ValueError("has_event() requires an event type argument")

        event_type = self._eval_literal(node.args[0], ctx)
        if not isinstance(event_type, str):
            raise TypeError(f"has_event() type must be string, got {type(event_type)}")

        # Parse parameters
        params = self._extract_event_parameters(node, ctx, start_index=1)

        plan = EventExists(
            event_type=event_type,
            after=params.get("after"),
            before=params.get("before"),
            within_days=params.get("within_days"),
            within_months=params.get("within_months"),
            period=params.get("period"),
            states=params.get("states", ["active"]),  # Default to active events
        )

        explain = f"has_event({event_type}"
        if params:
            explain += f", {params}"
        explain += ")"

        return plan, explain

    def _handle_events_aggregate(self, model: str, node: P.Call, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Handle events_count/sum/avg/min/max() functions.

        Syntax:
            events_count(type, [filters...])
            events_sum(type, field, [filters...])
            events_avg(type, field, [filters...])
            events_min(type, field, [filters...])
            events_max(type, field, [filters...])

        Note: This returns an intermediate node. It must be compared with a value
        to form a complete query plan.

        Args:
            model: Target model name
            node: Call node
            cfg: Configuration
            ctx: Translation context

        Returns:
            Tuple of (EventsAggregate, explanation)
        """
        func_name = node.func.name
        agg_type = func_name.replace("events_", "")  # count, sum, avg, min, max

        if not node.args:
            raise ValueError(f"{func_name}() requires at least an event type argument")

        event_type = self._eval_literal(node.args[0], ctx)
        if not isinstance(event_type, str):
            raise TypeError(f"{func_name}() type must be string, got {type(event_type)}")

        # For sum/avg/min/max, field_name is second argument
        field_name = None
        param_start_index = 1

        if agg_type in ("sum", "avg", "min", "max"):
            if len(node.args) < 2:
                raise ValueError(f"{func_name}() requires a field name argument")
            field_name = self._eval_literal(node.args[1], ctx)
            if not isinstance(field_name, str):
                raise TypeError(f"{func_name}() field must be string, got {type(field_name)}")
            param_start_index = 2

        # Parse parameters
        params = self._extract_event_parameters(node, ctx, start_index=param_start_index)

        # Build EventsAggregate node (will be wrapped in comparison later)
        plan = EventsAggregate(
            event_type=event_type,
            field_name=field_name,
            agg=agg_type,
            after=params.get("after"),
            before=params.get("before"),
            within_days=params.get("within_days"),
            within_months=params.get("within_months"),
            period=params.get("period"),
            states=params.get("states", ["active"]),
            where_predicate=params.get("where"),
            op=">=",  # Default operator
            rhs=0,  # Default threshold
        )

        explain = f"{func_name}({event_type}"
        if field_name:
            explain += f", {field_name}"
        if params:
            explain += f", {params}"
        explain += ")"

        return plan, explain

    def _handle_aggregate_compare(self, model: str, cmp: P.Compare, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Handle comparison with aggregate function.

        Converts: events_count('type') >= 10
        Into: EventsAggregate with op and rhs set

        Args:
            model: Target model name
            cmp: Compare node
            cfg: Configuration
            ctx: Translation context

        Returns:
            Tuple of (EventsAggregate, explanation)
        """
        # Get the aggregate plan from the left side
        agg_plan, agg_explain = self._handle_events_aggregate(model, cmp.left, cfg, ctx)

        # Evaluate right-hand side
        rhs = self._eval_literal(cmp.right, ctx)

        # Map operator
        op_map = {"EQ": "==", "NE": "!=", "GT": ">", "GE": ">=", "LT": "<", "LE": "<="}
        op = op_map.get(cmp.op, cmp.op)

        # Update the aggregate plan with comparison
        agg_plan.op = op
        agg_plan.rhs = rhs

        explain = f"{agg_explain} {op} {rhs}"
        return agg_plan, explain

    def _handle_period_function(self, model: str, node: P.Call, cfg: dict[str, Any], ctx: dict[str, Any]):
        """Handle period helper functions.

        Functions:
            - this_year() -> '2024'
            - last_year() -> '2023'
            - this_quarter() -> '2024-Q4'
            - last_quarter() -> '2024-Q3'
            - this_month() -> '2024-12'
            - last_month() -> '2024-11'
            - quarters_ago(n) -> '2024-Q2'
            - months_ago(n) -> '2024-06'

        Args:
            model: Target model name
            node: Call node
            cfg: Configuration
            ctx: Translation context

        Returns:
            Tuple of (LeafDomain, explanation) - returns period string as constant
        """
        from ...spp_cel_domain.models.cel_queryplan import LeafDomain

        func_name = node.func.name
        today = fields.Date.context_today(self)

        period_str = None

        if func_name == "this_year":
            period_str = event_funcs.this_year(today)
        elif func_name == "last_year":
            period_str = event_funcs.last_year(today)
        elif func_name == "this_quarter":
            period_str = event_funcs.this_quarter(today)
        elif func_name == "last_quarter":
            period_str = event_funcs.last_quarter(today)
        elif func_name == "this_month":
            period_str = event_funcs.this_month(today)
        elif func_name == "last_month":
            period_str = event_funcs.last_month(today)
        elif func_name == "quarters_ago":
            n = self._eval_literal(node.args[0], ctx) if node.args else 0
            period_str = event_funcs.quarters_ago(int(n), today)
        elif func_name == "months_ago":
            n = self._eval_literal(node.args[0], ctx) if node.args else 0
            period_str = event_funcs.months_ago(int(n), today)

        # Return as a LeafDomain that matches everything (period is a constant value)
        # The period will be used by event functions via _eval_literal
        return LeafDomain(model, [("id", "!=", 0)]), f"{func_name}() = '{period_str}'"

    def _extract_event_parameters(self, node: P.Call, ctx: dict[str, Any], start_index: int = 1) -> dict[str, Any]:
        """Extract named parameters from event function call.

        Extracts named parameters from the Call node's kwargs dict.
        Supported parameters:
        - select: str ('auto', 'latest', 'latest_active', 'first', 'any', 'active')
        - after, before: date
        - within_days, within_months: int
        - period: str ('2024', '2024-Q1', '2024-01', etc.)
        - states: list of state strings
        - default: any value
        - where: str (CEL predicate for aggregates)

        Args:
            node: Call node with optional kwargs
            ctx: Translation context
            start_index: Index to start parsing positional parameters from (unused now)

        Returns:
            Dictionary of parameter name -> evaluated value
        """
        params = {}

        # Extract from Call.kwargs (named arguments parsed by CEL parser)
        if hasattr(node, "kwargs") and node.kwargs:
            for key, value in node.kwargs.items():
                # Evaluate the value to handle literals, lists, etc.
                evaluated = self._eval_literal(value, ctx)
                params[key] = evaluated

        return params

    def _eval_literal(self, node: Any, ctx: dict[str, Any] | None = None):
        """Evaluate literal values, including period functions.

        Extended to handle EventFieldRef intermediate nodes and period helpers.

        Args:
            node: AST node or value
            ctx: Translation context

        Returns:
            Evaluated value
        """
        # If it's already an EventFieldRef, return as-is (intermediate representation)
        if isinstance(node, EventFieldRef):
            return node

        # Handle period helper functions
        if isinstance(node, P.Call) and isinstance(node.func, P.Ident):
            func_name = node.func.name
            if func_name in (
                "this_year",
                "last_year",
                "this_quarter",
                "last_quarter",
                "this_month",
                "last_month",
                "quarters_ago",
                "months_ago",
            ):
                _, explain = self._handle_period_function("", node, {}, ctx or {})
                # Extract period string from explanation
                import re

                match = re.search(r"'([^']+)'", explain)
                if match:
                    return match.group(1)
                return None

        # Delegate to parent for standard evaluation
        return super()._eval_literal(node, ctx)

    @api.model
    def parse_period_to_dates(self, period_str: str) -> tuple[date, date]:
        """Parse period string to (start_date, end_date) tuple.

        Supported formats:
            - 'YYYY' -> (YYYY-01-01, YYYY-12-31)
            - 'YYYY-QN' -> Quarter dates
            - 'YYYY-HN' -> Half-year dates
            - 'YYYY-MM' -> Month dates
            - 'YYYY-WNN' -> ISO week dates

        Args:
            period_str: Period string to parse

        Returns:
            Tuple of (start_date, end_date)

        Raises:
            ValueError: If period format is invalid
        """
        return event_funcs.parse_period(period_str)
