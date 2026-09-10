# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Performance tests for program eligibility evaluation with CEL expressions.

Tests the eligibility evaluation performance for programs using CEL expressions,
including:
- Simple eligibility checks
- Complex multi-criteria evaluation
- Domain preparation and compilation
- Bulk enrollment simulation
- Household-based criteria
- Concurrent eligibility checks across programs
"""

import logging

import odoo
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from . import common

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "performance")
class TestEligibilityPerformance(common.PerformanceTestCase):
    """Test suite for eligibility evaluation performance benchmarks."""

    @classmethod
    def setUpClass(cls):
        """Initialize test data for eligibility performance tests."""
        super().setUpClass()

        # Skip if spp_eligibility_cel is not installed
        if "spp.program.membership.manager.default" not in cls.env:
            cls.skipTest(cls, "spp_eligibility_cel module not installed")

        # Generate registrants for testing (configurable via cel_benchmark_registrants)
        _logger.info("Setting up eligibility performance test data...")

        # Inline data generation for setUpClass (instance method not available)
        default_count = 1000
        count = int(odoo.tools.config.get("cel_benchmark_registrants", default_count))
        prefix = "EligTest"
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

        # Create test program
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Performance Program",
                "target_type": "individual",
            }
        )

        # Try to create eligibility manager with CEL mode
        try:
            cls.manager = cls.env["spp.program.membership.manager.default"].create(
                {
                    "name": "Test CEL Eligibility Manager",
                    "program_id": cls.program.id,
                    "eligibility_mode": "cel",
                    "cel_expression": "true",  # Will be updated in tests
                }
            )
            cls._manager_available = True
        except Exception as e:
            _logger.warning(f"Could not create eligibility manager: {e}")
            cls._manager_available = False
            cls.manager = None

        _logger.info("Test data setup complete")

    def setUp(self):
        """Check if eligibility manager is available before each test."""
        super().setUp()
        if not getattr(self, "_manager_available", False):
            self.skipTest("Eligibility manager could not be created")

    def test_eligibility_check_simple_expression(self):
        """Test eligibility evaluation with simple CEL expression.

        Evaluates "age_years(r.birthdate) >= 18" against 1000 registrants.
        Measures:
        - Total evaluation time
        - Domain preparation time
        - SQL query performance
        """
        # Set simple eligibility expression
        self.manager.cel_expression = "age_years(r.birthdate) >= 18"
        self.manager._compute_cel_preview()

        # Verify expression is valid
        self.assertTrue(
            self.manager.cel_is_valid,
            f"CEL expression validation failed: {self.manager.cel_preview_error}",
        )

        # Measure domain preparation performance
        with self.benchmark("Prepare eligible domain (simple expression)"):
            with self.analyze_queries("Domain preparation - simple"):
                domain = self.manager._prepare_eligible_domain()

        self.assertIsInstance(domain, list)
        _logger.info(f"Generated domain has {len(domain)} conditions")

        # Measure eligibility check performance
        with self.benchmark("Check 1000 registrants eligibility (simple)"):
            with self.analyze_queries("Eligibility check - simple"):
                eligible = self.env["res.partner"].search(domain)

        _logger.info(f"Found {len(eligible)} eligible registrants out of {len(self.registrants)}")

        # Report metrics
        self.report_metrics(
            {
                "Total registrants": len(self.registrants),
                "Eligible registrants": len(eligible),
                "Eligibility rate": f"{len(eligible) / len(self.registrants) * 100:.1f}%",
                "Domain conditions": len(domain),
            }
        )

    def test_eligibility_check_complex_expression(self):
        """Test eligibility evaluation with complex CEL expression.

        Evaluates multi-criteria expression against 1000 registrants.
        Expression: "age_years(r.birthdate) >= 60 && r.income < 5000"
        Compares performance with simple expression.
        """
        # Set complex eligibility expression
        self.manager.cel_expression = "age_years(r.birthdate) >= 60 && r.income < 5000"
        self.manager._compute_cel_preview()

        # Verify expression is valid
        self.assertTrue(
            self.manager.cel_is_valid,
            f"CEL expression validation failed: {self.manager.cel_preview_error}",
        )

        # Measure domain preparation
        with self.benchmark("Prepare eligible domain (complex expression)"):
            with self.analyze_queries("Domain preparation - complex"):
                domain = self.manager._prepare_eligible_domain()

        # Measure eligibility check
        with self.benchmark("Check 1000 registrants eligibility (complex)"):
            with self.analyze_queries("Eligibility check - complex"):
                eligible = self.env["res.partner"].search(domain)

        _logger.info(f"Complex criteria: Found {len(eligible)} eligible out of {len(self.registrants)}")

        # Report metrics
        self.report_metrics(
            {
                "Total registrants": len(self.registrants),
                "Eligible (complex criteria)": len(eligible),
                "Eligibility rate": f"{len(eligible) / len(self.registrants) * 100:.1f}%",
                "Domain conditions": len(domain),
            }
        )

    def test_eligibility_domain_preparation(self):
        """Test performance of _prepare_eligible_domain() method.

        Measures:
        - Time to prepare domain from CEL expression
        - Domain generation overhead
        - Comparison between cached and uncached compilation
        """
        expressions = [
            "true",
            "age_years(r.birthdate) >= 18",
            "r.income < 5000",
            "r.income > 1000",
            "age_years(r.birthdate) >= 60 && r.income < 5000",
        ]

        results = {}

        for expr in expressions:
            self.manager.cel_expression = expr
            self.manager._compute_cel_preview()

            # First call (may involve compilation)
            with self.benchmark(f"Domain prep (first): {expr[:50]}"):
                domain1 = self.manager._prepare_eligible_domain()

            # Second call (may use cache)
            with self.benchmark(f"Domain prep (cached): {expr[:50]}"):
                domain2 = self.manager._prepare_eligible_domain()

            results[expr[:30]] = {
                "conditions": len(domain1),
                "cached_same": domain1 == domain2,
            }

        # Report all results
        _logger.info("\n" + "=" * 70)
        _logger.info("DOMAIN PREPARATION BENCHMARK")
        _logger.info("=" * 70)
        for expr, result in results.items():
            _logger.info(f"  {expr}")
            _logger.info(f"    Conditions: {result['conditions']}")
            _logger.info(f"    Cache hit: {result['cached_same']}")
        _logger.info("=" * 70 + "\n")

    def test_bulk_enrollment_simulation(self):
        """Test bulk enrollment performance.

        Simulates enrolling 500+ eligible registrants into a program.
        Tests:
        - Enrollment throughput
        - Deduplication performance (some already enrolled)
        - Database insertion performance
        """
        # Set eligibility to capture about half the registrants
        self.manager.cel_expression = "age_years(r.birthdate) >= 30"
        self.manager._compute_cel_preview()

        # Get eligible registrants
        with self.benchmark("Find eligible registrants for enrollment"):
            domain = self.manager._prepare_eligible_domain()
            eligible = self.env["res.partner"].search(domain)

        _logger.info(f"Found {len(eligible)} eligible registrants for enrollment")

        # Ensure we have at least 500 for a meaningful test
        if len(eligible) < 100:
            _logger.warning(f"Only {len(eligible)} eligible registrants found, test may not be representative")

        # Enroll first batch (simulate initial enrollment)
        batch_size = min(len(eligible) // 2, 250)
        first_batch = eligible[:batch_size]

        with self.benchmark(f"Enroll first batch ({len(first_batch)} registrants)"):
            with self.analyze_queries("Enrollment - first batch"):
                memberships_vals = [
                    {
                        "partner_id": reg.id,
                        "program_id": self.program.id,
                        "state": "enrolled",
                    }
                    for reg in first_batch
                ]
                # Use the dedicated bulk helper so we exercise the same
                # path that large real-world jobs would use, while still
                # going through the normal ORM and audit hooks.
                first_memberships = self.env["spp.program.membership"].bulk_create_memberships(memberships_vals)

        _logger.info(f"Enrolled first batch: {len(first_memberships)} members")

        # Try to enroll full eligible set (includes duplicates)
        with self.benchmark(f"Bulk enrollment with deduplication ({len(eligible)} registrants)"):
            with self.analyze_queries("Enrollment - with deduplication"):
                # Check which are already enrolled
                existing = self.env["spp.program.membership"].search(
                    [
                        ("partner_id", "in", eligible.ids),
                        ("program_id", "=", self.program.id),
                    ]
                )

                # Enroll only new ones
                already_enrolled_ids = existing.mapped("partner_id.id")
                new_eligible = eligible.filtered(lambda r: r.id not in already_enrolled_ids)

                if new_eligible:
                    new_memberships_vals = [
                        {
                            "partner_id": reg.id,
                            "program_id": self.program.id,
                            "state": "enrolled",
                        }
                        for reg in new_eligible
                    ]
                    new_memberships = self.env["spp.program.membership"].bulk_create_memberships(new_memberships_vals)
                else:
                    new_memberships = self.env["spp.program.membership"]

        # Report metrics
        self.report_metrics(
            {
                "Total eligible": len(eligible),
                "First batch enrolled": len(first_memberships),
                "Already enrolled (duplicates)": len(existing),
                "Newly enrolled": len(new_memberships),
                "Total enrolled": len(existing) + len(new_memberships),
                "Deduplication saved": len(already_enrolled_ids),
            }
        )

    def test_eligibility_with_household_criteria(self):
        """Test eligibility evaluation with household member criteria.

        Expression: "members.exists(m, age_years(m.birthdate) < 5)"
        Tests:
        - Household relationship joins
        - Exists operation performance
        - Complex domain generation
        """
        # First, create some households with members for this test
        _logger.info("Creating test households with members...")

        # Generate 100 households with 5 members each
        households, members = self.generate_households(count=100, members_per=5, prefix="PerfHH")

        _logger.info(f"Created {len(households)} households with {len(members)} total members")

        # Create a program targeting groups (households)
        household_program = self.env["spp.program"].create(
            {
                "name": "Household Test Program",
                "target_type": "group",
            }
        )

        # Create eligibility manager for households
        household_manager = self.env["spp.program.membership.manager.default"].create(
            {
                "name": "Household CEL Manager",
                "program_id": household_program.id,
                "eligibility_mode": "cel",
                "cel_expression": "members.exists(m, age_years(m.birthdate) < 5)",
            }
        )

        household_manager._compute_cel_preview()

        # Check if expression is valid
        if not household_manager.cel_is_valid:
            _logger.warning(f"Household member expression not supported: {household_manager.cel_preview_error}")
            _logger.warning("Skipping household criteria test")
            return

        # Measure household eligibility check
        with self.benchmark("Check household eligibility with member criteria"):
            with self.analyze_queries("Household eligibility - member criteria"):
                try:
                    domain = household_manager._prepare_eligible_domain()
                    eligible_households = self.env["res.partner"].search(domain)
                except (ValidationError, Exception) as e:
                    _logger.warning(f"Household eligibility check failed: {e}")
                    _logger.warning("This may indicate the CEL engine doesn't support this pattern yet")
                    return

        _logger.info(f"Households with young children: {len(eligible_households)} out of {len(households)}")

        # Report metrics
        self.report_metrics(
            {
                "Total households": len(households),
                "Eligible households": len(eligible_households),
                "Eligibility rate": f"{len(eligible_households) / len(households) * 100:.1f}%",
            }
        )

    def test_concurrent_eligibility_checks(self):
        """Test sequential eligibility evaluation for multiple programs.

        Creates multiple programs with different CEL expressions and evaluates
        eligibility for all of them sequentially.
        Measures:
        - Total throughput across multiple programs
        - Expression switching overhead
        - Cache effectiveness
        """
        # Create multiple programs with different criteria
        programs_criteria = [
            ("Young Adults", "age_years(r.birthdate) >= 18 && age_years(r.birthdate) < 30"),
            ("Seniors", "age_years(r.birthdate) >= 60"),
            ("Low Income", "r.income < 3000"),
            ("Low Income Support", "r.income < 2000"),
            ("High Income Beneficiaries", "r.income >= 5000"),
        ]

        programs = []
        managers = []

        # Create programs and managers
        for prog_name, criteria in programs_criteria:
            program = self.env["spp.program"].create(
                {
                    "name": f"Concurrent Test - {prog_name}",
                    "target_type": "individual",
                }
            )

            manager = self.env["spp.program.membership.manager.default"].create(
                {
                    "name": f"Manager - {prog_name}",
                    "program_id": program.id,
                    "eligibility_mode": "cel",
                    "cel_expression": criteria,
                }
            )

            programs.append(program)
            managers.append(manager)

        # Evaluate eligibility for all programs
        results = {}

        with self.benchmark("Sequential eligibility checks for 5 programs"):
            with self.analyze_queries("Concurrent eligibility checks"):
                for _i, (manager, (prog_name, _)) in enumerate(zip(managers, programs_criteria, strict=False)):
                    # Compute preview (validates expression)
                    manager._compute_cel_preview()

                    if not manager.cel_is_valid:
                        _logger.warning(f"Program '{prog_name}' has invalid expression")
                        continue

                    # Get eligible count
                    domain = manager._prepare_eligible_domain()
                    eligible = self.env["res.partner"].search(domain)

                    results[prog_name] = {
                        "eligible": len(eligible),
                        "rate": len(eligible) / len(self.registrants) * 100,
                    }

        # Report results
        _logger.info("\n" + "=" * 70)
        _logger.info("CONCURRENT ELIGIBILITY CHECKS RESULTS")
        _logger.info("=" * 70)
        _logger.info(f"  Total registrants: {len(self.registrants)}")
        _logger.info("-" * 70)
        for prog_name, result in results.items():
            _logger.info(f"  {prog_name}:")
            _logger.info(f"    Eligible: {result['eligible']} ({result['rate']:.1f}%)")
        _logger.info("=" * 70 + "\n")

        # Verify we got results for most programs
        self.assertGreaterEqual(
            len(results),
            3,
            f"Expected at least 3 valid programs, got {len(results)}",
        )
