# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for layers service."""

import logging

from odoo import fields
from odoo.exceptions import MissingError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestLayersService(TransactionCase):
    """Test layers service functionality."""

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

        # Create area model reference
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)

        # Create test report
        cls.report = cls.env["spp.gis.report"].create(
            {
                "name": "Test Layers Report",
                "code": "test_layers_report",
                "description": "Test report for layers",
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

        # Create thresholds for styling
        cls.env["spp.gis.report.threshold"].create(
            {
                "report_id": cls.report.id,
                "sequence": 10,
                "min_value": 0,
                "max_value": 10,
                "color": "#440154",
                "label": "Low",
            }
        )
        cls.env["spp.gis.report.threshold"].create(
            {
                "report_id": cls.report.id,
                "sequence": 20,
                "min_value": 10,
                "max_value": 50,
                "color": "#21918c",
                "label": "Medium",
            }
        )

        # Create test areas for filtering
        cls.parent_area = cls.env["spp.area"].create(
            {
                "draft_name": "Test Parent Area",
                "code": "test_parent",
                "level": 1,
            }
        )

        cls.child_area1 = cls.env["spp.area"].create(
            {
                "draft_name": "Test Child Area 1",
                "code": "test_child_1",
                "level": 2,
                "parent_id": cls.parent_area.id,
            }
        )

        cls.child_area2 = cls.env["spp.area"].create(
            {
                "draft_name": "Test Child Area 2",
                "code": "test_child_2",
                "level": 2,
                "parent_id": cls.parent_area.id,
            }
        )

        # Create data layer if geo field exists
        cls.geo_field = cls.env["ir.model.fields"].search(
            [("model", "=", "spp.area"), ("name", "=", "polygon")],
            limit=1,
        )
        if cls.geo_field:
            cls.data_layer = cls.env["spp.gis.data.layer"].create(
                {
                    "name": "Test Areas Layer",
                    "model_name": "spp.area",
                    "geo_field_id": cls.geo_field.id,
                    "geo_repr": "basic",
                    "domain": "[('level', '=', 2)]",
                }
            )
        else:
            cls.data_layer = None

    def test_get_report_layer_as_geojson(self):
        """Test getting report layer as GeoJSON."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id="test_layers_report",
            layer_type="report",
        )

        # Verify GeoJSON structure
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertIn("features", geojson)
        self.assertIn("metadata", geojson)
        self.assertIn("styling", geojson)

        # Verify metadata
        metadata = geojson["metadata"]
        self.assertIn("styling", metadata)

        # Verify styling hints
        styling = geojson["styling"]
        self.assertEqual(styling["geometry_type"], "polygon")
        self.assertEqual(styling["threshold_mode"], "manual")
        self.assertIn("color_scheme", styling)
        self.assertIn("thresholds", styling)
        self.assertGreaterEqual(len(styling["thresholds"]), 2)

    def test_get_report_layer_invalid_code(self):
        """Test getting report with invalid code raises error."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)

        with self.assertRaises(MissingError) as context:
            service.get_layer_geojson(
                layer_id="nonexistent_report",
                layer_type="report",
            )

        self.assertIn("not found", str(context.exception))

    def test_get_report_layer_filter_by_admin_level(self):
        """Test filtering report by admin level."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id="test_layers_report",
            layer_type="report",
            admin_level=2,
        )

        # Verify request completes successfully
        self.assertEqual(geojson["type"], "FeatureCollection")

    def test_get_report_layer_filter_by_area_codes(self):
        """Test filtering report by area codes."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id="test_layers_report",
            layer_type="report",
            area_codes=["test_child_1", "test_child_2"],
        )

        # Verify request completes successfully
        self.assertEqual(geojson["type"], "FeatureCollection")

    def test_get_report_layer_filter_by_parent_area(self):
        """Test filtering report by parent area code."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id="test_layers_report",
            layer_type="report",
            parent_area_code="test_parent",
        )

        # Verify request completes successfully
        self.assertEqual(geojson["type"], "FeatureCollection")

    def test_get_report_layer_without_geometry(self):
        """Test getting report without geometry."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id="test_layers_report",
            layer_type="report",
            include_geometry=False,
        )

        # Verify request completes successfully
        self.assertEqual(geojson["type"], "FeatureCollection")

    def test_get_data_layer_as_geojson(self):
        """Test getting data layer as GeoJSON."""
        if not self.data_layer:
            self.skipTest("No data layer available (spp.area polygon field not found)")

        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id=str(self.data_layer.id),
            layer_type="layer",
        )

        # Verify GeoJSON structure
        self.assertEqual(geojson["type"], "FeatureCollection")
        self.assertIn("features", geojson)
        self.assertIn("metadata", geojson)

        # Verify metadata
        metadata = geojson["metadata"]
        self.assertIn("layer", metadata)
        layer_info = metadata["layer"]
        self.assertEqual(layer_info["name"], "Test Areas Layer")
        self.assertEqual(layer_info["model"], "spp.area")

    def test_get_data_layer_invalid_id(self):
        """Test getting data layer with invalid ID raises error."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)

        # Test with non-existent numeric ID
        with self.assertRaises(MissingError):
            service.get_layer_geojson(
                layer_id="99999",
                layer_type="layer",
            )

    def test_get_data_layer_invalid_id_format(self):
        """Test getting data layer with invalid ID format raises error."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)

        # Test with non-numeric ID
        with self.assertRaises(ValueError):
            service.get_layer_geojson(
                layer_id="not_a_number",
                layer_type="layer",
            )

    def test_invalid_layer_type(self):
        """Test invalid layer_type parameter raises error."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)

        with self.assertRaises(ValueError) as context:
            service.get_layer_geojson(
                layer_id="test_layers_report",
                layer_type="invalid_type",
            )

        self.assertIn("Invalid layer_type", str(context.exception))
        self.assertIn("Must be 'report' or 'layer'", str(context.exception))

    def test_resolve_area_codes_to_ids(self):
        """Test resolving area codes to IDs."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        area_ids = service._resolve_area_codes(["test_child_1", "test_child_2"])

        self.assertIsNotNone(area_ids)
        self.assertIn(self.child_area1.id, area_ids)
        self.assertIn(self.child_area2.id, area_ids)

    def test_resolve_area_codes_empty_list(self):
        """Test resolving empty area codes list returns None."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        area_ids = service._resolve_area_codes([])

        self.assertIsNone(area_ids)

    def test_resolve_area_codes_none(self):
        """Test resolving None area codes returns None."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        area_ids = service._resolve_area_codes(None)

        self.assertIsNone(area_ids)

    def test_resolve_area_codes_nonexistent(self):
        """Test resolving nonexistent area codes returns None."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        area_ids = service._resolve_area_codes(["nonexistent_code"])

        # Should return None when no areas found
        self.assertIsNone(area_ids)

    def test_build_report_styling_with_color_scheme(self):
        """Test building styling from report with color scheme."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        styling = service._build_report_styling(self.report)

        # Verify styling structure
        self.assertEqual(styling["geometry_type"], "polygon")
        self.assertEqual(styling["threshold_mode"], "manual")
        self.assertIsNotNone(styling["color_scheme"])
        self.assertEqual(styling["color_scheme"]["code"], "test_viridis")
        self.assertGreaterEqual(len(styling["thresholds"]), 2)

        # Verify thresholds
        threshold1 = styling["thresholds"][0]
        self.assertEqual(threshold1["min_value"], 0)
        self.assertEqual(threshold1["max_value"], 10)
        self.assertEqual(threshold1["color"], "#440154")
        self.assertEqual(threshold1["label"], "Low")

    def test_build_report_styling_without_color_scheme(self):
        """Test building styling from report using default color scheme."""
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
            }
        )

        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        styling = service._build_report_styling(report)

        # Verify styling structure
        self.assertEqual(styling["geometry_type"], "point")
        # Should use default color scheme (not None)
        self.assertIsNotNone(styling["color_scheme"])
        self.assertIn("code", styling["color_scheme"])
        self.assertEqual(len(styling["thresholds"]), 0)

    def test_build_layer_styling(self):
        """Test building styling from data layer."""
        if not self.data_layer:
            self.skipTest("No data layer available")

        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        styling = service._build_layer_styling(self.data_layer)

        # Verify styling structure
        self.assertIn("geometry_type", styling)
        self.assertEqual(styling["representation"], "basic")

    def test_fetch_layer_features_limit(self):
        """Test that fetching layer features respects limit."""
        if not self.data_layer:
            self.skipTest("No data layer available")

        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        features = service._fetch_layer_features(self.data_layer, include_geometry=True)

        # Should not exceed 5000 features
        self.assertLessEqual(len(features), 5000)

    def test_fetch_layer_features_without_geometry(self):
        """Test fetching layer features without geometry."""
        if not self.data_layer:
            self.skipTest("No data layer available")

        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        features = service._fetch_layer_features(self.data_layer, include_geometry=False)

        # Verify features have no geometry
        for feature in features:
            self.assertIsNone(feature["geometry"])

    def test_color_scheme_in_styling(self):
        """Test color scheme is included in styling."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id="test_layers_report",
            layer_type="report",
        )

        # Verify color scheme in styling
        styling = geojson["styling"]
        self.assertIsNotNone(styling["color_scheme"])
        self.assertEqual(styling["color_scheme"]["code"], "test_viridis")
        self.assertEqual(styling["color_scheme"]["name"], "Test Viridis")
        self.assertEqual(styling["color_scheme"]["type"], "sequential")

    def test_thresholds_in_styling(self):
        """Test thresholds are included in styling."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        geojson = service.get_layer_geojson(
            layer_id="test_layers_report",
            layer_type="report",
        )

        # Verify thresholds in styling
        styling = geojson["styling"]
        self.assertGreaterEqual(len(styling["thresholds"]), 2)

        # Verify threshold structure
        threshold = styling["thresholds"][0]
        self.assertIn("min_value", threshold)
        self.assertIn("max_value", threshold)
        self.assertIn("color", threshold)
        self.assertIn("label", threshold)

    def test_get_feature_count_with_admin_level(self):
        """Test get_feature_count filters by admin_level when provided."""
        # Create report data at specific levels
        area_type_1 = self.env["spp.area.type"].create({"name": "LS Country"})
        area_type_2 = self.env["spp.area.type"].create({"name": "LS Region"})

        area_l0 = self.env["spp.area"].create(
            {
                "draft_name": "LS Feature Count Country",
                "code": "ls_fc_country",
                "area_type_id": area_type_1.id,
            }
        )
        area_l1 = self.env["spp.area"].create(
            {
                "draft_name": "LS Feature Count Region",
                "code": "ls_fc_region",
                "parent_id": area_l0.id,
                "area_type_id": area_type_2.id,
            }
        )

        self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": area_l0.id,
                "area_code": area_l0.code,
                "area_name": area_l0.draft_name,
                "area_level": area_l0.area_level,
                "raw_value": 100.0,
                "normalized_value": 1.0,
                "display_value": "100",
                "record_count": 100,
            }
        )
        self.env["spp.gis.report.data"].create(
            {
                "report_id": self.report.id,
                "area_id": area_l1.id,
                "area_code": area_l1.code,
                "area_name": area_l1.draft_name,
                "area_level": area_l1.area_level,
                "raw_value": 50.0,
                "normalized_value": 0.5,
                "display_value": "50",
                "record_count": 50,
            }
        )

        from ..services.layers_service import LayersService

        service = LayersService(self.env)

        # Count with specific admin level should be less than total
        total_count = service.get_feature_count("test_layers_report", "report")
        level0_count = service.get_feature_count("test_layers_report", "report", admin_level=area_l0.area_level)
        level1_count = service.get_feature_count("test_layers_report", "report", admin_level=area_l1.area_level)

        self.assertGreater(total_count, 0)
        self.assertGreater(level0_count, 0)
        self.assertGreater(level1_count, 0)
        # Filtered counts should be less than or equal to total
        self.assertLessEqual(level0_count, total_count)
        self.assertLessEqual(level1_count, total_count)

    def test_get_feature_count_without_admin_level(self):
        """Test get_feature_count returns total count when no admin_level."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        count = service.get_feature_count("test_layers_report", "report")
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    # ------------------------------------------------------------------
    # Module-level coordinate/bbox helpers
    # ------------------------------------------------------------------
    def test_extract_all_coordinates_geometry_types(self):
        """Coordinates are extracted from every supported geometry type."""
        from ..services.layers_service import _extract_all_coordinates

        self.assertEqual(_extract_all_coordinates({"type": "Point", "coordinates": [1, 2]}), [[1, 2]])
        self.assertEqual(
            _extract_all_coordinates({"type": "MultiPoint", "coordinates": [[1, 2], [3, 4]]}),
            [[1, 2], [3, 4]],
        )
        self.assertEqual(
            _extract_all_coordinates({"type": "LineString", "coordinates": [[1, 2], [3, 4]]}),
            [[1, 2], [3, 4]],
        )
        polygon = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}
        self.assertEqual(len(_extract_all_coordinates(polygon)), 4)
        multilinestring = {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}
        self.assertEqual(len(_extract_all_coordinates(multilinestring)), 4)
        multipolygon = {
            "type": "MultiPolygon",
            "coordinates": [[[[0, 0], [1, 0], [0, 0]]], [[[2, 2], [3, 2], [2, 2]]]],
        }
        self.assertEqual(len(_extract_all_coordinates(multipolygon)), 6)

    def test_extract_all_coordinates_empty_or_unknown(self):
        """Empty coordinates or unknown geometry types yield an empty list."""
        from ..services.layers_service import _extract_all_coordinates

        self.assertEqual(_extract_all_coordinates({"type": "Point", "coordinates": None}), [])
        self.assertEqual(_extract_all_coordinates({"type": "GeometryCollection", "coordinates": [[1, 2]]}), [])

    def test_bbox_to_geojson(self):
        """A bbox is converted to a closed GeoJSON polygon ring."""
        from ..services.layers_service import LayersService

        geometry = LayersService(self.env)._bbox_to_geojson([0, 1, 2, 3])
        self.assertEqual(geometry["type"], "Polygon")
        ring = geometry["coordinates"][0]
        self.assertEqual(len(ring), 5)
        self.assertEqual(ring[0], [0, 1])
        self.assertEqual(ring[0], ring[-1])

    # ------------------------------------------------------------------
    # Feature count / feature-by-id
    # ------------------------------------------------------------------
    def _make_report_data(self, **overrides):
        vals = {
            "report_id": self.report.id,
            "area_id": self.child_area1.id,
            "area_code": self.child_area1.code,
            "area_name": "Test Child Area 1",
            "area_level": 2,
            "raw_value": 5.0,
            "normalized_value": 0.5,
            "display_value": "5",
            "record_count": 5,
            "bucket_index": 0,
            "bucket_color": "#440154",
            "bucket_label": "Low",
            "computed_at": fields.Datetime.now(),
        }
        vals.update(overrides)
        return self.env["spp.gis.report.data"].create(vals)

    def test_get_feature_count_report(self):
        """Report feature count honours the optional admin-level filter."""
        from ..services.layers_service import LayersService

        data = self._make_report_data()
        service = LayersService(self.env)
        self.assertEqual(service.get_feature_count("test_layers_report", layer_type="report"), 1)
        # area_level is related to area_id.area_level; use the record's actual value.
        self.assertEqual(
            service.get_feature_count("test_layers_report", layer_type="report", admin_level=data.area_level), 1
        )
        self.assertEqual(
            service.get_feature_count("test_layers_report", layer_type="report", admin_level=data.area_level + 99), 0
        )

    def test_get_feature_count_report_not_found(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(MissingError):
            LayersService(self.env).get_feature_count("nonexistent", layer_type="report")

    def test_get_feature_count_layer(self):
        if not self.data_layer:
            self.skipTest("No geo field available on spp.area")
        from ..services.layers_service import LayersService

        count = LayersService(self.env).get_feature_count(str(self.data_layer.id), layer_type="layer")
        self.assertIsInstance(count, int)

    def test_get_feature_count_layer_invalid_id(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(ValueError):
            LayersService(self.env).get_feature_count("not-an-int", layer_type="layer")

    def test_get_feature_count_layer_not_found(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(MissingError):
            LayersService(self.env).get_feature_count("999999", layer_type="layer")

    def test_get_feature_count_invalid_type(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(ValueError):
            LayersService(self.env).get_feature_count("x", layer_type="bogus")

    def test_get_feature_by_id_invalid_type(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(ValueError):
            LayersService(self.env).get_feature_by_id("x", "y", layer_type="bogus")

    def test_get_report_feature_by_id(self):
        """A report feature is returned with properties and bucket range."""
        from ..services.layers_service import LayersService

        self._make_report_data()
        feature = LayersService(self.env).get_feature_by_id(
            "test_layers_report", self.child_area1.code, layer_type="report"
        )
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["id"], self.child_area1.code)
        self.assertEqual(feature["properties"]["area_code"], self.child_area1.code)
        self.assertTrue(feature["properties"]["has_data"])
        self.assertEqual(feature["properties"]["bucket"]["index"], 0)
        self.assertEqual(feature["properties"]["bucket"]["min_value"], 0)

    def test_get_report_feature_by_id_report_not_found(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(MissingError):
            LayersService(self.env).get_feature_by_id("nonexistent", "x", layer_type="report")

    def test_get_report_feature_by_id_feature_not_found(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(MissingError):
            LayersService(self.env).get_feature_by_id("test_layers_report", "no_such_area", layer_type="report")

    def test_get_layer_feature_by_id_success(self):
        if not self.data_layer:
            self.skipTest("No geo field available on spp.area")
        from ..services.layers_service import LayersService

        feature = LayersService(self.env).get_feature_by_id(
            str(self.data_layer.id), str(self.child_area1.id), layer_type="layer"
        )
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["id"], self.child_area1.id)
        self.assertEqual(feature["properties"]["id"], self.child_area1.id)

    def test_get_layer_feature_by_id_layer_not_found(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(MissingError):
            LayersService(self.env).get_feature_by_id("999999", "1", layer_type="layer")

    def test_get_layer_feature_by_id_invalid_layer_id(self):
        from ..services.layers_service import LayersService

        with self.assertRaises(ValueError):
            LayersService(self.env).get_feature_by_id("not-int", "1", layer_type="layer")

    def test_get_layer_feature_by_id_feature_not_found(self):
        if not self.data_layer:
            self.skipTest("No geo field available on spp.area")
        from ..services.layers_service import LayersService

        with self.assertRaises(MissingError):
            LayersService(self.env).get_feature_by_id(str(self.data_layer.id), "999999", layer_type="layer")

    def test_get_layer_feature_by_id_invalid_feature_id(self):
        if not self.data_layer:
            self.skipTest("No geo field available on spp.area")
        from ..services.layers_service import LayersService

        with self.assertRaises(MissingError):
            LayersService(self.env).get_feature_by_id(str(self.data_layer.id), "not-int", layer_type="layer")


@tagged("post_install", "-at_install")
class TestBboxFeatureFilter(TransactionCase):
    """Test Python-level bbox filtering of GeoJSON features."""

    def test_filter_features_matching_bbox(self):
        """Test that features inside the bbox are kept."""
        from ..services.layers_service import filter_features_by_bbox

        features = [
            {
                "type": "Feature",
                "id": "manila",
                "properties": {"name": "Manila"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[120.9, 14.5], [121.1, 14.5], [121.1, 14.7], [120.9, 14.7], [120.9, 14.5]]],
                },
            },
        ]
        # bbox that fully contains Manila
        result = filter_features_by_bbox(features, [120.0, 14.0, 122.0, 15.0])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "manila")

    def test_filter_features_outside_bbox(self):
        """Test that features outside the bbox are excluded."""
        from ..services.layers_service import filter_features_by_bbox

        features = [
            {
                "type": "Feature",
                "id": "manila",
                "properties": {"name": "Manila"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[120.9, 14.5], [121.1, 14.5], [121.1, 14.7], [120.9, 14.7], [120.9, 14.5]]],
                },
            },
        ]
        # bbox far from Manila (in Europe)
        result = filter_features_by_bbox(features, [0.0, 40.0, 10.0, 50.0])
        self.assertEqual(len(result), 0)

    def test_filter_features_partial_overlap(self):
        """Test that features partially overlapping bbox are included."""
        from ..services.layers_service import filter_features_by_bbox

        features = [
            {
                "type": "Feature",
                "id": "manila",
                "properties": {"name": "Manila"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[120.9, 14.5], [121.1, 14.5], [121.1, 14.7], [120.9, 14.7], [120.9, 14.5]]],
                },
            },
        ]
        # bbox that partially overlaps Manila (cuts through it)
        result = filter_features_by_bbox(features, [121.0, 14.0, 122.0, 15.0])
        self.assertEqual(len(result), 1)

    def test_filter_features_null_geometry_excluded(self):
        """Test that features with null geometry are excluded."""
        from ..services.layers_service import filter_features_by_bbox

        features = [
            {
                "type": "Feature",
                "id": "no_geom",
                "properties": {"name": "No Geometry"},
                "geometry": None,
            },
        ]
        result = filter_features_by_bbox(features, [0.0, 0.0, 180.0, 90.0])
        self.assertEqual(len(result), 0)

    def test_filter_features_mixed(self):
        """Test filtering a mix of inside, outside, and null geometry features."""
        from ..services.layers_service import filter_features_by_bbox

        features = [
            {
                "type": "Feature",
                "id": "inside",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[121.0, 14.5], [121.2, 14.5], [121.2, 14.7], [121.0, 14.7], [121.0, 14.5]]],
                },
            },
            {
                "type": "Feature",
                "id": "outside",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1.0, 1.0], [2.0, 1.0], [2.0, 2.0], [1.0, 2.0], [1.0, 1.0]]],
                },
            },
            {
                "type": "Feature",
                "id": "null_geom",
                "properties": {},
                "geometry": None,
            },
        ]
        result = filter_features_by_bbox(features, [120.0, 14.0, 122.0, 15.0])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "inside")

    def test_filter_features_multipolygon(self):
        """Test bbox filtering works with MultiPolygon geometries."""
        from ..services.layers_service import filter_features_by_bbox

        features = [
            {
                "type": "Feature",
                "id": "multi",
                "properties": {},
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [[[121.0, 14.5], [121.2, 14.5], [121.2, 14.7], [121.0, 14.7], [121.0, 14.5]]],
                        [[[122.0, 15.0], [122.2, 15.0], [122.2, 15.2], [122.0, 15.2], [122.0, 15.0]]],
                    ],
                },
            },
        ]
        # bbox that contains only the first polygon
        result = filter_features_by_bbox(features, [120.0, 14.0, 121.5, 15.0])
        self.assertEqual(len(result), 1)

    def test_filter_features_empty_list(self):
        """Test filtering empty feature list returns empty."""
        from ..services.layers_service import filter_features_by_bbox

        result = filter_features_by_bbox([], [0.0, 0.0, 180.0, 90.0])
        self.assertEqual(len(result), 0)


@tagged("post_install", "-at_install")
class TestReportGeoJSONCache(TransactionCase):
    """Test report GeoJSON caching in LayersService."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)
        cls.report = cls.env["spp.gis.report"].create(
            {
                "name": "Cache Test Report",
                "code": "cache_test_report",
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
            }
        )

    def test_cache_hit_returns_same_data(self):
        """Test that cached report GeoJSON returns same features."""
        from ..services.layers_service import LayersService, _report_geojson_cache

        # Clear cache before test
        _report_geojson_cache.clear()

        service = LayersService(self.env)

        # First call populates cache
        geojson1 = service.get_layer_geojson(
            layer_id="cache_test_report",
            layer_type="report",
            admin_level=2,
        )

        # Second call should hit cache — verify same result
        geojson2 = service.get_layer_geojson(
            layer_id="cache_test_report",
            layer_type="report",
            admin_level=2,
        )

        self.assertEqual(len(geojson1["features"]), len(geojson2["features"]))
        self.assertEqual(geojson1["type"], geojson2["type"])

    def test_cache_populated_after_first_call(self):
        """Test that cache contains entry after first call."""
        from ..services.layers_service import LayersService, _report_geojson_cache

        _report_geojson_cache.clear()

        service = LayersService(self.env)
        service.get_layer_geojson(
            layer_id="cache_test_report",
            layer_type="report",
            admin_level=2,
        )

        # Cache should have an entry for this report+level
        self.assertGreater(len(_report_geojson_cache), 0)
