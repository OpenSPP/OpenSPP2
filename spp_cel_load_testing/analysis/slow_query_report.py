# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Slow Query Report Generator for CEL Performance Analysis.

Tracks and reports SQL queries that exceed performance thresholds during
CEL expression evaluation. Provides detailed metrics and formatted reports.
"""

import logging
import time
from typing import Any

_logger = logging.getLogger(__name__)


class SlowQueryTracker:
    """Tracks queries exceeding execution time threshold.

    Monitors query execution times and collects slow queries for analysis
    and reporting.
    """

    def __init__(self, threshold_ms: float = 100.0):
        """Initialize slow query tracker.

        Args:
            threshold_ms: Threshold in milliseconds to consider query slow (default: 100ms)
        """
        self.threshold_ms = threshold_ms
        self.slow_queries: list[dict[str, Any]] = []
        self._query_start_times: dict[str, float] = {}

    def start_timing(self, query_id: str):
        """Start timing a query execution.

        Args:
            query_id: Unique identifier for the query
        """
        self._query_start_times[query_id] = time.time()

    def end_timing(self, query_id: str, query: str, params: tuple | None = None):
        """End timing a query and record if slow.

        Args:
            query_id: Unique identifier for the query
            query: SQL query text
            params: Query parameters (optional)
        """
        if query_id not in self._query_start_times:
            _logger.warning("Query ID %s not found in start times", query_id)
            return

        start_time = self._query_start_times.pop(query_id)
        elapsed_ms = (time.time() - start_time) * 1000.0

        if elapsed_ms >= self.threshold_ms:
            self.slow_queries.append(
                {
                    "query": query,
                    "params": params,
                    "execution_time_ms": elapsed_ms,
                    "timestamp": time.time(),
                }
            )

    def record_query_time(self, query: str, execution_time_ms: float, params: tuple | None = None):
        """Directly record a query execution time.

        Args:
            query: SQL query text
            execution_time_ms: Execution time in milliseconds
            params: Query parameters (optional)
        """
        if execution_time_ms >= self.threshold_ms:
            self.slow_queries.append(
                {
                    "query": query,
                    "params": params,
                    "execution_time_ms": execution_time_ms,
                    "timestamp": time.time(),
                }
            )

    def get_slow_queries(self) -> list[dict[str, Any]]:
        """Get all tracked slow queries.

        Returns:
            List of slow query records sorted by execution time (slowest first)
        """
        return sorted(self.slow_queries, key=lambda q: q["execution_time_ms"], reverse=True)

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics of slow queries.

        Returns:
            Dictionary with count, total time, average time, worst query
        """
        if not self.slow_queries:
            return {
                "count": 0,
                "total_time_ms": 0.0,
                "average_time_ms": 0.0,
                "worst_query_ms": 0.0,
                "worst_query": None,
            }

        total_time = sum(q["execution_time_ms"] for q in self.slow_queries)
        worst = max(self.slow_queries, key=lambda q: q["execution_time_ms"])

        return {
            "count": len(self.slow_queries),
            "total_time_ms": total_time,
            "average_time_ms": total_time / len(self.slow_queries),
            "worst_query_ms": worst["execution_time_ms"],
            "worst_query": worst["query"][:200],  # Truncate for summary
        }

    def clear(self):
        """Clear all tracked slow queries."""
        self.slow_queries.clear()
        self._query_start_times.clear()


class SlowQueryReport:
    """Generates formatted reports for slow queries."""

    def __init__(self, tracker: SlowQueryTracker):
        """Initialize report generator.

        Args:
            tracker: SlowQueryTracker instance with collected data
        """
        self.tracker = tracker

    def generate_summary_report(self) -> str:
        """Generate summary report of slow queries.

        Returns:
            Formatted summary text
        """
        summary = self.tracker.get_summary()

        if summary["count"] == 0:
            return f"No slow queries detected (all queries < {self.tracker.threshold_ms:.0f}ms)"

        lines = []
        lines.append("=" * 80)
        lines.append("SLOW QUERY SUMMARY REPORT")
        lines.append("=" * 80)
        lines.append(f"Threshold: {self.tracker.threshold_ms:.0f}ms")
        lines.append(f"Total slow queries: {summary['count']}")
        lines.append(f"Total time in slow queries: {summary['total_time_ms']:.2f}ms")
        lines.append(f"Average slow query time: {summary['average_time_ms']:.2f}ms")
        lines.append(f"Worst query time: {summary['worst_query_ms']:.2f}ms")
        lines.append("=" * 80)

        return "\n".join(lines)

    def generate_detailed_report(self, limit: int = 10) -> str:
        """Generate detailed report with worst queries.

        Args:
            limit: Maximum number of queries to include (default: 10)

        Returns:
            Formatted detailed report
        """
        slow_queries = self.tracker.get_slow_queries()

        if not slow_queries:
            return "No slow queries detected."

        lines = []
        lines.append("=" * 80)
        lines.append("SLOW QUERIES DETAILED REPORT")
        lines.append("=" * 80)
        lines.append(f"Showing top {min(limit, len(slow_queries))} slowest queries")
        lines.append("")

        for i, query_info in enumerate(slow_queries[:limit], 1):
            lines.append(f"#{i} - {query_info['execution_time_ms']:.2f}ms")
            lines.append("-" * 80)
            lines.append(self._format_query(query_info["query"]))
            if query_info.get("params"):
                lines.append(f"Parameters: {query_info['params']}")
            lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    def _format_query(self, query: str, max_lines: int = 20) -> str:
        """Format SQL query for display.

        Args:
            query: SQL query text
            max_lines: Maximum lines to display

        Returns:
            Formatted query text
        """
        lines = query.strip().split("\n")

        if len(lines) > max_lines:
            lines = lines[:max_lines] + ["... (truncated)"]

        return "\n".join("  " + line for line in lines)

    def print_report(self, detailed: bool = False, limit: int = 10):
        """Print report to logger.

        Args:
            detailed: If True, print detailed report with queries
            limit: Number of queries to include in detailed report
        """
        # Print summary
        summary_report = self.generate_summary_report()
        for line in summary_report.split("\n"):
            _logger.info(line)

        # Print detailed if requested
        if detailed:
            _logger.info("")
            detailed_report = self.generate_detailed_report(limit)
            for line in detailed_report.split("\n"):
                _logger.info(line)

    def export_to_dict(self) -> dict[str, Any]:
        """Export report data as dictionary for JSON serialization.

        Returns:
            Dictionary with summary and queries
        """
        return {
            "summary": self.tracker.get_summary(),
            "threshold_ms": self.tracker.threshold_ms,
            "slow_queries": [
                {
                    "query": q["query"],
                    "execution_time_ms": q["execution_time_ms"],
                    "params": str(q.get("params", "")),
                }
                for q in self.tracker.get_slow_queries()
            ],
        }


def create_slow_query_tracker(threshold_ms: float = 100.0) -> SlowQueryTracker:
    """Factory function to create a SlowQueryTracker instance.

    Args:
        threshold_ms: Threshold in milliseconds (default: 100ms)

    Returns:
        Configured SlowQueryTracker instance
    """
    return SlowQueryTracker(threshold_ms=threshold_ms)


def print_slow_query_report(tracker: SlowQueryTracker, detailed: bool = False, limit: int = 10):
    """Convenience function to print slow query report.

    Args:
        tracker: SlowQueryTracker instance with collected data
        detailed: If True, print detailed report
        limit: Number of queries to include in detailed report
    """
    report = SlowQueryReport(tracker)
    report.print_report(detailed=detailed, limit=limit)
