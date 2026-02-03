# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestGISReport(TransactionCase):
    """Test the main GISReport model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set context to avoid job queue delay for faster tests
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                test_queue_job_no_delay=True,
            )
        )

        # Create test area hierarchy
        cls.area_country = cls.env["spp.area"].create(
            {
                "draft_name": "Test Country",
                "code": "TC",
                "area_level": 0,
            }
        )
        cls.area_region = cls.env["spp.area"].create(
            {
                "draft_name": "Test Region",
                "code": "TC-R1",
                "parent_id": cls.area_country.id,
                "area_level": 1,
                "area_sqkm": 1000.0,
                "population": 100000,
                "household_count": 20000,
            }
        )
        cls.area_district = cls.env["spp.area"].create(
            {
                "draft_name": "Test District",
                "code": "TC-R1-D1",
                "parent_id": cls.area_region.id,
                "area_level": 2,
                "area_sqkm": 500.0,
                "population": 50000,
                "household_count": 10000,
            }
        )

        # Create test registrants
        cls.registrant_individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_district.id,
            }
        )
        cls.registrant_group = cls.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_district.id,
            }
        )

        # Create test category
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "Test Category",
                "code": "test",
            }
        )

        # Get res.partner model reference
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    def test_01_create_report_basic(self):
        """Test creating a basic GIS report."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Test Report",
                "code": "test_report",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )
        self.assertTrue(report.exists())
        self.assertEqual(report.source_model, "res.partner")
        self.assertEqual(report.code, "test_report")
        self.assertEqual(report.base_area_level, 2)

    def test_02_create_report_with_template(self):
        """Test creating a report with template reference."""
        template = self.env["spp.gis.report.template"].create(
            {
                "name": "Test Template",
                "code": "test_template",
                "category_id": self.category.id,
                "config": {
                    "source_model": "res.partner",
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                },
            }
        )

        report = self.env["spp.gis.report"].create(
            {
                "name": "Report from Template",
                "code": "report_from_template",
                "category_id": self.category.id,
                "template_id": template.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )
        self.assertTrue(report.exists())
        self.assertEqual(report.template_id, template)

    def test_03_unique_code_constraint(self):
        """Test that report codes must be unique."""
        self.env["spp.gis.report"].create(
            {
                "name": "First Report",
                "code": "unique_code",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["spp.gis.report"].create(
                {
                    "name": "Second Report",
                    "code": "unique_code",  # Duplicate code
                    "category_id": self.category.id,
                    "source_model_id": self.partner_model.id,
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                    "normalization_method": "raw",
                    "base_area_level": 2,
                }
            )

    def test_04_normalize_raw(self):
        """Test raw normalization (no normalization)."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Raw Test",
                "code": "raw_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )
        normalized = report._normalize_value(100, self.area_region)
        self.assertEqual(normalized, 100)

    def test_05_normalize_per_sqkm(self):
        """Test per km² normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Density Test",
                "code": "density_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_area_sqkm",
                "base_area_level": 2,
            }
        )
        # Test normalization calculation
        normalized = report._normalize_value(100, self.area_region)
        self.assertEqual(normalized, 0.1)  # 100 / 1000 km²

        # Test with zero area - returns None because normalization is undefined
        area_zero = self.env["spp.area"].create(
            {
                "draft_name": "Zero Area",
                "code": "ZERO",
                "area_sqkm": 0,
            }
        )
        normalized_zero = report._normalize_value(100, area_zero)
        self.assertIsNone(normalized_zero)

    def test_06_normalize_per_population(self):
        """Test per population normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Per Capita Test",
                "code": "per_capita_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_population",
                "base_area_level": 2,
            }
        )
        normalized = report._normalize_value(1000, self.area_region)
        self.assertEqual(normalized, 10.0)  # 1000 / 100000 * 1000

        # Test with zero population - returns None because normalization is undefined
        area_zero = self.env["spp.area"].create(
            {
                "draft_name": "Zero Population",
                "code": "ZEROPOP",
                "population": 0,
            }
        )
        normalized_zero = report._normalize_value(100, area_zero)
        self.assertIsNone(normalized_zero)

    def test_07_normalize_per_household(self):
        """Test per household normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Per Household Test",
                "code": "per_household_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_household",
                "base_area_level": 2,
            }
        )
        normalized = report._normalize_value(2000, self.area_region)
        self.assertEqual(normalized, 10.0)  # 2000 / 20000 * 100

    def test_08_normalize_per_reference(self):
        """Test percentage of reference normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Percentage Test",
                "code": "percentage_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_reference",
                "base_area_level": 2,
            }
        )
        normalized = report._normalize_value(25, self.area_region, weight=100)
        self.assertEqual(normalized, 25.0)  # 25 / 100 * 100 = 25%

    def test_09_normalize_statistical_methods(self):
        """Test statistical normalization methods return None (post-processing)."""
        for method in ["index", "percentile", "zscore"]:
            report = self.env["spp.gis.report"].create(
                {
                    "name": f"Statistical Test {method}",
                    "code": f"statistical_{method}",
                    "category_id": self.category.id,
                    "source_model_id": self.partner_model.id,
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                    "normalization_method": method,
                    "base_area_level": 2,
                }
            )
            normalized = report._normalize_value(100, self.area_region)
            self.assertIsNone(normalized, f"Statistical method {method} should return None")

    def test_10_compute_data_count(self):
        """Test data count computation."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Data Count Test",
                "code": "data_count_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        # Initially no data
        self.assertEqual(report.data_count, 0)

        # Create some data records
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_region.id,
                "raw_value": 200,
                "normalized_value": 200,
            }
        )

        # Recompute
        report._compute_data_count()
        self.assertEqual(report.data_count, 2)

    def test_11_compute_is_stale_no_refresh(self):
        """Test is_stale when no last_refresh."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Stale Test",
                "code": "stale_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "refresh_interval": "daily",
            }
        )
        report._compute_is_stale()
        self.assertTrue(report.is_stale)

    def test_12_action_refresh(self):
        """Test refresh action returns notification."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Refresh Test",
                "code": "refresh_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )
        result = report.action_refresh()
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")

    def test_13_to_geojson_basic(self):
        """Test GeoJSON generation."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "GeoJSON Test",
                "code": "geojson_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        # Create some data
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )

        # Generate GeoJSON
        geojson = report._to_geojson(include_geometry=False)

        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertEqual(len(geojson["features"]), 1)
        self.assertIn("metadata", geojson)
        self.assertEqual(geojson["metadata"]["report"]["code"], "geojson_test")

    def test_14_to_geojson_filter_by_level(self):
        """Test GeoJSON generation filtered by admin level."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "GeoJSON Filter Test",
                "code": "geojson_filter_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        # Create data for multiple levels
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_region.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 50,
                "normalized_value": 50,
            }
        )

        # Filter to level 2 only
        geojson = report._to_geojson(admin_level=2, include_geometry=False)

        self.assertEqual(len(geojson["features"]), 1)
        self.assertEqual(geojson["features"][0]["properties"]["area_level"], 2)

    def test_15_to_geojson_filter_by_parent(self):
        """Test GeoJSON generation filtered by parent area."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "GeoJSON Parent Filter Test",
                "code": "geojson_parent_filter",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        # Create data for district (child of region)
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 50,
                "normalized_value": 50,
            }
        )

        # Filter to children of region
        geojson = report._to_geojson(
            parent_area_id=self.area_region.id, include_geometry=False
        )

        self.assertEqual(len(geojson["features"]), 1)
        self.assertEqual(
            geojson["features"][0]["properties"]["parent_area_id"], self.area_region.id
        )

    def test_16_get_summary_basic(self):
        """Test summary statistics generation."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Summary Test",
                "code": "summary_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        # Create data
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )
        self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_region.id,
                "raw_value": 200,
                "normalized_value": 200,
            }
        )

        # Get summary
        summary = report._get_summary()

        self.assertEqual(summary["report_id"], report.id)
        self.assertEqual(summary["area_count"], 2)
        self.assertEqual(summary["summary"]["total_raw_value"], 300)
        self.assertEqual(summary["summary"]["min_raw"], 100)
        self.assertEqual(summary["summary"]["max_raw"], 200)

    def test_17_get_summary_empty(self):
        """Test summary with no data."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Empty Summary Test",
                "code": "empty_summary_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        summary = report._get_summary()

        self.assertEqual(summary["area_count"], 0)
        self.assertEqual(summary["summary"], {})

    def test_18_color_scheme_options(self):
        """Test different color scheme options."""
        # Test that reports can use different color schemes
        color_schemes = self.env["spp.gis.color.scheme"].search([])
        self.assertTrue(len(color_schemes) > 0, "Color schemes should be available")

        # Get default scheme
        default_scheme = self.env["spp.gis.color.scheme"].get_default_scheme()
        self.assertTrue(default_scheme, "Default color scheme should exist")

        # Create report with specific color scheme
        viridis_scheme = self.env["spp.gis.color.scheme"].search(
            [("code", "=", "viridis")], limit=1
        )
        if viridis_scheme:
            report = self.env["spp.gis.report"].create(
                {
                    "name": "Color Scheme Test",
                    "code": "color_viridis_test",
                    "category_id": self.category.id,
                    "source_model_id": self.partner_model.id,
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                    "normalization_method": "raw",
                    "base_area_level": 2,
                    "color_scheme_id": viridis_scheme.id,
                }
            )
            self.assertEqual(report.color_scheme_id, viridis_scheme)

    def test_19_threshold_modes(self):
        """Test different threshold mode options."""
        for mode in [
            "auto_quartile",
            "auto_equal",
            "auto_jenks",
            "auto_stddev",
            "manual",
        ]:
            report = self.env["spp.gis.report"].create(
                {
                    "name": f"Threshold Mode {mode}",
                    "code": f"threshold_{mode}",
                    "category_id": self.category.id,
                    "source_model_id": self.partner_model.id,
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                    "normalization_method": "raw",
                    "base_area_level": 2,
                    "threshold_mode": mode,
                }
            )
            self.assertEqual(report.threshold_mode, mode)

    def test_20_active_flag(self):
        """Test active flag for archiving reports."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Active Test",
                "code": "active_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "active": True,
            }
        )
        self.assertTrue(report.active)

        # Archive the report
        report.active = False
        self.assertFalse(report.active)

        # Should not appear in default search
        active_reports = self.env["spp.gis.report"].search([("code", "=", "active_test")])
        self.assertEqual(len(active_reports), 0)

        # Should appear when searching with active_test=False
        inactive_reports = self.env["spp.gis.report"].with_context(
            active_test=False
        ).search([("code", "=", "active_test")])
        self.assertEqual(len(inactive_reports), 1)
