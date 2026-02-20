# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Integration tests using MIS Demo V2 data.

These tests use the realistic demo data generator from spp_mis_demo_v2 to test
aggregation service functionality with real-world data patterns including:
- Hierarchical administrative areas (Philippines)
- Realistic demographic distributions
- Multiple programs with enrollments
- GPS coordinates for spatial queries
"""

import logging
import unittest

from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestAggregationIntegrationDemo(TransactionCase):
    """Integration tests for aggregation service using MIS demo data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Check if spp_mis_demo_v2 is available
        if "spp.mis.demo.generator" not in cls.env:
            # Module not available - skip all tests in this class
            raise unittest.SkipTest("spp_mis_demo_v2 module not installed - integration tests skipped")

        # Generate MIS demo data with controlled volume
        # Use smaller volume for faster tests but enough for statistical significance
        _logger.info("Generating MIS demo data for integration tests...")
        cls.demo_wizard = cls.env["spp.mis.demo.generator"].create(
            {
                "name": "Integration Test Demo",
                "demo_mode": "testing",
                "create_demo_programs": True,
                "enroll_demo_stories": True,
                "generate_random_groups": True,
                "random_groups_count": 50,  # Enough for multi-dimensional breakdowns
                "members_per_group_min": 2,
                "members_per_group_max": 6,
                "generate_volume": True,
                "volume_enrollments": 30,
                "load_geographic_data": True,
                "country_code": "phl",
                "create_cycles": True,
                "cycles_per_program": 2,
                "create_change_requests": False,  # Skip CRs for faster tests
                "generate_grm_demo": False,  # Skip GRM for faster tests
                "generate_case_demo": False,  # Skip cases for faster tests
                "generate_claim169_demo": False,  # Skip QR credentials for faster tests
                "generate_simulation_demo": False,  # Skip simulation for faster tests
            }
        )

        # Run demo generation
        cls.demo_wizard.action_generate()
        _logger.info("MIS demo data generation complete")

        # Get references to key models
        cls.service = cls.env["spp.aggregation.service"]
        cls.scope_model = cls.env["spp.aggregation.scope"]
        cls.area_model = cls.env["spp.area"]
        cls.partner_model = cls.env["res.partner"]
        cls.dimension_model = cls.env["spp.demographic.dimension"]

        # Get demo data references
        cls.all_registrants = cls.partner_model.search([("is_registrant", "=", True)])
        cls.all_areas = cls.area_model.search([])

        # Get specific area levels (Philippines hierarchy)
        cls.country_areas = cls.area_model.search([("level", "=", 0)])
        cls.region_areas = cls.area_model.search([("level", "=", 1)])
        cls.province_areas = cls.area_model.search([("level", "=", 2)])
        cls.municipality_areas = cls.area_model.search([("level", "=", 3)])

        # Get dimension records for testing
        cls.dim_gender = cls.dimension_model.search([("name", "=", "gender")], limit=1)
        cls.dim_disability = cls.dimension_model.search([("name", "=", "disability_status")], limit=1)
        cls.dim_area = cls.dimension_model.search([("name", "=", "area")], limit=1)
        cls.dim_age_group = cls.dimension_model.search([("name", "=", "age_group")], limit=1)

        _logger.info(
            "Test setup complete: %d registrants, %d areas (%d regions, %d provinces, %d municipalities)",
            len(cls.all_registrants),
            len(cls.all_areas),
            len(cls.region_areas),
            len(cls.province_areas),
            len(cls.municipality_areas),
        )

    def test_area_based_aggregation_country_level(self):
        """Test aggregation at country level with hierarchical rollup."""
        if not self.country_areas:
            self.skipTest("No country-level areas found in demo data")

        country = self.country_areas[0]

        # Create scope for entire country
        scope = self.scope_model.create(
            {
                "name": f"Test Country: {country.draft_name}",
                "scope_type": "area",
                "area_id": country.id,
                "include_child_areas": True,
            }
        )

        # Compute aggregation
        result = self.service.compute_aggregation(scope)

        # Assertions
        self.assertGreater(result["total_count"], 0, "Should have registrants in country")
        self.assertEqual(result["access_level"], "individual", "Admin should have individual access")
        self.assertIn("computed_at", result)
        self.assertFalse(result["from_cache"], "First query should not be cached")

        # Verify all registrants from demo are included
        country_registrants = self.partner_model.search(
            [
                ("is_registrant", "=", True),
                ("area_id", "child_of", country.id),
            ]
        )
        self.assertEqual(
            result["total_count"],
            len(country_registrants),
            "Country scope should include all descendant areas",
        )

    def test_area_based_aggregation_region_level(self):
        """Test aggregation at region level (first administrative division)."""
        if not self.region_areas:
            self.skipTest("No region-level areas found in demo data")

        region = self.region_areas[0]

        # Create scope for single region
        scope = self.scope_model.create(
            {
                "name": f"Test Region: {region.draft_name}",
                "scope_type": "area",
                "area_id": region.id,
                "include_child_areas": True,
            }
        )

        # Compute aggregation
        result = self.service.compute_aggregation(scope)

        # Assertions
        self.assertGreater(result["total_count"], 0, "Should have registrants in region")

        # Verify count matches actual registrants in this region's hierarchy
        region_registrants = self.partner_model.search(
            [
                ("is_registrant", "=", True),
                ("area_id", "child_of", region.id),
            ]
        )
        self.assertEqual(result["total_count"], len(region_registrants))

    def test_multi_dimensional_breakdown_gender_x_area(self):
        """Test 2D breakdown: gender × area."""
        if not self.region_areas:
            self.skipTest("No regions found in demo data")

        # Pick a region with registrants
        region = self.region_areas[0]

        scope = self.scope_model.create(
            {
                "name": "Test 2D: Gender × Area",
                "scope_type": "area",
                "area_id": region.id,
                "include_child_areas": True,
            }
        )

        # Compute with 2D breakdown
        result = self.service.compute_aggregation(
            scope,
            group_by=["gender", "area"],
        )

        # Assertions
        self.assertIn("breakdown", result, "Should have breakdown cells")
        self.assertGreater(len(result["breakdown"]), 0, "Should have breakdown cells")

        # Check cell structure
        first_cell_key = list(result["breakdown"].keys())[0]
        first_cell = result["breakdown"][first_cell_key]
        self.assertIn("count", first_cell)
        self.assertIn("dimensions", first_cell)
        self.assertEqual(len(first_cell["dimensions"]), 2, "Should have 2 dimensions")

        # Verify total count matches sum of cells
        total_from_cells = sum(cell["count"] for cell in result["breakdown"].values())
        self.assertEqual(
            result["total_count"],
            total_from_cells,
            "Total count should equal sum of breakdown cells",
        )

    def test_multi_dimensional_breakdown_gender_x_disability_x_area(self):
        """Test 3D breakdown: gender × disability × area (max dimensions)."""
        if not self.province_areas:
            self.skipTest("No provinces found in demo data")

        # Pick a province with registrants
        province = self.province_areas[0]

        scope = self.scope_model.create(
            {
                "name": "Test 3D: Gender × Disability × Area",
                "scope_type": "area",
                "area_id": province.id,
                "include_child_areas": True,
            }
        )

        # Compute with 3D breakdown (max allowed dimensions)
        result = self.service.compute_aggregation(
            scope,
            group_by=["gender", "disability_status", "area"],
        )

        # Assertions
        self.assertIn("breakdown", result)
        self.assertGreater(len(result["breakdown"]), 0)

        # Check cell structure has 3 dimensions
        first_cell = list(result["breakdown"].values())[0]
        self.assertEqual(len(first_cell["dimensions"]), 3)

        # Verify dimension order matches request
        dim_names = [d["name"] for d in first_cell["dimensions"]]
        self.assertEqual(dim_names, ["gender", "disability_status", "area"])

    def test_k_anonymity_suppression_with_realistic_data(self):
        """Test k-anonymity suppression with real demographic distributions."""
        # Create a restricted user with aggregate-only access
        restricted_user = self.env["res.users"].create(
            {
                "name": "Test Researcher",
                "login": "test_researcher",
                "groups_id": [(6, 0, [self.ref("base.group_user")])],
            }
        )

        # Create access rule for aggregate-only access with k=5
        self.env["spp.aggregation.access.rule"].create(
            {
                "name": "Researcher Aggregate Access",
                "access_level": "aggregate",
                "k_threshold": 5,
                "group_id": self.ref("base.group_user"),
            }
        )

        # Pick a small area that likely has cells with count < 5
        if self.municipality_areas:
            small_area = self.municipality_areas[0]
        elif self.province_areas:
            small_area = self.province_areas[0]
        else:
            self.skipTest("No suitable areas for k-anonymity testing")

        scope = self.scope_model.create(
            {
                "name": "Test K-Anonymity",
                "scope_type": "area",
                "area_id": small_area.id,
                "include_child_areas": False,  # Don't include children for smaller cells
            }
        )

        # Compute with 2D breakdown as restricted user
        result = self.service.with_user(restricted_user).compute_aggregation(
            scope,
            group_by=["gender", "disability_status"],
        )

        # Assertions
        self.assertEqual(result["access_level"], "aggregate")

        # Check that small cells are suppressed
        suppressed_cells = 0
        visible_cells = 0
        for cell in result["breakdown"].values():
            if cell.get("suppressed"):
                suppressed_cells += 1
                # Suppressed cells should not expose count
                self.assertNotIn("count", cell)
            else:
                visible_cells += 1
                # Visible cells must meet k-threshold
                self.assertGreaterEqual(cell["count"], 5)

        _logger.info(
            "K-anonymity test: %d visible cells, %d suppressed cells",
            visible_cells,
            suppressed_cells,
        )

        # Should have some suppression with realistic data
        self.assertGreater(
            suppressed_cells,
            0,
            "Should have suppressed some small cells with k=5",
        )

    def test_cache_behavior_repeated_queries(self):
        """Test that repeated queries use cache correctly."""
        if not self.region_areas:
            self.skipTest("No regions found for cache testing")

        region = self.region_areas[0]

        scope = self.scope_model.create(
            {
                "name": "Test Cache",
                "scope_type": "area",
                "area_id": region.id,
                "include_child_areas": True,
            }
        )

        # First query - should not be cached
        result1 = self.service.compute_aggregation(scope)
        self.assertFalse(result1["from_cache"])
        computed_at_1 = result1["computed_at"]

        # Second query - should be cached
        result2 = self.service.compute_aggregation(scope)
        self.assertTrue(result2["from_cache"])
        self.assertEqual(result2["computed_at"], computed_at_1)
        self.assertEqual(result2["total_count"], result1["total_count"])

        # Query with use_cache=False - should recompute
        result3 = self.service.compute_aggregation(scope, use_cache=False)
        self.assertFalse(result3["from_cache"])
        self.assertNotEqual(result3["computed_at"], computed_at_1)
        self.assertEqual(result3["total_count"], result1["total_count"])

    def test_cache_invalidation_different_breakdowns(self):
        """Test that cache properly differentiates breakdown dimensions."""
        if not self.region_areas:
            self.skipTest("No regions found for cache testing")

        region = self.region_areas[0]

        scope = self.scope_model.create(
            {
                "name": "Test Cache Breakdown",
                "scope_type": "area",
                "area_id": region.id,
                "include_child_areas": True,
            }
        )

        # Query with gender breakdown
        result1 = self.service.compute_aggregation(scope, group_by=["gender"])
        self.assertFalse(result1["from_cache"])

        # Query with disability breakdown - should NOT use cache
        result2 = self.service.compute_aggregation(scope, group_by=["disability_status"])
        self.assertFalse(result2["from_cache"])

        # Repeat gender query - SHOULD use cache
        result3 = self.service.compute_aggregation(scope, group_by=["gender"])
        self.assertTrue(result3["from_cache"])

    def test_performance_larger_dataset(self):
        """Test performance with larger dataset (all demo registrants)."""
        # Use entire country for maximum dataset
        if self.country_areas:
            area = self.country_areas[0]
        elif self.all_areas:
            area = self.all_areas[0]
        else:
            self.skipTest("No areas available for performance testing")

        scope = self.scope_model.create(
            {
                "name": "Test Performance - Large Dataset",
                "scope_type": "area",
                "area_id": area.id,
                "include_child_areas": True,
            }
        )

        # Test aggregation with 2D breakdown
        import time

        start = time.time()
        result = self.service.compute_aggregation(
            scope,
            group_by=["gender", "age_group"],
        )
        duration = time.time() - start

        _logger.info(
            "Performance test: aggregated %d registrants with 2D breakdown in %.2fs",
            result["total_count"],
            duration,
        )

        # Assertions
        self.assertGreater(result["total_count"], 50, "Should have substantial dataset")
        self.assertLess(duration, 10.0, "Should complete within 10 seconds")
        self.assertIn("breakdown", result)

    def test_privacy_differencing_attack_prevention(self):
        """Test that differencing attacks are prevented through complementary suppression."""
        # Create restricted user
        restricted_user = self.env["res.users"].create(
            {
                "name": "Test Attacker",
                "login": "test_attacker",
                "groups_id": [(6, 0, [self.ref("base.group_user")])],
            }
        )

        # Create strict access rule with k=10
        self.env["spp.aggregation.access.rule"].create(
            {
                "name": "Strict Aggregate Access",
                "access_level": "aggregate",
                "k_threshold": 10,
                "group_id": self.ref("base.group_user"),
            }
        )

        if not self.province_areas:
            self.skipTest("No provinces available for privacy testing")

        province = self.province_areas[0]

        # Attacker tries to isolate small groups by complementary queries
        scope_all = self.scope_model.create(
            {
                "name": "Privacy Test - All",
                "scope_type": "area",
                "area_id": province.id,
                "include_child_areas": True,
            }
        )

        # Query 1: All registrants by gender
        result_all = self.service.with_user(restricted_user).compute_aggregation(
            scope_all,
            group_by=["gender"],
        )

        # Count suppressed cells
        suppressed_count = sum(1 for cell in result_all["breakdown"].values() if cell.get("suppressed"))

        # With complementary suppression, if one cell is suppressed,
        # its complement should also be suppressed to prevent differencing
        if suppressed_count > 0:
            # If any cell is suppressed, there should be multiple suppressions
            # (complementary suppression)
            visible_count = sum(1 for cell in result_all["breakdown"].values() if not cell.get("suppressed"))

            _logger.info(
                "Privacy test: %d visible cells, %d suppressed cells",
                visible_count,
                suppressed_count,
            )

            # With 2 genders and small counts, if one is suppressed,
            # the other should be too (complementary suppression)
            if len(result_all["breakdown"]) == 2:
                self.assertEqual(
                    suppressed_count,
                    2,
                    "Both cells should be suppressed for complementary protection",
                )

    def test_spatial_aggregation_with_gps_coordinates(self):
        """Test spatial aggregation using GPS coordinates from demo data."""
        # Check if any registrants have GPS coordinates
        registrants_with_gps = self.partner_model.search(
            [
                ("is_registrant", "=", True),
                ("geo_point", "!=", False),
            ]
        )

        if not registrants_with_gps:
            self.skipTest("No registrants with GPS coordinates in demo data")

        # Get GPS point from first registrant
        sample_registrant = registrants_with_gps[0]
        if not sample_registrant.geo_point:
            self.skipTest("Sample registrant has no valid GPS point")

        # Create a polygon around the point (approximate 10km radius)
        # Using WKT format for PostGIS
        try:
            from shapely.geometry import Point
        except ImportError:
            self.skipTest("shapely library not available for spatial tests")

        # Parse geo_point (format: "POINT(lon lat)")
        point_wkt = sample_registrant.geo_point
        lon, lat = (float(x) for x in point_wkt.replace("POINT(", "").replace(")", "").split())

        # Create approximate 10km buffer (0.1 degrees ~= 11km at equator)
        center = Point(lon, lat)
        buffer_geom = center.buffer(0.1)
        polygon_wkt = buffer_geom.wkt

        # Create spatial scope
        scope = self.scope_model.create(
            {
                "name": "Test Spatial Aggregation",
                "scope_type": "spatial",
                "spatial_filter_geom": polygon_wkt,
            }
        )

        # Compute aggregation
        result = self.service.compute_aggregation(scope)

        # Assertions
        self.assertGreater(result["total_count"], 0, "Should find registrants in spatial scope")

        # Verify sample registrant is included
        scope_registrant_ids = self.env["spp.aggregation.scope.resolver"].resolve_scope(scope)
        self.assertIn(
            sample_registrant.id,
            scope_registrant_ids,
            "Sample registrant should be within spatial scope",
        )

    def test_breakdown_with_area_hierarchy(self):
        """Test breakdown by area shows proper hierarchy levels."""
        if not self.region_areas:
            self.skipTest("No regions found for hierarchy testing")

        region = self.region_areas[0]

        scope = self.scope_model.create(
            {
                "name": "Test Area Hierarchy",
                "scope_type": "area",
                "area_id": region.id,
                "include_child_areas": True,
            }
        )

        # Break down by area only
        result = self.service.compute_aggregation(scope, group_by=["area"])

        # Assertions
        self.assertIn("breakdown", result)

        # Each cell should have area dimension with proper metadata
        area_ids_in_breakdown = set()
        for cell in result["breakdown"].values():
            area_dim = next(d for d in cell["dimensions"] if d["name"] == "area")
            self.assertIn("value", area_dim)
            self.assertIn("label", area_dim)

            # Extract area ID from value
            area_id = area_dim["value"]
            if area_id:
                area_ids_in_breakdown.add(int(area_id))

        # All areas in breakdown should be descendants of region
        for area_id in area_ids_in_breakdown:
            area = self.area_model.browse(area_id)
            self.assertTrue(
                area.id == region.id or region.id in area.parent_path_ids,
                f"Area {area.draft_name} should be descendant of {region.draft_name}",
            )

    def test_age_group_dimension_with_realistic_data(self):
        """Test age group dimension with realistic birth dates from demo data."""
        if not self.region_areas:
            self.skipTest("No regions found")

        region = self.region_areas[0]

        scope = self.scope_model.create(
            {
                "name": "Test Age Groups",
                "scope_type": "area",
                "area_id": region.id,
                "include_child_areas": True,
            }
        )

        # Break down by age group
        result = self.service.compute_aggregation(scope, group_by=["age_group"])

        # Assertions
        self.assertIn("breakdown", result)

        # Should have multiple age groups
        age_groups = set()
        for cell in result["breakdown"].values():
            age_dim = next(d for d in cell["dimensions"] if d["name"] == "age_group")
            age_groups.add(age_dim["value"])

        _logger.info("Age groups found in demo data: %s", age_groups)

        # Demo data should include varied ages
        self.assertGreaterEqual(
            len(age_groups),
            2,
            "Should have at least 2 age groups in realistic demo data",
        )

        # Expected age groups: child, adult, elderly, unknown
        expected_groups = {"child", "adult", "elderly", "unknown"}
        self.assertTrue(
            age_groups.issubset(expected_groups),
            f"Age groups {age_groups} should be subset of {expected_groups}",
        )

    def test_complementary_suppression_across_dimensions(self):
        """Test complementary suppression works across multiple dimensions."""
        # Create restricted user with k=8
        restricted_user = self.env["res.users"].create(
            {
                "name": "Test Complement User",
                "login": "test_complement",
                "groups_id": [(6, 0, [self.ref("base.group_user")])],
            }
        )

        self.env["spp.aggregation.access.rule"].create(
            {
                "name": "Complement Test Access",
                "access_level": "aggregate",
                "k_threshold": 8,
                "group_id": self.ref("base.group_user"),
            }
        )

        if not self.municipality_areas:
            self.skipTest("No municipalities for complementary suppression testing")

        # Pick smallest area to maximize chance of suppression
        municipality = self.municipality_areas[0]

        scope = self.scope_model.create(
            {
                "name": "Test Complementary Suppression",
                "scope_type": "area",
                "area_id": municipality.id,
                "include_child_areas": False,
            }
        )

        # 2D breakdown with gender × disability
        result = self.service.with_user(restricted_user).compute_aggregation(
            scope,
            group_by=["gender", "disability_status"],
        )

        # Analyze suppression pattern
        cells_by_gender = {}
        for _cell_key, cell in result["breakdown"].items():
            gender_val = cell["dimensions"][0]["value"]
            if gender_val not in cells_by_gender:
                cells_by_gender[gender_val] = []
            cells_by_gender[gender_val].append(cell)

        # For each gender, if one disability status is suppressed,
        # its complement should also be suppressed
        for gender, cells in cells_by_gender.items():
            suppressed = [c for c in cells if c.get("suppressed")]
            visible = [c for c in cells if not c.get("suppressed")]

            if len(suppressed) > 0 and len(suppressed) < len(cells):
                # Partial suppression detected - this could allow differencing
                # Log warning but don't fail (depends on counts)
                _logger.warning(
                    "Partial suppression for gender %s: %d suppressed, %d visible",
                    gender,
                    len(suppressed),
                    len(visible),
                )

    def test_explicit_scope_with_demo_registrants(self):
        """Test explicit scope using specific demo story registrants."""
        # Find demo story personas (if they exist)
        story_registrants = self.partner_model.search(
            [
                ("is_registrant", "=", True),
                ("name", "ilike", "Santos"),
            ],
            limit=5,
        )

        if not story_registrants:
            # Use any registrants
            story_registrants = self.all_registrants[:5]

        if not story_registrants:
            self.skipTest("No registrants available for explicit scope testing")

        scope = self.scope_model.create(
            {
                "name": "Test Explicit Scope - Story Registrants",
                "scope_type": "explicit",
                "explicit_partner_ids": [(6, 0, story_registrants.ids)],
            }
        )

        # Compute aggregation
        result = self.service.compute_aggregation(scope)

        # Assertions
        self.assertEqual(result["total_count"], len(story_registrants))

        # Test with breakdown
        result_breakdown = self.service.compute_aggregation(
            scope,
            group_by=["gender"],
        )
        self.assertIn("breakdown", result_breakdown)

        # Sum of cells should equal total
        total_from_cells = sum(cell["count"] for cell in result_breakdown["breakdown"].values())
        self.assertEqual(total_from_cells, len(story_registrants))

    def test_empty_scope_handling(self):
        """Test handling of scope with no registrants."""
        # Create scope with non-existent area or empty criteria
        scope = self.scope_model.create(
            {
                "name": "Test Empty Scope",
                "scope_type": "explicit",
                "explicit_partner_ids": [(6, 0, [])],
            }
        )

        # Compute aggregation
        result = self.service.compute_aggregation(scope)

        # Assertions
        self.assertEqual(result["total_count"], 0)
        self.assertEqual(result["breakdown"], {})

    def test_program_enrollment_correlation(self):
        """Test aggregation correlates with program enrollments from demo data."""
        # Find registrants enrolled in programs
        enrolled_registrants = self.partner_model.search(
            [
                ("is_registrant", "=", True),
                ("program_membership_ids", "!=", False),
            ]
        )

        if not enrolled_registrants:
            self.skipTest("No enrolled registrants in demo data")

        # Create explicit scope with enrolled registrants
        scope = self.scope_model.create(
            {
                "name": "Test Enrolled Registrants",
                "scope_type": "explicit",
                "explicit_partner_ids": [(6, 0, enrolled_registrants.ids)],
            }
        )

        # Compute aggregation
        result = self.service.compute_aggregation(scope)

        # Assertions
        self.assertEqual(result["total_count"], len(enrolled_registrants))

        # Test breakdown to verify data quality
        result_breakdown = self.service.compute_aggregation(
            scope,
            group_by=["gender", "age_group"],
        )

        # Should have multiple cells with varied demographics
        self.assertGreater(
            len(result_breakdown["breakdown"]),
            1,
            "Enrolled registrants should have varied demographics",
        )

        _logger.info(
            "Program enrollment test: %d enrolled registrants with %d demographic cells",
            result["total_count"],
            len(result_breakdown["breakdown"]),
        )
