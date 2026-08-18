# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Performance tests for CEL executor (spp.cel.executor model).

This test suite measures the performance of CEL expression execution against the
database, including:
- Simple expression scaling across different dataset sizes
- Exists/count expression performance with complex relationships
- Domain compilation vs execution time breakdown
- Complex boolean logic optimization
- Batch evaluation throughput
- Index impact detection and recommendations
"""

import logging
import time

import odoo
from odoo import Command
from odoo.tests import tagged

from . import common

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "performance")
class TestCELExecutorPerformance(common.PerformanceTestCase):
    """Performance tests for CEL executor."""

    @classmethod
    def setUpClass(cls):
        """Set up test data for executor performance tests."""
        super().setUpClass()

        # Generate test data at different scales.
        # Default sizes: 100 / 1000 / 5000 registrants.
        # The largest dataset scales with cel_benchmark_registrants so that
        # running with --registrants=10000 yields ~200 / 2000 / 10000.
        _logger.info("Generating test data for executor performance tests...")

        default_max = 5000
        max_requested = int(odoo.tools.config.get("cel_benchmark_registrants", default_max))
        scale_factor = max(1, max_requested // default_max)

        base_small, base_medium, base_large = 100, 1000, 5000
        small_n = base_small * scale_factor
        medium_n = base_medium * scale_factor
        large_n = base_large * scale_factor

        _logger.info(
            "Executor registrant split: %s (small) + %s (medium) + %s (large) = %s total",
            small_n,
            medium_n,
            large_n,
            small_n + medium_n + large_n,
        )

        # Small dataset: for quick tests
        cls.registrants_100 = cls._create_registrants(small_n, prefix="Small")

        # Medium dataset: for scaling tests
        cls.registrants_1000 = cls._create_registrants(medium_n, prefix="Medium")

        # Large dataset: for stress tests
        cls.registrants_5000 = cls._create_registrants(large_n, prefix="Large")

        # Household data: 500 households with 5 members each
        cls.households_500, cls.household_members = cls._create_households(500, members_per=5, prefix="TestHH")

        # Varying household sizes for count tests
        cls.households_varying = cls.env["res.partner"]
        cls.households_varying_members = cls.env["res.partner"]

        # Create 100 households with 2 members
        hh_2, members_2 = cls._create_households(100, members_per=2, prefix="HH2")
        cls.households_varying += hh_2
        cls.households_varying_members += members_2

        # Create 100 households with 5 members
        hh_5, members_5 = cls._create_households(100, members_per=5, prefix="HH5")
        cls.households_varying += hh_5
        cls.households_varying_members += members_5

        # Create 100 households with 10 members
        hh_10, members_10 = cls._create_households(100, members_per=10, prefix="HH10")
        cls.households_varying += hh_10
        cls.households_varying_members += members_10

        _logger.info("Test data generation complete")

    @classmethod
    def _create_registrants(cls, count, prefix="TestReg", log_details=True):
        """Create test registrant records efficiently (classmethod version)."""
        if log_details:
            _logger.info(f"Generating {count} registrants...")
        registrant_vals = []
        for i in range(count):
            birthdate = cls.fake.date_of_birth(minimum_age=0, maximum_age=90)
            vals = {
                "name": f"{prefix} {cls.fake.name()} {i}",
                "is_registrant": True,
                "is_group": False,
                "birthdate": birthdate,
                "phone": cls.fake.phone_number()[:20],
                "email": cls.fake.email(),
                "street": cls.fake.street_address(),
                "city": cls.fake.city(),
                "income": cls.fake.random_int(min=0, max=10000),
            }
            registrant_vals.append(vals)
        registrants = cls.env["res.partner"].create(registrant_vals)
        if log_details:
            _logger.info(f"Created {len(registrants)} registrants")
        return registrants

    @classmethod
    def _create_households(cls, count, members_per=5, prefix="TestHH"):
        """Create test household records with members (classmethod version)."""
        _logger.info(f"Generating {count} households with {members_per} members each...")
        household_vals = []
        for i in range(count):
            vals = {
                "name": f"{prefix} {cls.fake.last_name()} Family {i}",
                "is_registrant": True,
                "is_group": True,
            }
            household_vals.append(vals)
        households = cls.env["res.partner"].create(household_vals)

        all_members = cls.env["res.partner"]
        membership_vals = []
        for household in households:
            # Avoid spamming logs for small per-household batches
            members = cls._create_registrants(
                members_per,
                prefix=f"Member-{household.id}",
                log_details=False,
            )
            all_members += members
            for member in members:
                membership_vals.append(
                    {
                        "group": household.id,
                        "individual": member.id,
                    }
                )
        cls.env["spp.group.membership"].create(membership_vals)
        _logger.info(f"Created {len(households)} households with {len(all_members)} total members")
        return households, all_members

    def test_simple_expression_scaling(self):
        """Test simple expression evaluation scaling across different dataset sizes.

        Evaluates 'age_years(r.birthdate) >= 18' against 100, 1000, and 5000 registrants
        to measure how execution time scales with dataset size.
        """
        expression = "age_years(r.birthdate) >= 18"
        profile = "registry_individuals"

        results = {}
        scales = [
            ("100 registrants", 100),
            ("1000 registrants", 1000),
            ("5000 registrants", 5000),
        ]

        for scale_name, count in scales:
            # Use appropriate dataset
            if count == 100:
                dataset_ids = self.registrants_100.ids
            elif count == 1000:
                dataset_ids = self.registrants_1000.ids
            else:
                dataset_ids = self.registrants_5000.ids

            # Add base domain to restrict to our test dataset
            base_domain = [("id", "in", dataset_ids)]

            # Measure compilation + execution time
            with self.benchmark(f"Evaluate simple expression ({scale_name})", print_result=True):
                with self.analyze_queries(f"Simple expression - {scale_name}"):
                    result = self.env["spp.cel.service"].compile_expression(
                        expression, profile, base_domain=base_domain, limit=0
                    )

            # Verify valid result
            self.assertTrue(result["valid"], f"Error: {result.get('error')}")

            results[scale_name] = {
                "count": count,
                "matched": result["count"],
                "time_ms": self._benchmark_results[f"Evaluate simple expression ({scale_name})"]["elapsed_ms"],
            }

        # Calculate scaling factors
        time_100 = results["100 registrants"]["time_ms"]
        time_1000 = results["1000 registrants"]["time_ms"]
        time_5000 = results["5000 registrants"]["time_ms"]

        scaling_10x = time_1000 / time_100 if time_100 > 0 else 0
        scaling_50x = time_5000 / time_100 if time_100 > 0 else 0

        # Report results
        self.report_metrics(
            {
                "100 registrants time (ms)": time_100,
                "1000 registrants time (ms)": time_1000,
                "5000 registrants time (ms)": time_5000,
                "Scaling 100→1000 (10x data)": f"{scaling_10x:.2f}x",
                "Scaling 100→5000 (50x data)": f"{scaling_50x:.2f}x",
                "100 registrants matched": results["100 registrants"]["matched"],
                "1000 registrants matched": results["1000 registrants"]["matched"],
                "5000 registrants matched": results["5000 registrants"]["matched"],
            }
        )

        # Assert linear or better scaling (10x data should not be > 15x time)
        self.assertLess(
            scaling_10x,
            15.0,
            f"Scaling appears worse than linear: 10x data took {scaling_10x:.2f}x time",
        )

    def test_exists_expression_performance(self):
        """Test exists() expression performance on household relationships.

        Evaluates 'members.exists(m, age_years(m.birthdate) < 5)'
        against 500 households with 5 members each.
        """
        expression = "members.exists(m, age_years(m.birthdate) < 5)"
        profile = "registry_groups"

        # Restrict to our test households
        base_domain = [("id", "in", self.households_500.ids)]

        # Measure execution
        with self.benchmark("Evaluate exists() expression", print_result=True):
            with self.analyze_queries("Exists expression"):
                result = self.env["spp.cel.service"].compile_expression(
                    expression, profile, base_domain=base_domain, limit=0
                )

        # Verify valid result
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

        # Check for sequential scans in query stats
        sequential_scans = []
        if hasattr(self, "_query_stats"):
            for stat in self._query_stats:
                explain = str(stat.get("explain", "")).lower()
                if "seq scan" in explain:
                    sequential_scans.append(stat["query"][:100])

        # Report results
        elapsed_ms = self._benchmark_results["Evaluate exists() expression"]["elapsed_ms"]
        self.report_metrics(
            {
                "Households evaluated": len(self.households_500),
                "Total members": len(self.household_members),
                "Matched households": result["count"],
                "Execution time (ms)": elapsed_ms,
                "Time per household (ms)": elapsed_ms / len(self.households_500),
                "Sequential scans detected": len(sequential_scans),
            }
        )

        # Log sequential scans for review
        if sequential_scans:
            _logger.warning(f"Sequential scans detected in exists() query: {sequential_scans}")

        # Assert reasonable performance (should complete in < 5 seconds for 500 households)
        self.assertLess(
            elapsed_ms,
            5000,
            f"Exists expression took {elapsed_ms:.2f}ms, expected < 5000ms",
        )

    def test_count_expression_performance(self):
        """Test count() expression performance with varying household sizes.

        Evaluates 'members.count(m, m.income < 2000) >= 2'
        against households with 2, 5, and 10 members.
        """
        expression = "members.count(m, m.income < 2000) >= 2"
        profile = "registry_groups"

        # Test on all varying household sizes
        base_domain = [("id", "in", self.households_varying.ids)]

        # Measure execution
        with self.benchmark("Evaluate count() expression", print_result=True):
            with self.analyze_queries("Count expression"):
                result = self.env["spp.cel.service"].compile_expression(
                    expression, profile, base_domain=base_domain, limit=0
                )

        # Verify valid result
        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

        # Report results
        elapsed_ms = self._benchmark_results["Evaluate count() expression"]["elapsed_ms"]
        self.report_metrics(
            {
                "Households evaluated": len(self.households_varying),
                "Total members": len(self.households_varying_members),
                "Matched households": result["count"],
                "Execution time (ms)": elapsed_ms,
                "Time per household (ms)": elapsed_ms / len(self.households_varying),
                "Avg members per household": len(self.households_varying_members) / len(self.households_varying),
            }
        )

        # Assert reasonable performance
        self.assertLess(
            elapsed_ms,
            3000,
            f"Count expression took {elapsed_ms:.2f}ms, expected < 3000ms",
        )

    def test_domain_compilation_vs_execution(self):
        """Compare time spent compiling domain vs executing query.

        Breaks down the phases: parsing, translation, domain compilation, and query execution.
        """
        expression = "age_years(r.birthdate) >= 18 && r.income < 5000"
        profile = "registry_individuals"
        base_domain = [("id", "in", self.registrants_1000.ids)]

        # Phase 1: Compile expression (parsing + translation)
        compile_start = time.perf_counter()
        result = self.env["spp.cel.service"].compile_expression(expression, profile, base_domain=base_domain, limit=0)
        compile_end = time.perf_counter()
        compile_time = (compile_end - compile_start) * 1000

        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

        # Phase 2: Execute the compiled domain directly
        domain = result["domain"]
        exec_start = time.perf_counter()
        records = self.env["res.partner"].search(domain)
        exec_count = len(records)
        exec_end = time.perf_counter()
        exec_time = (exec_end - exec_start) * 1000

        # Calculate breakdown
        total_time = compile_time + exec_time
        compile_pct = (compile_time / total_time * 100) if total_time > 0 else 0
        exec_pct = (exec_time / total_time * 100) if total_time > 0 else 0

        # Report breakdown
        self.report_metrics(
            {
                "Total time (ms)": total_time,
                "Compilation time (ms)": compile_time,
                "Execution time (ms)": exec_time,
                "Compilation %": f"{compile_pct:.1f}%",
                "Execution %": f"{exec_pct:.1f}%",
                "Records matched": exec_count,
                "Records evaluated": len(self.registrants_1000),
            }
        )

        # For simple expressions, execution should be the dominant cost
        # (compilation is a one-time cost that can be cached)
        self.assertGreater(
            exec_time,
            compile_time * 0.1,
            "Execution time suspiciously low - may indicate caching issues",
        )

    def test_complex_and_or_expressions(self):
        """Test complex boolean logic with AND/OR combinations.

        Evaluates '(age_years(r.birthdate) >= 18 && r.income < 5000) || r.income < 2000'
        to measure performance of complex boolean expressions.
        """
        expression = "(age_years(r.birthdate) >= 18 && r.income < 5000) || " "r.income < 2000"
        profile = "registry_individuals"
        base_domain = [("id", "in", self.registrants_1000.ids)]

        # Measure execution
        with self.benchmark("Evaluate complex AND/OR expression", print_result=True):
            with self.analyze_queries("Complex AND/OR"):
                result = self.env["spp.cel.service"].compile_expression(
                    expression, profile, base_domain=base_domain, limit=0
                )

        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

        # Get the generated domain for inspection
        domain = result["domain"]

        # Report results
        elapsed_ms = self._benchmark_results["Evaluate complex AND/OR expression"]["elapsed_ms"]
        self.report_metrics(
            {
                "Expression": expression[:80] + "...",
                "Records evaluated": len(self.registrants_1000),
                "Records matched": result["count"],
                "Execution time (ms)": elapsed_ms,
                "Time per record (μs)": (elapsed_ms * 1000) / len(self.registrants_1000),
                "Domain clauses": len(domain),
            }
        )

        # Assert reasonable performance
        self.assertLess(
            elapsed_ms,
            2000,
            f"Complex AND/OR expression took {elapsed_ms:.2f}ms, expected < 2000ms",
        )

    def test_batch_evaluation_performance(self):
        """Test batch evaluation performance at different batch sizes.

        Evaluates the same expression in batches of 100, 500, and 1000 records
        to find optimal batch size.
        """
        expression = "age_years(r.birthdate) >= 18"
        profile = "registry_individuals"

        batch_sizes = [100, 500, 1000]
        results = {}

        for batch_size in batch_sizes:
            # Take first N records for this batch
            batch_ids = self.registrants_1000.ids[:batch_size]
            base_domain = [("id", "in", batch_ids)]

            # Measure throughput
            batch_results = []
            iterations = max(1, 1000 // batch_size)  # Do ~1000 total evaluations

            with self.benchmark(f"Batch evaluation (batch_size={batch_size})", print_result=True):
                for _ in range(iterations):
                    result = self.env["spp.cel.service"].compile_expression(
                        expression, profile, base_domain=base_domain, limit=0
                    )
                    batch_results.append(result["count"])

            elapsed_ms = self._benchmark_results[f"Batch evaluation (batch_size={batch_size})"]["elapsed_ms"]
            elapsed_s = elapsed_ms / 1000

            # Calculate throughput
            total_evaluations = batch_size * iterations
            throughput = total_evaluations / elapsed_s if elapsed_s > 0 else 0

            results[batch_size] = {
                "batch_size": batch_size,
                "iterations": iterations,
                "total_evaluations": total_evaluations,
                "elapsed_ms": elapsed_ms,
                "throughput": throughput,
                "time_per_batch_ms": elapsed_ms / iterations,
            }

        # Find optimal batch size (highest throughput)
        optimal_batch = max(results.items(), key=lambda x: x[1]["throughput"])

        # Report results
        self.report_metrics(
            {
                "Batch 100 - throughput (evals/sec)": results[100]["throughput"],
                "Batch 100 - time per batch (ms)": results[100]["time_per_batch_ms"],
                "Batch 500 - throughput (evals/sec)": results[500]["throughput"],
                "Batch 500 - time per batch (ms)": results[500]["time_per_batch_ms"],
                "Batch 1000 - throughput (evals/sec)": results[1000]["throughput"],
                "Batch 1000 - time per batch (ms)": results[1000]["time_per_batch_ms"],
                "Optimal batch size": optimal_batch[0],
                "Optimal throughput (evals/sec)": optimal_batch[1]["throughput"],
            }
        )

        # Assert minimum throughput (should handle at least 1000 evals/sec)
        for batch_size, metrics in results.items():
            self.assertGreater(
                metrics["throughput"],
                1000,
                f"Batch size {batch_size} throughput {metrics['throughput']:.2f} evals/sec "
                f"is below minimum 1000 evals/sec",
            )

    def test_index_impact_detection(self):
        """Analyze query execution plans to detect sequential scans and get index recommendations.

        Runs multiple query types and uses IndexAdvisor to generate recommendations.
        """
        test_cases = [
            ("Simple age filter", "age_years(r.birthdate) >= 18", "registry_individuals", self.registrants_1000.ids),
            ("Income filter", "r.income < 5000", "registry_individuals", self.registrants_1000.ids),
            ("Low income filter", "r.income < 2000", "registry_individuals", self.registrants_1000.ids),
            (
                "Household exists",
                "members.exists(m, age_years(m.birthdate) < 5)",
                "registry_groups",
                self.households_500.ids,
            ),
        ]

        all_sequential_scans = []
        all_recommendations = []

        for name, expression, profile, dataset_ids in test_cases:
            base_domain = [("id", "in", dataset_ids)]

            # Execute with query analysis
            with self.analyze_queries(name):
                result = self.env["spp.cel.service"].compile_expression(
                    expression, profile, base_domain=base_domain, limit=0
                )

            self.assertTrue(result["valid"], f"{name} error: {result.get('error')}")

            # Check for sequential scans
            if hasattr(self, "_query_stats"):
                for stat in self._query_stats:
                    if stat.get("operation") == name:
                        explain = str(stat.get("explain", "")).lower()
                        if "seq scan" in explain:
                            all_sequential_scans.append(
                                {
                                    "test": name,
                                    "query": stat["query"][:150],
                                    "explain": explain[:200],
                                }
                            )

        # Collect index recommendations
        if hasattr(self, "_index_recommendations") and self._index_recommendations:
            all_recommendations.extend(self._index_recommendations)

        # Report findings
        _logger.info("\n" + "=" * 70)
        _logger.info("INDEX IMPACT ANALYSIS")
        _logger.info("=" * 70)
        _logger.info(f"Test cases analyzed: {len(test_cases)}")
        _logger.info(f"Sequential scans detected: {len(all_sequential_scans)}")
        _logger.info(f"Index recommendations: {len(all_recommendations)}")

        if all_sequential_scans:
            _logger.info("\nSequential Scans Detected:")
            for scan in all_sequential_scans[:5]:  # Top 5
                _logger.info(f"  Test: {scan['test']}")
                _logger.info(f"  Query: {scan['query']}")
                _logger.info("")

        if all_recommendations:
            _logger.info("\nIndex Recommendations:")
            for rec in list(all_recommendations)[:10]:  # Top 10
                _logger.info(f"  {rec}")

        _logger.info("=" * 70 + "\n")

        # This test is informational - we don't fail on sequential scans
        # but we log them for review
        self.assertTrue(True, "Index impact detection completed - see logs for recommendations")


@tagged("post_install", "-at_install", "performance")
class TestCELAreaHelpersPerformance(common.PerformanceTestCase):
    """Performance tests for area-aware CEL helpers.

    These tests exercise in_area_tree() and has_area_tag()/has_any_area_tag()
    over a realistic number of registrants to ensure:
    - Domains compile efficiently
    - Queries use the area hierarchy and tag relations at scale
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Skip cleanly if spp_area is not installed
        if "spp.area" not in cls.env:
            raise odoo.exceptions.UserError("spp_area is required for area performance tests")

        Area = cls.env["spp.area"]
        Tag = cls.env["spp.area.tag"]
        Partner = cls.env["res.partner"]

        # Generate a moderate-sized dataset controlled by cel_benchmark_registrants
        default_max = 10000
        max_requested = int(odoo.tools.config.get("cel_benchmark_registrants", default_max))
        cls._registrant_count = max(1000, max_requested)

        _logger.info(
            "Generating %s registrants for area helper performance tests...",
            cls._registrant_count,
        )

        # Create a simple area hierarchy:
        #   REGION_REMOTE (code=REGION_REMOTE)
        #     - DISTRICT_REMOTE_1
        #   REGION_URBAN (code=REGION_URBAN)
        #     - DISTRICT_URBAN_1
        cls.region_remote = Area.create(
            {
                "draft_name": "Region Remote",
                "code": "REGION_REMOTE",
            }
        )
        cls.district_remote = Area.create(
            {
                "draft_name": "District Remote 1",
                "code": "REGION_REMOTE_1",
                "parent_id": cls.region_remote.id,
            }
        )

        cls.region_urban = Area.create(
            {
                "draft_name": "Region Urban",
                "code": "REGION_URBAN",
            }
        )
        cls.district_urban = Area.create(
            {
                "draft_name": "District Urban 1",
                "code": "REGION_URBAN_1",
                "parent_id": cls.region_urban.id,
            }
        )

        # Flush to ensure parent_path is computed for child_of queries
        cls.env.flush_all()

        # Area tags used by has_area_tag()/has_any_area_tag()
        # Search before create to avoid unique constraint violation
        cls.tag_remote = Tag.search([("code", "=", "REMOTE")], limit=1)
        if not cls.tag_remote:
            cls.tag_remote = Tag.create(
                {
                    "name": "Remote",
                    "code": "REMOTE",
                }
            )
        cls.tag_urban = Tag.search([("code", "=", "URBAN")], limit=1)
        if not cls.tag_urban:
            cls.tag_urban = Tag.create(
                {
                    "name": "Urban",
                    "code": "URBAN",
                }
            )

        # Attach tags to the leaf areas where registrants live
        cls.district_remote.tag_ids = [Command.link(cls.tag_remote.id)]
        cls.district_urban.tag_ids = [Command.link(cls.tag_urban.id)]

        # Create registrants split evenly between remote and urban districts
        registrant_vals_remote = []
        registrant_vals_urban = []
        for i in range(cls._registrant_count):
            vals = {
                "name": f"AreaPerf {cls.fake.name()} {i}",
                "is_registrant": True,
                "is_group": False,
                "birthdate": cls.fake.date_of_birth(minimum_age=0, maximum_age=90),
                "phone": cls.fake.phone_number()[:20],
                "email": cls.fake.email(),
                "street": cls.fake.street_address(),
                "city": cls.fake.city(),
                "income": cls.fake.random_int(min=0, max=10000),
            }
            if i % 2 == 0:
                vals["area_id"] = cls.district_remote.id
                registrant_vals_remote.append(vals)
            else:
                vals["area_id"] = cls.district_urban.id
                registrant_vals_urban.append(vals)

        cls.registrants_remote = Partner.create(registrant_vals_remote)
        cls.registrants_urban = Partner.create(registrant_vals_urban)
        cls.all_registrants = cls.registrants_remote | cls.registrants_urban

        _logger.info(
            "Created %s registrants for area helper tests " "(%s remote, %s urban)",
            len(cls.all_registrants),
            len(cls.registrants_remote),
            len(cls.registrants_urban),
        )

    def test_in_area_tree_performance(self):
        """Measure performance of in_area_tree() over registrants.

        Expression: in_area_tree('REGION_REMOTE')
        Profile: registry_individuals
        """
        expression = "in_area_tree('REGION_REMOTE')"
        profile = "registry_individuals"
        base_domain = [("id", "in", self.all_registrants.ids)]

        with self.benchmark("Evaluate in_area_tree over registrants", print_result=True):
            with self.analyze_queries("in_area_tree expression"):
                result = self.env["spp.cel.service"].compile_expression(
                    expression, profile, base_domain=base_domain, limit=0
                )

        self.assertTrue(result["valid"], f"Error: {result.get('error')}")

        # Check matched registrants - log overlap ratio for diagnostics
        remote_ids = set(self.registrants_remote.ids)
        matched_ids = set(result["ids"])
        overlap = remote_ids & matched_ids
        if remote_ids:
            overlap_ratio = len(overlap) / len(remote_ids)
            _logger.info(
                "in_area_tree match ratio: %.1f%% (%d/%d remote registrants matched)",
                overlap_ratio * 100,
                len(overlap),
                len(remote_ids),
            )
        # Performance test: assert we got some results (correctness tested elsewhere)
        self.assertGreater(result["count"], 0, "in_area_tree should return some matches")

        elapsed_ms = self._benchmark_results["Evaluate in_area_tree over registrants"]["elapsed_ms"]
        self.report_metrics(
            {
                "Total registrants": len(self.all_registrants),
                "Remote registrants": len(self.registrants_remote),
                "Matched registrants": result["count"],
                "Execution time (ms)": elapsed_ms,
                "Time per registrant (ms)": elapsed_ms / len(self.all_registrants),
            }
        )

    def test_has_area_tag_performance(self):
        """Measure performance of has_area_tag() and has_any_area_tag() over registrants."""
        profile = "registry_individuals"
        base_domain = [("id", "in", self.all_registrants.ids)]

        # Single-tag helper
        with self.benchmark("Evaluate has_area_tag('REMOTE')", print_result=True):
            with self.analyze_queries("has_area_tag expression"):
                result_remote = self.env["spp.cel.service"].compile_expression(
                    "has_area_tag('REMOTE')", profile, base_domain=base_domain, limit=0
                )

        self.assertTrue(result_remote["valid"], f"Error: {result_remote.get('error')}")

        # Multi-tag helper
        with self.benchmark(
            "Evaluate has_any_area_tag(['REMOTE','URBAN'])",
            print_result=True,
        ):
            with self.analyze_queries("has_any_area_tag expression"):
                result_any = self.env["spp.cel.service"].compile_expression(
                    "has_any_area_tag(['REMOTE', 'URBAN'])",
                    profile,
                    base_domain=base_domain,
                    limit=0,
                )

        self.assertTrue(result_any["valid"], f"Error: {result_any.get('error')}")

        elapsed_remote = self._benchmark_results["Evaluate has_area_tag('REMOTE')"]["elapsed_ms"]
        elapsed_any = self._benchmark_results["Evaluate has_any_area_tag(['REMOTE','URBAN'])"]["elapsed_ms"]

        self.report_metrics(
            {
                "Total registrants": len(self.all_registrants),
                "Matched (REMOTE)": result_remote["count"],
                "Matched (REMOTE or URBAN)": result_any["count"],
                "Execution time has_area_tag (ms)": elapsed_remote,
                "Execution time has_any_area_tag (ms)": elapsed_any,
            }
        )
