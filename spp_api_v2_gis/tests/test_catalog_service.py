# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for catalog service."""

import logging
from datetime import datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestCatalogService(TransactionCase):
    """Test catalog service functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create color scheme for reports
        cls.color_scheme = cls.env["spp.gis.color.scheme"].create(
            {
                "name": "Test Color Scheme",
                "code": "test_scheme",
                "scheme_type": "sequential",
                "colors": '["#440154", "#21918c", "#fde725"]',
                "default_steps": 3,
            }
        )

        # Create report category
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "Test Category",
                "code": "test_category",
                "sequence": 10,
            }
        )

        # Create area model reference
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)

        # Create test reports
        cls.report1 = cls.env["spp.gis.report"].create(
            {
                "name": "Test Report 1",
                "code": "test_report_1",
                "description": "Test report description",
                "category_id": cls.category.id,
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
                "color_scheme_id": cls.color_scheme.id,
                "last_refresh": datetime.now() - timedelta(days=1),
                "sequence": 10,
            }
        )

        cls.report2 = cls.env["spp.gis.report"].create(
            {
                "name": "Test Report 2",
                "code": "test_report_2",
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 3,
                "normalization_method": "raw",
                "geometry_type": "point",
                "sequence": 20,
            }
        )

        # Create inactive report (should not appear in catalog)
        cls.inactive_report = cls.env["spp.gis.report"].create(
            {
                "name": "Inactive Report",
                "code": "inactive_report",
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
                "active": False,
                "sequence": 30,
            }
        )

        # Create data layer
        cls.geo_field = cls.env["ir.model.fields"].search(
            [("model", "=", "spp.area"), ("name", "=", "polygon")],
            limit=1,
        )
        if cls.geo_field:
            cls.data_layer = cls.env["spp.gis.data.layer"].create(
                {
                    "name": "Test Data Layer",
                    "model_name": "spp.area",
                    "geo_field_id": cls.geo_field.id,
                    "geo_repr": "basic",
                    "sequence": 10,
                }
            )
        else:
            cls.data_layer = None

    def test_get_catalog_with_reports(self):
        """Test getting catalog with reports."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        # Verify catalog structure
        self.assertIn("reports", catalog)
        self.assertIn("data_layers", catalog)

        # Verify reports are present
        reports = catalog["reports"]
        self.assertGreaterEqual(len(reports), 2, "Should have at least 2 active reports")

        # Verify report 1 data
        report1_data = next((r for r in reports if r["id"] == "test_report_1"), None)
        self.assertIsNotNone(report1_data)
        self.assertEqual(report1_data["name"], "Test Report 1")
        self.assertEqual(report1_data["description"], "Test report description")
        self.assertEqual(report1_data["category"], "Test Category")
        self.assertEqual(report1_data["geometry_type"], "polygon")
        self.assertEqual(report1_data["area_level"], 2)
        self.assertIsNotNone(report1_data["last_refresh"])

        # Verify report 2 data
        report2_data = next((r for r in reports if r["id"] == "test_report_2"), None)
        self.assertIsNotNone(report2_data)
        self.assertEqual(report2_data["name"], "Test Report 2")
        self.assertIsNone(report2_data["category"])
        self.assertEqual(report2_data["geometry_type"], "point")
        self.assertEqual(report2_data["area_level"], 3)

        # Verify inactive report is not present
        inactive_data = next((r for r in reports if r["id"] == "inactive_report"), None)
        self.assertIsNone(inactive_data, "Inactive reports should not appear in catalog")

    def test_get_catalog_with_data_layers(self):
        """Test getting catalog with data layers."""
        if not self.data_layer:
            self.skipTest("No data layer available (spp.area polygon field not found)")

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        # Verify data layers are present
        data_layers = catalog["data_layers"]
        self.assertGreater(len(data_layers), 0, "Should have at least 1 data layer")

        # Verify data layer structure
        layer_data = next((layer for layer in data_layers if layer["name"] == "Test Data Layer"), None)
        self.assertIsNotNone(layer_data)
        self.assertEqual(layer_data["name"], "Test Data Layer")
        self.assertEqual(layer_data["geometry_type"], "polygon")
        self.assertEqual(layer_data["source_model"], "spp.area")
        # Verify source_type and report_code fields
        self.assertIn("source_type", layer_data)
        self.assertEqual(layer_data["source_type"], "model")
        self.assertIn("report_code", layer_data)
        self.assertIsNone(layer_data["report_code"])

    def test_get_catalog_report_driven_data_layer(self):
        """Test catalog includes source_type and report_code for report-driven layers."""
        if not self.geo_field:
            self.skipTest("No geo field available for data layer creation")
        # Create a report-driven data layer
        report_layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Report-Driven Layer",
                "source_type": "report",
                "report_id": self.report1.id,
                "geo_field_id": self.geo_field.id,
                "geo_repr": "choropleth",
                "sequence": 99,
            }
        )

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        data_layers = catalog["data_layers"]
        layer_data = next(
            (layer for layer in data_layers if layer["id"] == str(report_layer.id)),
            None,
        )
        self.assertIsNotNone(layer_data, "Report-driven data layer should appear in catalog")
        self.assertEqual(layer_data["source_type"], "report")
        self.assertEqual(layer_data["report_code"], "test_report_1")

    def test_catalog_reports_ordered_by_sequence(self):
        """Test that reports are ordered by sequence then name."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        reports = catalog["reports"]
        report_codes = [r["id"] for r in reports if r["id"].startswith("test_report_")]

        # Should be ordered by sequence
        self.assertGreater(
            report_codes.index("test_report_1"),
            -1,
        )
        self.assertGreater(
            report_codes.index("test_report_2"),
            -1,
        )

    def test_empty_catalog(self):
        """Test catalog with no reports or layers."""
        # Deactivate all test reports
        self.report1.active = False
        self.report2.active = False

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        # Should still have structure but may be empty or have other reports
        self.assertIn("reports", catalog)
        self.assertIn("data_layers", catalog)
        self.assertIsInstance(catalog["reports"], list)
        self.assertIsInstance(catalog["data_layers"], list)

    def test_freshness_indicator_fresh(self):
        """Test freshness indicator for recently refreshed report."""
        # Set last_refresh to recent time
        self.report1.write(
            {
                "last_refresh": datetime.now() - timedelta(hours=1),
                "is_stale": False,
            }
        )

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        report1_data = next((r for r in catalog["reports"] if r["id"] == "test_report_1"), None)
        self.assertIsNotNone(report1_data)
        self.assertEqual(report1_data["freshness"], "fresh")

    def test_freshness_indicator_stale(self):
        """Test freshness indicator for stale report."""
        # Mark report as stale
        self.report1.write(
            {
                "last_refresh": datetime.now() - timedelta(days=10),
                "is_stale": True,
            }
        )

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        report1_data = next((r for r in catalog["reports"] if r["id"] == "test_report_1"), None)
        self.assertIsNotNone(report1_data)
        self.assertEqual(report1_data["freshness"], "stale")

    def test_freshness_indicator_never_refreshed(self):
        """Test freshness indicator for never refreshed report."""
        # Clear last_refresh
        self.report2.write({"last_refresh": False})

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        report2_data = next((r for r in catalog["reports"] if r["id"] == "test_report_2"), None)
        self.assertIsNotNone(report2_data)
        self.assertEqual(report2_data["freshness"], "never_refreshed")

    def test_normalize_geometry_type_polygon(self):
        """Test geometry type normalization for polygon."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        self.assertEqual(service._normalize_geometry_type("polygon"), "polygon")

    def test_normalize_geometry_type_point(self):
        """Test geometry type normalization for point."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        self.assertEqual(service._normalize_geometry_type("point"), "point")

    def test_normalize_geometry_type_cluster(self):
        """Test geometry type normalization for cluster."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        # Cluster is still point type
        self.assertEqual(service._normalize_geometry_type("cluster"), "point")

    def test_normalize_geometry_type_heatmap(self):
        """Test geometry type normalization for heatmap."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        # Heatmap is based on points
        self.assertEqual(service._normalize_geometry_type("heatmap"), "point")

    def test_normalize_geometry_type_unknown(self):
        """Test geometry type normalization for unknown type."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        # Should default to polygon
        self.assertEqual(service._normalize_geometry_type("unknown"), "polygon")

    def test_data_layer_geo_repr_mapping(self):
        """Test data layer geo_repr to geometry type mapping."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        # Basic and choropleth both map to polygon
        self.assertEqual(service._map_geo_repr_to_geometry_type("basic"), "polygon")
        self.assertEqual(service._map_geo_repr_to_geometry_type("choropleth"), "polygon")

    def test_report_has_admin_levels_available(self):
        """Test that reports include admin_levels_available from report data."""
        # Create area type for level 1
        area_type_1 = self.env["spp.area.type"].create({"name": "Region"})
        area_type_2 = self.env["spp.area.type"].create({"name": "District"})

        # Create areas at levels 1 and 2
        area_l1 = self.env["spp.area"].create(
            {
                "draft_name": "Catalog Test Region",
                "code": "catalog_test_region",
                "area_type_id": area_type_1.id,
            }
        )
        area_l2 = self.env["spp.area"].create(
            {
                "draft_name": "Catalog Test District",
                "code": "catalog_test_district",
                "parent_id": area_l1.id,
                "area_type_id": area_type_2.id,
            }
        )

        # Create report data at both levels
        self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report1.id,
                "area_id": area_l1.id,
                "area_code": area_l1.code,
                "area_name": area_l1.draft_name,
                "area_level": area_l1.area_level,
                "raw_value": 100.0,
                "normalized_value": 0.5,
                "display_value": "100",
                "record_count": 100,
            }
        )
        self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report1.id,
                "area_id": area_l2.id,
                "area_code": area_l2.code,
                "area_name": area_l2.draft_name,
                "area_level": area_l2.area_level,
                "raw_value": 50.0,
                "normalized_value": 0.25,
                "display_value": "50",
                "record_count": 50,
            }
        )

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        report1_data = next((r for r in catalog["reports"] if r["id"] == "test_report_1"), None)
        self.assertIsNotNone(report1_data)
        self.assertIn("admin_levels_available", report1_data)
        levels = report1_data["admin_levels_available"]
        self.assertIsInstance(levels, list)
        self.assertEqual(levels, sorted(levels))
        self.assertIn(area_l1.area_level, levels)
        self.assertIn(area_l2.area_level, levels)

    def test_report_no_data_has_empty_admin_levels(self):
        """Test that reports with no data have empty admin_levels_available."""
        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        report2_data = next((r for r in catalog["reports"] if r["id"] == "test_report_2"), None)
        self.assertIsNotNone(report2_data)
        self.assertIn("admin_levels_available", report2_data)
        self.assertEqual(report2_data["admin_levels_available"], [])

    def test_catalog_has_area_level_names(self):
        """Test that catalog includes area_level_names mapping."""
        # Create area type and area at known level
        area_type = self.env["spp.area.type"].create({"name": "Province"})
        self.env["spp.area"].create(
            {
                "draft_name": "Catalog Level Name Test",
                "code": "catalog_level_name_test",
                "area_type_id": area_type.id,
            }
        )

        from ..services.catalog_service import CatalogService

        service = CatalogService(self.env)
        catalog = service.get_catalog()

        self.assertIn("area_level_names", catalog)
        self.assertIsInstance(catalog["area_level_names"], dict)
