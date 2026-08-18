# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Unit tests for the analysis helpers and expression template corpus.

These are correctness tests for the tooling itself (not benchmarks):
query capture, slow-query tracking/reporting, index advice, and the CEL
expression corpus used by the performance suites.
"""

import logging

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..analysis.index_advisor import IndexAdvisor
from ..analysis.query_capture import QueryCapture, capture_queries
from ..analysis.slow_query_report import (
    SlowQueryReport,
    SlowQueryTracker,
    create_slow_query_tracker,
    print_slow_query_report,
)
from ..data import expression_templates

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "analysis")
class TestExpressionTemplates(TransactionCase):
    """Validate the expression corpus helpers."""

    def test_complexity_levels_are_populated(self):
        levels = expression_templates.get_complexity_levels()
        self.assertTrue(levels, "No complexity levels defined")
        for level in levels:
            expressions = expression_templates.get_expressions_by_complexity(level)
            self.assertTrue(expressions, f"Complexity level '{level}' has no expressions")
            for name, expr in expressions:
                self.assertTrue(name, "Expression entry missing a name")
                self.assertTrue(expr, f"Expression '{name}' is empty")

    def test_unknown_complexity_level_raises(self):
        with self.assertRaises(KeyError):
            expression_templates.get_expressions_by_complexity("no_such_level")

    def test_get_all_expressions_matches_count(self):
        all_expressions = expression_templates.get_all_expressions()
        self.assertEqual(len(all_expressions), expression_templates.get_expression_count())
        for level, name, expr in all_expressions:
            self.assertIn(level, expression_templates.get_complexity_levels())
            self.assertTrue(name)
            self.assertTrue(expr)


@tagged("post_install", "-at_install", "analysis")
class TestQueryCapture(TransactionCase):
    """Validate the SQL query interceptor."""

    def test_capture_collects_select_queries(self):
        capture = QueryCapture()
        capture.start_capture(self.env.cr)
        try:
            self.env.cr.execute("SELECT id FROM res_partner LIMIT 1")
        finally:
            capture.stop_capture(self.env.cr)

        queries = capture.get_queries()
        self.assertTrue(queries, "No queries captured")
        self.assertIn("res_partner", queries[-1]["tables"])

        stats = capture.get_query_stats()
        self.assertGreaterEqual(stats.get("total_queries", 0), 1)

        capture.clear()
        self.assertEqual(capture.get_queries(), [])

    def test_capture_ignores_non_select(self):
        capture = QueryCapture()
        capture.start_capture(self.env.cr)
        try:
            self.env.cr.execute("SAVEPOINT qc_probe")
            self.env.cr.execute("RELEASE SAVEPOINT qc_probe")
        finally:
            capture.stop_capture(self.env.cr)

        for query_info in capture.get_queries():
            self.assertTrue(query_info["query"].strip().upper().startswith("SELECT"))

    def test_capture_context_manager_restores_cursor(self):
        original_execute = self.env.cr.execute
        with capture_queries(self.env.cr) as capture:
            self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.execute, original_execute, "Cursor execute was not restored")
        self.assertTrue(capture.get_queries())

    def test_capture_extracts_join_tables_and_where_columns(self):
        with capture_queries(self.env.cr) as capture:
            self.env.cr.execute(
                "SELECT p.id FROM res_partner p "
                "JOIN res_users u ON u.partner_id = p.id "
                "WHERE p.active = TRUE AND u.login = %s LIMIT 1",
                ("__no_such_login__",),
            )

        stats = capture.get_query_stats()
        self.assertIn("res_partner", stats["tables"])
        self.assertIn("res_users", stats["tables"])
        self.assertIn("login", stats["columns"])


@tagged("post_install", "-at_install", "analysis")
class TestSlowQueryTracking(TransactionCase):
    """Validate slow-query tracking and report generation."""

    def test_tracker_records_only_slow_queries(self):
        tracker = SlowQueryTracker(threshold_ms=50.0)
        tracker.record_query_time("SELECT fast", 10.0)
        tracker.record_query_time("SELECT slow", 120.0)

        slow = tracker.get_slow_queries()
        self.assertEqual(len(slow), 1)
        self.assertEqual(slow[0]["query"], "SELECT slow")

        summary = tracker.get_summary()
        self.assertEqual(summary.get("count"), 1)
        self.assertEqual(summary.get("worst_query"), "SELECT slow")

        tracker.clear()
        self.assertEqual(tracker.get_slow_queries(), [])

    def test_tracker_start_end_timing(self):
        tracker = SlowQueryTracker(threshold_ms=0.0)
        tracker.start_timing("q1")
        tracker.end_timing("q1", "SELECT timed", params=("x",))
        slow = tracker.get_slow_queries()
        self.assertEqual(len(slow), 1)
        self.assertEqual(slow[0]["query"], "SELECT timed")

    def test_tracker_end_timing_without_start_is_ignored(self):
        tracker = SlowQueryTracker(threshold_ms=0.0)
        tracker.end_timing("never-started", "SELECT ignored")
        self.assertEqual(tracker.get_slow_queries(), [])

    def test_empty_tracker_reports(self):
        tracker = SlowQueryTracker(threshold_ms=100.0)
        summary = tracker.get_summary()
        self.assertEqual(summary["count"], 0)
        self.assertIsNone(summary["worst_query"])

        report = SlowQueryReport(tracker)
        self.assertIn("No slow queries detected", report.generate_summary_report())
        self.assertIn("No slow queries detected", report.generate_detailed_report())

    def test_detailed_report_includes_params_and_truncates(self):
        tracker = SlowQueryTracker(threshold_ms=1.0)
        long_query = "SELECT col\n" * 40 + "FROM res_partner"
        tracker.record_query_time(long_query, 50.0, params=("p1", "p2"))

        detailed = SlowQueryReport(tracker).generate_detailed_report(limit=1)
        self.assertIn("Parameters:", detailed)
        self.assertIn("truncated", detailed)

    def test_report_generation(self):
        tracker = create_slow_query_tracker(threshold_ms=1.0)
        tracker.record_query_time("SELECT a FROM res_partner", 25.0)
        tracker.record_query_time("SELECT b FROM res_partner", 75.0)

        report = SlowQueryReport(tracker)
        summary_text = report.generate_summary_report()
        self.assertIn("2", summary_text)
        detailed_text = report.generate_detailed_report(limit=1)
        self.assertTrue(detailed_text)

        exported = report.export_to_dict()
        self.assertEqual(len(exported.get("slow_queries", [])), 2)

        # Smoke: printing helpers must not raise
        report.print_report(detailed=True, limit=1)
        print_slow_query_report(tracker, detailed=False)


@tagged("post_install", "-at_install", "analysis")
class TestIndexAdvisor(TransactionCase):
    """Validate index inspection and recommendation logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.advisor = IndexAdvisor(cls.env.cr)

    def test_get_existing_indexes_sees_core_tables(self):
        indexes = self.advisor.get_existing_indexes()
        self.assertIn("res_partner", indexes, "res_partner indexes not found in pg_index scan")
        # refresh path
        refreshed = self.advisor.get_existing_indexes(refresh=True)
        self.assertIn("res_partner", refreshed)

    def test_check_index_exists(self):
        self.assertTrue(self.advisor.check_index_exists("res_partner", ["id"]))
        self.assertFalse(self.advisor.check_index_exists("res_partner", ["no_such_column_xyz"]))

    def test_recommended_cel_indexes_structure(self):
        recommendations = self.advisor.get_recommended_cel_indexes()
        self.assertTrue(recommendations, "No CEL index recommendations defined")
        for rec in recommendations:
            self.assertIn("table", rec)
            self.assertIn("columns", rec)

    def test_analyze_missing_indexes_runs(self):
        missing = self.advisor.analyze_missing_indexes()
        self.assertIsInstance(missing, list)
        for rec in missing:
            self.assertFalse(
                self.advisor.check_index_exists(rec["table"], rec["columns"]),
                f"Recommendation {rec} reported missing but the index exists",
            )

    def test_analyze_explain_issues_maps_to_recommendations(self):
        issues = [
            {
                "severity": "high",
                "type": "sequential_scan_large_table",
                "table": "res_partner",
                "rows": 100000,
                "time_ms": 500.0,
                "message": "Sequential scan on res_partner",
                "path": "Seq Scan",
            }
        ]
        recommendations = self.advisor.analyze_explain_issues(issues)
        self.assertIsInstance(recommendations, list)

        # Unknown issue types must be ignored, not crash
        self.assertIsInstance(
            self.advisor.analyze_explain_issues([{"type": "unknown_issue_type"}]),
            list,
        )

    def test_get_existing_indexes_survives_broken_cursor(self):
        class BrokenCursor:
            def execute(self, *args, **kwargs):
                raise RuntimeError("cursor unavailable")

        self.assertEqual(IndexAdvisor(BrokenCursor()).get_existing_indexes(), {})

    def test_check_index_exists_prefix_match(self):
        """A multi-column index must satisfy a lookup on its leading column."""
        indexes = self.advisor.get_existing_indexes()
        candidate = None
        for table, table_indexes in indexes.items():
            single = {idx["columns"][0] for idx in table_indexes if len(idx["columns"]) == 1}
            for idx in table_indexes:
                if len(idx["columns"]) >= 2 and idx["columns"][0] not in single:
                    candidate = (table, idx["columns"][0])
                    break
            if candidate:
                break
        if not candidate:
            self.skipTest("No multi-column index without a single-column twin found")
        table, leading_column = candidate
        self.assertTrue(self.advisor.check_index_exists(table, [leading_column]))

    def test_analyze_explain_issues_nested_loop_logged_only(self):
        recommendations = self.advisor.analyze_explain_issues(
            [{"type": "nested_loop_no_index", "message": "nested loop probe"}]
        )
        self.assertEqual(recommendations, [])

    def test_print_recommendations_report_empty(self):
        self.advisor.print_recommendations_report([])

    def test_print_recommendations_report_smoke(self):
        # The printer expects analyze_missing_indexes() output (carries
        # index_name/ddl); fall back to a synthetic entry if no index is
        # missing on this database.
        recommendations = self.advisor.analyze_missing_indexes()[:1] or [
            {
                "table": "res_partner",
                "columns": ["birthdate"],
                "rationale": "synthetic smoke entry",
                "index_name": "idx_res_partner_birthdate",
                "ddl": "CREATE INDEX idx_res_partner_birthdate ON res_partner (birthdate);",
            }
        ]
        self.advisor.print_recommendations_report(recommendations)
