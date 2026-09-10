# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Performance tests for CEL Event Data Integration.

Tests the performance of CEL expressions that query event data:
- event() function with various selection modes
- has_event() existence checks
- events_count() aggregation
- events_sum/avg/min/max functions
- Temporal filters (within_days, within_months, period)
- SQL vs Python execution paths
- Index usage and optimization
"""

import logging
from datetime import date, timedelta

import odoo
from odoo.tests import tagged

from .common import PerformanceTestCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "performance")
class TestEventDataPerformance(PerformanceTestCase):
    """Performance tests for CEL event data expressions."""

    @classmethod
    def setUpClass(cls):
        """Initialize test data: registrants + events for performance tests.

        The number of registrants is driven by the ``cel_benchmark_registrants``
        configuration key (default 1000).
        """
        super().setUpClass()

        # Check if required modules are installed
        if "spp.event.data" not in cls.env:
            cls._module_installed = False
            _logger.warning("spp_event_data module not installed - event data performance tests will be skipped")
            return

        if "spp.cel.translator" not in cls.env:
            cls._module_installed = False
            _logger.warning("spp_cel_domain module not installed - event data performance tests will be skipped")
            return

        cls._module_installed = True

        # Create event type for testing
        cls.survey_type = cls.env["spp.event.type"].create(
            {
                "name": "Household Survey",
                "code": "household_survey",
                "category": "survey",
                "is_one_active_per_registrant": True,
            }
        )

        cls.visit_type = cls.env["spp.event.type"].create(
            {
                "name": "Field Visit",
                "code": "field_visit",
                "category": "visit",
                "is_one_active_per_registrant": False,
            }
        )

        # Generate registrants (scales with cel_benchmark_registrants)
        _logger.info("Generating test registrants for event data performance tests...")

        # Inline data generation for setUpClass (instance method not available)
        default_count = 1000
        count = int(odoo.tools.config.get("cel_benchmark_registrants", default_count))
        prefix = "EventPerfTest"
        registrant_vals = []

        for i in range(count):
            # Generate realistic data with Faker
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

        # Batch create
        cls.registrants = cls.env["res.partner"].create(registrant_vals)
        _logger.info(f"Created {len(cls.registrants)} registrants")

        # Generate 2000+ event records
        _logger.info("Generating event data for performance tests...")
        cls._generate_event_data()

        # Initialize CEL service
        cls.cel_service = cls.env["spp.cel.service"]
        cls.executor = cls.env["spp.cel.executor"]

        _logger.info("Event data performance test setup complete")

    @classmethod
    def _generate_event_data(cls):
        """Generate event data records for testing.

        Creates:
        - 1000 household survey events (one per registrant)
        - 1000+ field visit events (some registrants have multiple)
        """
        event_vals = []

        # Create one survey per registrant
        for registrant in cls.registrants:
            # Random date within last year
            days_ago = cls.fake.random_int(min=0, max=365)
            collection_date = date.today() - timedelta(days=days_ago)

            event_vals.append(
                {
                    "partner_id": registrant.id,
                    "event_type_id": cls.survey_type.id,
                    "collection_date": collection_date,
                    "state": "active",
                    "data_json": {
                        "income": cls.fake.random_int(min=100, max=10000),
                        "household_size": cls.fake.random_int(min=1, max=12),
                        "has_disability": cls.fake.boolean(chance_of_getting_true=15),
                        "employed": cls.fake.boolean(chance_of_getting_true=60),
                        "score": cls.fake.random_int(min=0, max=100),
                    },
                }
            )

        # Create multiple visits for some registrants (50% have visits)
        for registrant in cls.registrants[: len(cls.registrants) // 2]:
            # Random number of visits (1-3)
            num_visits = cls.fake.random_int(min=1, max=3)

            for i in range(num_visits):
                days_ago = cls.fake.random_int(min=0, max=365)
                collection_date = date.today() - timedelta(days=days_ago)

                event_vals.append(
                    {
                        "partner_id": registrant.id,
                        "event_type_id": cls.visit_type.id,
                        "collection_date": collection_date,
                        "state": "active",
                        "data_json": {
                            "verified": cls.fake.boolean(chance_of_getting_true=70),
                            "visit_number": i + 1,
                            "notes": cls.fake.text(max_nb_chars=100),
                        },
                    }
                )

        # Batch create all events
        import time

        start = time.perf_counter()
        cls.events = cls.env["spp.event.data"].create(event_vals)
        elapsed = time.perf_counter() - start
        _logger.info(f"Created {len(cls.events)} event records in {elapsed:.2f}s")

    def setUp(self):
        """Check module availability before each test."""
        super().setUp()
        if not self._module_installed:
            self.skipTest("Required modules (spp_event_data, spp_cel_event) not installed")

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 1: Event value comparison performance
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_value_compare_performance(self):
        """Test performance of event field comparison.

        Expression: event('household_survey').income < 500
        Measures SQL fast path performance and index usage.
        """
        expression = "event('household_survey').income < 500"

        # Translate expression
        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"
        with self.benchmark("Translate event comparison expression"):
            translation = self.translator.translate(model, expression, cfg)

        # Evaluate against all registrants with query analysis
        base_domain = [("id", "in", self.registrants.ids)]
        with self.analyze_queries("Event value comparison"):
            with self.benchmark("Evaluate event comparison (1000 registrants)"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

        # Count matches
        matches = result["count"] if result["valid"] else 0

        # Report results
        self.report_metrics(
            {
                "Expression": expression,
                "Total registrants": len(self.registrants),
                "Matching registrants": matches,
                "Match percentage": f"{matches / len(self.registrants) * 100:.1f}%",
                "Translation available": translation is not None,
            }
        )

        # Verify we got results
        self.assertIsNotNone(translation, "Expression should translate successfully")
        self.assertGreater(matches, 0, "Should find some matching registrants")

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 2: Event existence check performance
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_exists_performance(self):
        """Test performance of has_event() function.

        Compares:
        - has_event('household_survey') - simple existence
        - has_event('household_survey', within_days=365) - with temporal filter
        """
        expressions = {
            "Simple existence": "has_event('household_survey')",
            "With temporal filter": "has_event('household_survey', within_days=365)",
        }

        results_summary = {}

        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"

        for name, expression in expressions.items():
            # Translate (result not used, but translation is validated)
            self.translator.translate(model, expression, cfg)

            # Evaluate with benchmarking
            base_domain = [("id", "in", self.registrants.ids)]
            with self.benchmark(f"Evaluate {name}"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

            matches = result["count"] if result["valid"] else 0
            results_summary[name] = {
                "matches": matches,
                "percentage": f"{matches / len(self.registrants) * 100:.1f}%",
            }

        # Report comparison
        self.report_metrics(
            {
                "Total registrants": len(self.registrants),
                "Simple existence matches": results_summary["Simple existence"]["matches"],
                "Simple existence %": results_summary["Simple existence"]["percentage"],
                "Temporal filter matches": results_summary["With temporal filter"]["matches"],
                "Temporal filter %": results_summary["With temporal filter"]["percentage"],
            }
        )

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 3: Events count aggregation performance
    # ══════════════════════════════════════════════════════════════════════════════

    def test_events_count_aggregation(self):
        """Test performance of events_count() function.

        Expression: events_count('field_visit') >= 2
        Tests GROUP BY HAVING performance.
        """
        expression = "events_count('field_visit') >= 2"

        # Translate
        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"
        with self.benchmark("Translate events_count expression"):
            translation = self.translator.translate(model, expression, cfg)

        # Evaluate with query analysis
        base_domain = [("id", "in", self.registrants.ids)]
        with self.analyze_queries("Events count aggregation"):
            with self.benchmark("Evaluate events_count (1000 registrants)"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

        matches = result["count"] if result["valid"] else 0

        # Report results
        self.report_metrics(
            {
                "Expression": expression,
                "Total registrants": len(self.registrants),
                "Registrants with 2+ visits": matches,
                "Percentage": f"{matches / len(self.registrants) * 100:.1f}%",
            }
        )

        self.assertIsNotNone(translation, "Expression should translate successfully")

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 4: Event aggregate functions performance
    # ══════════════════════════════════════════════════════════════════════════════

    def test_events_aggregate_functions(self):
        """Test performance of event aggregation functions.

        Tests: events_sum, events_avg, events_min, events_max
        Expression: events_avg('household_survey', 'income', within_days=365) < 500
        """
        expressions = {
            "Average income": "events_avg('household_survey', 'income', within_days=365) < 500",
            "Sum household size": "events_sum('household_survey', 'household_size') > 5",
            "Max score": "events_max('household_survey', 'score') >= 80",
            "Min income": "events_min('household_survey', 'income') < 200",
        }

        results_summary = {}

        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"

        for name, expression in expressions.items():
            # Translate (result not used, but translation is validated)
            self.translator.translate(model, expression, cfg)

            # Evaluate with benchmarking
            base_domain = [("id", "in", self.registrants.ids)]
            with self.benchmark(f"Evaluate {name}"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

            matches = result["count"] if result["valid"] else 0
            results_summary[name] = matches

        # Report results
        self.report_metrics(
            {
                "Total registrants": len(self.registrants),
                "Average income < 500": results_summary["Average income"],
                "Sum household_size > 5": results_summary["Sum household size"],
                "Max score >= 80": results_summary["Max score"],
                "Min income < 200": results_summary["Min income"],
            }
        )

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 5: Temporal filter performance comparison
    # ══════════════════════════════════════════════════════════════════════════════

    def test_temporal_filter_performance(self):
        """Test performance of different temporal filters.

        Compares: within_days vs within_months vs period
        Tests date range index usage.
        """
        base_expression = "has_event('household_survey'{})"

        filters = {
            "No filter": "",
            "within_days=90": ", within_days=90",
            "within_days=365": ", within_days=365",
            "within_months=6": ", within_months=6",
            "within_months=12": ", within_months=12",
        }

        results_summary = {}

        for name, filter_params in filters.items():
            expression = base_expression.format(filter_params)

            # Evaluate with benchmarking
            base_domain = [("id", "in", self.registrants.ids)]
            with self.benchmark(f"Temporal filter: {name}"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

            matches = result["count"] if result["valid"] else 0
            results_summary[name] = matches

        # Report comparison
        metrics = {"Total registrants": len(self.registrants)}
        for name, matches in results_summary.items():
            metrics[f"{name} matches"] = matches
            metrics[f"{name} %"] = f"{matches / len(self.registrants) * 100:.1f}%"

        self.report_metrics(metrics)

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 6: Selection mode performance comparison
    # ══════════════════════════════════════════════════════════════════════════════

    def test_selection_mode_performance(self):
        """Test performance of different selection modes.

        Compares: select='latest' vs select='first' vs select='active'
        Measures DISTINCT ON performance.
        """
        base_expression = "event('household_survey', select='{}').income < 500"

        selection_modes = ["latest", "first", "active"]
        results_summary = {}

        for mode in selection_modes:
            expression = base_expression.format(mode)

            # Evaluate with benchmarking
            base_domain = [("id", "in", self.registrants.ids)]
            with self.benchmark(f"Selection mode: {mode}"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

            matches = result["count"] if result["valid"] else 0
            results_summary[mode] = matches

        # Report comparison
        self.report_metrics(
            {
                "Total registrants": len(self.registrants),
                "select='latest' matches": results_summary["latest"],
                "select='first' matches": results_summary["first"],
                "select='active' matches": results_summary["active"],
            }
        )

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 7: SQL vs Python execution path comparison
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_sql_vs_python_path(self):
        """Test SQL fast path vs Python fallback performance.

        Compares execution time for SQL-translatable vs Python-only expressions.
        Reports speedup factor.
        """
        # SQL-translatable expression (simple field comparison)
        sql_expression = "event('household_survey').income < 500"

        # Python-only expression (complex logic requiring Python evaluation)
        # Note: This depends on what the translator supports
        # For now, we'll just measure the SQL path performance
        python_expression = "event('household_survey').income < 500 && event('household_survey').household_size > 5"

        results = {}
        base_domain = [("id", "in", self.registrants.ids)]

        # Test SQL path
        with self.benchmark("SQL path evaluation"):
            sql_result = self.cel_service.compile_expression(
                sql_expression,
                profile="registry_individuals",
                base_domain=base_domain,
                limit=0,
            )
        sql_matches = sql_result["count"] if sql_result["valid"] else 0
        results["SQL path"] = {
            "matches": sql_matches,
            "time": self._benchmark_results.get("SQL path evaluation", {}).get("elapsed_s", 0),
        }

        # Test complex expression (may use Python fallback)
        with self.benchmark("Complex expression evaluation"):
            python_result = self.cel_service.compile_expression(
                python_expression,
                profile="registry_individuals",
                base_domain=base_domain,
                limit=0,
            )
        python_matches = python_result["count"] if python_result["valid"] else 0
        results["Complex expression"] = {
            "matches": python_matches,
            "time": self._benchmark_results.get("Complex expression evaluation", {}).get("elapsed_s", 0),
        }

        # Calculate speedup if both completed
        speedup = 0
        if results["Complex expression"]["time"] > 0:
            speedup = results["SQL path"]["time"] / results["Complex expression"]["time"]

        # Report results
        self.report_metrics(
            {
                "Total registrants": len(self.registrants),
                "SQL path matches": results["SQL path"]["matches"],
                "SQL path time (s)": results["SQL path"]["time"],
                "Complex expr matches": results["Complex expression"]["matches"],
                "Complex expr time (s)": results["Complex expression"]["time"],
                "Time ratio (SQL/Complex)": f"{speedup:.2f}x" if speedup > 0 else "N/A",
            }
        )

    # ══════════════════════════════════════════════════════════════════════════════
    # Test 8: Index recommendations for event queries
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_index_recommendations(self):
        """Test event queries and check for index recommendations.

        Runs various event queries with analyze_queries to identify
        missing indexes on spp_event_data table.
        """
        expressions = [
            "event('household_survey').income < 500",
            "has_event('household_survey', within_days=365)",
            "events_count('field_visit') >= 2",
            "events_avg('household_survey', 'income') < 500",
        ]

        _logger.info("\n" + "=" * 70)
        _logger.info("EVENT QUERY INDEX ANALYSIS")
        _logger.info("=" * 70)

        for expression in expressions:
            _logger.info(f"\nAnalyzing: {expression}")

            base_domain = [("id", "in", self.registrants[:100].ids)]
            with self.analyze_queries(f"Query: {expression}"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

            matches = result["count"] if result["valid"] else 0
            _logger.info(f"  Matches: {matches}/100")

        # Print index recommendations if any were collected
        if self._index_recommendations:
            _logger.info("\n" + "=" * 70)
            _logger.info("INDEX RECOMMENDATIONS FOR EVENT DATA")
            _logger.info("=" * 70)
            unique_recommendations = list(set(self._index_recommendations))
            for rec in unique_recommendations[:10]:  # Top 10
                _logger.info(f"  {rec}")
            _logger.info("=" * 70)
        else:
            _logger.info("\nNo index recommendations - event queries are well optimized!")

    # ══════════════════════════════════════════════════════════════════════════════
    # Additional test: Complex real-world eligibility scenario
    # ══════════════════════════════════════════════════════════════════════════════

    def test_complex_event_eligibility_scenario(self):
        """Test complex real-world eligibility expression with events.

        Expression combines:
        - Event data comparison
        - Temporal filters
        - Multiple event types
        - Aggregation

        Example: "Poor households with recent survey and multiple visits"
        """
        expression = (
            "event('household_survey', within_days=365).income < 500 && "
            "events_count('field_visit', within_days=180) >= 2"
        )

        # Translate
        cfg = self.cel_registry.load_profile("registry_individuals")
        model = "res.partner"
        with self.benchmark("Translate complex eligibility expression"):
            translation = self.translator.translate(model, expression, cfg)

        # Evaluate with full analysis
        base_domain = [("id", "in", self.registrants.ids)]
        with self.analyze_queries("Complex eligibility scenario"):
            with self.benchmark("Evaluate complex eligibility (1000 registrants)"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

        matches = result["count"] if result["valid"] else 0

        # Report results
        self.report_metrics(
            {
                "Expression": expression,
                "Total registrants": len(self.registrants),
                "Eligible registrants": matches,
                "Eligibility rate": f"{matches / len(self.registrants) * 100:.1f}%",
                "Translation available": translation is not None,
            }
        )

        self.assertIsNotNone(translation, "Expression should translate successfully")

    # ══════════════════════════════════════════════════════════════════════════════
    # Bonus test: Large dataset scalability
    # ══════════════════════════════════════════════════════════════════════════════

    def test_event_query_scalability(self):
        """Test event query performance at different scales.

        Measures performance with:
        - 100 registrants
        - 500 registrants
        - 1000 registrants

        Checks for linear scaling.
        """
        expression = "event('household_survey').income < 500"

        scales = [100, 500, 1000]
        timings = {}

        for scale in scales:
            subset = self.registrants[:scale]
            base_domain = [("id", "in", subset.ids)]

            with self.benchmark(f"Evaluate at scale {scale}"):
                result = self.cel_service.compile_expression(
                    expression,
                    profile="registry_individuals",
                    base_domain=base_domain,
                    limit=0,
                )

            matches = result["count"] if result["valid"] else 0
            elapsed = self._benchmark_results.get(f"Evaluate at scale {scale}", {}).get("elapsed_s", 0)
            timings[scale] = {
                "elapsed": elapsed,
                "matches": matches,
                "ops_per_sec": scale / elapsed if elapsed > 0 else 0,
            }

        # Report scalability
        metrics = {}
        for scale, data in timings.items():
            metrics[f"Scale {scale} time (s)"] = data["elapsed"]
            metrics[f"Scale {scale} matches"] = data["matches"]
            metrics[f"Scale {scale} ops/sec"] = f"{data['ops_per_sec']:.0f}"

        self.report_metrics(metrics)

        # Check for roughly linear scaling
        # Time for 1000 should be roughly 10x time for 100
        if timings[100]["elapsed"] > 0:
            scaling_factor = timings[1000]["elapsed"] / timings[100]["elapsed"]
            _logger.info(f"\nScaling factor (1000/100): {scaling_factor:.2f}x (ideal: ~10x)")
            # Allow 2x overhead for non-linear effects
            self.assertLess(
                scaling_factor,
                20.0,
                f"Scaling appears super-linear: {scaling_factor:.2f}x",
            )
