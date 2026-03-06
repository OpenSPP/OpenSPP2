# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for QML template service."""

import logging

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestQMLTemplateService(TransactionCase):
    """Test QML template generation."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create color scheme
        cls.color_scheme = cls.env["spp.gis.color.scheme"].create(
            {
                "name": "Test Viridis",
                "code": "test_viridis",
                "scheme_type": "sequential",
                "colors": '["#440154", "#21918c", "#fde725"]',
                "default_steps": 3,
            }
        )

        # Create GIS report
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        cls.report = cls.env["spp.gis.report"].create(
            {
                "name": "Test QML Report",
                "code": "test_qml_report",
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
                "color_scheme_id": cls.color_scheme.id,
                "threshold_mode": "manual",
            }
        )

        # Create thresholds
        cls.threshold1 = cls.env["spp.gis.report.threshold"].create(
            {
                "report_id": cls.report.id,
                "sequence": 10,
                "min_value": 0,
                "max_value": 10,
                "color": "#440154",
                "label": "Low",
            }
        )
        cls.threshold2 = cls.env["spp.gis.report.threshold"].create(
            {
                "report_id": cls.report.id,
                "sequence": 20,
                "min_value": 10,
                "max_value": 50,
                "color": "#21918c",
                "label": "Medium",
            }
        )
        cls.threshold3 = cls.env["spp.gis.report.threshold"].create(
            {
                "report_id": cls.report.id,
                "sequence": 30,
                "min_value": 50,
                "max_value": None,
                "color": "#fde725",
                "label": "High",
            }
        )

    def test_generate_graduated_polygon_qml(self):
        """Test generating graduated polygon QML."""
        from ..services.qml_template_service import QMLTemplateService

        service = QMLTemplateService(self.env)

        # Generate QML
        qml = service.generate_qml(
            report_id=self.report.id,
            geometry_type="polygon",
            field_name="normalized_value",
            opacity=0.7,
        )

        # Verify QML structure
        self.assertIn("<!DOCTYPE qgis", qml)
        self.assertIn('renderer-v2 type="graduatedSymbol"', qml)
        self.assertIn('attr="normalized_value"', qml)
        self.assertIn("<ranges>", qml)
        self.assertIn("<symbols>", qml)
        self.assertIn("<layerOpacity>0.7</layerOpacity>", qml)

        # Verify ranges are present
        self.assertIn('label="Low"', qml)
        self.assertIn('label="Medium"', qml)
        self.assertIn('label="High"', qml)

        # Verify colors are present (converted to RGB)
        self.assertIn("68,1,84,255", qml)  # #440154
        self.assertIn("33,145,140,255", qml)  # #21918c
        self.assertIn("253,231,37,255", qml)  # #fde725

        _logger.info("Generated polygon QML length: %d", len(qml))

    def test_generate_point_qml(self):
        """Test generating basic point QML."""
        from ..services.qml_template_service import QMLTemplateService

        # Update report to use point geometry
        self.report.write({"geometry_type": "point"})

        service = QMLTemplateService(self.env)

        # Generate QML
        qml = service.generate_qml(
            report_id=self.report.id,
            geometry_type="point",
            opacity=0.8,
        )

        # Verify QML structure
        self.assertIn("<!DOCTYPE qgis", qml)
        self.assertIn('renderer-v2 type="singleSymbol"', qml)
        self.assertIn('symbol type="marker"', qml)
        self.assertIn("<layerOpacity>0.8</layerOpacity>", qml)

        # Verify color from color scheme is present
        # First color from scheme should be used
        self.assertIn("68,1,84,255", qml)  # #440154

        _logger.info("Generated point QML length: %d", len(qml))

    def test_generate_cluster_qml(self):
        """Test generating clustered point QML."""
        from ..services.qml_template_service import QMLTemplateService

        # Update report to use cluster geometry
        self.report.write({"geometry_type": "cluster"})

        service = QMLTemplateService(self.env)

        # Generate QML
        qml = service.generate_qml(
            report_id=self.report.id,
            geometry_type="cluster",
            opacity=0.9,
        )

        # Verify QML structure
        self.assertIn("<!DOCTYPE qgis", qml)
        self.assertIn('renderer-v2 type="pointCluster"', qml)
        self.assertIn('symbol type="marker"', qml)
        self.assertIn("<layerOpacity>0.9</layerOpacity>", qml)

        _logger.info("Generated cluster QML length: %d", len(qml))

    def test_hex_to_rgb_conversion(self):
        """Test hex to RGB conversion."""
        from ..services.qml_template_service import QMLTemplateService

        # Test valid hex colors
        self.assertEqual(QMLTemplateService._hex_to_rgb("#440154"), "68,1,84,255")
        self.assertEqual(QMLTemplateService._hex_to_rgb("#21918c"), "33,145,140,255")
        self.assertEqual(QMLTemplateService._hex_to_rgb("#fde725"), "253,231,37,255")
        self.assertEqual(QMLTemplateService._hex_to_rgb("#ffffff"), "255,255,255,255")
        self.assertEqual(QMLTemplateService._hex_to_rgb("#000000"), "0,0,0,255")

        # Test without # prefix
        self.assertEqual(QMLTemplateService._hex_to_rgb("440154"), "68,1,84,255")

        # Test invalid hex (should fallback to gray)
        self.assertEqual(QMLTemplateService._hex_to_rgb("invalid"), "128,128,128,255")
        self.assertEqual(QMLTemplateService._hex_to_rgb(""), "128,128,128,255")

    def test_xml_escaping(self):
        """Test XML special character escaping."""
        from ..services.qml_template_service import QMLTemplateService

        self.assertEqual(QMLTemplateService._escape_xml("Test & Co"), "Test &amp; Co")
        self.assertEqual(QMLTemplateService._escape_xml("<tag>"), "&lt;tag&gt;")
        self.assertEqual(QMLTemplateService._escape_xml('"quoted"'), "&quot;quoted&quot;")
        self.assertEqual(QMLTemplateService._escape_xml("'single'"), "&apos;single&apos;")
        self.assertEqual(QMLTemplateService._escape_xml("Normal text"), "Normal text")

    def test_invalid_report_id(self):
        """Test QML generation with invalid report ID."""
        from ..services.qml_template_service import QMLTemplateService

        service = QMLTemplateService(self.env)

        # Should raise ValueError for non-existent report
        with self.assertRaises(ValueError) as context:
            service.generate_qml(
                report_id=99999,
                geometry_type="polygon",
            )

        self.assertIn("not found", str(context.exception))

    def test_unsupported_geometry_type(self):
        """Test QML generation with unsupported geometry type."""
        from ..services.qml_template_service import QMLTemplateService

        service = QMLTemplateService(self.env)

        # Should raise ValueError for unsupported geometry type
        with self.assertRaises(ValueError) as context:
            service.generate_qml(
                report_id=self.report.id,
                geometry_type="unsupported",
            )

        self.assertIn("Unsupported geometry type", str(context.exception))

    def test_report_without_thresholds(self):
        """Test QML generation for report without thresholds."""
        from ..services.qml_template_service import QMLTemplateService

        # Create report without thresholds
        report = self.env["spp.gis.report"].create(
            {
                "name": "Test Report No Thresholds",
                "code": "test_no_thresholds",
                "source_model_id": self.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
                "color_scheme_id": self.color_scheme.id,
            }
        )

        service = QMLTemplateService(self.env)

        # Should generate default QML with single class
        qml = service.generate_qml(
            report_id=report.id,
            geometry_type="polygon",
        )

        self.assertIn("<!DOCTYPE qgis", qml)
        self.assertIn('renderer-v2 type="graduatedSymbol"', qml)
        self.assertIn('label="All Values"', qml)
        self.assertIn("52,152,219,255", qml)  # Default blue color

    def test_report_without_color_scheme(self):
        """Test QML generation for report using default color scheme."""
        from ..services.qml_template_service import QMLTemplateService

        # Create report without explicitly setting color scheme (uses default)
        report = self.env["spp.gis.report"].create(
            {
                "name": "Test Report No Colors",
                "code": "test_no_colors",
                "source_model_id": self.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "point",
                # color_scheme_id not set - will use default
            }
        )

        service = QMLTemplateService(self.env)

        # Should use default color scheme
        qml = service.generate_qml(
            report_id=report.id,
            geometry_type="point",
        )

        self.assertIn("<!DOCTYPE qgis", qml)
        self.assertIn('renderer-v2 type="singleSymbol"', qml)
        # Should have some color (from default scheme or fallback)
        self.assertIn("color", qml.lower())

    def test_per_level_thresholds_when_single_bucket(self):
        """Test that per-level QML adapts thresholds when all data falls in one global bucket."""
        from ..services.qml_template_service import QMLTemplateService

        # Create areas at level 2 with values that all fall into the global "Low" bucket (0-10)
        area_type = self.env["spp.area.type"].create({"name": "QML Municipality"})
        parent_area = self.env["spp.area"].create(
            {
                "draft_name": "QML Parent",
                "code": "qml_parent",
                "area_type_id": area_type.id,
            }
        )

        child_type = self.env["spp.area.type"].create({"name": "QML City"})
        areas = []
        for i in range(5):
            areas.append(
                self.env["spp.area"].create(
                    {
                        "draft_name": f"QML City {i}",
                        "code": f"qml_city_{i}",
                        "parent_id": parent_area.id,
                        "area_type_id": child_type.id,
                    }
                )
            )

        # Create report data at level 1 with values 2.0-6.0
        # These all fall into global "Low" bucket (0-10)
        for idx, area in enumerate(areas):
            self.env["spp.gis.report.data"].create(
                {
                    "report_id": self.report.id,
                    "area_id": area.id,
                    "area_code": area.code,
                    "area_name": area.draft_name,
                    "area_level": area.area_level,
                    "raw_value": 2.0 + idx,
                    "normalized_value": 2.0 + idx,
                    "display_value": str(2.0 + idx),
                    "record_count": 10,
                }
            )

        service = QMLTemplateService(self.env)
        admin_level = areas[0].area_level

        # Generate QML with admin_level — thresholds should be adapted
        qml_level = service.generate_qml(
            report_id=self.report.id,
            geometry_type="polygon",
            admin_level=admin_level,
        )

        # Generate QML without admin_level — uses global thresholds
        qml_global = service.generate_qml(
            report_id=self.report.id,
            geometry_type="polygon",
        )

        # Both should be valid QML
        self.assertIn("<!DOCTYPE qgis", qml_level)
        self.assertIn("<!DOCTYPE qgis", qml_global)

        # Per-level QML should have different threshold ranges than global
        # Global has lower="0" upper="10" for Low bucket
        # Per-level should have ranges within the 2.0-6.0 range
        self.assertIn('label="Low"', qml_level)
        self.assertIn('label="Medium"', qml_level)
        self.assertIn('label="High"', qml_level)
        # The per-level thresholds should NOT use the global 0-10 range
        self.assertNotIn('lower="0" upper="10"', qml_level)

    def test_per_level_thresholds_skipped_when_data_spans_buckets(self):
        """Test that per-level thresholds are not used when data already spans multiple buckets."""
        from ..services.qml_template_service import QMLTemplateService

        # Create areas at a specific level with values spanning multiple global thresholds
        area_type = self.env["spp.area.type"].create({"name": "QML Spanning"})
        areas = []
        for i in range(3):
            areas.append(
                self.env["spp.area"].create(
                    {
                        "draft_name": f"QML Span Area {i}",
                        "code": f"qml_span_{i}",
                        "area_type_id": area_type.id,
                    }
                )
            )

        # Values 5, 25, 75 span Low (0-10), Medium (10-50), and High (50+)
        for area, value in zip(areas, [5.0, 25.0, 75.0], strict=False):
            self.env["spp.gis.report.data"].create(
                {
                    "report_id": self.report.id,
                    "area_id": area.id,
                    "area_code": area.code,
                    "area_name": area.draft_name,
                    "area_level": area.area_level,
                    "raw_value": value,
                    "normalized_value": value,
                    "display_value": str(value),
                    "record_count": 10,
                }
            )

        service = QMLTemplateService(self.env)
        admin_level = areas[0].area_level

        # Generate per-level QML
        qml_level = service.generate_qml(
            report_id=self.report.id,
            geometry_type="polygon",
            admin_level=admin_level,
        )

        # Generate global QML
        qml_global = service.generate_qml(
            report_id=self.report.id,
            geometry_type="polygon",
        )

        # Both should use the same global thresholds since data spans 3 buckets
        self.assertEqual(qml_level, qml_global)
