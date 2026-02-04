"""Tests for GIS Data Layer Extension.

Tests cover:
- Data layer source types (model vs report)
- Report-driven layer creation
- Geometry type configuration
- Color scheme integration
- Layer styling methods
"""

from odoo.tests import TransactionCase


class TestDataLayerExtension(TransactionCase):
    """Test cases for spp.gis.data.layer extension."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get required models
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)

        # Get geo field for area
        cls.geo_field = cls.env["ir.model.fields"].search(
            [
                ("model_id", "=", cls.area_model.id),
                ("name", "=", "geo_polygon"),
            ],
            limit=1,
        )

        # Get or create a GIS view for spp.area
        cls.gis_view = cls.env["ir.ui.view"].search(
            [
                ("model", "=", "spp.area"),
                ("type", "=", "gis"),
            ],
            limit=1,
        )

        # Create a color scheme for tests
        cls.color_scheme = cls.env["spp.gis.color.scheme"].search([("code", "=", "viridis")], limit=1)

        # Create category
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "Test Category",
                "code": "test_layer_ext",
            }
        )

        # Create a test report
        cls.report = cls.env["spp.gis.report"].create(
            {
                "name": "Layer Test Report",
                "code": "layer_test_report",
                "category_id": cls.category.id,
                "source_model_id": cls.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "geometry_type": "polygon",
                "auto_create_layer": False,  # Disable for manual testing
            }
        )

    def test_01_layer_source_type_default(self):
        """Test default source type is 'model'."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Model Layer",
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        self.assertEqual(layer.source_type, "model")
        self.assertFalse(layer.is_report_layer)

    def test_02_layer_report_source_type(self):
        """Test report source type."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Report Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        self.assertEqual(layer.source_type, "report")
        self.assertTrue(layer.is_report_layer)
        self.assertEqual(layer.report_id, self.report)
        self.assertEqual(layer.report_code, self.report.code)

    def test_03_layer_geometry_types(self):
        """Test different geometry type configurations."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        geometry_types = ["polygon", "point", "cluster", "heatmap"]

        for geom_type in geometry_types:
            layer = self.env["spp.gis.data.layer"].create(
                {
                    "name": f"Geom {geom_type}",
                    "source_type": "report",
                    "report_id": self.report.id,
                    "geometry_type": geom_type,
                    "geo_field_id": self.geo_field.id,
                    "view_id": self.gis_view.id,
                }
            )

            self.assertEqual(layer.geometry_type, geom_type)
            layer.unlink()

    def test_04_layer_color_scheme_integration(self):
        """Test color scheme integration."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Color Scheme Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "color_scheme_id": self.color_scheme.id if self.color_scheme else False,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        if self.color_scheme:
            self.assertEqual(layer.color_scheme_id, self.color_scheme)

    def test_05_layer_effective_color_scheme(self):
        """Test effective color scheme resolution."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        # Layer without color scheme should fall back to report's scheme
        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Fallback Scheme Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        effective = layer.get_effective_color_scheme()
        # Should get report's scheme or default
        self.assertTrue(effective)

    def test_06_layer_style_polygon(self):
        """Test layer style for polygon geometry."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Polygon Style Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "geometry_type": "polygon",
                "fill_opacity": 0.8,
                "stroke_color": "#ff0000",
                "stroke_width": 2.0,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        style = layer.get_layer_style()

        self.assertEqual(style["geometry_type"], "polygon")
        self.assertEqual(style["fill_opacity"], 0.8)
        self.assertEqual(style["stroke_color"], "#ff0000")
        self.assertEqual(style["stroke_width"], 2.0)

    def test_07_layer_style_point(self):
        """Test layer style for point geometry."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Point Style Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "geometry_type": "point",
                "point_radius": 12,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        style = layer.get_layer_style()

        self.assertEqual(style["geometry_type"], "point")
        self.assertEqual(style["point_radius"], 12)

    def test_08_layer_style_cluster(self):
        """Test layer style for cluster geometry."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Cluster Style Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "geometry_type": "cluster",
                "point_radius": 10,
                "cluster_radius": 80,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        style = layer.get_layer_style()

        self.assertEqual(style["geometry_type"], "cluster")
        self.assertEqual(style["point_radius"], 10)
        self.assertEqual(style["cluster_radius"], 80)

    def test_09_layer_style_heatmap(self):
        """Test layer style for heatmap geometry."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Heatmap Style Layer",
                "source_type": "report",
                "report_id": self.report.id,
                "geometry_type": "heatmap",
                "heatmap_radius": 30,
                "heatmap_blur": 20,
                "heatmap_max_intensity": 0.8,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        style = layer.get_layer_style()

        self.assertEqual(style["geometry_type"], "heatmap")
        self.assertEqual(style["heatmap_radius"], 30)
        self.assertEqual(style["heatmap_blur"], 20)
        self.assertEqual(style["heatmap_max_intensity"], 0.8)

    def test_10_layer_onchange_source_type(self):
        """Test onchange behavior for source type."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].new(
            {
                "name": "Onchange Test",
                "source_type": "model",
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        # Change to report type
        layer.source_type = "report"
        layer._onchange_source_type()

        # geo_field_id should be cleared when switching to report
        self.assertFalse(layer.geo_field_id)

    def test_11_layer_onchange_report(self):
        """Test onchange behavior when report is selected."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        layer = self.env["spp.gis.data.layer"].new(
            {
                "name": "New",
                "source_type": "report",
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        # Select report
        layer.report_id = self.report
        layer._onchange_report_id()

        # Name should be updated
        self.assertEqual(layer.name, self.report.name)

        # Color scheme should be set from report
        if self.report.color_scheme_id:
            self.assertEqual(layer.color_scheme_id, self.report.color_scheme_id)

    def test_12_layer_style_includes_color_scheme(self):
        """Test that layer style includes color scheme info."""
        if not self.gis_view or not self.geo_field or not self.color_scheme:
            self.skipTest("Required models not available")

        layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "Color Scheme Style Test",
                "source_type": "report",
                "report_id": self.report.id,
                "color_scheme_id": self.color_scheme.id,
                "geo_field_id": self.geo_field.id,
                "view_id": self.gis_view.id,
            }
        )

        style = layer.get_layer_style()

        self.assertIn("color_scheme", style)
        self.assertEqual(style["color_scheme"]["code"], self.color_scheme.code)
        self.assertEqual(style["color_scheme"]["type"], self.color_scheme.scheme_type)
        self.assertIsInstance(style["color_scheme"]["colors"], list)


class TestReportLayerAutoSync(TransactionCase):
    """Test cases for report layer auto-sync functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)

        cls.geo_field = cls.env["ir.model.fields"].search(
            [
                ("model_id", "=", cls.area_model.id),
                ("name", "=", "geo_polygon"),
            ],
            limit=1,
        )

        cls.gis_view = cls.env["ir.ui.view"].search(
            [
                ("model", "=", "spp.area"),
                ("type", "=", "gis"),
            ],
            limit=1,
        )

        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "Auto Sync Test",
                "code": "auto_sync_test",
            }
        )

    def test_01_report_auto_create_layer_on_create(self):
        """Test layer is auto-created when report is created with auto_create_layer=True."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        report = self.env["spp.gis.report"].create(
            {
                "name": "Auto Create Layer Test",
                "code": "auto_create_layer_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "geometry_type": "polygon",
                "auto_create_layer": True,
            }
        )

        self.assertTrue(report.layer_id)
        self.assertEqual(report.layer_id.source_type, "report")
        self.assertEqual(report.layer_id.report_id, report)
        self.assertEqual(report.layer_id.name, report.name)

    def test_02_report_no_layer_when_disabled(self):
        """Test no layer is created when auto_create_layer=False."""
        report = self.env["spp.gis.report"].create(
            {
                "name": "No Auto Layer Test",
                "code": "no_auto_layer_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "auto_create_layer": False,
            }
        )

        self.assertFalse(report.layer_id)

    def test_03_report_layer_sync_on_name_change(self):
        """Test layer is updated when report name changes."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        report = self.env["spp.gis.report"].create(
            {
                "name": "Original Name",
                "code": "name_sync_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "auto_create_layer": True,
            }
        )

        original_layer = report.layer_id
        self.assertEqual(original_layer.name, "Original Name")

        # Update report name
        report.write({"name": "Updated Name"})

        # Layer name should be updated
        self.assertEqual(report.layer_id.name, "Updated Name")

    def test_04_report_layer_sync_geometry_type(self):
        """Test layer geometry type is synced with report."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        report = self.env["spp.gis.report"].create(
            {
                "name": "Geometry Sync Test",
                "code": "geom_sync_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "geometry_type": "polygon",
                "auto_create_layer": True,
            }
        )

        self.assertEqual(report.layer_id.geometry_type, "polygon")

        # Change geometry type
        report.write({"geometry_type": "heatmap"})

        self.assertEqual(report.layer_id.geometry_type, "heatmap")

    def test_05_report_layer_deleted_on_disable(self):
        """Test layer is deleted when auto_create_layer is disabled."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        report = self.env["spp.gis.report"].create(
            {
                "name": "Delete Layer Test",
                "code": "delete_layer_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "auto_create_layer": True,
            }
        )

        layer_id = report.layer_id.id
        self.assertTrue(layer_id)

        # Disable auto-create
        report.write({"auto_create_layer": False})

        # Layer should be deleted
        self.assertFalse(self.env["spp.gis.data.layer"].browse(layer_id).exists())

    def test_06_report_action_sync_layer(self):
        """Test manual layer sync action."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        report = self.env["spp.gis.report"].create(
            {
                "name": "Manual Sync Test",
                "code": "manual_sync_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "auto_create_layer": True,
            }
        )

        # Call sync action
        result = report.action_sync_layer()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")

    def test_07_report_geometry_type_options(self):
        """Test all geometry type options are valid."""
        geometry_types = ["polygon", "point", "cluster", "heatmap"]

        for geom_type in geometry_types:
            report = self.env["spp.gis.report"].create(
                {
                    "name": f"Geom Type {geom_type}",
                    "code": f"geom_type_{geom_type}",
                    "category_id": self.category.id,
                    "source_model_id": self.partner_model.id,
                    "area_field_path": "area_id",
                    "aggregation_method": "count",
                    "normalization_method": "raw",
                    "base_area_level": 2,
                    "geometry_type": geom_type,
                    "auto_create_layer": False,
                }
            )

            self.assertEqual(report.geometry_type, geom_type)
            report.unlink()

    def test_08_layer_cascade_delete(self):
        """Test layer is deleted when report is deleted."""
        if not self.gis_view or not self.geo_field:
            self.skipTest("GIS view or geo field not available")

        report = self.env["spp.gis.report"].create(
            {
                "name": "Cascade Delete Test",
                "code": "cascade_delete_test",
                "category_id": self.category.id,
                "source_model_id": self.partner_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "normalization_method": "raw",
                "base_area_level": 2,
                "auto_create_layer": True,
            }
        )

        layer_id = report.layer_id.id
        self.assertTrue(layer_id)

        # Delete report
        report.unlink()

        # Layer should be deleted via cascade
        self.assertFalse(self.env["spp.gis.data.layer"].browse(layer_id).exists())
