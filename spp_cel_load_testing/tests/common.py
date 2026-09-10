# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Performance Testing Base Classes and Utilities.

This module provides base classes and utilities for performance testing
of CEL expression evaluation, including:
- Benchmark timing utilities
- Query analysis and optimization
- Test data generation with Faker
- Performance assertion helpers
- Metrics reporting
"""

import logging
import time
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any

from faker import Faker

from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class PerformanceTestCase(TransactionCase):
    """Base class for CEL performance tests.

    Provides utilities for:
    - Benchmarking code execution time
    - Analyzing database queries and indexes
    - Generating realistic test data at scale
    - Asserting performance thresholds
    - Reporting metrics
    """

    # Performance thresholds (in milliseconds or seconds as indicated)
    PARSE_SIMPLE_MAX_MS = 1.0  # Simple expression parsing
    PARSE_COMPLEX_MAX_MS = 5.0  # Complex expression parsing
    TRANSLATE_CACHED_MAX_MS = 0.5  # Cached translation lookup
    TRANSLATE_UNCACHED_MAX_MS = 10.0  # First-time translation
    EVAL_SIMPLE_10K_MAX_S = 2.0  # 10K evaluations of simple expressions
    EVAL_COMPLEX_10K_MAX_S = 5.0  # 10K evaluations of complex expressions
    QUERY_MAX_MS = 100.0  # Individual query execution
    BULK_EVAL_1K_MAX_S = 1.0  # 1K bulk evaluations

    @classmethod
    def setUpClass(cls):
        """Initialize performance testing tools."""
        super().setUpClass()

        # Initialize CEL services
        # Note: Do NOT use 'cls.registry' as it conflicts with Odoo's TransactionCase.registry
        cls.translator = cls.env["spp.cel.translator"]
        cls.cel_registry = cls.env["spp.cel.registry"]
        cls.executor = cls.env["spp.cel.executor"]

        # Initialize Faker with a fixed seed for reproducibility
        cls.fake = Faker()
        Faker.seed(42)

        # Performance tracking
        cls._benchmark_results = {}
        cls._query_stats = []
        cls._index_recommendations = []

        # Try to initialize analysis tools (may not exist yet)
        try:
            from ..analysis.explain_analyzer import ExplainAnalyzer
            from ..analysis.index_advisor import IndexAdvisor
            from ..analysis.slow_query_report import SlowQueryTracker

            cls.explain_analyzer = ExplainAnalyzer(cls.env.cr)
            cls.index_advisor = IndexAdvisor(cls.env.cr)
            cls.slow_query_tracker = SlowQueryTracker(threshold_ms=100.0)
        except ImportError:
            _logger.warning("Analysis tools not available. Query analysis features disabled.")
            cls.explain_analyzer = None
            cls.index_advisor = None
            cls.slow_query_tracker = None

    @contextmanager
    def benchmark(self, name, print_result=True):
        """Context manager for benchmarking code execution.

        Args:
            name: Descriptive name for the benchmark
            print_result: Whether to print the result immediately

        Example:
            with self.benchmark("Parse 1000 expressions"):
                for expr in expressions:
                    parser.parse(expr)
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            elapsed_ms = elapsed * 1000

            # Store result
            self._benchmark_results[name] = {
                "elapsed_s": elapsed,
                "elapsed_ms": elapsed_ms,
            }

            # Also store per-test metrics for JSON export / analysis
            test_name = getattr(self, "_testMethodName", None)
            if test_name:
                if not hasattr(self, "_per_test_benchmarks"):
                    self._per_test_benchmarks = {}
                per_test = self._per_test_benchmarks.setdefault(test_name, {})
                per_test[name] = {
                    "elapsed_s": elapsed,
                    "elapsed_ms": elapsed_ms,
                }

            # Print if requested
            if print_result:
                if elapsed < 0.001:
                    _logger.info(f"{name}: {elapsed * 1_000_000:.2f} μs")
                elif elapsed < 1:
                    _logger.info(f"{name}: {elapsed_ms:.2f} ms")
                else:
                    _logger.info(f"{name}: {elapsed:.2f} s")

    @contextmanager
    def analyze_queries(self, operation_name: str = "Operation"):
        """Context manager for capturing and analyzing queries.

        Captures all SQL queries executed in the block using Odoo 19's
        sql_log_count and query_hooks mechanism.

        Args:
            operation_name: Descriptive name for the operation

        Example:
            with self.analyze_queries("Bulk evaluation"):
                evaluator.evaluate_bulk(expressions, records)
        """
        import threading

        # Get baseline query count using Odoo 19's sql_log_count
        query_count_before = getattr(self.env.cr, "sql_log_count", 0)

        # Set up query hook to capture actual SQL text (if analysis tools available)
        queries_captured = []

        def query_hook(cr, query, params, query_start, query_time):
            """Hook to capture query details for analysis."""
            queries_captured.append(
                {
                    "query": str(query),
                    "params": params,
                    "time": query_time,
                }
            )

        # Install query hook on current thread
        current_thread = threading.current_thread()
        hooks_installed = False
        if self.explain_analyzer:
            if not hasattr(current_thread, "query_hooks"):
                current_thread.query_hooks = []
            current_thread.query_hooks.append(query_hook)
            hooks_installed = True

        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start

            # Clean up query hook
            if hooks_installed:
                try:
                    current_thread.query_hooks.remove(query_hook)
                except (AttributeError, ValueError):
                    pass

            # Calculate query count using Odoo 19's sql_log_count
            query_count_after = getattr(self.env.cr, "sql_log_count", 0)
            num_queries = query_count_after - query_count_before

            _logger.info(f"{operation_name}: {num_queries} queries in {elapsed:.3f}s")

            # Analyze captured queries if we have the tools
            if self.explain_analyzer and queries_captured:
                try:
                    for query_info in queries_captured:
                        query = query_info.get("query", "")
                        if query and not query.strip().upper().startswith("EXPLAIN"):
                            # Run EXPLAIN ANALYZE
                            params = query_info.get("params")
                            explain_result = self.explain_analyzer.analyze_query(query, params)
                            if explain_result and explain_result.get("issues"):
                                self._query_stats.append(
                                    {
                                        "operation": operation_name,
                                        "query": query[:200],  # Truncate
                                        "explain": explain_result,
                                    }
                                )

                                # Get index recommendations based on EXPLAIN issues
                                if self.index_advisor:
                                    recommendations = self.index_advisor.analyze_explain_issues(
                                        explain_result.get("issues", [])
                                    )
                                    if recommendations:
                                        self._index_recommendations.extend(recommendations)

                except Exception as e:
                    _logger.warning(f"Query analysis failed: {e}")

    def generate_registrants(
        self,
        count: int,
        with_households: bool = False,
        prefix: str = "TestReg",
    ) -> list:
        """Generate test registrant records efficiently.

        Args:
            count: Number of registrants to create
            with_households: If True, also create household relationships
            prefix: Name prefix for generated records

        Returns:
            List of created res.partner records
        """
        _logger.info(f"Generating {count} registrants...")

        # Prepare batch data
        registrant_vals = []
        for i in range(count):
            # Generate realistic data with Faker
            # Note: gender_id is a Many2one, disabled is Datetime - skip these for simplicity
            birthdate = self.fake.date_of_birth(minimum_age=0, maximum_age=90)

            vals = {
                "name": f"{prefix} {self.fake.name()} {i}",
                "is_registrant": True,
                "is_group": False,
                "birthdate": birthdate,
                "phone": self.fake.phone_number()[:20],  # Limit length
                "email": self.fake.email(),
                "street": self.fake.street_address(),
                "city": self.fake.city(),
                # Random income between 0 and 10000
                "income": self.fake.random_int(min=0, max=10000),
            }
            registrant_vals.append(vals)

        # Batch create
        with self.benchmark(f"Create {count} registrants", print_result=True):
            registrants = self.env["res.partner"].create(registrant_vals)

        _logger.info(f"Created {len(registrants)} registrants")
        return registrants

    def generate_households(
        self,
        count: int,
        members_per: int = 5,
        prefix: str = "TestHH",
    ) -> tuple[list, list]:
        """Generate test household records with members.

        Args:
            count: Number of households to create
            members_per: Number of members per household
            prefix: Name prefix for generated households

        Returns:
            Tuple of (households, all_members) lists
        """
        _logger.info(f"Generating {count} households with {members_per} members each...")

        # Create households
        household_vals = []
        for i in range(count):
            vals = {
                "name": f"{prefix} {self.fake.last_name()} Family {i}",
                "is_registrant": True,
                "is_group": True,
            }
            household_vals.append(vals)

        with self.benchmark(f"Create {count} households"):
            households = self.env["res.partner"].create(household_vals)

        # Create members for each household
        all_members = []
        membership_vals = []

        for household in households:
            # Generate members for this household
            members = self.generate_registrants(
                members_per,
                with_households=False,
                prefix=f"Member-{household.id}",
            )
            all_members.extend(members)

            # Create membership links (without membership_type_ids for simplicity)
            for member in members:
                membership_vals.append(
                    {
                        "group": household.id,
                        "individual": member.id,
                    }
                )

        # Batch create memberships
        with self.benchmark(f"Create {len(membership_vals)} memberships"):
            self.env["spp.group.membership"].create(membership_vals)

        _logger.info(f"Created {len(households)} households with {len(all_members)} total members")
        return households, all_members

    def generate_events(
        self,
        registrants: list,
        event_type: str,
        count_per: int = 1,
        days_ago: int = 365,
    ) -> list:
        """Generate event data for testing event-based expressions.

        Args:
            registrants: List of res.partner records
            event_type: Type of event to generate
            count_per: Number of events per registrant
            days_ago: Maximum days in the past for event dates

        Returns:
            List of created event records
        """
        _logger.info(f"Generating {count_per} '{event_type}' events for {len(registrants)} registrants...")

        # This is a placeholder - actual implementation depends on your event model
        # Adjust based on your actual event data structure
        event_vals = []

        for registrant in registrants:
            for _ in range(count_per):
                # Random date within the past N days
                days_offset = self.fake.random_int(min=0, max=days_ago)
                event_date = date.today() - timedelta(days=days_offset)

                vals = {
                    "partner_id": registrant.id,
                    "event_type": event_type,
                    "event_date": event_date,
                    # Add event-specific fields based on type
                    "data": {
                        "income": self.fake.random_int(min=100, max=8000),
                        "employed": self.fake.boolean(chance_of_getting_true=60),
                        "score": self.fake.random_int(min=0, max=100),
                        "status": self.fake.random_element(["secure", "insecure", "moderate"]),
                    },
                }
                event_vals.append(vals)

        # Note: Replace 'spp.event' with your actual event model name
        # with self.benchmark(f"Create {len(event_vals)} events"):
        #     events = self.env['spp.event'].create(event_vals)

        # For now, return empty list - implement based on your event model
        _logger.warning("Event generation is a placeholder - implement based on your event model")
        return []

    def assert_performance(
        self,
        metric_name: str,
        value: float,
        threshold: float,
        unit: str = "ms",
    ):
        """Assert that a performance metric meets the threshold.

        Args:
            metric_name: Name of the metric being tested
            value: Actual measured value
            threshold: Maximum acceptable value
            unit: Unit of measurement (ms, s, etc.)

        Raises:
            AssertionError: If value exceeds threshold
        """
        self.assertLessEqual(
            value,
            threshold,
            f"{metric_name} exceeded threshold: {value:.2f}{unit} > {threshold:.2f}{unit}",
        )
        _logger.info(f"✓ {metric_name}: {value:.2f}{unit} (threshold: {threshold:.2f}{unit})")

    def report_metrics(self, metrics: dict[str, Any]):
        """Print a formatted table of performance metrics.

        Args:
            metrics: Dictionary of metric_name -> value
        """
        _logger.info("\n" + "=" * 70)
        _logger.info("PERFORMANCE METRICS")
        _logger.info("=" * 70)

        # Find longest key for alignment
        max_key_len = max(len(k) for k in metrics.keys()) if metrics else 20

        for name, value in metrics.items():
            # Format value based on type
            if isinstance(value, float):
                if value < 0.001:
                    formatted = f"{value * 1_000_000:.2f} μs"
                elif value < 1:
                    formatted = f"{value * 1000:.2f} ms"
                else:
                    formatted = f"{value:.2f} s"
            elif isinstance(value, int):
                formatted = f"{value:,}"
            else:
                formatted = str(value)

            _logger.info(f"  {name:<{max_key_len}} : {formatted}")

        _logger.info("=" * 70 + "\n")

    # Legacy compatibility methods (from old implementation)
    @contextmanager
    def timer(self, operation_name: str = "operation"):
        """Context manager to time operations (legacy compatibility).

        Usage:
            with self.timer("translate 1000 expressions") as t:
                # do work
                pass
            ops_per_sec = 1000 / t.elapsed

        Args:
            operation_name: Description of the operation being timed

        Yields:
            Timer object with elapsed property
        """
        timer_obj = Timer()
        start = time.perf_counter()
        try:
            yield timer_obj
        finally:
            end = time.perf_counter()
            timer_obj.elapsed = end - start
            _logger.info(
                "[PERF] %s: %.4f seconds (%.2f ops/sec)",
                operation_name,
                timer_obj.elapsed,
                1.0 / timer_obj.elapsed if timer_obj.elapsed > 0 else 0,
            )

    def measure_throughput(self, operation, count, operation_name="operation"):
        """Measure throughput of an operation (legacy compatibility).

        Args:
            operation: Callable to execute
            count: Number of times to execute
            operation_name: Description for logging

        Returns:
            dict with keys: elapsed, throughput, avg_time
        """
        start = time.perf_counter()
        for _ in range(count):
            operation()
        end = time.perf_counter()

        elapsed = end - start
        throughput = count / elapsed if elapsed > 0 else 0
        avg_time = elapsed / count if count > 0 else 0

        _logger.info(
            "[PERF] %s: %d operations in %.4f seconds = %.2f ops/sec (avg: %.6f sec/op)",
            operation_name,
            count,
            elapsed,
            throughput,
            avg_time,
        )

        return {
            "elapsed": elapsed,
            "throughput": throughput,
            "avg_time": avg_time,
            "count": count,
        }

    def print_benchmark_result(self, test_name, metrics):
        """Print formatted benchmark results (legacy compatibility).

        Args:
            test_name: Name of the test
            metrics: Dictionary of metric name -> value pairs
        """
        _logger.info("=" * 80)
        _logger.info("[BENCHMARK] %s", test_name)
        _logger.info("-" * 80)
        for metric, value in metrics.items():
            if isinstance(value, float):
                _logger.info("  %-30s: %.4f", metric, value)
            else:
                _logger.info("  %-30s: %s", metric, value)
        _logger.info("=" * 80)

    @classmethod
    def tearDownClass(cls):
        """Print summary reports and cleanup."""
        super().tearDownClass()

        # Print benchmark summary
        if cls._benchmark_results:
            _logger.info("\n" + "=" * 70)
            _logger.info("BENCHMARK SUMMARY")
            _logger.info("=" * 70)
            for name, result in cls._benchmark_results.items():
                elapsed = result["elapsed_s"]
                if elapsed < 0.001:
                    _logger.info(f"  {name}: {elapsed * 1_000_000:.2f} μs")
                elif elapsed < 1:
                    _logger.info(f"  {name}: {result['elapsed_ms']:.2f} ms")
                else:
                    _logger.info(f"  {name}: {elapsed:.2f} s")
            _logger.info("=" * 70 + "\n")

        # Print query analysis report
        if cls._query_stats:
            try:
                _logger.info("\n" + "=" * 70)
                _logger.info("QUERY ANALYSIS REPORT")
                _logger.info("=" * 70)
                for stat in cls._query_stats[:10]:  # Top 10
                    _logger.info(f"  Operation: {stat['operation']}")
                    _logger.info(f"  Query: {stat['query']}")
                    explain_info = stat.get("explain", {})
                    if explain_info.get("total_time_ms"):
                        _logger.info(f"  Total Time: {explain_info['total_time_ms']:.2f}ms")
                    if explain_info.get("issues"):
                        _logger.info(f"  Issues: {len(explain_info['issues'])}")
                    _logger.info("-" * 70)
                _logger.info("=" * 70 + "\n")
            except Exception as e:
                _logger.warning(f"Failed to print query analysis report: {e}")

        # Print index recommendations
        if cls._index_recommendations:
            _logger.info("\n" + "=" * 70)
            _logger.info("INDEX RECOMMENDATIONS")
            _logger.info("=" * 70)
            # Show first 20 recommendations (already collected during tests)
            for rec in cls._index_recommendations[:20]:
                _logger.info(f"  {rec}")
            _logger.info("=" * 70 + "\n")


class Timer:
    """Simple timer object for tracking elapsed time."""

    def __init__(self):
        self.elapsed = 0.0
