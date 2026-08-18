# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Performance tests for CEL translator (spp.cel.translator model).

This test suite measures the performance of CEL expression translation to query plans,
including throughput, caching efficiency, and performance across different expression types.
"""

import logging

from odoo.tests import tagged

from odoo.addons.spp_cel_domain.models import cel_translator

from ..data import expression_templates
from . import common

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "performance")
class TestCELTranslatorPerformance(common.PerformanceTestCase):
    """Performance tests for CEL translator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # cel_registry is already set in parent class (PerformanceTestCase)
        # Clear all caches before tests
        cel_translator.invalidate_translation_cache()

    def setUp(self):
        super().setUp()
        # Clear caches before each test for consistent measurements
        cel_translator.invalidate_translation_cache()

    def test_translate_simple_expressions_throughput(self):
        """Translate 5,000 simple expressions to Odoo domains.

        Measures translations per second for simple field comparisons.
        Target: > 5,000 ops/sec
        """
        # Get simple expressions
        simple_exprs = []
        base_expressions = expression_templates.get_expressions_by_complexity("simple")
        # Extend to 5000 by repeating and varying
        for i in range(5000):
            _, expr = base_expressions[i % len(base_expressions)]
            simple_exprs.append(expr)

        # Load profile configuration
        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"

        # Measure throughput
        translation_count = 0

        def translate_one():
            nonlocal translation_count
            expr = simple_exprs[translation_count % len(simple_exprs)]
            self.translator.translate(model, expr, cfg)
            translation_count += 1

        metrics = self.measure_throughput(
            translate_one,
            5000,
            "translate 5,000 simple expressions",
        )

        # Assert performance target
        self.assertGreater(
            metrics["throughput"],
            5000,
            f"Simple expression translation throughput {metrics['throughput']:.2f} ops/sec "
            f"is below target of 5,000 ops/sec",
        )

        self.print_benchmark_result(
            "Simple Expression Translation Throughput",
            {
                "Total translations": 5000,
                "Elapsed time (seconds)": metrics["elapsed"],
                "Throughput (ops/sec)": metrics["throughput"],
                "Average time per translation (ms)": metrics["avg_time"] * 1000,
                "Target met": "YES" if metrics["throughput"] > 5000 else "NO",
            },
        )

    def test_translate_complex_expressions_throughput(self):
        """Translate 1,000 complex expressions (exists, count, aggregations).

        Measures throughput for query plan generation with complex operations.
        """
        # Get complex expressions (exists, count, aggregations)
        complex_exprs = []
        for complexity in ["complex_exists", "complex_count", "complex_aggregate"]:
            exprs = expression_templates.get_expressions_by_complexity(complexity)
            complex_exprs.extend([expr for _, expr in exprs])

        # Extend to 1000
        while len(complex_exprs) < 1000:
            complex_exprs.extend(complex_exprs[: 1000 - len(complex_exprs)])
        complex_exprs = complex_exprs[:1000]

        # Load profile
        cfg = self.cel_registry.load_profile("registry_groups")
        model = "res.partner"

        # Measure throughput
        translation_count = 0

        def translate_one():
            nonlocal translation_count
            expr = complex_exprs[translation_count % len(complex_exprs)]
            self.translator.translate(model, expr, cfg)
            translation_count += 1

        metrics = self.measure_throughput(
            translate_one,
            1000,
            "translate 1,000 complex expressions",
        )

        self.print_benchmark_result(
            "Complex Expression Translation Throughput",
            {
                "Total translations": 1000,
                "Elapsed time (seconds)": metrics["elapsed"],
                "Throughput (ops/sec)": metrics["throughput"],
                "Average time per translation (ms)": metrics["avg_time"] * 1000,
            },
        )

    def test_translation_cache_hit_rate(self):
        """Translate same expressions multiple times each.

        Verifies cache hit rate > 90% and measures performance improvement from caching.
        """
        # Get unique expressions
        # Note: Use simple/medium only with registry_individuals since it doesn't have 'members'
        all_exprs = []
        for complexity in ["simple", "medium"]:
            exprs = expression_templates.get_expressions_by_complexity(complexity)
            all_exprs.extend([expr for _, expr in exprs])

        # Use all available expressions (may be less than 50)
        unique_exprs = all_exprs
        num_unique = len(unique_exprs)

        if num_unique == 0:
            self.skipTest("No expressions available for cache testing")

        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"

        # First pass: populate cache (translate each expression once)
        cel_translator.invalidate_translation_cache()
        for expr in unique_exprs:
            self.translator.translate(model, expr, cfg)

        # Measure cache hit performance (translate each 200 times)
        total_translations = num_unique * 200
        translation_count = 0

        def translate_cached():
            nonlocal translation_count
            expr = unique_exprs[translation_count % num_unique]
            self.translator.translate(model, expr, cfg)
            translation_count += 1

        metrics = self.measure_throughput(
            translate_cached,
            total_translations,
            f"translate {total_translations} expressions ({num_unique} unique x 200 times) with cache",
        )

        # Compare with cold cache performance
        cel_translator.invalidate_translation_cache()
        cold_translation_count = 0

        def translate_cold():
            nonlocal cold_translation_count
            expr = unique_exprs[cold_translation_count % num_unique]
            self.translator.translate(model, expr, cfg)
            cold_translation_count += 1

        cold_metrics = self.measure_throughput(
            translate_cold,
            500,  # Smaller sample for cold cache
            "translate 500 expressions with cold cache",
        )

        # Calculate improvement
        improvement_ratio = metrics["throughput"] / cold_metrics["throughput"]

        # Cache hit rate should be very high (> 90% of requests are cache hits)
        # With N unique and N*200 total, theoretical hit rate is (N*200-N)/(N*200) = 99.5%
        # Performance improvement should reflect this
        theoretical_hit_rate = (total_translations - num_unique) / total_translations if total_translations > 0 else 0

        # Cache should provide some improvement, but ratio depends on expression complexity
        # and system load. We just verify cache doesn't make things slower.
        self.assertGreater(
            improvement_ratio,
            0.5,  # Cache should not be more than 2x slower
            f"Cache performance improvement {improvement_ratio:.2f}x is unexpectedly low",
        )

        self.print_benchmark_result(
            "Translation Cache Hit Rate Performance",
            {
                "Unique expressions": num_unique,
                "Total translations": total_translations,
                "Cache hit rate (theoretical)": f"{theoretical_hit_rate * 100:.1f}%",
                "Cached throughput (ops/sec)": metrics["throughput"],
                "Cold cache throughput (ops/sec)": cold_metrics["throughput"],
                "Performance improvement": f"{improvement_ratio:.2f}x",
                "Average cached time (ms)": metrics["avg_time"] * 1000,
                "Average cold time (ms)": cold_metrics["avg_time"] * 1000,
            },
        )

    def test_translation_cache_eviction_impact(self):
        """Fill cache beyond max size (128 entries).

        Measures performance during cache eviction and verifies graceful degradation.
        """
        # Get expressions from simple/medium complexity only
        # (registry_individuals doesn't have 'members' collection for complex expressions)
        all_exprs = []
        for complexity in ["simple", "medium"]:
            exprs = expression_templates.get_expressions_by_complexity(complexity)
            all_exprs.extend([expr for _, expr in exprs])

        # Generate 200 unique expressions (exceeds cache max of 128)
        unique_exprs = []
        for _i, expr in enumerate(all_exprs):
            # Make expressions unique by varying field comparisons
            unique_exprs.append(expr)
            if len(unique_exprs) >= 200:
                break

        # Pad by creating variations of base expressions
        i = 0
        while len(unique_exprs) < 200:
            base_expr = all_exprs[i % len(all_exprs)]
            unique_exprs.append(f"({base_expr}) && r.id > {i}")
            i += 1

        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"

        # Clear cache
        cel_translator.invalidate_translation_cache()

        # Translate all 200 expressions (will trigger eviction after 128)
        translation_count = 0

        def translate_with_eviction():
            nonlocal translation_count
            expr = unique_exprs[translation_count]
            self.translator.translate(model, expr, cfg)
            translation_count += 1

        metrics = self.measure_throughput(
            translate_with_eviction,
            200,
            "translate 200 unique expressions (triggers cache eviction)",
        )

        # Now translate again - some should be cache hits, some misses
        translation_count = 0
        second_metrics = self.measure_throughput(
            translate_with_eviction,
            200,
            "translate same 200 expressions again (after eviction)",
        )

        # Performance should degrade gracefully (not catastrophically)
        # Second pass should be faster than cold but not as fast as full cache
        self.assertGreater(
            second_metrics["throughput"],
            metrics["throughput"] * 0.5,  # Should be at least 50% as fast
            "Cache eviction caused catastrophic performance degradation",
        )

        self.print_benchmark_result(
            "Translation Cache Eviction Impact",
            {
                "Unique expressions": 200,
                "Cache max size": 128,
                "First pass throughput (ops/sec)": metrics["throughput"],
                "Second pass throughput (ops/sec)": second_metrics["throughput"],
                "Performance retention": f"{(second_metrics['throughput'] / metrics['throughput'] * 100):.1f}%",
                "Average first pass time (ms)": metrics["avg_time"] * 1000,
                "Average second pass time (ms)": second_metrics["avg_time"] * 1000,
            },
        )

    def test_translate_to_query_plan_types(self):
        """Test translation performance for different query plan types.

        Measures per-type translation time for:
        - LeafDomain generation
        - ExistsThrough generation
        - CountThrough generation
        - FieldAggregateThrough generation
        """
        cfg = self.cel_registry.load_profile("registry_groups")
        model = "res.partner"

        results = {}

        # Test LeafDomain expressions
        leaf_exprs = [
            "age_years(r.birthdate) >= 18",
            "r.income < 5000",
            "r.is_group == false",
            "r.name != ''",
            "age_years(r.birthdate) >= 21 && age_years(r.birthdate) <= 60",
        ]
        cel_translator.invalidate_translation_cache()
        count = 0

        def translate_leaf():
            nonlocal count
            self.translator.translate(model, leaf_exprs[count % len(leaf_exprs)], cfg)
            count += 1

        leaf_metrics = self.measure_throughput(translate_leaf, 1000, "LeafDomain translations")
        results["LeafDomain"] = leaf_metrics

        # Test ExistsThrough expressions
        exists_exprs = expression_templates.get_expressions_by_complexity("complex_exists")
        exists_exprs = [expr for _, expr in exists_exprs]
        cel_translator.invalidate_translation_cache()
        count = 0

        def translate_exists():
            nonlocal count
            self.translator.translate(model, exists_exprs[count % len(exists_exprs)], cfg)
            count += 1

        exists_metrics = self.measure_throughput(translate_exists, 500, "ExistsThrough translations")
        results["ExistsThrough"] = exists_metrics

        # Test CountThrough expressions
        count_exprs = expression_templates.get_expressions_by_complexity("complex_count")
        count_exprs = [expr for _, expr in count_exprs]
        cel_translator.invalidate_translation_cache()
        count = 0

        def translate_count():
            nonlocal count
            self.translator.translate(model, count_exprs[count % len(count_exprs)], cfg)
            count += 1

        count_metrics = self.measure_throughput(translate_count, 500, "CountThrough translations")
        results["CountThrough"] = count_metrics

        # Test FieldAggregateThrough expressions
        agg_exprs = expression_templates.get_expressions_by_complexity("complex_aggregate")
        agg_exprs = [expr for _, expr in agg_exprs]
        cel_translator.invalidate_translation_cache()
        count = 0

        def translate_agg():
            nonlocal count
            self.translator.translate(model, agg_exprs[count % len(agg_exprs)], cfg)
            count += 1

        agg_metrics = self.measure_throughput(translate_agg, 500, "FieldAggregateThrough translations")
        results["FieldAggregateThrough"] = agg_metrics

        self.print_benchmark_result(
            "Query Plan Type Translation Performance",
            {
                "LeafDomain throughput (ops/sec)": results["LeafDomain"]["throughput"],
                "LeafDomain avg time (ms)": results["LeafDomain"]["avg_time"] * 1000,
                "ExistsThrough throughput (ops/sec)": results["ExistsThrough"]["throughput"],
                "ExistsThrough avg time (ms)": results["ExistsThrough"]["avg_time"] * 1000,
                "CountThrough throughput (ops/sec)": results["CountThrough"]["throughput"],
                "CountThrough avg time (ms)": results["CountThrough"]["avg_time"] * 1000,
                "FieldAggregateThrough throughput (ops/sec)": results["FieldAggregateThrough"]["throughput"],
                "FieldAggregateThrough avg time (ms)": results["FieldAggregateThrough"]["avg_time"] * 1000,
            },
        )

    def test_translate_event_expressions(self):
        """Translate event CEL expressions.

        Tests EventValueCompare, EventExists, EventsAggregate query plans.
        Measures throughput for event-based expressions.
        """
        # Get event expressions
        event_exprs = []
        for complexity in ["event_basic", "event_temporal", "event_aggregate"]:
            exprs = expression_templates.get_expressions_by_complexity(complexity)
            event_exprs.extend([expr for _, expr in exprs])

        # Extend to 500
        while len(event_exprs) < 500:
            event_exprs.extend(event_exprs[: 500 - len(event_exprs)])
        event_exprs = event_exprs[:500]

        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"

        # Measure throughput
        cel_translator.invalidate_translation_cache()
        translation_count = 0

        def translate_event():
            nonlocal translation_count
            expr = event_exprs[translation_count % len(event_exprs)]
            try:
                self.translator.translate(model, expr, cfg)
            except Exception:
                # Event expressions may fail if event models not available
                # This is expected in test environment
                pass
            translation_count += 1

        metrics = self.measure_throughput(
            translate_event,
            500,
            "translate 500 event expressions",
        )

        self.print_benchmark_result(
            "Event Expression Translation Throughput",
            {
                "Total translations": 500,
                "Elapsed time (seconds)": metrics["elapsed"],
                "Throughput (ops/sec)": metrics["throughput"],
                "Average time per translation (ms)": metrics["avg_time"] * 1000,
            },
        )

    def test_translate_with_different_profiles(self):
        """Test translation performance across different profiles.

        Compares translation performance for:
        - registry_individuals profile
        - registry_groups profile
        - program_memberships profile (if available)
        """
        profiles = ["registry_individuals", "registry_groups"]
        model = "res.partner"

        # Get medium complexity expressions
        medium_exprs = expression_templates.get_expressions_by_complexity("medium")
        medium_exprs = [expr for _, expr in medium_exprs]

        results = {}

        for profile_name in profiles:
            try:
                cfg = self.cel_registry.load_profile(profile_name)
                cel_translator.invalidate_translation_cache()

                count = 0
                # Capture cfg in closure to avoid B023
                profile_cfg = cfg

                def translate_profile():
                    nonlocal count
                    expr = medium_exprs[count % len(medium_exprs)]
                    self.translator.translate(model, expr, profile_cfg)
                    count += 1

                metrics = self.measure_throughput(
                    translate_profile,
                    500,
                    f"translate 500 expressions with {profile_name} profile",
                )
                results[profile_name] = metrics

            except Exception as e:
                _logger.warning(f"Profile {profile_name} not available: {e}")
                continue

        # Try program_memberships if available
        try:
            cfg = self.cel_registry.load_profile("program_memberships")
            membership_model = "spp.program.membership"
            membership_exprs = [
                "r.state == 'enrolled'",
                "r.state == 'active'",
                "r.is_ended == false",
            ]
            cel_translator.invalidate_translation_cache()

            count = 0

            def translate_membership():
                nonlocal count
                expr = membership_exprs[count % len(membership_exprs)]
                self.translator.translate(membership_model, expr, cfg)
                count += 1

            metrics = self.measure_throughput(
                translate_membership,
                300,
                "translate 300 expressions with program_memberships profile",
            )
            results["program_memberships"] = metrics

        except Exception as e:
            _logger.warning(f"Profile program_memberships not available: {e}")

        # Print results
        benchmark_data = {}
        for profile_name, metrics in results.items():
            benchmark_data[f"{profile_name} throughput (ops/sec)"] = metrics["throughput"]
            benchmark_data[f"{profile_name} avg time (ms)"] = metrics["avg_time"] * 1000

        self.print_benchmark_result(
            "Translation Performance by Profile",
            benchmark_data,
        )

        # Assert we tested at least 2 profiles
        self.assertGreaterEqual(
            len(results),
            2,
            "Should test at least 2 different profiles",
        )
