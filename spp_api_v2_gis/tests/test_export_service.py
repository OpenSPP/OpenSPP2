# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for export service."""

import json
import logging
import zipfile
from io import BytesIO

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestExportService(TransactionCase):
    """Test export service functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Sample polygon GeoJSON
        cls.sample_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [100.0, 0.0],
                    [101.0, 0.0],
                    [101.0, 1.0],
                    [100.0, 1.0],
                    [100.0, 0.0],
                ]
            ],
        }

        # Create color scheme
        cls.color_scheme = cls.env["spp.gis.color.scheme"].create(
            {
                "name": "Test Export Colors",
                "code": "test_export",
                "scheme_type": "sequential",
                "colors": '["#440154", "#21918c"]',
                "default_steps": 2,
            }
        )

        # Create area model reference
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)

        # Create test reports
        cls.report1 = cls.env["spp.gis.report"].create(
            {
                "name": "Export Test Report 1",
                "code": "export_test_report_1",
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
                "color_scheme_id": cls.color_scheme.id,
            }
        )

        cls.report2 = cls.env["spp.gis.report"].create(
            {
                "name": "Export Test Report 2",
                "code": "export_test_report_2",
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "point",
            }
        )

        # Create test geofences
        cls.geofence1 = cls.env["spp.gis.geofence"].create(
            {
                "name": "Export Geofence 1",
                "geometry": json.dumps(cls.sample_polygon),
                "geofence_type": "custom",
            }
        )

        cls.geofence2 = cls.env["spp.gis.geofence"].create(
            {
                "name": "Export Geofence 2",
                "geometry": json.dumps(cls.sample_polygon),
                "geofence_type": "hazard_zone",
            }
        )

    def test_export_geopackage_fallback_to_zip(self):
        """Test that export falls back to ZIP when fiona unavailable."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        # Export (should fall back to ZIP since fiona likely not available in tests)
        content, filename, content_type = service.export_geopackage(
            layer_ids=["export_test_report_1"],
            include_geofences=True,
        )

        # Verify result (likely ZIP fallback)
        self.assertTrue(content)
        self.assertTrue(filename)
        self.assertIn(content_type, ["application/geopackage+sqlite3", "application/zip"])

    def test_export_specific_layers(self):
        """Test exporting specific layers."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        content, filename, content_type = service.export_geopackage(
            layer_ids=["export_test_report_1", "export_test_report_2"],
            include_geofences=False,
        )

        self.assertTrue(content)
        self.assertIsInstance(content, bytes)

    def test_export_all_layers(self):
        """Test exporting all available layers."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        content, filename, content_type = service.export_geopackage(
            layer_ids=None,  # Export all
            include_geofences=False,
        )

        self.assertTrue(content)
        self.assertIsInstance(content, bytes)

    def test_export_with_geofences(self):
        """Test exporting with geofences included."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        content, filename, content_type = service.export_geopackage(
            layer_ids=["export_test_report_1"],
            include_geofences=True,
        )

        self.assertTrue(content)
        self.assertIsInstance(content, bytes)

    def test_export_without_geofences(self):
        """Test exporting without geofences."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        content, filename, content_type = service.export_geopackage(
            layer_ids=["export_test_report_1"],
            include_geofences=False,
        )

        self.assertTrue(content)
        self.assertIsInstance(content, bytes)

    def test_export_no_data_raises_error(self):
        """Test that exporting with no data raises error."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        # Deactivate all reports
        self.report1.active = False
        self.report2.active = False

        # Deactivate all geofences
        self.geofence1.active = False
        self.geofence2.active = False

        with self.assertRaises(ValueError) as context:
            service.export_geopackage(
                layer_ids=[],
                include_geofences=True,
            )

        self.assertIn("No data available", str(context.exception))

    def test_collect_layers_specific_codes(self):
        """Test collecting specific layers by code."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)
        layers_data = service._collect_layers(
            layer_ids=["export_test_report_1"],
            admin_level=None,
        )

        self.assertGreater(len(layers_data), 0)
        # Verify structure: list of (name, geojson) tuples
        self.assertIsInstance(layers_data[0], tuple)
        self.assertEqual(len(layers_data[0]), 2)

    def test_collect_layers_all(self):
        """Test collecting all available layers."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)
        layers_data = service._collect_layers(
            layer_ids=None,
            admin_level=None,
        )

        # Should collect all active reports
        self.assertGreater(len(layers_data), 0)

    def test_collect_layers_with_admin_level_filter(self):
        """Test collecting layers with admin level filter."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)
        layers_data = service._collect_layers(
            layer_ids=["export_test_report_1"],
            admin_level=2,
        )

        # Should complete without error
        self.assertIsInstance(layers_data, list)

    def test_collect_layers_invalid_code(self):
        """Test collecting layers with invalid code logs warning."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)
        layers_data = service._collect_layers(
            layer_ids=["nonexistent_report"],
            admin_level=None,
        )

        # Should return empty list for invalid codes
        self.assertEqual(len(layers_data), 0)

    def test_collect_geofences(self):
        """Test collecting geofences."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)
        geofences_data = service._collect_geofences()

        # Should return list of (name, geojson) tuples
        self.assertIsInstance(geofences_data, list)
        if len(geofences_data) > 0:
            self.assertEqual(len(geofences_data), 1)  # Returns as single "geofences" layer
            name, geojson = geofences_data[0]
            self.assertEqual(name, "geofences")
            self.assertEqual(geojson["type"], "FeatureCollection")
            self.assertGreater(len(geojson["features"]), 0)

    def test_collect_geofences_empty(self):
        """Test collecting geofences when none exist."""
        # Deactivate all geofences
        self.geofence1.active = False
        self.geofence2.active = False

        from ..services.export_service import ExportService

        service = ExportService(self.env)
        geofences_data = service._collect_geofences()

        self.assertEqual(len(geofences_data), 0)

    def test_create_geojson_zip(self):
        """Test creating GeoJSON ZIP archive."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        # Collect some data
        layers_data = service._collect_layers(
            layer_ids=["export_test_report_1"],
            admin_level=None,
        )
        geofences_data = service._collect_geofences()

        # Create ZIP
        content, filename, content_type = service._create_geojson_zip(
            layers_data,
            geofences_data,
        )

        # Verify ZIP structure
        self.assertEqual(filename, "openspp_export.zip")
        self.assertEqual(content_type, "application/zip")
        self.assertIsInstance(content, bytes)

        # Verify ZIP contents
        with zipfile.ZipFile(BytesIO(content), "r") as zf:
            file_list = zf.namelist()
            self.assertGreater(len(file_list), 0)

            # Verify files are GeoJSON
            for file_name in file_list:
                self.assertTrue(file_name.endswith(".geojson"))

                # Verify file contains valid GeoJSON
                with zf.open(file_name) as f:
                    geojson_data = json.load(f)
                    self.assertEqual(geojson_data["type"], "FeatureCollection")

    def test_sanitize_filename_basic(self):
        """Test filename sanitization."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        self.assertEqual(service._sanitize_filename("simple_name"), "simple_name")
        self.assertEqual(service._sanitize_filename("name with spaces"), "name_with_spaces")
        self.assertEqual(service._sanitize_filename("name/with/slashes"), "name_with_slashes")
        self.assertEqual(service._sanitize_filename("name\\with\\backslashes"), "name_with_backslashes")

    def test_sanitize_filename_special_chars(self):
        """Test filename sanitization with special characters."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        # Should keep alphanumeric, underscore, and dash
        result = service._sanitize_filename("name-123_test")
        self.assertEqual(result, "name-123_test")

        # Should remove other special characters
        result = service._sanitize_filename("name@#$%test")
        self.assertEqual(result, "nametest")

    def test_sanitize_filename_empty(self):
        """Test filename sanitization with empty string."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        # Should return default "layer"
        result = service._sanitize_filename("")
        self.assertEqual(result, "layer")

    def test_get_geometry_type_polygon(self):
        """Test extracting polygon geometry type."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": []},
            "properties": {},
        }

        geom_type = service._get_geometry_type(feature)
        self.assertEqual(geom_type, "Polygon")

    def test_get_geometry_type_point(self):
        """Test extracting point geometry type."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": []},
            "properties": {},
        }

        geom_type = service._get_geometry_type(feature)
        self.assertEqual(geom_type, "Point")

    def test_get_geometry_type_multipolygon(self):
        """Test extracting multipolygon geometry type."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        feature = {
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": []},
            "properties": {},
        }

        geom_type = service._get_geometry_type(feature)
        self.assertEqual(geom_type, "MultiPolygon")

    def test_get_geometry_type_missing(self):
        """Test extracting geometry type when missing."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        feature = {
            "type": "Feature",
            "geometry": None,
            "properties": {},
        }

        geom_type = service._get_geometry_type(feature)
        self.assertEqual(geom_type, "Point")  # Default

    def test_build_schema_from_feature(self):
        """Test building fiona schema from feature properties."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        feature = {
            "type": "Feature",
            "geometry": {"type": "Polygon"},
            "properties": {
                "name": "Test",
                "count": 42,
                "value": 3.14,
                "active": True,
            },
        }

        schema = service._build_schema(feature, "Polygon")

        self.assertEqual(schema["geometry"], "Polygon")
        self.assertIn("properties", schema)

        props = schema["properties"]
        self.assertEqual(props["name"], "str")
        self.assertEqual(props["count"], "int")
        self.assertEqual(props["value"], "float")
        self.assertEqual(props["active"], "bool")

    def test_build_schema_empty_properties(self):
        """Test building schema with empty properties."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        feature = {
            "type": "Feature",
            "geometry": {"type": "Point"},
            "properties": {},
        }

        schema = service._build_schema(feature, "Point")

        self.assertEqual(schema["geometry"], "Point")
        self.assertEqual(len(schema["properties"]), 0)

    def test_export_returns_valid_tuple(self):
        """Test that export returns valid tuple structure."""
        from ..services.export_service import ExportService

        service = ExportService(self.env)

        result = service.export_geopackage(
            layer_ids=["export_test_report_1"],
            include_geofences=False,
        )

        # Should return tuple of (bytes, filename, content_type)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 3)

        content, filename, content_type = result
        self.assertIsInstance(content, bytes)
        self.assertIsInstance(filename, str)
        self.assertIsInstance(content_type, str)
