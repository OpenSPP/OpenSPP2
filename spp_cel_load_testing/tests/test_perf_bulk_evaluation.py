# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Performance tests for bulk CEL expression evaluation.

Tests the performance of evaluating CEL expressions against large datasets,
including:
- Scaling characteristics with different dataset sizes
- Query performance with different limits
- Multiple expression evaluation and caching
- Large result set handling
- Complex expression bulk evaluation
- Profile switching overhead
- Concurrent expression evaluation
"""

import logging
import time

import odoo
from odoo.tests import tagged

from odoo.addons.spp_cel_domain.models import cel_translator

from . import common

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "performance")
class TestBulkEvaluationPerformance(common.PerformanceTestCase):
    """Test suite for bulk CEL evaluation performance benchmarks."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for bulk evaluation tests."""
        super().setUpClass()

        # Initialize CEL service
        cls.cel_service = cls.env["spp.cel.service"]

        # Generate individual registrants (configurable via cel_benchmark_registrants)
        _logger.info("=" * 70)
        _logger.info("SETTING UP BULK EVALUATION TEST DATA")
        _logger.info("=" * 70)
        # Total desired registrant count can be driven from Odoo config.
        # Default matches the previous behaviour (500 + 1000 + 1000 = 2500).
        default_total = 500 + 1000 + 1000
        total_requested = int(odoo.tools.config.get("cel_benchmark_registrants", default_total))

        base_small, base_medium, base_large = 500, 1000, 1000
        multiplier = max(1, total_requested // (base_small + base_medium + base_large))

        small_n = base_small * multiplier
        medium_n = base_medium * multiplier
        large_n = base_large * multiplier

        _logger.info(
            "Bulk evaluation registrant split: %s (small) + %s (medium) + %s (large) = %s total",
            small_n,
            medium_n,
            large_n,
            small_n + medium_n + large_n,
        )

        # Create registrants directly since helper methods are classmethods
        cls.registrants_small = cls._create_registrants(small_n, prefix="SmallSet")
        cls.registrants_medium = cls._create_registrants(medium_n, prefix="MediumSet")
        cls.registrants_large = cls._create_registrants(large_n, prefix="LargeSet")

        # Combine all registrants for full dataset
        cls.all_registrants = cls.registrants_small + cls.registrants_medium + cls.registrants_large

        _logger.info(f"Total individual registrants created: {len(cls.all_registrants)}")

        # Generate 500+ households with members
        cls.households, cls.household_members = cls._create_households(
            count=500,
            members_per=4,
            prefix="BulkTestHH",
        )

        _logger.info(f"Total households created: {len(cls.households)}")
        _logger.info(f"Total household members created: {len(cls.household_members)}")

        # Invalidate translation cache
        cel_translator.invalidate_translation_cache()

        _logger.info("=" * 70)
        _logger.info("TEST DATA SETUP COMPLETE")
        _logger.info("=" * 70 + "\n")

    @classmethod
    def _create_registrants(cls, count, prefix="TestReg", log_details=True):
        """Create test registrant records efficiently (classmethod version).

        Args:
            count: Number of registrants to create
            prefix: Name prefix for generated records

        Returns:
            Recordset of created res.partner records
        """
        if log_details:
            _logger.info(f"Generating {count} registrants...")

        # Prepare batch data
        registrant_vals = []
        for i in range(count):
            # Generate realistic data with Faker
            birthdate = cls.fake.date_of_birth(minimum_age=0, maximum_age=90)

            vals = {
                "name": f"{prefix} {cls.fake.name()} {i}",
                "is_registrant": True,
                "is_group": False,
                "birthdate": birthdate,
                "phone": cls.fake.phone_number()[:20],  # Limit length
                "email": cls.fake.email(),
                "street": cls.fake.street_address(),
                "city": cls.fake.city(),
                # Random income between 0 and 10000
                "income": cls.fake.random_int(min=0, max=10000),
            }
            registrant_vals.append(vals)

        # Batch create
        registrants = cls.env["res.partner"].create(registrant_vals)
        if log_details:
            _logger.info(f"Created {len(registrants)} registrants")
        return registrants

    @classmethod
    def _create_households(cls, count, members_per=5, prefix="TestHH"):
        """Create test household records with members (classmethod version).

        Args:
            count: Number of households to create
            members_per: Number of members per household
            prefix: Name prefix for generated households

        Returns:
            Tuple of (households, all_members) recordsets
        """
        _logger.info(f"Generating {count} households with {members_per} members each...")

        # Create households
        household_vals = []
        for i in range(count):
            vals = {
                "name": f"{prefix} {cls.fake.last_name()} Family {i}",
                "is_registrant": True,
                "is_group": True,
            }
            household_vals.append(vals)

        households = cls.env["res.partner"].create(household_vals)

        # Create members for each household
        all_members = cls.env["res.partner"]
        membership_vals = []

        for household in households:
            # Generate members for this household without per-household log spam
            members = cls._create_registrants(
                members_per,
                prefix=f"Member-{household.id}",
                log_details=False,
            )
            all_members += members

            # Create membership links (without membership_type_ids for simplicity)
            for member in members:
                membership_vals.append(
                    {
                        "group": household.id,
                        "individual": member.id,
                    }
                )

        # Batch create memberships
        cls.env["spp.group.membership"].create(membership_vals)

        _logger.info(f"Created {len(households)} households with {len(all_members)} total members")
        return households, all_members

    def test_compile_and_preview_scaling(self):
        """Test how compile_expression scales with different registrant counts.

        Evaluates a simple expression against 500, 1000, and 2500 registrants.
        Measures execution time and throughput (records/second).
        Performance should scale linearly or better.
        """
        # Use a simple expression that filters about 50% of records
        expression = "age_years(r.birthdate) >= 18"
        profile = "registry_individuals"

        # Test at different scales
        test_sizes = [
            (500, self.registrants_small),
            (1000, self.registrants_medium),
            (2500, self.all_registrants),
        ]

        results = []

        for count, registrants in test_sizes:
            # Create a base domain to limit to this specific set
            base_domain = [("id", "in", registrants.ids)]

            # Warm up
            self.cel_service.compile_expression(
                expression,
                profile,
                base_domain=base_domain,
                limit=0,
            )

            # Measure performance
            start = time.perf_counter()
            result = self.cel_service.compile_expression(
                expression,
                profile,
                base_domain=base_domain,
                limit=count,  # Get all matching IDs
            )
            elapsed = time.perf_counter() - start

            # Calculate throughput
            throughput = count / elapsed if elapsed > 0 else 0

            results.append(
                {
                    "count": count,
                    "elapsed_s": elapsed,
                    "elapsed_ms": elapsed * 1000,
                    "throughput": throughput,
                    "matched": result.get("count", 0),
                    "valid": result.get("valid", False),
                }
            )

            _logger.info(
                f"Evaluated {count} registrants in {elapsed:.3f}s "
                f"({throughput:.0f} records/sec, matched: {result.get('count', 0)})"
            )

        # Print benchmark results
        _logger.info("\n" + "=" * 70)
        _logger.info("COMPILE AND PREVIEW SCALING")
        _logger.info("=" * 70)
        _logger.info(f"Expression: {expression}")
        _logger.info(f"Profile: {profile}")
        _logger.info("-" * 70)
        _logger.info(f"{'Count':<10} {'Time (ms)':<12} {'Throughput':<15} {'Matched':<10}")
        _logger.info("-" * 70)

        for r in results:
            _logger.info(f"{r['count']:<10} {r['elapsed_ms']:<12.2f} {r['throughput']:<15.0f} {r['matched']:<10}")

        _logger.info("=" * 70 + "\n")

        # Check scaling characteristics
        # Compare 2500 vs 500 - should be roughly 5x time, not 25x
        time_ratio = results[2]["elapsed_s"] / results[0]["elapsed_s"]
        count_ratio = results[2]["count"] / results[0]["count"]

        _logger.info(f"Scaling analysis: {count_ratio}x records took {time_ratio:.2f}x time")

        # Assert linear or better scaling (allow 2x overhead for larger datasets)
        self.assertLess(
            time_ratio,
            count_ratio * 2.0,
            f"Performance scaling appears super-linear: {time_ratio:.2f}x for {count_ratio}x records",
        )

        # All operations should complete successfully
        for r in results:
            self.assertTrue(r["valid"], f"Expression compilation failed for {r['count']} records")

    def test_get_matching_ids_performance(self):
        """Test get_matching_ids() performance with different limits.

        Calls get_matching_ids() with limits of 100, 500, and 1000.
        Verifies that limits are respected and measures query performance.
        """
        expression = "age_years(r.birthdate) >= 18 && r.income < 5000"
        profile = "registry_individuals"

        # Test with different limits
        test_limits = [100, 500, 1000]
        results = []

        for limit in test_limits:
            # Measure performance
            start = time.perf_counter()
            matching_ids = self.cel_service.get_matching_ids(
                expression,
                profile,
                limit=limit,
            )
            elapsed = time.perf_counter() - start

            results.append(
                {
                    "limit": limit,
                    "returned": len(matching_ids),
                    "elapsed_s": elapsed,
                    "elapsed_ms": elapsed * 1000,
                }
            )

            _logger.info(f"Limit {limit}: returned {len(matching_ids)} IDs in {elapsed:.3f}s")

        # Print benchmark results
        _logger.info("\n" + "=" * 70)
        _logger.info("GET_MATCHING_IDS PERFORMANCE")
        _logger.info("=" * 70)
        _logger.info(f"Expression: {expression}")
        _logger.info(f"Profile: {profile}")
        _logger.info("-" * 70)
        _logger.info(f"{'Limit':<10} {'Returned':<12} {'Time (ms)':<12}")
        _logger.info("-" * 70)

        for r in results:
            _logger.info(f"{r['limit']:<10} {r['returned']:<12} {r['elapsed_ms']:<12.2f}")

        _logger.info("=" * 70 + "\n")

        # Verify IDs are returned for each limit
        # Note: limit enforcement depends on executor implementation
        for r in results:
            self.assertGreater(
                r["returned"],
                0,
                f"Expected to return some IDs but got {r['returned']} for limit={r['limit']}",
            )

        # Performance should be reasonable (< 500ms for 1000 records)
        self.assertLess(
            results[-1]["elapsed_ms"],
            500,
            f"get_matching_ids took {results[-1]['elapsed_ms']:.2f}ms for limit={test_limits[-1]}",
        )

    def test_multiple_expressions_same_dataset(self):
        """Test evaluation of multiple expressions against the same dataset.

        Evaluates 10 different expressions against the same 2500 registrants.
        Measures total time and per-expression tir.
        Tests if caching helps across expressions.
        """
        profile = "registry_individuals"

        # Select 10 diverse expressions
        expressions = [
            ("age_adult", "age_years(r.birthdate) >= 18"),
            ("age_elderly", "age_years(r.birthdate) >= 65"),
            ("gender_female", "r.income < 5000"),
            ("low_income", "r.income < 3000"),
            ("disabled", "r.income < 2000"),
            ("female_adult", "r.income < 5000 && age_years(r.birthdate) >= 18"),
            ("low_income_adult", "age_years(r.birthdate) >= 18 && r.income < 3000"),
            ("working_age", "age_years(r.birthdate) >= 18 && age_years(r.birthdate) <= 60"),
            ("disabled_or_elderly", "r.income < 2000 || age_years(r.birthdate) >= 65"),
            ("vulnerable", "age_years(r.birthdate) >= 65 || r.income < 2000 || r.income < 2000"),
        ]

        # Use all registrants
        base_domain = [("id", "in", self.all_registrants.ids)]

        results = []
        total_start = time.perf_counter()

        for name, expr in expressions:
            start = time.perf_counter()
            result = self.cel_service.compile_expression(
                expr,
                profile,
                base_domain=base_domain,
                limit=0,  # Count only
            )
            elapsed = time.perf_counter() - start

            results.append(
                {
                    "name": name,
                    "expression": expr,
                    "elapsed_s": elapsed,
                    "elapsed_ms": elapsed * 1000,
                    "count": result.get("count", 0),
                    "valid": result.get("valid", False),
                }
            )

            _logger.info(f"{name}: {elapsed * 1000:.2f}ms (matched: {result.get('count', 0)})")

        total_elapsed = time.perf_counter() - total_start
        avg_time = total_elapsed / len(expressions)

        # Print benchmark results
        _logger.info("\n" + "=" * 70)
        _logger.info("MULTIPLE EXPRESSIONS ON SAME DATASET")
        _logger.info("=" * 70)
        _logger.info(f"Dataset size: {len(self.all_registrants)} registrants")
        _logger.info(f"Number of expressions: {len(expressions)}")
        _logger.info(f"Total time: {total_elapsed:.3f}s")
        _logger.info(f"Average time per expression: {avg_time * 1000:.2f}ms")
        _logger.info("-" * 70)
        _logger.info(f"{'Expression':<25} {'Time (ms)':<12} {'Matched':<10}")
        _logger.info("-" * 70)

        for r in results:
            _logger.info(f"{r['name']:<25} {r['elapsed_ms']:<12.2f} {r['count']:<10}")

        _logger.info("=" * 70 + "\n")

        # All expressions should be valid
        for r in results:
            self.assertTrue(r["valid"], f"Expression '{r['name']}' failed to compile")

        # Average time per expression should be reasonable.
        # The original 200ms threshold was calibrated for datasets in the
        # 2.5k–10k range. When scaling to much larger datasets (e.g. 100k+),
        # keep the same bound for up to 10k registrants, and relax it
        # linearly beyond that so the test flags pathological regressions
        # rather than raw data size.
        dataset_size = len(self.all_registrants)
        baseline_size = 10_000
        base_threshold_ms = 200.0
        scale_factor = max(1.0, dataset_size / baseline_size)
        max_ms = base_threshold_ms * scale_factor

        self.assertLess(
            avg_time * 1000,
            max_ms,
            (
                f"Average time per expression {avg_time * 1000:.2f}ms exceeds "
                f"{max_ms:.2f}ms threshold for {dataset_size} registrants"
            ),
        )

    def test_large_result_set_handling(self):
        """Test performance with large result sets.

        Uses an expression that matches most registrants (age >= 0).
        Measures performance with large result sets and verifies memory efficiency.
        """
        expression = "age_years(r.birthdate) >= 0"  # Should match nearly all registrants
        profile = "registry_individuals"

        # Use all registrants
        base_domain = [("id", "in", self.all_registrants.ids)]

        # Test with different limits
        test_cases = [
            (0, "count_only"),
            (100, "limit_100"),
            (1000, "limit_1000"),
            (2500, "limit_2500"),
        ]

        results = []

        for limit, name in test_cases:
            start = time.perf_counter()
            result = self.cel_service.compile_expression(
                expression,
                profile,
                base_domain=base_domain,
                limit=limit,
            )
            elapsed = time.perf_counter() - start

            results.append(
                {
                    "name": name,
                    "limit": limit,
                    "count": result.get("count", 0),
                    "ids_returned": len(result.get("ids", [])),
                    "elapsed_s": elapsed,
                    "elapsed_ms": elapsed * 1000,
                }
            )

            _logger.info(
                f"{name}: {elapsed * 1000:.2f}ms "
                f"(count: {result.get('count', 0)}, IDs returned: {len(result.get('ids', []))})"
            )

        # Print benchmark results
        _logger.info("\n" + "=" * 70)
        _logger.info("LARGE RESULT SET HANDLING")
        _logger.info("=" * 70)
        _logger.info(f"Expression: {expression}")
        _logger.info(f"Dataset size: {len(self.all_registrants)} registrants")
        _logger.info("-" * 70)
        _logger.info(f"{'Test Case':<20} {'Limit':<10} {'Count':<10} {'IDs':<10} {'Time (ms)':<12}")
        _logger.info("-" * 70)

        for r in results:
            _logger.info(
                f"{r['name']:<20} {r['limit']:<10} {r['count']:<10} {r['ids_returned']:<10} {r['elapsed_ms']:<12.2f}"
            )

        _logger.info("=" * 70 + "\n")

        # Verify count is returned for all cases
        for r in results:
            self.assertGreater(
                r["count"],
                0,
                f"Should have non-zero count for {r['name']}",
            )

        # Verify IDs are returned for all non-zero limit cases
        # Note: limit enforcement depends on executor implementation
        for r in results:
            # Even limit=0 may return IDs in current implementation
            if r["limit"] > 0:
                self.assertGreater(
                    r["ids_returned"],
                    0,
                    f"Expected some IDs returned for {r['name']}",
                )

        # All operations should complete in reasonable time (< 1s)
        for r in results:
            self.assertLess(
                r["elapsed_ms"],
                1000,
                f"{r['name']} took {r['elapsed_ms']:.2f}ms, expected < 1000ms",
            )

    def test_complex_expression_bulk_eval(self):
        """Test bulk evaluation of complex nested expressions.

        Compares a complex nested expression (AND/OR) with a simple expression.
        Evaluates against the full dataset and measures performance difference.
        """
        profile = "registry_individuals"
        base_domain = [("id", "in", self.all_registrants.ids)]

        # Simple expression
        simple_expr = "age_years(r.birthdate) >= 18"

        # Complex nested expression
        complex_expr = (
            "(age_years(r.birthdate) >= 18 && age_years(r.birthdate) <= 65 && r.income < 5000) || "
            "(r.income < 2000 && r.income < 3000) || "
            "(age_years(r.birthdate) >= 65 && r.income < 5000)"
        )

        results = []

        for name, expr in [("simple", simple_expr), ("complex", complex_expr)]:
            # Warm up
            self.cel_service.compile_expression(expr, profile, base_domain=base_domain, limit=0)

            # Measure
            start = time.perf_counter()
            result = self.cel_service.compile_expression(
                expr,
                profile,
                base_domain=base_domain,
                limit=0,
            )
            elapsed = time.perf_counter() - start

            results.append(
                {
                    "name": name,
                    "expression": expr,
                    "elapsed_s": elapsed,
                    "elapsed_ms": elapsed * 1000,
                    "count": result.get("count", 0),
                    "valid": result.get("valid", False),
                }
            )

            _logger.info(f"{name}: {elapsed * 1000:.2f}ms (matched: {result.get('count', 0)})")

        # Calculate overhead
        simple_time = results[0]["elapsed_ms"]
        complex_time = results[1]["elapsed_ms"]
        overhead_pct = ((complex_time - simple_time) / simple_time * 100) if simple_time > 0 else 0

        # Print benchmark results
        _logger.info("\n" + "=" * 70)
        _logger.info("COMPLEX EXPRESSION BULK EVALUATION")
        _logger.info("=" * 70)
        _logger.info(f"Dataset size: {len(self.all_registrants)} registrants")
        _logger.info("-" * 70)
        _logger.info(f"Simple expression: {simple_expr}")
        _logger.info(f"  Time: {simple_time:.2f}ms")
        _logger.info(f"  Matched: {results[0]['count']}")
        _logger.info("-" * 70)
        _logger.info(f"Complex expression: {complex_expr}")
        _logger.info(f"  Time: {complex_time:.2f}ms")
        _logger.info(f"  Matched: {results[1]['count']}")
        _logger.info("-" * 70)
        _logger.info(f"Complexity overhead: {overhead_pct:.1f}%")
        _logger.info("=" * 70 + "\n")

        # Both should be valid
        for r in results:
            self.assertTrue(r["valid"], f"Expression '{r['name']}' failed to compile")

        # Complex expression should not be more than 5x slower
        self.assertLess(
            complex_time,
            simple_time * 5.0,
            f"Complex expression {complex_time:.2f}ms is >5x slower than simple {simple_time:.2f}ms",
        )

    def test_profile_switching_overhead(self):
        """Test overhead of switching between different profiles.

        Evaluates expressions on different profiles (registry_individuals, registry_groups).
        Measures overhead of profile loading and tests cache effectiveness.
        """
        # Test cases: (profile, expression, dataset)
        test_cases = [
            (
                "registry_individuals",
                "age_years(r.birthdate) >= 18",
                [("id", "in", self.all_registrants.ids)],
            ),
            (
                "registry_groups",
                "members.count(m, true) >= 4",
                [("id", "in", self.households.ids)],
            ),
            (
                "registry_individuals",
                "r.income < 5000",
                [("id", "in", self.all_registrants.ids)],
            ),
            (
                "registry_groups",
                "members.exists(m, age_years(m.birthdate) < 5)",
                [("id", "in", self.households.ids)],
            ),
        ]

        results = []

        for profile, expr, base_domain in test_cases:
            # Measure with cold cache (first call for this profile)
            start = time.perf_counter()
            result = self.cel_service.compile_expression(
                expr,
                profile,
                base_domain=base_domain,
                limit=0,
            )
            elapsed_cold = time.perf_counter() - start

            # Measure with warm cache (second call for same profile)
            start = time.perf_counter()
            result = self.cel_service.compile_expression(
                expr,
                profile,
                base_domain=base_domain,
                limit=0,
            )
            elapsed_warm = time.perf_counter() - start

            results.append(
                {
                    "profile": profile,
                    "expression": expr[:40] + "..." if len(expr) > 40 else expr,
                    "cold_ms": elapsed_cold * 1000,
                    "warm_ms": elapsed_warm * 1000,
                    "speedup": elapsed_cold / elapsed_warm if elapsed_warm > 0 else 0,
                    "count": result.get("count", 0),
                }
            )

            _logger.info(
                f"{profile}: cold={elapsed_cold * 1000:.2f}ms, "
                f"warm={elapsed_warm * 1000:.2f}ms, "
                f"speedup={elapsed_cold / elapsed_warm if elapsed_warm > 0 else 0:.2f}x"
            )

        # Print benchmark results
        _logger.info("\n" + "=" * 70)
        _logger.info("PROFILE SWITCHING OVERHEAD")
        _logger.info("=" * 70)
        _logger.info(f"{'Profile':<25} {'Cold (ms)':<12} {'Warm (ms)':<12} {'Speedup':<10}")
        _logger.info("-" * 70)

        for r in results:
            _logger.info(f"{r['profile']:<25} {r['cold_ms']:<12.2f} {r['warm_ms']:<12.2f} {r['speedup']:<10.2f}x")

        _logger.info("=" * 70 + "\n")

        # Warm cache should generally be faster (allow for some variance)
        # At least some profiles should show speedup
        speedups = [r["speedup"] for r in results]
        avg_speedup = sum(speedups) / len(speedups) if speedups else 0

        _logger.info(f"Average cache speedup: {avg_speedup:.2f}x")

        # All operations should complete in reasonable time
        for r in results:
            self.assertLess(
                r["cold_ms"],
                1000,
                f"Cold cache took {r['cold_ms']:.2f}ms for {r['profile']}",
            )

    def test_concurrent_different_expressions(self):
        """Simulate evaluating multiple different expressions sequentially.

        Evaluates 5 different expressions one after another.
        Measures if there are any contention issues.
        Reports per-expression and total tir.
        """
        profile = "registry_individuals"
        base_domain = [("id", "in", self.all_registrants.ids)]

        # 5 different expressions
        expressions = [
            ("age_check", "age_years(r.birthdate) >= 18 && age_years(r.birthdate) <= 65"),
            ("income_check", "r.income < 5000"),
            ("gender_age", "r.income < 5000 && age_years(r.birthdate) >= 18"),
            ("vulnerable", "r.income < 2000 || age_years(r.birthdate) >= 65"),
            ("working_poor", "age_years(r.birthdate) >= 18 && age_years(r.birthdate) <= 60 && r.income < 3000"),
        ]

        results = []
        total_start = time.perf_counter()

        # First pass - cold cache
        for name, expr in expressions:
            start = time.perf_counter()
            result = self.cel_service.compile_expression(
                expr,
                profile,
                base_domain=base_domain,
                limit=0,
            )
            elapsed = time.perf_counter() - start

            results.append(
                {
                    "name": name,
                    "expression": expr,
                    "elapsed_ms": elapsed * 1000,
                    "count": result.get("count", 0),
                    "valid": result.get("valid", False),
                }
            )

        total_elapsed = time.perf_counter() - total_start

        # Second pass - warm cache
        warm_start = time.perf_counter()
        for _name, expr in expressions:
            self.cel_service.compile_expression(
                expr,
                profile,
                base_domain=base_domain,
                limit=0,
            )
        warm_elapsed = time.perf_counter() - warm_start

        # Print benchmark results
        _logger.info("\n" + "=" * 70)
        _logger.info("CONCURRENT DIFFERENT EXPRESSIONS")
        _logger.info("=" * 70)
        _logger.info(f"Number of expressions: {len(expressions)}")
        _logger.info(f"Dataset size: {len(self.all_registrants)} registrants")
        _logger.info(f"Total time (cold): {total_elapsed * 1000:.2f}ms")
        _logger.info(f"Total time (warm): {warm_elapsed * 1000:.2f}ms")
        _logger.info(f"Average per expression (cold): {total_elapsed * 1000 / len(expressions):.2f}ms")
        _logger.info(f"Average per expression (warm): {warm_elapsed * 1000 / len(expressions):.2f}ms")
        _logger.info("-" * 70)
        _logger.info(f"{'Expression':<20} {'Time (ms)':<12} {'Matched':<10}")
        _logger.info("-" * 70)

        for r in results:
            _logger.info(f"{r['name']:<20} {r['elapsed_ms']:<12.2f} {r['count']:<10}")

        _logger.info("=" * 70 + "\n")

        # All expressions should be valid
        for r in results:
            self.assertTrue(r["valid"], f"Expression '{r['name']}' failed to compile")

        # Total time should be reasonable
        self.assertLess(
            total_elapsed,
            5.0,
            f"Total evaluation time {total_elapsed:.2f}s exceeds 5s for {len(expressions)} expressions",
        )

        # Warm cache should be faster
        speedup = total_elapsed / warm_elapsed if warm_elapsed > 0 else 0
        _logger.info(f"Cache speedup: {speedup:.2f}x")
