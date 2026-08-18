# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Correctness tests for the ExplainAnalyzer analysis helper.

EXPLAIN (ANALYZE, ...) executes the statement it analyzes. The analyzer
must therefore never run ANALYZE on data-modifying statements captured
during benchmarks: re-executing an INSERT duplicates rows (or violates
unique constraints and aborts the whole test transaction).
"""

import logging

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..analysis.explain_analyzer import ExplainAnalyzer

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "analysis")
class TestExplainAnalyzer(TransactionCase):
    """Guard the side-effect behavior of ExplainAnalyzer.analyze_query."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.analyzer = ExplainAnalyzer(cls.env.cr)

    def test_analyze_insert_does_not_execute_statement(self):
        """Analyzing an INSERT must not actually insert the row."""
        marker = "ExplainAnalyzerProbe-no-execute"
        result = self.analyzer.analyze_query(
            "INSERT INTO res_partner (name, active) VALUES (%s, true)",
            (marker,),
        )

        self.env.cr.execute(
            "SELECT COUNT(*) FROM res_partner WHERE name = %s",
            (marker,),
        )
        count = self.env.cr.fetchone()[0]
        self.assertEqual(count, 0, "analyze_query executed the INSERT it was analyzing")

        # A plan must still be produced (plain EXPLAIN, without ANALYZE)
        self.assertIsNone(result.get("error"), f"analyze_query errored: {result.get('error')}")
        self.assertIsNotNone(result.get("plan"), "analyze_query returned no plan for the INSERT")

    def test_analyze_conflicting_insert_keeps_transaction_alive(self):
        """A DML that would violate a constraint must not abort the transaction.

        This is the exact failure mode seen with the enrollment benchmark:
        the captured INSERT hits a unique constraint when re-executed and
        poisons the outer test transaction ("current transaction is
        aborted") for every statement that follows.
        """
        partner = self.env["res.partner"].create({"name": "ExplainAnalyzerProbe-conflict"})

        # Re-inserting the same primary key is guaranteed to conflict
        self.analyzer.analyze_query(
            "INSERT INTO res_partner (id, name, active) VALUES (%s, %s, true)",
            (partner.id, "ExplainAnalyzerProbe-conflict-dup"),
        )

        # The transaction must still accept statements
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone()[0], 1)

    def test_analyze_select_reports_execution_metrics(self):
        """SELECTs are side-effect free and keep full ANALYZE instrumentation."""
        result = self.analyzer.analyze_query("SELECT COUNT(*) FROM res_partner")

        self.assertIsNone(result.get("error"), f"analyze_query errored: {result.get('error')}")
        self.assertIsNotNone(result.get("plan"), "analyze_query returned no plan for the SELECT")
        # ANALYZE output carries an Execution Time; plan-only output does not
        self.assertGreater(
            result.get("total_time_ms", 0.0),
            0.0,
            "SELECT analysis lost ANALYZE instrumentation (no Execution Time)",
        )
