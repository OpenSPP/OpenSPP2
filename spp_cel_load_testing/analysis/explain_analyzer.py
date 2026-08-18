# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""PostgreSQL EXPLAIN ANALYZE Query Analyzer.

Analyzes PostgreSQL query execution plans to detect performance issues such as
sequential scans on large tables, slow operations, and inefficient nested loops.
"""

import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)


class ExplainAnalyzer:
    """Analyzes PostgreSQL EXPLAIN ANALYZE output for performance issues.

    Detects:
    - Sequential scans on tables with >1000 rows
    - Slow nodes (execution time >100ms)
    - Nested loops without index usage
    """

    # Performance thresholds
    SEQSCAN_ROW_THRESHOLD = 1000  # Flag sequential scans on tables with >1000 rows
    SLOW_NODE_MS_THRESHOLD = 100.0  # Flag nodes taking >100ms

    def __init__(self, cursor):
        """Initialize analyzer with database cursor.

        Args:
            cursor: Odoo database cursor for running EXPLAIN queries
        """
        self.cursor = cursor

    def analyze_query(self, query: str, params: tuple | None = None) -> dict[str, Any]:
        """Run EXPLAIN ANALYZE on a query and detect issues.

        Args:
            query: SQL query to analyze
            params: Query parameters (optional)

        Returns:
            Dictionary with:
                - plan: Full execution plan as JSON
                - issues: List of detected performance issues
                - total_time_ms: Total execution time in milliseconds
        """
        try:
            # Run EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"

            if params:
                self.cursor.execute(explain_query, params)
            else:
                self.cursor.execute(explain_query)

            result = self.cursor.fetchone()
            if not result or not result[0]:
                return {"plan": None, "issues": [], "total_time_ms": 0.0, "error": "No EXPLAIN output received"}

            # Parse JSON plan
            plan_json = result[0]
            if isinstance(plan_json, str):
                plan_json = json.loads(plan_json)

            # Extract root plan node
            plan = plan_json[0] if isinstance(plan_json, list) else plan_json
            root_plan = plan.get("Plan", {})
            total_time = plan.get("Execution Time", 0.0)

            # Detect issues by traversing plan tree
            issues = []
            self._detect_issues_recursive(root_plan, issues, path=[])

            return {
                "plan": plan,
                "issues": issues,
                "total_time_ms": total_time,
            }

        except Exception as e:
            _logger.warning("Failed to analyze query: %s", e, exc_info=True)
            return {"plan": None, "issues": [], "total_time_ms": 0.0, "error": str(e)}

    def _detect_issues_recursive(self, node: dict[str, Any], issues: list[dict[str, Any]], path: list[str]):
        """Recursively traverse plan tree to detect performance issues.

        Args:
            node: Current plan node
            issues: List to append detected issues to
            path: Current path in plan tree (for issue context)
        """
        if not node:
            return

        node_type = node.get("Node Type", "")
        actual_time = node.get("Actual Total Time", 0.0)
        actual_rows = node.get("Actual Rows", 0)
        relation_name = node.get("Relation Name", "")

        # Build path for this node
        current_path = path + [node_type]

        # Issue 1: Sequential Scan on large tables
        if node_type == "Seq Scan" and actual_rows > self.SEQSCAN_ROW_THRESHOLD:
            issues.append(
                {
                    "severity": "high",
                    "type": "sequential_scan_large_table",
                    "message": (
                        f"Sequential scan on {relation_name} with {actual_rows:,} rows "
                        f"(threshold: {self.SEQSCAN_ROW_THRESHOLD:,})"
                    ),
                    "table": relation_name,
                    "rows": actual_rows,
                    "time_ms": actual_time,
                    "path": " -> ".join(current_path),
                }
            )

        # Issue 2: Slow nodes (>100ms)
        if actual_time > self.SLOW_NODE_MS_THRESHOLD:
            # Only report if not already reporting parent issue
            issues.append(
                {
                    "severity": "medium",
                    "type": "slow_node",
                    "message": (
                        f"Slow {node_type} operation: {actual_time:.2f}ms "
                        f"(threshold: {self.SLOW_NODE_MS_THRESHOLD}ms)"
                    ),
                    "node_type": node_type,
                    "time_ms": actual_time,
                    "table": relation_name if relation_name else "N/A",
                    "path": " -> ".join(current_path),
                }
            )

        # Issue 3: Nested Loop without index usage
        if node_type == "Nested Loop":
            has_index_scan = self._has_index_scan_child(node)
            if not has_index_scan and actual_rows > 100:
                issues.append(
                    {
                        "severity": "high",
                        "type": "nested_loop_no_index",
                        "message": (
                            f"Nested loop without index scan processing {actual_rows:,} rows " f"({actual_time:.2f}ms)"
                        ),
                        "rows": actual_rows,
                        "time_ms": actual_time,
                        "path": " -> ".join(current_path),
                    }
                )

        # Recurse into child plans
        plans = node.get("Plans", [])
        for child_plan in plans:
            self._detect_issues_recursive(child_plan, issues, current_path)

    def _has_index_scan_child(self, node: dict[str, Any]) -> bool:
        """Check if node or its children contain an index scan.

        Args:
            node: Plan node to check

        Returns:
            True if index scan found in node or children
        """
        node_type = node.get("Node Type", "")
        if "Index" in node_type:  # Index Scan, Index Only Scan, Bitmap Index Scan
            return True

        # Check children
        plans = node.get("Plans", [])
        for child_plan in plans:
            if self._has_index_scan_child(child_plan):
                return True

        return False

    def format_issues_report(self, issues: list[dict[str, Any]]) -> str:
        """Format detected issues as a human-readable report.

        Args:
            issues: List of issue dictionaries from analyze_query()

        Returns:
            Formatted text report
        """
        if not issues:
            return "No performance issues detected."

        # Group by severity
        high_severity = [i for i in issues if i.get("severity") == "high"]
        medium_severity = [i for i in issues if i.get("severity") == "medium"]
        low_severity = [i for i in issues if i.get("severity") == "low"]

        lines = []
        lines.append("=" * 80)
        lines.append("EXPLAIN ANALYZE - Performance Issues Report")
        lines.append("=" * 80)
        lines.append("")

        if high_severity:
            lines.append(f"HIGH SEVERITY ({len(high_severity)} issues):")
            lines.append("-" * 80)
            for issue in high_severity:
                lines.append(f"  • {issue['message']}")
                lines.append(f"    Path: {issue['path']}")
                lines.append("")

        if medium_severity:
            lines.append(f"MEDIUM SEVERITY ({len(medium_severity)} issues):")
            lines.append("-" * 80)
            for issue in medium_severity:
                lines.append(f"  • {issue['message']}")
                lines.append(f"    Path: {issue['path']}")
                lines.append("")

        if low_severity:
            lines.append(f"LOW SEVERITY ({len(low_severity)} issues):")
            lines.append("-" * 80)
            for issue in low_severity:
                lines.append(f"  • {issue['message']}")
                lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    def get_table_row_estimates(self, tables: list[str]) -> dict[str, int]:
        """Get row count estimates for tables from pg_class.

        Args:
            tables: List of table names

        Returns:
            Dictionary mapping table name to estimated row count
        """
        if not tables:
            return {}

        estimates = {}
        try:
            for table in tables:
                self.cursor.execute(
                    """
                    SELECT reltuples::bigint
                    FROM pg_class
                    WHERE relname = %s
                    """,
                    (table,),
                )
                result = self.cursor.fetchone()
                if result:
                    estimates[table] = int(result[0])
                else:
                    estimates[table] = 0
        except Exception as e:
            _logger.warning("Failed to get table row estimates: %s", e)

        return estimates
