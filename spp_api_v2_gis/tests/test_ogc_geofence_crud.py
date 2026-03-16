# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for OGC API - Features Part 4: CRUD for Geofences.

Tests cover:
- Phase 1: Read path (collection discovery, GET items, GET single item)
- Phase 2: Write path (POST, PUT, DELETE)
"""

import json
import logging

from odoo.exceptions import MissingError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)

# Sample polygon covering a small area in Southeast Asia
SAMPLE_POLYGON = {
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

# Another polygon, shifted east
SAMPLE_POLYGON_2 = {
    "type": "Polygon",
    "coordinates": [
        [
            [102.0, 2.0],
            [103.0, 2.0],
            [103.0, 3.0],
            [102.0, 3.0],
            [102.0, 2.0],
        ]
    ],
}


@tagged("post_install", "-at_install")
class TestOGCGeofenceRead(TransactionCase):
    """Phase 1: Read path tests for geofence OGC collection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Geofence = cls.env["spp.gis.geofence"]

        cls.geofence1 = cls.Geofence.create(
            {
                "name": "OGC Read Test Area 1",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "area_of_interest",
                "created_from": "api",
            }
        )
        cls.geofence2 = cls.Geofence.create(
            {
                "name": "OGC Read Test Area 2",
                "geometry": json.dumps(SAMPLE_POLYGON_2),
                "geofence_type": "custom",
                "created_from": "ui",
            }
        )
        # Inactive geofence (soft-deleted)
        cls.geofence_inactive = cls.Geofence.create(
            {
                "name": "OGC Read Inactive",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "custom",
                "active": False,
            }
        )

    def _make_service(self, base_url="http://localhost:8069/api/v2/spp"):
        from ..services.ogc_service import OGCService

        return OGCService(self.env, base_url)

    # --- to_geojson top-level id ---

    def test_to_geojson_has_top_level_id(self):
        """to_geojson() must emit 'id' at the Feature top level (OGC Req 23)."""
        feature = self.geofence1.to_geojson()
        self.assertIn("id", feature)
        self.assertEqual(feature["id"], self.geofence1.uuid)

    # --- Collection discovery ---

    def test_collections_includes_geofences(self):
        """GET /collections must include a 'geofences' collection."""
        service = self._make_service()
        result = service.get_collections()

        ids = [c["id"] for c in result["collections"]]
        self.assertIn("geofences", ids)

    def test_geofences_collection_has_bbox(self):
        """Geofences collection metadata must include extent.spatial.bbox."""
        service = self._make_service()
        collection = service.get_collection("geofences")

        self.assertIn("extent", collection)
        self.assertIn("spatial", collection["extent"])
        self.assertIn("bbox", collection["extent"]["spatial"])
        bbox = collection["extent"]["spatial"]["bbox"][0]
        self.assertEqual(len(bbox), 4)
        # bbox should encompass both test geofences: lon 100..103, lat 0..3
        self.assertLessEqual(bbox[0], 100.0)  # west
        self.assertLessEqual(bbox[1], 0.0)  # south
        self.assertGreaterEqual(bbox[2], 103.0)  # east
        self.assertGreaterEqual(bbox[3], 3.0)  # north

    def test_geofences_collection_has_items_link(self):
        """Geofences collection must have an 'items' link."""
        service = self._make_service()
        collection = service.get_collection("geofences")

        link_rels = [link["rel"] for link in collection["links"]]
        self.assertIn("items", link_rels)
        self.assertIn("self", link_rels)

    # --- _parse_collection_id ---

    def test_parse_collection_id_geofences(self):
        """'geofences' must parse as ('geofence', None, None)."""
        service = self._make_service()
        layer_type, layer_id, admin_level = service._parse_collection_id("geofences")

        self.assertEqual(layer_type, "geofence")
        self.assertIsNone(layer_id)
        self.assertIsNone(admin_level)

    # --- GET items ---

    def test_get_items_returns_feature_collection(self):
        """GET items returns GeoJSON FeatureCollection with pagination."""
        service = self._make_service()
        result = service.get_collection_items("geofences")

        self.assertEqual(result["type"], "FeatureCollection")
        self.assertIn("numberMatched", result)
        self.assertIn("numberReturned", result)
        self.assertIn("features", result)
        self.assertGreaterEqual(result["numberMatched"], 2)

    def test_get_items_features_have_top_level_id(self):
        """Each feature in GET items must have a top-level 'id'."""
        service = self._make_service()
        result = service.get_collection_items("geofences")

        for feature in result["features"]:
            self.assertIn("id", feature)
            self.assertIsNotNone(feature["id"])

    def test_get_items_features_have_expected_properties(self):
        """Features must include all documented properties."""
        service = self._make_service()
        result = service.get_collection_items("geofences")

        self.assertGreater(len(result["features"]), 0)
        props = result["features"][0]["properties"]

        expected_keys = [
            "uuid",
            "name",
            "description",
            "geofence_type",
            "geofence_type_label",
            "area_sqkm",
            "tags",
            "created_from",
            "created_by",
            "create_date",
        ]
        for key in expected_keys:
            self.assertIn(key, props, f"Missing property: {key}")

    def test_get_items_excludes_inactive(self):
        """GET items must exclude inactive (soft-deleted) geofences by default."""
        service = self._make_service()
        result = service.get_collection_items("geofences")

        uuids = [f["id"] for f in result["features"]]
        self.assertNotIn(self.geofence_inactive.uuid, uuids)

    def test_get_items_pagination(self):
        """GET items respects limit and offset."""
        service = self._make_service()
        result = service.get_collection_items("geofences", limit=1, offset=0)

        self.assertEqual(result["numberReturned"], 1)
        self.assertGreaterEqual(result["numberMatched"], 2)

    def test_get_items_bbox_filter(self):
        """bbox filter returns only geofences intersecting the box."""
        service = self._make_service()
        # bbox covering only geofence1 (100-101, 0-1), not geofence2 (102-103, 2-3)
        result = service.get_collection_items("geofences", bbox=[99.5, -0.5, 101.5, 1.5])

        uuids = [f["id"] for f in result["features"]]
        self.assertIn(self.geofence1.uuid, uuids)
        self.assertNotIn(self.geofence2.uuid, uuids)

    def test_get_items_geofence_type_filter(self):
        """geofence_type filter returns only matching geofences."""
        service = self._make_service()
        result = service.get_collection_items("geofences", geofence_type="area_of_interest")

        for feature in result["features"]:
            self.assertEqual(feature["properties"]["geofence_type"], "area_of_interest")

    # --- GET single item ---

    def test_get_item_by_uuid(self):
        """GET single item by UUID returns the correct feature."""
        service = self._make_service()
        feature = service.get_collection_item("geofences", self.geofence1.uuid)

        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["id"], self.geofence1.uuid)
        self.assertEqual(feature["properties"]["name"], "OGC Read Test Area 1")

    def test_get_item_inactive_returns_404(self):
        """GET single inactive item returns MissingError (404)."""
        service = self._make_service()

        with self.assertRaises(MissingError):
            service.get_collection_item("geofences", self.geofence_inactive.uuid)

    def test_get_item_nonexistent_returns_404(self):
        """GET single item with bad UUID returns MissingError (404)."""
        service = self._make_service()

        with self.assertRaises(MissingError):
            service.get_collection_item("geofences", "nonexistent-uuid-12345")

    # --- Conformance ---

    def test_conformance_includes_crud_class(self):
        """Conformance must include OGC Features Part 4 create-replace-delete."""
        service = self._make_service()
        conf = service.get_conformance()

        self.assertIn(
            "http://www.opengis.net/spec/ogcapi-features-4/1.0/conf/create-replace-delete",
            conf["conformsTo"],
        )


@tagged("post_install", "-at_install")
class TestOGCGeofenceWrite(TransactionCase):
    """Phase 2: Write path tests for geofence OGC collection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Geofence = cls.env["spp.gis.geofence"]

        # Create a geofence to test PUT and DELETE on
        cls.existing_geofence = cls.Geofence.create(
            {
                "name": "OGC Write Existing",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "custom",
                "created_from": "api",
            }
        )

    def _make_service(self, base_url="http://localhost:8069/api/v2/spp"):
        from ..services.ogc_service import OGCService

        return OGCService(self.env, base_url)

    # --- POST (create) ---

    def test_post_creates_geofence(self):
        """POST creates a geofence and returns 201-style result."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON_2,
            "properties": {
                "name": "OGC POST Test",
                "geofence_type": "area_of_interest",
            },
        }

        result = service.create_geofence_feature(feature_input)

        self.assertEqual(result["feature"]["type"], "Feature")
        self.assertIn("id", result["feature"])
        self.assertEqual(result["feature"]["properties"]["name"], "OGC POST Test")
        self.assertEqual(result["feature"]["properties"]["created_from"], "api")
        self.assertIsNotNone(result["location"])

    def test_post_with_tags_resolves_or_creates(self):
        """POST with tags creates tag records if they don't exist."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {
                "name": "OGC POST Tags Test",
                "tags": ["ogc-tag-alpha", "ogc-tag-beta"],
            },
        }

        result = service.create_geofence_feature(feature_input)

        props = result["feature"]["properties"]
        self.assertIn("ogc-tag-alpha", props["tags"])
        self.assertIn("ogc-tag-beta", props["tags"])

    def test_post_with_incident_code(self):
        """POST with incident_code links to hazard incident."""
        # Create hazard incident
        category = self.env["spp.hazard.category"].create({"name": "OGC Test Cat", "code": "OGC_TEST_CAT"})
        self.env["spp.hazard.incident"].create(
            {
                "name": "OGC Test Flood",
                "code": "OGC-FLOOD-001",
                "category_id": category.id,
                "start_date": "2026-01-01",
            }
        )

        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {
                "name": "OGC POST Incident Test",
                "geofence_type": "hazard_zone",
                "incident_code": "OGC-FLOOD-001",
            },
        }

        result = service.create_geofence_feature(feature_input)

        props = result["feature"]["properties"]
        self.assertEqual(props["incident_id"], "OGC-FLOOD-001")
        self.assertEqual(props["incident_name"], "OGC Test Flood")

    def test_post_invalid_geofence_type_returns_error(self):
        """POST with invalid geofence_type raises ValueError with valid options."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {
                "name": "Bad Type Test",
                "geofence_type": "nonexistent_type",
            },
        }

        with self.assertRaises(ValueError) as cm:
            service.create_geofence_feature(feature_input)

        # Error message should list valid options
        self.assertIn("geofence_type", str(cm.exception))

    def test_post_invalid_geometry_type_returns_error(self):
        """POST with Point geometry raises ValueError."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [100.0, 0.0]},
            "properties": {"name": "Bad Geom Test"},
        }

        with self.assertRaises(ValueError) as cm:
            service.create_geofence_feature(feature_input)

        self.assertIn("Polygon", str(cm.exception))

    def test_post_missing_name_returns_error(self):
        """POST without 'name' property raises ValueError."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {},
        }

        with self.assertRaises(ValueError):
            service.create_geofence_feature(feature_input)

    # --- PUT (replace) ---

    def test_put_replaces_geofence(self):
        """PUT replaces geofence geometry and properties."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON_2,
            "properties": {
                "name": "OGC PUT Replaced",
                "geofence_type": "area_of_interest",
                "description": "Updated via PUT",
            },
        }

        result = service.replace_geofence_feature(self.existing_geofence.uuid, feature_input)

        self.assertEqual(result["type"], "Feature")
        self.assertEqual(result["properties"]["name"], "OGC PUT Replaced")
        self.assertEqual(result["properties"]["description"], "Updated via PUT")
        self.assertEqual(result["properties"]["geofence_type"], "area_of_interest")

    def test_put_recomputes_area(self):
        """PUT recomputes area_sqkm from the new geometry."""
        service = self._make_service()

        # Get original area
        original_area = self.existing_geofence.area_sqkm

        # Replace with a larger polygon
        large_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [100.0, 0.0],
                    [105.0, 0.0],
                    [105.0, 5.0],
                    [100.0, 5.0],
                    [100.0, 0.0],
                ]
            ],
        }
        feature_input = {
            "type": "Feature",
            "geometry": large_polygon,
            "properties": {
                "name": "OGC PUT Area Recompute",
            },
        }

        result = service.replace_geofence_feature(self.existing_geofence.uuid, feature_input)

        new_area = result["properties"]["area_sqkm"]
        self.assertGreater(new_area, original_area)

    def test_put_missing_feature_returns_error(self):
        """PUT on nonexistent UUID raises MissingError."""
        service = self._make_service()
        feature_input = {
            "type": "Feature",
            "geometry": SAMPLE_POLYGON,
            "properties": {"name": "No Such Feature"},
        }

        with self.assertRaises(MissingError):
            service.replace_geofence_feature("nonexistent-uuid-99999", feature_input)

    # --- DELETE ---

    def test_delete_soft_deletes(self):
        """DELETE sets active=False; subsequent GET returns 404."""
        # Create a geofence specifically for deletion
        geofence = self.Geofence.create(
            {
                "name": "OGC Delete Target",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "custom",
            }
        )
        uuid = geofence.uuid

        service = self._make_service()
        service.delete_geofence_feature(uuid)

        # Verify soft-deleted
        geofence.invalidate_recordset()
        self.assertFalse(geofence.with_context(active_test=False).active)

        # GET should now return 404
        with self.assertRaises(MissingError):
            service.get_collection_item("geofences", uuid)

    def test_delete_missing_feature_returns_error(self):
        """DELETE on nonexistent UUID raises MissingError."""
        service = self._make_service()

        with self.assertRaises(MissingError):
            service.delete_geofence_feature("nonexistent-uuid-99999")

    def test_delete_allowed_when_no_program_module(self):
        """DELETE succeeds when spp_program_geofence is not installed."""
        # spp_program_geofence is not a dependency of spp_api_v2_gis,
        # so spp.program should not have geofence_ids in this test env.
        # _check_geofence_not_referenced should be a no-op.
        geofence = self.Geofence.create(
            {
                "name": "OGC Delete No Program",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "custom",
            }
        )
        uuid = geofence.uuid

        service = self._make_service()
        service.delete_geofence_feature(uuid)

        geofence.invalidate_recordset()
        self.assertFalse(geofence.with_context(active_test=False).active)

    def test_delete_blocked_when_referenced_by_program(self):
        """DELETE raises ValueError if geofence is linked to a program."""
        geofence = self.Geofence.create(
            {
                "name": "OGC Delete Referenced",
                "geometry": json.dumps(SAMPLE_POLYGON),
                "geofence_type": "custom",
            }
        )

        service = self._make_service()

        # Patch _check_geofence_not_referenced to simulate a program reference
        original_check = service._check_geofence_not_referenced

        def mock_check(gf):
            raise ValueError("Cannot delete geofence: referenced by program(s): Test Program")

        service._check_geofence_not_referenced = mock_check

        with self.assertRaises(ValueError) as cm:
            service.delete_geofence_feature(geofence.uuid)

        self.assertIn("referenced by program", str(cm.exception))

        # Verify geofence is still active (delete was blocked)
        geofence.invalidate_recordset()
        self.assertTrue(geofence.active)

        # Restore and verify normal delete still works
        service._check_geofence_not_referenced = original_check
        service.delete_geofence_feature(geofence.uuid)
        geofence.invalidate_recordset()
        self.assertFalse(geofence.with_context(active_test=False).active)
