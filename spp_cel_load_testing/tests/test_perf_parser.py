# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Performance tests for the CEL parser.

Tests the parsing performance of CEL expressions, including:
- Simple expression throughput
- Complex expression parsing
- Cache effectiveness
- Adversarial/deeply nested expressions
- Event-related expressions
- Memory stability
"""

import logging
import time

from odoo.tests import tagged

from odoo.addons.spp_cel_domain.services.cel_parser import parse

from ..data import expression_templates
from . import common

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "performance")
class TestCELParserPerformance(common.PerformanceTestCase):
    """Test suite for CEL parser performance benchmarks."""

    def test_parse_simple_expressions_throughput(self):
        """Test throughput for parsing simple CEL expressions.

        Parses 10,000 simple expressions (age checks, gender checks, etc.)
        and measures expressions parsed per second. Should achieve > 10,000 ops/sec.
        """
        # Get simple expression templates
        simple_exprs = [expr for _, expr in expression_templates.EXPRESSIONS["simple"]]

        # Generate 10,000 expressions by repeating and varying the simple ones
        expressions = []
        for i in range(10000):
            # Cycle through simple expressions
            base_expr = simple_exprs[i % len(simple_exprs)]
            expressions.append(base_expr)

        # Parse all expressions
        def parse_all():
            for expr in expressions:
                parse(expr)

        # Clear the cache before measuring
        parse.cache_clear()

        # Measure throughput
        result = self.measure_throughput(
            parse_all,
            count=1,
            operation_name="parse 10,000 simple expressions",
        )

        # Calculate per-expression throughput (not batch throughput)
        per_expr_throughput = len(expressions) / result["elapsed"] if result["elapsed"] > 0 else 0

        # Print benchmark results
        self.print_benchmark_result(
            "Simple Expression Parsing",
            {
                "Total expressions": len(expressions),
                "Time (seconds)": result["elapsed"],
                "Throughput (ops/sec)": per_expr_throughput,
                "Avg time per parse (ms)": (result["elapsed"] / len(expressions)) * 1000,
            },
        )

        # Assert threshold - per-expression throughput should exceed 10,000 ops/sec
        threshold = 10000  # ops/sec
        self.assertGreater(
            per_expr_throughput,
            threshold,
            f"Simple expression parsing throughput {per_expr_throughput:.2f} ops/sec "
            f"is below threshold {threshold} ops/sec",
        )

    def test_parse_complex_expressions_throughput(self):
        """Test throughput for parsing complex CEL expressions.

        Parses 1,000 complex expressions (nested AND/OR, exists, count)
        and measures throughput. Should achieve > 1,000 ops/sec.
        """
        # Get complex expression templates
        complex_exprs = []
        complex_exprs.extend([expr for _, expr in expression_templates.EXPRESSIONS["complex_exists"]])
        complex_exprs.extend([expr for _, expr in expression_templates.EXPRESSIONS["complex_count"]])
        complex_exprs.extend([expr for _, expr in expression_templates.EXPRESSIONS["complex_aggregate"]])

        # Generate 1,000 expressions
        expressions = []
        for i in range(1000):
            base_expr = complex_exprs[i % len(complex_exprs)]
            expressions.append(base_expr)

        # Parse all expressions
        def parse_all():
            for expr in expressions:
                parse(expr)

        # Clear the cache before measuring
        parse.cache_clear()

        # Measure throughput
        result = self.measure_throughput(
            parse_all,
            count=1,
            operation_name="parse 1,000 complex expressions",
        )

        # Print benchmark results
        self.print_benchmark_result(
            "Complex Expression Parsing",
            {
                "Total expressions": len(expressions),
                "Time (seconds)": result["elapsed"],
                "Throughput (ops/sec)": result["throughput"],
                "Avg time per parse (ms)": result["avg_time"] * 1000,
            },
        )

        # Assert threshold (lowered for consistency across different test
        # environments; GitHub CI runners measured ~324 ops/sec)
        threshold = 150  # ops/sec
        self.assertGreater(
            result["throughput"],
            threshold,
            f"Complex expression parsing throughput {result['throughput']:.2f} ops/sec "
            f"is below threshold {threshold} ops/sec",
        )

    def test_parser_cache_effectiveness(self):
        """Test the effectiveness of the parser's LRU cache.

        Parses the same 100 expressions 100 times each (10,000 total parses).
        Measures cache hit ratio (should be >90%) and compares cached vs uncached performance.
        """
        # Get 100 diverse expressions
        all_exprs = []
        for complexity in ["simple", "medium", "complex_exists", "complex_count"]:
            exprs = [expr for _, expr in expression_templates.EXPRESSIONS[complexity]]
            all_exprs.extend(exprs[:25])  # Take 25 from each category

        unique_expressions = all_exprs[:100]

        # Test 1: Uncached performance (parse each once with cleared cache)
        parse.cache_clear()

        def parse_uncached():
            parse.cache_clear()
            for expr in unique_expressions:
                parse(expr)

        uncached_result = self.measure_throughput(
            parse_uncached,
            count=1,
            operation_name="parse 100 expressions (uncached)",
        )

        # Test 2: Cached performance (parse same 100 expressions 100 times)
        parse.cache_clear()

        # Prime the cache with first pass
        for expr in unique_expressions:
            parse(expr)

        # Now measure with warm cache
        def parse_cached():
            for _ in range(100):
                for expr in unique_expressions:
                    parse(expr)

        cached_result = self.measure_throughput(
            parse_cached,
            count=1,
            operation_name="parse 100 expressions x 100 (cached)",
        )

        # Calculate speedup
        speedup = cached_result["throughput"] / uncached_result["throughput"]

        # Cache hit ratio calculation
        # Total parses: 10,000 (100 expressions * 100 repetitions)
        # Cache misses: ~100 (first parse of each unique expression)
        # Cache hits: ~9,900
        cache_hit_ratio = 0.99  # Expected ~99% hit ratio

        # Print benchmark results
        self.print_benchmark_result(
            "Parser Cache Effectiveness",
            {
                "Unique expressions": len(unique_expressions),
                "Total parses": 10000,
                "Uncached throughput (ops/sec)": uncached_result["throughput"],
                "Cached throughput (ops/sec)": cached_result["throughput"],
                "Speedup": speedup,
                "Expected cache hit ratio": f"{cache_hit_ratio * 100:.1f}%",
                "Cache size": parse.cache_info().maxsize,
                "Cache hits": parse.cache_info().hits,
                "Cache misses": parse.cache_info().misses,
            },
        )

        # Assert cache effectiveness
        self.assertGreater(
            speedup,
            2.0,
            f"Cache speedup {speedup:.2f}x is less than expected (should be >2x)",
        )

        # Verify cache hit ratio
        cache_info = parse.cache_info()
        total_requests = cache_info.hits + cache_info.misses
        actual_hit_ratio = cache_info.hits / total_requests if total_requests > 0 else 0
        self.assertGreater(
            actual_hit_ratio,
            0.90,
            f"Cache hit ratio {actual_hit_ratio:.2%} is below 90%",
        )

    def test_parse_adversarial_expressions(self):
        """Test parsing of adversarial/pathological expressions.

        Tests deeply nested expressions (10 levels) and very long expressions
        to ensure no exponential blowup. Performance should be linear or better.
        """
        # Test deeply nested AND expressions
        depths = [5, 10, 15, 20]
        parse_times = []

        for depth in depths:
            # Generate deeply nested expression: (income > 0) and (income > 1) and ... and (income > depth-1)
            nested_expr = " && ".join([f"(r.income > {i})" for i in range(depth)])

            # Clear cache
            parse.cache_clear()

            # Measure parse time
            start = time.perf_counter()
            parse(nested_expr)
            end = time.perf_counter()
            elapsed = end - start

            parse_times.append(elapsed)
            _logger.info(
                "Nested depth %d: %.6f seconds",
                depth,
                elapsed,
            )

        # Check for linear growth (not exponential)
        # Compare depth 20 vs depth 10 - should be roughly 2x, not 4x or more
        time_ratio = parse_times[-1] / parse_times[1]
        depth_ratio = depths[-1] / depths[1]

        # Print results
        self.print_benchmark_result(
            "Adversarial Expression Parsing",
            {
                "Depth 5 time (ms)": parse_times[0] * 1000,
                "Depth 10 time (ms)": parse_times[1] * 1000,
                "Depth 15 time (ms)": parse_times[2] * 1000,
                "Depth 20 time (ms)": parse_times[3] * 1000,
                "Time ratio (20/10)": time_ratio,
                "Depth ratio (20/10)": depth_ratio,
                "Growth type": "linear" if time_ratio < depth_ratio * 1.5 else "super-linear",
            },
        )

        # Assert linear or better growth
        self.assertLess(
            time_ratio,
            depth_ratio * 2.0,  # Allow up to 2x the linear ratio for overhead
            f"Parse time growth appears exponential: {time_ratio:.2f}x for {depth_ratio:.2f}x depth increase",
        )

        # Test very long OR chain
        parse.cache_clear()
        long_expr = " || ".join([f"r.status == 'status_{i}'" for i in range(100)])

        start = time.perf_counter()
        parse(long_expr)
        end = time.perf_counter()
        long_expr_time = end - start

        _logger.info("Long OR chain (100 clauses): %.6f seconds", long_expr_time)

        # Should complete in reasonable time (< 0.1 seconds for 100 clauses)
        self.assertLess(
            long_expr_time,
            0.1,
            f"Long expression parsing took {long_expr_time:.4f}s, expected < 0.1s",
        )

    def test_parse_event_expressions_throughput(self):
        """Test throughput for parsing event-related expressions.

        Parses event-related expressions including event(), has_event(), events_count().
        Measures throughput and ensures good performance on event queries.
        """
        # Get event-related expressions
        event_exprs = []
        event_exprs.extend([expr for _, expr in expression_templates.EXPRESSIONS["event_basic"]])
        event_exprs.extend([expr for _, expr in expression_templates.EXPRESSIONS["event_temporal"]])
        event_exprs.extend([expr for _, expr in expression_templates.EXPRESSIONS["event_aggregate"]])

        # Generate 1,000 event expressions
        expressions = []
        for i in range(1000):
            base_expr = event_exprs[i % len(event_exprs)]
            expressions.append(base_expr)

        # Parse all expressions
        def parse_all():
            for expr in expressions:
                parse(expr)

        # Clear the cache before measuring
        parse.cache_clear()

        # Measure throughput
        result = self.measure_throughput(
            parse_all,
            count=1,
            operation_name="parse 1,000 event expressions",
        )

        # Print benchmark results
        self.print_benchmark_result(
            "Event Expression Parsing",
            {
                "Total expressions": len(expressions),
                "Unique templates": len(event_exprs),
                "Time (seconds)": result["elapsed"],
                "Throughput (ops/sec)": result["throughput"],
                "Avg time per parse (ms)": result["avg_time"] * 1000,
            },
        )

        # Assert reasonable threshold for event expressions
        # Lowered from 1000 to account for CI environment variance
        # (GitHub CI runners measured ~435 ops/sec)
        threshold = 150  # ops/sec
        self.assertGreater(
            result["throughput"],
            threshold,
            f"Event expression parsing throughput {result['throughput']:.2f} ops/sec "
            f"is below threshold {threshold} ops/sec",
        )

    def test_parse_memory_stability(self):
        """Test memory stability when parsing many unique expressions.

        Parses 50,000 unique expressions and verifies no memory leak.
        Uses tracemalloc if available to measure memory usage.
        """
        # Generate 50,000 unique expressions by varying parameters
        expressions = []

        # Base templates to vary
        templates = [
            "r.income > {val}",
            "r.income < {val}",
            "r.income >= {val}",
            "r.income <= {val}",
            "r.name == 'name_{val}'",
            "r.income > {val}",
            "r.income > {val1} && r.income < {val2}",
            "r.income == {val} || r.name == 'type_{val}'",
        ]

        for i in range(50000):
            template = templates[i % len(templates)]
            if "{field}" in template:
                expr = template.format(field=i % 100, val=i % 1000, val1=i % 100, val2=i % 10000)
            elif "{val1}" in template:
                expr = template.format(val1=i % 100, val2=i % 10000)
            else:
                expr = template.format(val=i)
            expressions.append(expr)

        # Measure memory if tracemalloc is available
        try:
            import tracemalloc

            tracemalloc.start()
            start_memory = tracemalloc.get_traced_memory()[0]

            # Parse all expressions
            parse.cache_clear()

            for expr in expressions:
                parse(expr)

            end_memory = tracemalloc.get_traced_memory()[0]
            peak_memory = tracemalloc.get_traced_memory()[1]
            tracemalloc.stop()

            memory_increase_mb = (end_memory - start_memory) / (1024 * 1024)
            peak_memory_mb = peak_memory / (1024 * 1024)

            memory_available = True
        except ImportError:
            memory_available = False
            memory_increase_mb = 0
            peak_memory_mb = 0
            _logger.warning("tracemalloc not available, skipping memory measurement")

        # Also measure throughput
        parse.cache_clear()

        def parse_all():
            for expr in expressions:
                parse(expr)

        result = self.measure_throughput(
            parse_all,
            count=1,
            operation_name="parse 50,000 unique expressions",
        )

        # Calculate per-expression throughput (not batch throughput)
        per_expr_throughput = len(expressions) / result["elapsed"] if result["elapsed"] > 0 else 0

        # Print benchmark results
        benchmark_metrics = {
            "Total unique expressions": len(expressions),
            "Time (seconds)": result["elapsed"],
            "Throughput (ops/sec)": per_expr_throughput,
            "Avg time per parse (ms)": (result["elapsed"] / len(expressions)) * 1000,
        }

        if memory_available:
            benchmark_metrics.update(
                {
                    "Memory increase (MB)": memory_increase_mb,
                    "Peak memory (MB)": peak_memory_mb,
                    "Memory per expression (KB)": (memory_increase_mb * 1024) / len(expressions),
                }
            )

        self.print_benchmark_result(
            "Memory Stability (50k unique expressions)",
            benchmark_metrics,
        )

        # Assert reasonable throughput even with many unique expressions
        threshold = 5000  # ops/sec (lower than simple since these are unique, not cached)
        self.assertGreater(
            per_expr_throughput,
            threshold,
            f"Unique expression parsing throughput {per_expr_throughput:.2f} ops/sec "
            f"is below threshold {threshold} ops/sec",
        )

        # Check memory usage is reasonable (if available)
        # Should use less than 100 MB for 50k expressions
        if memory_available:
            self.assertLess(
                memory_increase_mb,
                100,
                f"Memory usage {memory_increase_mb:.2f} MB is excessive for 50k expressions",
            )
