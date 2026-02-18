# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestGISReportData(TransactionCase):
    """Test computed data and thresholds for GIS reports."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set context to avoid job queue delay for faster tests
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                queue_job__no_delay=True,
            )
        )

        # Create test areas
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

        # Create test report
        cls.report = cls.env["spp.gis.report"].create(
            {
                "name": "Test Report",
                "code": "test_report",
                "category_id": cls.category.id,
                "source_model_id": cls.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "refresh_interval": "daily",
            }
        )

    def test_01_create_data_record(self):
        """Test creating a data record."""
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "record_count": 100,
            }
        )
        self.assertTrue(data.exists())
        self.assertEqual(data.raw_value, 100)
        self.assertEqual(data.normalized_value, 100)

    def test_02_unique_report_area_constraint(self):
        """Test that report+area combination must be unique."""
        self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )

        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.env["spp.gis.report.data"].create(
                {
                    "report_id": self.report.id,
                    "area_id": self.area_district.id,  # Duplicate
                    "raw_value": 200,
                    "normalized_value": 200,
                }
            )

    def test_03_denormalized_area_fields(self):
        """Test that area metadata is denormalized correctly."""
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )

        # Related fields should be auto-populated
        self.assertEqual(data.area_code, self.area_district.code)
        self.assertEqual(data.area_name, self.area_district.name)
        self.assertEqual(data.area_level, self.area_district.area_level)
        self.assertEqual(data.parent_area_id, self.area_district.parent_id)

    def test_04_display_value_raw(self):
        """Test display value formatting for raw normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Raw Display Test",
                "code": "raw_display",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 1234.5,
                "normalized_value": 1234.5,
            }
        )

        # Should format as integer with thousands separator
        self.assertEqual(data.display_value, "1,234")

    def test_05_display_value_per_sqkm(self):
        """Test display value formatting for per km² normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Per km² Display Test",
                "code": "per_sqkm_display",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_area_sqkm",
                "base_area_level": 2,
            }
        )

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 0.2,
            }
        )

        self.assertEqual(data.display_value, "0.20 per km²")

    def test_06_display_value_per_population(self):
        """Test display value formatting for per population normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Per Population Display Test",
                "code": "per_pop_display",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_population",
                "base_area_level": 2,
            }
        )

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 2.0,
            }
        )

        self.assertEqual(data.display_value, "2.0 per 1,000")

    def test_07_display_value_per_household(self):
        """Test display value formatting for per household normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Per Household Display Test",
                "code": "per_hh_display",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_household",
                "base_area_level": 2,
            }
        )

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 5.0,
            }
        )

        self.assertEqual(data.display_value, "5.0 per 100")

    def test_08_display_value_percentage(self):
        """Test display value formatting for percentage normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Percentage Display Test",
                "code": "percentage_display",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "per_reference",
                "base_area_level": 2,
            }
        )

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 25,
                "normalized_value": 25.0,
            }
        )

        self.assertEqual(data.display_value, "25.0%")

    def test_09_display_value_zscore(self):
        """Test display value formatting for z-score normalization."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Z-Score Display Test",
                "code": "zscore_display",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "zscore",
                "base_area_level": 2,
            }
        )

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 1.5,
            }
        )

        self.assertEqual(data.display_value, "+1.50σ")

    def test_10_is_stale_no_computed_at(self):
        """Test is_stale when computed_at is not set."""
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )
        # Clear computed_at
        data.write({"computed_at": False})
        data._compute_is_stale()
        self.assertTrue(data.is_stale)

    def test_11_is_stale_hourly_fresh(self):
        """Test is_stale for hourly refresh - fresh data."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Hourly Test",
                "code": "hourly_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "refresh_interval": "hourly",
            }
        )

        # Create data computed 30 minutes ago (fresh)
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "computed_at": fields.Datetime.now() - timedelta(minutes=30),
            }
        )
        data._compute_is_stale()
        self.assertFalse(data.is_stale)

    def test_12_is_stale_hourly_stale(self):
        """Test is_stale for hourly refresh - stale data."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Hourly Stale Test",
                "code": "hourly_stale_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "refresh_interval": "hourly",
            }
        )

        # Create data computed 2 hours ago (stale)
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "computed_at": fields.Datetime.now() - timedelta(hours=2),
            }
        )
        data._compute_is_stale()
        self.assertTrue(data.is_stale)

    def test_13_is_stale_daily_fresh(self):
        """Test is_stale for daily refresh - fresh data."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Daily Test",
                "code": "daily_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "refresh_interval": "daily",
            }
        )

        # Create data computed 12 hours ago (fresh)
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "computed_at": fields.Datetime.now() - timedelta(hours=12),
            }
        )
        data._compute_is_stale()
        self.assertFalse(data.is_stale)

    def test_14_is_stale_daily_stale(self):
        """Test is_stale for daily refresh - stale data."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Daily Stale Test",
                "code": "daily_stale_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "refresh_interval": "daily",
            }
        )

        # Create data computed 2 days ago (stale)
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "computed_at": fields.Datetime.now() - timedelta(days=2),
            }
        )
        data._compute_is_stale()
        self.assertTrue(data.is_stale)

    def test_15_is_stale_weekly(self):
        """Test is_stale for weekly refresh."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Weekly Test",
                "code": "weekly_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "refresh_interval": "weekly",
            }
        )

        # Create data computed 3 days ago (fresh)
        data_fresh = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "computed_at": fields.Datetime.now() - timedelta(days=3),
            }
        )
        data_fresh._compute_is_stale()
        self.assertFalse(data_fresh.is_stale)

        # Create data computed 8 days ago (stale)
        data_stale = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_region.id,
                "raw_value": 200,
                "normalized_value": 200,
                "computed_at": fields.Datetime.now() - timedelta(days=8),
            }
        )
        data_stale._compute_is_stale()
        self.assertTrue(data_stale.is_stale)

    def test_16_rollup_metadata(self):
        """Test rollup metadata fields."""
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_region.id,
                "raw_value": 100,
                "normalized_value": 100,
                "is_rollup": True,
                "source_area_count": 5,
            }
        )

        self.assertTrue(data.is_rollup)
        self.assertEqual(data.source_area_count, 5)

    def test_17_bucket_assignment(self):
        """Test threshold bucket assignment."""
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "bucket_index": 2,
                "bucket_color": "#FFA500",
                "bucket_label": "Medium",
            }
        )

        self.assertEqual(data.bucket_index, 2)
        self.assertEqual(data.bucket_color, "#FFA500")
        self.assertEqual(data.bucket_label, "Medium")

    def test_18_disaggregation_data(self):
        """Test disaggregation data storage."""
        disagg_data = {
            "gender": {"male": 580, "female": 670},
            "age_group": {"0-17": 450, "18-59": 600, "60+": 200},
        }

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_district.id,
                "raw_value": 1250,
                "normalized_value": 1250,
                "disaggregation": disagg_data,
            }
        )

        self.assertEqual(data.disaggregation, disagg_data)
        self.assertEqual(data.disaggregation["gender"]["male"], 580)
        self.assertEqual(data.disaggregation["age_group"]["60+"], 200)

    def test_19_weight_field(self):
        """Test weight/denominator field for calculations."""
        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
                "weight": 500.0,
            }
        )

        self.assertEqual(data.weight, 500.0)

    def test_20_cascade_delete(self):
        """Test that deleting report cascades to data records."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "Cascade Test",
                "code": "cascade_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
            }
        )

        data = self.env["spp.gis.report.data"].create(
            {
                "report_id": report.id,
                "area_id": self.area_district.id,
                "raw_value": 100,
                "normalized_value": 100,
            }
        )

        data_id = data.id
        self.assertTrue(data.exists())

        # Delete report
        report.unlink()

        # Data should be deleted too
        data_exists = self.env["spp.gis.report.data"].search([("id", "=", data_id)])
        self.assertFalse(data_exists)
