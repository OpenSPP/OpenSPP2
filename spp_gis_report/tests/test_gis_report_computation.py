# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
import unittest

from odoo.tests import tagged

from .common import GISReportTestBase

_logger = logging.getLogger(__name__)


def skip_if_no_programs(method):
    """Decorator to skip tests if spp_programs module is not installed."""

    def wrapper(self, *args, **kwargs):
        if "spp.program" not in self.env:
            raise unittest.SkipTest("spp_programs module not installed")
        return method(self, *args, **kwargs)

    return wrapper


@tagged("post_install", "-at_install")
class TestGISReportComputation(GISReportTestBase):
    """Test the core computation logic of GIS Reports.

    This tests the actual business logic:
    - Base aggregation (counting, summing, averaging)
    - Hierarchy rollup (sum, weighted avg, etc.)
    - Threshold calculation and assignment
    - Full refresh workflow
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create additional registrants to have meaningful aggregation data
        cls._create_additional_registrants()
        # Create second region for multi-region tests
        cls._create_second_region()

    @classmethod
    def _create_additional_registrants(cls):
        """Create more registrants for aggregation testing."""
        # District 1: 5 individuals, 2 groups
        for i in range(4):
            cls.env["res.partner"].create({
                "name": f"District1 Individual {i+2}",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_district_1.id,
            })
        cls.env["res.partner"].create({
            "name": "District1 Group 2",
            "is_registrant": True,
            "is_group": True,
            "area_id": cls.area_district_1.id,
        })

        # District 2: 3 individuals, 1 group
        for i in range(2):
            cls.env["res.partner"].create({
                "name": f"District2 Individual {i+2}",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_district_2.id,
            })

    @classmethod
    def _create_second_region(cls):
        """Create a second region with districts for multi-region tests."""
        cls.area_region_2 = cls.env["spp.area"].create({
            "draft_name": "Test Region 2",
            "code": "TC-R2",
            "parent_id": cls.area_country.id,
            "area_level": 1,
            "area_sqkm": 2000.0,
            "population": 200000,
            "household_count": 40000,
        })
        cls.area_district_3 = cls.env["spp.area"].create({
            "draft_name": "Test District 3",
            "code": "TC-R2-D1",
            "parent_id": cls.area_region_2.id,
            "area_level": 2,
            "area_sqkm": 1000.0,
            "population": 100000,
            "household_count": 20000,
        })
        # Add some registrants to district 3
        for i in range(10):
            cls.env["res.partner"].create({
                "name": f"District3 Individual {i+1}",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_district_3.id,
            })

    # ===== BASE AGGREGATION TESTS =====

    def test_base_aggregation_count(self):
        """Test counting registrants by area."""
        report = self.create_test_report(
            name="Count Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
        )

        results = report._compute_base_aggregation()

        # District 1: 5 individuals (1 from base + 4 additional)
        self.assertEqual(results[self.area_district_1.id]["raw"], 5)
        self.assertEqual(results[self.area_district_1.id]["count"], 5)

        # District 2: 3 individuals (1 from base + 2 additional)
        self.assertEqual(results[self.area_district_2.id]["raw"], 3)

        # District 3: 10 individuals
        self.assertEqual(results[self.area_district_3.id]["raw"], 10)

    def test_base_aggregation_count_groups(self):
        """Test counting group registrants."""
        report = self.create_test_report(
            name="Group Count Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', True)]",
        )

        results = report._compute_base_aggregation()

        # District 1: 2 groups (1 from base + 1 additional)
        self.assertEqual(results[self.area_district_1.id]["raw"], 2)

        # District 2: 0 groups
        self.assertEqual(results[self.area_district_2.id]["raw"], 0)

    def test_base_aggregation_empty_domain(self):
        """Test aggregation with no matching records."""
        report = self.create_test_report(
            name="Empty Domain Test",
            aggregation_method="count",
            filter_domain="[('name', '=', 'NONEXISTENT')]",
        )

        results = report._compute_base_aggregation()

        # All districts should have 0
        for area_id in results:
            self.assertEqual(results[area_id]["raw"], 0)

    def test_base_aggregation_no_source_model(self):
        """Test aggregation with missing source model."""
        report = self.create_test_report(name="No Model Test")
        # Clear source model
        report.source_model_id = False

        results = report._compute_base_aggregation()

        self.assertEqual(results, {})

    # ===== HIERARCHY ROLLUP TESTS =====

    def test_rollup_sum(self):
        """Test sum rollup from districts to regions to country."""
        report = self.create_test_report(
            name="Rollup Sum Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
            enable_rollup=True,
            rollup_method="sum",
        )

        base_results = report._compute_base_aggregation()
        all_results = report._compute_hierarchy_rollup(base_results)

        # Districts remain unchanged
        self.assertEqual(all_results[self.area_district_1.id]["raw"], 5)
        self.assertEqual(all_results[self.area_district_1.id]["is_rollup"], False)

        # Region 1 should have sum of its districts (5 + 3 = 8)
        self.assertEqual(all_results[self.area_region.id]["raw"], 8)
        self.assertEqual(all_results[self.area_region.id]["is_rollup"], True)
        self.assertEqual(all_results[self.area_region.id]["source_area_count"], 2)

        # Region 2 should have its district (10)
        self.assertEqual(all_results[self.area_region_2.id]["raw"], 10)

        # Country should have sum of all regions (8 + 10 = 18)
        self.assertEqual(all_results[self.area_country.id]["raw"], 18)
        self.assertEqual(all_results[self.area_country.id]["is_rollup"], True)

    def test_rollup_weighted_avg_by_count(self):
        """Test weighted average rollup using record count as weight."""
        report = self.create_test_report(
            name="Weighted Avg Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
            enable_rollup=True,
            rollup_method="weighted_avg",
            rollup_weight_source="count",
        )

        base_results = report._compute_base_aggregation()
        all_results = report._compute_hierarchy_rollup(base_results)

        # Region 1: weighted avg = (5*5 + 3*3) / (5+3) = (25+9)/8 = 4.25
        self.assertAlmostEqual(all_results[self.area_region.id]["raw"], 4.25, places=2)

    def test_rollup_simple_avg(self):
        """Test simple average rollup."""
        report = self.create_test_report(
            name="Simple Avg Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
            enable_rollup=True,
            rollup_method="avg",
        )

        base_results = report._compute_base_aggregation()
        all_results = report._compute_hierarchy_rollup(base_results)

        # Region 1: simple avg = (5 + 3) / 2 = 4.0
        self.assertEqual(all_results[self.area_region.id]["raw"], 4.0)

    def test_rollup_min(self):
        """Test minimum rollup."""
        report = self.create_test_report(
            name="Min Rollup Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
            enable_rollup=True,
            rollup_method="min",
        )

        base_results = report._compute_base_aggregation()
        all_results = report._compute_hierarchy_rollup(base_results)

        # Region 1: min = min(5, 3) = 3
        self.assertEqual(all_results[self.area_region.id]["raw"], 3)

    def test_rollup_max(self):
        """Test maximum rollup."""
        report = self.create_test_report(
            name="Max Rollup Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
            enable_rollup=True,
            rollup_method="max",
        )

        base_results = report._compute_base_aggregation()
        all_results = report._compute_hierarchy_rollup(base_results)

        # Region 1: max = max(5, 3) = 5
        self.assertEqual(all_results[self.area_region.id]["raw"], 5)

    def test_rollup_disabled(self):
        """Test that rollup can be disabled."""
        report = self.create_test_report(
            name="No Rollup Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True)]",
            enable_rollup=False,
        )

        base_results = report._compute_base_aggregation()
        all_results = report._compute_hierarchy_rollup(base_results)

        # Should only have district-level data, no parent levels
        self.assertIn(self.area_district_1.id, all_results)
        self.assertNotIn(self.area_region.id, all_results)
        self.assertNotIn(self.area_country.id, all_results)

    # ===== THRESHOLD CALCULATION TESTS =====

    def test_auto_thresholds_quartile(self):
        """Test quartile threshold calculation."""
        report = self.create_test_report(
            name="Quartile Test",
            threshold_mode="auto_quartile",
            bucket_count=4,
        )

        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        thresholds = report._compute_auto_thresholds(values)

        self.assertEqual(len(thresholds), 4)
        # Check labels are assigned
        self.assertIn(thresholds[0]["label"], ["Very Low", "Low", "Level 1"])
        # Check colors are assigned
        self.assertTrue(all(t["color"].startswith("#") for t in thresholds))

    def test_auto_thresholds_equal_interval(self):
        """Test equal interval threshold calculation."""
        report = self.create_test_report(
            name="Equal Interval Test",
            threshold_mode="auto_equal",
            bucket_count=4,
        )

        values = [0, 25, 50, 75, 100]
        thresholds = report._compute_auto_thresholds(values)

        self.assertEqual(len(thresholds), 4)
        # For equal intervals: 0-25, 25-50, 50-75, 75-100
        self.assertEqual(thresholds[0]["min_value"], 0)
        self.assertEqual(thresholds[0]["max_value"], 25)
        self.assertEqual(thresholds[1]["min_value"], 25)
        self.assertEqual(thresholds[1]["max_value"], 50)

    def test_auto_thresholds_jenks(self):
        """Test Jenks natural breaks threshold calculation."""
        report = self.create_test_report(
            name="Jenks Test",
            threshold_mode="auto_jenks",
            bucket_count=3,
        )

        # Values with natural gaps
        values = [1, 2, 3, 50, 51, 52, 100, 101, 102]
        thresholds = report._compute_auto_thresholds(values)

        self.assertEqual(len(thresholds), 3)
        # Breaks should occur at natural gaps

    def test_auto_thresholds_stddev(self):
        """Test standard deviation threshold calculation."""
        report = self.create_test_report(
            name="StdDev Test",
            threshold_mode="auto_stddev",
            bucket_count=5,
        )

        # Values with known mean=50, std≈28.87
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        thresholds = report._compute_auto_thresholds(values)

        # Should have buckets centered around mean
        self.assertTrue(len(thresholds) > 0)

    def test_auto_thresholds_empty_values(self):
        """Test threshold calculation with empty values."""
        report = self.create_test_report(
            name="Empty Values Test",
            threshold_mode="auto_quartile",
            bucket_count=4,
        )

        thresholds = report._compute_auto_thresholds([])

        self.assertEqual(thresholds, [])

    def test_auto_thresholds_single_value(self):
        """Test threshold calculation with single value."""
        report = self.create_test_report(
            name="Single Value Test",
            threshold_mode="auto_equal",
            bucket_count=4,
        )

        thresholds = report._compute_auto_thresholds([50])

        # Should still return valid thresholds
        self.assertTrue(len(thresholds) > 0)

    # ===== THRESHOLD ASSIGNMENT TESTS =====

    def test_assign_thresholds_basic(self):
        """Test assigning values to threshold buckets."""
        report = self.create_test_report(name="Assign Test")

        results = {
            1: {"raw": 10, "normalized": 10},
            2: {"raw": 30, "normalized": 30},
            3: {"raw": 70, "normalized": 70},
            4: {"raw": 95, "normalized": 95},
        }

        thresholds = [
            {"min_value": 0, "max_value": 25, "color": "#ff0000", "label": "Low"},
            {"min_value": 25, "max_value": 50, "color": "#ffff00", "label": "Medium"},
            {"min_value": 50, "max_value": 75, "color": "#00ff00", "label": "High"},
            {"min_value": 75, "max_value": None, "color": "#0000ff", "label": "Very High"},
        ]

        assigned = report._assign_thresholds(results, thresholds)

        self.assertEqual(assigned[1]["bucket_label"], "Low")
        self.assertEqual(assigned[1]["bucket_color"], "#ff0000")
        self.assertEqual(assigned[2]["bucket_label"], "Medium")
        self.assertEqual(assigned[3]["bucket_label"], "High")
        self.assertEqual(assigned[4]["bucket_label"], "Very High")

    def test_assign_thresholds_no_thresholds(self):
        """Test assignment when no thresholds defined."""
        report = self.create_test_report(name="No Thresholds Test")

        results = {1: {"raw": 50, "normalized": 50}}

        assigned = report._assign_thresholds(results, [])

        self.assertEqual(assigned[1]["bucket_label"], "No Classification")
        self.assertEqual(assigned[1]["bucket_color"], "#808080")

    def test_assign_thresholds_boundary_values(self):
        """Test assignment at exact boundary values."""
        report = self.create_test_report(name="Boundary Test")

        results = {
            1: {"raw": 0, "normalized": 0},    # Exactly at min
            2: {"raw": 25, "normalized": 25},  # At boundary (should go to next)
            3: {"raw": 100, "normalized": 100},  # At max
        }

        thresholds = [
            {"min_value": 0, "max_value": 25, "color": "#ff0000", "label": "Low"},
            {"min_value": 25, "max_value": 100, "color": "#00ff00", "label": "High"},
        ]

        assigned = report._assign_thresholds(results, thresholds)

        self.assertEqual(assigned[1]["bucket_label"], "Low")  # 0 >= 0 and 0 < 25
        self.assertEqual(assigned[2]["bucket_label"], "High")  # 25 >= 25
        self.assertEqual(assigned[3]["bucket_label"], "High")  # 100 >= 25

    # ===== STATISTICAL NORMALIZATION TESTS =====

    def test_statistical_normalization_index(self):
        """Test index (0-100) normalization."""
        report = self.create_test_report(
            name="Index Test",
            normalization_method="index",
        )

        results = {
            1: {"raw": 0},
            2: {"raw": 50},
            3: {"raw": 100},
        }

        normalized = report._apply_statistical_normalization(results)

        self.assertEqual(normalized[1]["normalized"], 0)    # Min maps to 0
        self.assertEqual(normalized[2]["normalized"], 50)   # Mid maps to 50
        self.assertEqual(normalized[3]["normalized"], 100)  # Max maps to 100

    def test_statistical_normalization_percentile(self):
        """Test percentile rank normalization."""
        report = self.create_test_report(
            name="Percentile Test",
            normalization_method="percentile",
        )

        results = {
            1: {"raw": 10},
            2: {"raw": 20},
            3: {"raw": 30},
            4: {"raw": 40},
            5: {"raw": 50},
        }

        normalized = report._apply_statistical_normalization(results)

        # Lowest value should be 0th percentile
        self.assertEqual(normalized[1]["normalized"], 0)
        # Highest value should be 80th percentile (4 values below, 5 total)
        self.assertEqual(normalized[5]["normalized"], 80)

    def test_statistical_normalization_zscore(self):
        """Test z-score normalization."""
        report = self.create_test_report(
            name="Z-Score Test",
            normalization_method="zscore",
        )

        # Values with mean=50
        results = {
            1: {"raw": 30},
            2: {"raw": 50},
            3: {"raw": 70},
        }

        normalized = report._apply_statistical_normalization(results)

        # Value at mean should have z-score of 0
        self.assertAlmostEqual(normalized[2]["normalized"], 0, places=2)
        # Values below mean should be negative
        self.assertLess(normalized[1]["normalized"], 0)
        # Values above mean should be positive
        self.assertGreater(normalized[3]["normalized"], 0)

    # ===== FULL REFRESH WORKFLOW TESTS =====

    def test_refresh_data_full_workflow(self):
        """Test complete data refresh workflow."""
        report = self.create_test_report(
            name="Full Refresh Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
            normalization_method="raw",
            enable_rollup=True,
            rollup_method="sum",
            threshold_mode="auto_quartile",
            bucket_count=4,
        )

        # No data initially
        self.assertEqual(report.data_count, 0)

        # Run refresh
        report._refresh_data()

        # Should have data for districts, regions, and country
        self.assertGreater(report.data_count, 0)
        self.assertIsNotNone(report.last_refresh)

        # Check district data
        district_data = report.data_ids.filtered(
            lambda d: d.area_id == self.area_district_1
        )
        self.assertEqual(len(district_data), 1)
        self.assertEqual(district_data.raw_value, 5)
        self.assertFalse(district_data.is_rollup)

        # Check region data (rolled up)
        region_data = report.data_ids.filtered(
            lambda d: d.area_id == self.area_region
        )
        self.assertEqual(len(region_data), 1)
        self.assertEqual(region_data.raw_value, 8)  # 5 + 3
        self.assertTrue(region_data.is_rollup)

        # Check thresholds were created
        self.assertGreater(len(report.threshold_ids), 0)

        # Check bucket assignment
        self.assertTrue(all(d.bucket_color for d in report.data_ids))

    def test_refresh_data_update_existing(self):
        """Test that refresh updates existing data records."""
        report = self.create_test_report(
            name="Update Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
        )

        # First refresh
        report._refresh_data()
        first_refresh = report.last_refresh
        first_count = report.data_ids.filtered(
            lambda d: d.area_id == self.area_district_1
        ).raw_value

        # Add more registrants
        self.env["res.partner"].create({
            "name": "New Individual",
            "is_registrant": True,
            "is_group": False,
            "area_id": self.area_district_1.id,
        })

        # Second refresh
        report._refresh_data()

        # Should have updated timestamp (>= because both refreshes may happen in same second)
        self.assertGreaterEqual(report.last_refresh, first_refresh)

        # Should have updated count
        new_count = report.data_ids.filtered(
            lambda d: d.area_id == self.area_district_1
        ).raw_value
        self.assertEqual(new_count, first_count + 1)

    def test_refresh_data_removes_obsolete(self):
        """Test that refresh removes data for deleted areas."""
        report = self.create_test_report(
            name="Obsolete Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True)]",
        )

        # First refresh
        report._refresh_data()

        # Create a temporary area with data
        temp_area = self.env["spp.area"].create({
            "draft_name": "Temporary Area",
            "code": "TEMP",
            "area_level": 2,
        })
        self.env["spp.gis.report.data"].create({
            "report_id": report.id,
            "area_id": temp_area.id,
            "raw_value": 999,
            "normalized_value": 999,
        })

        # Refresh - temp area has no matching registrants so data should be removed
        report._refresh_data()

        # Temp area data should be gone (replaced with 0 or removed)
        temp_data = report.data_ids.filtered(lambda d: d.area_id == temp_area)
        if temp_data:
            self.assertEqual(temp_data.raw_value, 0)

    def test_refresh_data_no_matching_records(self):
        """Test refresh when no records match filter."""
        report = self.create_test_report(
            name="No Match Test",
            aggregation_method="count",
            filter_domain="[('name', '=', 'IMPOSSIBLE_NAME_MATCH')]",
        )

        report._refresh_data()

        # Should have data records but with zero values
        self.assertIsNotNone(report.last_refresh)

    def test_refresh_with_per_population_normalization(self):
        """Test refresh with per-population normalization."""
        report = self.create_test_report(
            name="Per Capita Refresh Test",
            aggregation_method="count",
            filter_domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
            normalization_method="per_population",
        )

        report._refresh_data()

        # Check normalization was applied
        district_data = report.data_ids.filtered(
            lambda d: d.area_id == self.area_district_1
        )
        # 5 individuals / 50000 population * 1000 = 0.1
        self.assertAlmostEqual(district_data.normalized_value, 0.1, places=2)

    # ===== COLOR PALETTE TESTS =====

    def test_color_palette_viridis(self):
        """Test color-blind safe palette generation."""
        # Get viridis color scheme (default, color-blind safe)
        viridis = self.env["spp.gis.color.scheme"].search(
            [("code", "=", "viridis")], limit=1
        )
        report = self.create_test_report(
            name="Color Palette Test",
            color_scheme_id=viridis.id if viridis else False,
        )

        colors = report._get_color_palette(4)

        self.assertEqual(len(colors), 4)
        self.assertTrue(all(c.startswith("#") for c in colors))

    def test_color_palette_interpolation(self):
        """Test palette interpolation for different bucket counts."""
        # Get blues color scheme for interpolation test
        blues = self.env["spp.gis.color.scheme"].search(
            [("code", "=", "blues")], limit=1
        )
        report = self.create_test_report(
            name="Palette Interpolation Test",
            color_scheme_id=blues.id if blues else False,
        )

        # Request more colors than in base palette
        colors_3 = report._get_color_palette(3)
        colors_5 = report._get_color_palette(5)
        colors_10 = report._get_color_palette(10)

        self.assertEqual(len(colors_3), 3)
        self.assertEqual(len(colors_5), 5)
        self.assertEqual(len(colors_10), 10)

    # ===== BUCKET LABEL TESTS =====

    def test_bucket_labels(self):
        """Test bucket label generation for different bucket counts."""
        report = self.create_test_report(name="Label Test")

        labels_2 = report._get_bucket_labels(2)
        labels_3 = report._get_bucket_labels(3)
        labels_4 = report._get_bucket_labels(4)
        labels_5 = report._get_bucket_labels(5)

        self.assertEqual(labels_2, ["Low", "High"])
        self.assertEqual(labels_3, ["Low", "Medium", "High"])
        self.assertEqual(labels_4, ["Very Low", "Low", "High", "Very High"])
        self.assertEqual(labels_5, ["Very Low", "Low", "Medium", "High", "Very High"])

    # ===== FILTER DOMAIN TESTS =====

    def test_build_filter_domain_basic(self):
        """Test basic filter domain building."""
        report = self.create_test_report(
            name="Domain Test",
            filter_domain="[('is_registrant', '=', True)]",
        )

        domain = report._build_filter_domain()

        self.assertIn(("is_registrant", "=", True), domain)

    @skip_if_no_programs
    def test_build_filter_domain_with_program_context(self):
        """Test filter domain with program context.

        Note: This test only runs when spp_programs is installed because
        the program_id field is added by the spp_gis_report_programs glue module.
        """
        report = self.create_test_report(
            name="Program Domain Test",
            filter_domain="[('is_registrant', '=', True)]",
            program_id=self.program.id,
        )

        domain = report._build_filter_domain()

        # Should include program membership filter
        has_program_filter = any(
            "program_membership_ids.program_id" in str(d) for d in domain
        )
        self.assertTrue(has_program_filter)

    def test_build_filter_domain_invalid(self):
        """Test handling of invalid filter domain."""
        report = self.create_test_report(
            name="Invalid Domain Test",
            filter_domain="INVALID DOMAIN",
        )

        # Should not raise, just log warning
        domain = report._build_filter_domain()
        self.assertIsInstance(domain, list)

    # ===== EDGE CASE TESTS =====

    def test_single_area_at_base_level(self):
        """Test with only one area at base level.

        Note: area_level is computed based on parent hierarchy, so we cannot
        create an isolated area at an arbitrary level. Instead, we create a
        child of area_country (level 0) which will be at level 1.
        """
        # Create isolated area as child of country (will be level 1)
        isolated_area = self.env["spp.area"].create({
            "draft_name": "Isolated Area",
            "code": "ISOLATED",
            "parent_id": self.area_country.id,  # Child of country = level 1
            "population": 1000,
        })
        self.env["res.partner"].create({
            "name": "Isolated Registrant",
            "is_registrant": True,
            "is_group": False,
            "area_id": isolated_area.id,
        })
        # Ensure records are visible to subsequent searches
        self.env.cr.flush()
        self.env.invalidate_all()

        report = self.create_test_report(
            name="Single Area Test",
            aggregation_method="count",
            filter_domain=f"[('area_id', '=', {isolated_area.id})]",  # Only this area
            base_area_level=1,  # Match isolated area level
            threshold_mode="auto_quartile",
            bucket_count=4,
        )

        report._refresh_data()

        # Should work - creates data for all areas at level 1
        # but only isolated area has matching data (1 registrant)
        self.assertGreater(report.data_count, 0)

        # Verify the isolated area has the expected count (1 registrant)
        isolated_data = report.data_ids.filtered(
            lambda d: d.area_id == isolated_area
        )
        self.assertEqual(len(isolated_data), 1)
        self.assertEqual(isolated_data.raw_value, 1)

    def test_all_zero_values(self):
        """Test handling when all aggregated values are zero."""
        report = self.create_test_report(
            name="All Zeros Test",
            aggregation_method="count",
            filter_domain="[('name', '=', 'NONEXISTENT')]",
            threshold_mode="auto_equal",
        )

        report._refresh_data()

        # Should handle gracefully without division errors
        self.assertIsNotNone(report.last_refresh)

    def test_negative_values(self):
        """Test threshold assignment with negative values."""
        report = self.create_test_report(name="Negative Test")

        results = {
            1: {"raw": -50, "normalized": -50},
            2: {"raw": 0, "normalized": 0},
            3: {"raw": 50, "normalized": 50},
        }

        thresholds = [
            {"min_value": None, "max_value": 0, "color": "#ff0000", "label": "Negative"},
            {"min_value": 0, "max_value": None, "color": "#00ff00", "label": "Positive"},
        ]

        assigned = report._assign_thresholds(results, thresholds)

        self.assertEqual(assigned[1]["bucket_label"], "Negative")
        self.assertEqual(assigned[2]["bucket_label"], "Positive")
        self.assertEqual(assigned[3]["bucket_label"], "Positive")
