# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Tests for CEL event translator extension."""

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_cel_domain.services import cel_parser as P

from ..models.cel_event_queryplan import (
    EventExists,
    EventFieldRef,
    EventsAggregate,
    EventValueCompare,
)


@tagged("post_install", "-at_install")
class TestCelEventTranslator(TransactionCase):
    """Unit tests for the CEL event translator methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.translator = cls.env["spp.cel.translator"]
        cls.model = "res.partner"
        cls.cfg = {}
        cls.ctx = {}

    # ══════════════════════════════════════════════════════════════════════════
    # _is_event_field_access tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_is_event_field_access_dot_notation(self):
        """Test event('type').field is recognized as event field access."""
        # event('survey').income
        node = P.Attr(
            obj=P.Call(func=P.Ident("event"), args=[P.Literal("survey")]),
            name="income",
        )
        self.assertTrue(self.translator._is_event_field_access(node))

    def test_is_event_field_access_two_arg(self):
        """Test event('type', 'field') is recognized as event field access."""
        node = P.Call(
            func=P.Ident("event"),
            args=[P.Literal("survey"), P.Literal("income")],
        )
        self.assertTrue(self.translator._is_event_field_access(node))

    def test_is_event_field_access_not_event(self):
        """Test non-event call is not recognized."""
        node = P.Call(func=P.Ident("other_func"), args=[P.Literal("survey")])
        self.assertFalse(self.translator._is_event_field_access(node))

    def test_is_event_field_access_plain_ident(self):
        """Test plain identifier is not recognized."""
        node = P.Ident("some_var")
        self.assertFalse(self.translator._is_event_field_access(node))

    def test_is_event_field_access_event_no_field(self):
        """Test event('type') without field access is not a field access."""
        node = P.Call(func=P.Ident("event"), args=[P.Literal("survey")])
        self.assertFalse(self.translator._is_event_field_access(node))

    def test_is_event_field_access_event_single_non_string_arg(self):
        """Test event('type', 123) where second arg is not string is not field access."""
        node = P.Call(
            func=P.Ident("event"),
            args=[P.Literal("survey"), P.Literal(123)],
        )
        self.assertFalse(self.translator._is_event_field_access(node))

    # ══════════════════════════════════════════════════════════════════════════
    # _handle_event_call tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_handle_event_call_basic(self):
        """Test basic event('type') call produces EventFieldRef."""
        node = P.Call(func=P.Ident("event"), args=[P.Literal("survey")])
        result, explain = self.translator._handle_event_call(self.model, node, self.cfg, self.ctx)

        self.assertIsInstance(result, EventFieldRef)
        self.assertEqual(result.event_type, "survey")
        self.assertIsNone(result.field_name)
        self.assertEqual(result.select, "auto")

    def test_handle_event_call_with_field(self):
        """Test event('type', 'field') sets field_name."""
        node = P.Call(
            func=P.Ident("event"),
            args=[P.Literal("survey"), P.Literal("income")],
        )
        result, explain = self.translator._handle_event_call(self.model, node, self.cfg, self.ctx)

        self.assertIsInstance(result, EventFieldRef)
        self.assertEqual(result.event_type, "survey")
        self.assertEqual(result.field_name, "income")

    def test_handle_event_call_with_kwargs(self):
        """Test event() with named parameters."""
        node = P.Call(
            func=P.Ident("event"),
            args=[P.Literal("survey")],
            kwargs={
                "select": P.Literal("latest"),
                "within_days": P.Literal(90),
            },
        )
        result, explain = self.translator._handle_event_call(self.model, node, self.cfg, self.ctx)

        self.assertEqual(result.select, "latest")
        self.assertEqual(result.within_days, 90)

    def test_handle_event_call_no_args_raises(self):
        """Test event() with no arguments raises ValueError."""
        node = P.Call(func=P.Ident("event"), args=[])
        with self.assertRaises(ValueError):
            self.translator._handle_event_call(self.model, node, self.cfg, self.ctx)

    def test_handle_event_call_non_string_type_raises(self):
        """Test event(123) with non-string type raises TypeError."""
        node = P.Call(func=P.Ident("event"), args=[P.Literal(123)])
        with self.assertRaises(TypeError):
            self.translator._handle_event_call(self.model, node, self.cfg, self.ctx)

    # ══════════════════════════════════════════════════════════════════════════
    # _handle_has_event tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_handle_has_event_basic(self):
        """Test has_event('type') produces EventExists."""
        node = P.Call(func=P.Ident("has_event"), args=[P.Literal("survey")])
        result, explain = self.translator._handle_has_event(self.model, node, self.cfg, self.ctx)

        self.assertIsInstance(result, EventExists)
        self.assertEqual(result.event_type, "survey")
        self.assertEqual(result.states, ["active"])  # Default

    def test_handle_has_event_with_temporal(self):
        """Test has_event() with within_days parameter."""
        node = P.Call(
            func=P.Ident("has_event"),
            args=[P.Literal("assessment")],
            kwargs={"within_days": P.Literal(365)},
        )
        result, explain = self.translator._handle_has_event(self.model, node, self.cfg, self.ctx)

        self.assertEqual(result.within_days, 365)

    def test_handle_has_event_no_args_raises(self):
        """Test has_event() with no arguments raises ValueError."""
        node = P.Call(func=P.Ident("has_event"), args=[])
        with self.assertRaises(ValueError):
            self.translator._handle_has_event(self.model, node, self.cfg, self.ctx)

    def test_handle_has_event_non_string_type_raises(self):
        """Test has_event(123) raises TypeError."""
        node = P.Call(func=P.Ident("has_event"), args=[P.Literal(123)])
        with self.assertRaises(TypeError):
            self.translator._handle_has_event(self.model, node, self.cfg, self.ctx)

    # ══════════════════════════════════════════════════════════════════════════
    # _handle_events_aggregate tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_handle_events_count(self):
        """Test events_count('type') produces EventsAggregate with agg='count'."""
        node = P.Call(func=P.Ident("events_count"), args=[P.Literal("attendance")])
        result, explain = self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

        self.assertIsInstance(result, EventsAggregate)
        self.assertEqual(result.event_type, "attendance")
        self.assertEqual(result.agg, "count")
        self.assertIsNone(result.field_name)
        # Default op and rhs
        self.assertEqual(result.op, ">=")
        self.assertEqual(result.rhs, 0)

    def test_handle_events_sum(self):
        """Test events_sum('type', 'field') produces correct aggregate."""
        node = P.Call(
            func=P.Ident("events_sum"),
            args=[P.Literal("survey"), P.Literal("income")],
        )
        result, explain = self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

        self.assertEqual(result.agg, "sum")
        self.assertEqual(result.field_name, "income")

    def test_handle_events_avg(self):
        """Test events_avg produces correct aggregate."""
        node = P.Call(
            func=P.Ident("events_avg"),
            args=[P.Literal("survey"), P.Literal("score")],
        )
        result, explain = self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

        self.assertEqual(result.agg, "avg")
        self.assertEqual(result.field_name, "score")

    def test_handle_events_min(self):
        """Test events_min produces correct aggregate."""
        node = P.Call(
            func=P.Ident("events_min"),
            args=[P.Literal("survey"), P.Literal("score")],
        )
        result, explain = self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

        self.assertEqual(result.agg, "min")

    def test_handle_events_max(self):
        """Test events_max produces correct aggregate."""
        node = P.Call(
            func=P.Ident("events_max"),
            args=[P.Literal("survey"), P.Literal("score")],
        )
        result, explain = self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

        self.assertEqual(result.agg, "max")

    def test_handle_events_aggregate_with_kwargs(self):
        """Test aggregate function with named parameters."""
        node = P.Call(
            func=P.Ident("events_count"),
            args=[P.Literal("attendance")],
            kwargs={
                "period": P.Literal("2024"),
                "states": P.Literal(["active", "superseded"]),
            },
        )
        result, explain = self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

        self.assertEqual(result.period, "2024")
        self.assertEqual(result.states, ["active", "superseded"])

    def test_handle_events_sum_no_field_raises(self):
        """Test events_sum() without field argument raises ValueError."""
        node = P.Call(func=P.Ident("events_sum"), args=[P.Literal("survey")])
        with self.assertRaises(ValueError):
            self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

    def test_handle_events_count_no_args_raises(self):
        """Test events_count() with no arguments raises ValueError."""
        node = P.Call(func=P.Ident("events_count"), args=[])
        with self.assertRaises(ValueError):
            self.translator._handle_events_aggregate(self.model, node, self.cfg, self.ctx)

    # ══════════════════════════════════════════════════════════════════════════
    # _handle_aggregate_compare tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_handle_aggregate_compare_ge(self):
        """Test events_count('type') >= 10 sets op and rhs."""
        cmp = P.Compare(
            op="GE",
            left=P.Call(func=P.Ident("events_count"), args=[P.Literal("visit")]),
            right=P.Literal(10),
        )
        result, explain = self.translator._handle_aggregate_compare(self.model, cmp, self.cfg, self.ctx)

        self.assertIsInstance(result, EventsAggregate)
        self.assertEqual(result.op, ">=")
        self.assertEqual(result.rhs, 10)

    def test_handle_aggregate_compare_eq(self):
        """Test events_count('type') == 5."""
        cmp = P.Compare(
            op="EQ",
            left=P.Call(func=P.Ident("events_count"), args=[P.Literal("visit")]),
            right=P.Literal(5),
        )
        result, explain = self.translator._handle_aggregate_compare(self.model, cmp, self.cfg, self.ctx)

        self.assertEqual(result.op, "==")
        self.assertEqual(result.rhs, 5)

    def test_handle_aggregate_compare_lt(self):
        """Test events_sum('type', 'field') < 1000."""
        cmp = P.Compare(
            op="LT",
            left=P.Call(
                func=P.Ident("events_sum"),
                args=[P.Literal("survey"), P.Literal("income")],
            ),
            right=P.Literal(1000),
        )
        result, explain = self.translator._handle_aggregate_compare(self.model, cmp, self.cfg, self.ctx)

        self.assertEqual(result.op, "<")
        self.assertEqual(result.rhs, 1000)
        self.assertEqual(result.field_name, "income")

    # ══════════════════════════════════════════════════════════════════════════
    # _extract_event_parameters tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_extract_event_parameters_empty(self):
        """Test extracting parameters from node with no kwargs."""
        node = P.Call(func=P.Ident("event"), args=[P.Literal("survey")])
        params = self.translator._extract_event_parameters(node, self.ctx, start_index=1)
        self.assertEqual(params, {})

    def test_extract_event_parameters_with_kwargs(self):
        """Test extracting named parameters."""
        node = P.Call(
            func=P.Ident("event"),
            args=[P.Literal("survey")],
            kwargs={
                "select": P.Literal("latest"),
                "within_days": P.Literal(90),
                "default": P.Literal(0),
            },
        )
        params = self.translator._extract_event_parameters(node, self.ctx, start_index=1)

        self.assertEqual(params["select"], "latest")
        self.assertEqual(params["within_days"], 90)
        self.assertEqual(params["default"], 0)

    # ══════════════════════════════════════════════════════════════════════════
    # _eval_literal tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_eval_literal_event_field_ref_passthrough(self):
        """Test that EventFieldRef is returned as-is."""
        ref = EventFieldRef(event_type="survey", field_name="income")
        result = self.translator._eval_literal(ref, self.ctx)
        self.assertIs(result, ref)

    def test_eval_literal_string(self):
        """Test evaluating string literal."""
        result = self.translator._eval_literal(P.Literal("hello"), self.ctx)
        self.assertEqual(result, "hello")

    def test_eval_literal_number(self):
        """Test evaluating number literal."""
        result = self.translator._eval_literal(P.Literal(42), self.ctx)
        self.assertEqual(result, 42)

    def test_eval_literal_boolean(self):
        """Test evaluating boolean literal."""
        result = self.translator._eval_literal(P.Literal(True), self.ctx)
        self.assertTrue(result)

    # ══════════════════════════════════════════════════════════════════════════
    # _handle_period_function tests
    # ══════════════════════════════════════════════════════════════════════════

    def test_handle_period_this_year(self):
        """Test this_year() returns current year string."""
        from datetime import date

        node = P.Call(func=P.Ident("this_year"), args=[])
        result, explain = self.translator._handle_period_function(self.model, node, self.cfg, self.ctx)

        expected_year = str(date.today().year)
        self.assertIn(expected_year, explain)

    def test_handle_period_last_year(self):
        """Test last_year() returns previous year string."""
        from datetime import date

        node = P.Call(func=P.Ident("last_year"), args=[])
        result, explain = self.translator._handle_period_function(self.model, node, self.cfg, self.ctx)

        expected_year = str(date.today().year - 1)
        self.assertIn(expected_year, explain)

    def test_handle_period_this_quarter(self):
        """Test this_quarter() returns current quarter string."""
        node = P.Call(func=P.Ident("this_quarter"), args=[])
        result, explain = self.translator._handle_period_function(self.model, node, self.cfg, self.ctx)

        # Should contain a quarter like '2026-Q1'
        self.assertRegex(explain, r"\d{4}-Q[1-4]")

    def test_handle_period_this_month(self):
        """Test this_month() returns current month string."""
        node = P.Call(func=P.Ident("this_month"), args=[])
        result, explain = self.translator._handle_period_function(self.model, node, self.cfg, self.ctx)

        # Should contain a month like '2026-03'
        self.assertRegex(explain, r"\d{4}-\d{2}")

    def test_handle_period_quarters_ago(self):
        """Test quarters_ago(n) returns correct quarter string."""
        node = P.Call(func=P.Ident("quarters_ago"), args=[P.Literal(1)])
        result, explain = self.translator._handle_period_function(self.model, node, self.cfg, self.ctx)

        self.assertRegex(explain, r"\d{4}-Q[1-4]")

    def test_handle_period_months_ago(self):
        """Test months_ago(n) returns correct month string."""
        node = P.Call(func=P.Ident("months_ago"), args=[P.Literal(2)])
        result, explain = self.translator._handle_period_function(self.model, node, self.cfg, self.ctx)

        self.assertRegex(explain, r"\d{4}-\d{2}")

    # ══════════════════════════════════════════════════════════════════════════
    # _to_plan integration (end-to-end translator tests)
    # ══════════════════════════════════════════════════════════════════════════

    def test_to_plan_event_field_compare(self):
        """Test full _to_plan for event('type').field > value."""
        # event('survey').income > 500
        node = P.Compare(
            op="GT",
            left=P.Attr(
                obj=P.Call(func=P.Ident("event"), args=[P.Literal("survey")]),
                name="income",
            ),
            right=P.Literal(500),
        )

        result, explain = self.translator._to_plan(self.model, node, self.cfg, self.ctx)

        self.assertIsInstance(result, EventValueCompare)
        self.assertEqual(result.event_type, "survey")
        self.assertEqual(result.field_name, "income")
        self.assertEqual(result.op, ">")
        self.assertEqual(result.rhs, 500)

    def test_to_plan_has_event(self):
        """Test full _to_plan for has_event('type')."""
        node = P.Call(func=P.Ident("has_event"), args=[P.Literal("survey")])

        result, explain = self.translator._to_plan(self.model, node, self.cfg, self.ctx)

        self.assertIsInstance(result, EventExists)
        self.assertEqual(result.event_type, "survey")

    def test_to_plan_aggregate_compare(self):
        """Test full _to_plan for events_count('type') >= 10."""
        node = P.Compare(
            op="GE",
            left=P.Call(
                func=P.Ident("events_count"),
                args=[P.Literal("attendance")],
            ),
            right=P.Literal(10),
        )

        result, explain = self.translator._to_plan(self.model, node, self.cfg, self.ctx)

        self.assertIsInstance(result, EventsAggregate)
        self.assertEqual(result.op, ">=")
        self.assertEqual(result.rhs, 10)
