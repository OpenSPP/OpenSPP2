# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields
from odoo.tests import TransactionCase

_logger = logging.getLogger(__name__)


class GISReportTestBase(TransactionCase):
    """Base test class for GIS Report tests with common setup."""

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
        cls._create_test_areas()

        # Create test registrants
        cls._create_test_registrants()

        # Create test program (only if spp_programs module is installed)
        cls._create_test_program_if_available()

        # Create test category and template
        cls._create_test_category_and_template()

        # Get model references
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)

    @classmethod
    def _create_test_areas(cls):
        """Create test area hierarchy: country -> region -> district."""
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
        cls.area_district_1 = cls.env["spp.area"].create(
            {
                "draft_name": "Test District 1",
                "code": "TC-R1-D1",
                "parent_id": cls.area_region.id,
                "area_level": 2,
                "area_sqkm": 500.0,
                "population": 50000,
                "household_count": 10000,
            }
        )
        cls.area_district_2 = cls.env["spp.area"].create(
            {
                "draft_name": "Test District 2",
                "code": "TC-R1-D2",
                "parent_id": cls.area_region.id,
                "area_level": 2,
                "area_sqkm": 500.0,
                "population": 50000,
                "household_count": 10000,
            }
        )

    @classmethod
    def _create_test_registrants(cls):
        """Create test registrant individuals and groups."""
        cls.registrant_individual_1 = cls.env["res.partner"].create(
            {
                "name": "Test Individual 1",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_district_1.id,
            }
        )
        cls.registrant_individual_2 = cls.env["res.partner"].create(
            {
                "name": "Test Individual 2",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_district_2.id,
            }
        )
        cls.registrant_group = cls.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_district_1.id,
            }
        )

    @classmethod
    def _create_test_program_if_available(cls):
        """Create test program with cycle if spp_programs module is installed."""
        cls.program = None
        cls.cycle = None

        # Check if spp.program model exists (module installed)
        if "spp.program" not in cls.env:
            _logger.info("spp_programs not installed, skipping program test data")
            return

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Test Program",
            }
        )
        cls.cycle = cls.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": cls.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.add(fields.Date.today(), days=30),
            }
        )

    @classmethod
    def _create_test_category_and_template(cls):
        """Create test category and template."""
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "Test Category",
                "code": "test",
            }
        )
        cls.template = cls.env["spp.gis.report.template"].create(
            {
                "name": "Test Template",
                "code": "test_template",
                "category_id": cls.category.id,
                "description": "Test template for unit tests",
                "config": {
                    "source_model": "res.partner",
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                    "filter_mode": "domain",
                    "filter_domain": "[('is_registrant', '=', True)]",
                    "base_area_level": 2,
                    "normalization_method": "raw",
                    "color_scheme": "viridis",  # Color scheme code (wizard looks up by code)
                    "threshold_mode": "auto_quartile",
                    "enable_rollup": True,
                    "rollup_method": "sum",
                    "rollup_weight_source": "count",
                },
            }
        )

    def create_test_report(
        self, name="Test Report", code=None, aggregation_method="count", normalization_method="raw", **kwargs
    ):
        """Helper to create a test GIS report.

        Args:
            name: Report name
            code: Report code (auto-generated if None)
            aggregation_method: How to aggregate data
            normalization_method: How to normalize data
            **kwargs: Additional report fields

        Returns:
            spp.gis.report: Created report record
        """
        if code is None:
            # Generate unique code based on test method name
            import inspect

            frame = inspect.currentframe().f_back
            test_name = frame.f_code.co_name
            code = f"{test_name}_{id(self)}"

        vals = {
            "name": name,
            "code": code,
            "category_id": self.category.id,
            "source_model_id": self.partner_model.id,
            "area_field_path": "area_id",
            "aggregation_method": aggregation_method,
            "normalization_method": normalization_method,
            "base_area_level": 2,
        }
        vals.update(kwargs)
        return self.env["spp.gis.report"].create(vals)

    def create_test_data(self, report, area, raw_value=100, **kwargs):
        """Helper to create test report data.

        Args:
            report: spp.gis.report record
            area: spp.area record
            raw_value: Raw value to store
            **kwargs: Additional data fields

        Returns:
            spp.gis.report.data: Created data record
        """
        vals = {
            "report_id": report.id,
            "area_id": area.id,
            "raw_value": raw_value,
            "normalized_value": raw_value,
        }
        vals.update(kwargs)
        return self.env["spp.gis.report.data"].create(vals)

    def create_test_threshold(self, report, min_value, max_value, color, label, **kwargs):
        """Helper to create test threshold.

        Args:
            report: spp.gis.report record
            min_value: Minimum threshold value
            max_value: Maximum threshold value
            color: Hex color code
            label: Threshold label
            **kwargs: Additional threshold fields

        Returns:
            spp.gis.report.threshold: Created threshold record
        """
        vals = {
            "report_id": report.id,
            "min_value": min_value,
            "max_value": max_value,
            "color": color,
            "label": label,
        }
        vals.update(kwargs)
        return self.env["spp.gis.report.threshold"].create(vals)
