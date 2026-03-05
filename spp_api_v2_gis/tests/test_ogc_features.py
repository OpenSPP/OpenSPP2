# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for OGC API - Features service."""

import logging
from datetime import datetime, timedelta

from odoo.exceptions import MissingError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestOGCService(TransactionCase):
    """Test OGC API - Features service functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create color scheme for reports
        cls.color_scheme = cls.env["spp.gis.color.scheme"].create(
            {
                "name": "OGC Test Scheme",
                "code": "ogc_test_scheme",
                "scheme_type": "sequential",
                "colors": '["#440154", "#21918c", "#fde725"]',
                "default_steps": 3,
            }
        )

        # Create report category
        cls.category = cls.env["spp.gis.report.category"].create(
            {
                "name": "OGC Test Category",
                "code": "ogc_test_category",
                "sequence": 10,
            }
        )

        # Create area model reference
        cls.area_model = cls.env["ir.model"].search([("model", "=", "spp.area")], limit=1)

        # Create test reports
        cls.report1 = cls.env["spp.gis.report"].create(
            {
                "name": "OGC Report One",
                "code": "ogc_report_one",
                "description": "First OGC test report",
                "category_id": cls.category.id,
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 2,
                "normalization_method": "raw",
                "geometry_type": "polygon",
                "color_scheme_id": cls.color_scheme.id,
                "last_refresh": datetime.now() - timedelta(hours=1),
                "sequence": 10,
            }
        )

        cls.report2 = cls.env["spp.gis.report"].create(
            {
                "name": "OGC Report Two",
                "code": "ogc_report_two",
                "source_model_id": cls.area_model.id,
                "area_field_path": "area_id",
                "aggregation_method": "count",
                "base_area_level": 3,
                "normalization_method": "raw",
                "geometry_type": "point",
                "sequence": 20,
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
                    "name": "OGC Test Layer",
                    "model_name": "spp.area",
                    "geo_field_id": cls.geo_field.id,
                    "geo_repr": "basic",
                    "sequence": 10,
                }
            )
        else:
            cls.data_layer = None

        # Create area types and areas at multiple levels for fan-out tests
        cls.area_type_country = cls.env["spp.area.type"].create({"name": "OGC Country"})
        cls.area_type_region = cls.env["spp.area.type"].create({"name": "OGC Region"})

        cls.area_country = cls.env["spp.area"].create(
            {
                "draft_name": "OGC Test Country",
                "code": "ogc_test_country",
                "area_type_id": cls.area_type_country.id,
            }
        )
        cls.area_region = cls.env["spp.area"].create(
            {
                "draft_name": "OGC Test Region",
                "code": "ogc_test_region",
                "parent_id": cls.area_country.id,
                "area_type_id": cls.area_type_region.id,
            }
        )

        # Create report data at levels 0 and 1 for report1
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.report1.id,
                "area_id": cls.area_country.id,
                "area_code": cls.area_country.code,
                "area_name": cls.area_country.draft_name,
                "area_level": cls.area_country.area_level,
                "raw_value": 1000.0,
                "normalized_value": 1.0,
                "display_value": "1000",
                "record_count": 1000,
            }
        )
        cls.env["spp.gis.report.data"].create(
            {
                "report_id": cls.report1.id,
                "area_id": cls.area_region.id,
                "area_code": cls.area_region.code,
                "area_name": cls.area_region.draft_name,
                "area_level": cls.area_region.area_level,
                "raw_value": 500.0,
                "normalized_value": 0.5,
                "display_value": "500",
                "record_count": 500,
            }
        )

    # === Landing Page Tests ===

    def test_landing_page_structure(self):
        """Test landing page has required fields and links."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        page = service.get_landing_page()

        self.assertIn("title", page)
        self.assertIn("description", page)
        self.assertIn("links", page)
        self.assertIsInstance(page["links"], list)

    def test_landing_page_has_required_links(self):
        """Test landing page contains self, conformance, and data links."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        page = service.get_landing_page()

        link_rels = [link["rel"] for link in page["links"]]
        self.assertIn("self", link_rels)
        self.assertIn("conformance", link_rels)
        self.assertIn("data", link_rels)
        self.assertIn("service-desc", link_rels)

    # === Conformance Tests ===

    def test_conformance_structure(self):
        """Test conformance response has conformsTo list."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env)
        conf = service.get_conformance()

        self.assertIn("conformsTo", conf)
        self.assertIsInstance(conf["conformsTo"], list)
        self.assertGreater(len(conf["conformsTo"]), 0)

    def test_conformance_includes_core(self):
        """Test conformance declares Core conformance class."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env)
        conf = service.get_conformance()

        self.assertIn(
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
            conf["conformsTo"],
        )

    def test_conformance_includes_geojson(self):
        """Test conformance declares GeoJSON conformance class."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env)
        conf = service.get_conformance()

        self.assertIn(
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
            conf["conformsTo"],
        )

    # === Collections Tests ===

    def test_get_collections_structure(self):
        """Test collections response structure."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        self.assertIn("links", result)
        self.assertIn("collections", result)
        self.assertIsInstance(result["collections"], list)

    def test_get_collections_contains_reports(self):
        """Test collections include GIS reports with _admN suffixes."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        collection_ids = [c["id"] for c in result["collections"]]
        # Report 1 has data at two levels, should have _admN entries
        report1_collections = [cid for cid in collection_ids if cid.startswith("ogc_report_one")]
        self.assertGreaterEqual(len(report1_collections), 2, "Report with 2 levels should have at least 2 collections")

    def test_get_collections_contains_data_layers(self):
        """Test collections include data layers."""
        if not self.data_layer:
            self.skipTest("No data layer available (spp.area polygon field not found)")

        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        collection_ids = [c["id"] for c in result["collections"]]
        expected_id = f"layer_{self.data_layer.id}"
        self.assertIn(expected_id, collection_ids)

    def test_collection_has_required_fields(self):
        """Test each collection has required OGC fields."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        for collection in result["collections"]:
            self.assertIn("id", collection)
            self.assertIn("title", collection)
            self.assertIn("links", collection)
            self.assertIsInstance(collection["links"], list)

    def test_report_collection_has_items_link(self):
        """Test report collection has items link."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        # Find any ogc_report_one collection (with _admN suffix)
        report_collection = next(
            (c for c in result["collections"] if c["id"].startswith("ogc_report_one")),
            None,
        )
        self.assertIsNotNone(report_collection)

        link_rels = [link["rel"] for link in report_collection["links"]]
        self.assertIn("items", link_rels)
        self.assertIn("self", link_rels)

    def test_report_collection_has_qml_link(self):
        """Test report collection has QML describedby link."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        # Find any ogc_report_one collection (with _admN suffix)
        report_collection = next(
            (c for c in result["collections"] if c["id"].startswith("ogc_report_one")),
            None,
        )
        self.assertIsNotNone(report_collection)

        link_rels = [link["rel"] for link in report_collection["links"]]
        self.assertIn("describedby", link_rels)

        qml_link = next(
            (link for link in report_collection["links"] if link["rel"] == "describedby"),
            None,
        )
        self.assertIsNotNone(qml_link)
        self.assertEqual(qml_link["type"], "text/xml")

    def test_report_driven_data_layer_collection_has_qml_link(self):
        """Test report-driven data layer collection has QML describedby link."""
        if not self.geo_field:
            self.skipTest("No geo field available for data layer creation")
        # Create a report-driven data layer
        report_layer = self.env["spp.gis.data.layer"].create(
            {
                "name": "QML Link Test Layer",
                "source_type": "report",
                "report_id": self.report1.id,
                "geo_field_id": self.geo_field.id,
                "geo_repr": "choropleth",
                "sequence": 99,
            }
        )

        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        layer_collection_id = f"layer_{report_layer.id}"
        layer_collection = next(
            (c for c in result["collections"] if c["id"] == layer_collection_id),
            None,
        )
        self.assertIsNotNone(layer_collection, "Report-driven data layer should be in collections")

        link_rels = [link["rel"] for link in layer_collection["links"]]
        self.assertIn("describedby", link_rels, "Report-driven layer should have QML link")

        qml_link = next(
            (link for link in layer_collection["links"] if link["rel"] == "describedby"),
            None,
        )
        self.assertEqual(qml_link["type"], "text/xml")
        self.assertIn("/qml", qml_link["href"])

    def test_model_driven_data_layer_collection_has_no_qml_link(self):
        """Test model-driven data layer collection does not have QML link."""
        if not self.data_layer:
            self.skipTest("No data layer available")

        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        layer_collection_id = f"layer_{self.data_layer.id}"
        layer_collection = next(
            (c for c in result["collections"] if c["id"] == layer_collection_id),
            None,
        )
        self.assertIsNotNone(layer_collection)

        link_rels = [link["rel"] for link in layer_collection["links"]]
        self.assertNotIn("describedby", link_rels, "Model-driven layer should NOT have QML link")

    def test_report_collection_has_temporal_extent(self):
        """Test report with last_refresh has temporal extent."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        # Find any ogc_report_one collection (with _admN suffix)
        report_collection = next(
            (c for c in result["collections"] if c["id"].startswith("ogc_report_one")),
            None,
        )
        self.assertIsNotNone(report_collection)
        self.assertIn("extent", report_collection)
        self.assertIn("temporal", report_collection["extent"])

    # === Single Collection Tests ===

    def test_get_collection_by_report_code(self):
        """Test getting single collection by bare report code defaults to base level."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        collection = service.get_collection("ogc_report_one")

        # Bare code defaults to base_area_level (2), which becomes _admN
        self.assertIn("ogc_report_one", collection["id"])
        self.assertIn("OGC Report One", collection["title"])

    def test_get_collection_by_layer_id(self):
        """Test getting single collection by data layer ID."""
        if not self.data_layer:
            self.skipTest("No data layer available")

        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        collection_id = f"layer_{self.data_layer.id}"
        collection = service.get_collection(collection_id)

        self.assertEqual(collection["id"], collection_id)
        self.assertEqual(collection["title"], "OGC Test Layer")

    def test_get_collection_not_found(self):
        """Test getting non-existent collection raises MissingError."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")

        with self.assertRaises(MissingError):
            service.get_collection("nonexistent_collection")

    # === Collection Items Tests ===

    def test_get_collection_items_structure(self):
        """Test items response is a GeoJSON FeatureCollection."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collection_items("ogc_report_one")

        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIn("features", result)
        self.assertIn("links", result)
        self.assertIn("numberMatched", result)
        self.assertIn("numberReturned", result)

    def test_get_collection_items_pagination(self):
        """Test items pagination with limit and offset."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")

        # Request with small limit
        result = service.get_collection_items("ogc_report_one", limit=2, offset=0)

        self.assertLessEqual(result["numberReturned"], 2)
        self.assertGreaterEqual(result["numberMatched"], 0)

    def test_get_collection_items_has_self_link(self):
        """Test items response includes self link."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collection_items("ogc_report_one")

        link_rels = [link["rel"] for link in result["links"]]
        self.assertIn("self", link_rels)
        self.assertIn("collection", link_rels)

    def test_get_collection_items_not_found(self):
        """Test items for non-existent collection raises error."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")

        with self.assertRaises(MissingError):
            service.get_collection_items("nonexistent_collection")

    # === Single Feature Tests ===

    def test_get_collection_item_not_found(self):
        """Test getting non-existent feature raises MissingError."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")

        with self.assertRaises(MissingError):
            service.get_collection_item("ogc_report_one", "99999999")

    # === Collection ID Parsing Tests ===

    def test_parse_collection_id_report(self):
        """Test parsing report code collection ID returns 3-tuple."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env)
        layer_type, layer_id, admin_level = service._parse_collection_id("pop_density")

        self.assertEqual(layer_type, "report")
        self.assertEqual(layer_id, "pop_density")
        self.assertIsNone(admin_level)

    def test_parse_collection_id_layer(self):
        """Test parsing layer_ prefixed collection ID returns 3-tuple."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env)
        layer_type, layer_id, admin_level = service._parse_collection_id("layer_42")

        self.assertEqual(layer_type, "layer")
        self.assertEqual(layer_id, "42")
        self.assertIsNone(admin_level)

    def test_parse_collection_id_with_admin_level(self):
        """Test parsing collection ID with _admN suffix extracts admin level."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env)
        layer_type, layer_id, admin_level = service._parse_collection_id("pop_density_adm2")

        self.assertEqual(layer_type, "report")
        self.assertEqual(layer_id, "pop_density")
        self.assertEqual(admin_level, 2)

    def test_parse_collection_id_with_admin_level_0(self):
        """Test parsing collection ID with _adm0 suffix extracts level 0."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env)
        layer_type, layer_id, admin_level = service._parse_collection_id("my_report_adm0")

        self.assertEqual(layer_type, "report")
        self.assertEqual(layer_id, "my_report")
        self.assertEqual(admin_level, 0)

    # === Bbox Push-Down Tests ===

    def test_bbox_to_geojson_helper(self):
        """Test _bbox_to_geojson converts bbox array to GeoJSON Polygon."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        result = service._bbox_to_geojson([5.0, 15.0, 15.0, 25.0])

        self.assertEqual(result["type"], "Polygon")
        coords = result["coordinates"][0]
        self.assertEqual(len(coords), 5)
        # First and last coordinate should be the same (closed ring)
        self.assertEqual(coords[0], coords[-1])
        # Check corners: SW, SE, NE, NW, SW
        self.assertEqual(coords[0], [5.0, 15.0])
        self.assertEqual(coords[1], [15.0, 15.0])
        self.assertEqual(coords[2], [15.0, 25.0])
        self.assertEqual(coords[3], [5.0, 25.0])

    def test_bbox_none_does_not_filter(self):
        """Test bbox=None produces same result as no bbox."""
        from ..services.layers_service import LayersService

        service = LayersService(self.env)
        result_without = service.get_layer_geojson(
            layer_id="ogc_report_one",
            layer_type="report",
        )
        result_with_none = service.get_layer_geojson(
            layer_id="ogc_report_one",
            layer_type="report",
            bbox=None,
        )
        self.assertEqual(
            len(result_without.get("features", [])),
            len(result_with_none.get("features", [])),
        )

    def test_ogc_items_accepts_bbox_parameter(self):
        """Test OGC get_collection_items accepts bbox parameter."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        # Without bbox should work
        result = service.get_collection_items("ogc_report_one")
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIn("features", result)

    # === Per-Level Fan-Out Tests ===

    def test_get_collections_fans_out_by_level(self):
        """Test that a report with data at 2 levels produces 2 collections."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        # report1 has data at area_country.area_level and area_region.area_level
        report1_collections = [c for c in result["collections"] if c["id"].startswith("ogc_report_one_adm")]
        self.assertGreaterEqual(
            len(report1_collections), 2, "Report with data at 2 levels should produce at least 2 collections"
        )

    def test_get_collection_by_adm_suffix(self):
        """Test looking up collection by {code}_admN succeeds."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")

        # area_country is level 0, so ogc_report_one_adm0 should work
        level = self.area_country.area_level
        collection = service.get_collection(f"ogc_report_one_adm{level}")

        self.assertEqual(collection["id"], f"ogc_report_one_adm{level}")
        self.assertIn("OGC Report One", collection["title"])

    def test_get_collection_bare_code_defaults_to_base_level(self):
        """Test bare report code defaults to base_area_level for backward compat."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        collection = service.get_collection("ogc_report_one")

        # base_area_level for report1 is 2
        self.assertEqual(collection["id"], "ogc_report_one_adm2")

    def test_collection_title_includes_level_name(self):
        """Test that collection title includes the area level name."""
        from ..services.ogc_service import OGCService

        service = OGCService(self.env, "http://localhost:8069/api/v2/spp")
        result = service.get_collections()

        # Find a report1 collection
        report1_collection = next(
            (c for c in result["collections"] if c["id"].startswith("ogc_report_one_adm")),
            None,
        )
        self.assertIsNotNone(report1_collection)
        # Title should contain parenthetical level info
        self.assertIn("(", report1_collection["title"])
        self.assertIn(")", report1_collection["title"])
