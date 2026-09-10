#!/usr/bin/env python3
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
# Standalone CLI tool: report output goes to stdout by design.
# pylint: disable=print-used
"""CLI Benchmark Runner for CEL Performance Tests.

This standalone script runs CEL expression performance benchmarks and generates
comprehensive reports. It integrates with Odoo to execute test suites and collect
performance metrics.

Usage:
    ./run_benchmarks.py --db mydb --suite all
    ./run_benchmarks.py --db mydb --suite parser --output json
    ./run_benchmarks.py --db mydb --suite eligibility --registrants 5000 --verbose
    ./run_benchmarks.py --db mydb --suite all --output csv --output-file results.csv

Exit codes:
    0 - All tests passed
    1 - Some tests failed
    2 - Configuration error
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
import unittest
from io import StringIO
from typing import Any

# Set up logging
_logger = logging.getLogger(__name__)


def _ensure_module_on_path() -> None:
    """Ensure the spp_cel_load_testing addon is importable.

    When this script is executed directly (e.g. ``python scripts/run_benchmarks.py``)
    Python sets ``sys.path[0]`` to the ``scripts`` directory. In that case the
    ``spp_cel_load_testing`` package is *not* importable unless the addons
    root (the directory containing the module) is also on ``sys.path``.

    This helper adds the addons root to ``sys.path`` when needed
    so imports like ``spp_cel_load_testing.tests.*`` work both inside and
    outside Docker.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # .../<addons root>/spp_cel_load_testing/scripts -> .../<addons root>
    addons_root = os.path.abspath(os.path.join(script_dir, os.pardir, os.pardir))
    if os.path.isdir(addons_root) and addons_root not in sys.path:
        sys.path.insert(0, addons_root)


_ensure_module_on_path()


def _configure_logging(verbose: bool, ai_friendly: bool, log_file: str | None) -> None:
    """Configure logging for benchmark runs.

    Console output is kept minimal (especially in AI-friendly mode) while an
    optional log file can capture full details.
    """
    # Base console level
    console_level = logging.DEBUG if verbose else logging.INFO
    if ai_friendly and not verbose:
        # Suppress routine INFO logs on console; keep warnings/errors
        console_level = logging.WARNING

    root = logging.getLogger()
    root.setLevel(console_level)

    # Optional detailed log file
    if log_file:
        file_handler = logging.FileHandler(log_file)
        # Always capture full detail in the log file so that
        # AI/CI consumers can inspect fine-grained timings even when
        # console output is kept minimal (e.g. --ai-friendly).
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)

    if ai_friendly:
        # Reduce noise from common chatty loggers; keep errors visible.
        for name in ("odoo", "werkzeug", "psycopg2"):
            logging.getLogger(name).setLevel(logging.WARNING)


def _import_odoo():
    """Import Odoo and add to path if needed.

    Returns:
        odoo module if successful, None otherwise
    """
    try:
        import odoo

        return odoo
    except ImportError:
        # Try to find Odoo in common locations
        odoo_paths = [
            "/opt/odoo",
            "/usr/lib/python3/dist-packages/odoo",
            os.path.expanduser("~/odoo"),
        ]
        for path in odoo_paths:
            if os.path.exists(path):
                sys.path.insert(0, os.path.dirname(path))
                break
        try:
            import odoo

            return odoo
        except ImportError:
            return None


class BenchmarkResult:
    """Container for individual benchmark test results."""

    def __init__(self, test_name: str):
        self.test_name = test_name
        self.status = "pending"  # pending, running, passed, failed, error
        self.elapsed_time = 0.0
        self.error_message = None
        self.metrics = {}
        self.warnings = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "test_name": self.test_name,
            "status": self.status,
            "elapsed_time": self.elapsed_time,
            "error_message": self.error_message,
            "metrics": self.metrics,
            "warnings": self.warnings,
        }


class BenchmarkRunner:
    """Main benchmark runner that executes tests and collects results."""

    # Map suite names to test module/class paths
    TEST_SUITES = {
        "parser": ("spp_cel_load_testing.tests.test_perf_parser", "TestCELParserPerformance"),
        "translator": ("spp_cel_load_testing.tests.test_perf_translator", "TestCELTranslatorPerformance"),
        "executor": ("spp_cel_load_testing.tests.test_perf_executor", "TestCELExecutorPerformance"),
        "eligibility": ("spp_cel_load_testing.tests.test_perf_eligibility", "TestEligibilityPerformance"),
        "bulk": ("spp_cel_load_testing.tests.test_perf_bulk_evaluation", "TestBulkEvaluationPerformance"),
        "event": ("spp_cel_load_testing.tests.test_perf_event_data", "TestEventDataPerformance"),
    }

    def __init__(self, db_name: str, verbose: bool = False):
        """Initialize the benchmark runner.

        Args:
            db_name: Name of the Odoo database to use
            verbose: Enable verbose logging output
        """
        self.db_name = db_name
        self.verbose = verbose
        self.results: list[BenchmarkResult] = []
        self.env = None

    def initialize_odoo_env(self) -> bool:
        """Initialize Odoo environment and connect to database.

        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            # Import Odoo
            odoo = _import_odoo()
            if not odoo:
                _logger.error("Cannot import Odoo. Please ensure Odoo is in your PYTHONPATH.")
                return False

            from odoo import SUPERUSER_ID, api
            from odoo.modules.registry import Registry

            _logger.info(f"Connecting to database: {self.db_name}")

            # Initialize Odoo
            odoo.tools.config.parse_config([])
            odoo.tools.config["db_name"] = self.db_name

            # Get registry (Odoo 19 compatible)
            registry = Registry(self.db_name)

            # Create environment
            with registry.cursor() as cr:
                self.env = api.Environment(cr, SUPERUSER_ID, {})

                # Verify spp_cel_load_testing is installed
                module = self.env["ir.module.module"].search(
                    [
                        ("name", "=", "spp_cel_load_testing"),
                        ("state", "=", "installed"),
                    ]
                )

                if not module:
                    _logger.error(
                        "spp_cel_load_testing module is not installed in database '%s'",
                        self.db_name,
                    )
                    return False

                _logger.info("Successfully connected to database")
                return True

        except Exception as e:
            _logger.error(f"Failed to initialize Odoo environment: {e}")
            if self.verbose:
                _logger.exception(e)
            return False

    def get_test_suite(self, suite_name: str) -> unittest.TestSuite | None:
        """Load a test suite by name.

        Args:
            suite_name: Name of the suite to load (parser, translator, etc.)

        Returns:
            TestSuite object or None if loading failed
        """
        if suite_name not in self.TEST_SUITES:
            _logger.error(f"Unknown test suite: {suite_name}")
            _logger.info(f"Available suites: {', '.join(self.TEST_SUITES.keys())}")
            return None

        module_path, class_name = self.TEST_SUITES[suite_name]

        try:
            # Import Odoo's test suite implementation (ensures proper setUpClass handling)
            odoo_module = _import_odoo()
            if not odoo_module:
                _logger.error("Cannot import Odoo test framework. Is Odoo installed?")
                return None

            from odoo.tests.suite import OdooSuite  # type: ignore[import]

            # Import the test module and class
            module = __import__(module_path, fromlist=[class_name])
            test_class = getattr(module, class_name)

            # Load tests using the standard unittest loader, then wrap in OdooSuite
            python_suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            odoo_suite = OdooSuite()
            for test in python_suite:
                odoo_suite.addTest(test)

            _logger.debug(f"Loaded {odoo_suite.countTestCases()} tests from {suite_name}")
            return odoo_suite

        except Exception as e:
            _logger.error(f"Failed to load test suite '{suite_name}': {e}")
            if self.verbose:
                _logger.exception(e)
            return None

    def run_suite(self, suite_name: str) -> list[BenchmarkResult]:
        """Run a single test suite and collect results.

        Args:
            suite_name: Name of the suite to run

        Returns:
            List of BenchmarkResult objects
        """
        _logger.info(f"Running test suite: {suite_name}")

        suite = self.get_test_suite(suite_name)
        if not suite:
            return []

        try:
            from odoo.tests.result import OdooTestResult  # type: ignore[import]
        except Exception as e:  # pragma: no cover - defensive
            _logger.error("Failed to import OdooTestResult: %s", e)
            if self.verbose:
                _logger.exception(e)
            return []

        class BenchmarkOdooTestResult(OdooTestResult):
            """Odoo test result that populates BenchmarkResult objects."""

            def __init__(self, suite_label: str):
                super().__init__()
                self._suite_label = suite_label
                self.benchmark_results: dict[str, BenchmarkResult] = {}
                self._start_times: dict[str, float] = {}

            def startTest(self, test):  # type: ignore[override]
                test_id = test.id()
                # record high-precision start time for the test
                self._start_times[test_id] = time.perf_counter()

                super().startTest(test)
                test_name = getattr(test, "_testMethodName", test_id)
                bench_name = f"{self._suite_label}.{test_name}"
                bench_result = BenchmarkResult(bench_name)
                bench_result.status = "running"
                self.benchmark_results[test_id] = bench_result

            def stopTest(self, test):  # type: ignore[override]
                super().stopTest(test)
                test_id = test.id()
                bench_result = self.benchmark_results.get(test_id)
                if bench_result:
                    # Prefer our own timer; fall back to Odoo stats if needed
                    end = time.perf_counter()
                    start = self._start_times.pop(test_id, None)
                    if start is not None:
                        bench_result.elapsed_time = end - start
                    else:
                        stat = self.stats.get(test_id)
                        if stat:
                            bench_result.elapsed_time = stat.time

                    # Attach basic metrics for downstream analysis
                    stat = self.stats.get(test_id)
                    if stat:
                        bench_result.metrics.setdefault("queries", stat.queries)
                        bench_result.metrics.setdefault("time_s", stat.time)

                    # Attach fine-grained benchmark timings when available.
                    # PerformanceTestCase.benchmark() stores per-test metrics
                    # on ``test._per_test_benchmarks[method_name]``.
                    per_test = getattr(test, "_per_test_benchmarks", None)
                    if isinstance(per_test, dict):
                        method_name = getattr(test, "_testMethodName", test_id)
                        benchmarks_for_test = per_test.get(method_name)
                        if isinstance(benchmarks_for_test, dict):
                            bench_result.metrics.setdefault("benchmarks", benchmarks_for_test)

            def addSuccess(self, test):  # type: ignore[override]
                bench_result = self.benchmark_results.get(test.id())
                if bench_result:
                    bench_result.status = "passed"
                super().addSuccess(test)

            def addFailure(self, test, err):  # type: ignore[override]
                bench_result = self.benchmark_results.get(test.id())
                if bench_result:
                    bench_result.status = "failed"
                    bench_result.error_message = self._exc_info_to_string(err, test)
                super().addFailure(test, err)

            def addError(self, test, err):  # type: ignore[override]
                bench_result = self.benchmark_results.get(test.id())
                if bench_result:
                    bench_result.status = "error"
                    bench_result.error_message = self._exc_info_to_string(err, test)
                super().addError(test, err)

            def addSkip(self, test, reason):  # type: ignore[override]
                bench_result = self.benchmark_results.get(test.id())
                if bench_result:
                    bench_result.status = "pending"
                    bench_result.warnings.append(f"Skipped: {reason}")
                super().addSkip(test, reason)

        _logger.info("  Executing Odoo test suite for: %s", suite_name)
        result = BenchmarkOdooTestResult(suite_name)

        # Run the whole OdooSuite; it will handle class-level fixtures correctly
        suite(result)

        # Collect benchmark results for this suite
        suite_results = list(result.benchmark_results.values())
        if self.verbose:
            _logger.debug(
                "Suite '%s' finished: %d tests, %d failures, %d errors",
                suite_name,
                result.testsRun,
                result.failures_count,
                result.errors_count,
            )

        return suite_results

    def run_all_suites(self, suite_names: list[str]) -> list[BenchmarkResult]:
        """Run multiple test suites.

        Args:
            suite_names: List of suite names to run

        Returns:
            Combined list of all BenchmarkResult objects
        """
        all_results = []

        for suite_name in suite_names:
            suite_results = self.run_suite(suite_name)
            all_results.extend(suite_results)

        return all_results

    def generate_summary(self, results: list[BenchmarkResult]) -> dict[str, Any]:
        """Generate summary statistics from results.

        Args:
            results: List of BenchmarkResult objects

        Returns:
            Dictionary containing summary statistics
        """
        total = len(results)
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        errors = sum(1 for r in results if r.status == "error")

        total_time = sum(r.elapsed_time for r in results)

        # Collect performance regressions (tests that took longer than expected)
        regressions = []
        for r in results:
            # This is a placeholder - actual regression detection would compare
            # against baseline metrics
            if r.elapsed_time > 10.0:  # Simple threshold for demo
                regressions.append(
                    {
                        "test": r.test_name,
                        "time": r.elapsed_time,
                    }
                )

        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total_time": total_time,
            "pass_rate": (passed / total * 100) if total > 0 else 0,
            "regressions": regressions,
        }


class ReportGenerator:
    """Generate reports in various formats."""

    @staticmethod
    def format_time(seconds: float) -> str:
        """Format time in human-readable format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted string (e.g., "123.45ms", "1.23s")
        """
        if seconds < 0.001:
            return f"{seconds * 1_000_000:.2f}μs"
        elif seconds < 1:
            return f"{seconds * 1000:.2f}ms"
        else:
            return f"{seconds:.2f}s"

    @classmethod
    def generate_table(cls, results: list[BenchmarkResult], summary: dict[str, Any]) -> str:
        """Generate ASCII table report.

        Args:
            results: List of BenchmarkResult objects
            summary: Summary statistics dictionary

        Returns:
            Formatted table as string
        """
        output = StringIO()

        # Header
        output.write("\n" + "=" * 100 + "\n")
        output.write("CEL PERFORMANCE BENCHMARK RESULTS\n")
        output.write("=" * 100 + "\n\n")

        # Test results table
        output.write(f"{'Test Name':<50} {'Status':<10} {'Time':<15}\n")
        output.write("-" * 100 + "\n")

        for result in results:
            status_symbol = {
                "passed": "✓ PASS",
                "failed": "✗ FAIL",
                "error": "✗ ERROR",
                "pending": "- PENDING",
            }.get(result.status, "?")

            time_str = cls.format_time(result.elapsed_time)

            output.write(f"{result.test_name:<50} {status_symbol:<10} {time_str:<15}\n")

            # Show error message if failed/error
            if result.error_message and result.status in ("failed", "error"):
                # Truncate long error messages
                error_preview = result.error_message[:200]
                if len(result.error_message) > 200:
                    error_preview += "..."
                output.write(f"  Error: {error_preview}\n")

        output.write("-" * 100 + "\n\n")

        # Summary
        output.write("SUMMARY\n")
        output.write("-" * 100 + "\n")
        output.write(f"Total Tests:     {summary['total_tests']}\n")
        output.write(f"Passed:          {summary['passed']} ({summary['pass_rate']:.1f}%)\n")
        output.write(f"Failed:          {summary['failed']}\n")
        output.write(f"Errors:          {summary['errors']}\n")
        output.write(f"Total Time:      {cls.format_time(summary['total_time'])}\n")

        if summary["regressions"]:
            output.write(f"\nPerformance Regressions Detected: {len(summary['regressions'])}\n")
            for reg in summary["regressions"]:
                output.write(f"  - {reg['test']}: {cls.format_time(reg['time'])}\n")

        output.write("=" * 100 + "\n")

        return output.getvalue()

    @staticmethod
    def generate_json(results: list[BenchmarkResult], summary: dict[str, Any]) -> str:
        """Generate JSON report.

        Args:
            results: List of BenchmarkResult objects
            summary: Summary statistics dictionary

        Returns:
            JSON string
        """
        report = {
            "summary": summary,
            "results": [r.to_dict() for r in results],
        }
        return json.dumps(report, indent=2)

    @staticmethod
    def generate_csv(results: list[BenchmarkResult]) -> str:
        """Generate CSV report.

        Args:
            results: List of BenchmarkResult objects

        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow(["Test Name", "Status", "Elapsed Time (s)", "Error Message"])

        # Data rows
        for result in results:
            writer.writerow(
                [
                    result.test_name,
                    result.status,
                    f"{result.elapsed_time:.6f}",
                    result.error_message or "",
                ]
            )

        return output.getvalue()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="CEL Performance Benchmark Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all benchmarks on database 'mydb'
  %(prog)s --db mydb --suite all

  # Run parser benchmarks only with JSON output
  %(prog)s --db mydb --suite parser --output json

  # Run eligibility tests with custom registrant count
  %(prog)s --db mydb --suite eligibility --registrants 5000

  # Run multiple specific suites
  %(prog)s --db mydb --suite parser --suite translator --suite executor

  # Export results to CSV file
  %(prog)s --db mydb --suite all --output csv --output-file results.csv

Available test suites:
  all          - Run all test suites
  parser       - CEL parser performance tests
  translator   - CEL translator performance tests
  executor     - CEL executor performance tests
  eligibility  - Program eligibility evaluation tests
  bulk         - Bulk evaluation performance tests
  event        - Event data query performance tests

Exit codes:
  0 - All tests passed
  1 - Some tests failed
  2 - Configuration error
        """,
    )

    parser.add_argument(
        "--db",
        required=True,
        help="Odoo database name (required)",
    )

    parser.add_argument(
        "--suite",
        action="append",
        choices=["all", "parser", "translator", "executor", "eligibility", "bulk", "event"],
        default=[],
        help="Test suite to run (can be specified multiple times). Use 'all' for all suites.",
    )

    parser.add_argument(
        "--registrants",
        type=int,
        default=1000,
        help="Number of test registrants to generate (default: 1000)",
    )

    parser.add_argument(
        "--output",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )

    parser.add_argument(
        "--output-file",
        type=str,
        help="Write benchmark report to file instead of stdout",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        help="Optional log file for detailed logs (DEBUG level)",
    )

    parser.add_argument(
        "--ai-friendly",
        action="store_true",
        help="Reduce console logs to essentials for easier AI/CI consumption",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (overrides --ai-friendly for console level)",
    )

    return parser.parse_args()


def main():
    """Main entry point for the benchmark runner."""
    args = parse_arguments()

    # Validate suite selection
    if not args.suite:
        print("ERROR: No test suite specified. Use --suite to select test suites.")
        print("Run with --help for usage information.")
        sys.exit(2)

    # Configure logging before doing anything else
    _configure_logging(verbose=args.verbose, ai_friendly=args.ai_friendly, log_file=args.log_file)

    # Expand 'all' to all available suites
    if "all" in args.suite:
        suite_names = list(BenchmarkRunner.TEST_SUITES.keys())
    else:
        suite_names = args.suite

    # Initialize benchmark runner
    runner = BenchmarkRunner(args.db, verbose=args.verbose)

    # Initialize Odoo environment
    if not runner.initialize_odoo_env():
        _logger.error("Failed to initialize Odoo environment")
        sys.exit(2)

    # Propagate desired registrant count into Odoo config so tests can pick it up
    try:
        odoo = _import_odoo()
        if odoo:
            odoo.tools.config["cel_benchmark_registrants"] = int(args.registrants)
            _logger.info("Using registrant count for benchmarks: %s", args.registrants)
    except Exception as e:  # pragma: no cover - defensive
        _logger.warning("Failed to propagate registrant count to Odoo config: %s", e)

    # Run benchmarks
    _logger.info(f"Running {len(suite_names)} test suite(s): {', '.join(suite_names)}")
    start_time = time.perf_counter()

    results = runner.run_all_suites(suite_names)

    total_elapsed = time.perf_counter() - start_time
    _logger.info(f"All benchmarks completed in {ReportGenerator.format_time(total_elapsed)}")

    # Generate summary
    summary = runner.generate_summary(results)

    # Generate report in requested format
    report_gen = ReportGenerator()

    if args.output == "table":
        report = report_gen.generate_table(results, summary)
    elif args.output == "json":
        report = report_gen.generate_json(results, summary)
    elif args.output == "csv":
        report = report_gen.generate_csv(results)
    else:
        report = report_gen.generate_table(results, summary)  # Default

    # Output report
    if args.output_file:
        try:
            with open(args.output_file, "w") as f:
                f.write(report)
            _logger.info(f"Report written to: {args.output_file}")
        except Exception as e:
            _logger.error(f"Failed to write report to file: {e}")
            # Fall back to stdout
            print(report)
    else:
        print(report)

    # Determine exit code
    if summary["failed"] > 0 or summary["errors"] > 0:
        _logger.warning("Some tests failed or had errors")
        sys.exit(1)
    else:
        _logger.info("All tests passed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
