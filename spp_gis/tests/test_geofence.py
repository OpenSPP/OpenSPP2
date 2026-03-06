# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the core geofence model in spp_gis."""

import json
import logging

import psycopg2

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestGeofenceModel(TransactionCase):
    """Test geofence model functionality."""

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

        # Sample multipolygon GeoJSON
        cls.sample_multipolygon = {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [102.0, 2.0],
                        [103.0, 2.0],
                        [103.0, 3.0],
                        [102.0, 3.0],
                        [102.0, 2.0],
                    ]
                ],
                [
                    [
                        [100.0, 0.0],
                        [101.0, 0.0],
                        [101.0, 1.0],
                        [100.0, 1.0],
                        [100.0, 0.0],
                    ]
                ],
            ],
        }

        # Create test vocabulary for tags
        cls.tag1 = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:concept:geofence_tag_1")],
            limit=1,
        )
        if not cls.tag1:
            cls.tag1 = cls.env["spp.vocabulary"].create(
                {
                    "name": "Test Tag 1",
                    "namespace_uri": "urn:openspp:concept:geofence_tag_1",
                }
            )

    def test_create_geofence_basic(self):
        """Test creating a basic geofence."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Test Geofence",
                "description": "Test description",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        self.assertTrue(geofence)
        self.assertEqual(geofence.name, "Test Geofence")
        self.assertEqual(geofence.geofence_type, "custom")
        self.assertTrue(geofence.active)
        self.assertEqual(geofence.created_from, "ui")

    def test_create_geofence_with_type(self):
        """Test creating geofence with core types."""
        types = ["area_of_interest", "custom"]

        for geofence_type in types:
            geofence = self.env["spp.gis.geofence"].create(
                {
                    "name": f"Test {geofence_type}",
                    "geometry": json.dumps(self.sample_polygon),
                    "geofence_type": geofence_type,
                }
            )

            self.assertEqual(geofence.geofence_type, geofence_type)

    def test_create_geofence_from_qgis(self):
        """Test creating geofence from QGIS plugin."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "QGIS Geofence",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
                "created_from": "qgis",
            }
        )

        self.assertEqual(geofence.created_from, "qgis")

    def test_geofence_unique_name_constraint(self):
        """Test that active geofences must have unique names."""
        # Create first geofence
        self.env["spp.gis.geofence"].create(
            {
                "name": "Unique Name",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        # Try to create second with same name
        with self.assertRaises(ValidationError) as context:
            self.env["spp.gis.geofence"].create(
                {
                    "name": "Unique Name",
                    "geometry": json.dumps(self.sample_polygon),
                    "geofence_type": "custom",
                }
            )

        self.assertIn("already exists", str(context.exception))

    def test_geofence_inactive_allows_duplicate_names(self):
        """Test that inactive geofences can have duplicate names."""
        # Create first geofence and deactivate
        geofence1 = self.env["spp.gis.geofence"].create(
            {
                "name": "Duplicate OK",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )
        geofence1.active = False

        # Should be able to create second with same name
        geofence2 = self.env["spp.gis.geofence"].create(
            {
                "name": "Duplicate OK",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        self.assertTrue(geofence2)
        self.assertEqual(geofence2.name, "Duplicate OK")

    def test_geofence_geometry_required(self):
        """Test that geometry is required (enforced at DB level)."""
        # Geometry field has NOT NULL constraint at database level
        with self.assertRaises(psycopg2.IntegrityError):
            self.env["spp.gis.geofence"].create(
                {
                    "name": "No Geometry",
                    "geofence_type": "custom",
                }
            )

    def test_to_geojson_feature(self):
        """Test converting geofence to GeoJSON Feature."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "GeoJSON Test",
                "description": "Test description",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        feature = geofence.to_geojson()

        # Verify Feature structure
        self.assertEqual(feature["type"], "Feature")
        self.assertIn("geometry", feature)
        self.assertIn("properties", feature)

        # Verify geometry
        geometry = feature["geometry"]
        self.assertEqual(geometry["type"], "Polygon")
        self.assertIn("coordinates", geometry)

        # Verify properties
        props = feature["properties"]
        self.assertEqual(props["name"], "GeoJSON Test")
        self.assertEqual(props["description"], "Test description")
        self.assertEqual(props["geofence_type"], "custom")

    def test_to_geojson_properties_structure(self):
        """Test GeoJSON properties contain all expected fields."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Props Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        feature = geofence.to_geojson()
        props = feature["properties"]

        # Verify all expected properties (uuid instead of id)
        self.assertIn("uuid", props)
        self.assertIn("name", props)
        self.assertIn("description", props)
        self.assertIn("geofence_type", props)
        self.assertIn("geofence_type_label", props)
        self.assertIn("area_sqkm", props)
        self.assertIn("tags", props)
        self.assertIn("created_from", props)
        self.assertIn("created_by", props)
        self.assertIn("create_date", props)

        # Should NOT have incident fields in core
        self.assertNotIn("incident_id", props)
        self.assertNotIn("incident_name", props)

    def test_to_geojson_collection(self):
        """Test converting multiple geofences to GeoJSON FeatureCollection."""
        geofence1 = self.env["spp.gis.geofence"].create(
            {
                "name": "Geofence 1",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        geofence2 = self.env["spp.gis.geofence"].create(
            {
                "name": "Geofence 2",
                "geometry": json.dumps(self.sample_multipolygon),
                "geofence_type": "area_of_interest",
            }
        )

        geofences = geofence1 + geofence2
        collection = geofences.to_geojson_collection()

        # Verify FeatureCollection structure
        self.assertEqual(collection["type"], "FeatureCollection")
        self.assertIn("features", collection)
        self.assertEqual(len(collection["features"]), 2)

        # Verify features
        self.assertEqual(collection["features"][0]["type"], "Feature")
        self.assertEqual(collection["features"][1]["type"], "Feature")

    def test_create_from_geojson_feature(self):
        """Test creating geofence from GeoJSON Feature."""
        feature = {
            "type": "Feature",
            "geometry": self.sample_polygon,
            "properties": {
                "name": "Feature Test",
            },
        }

        geofence = self.env["spp.gis.geofence"].create_from_geojson(
            geojson_str=json.dumps(feature),
            name="Created From Feature",
            geofence_type="custom",
            created_from="api",
        )

        self.assertTrue(geofence)
        self.assertEqual(geofence.name, "Created From Feature")
        self.assertEqual(geofence.geofence_type, "custom")
        self.assertEqual(geofence.created_from, "api")

    def test_create_from_geojson_feature_collection(self):
        """Test creating geofence from GeoJSON FeatureCollection."""
        feature_collection = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": self.sample_polygon,
                    "properties": {},
                }
            ],
        }

        geofence = self.env["spp.gis.geofence"].create_from_geojson(
            geojson_str=json.dumps(feature_collection),
            name="Created From Collection",
            geofence_type="area_of_interest",
        )

        self.assertTrue(geofence)
        self.assertEqual(geofence.name, "Created From Collection")

    def test_create_from_geojson_raw_geometry(self):
        """Test creating geofence from raw GeoJSON geometry."""
        geofence = self.env["spp.gis.geofence"].create_from_geojson(
            geojson_str=json.dumps(self.sample_polygon),
            name="Created From Geometry",
            geofence_type="custom",
        )

        self.assertTrue(geofence)
        self.assertEqual(geofence.name, "Created From Geometry")

    def test_create_from_geojson_invalid_json(self):
        """Test creating geofence from invalid JSON raises error."""
        with self.assertRaises(ValidationError) as context:
            self.env["spp.gis.geofence"].create_from_geojson(
                geojson_str="invalid json",
                name="Invalid",
                geofence_type="custom",
            )

        self.assertIn("Invalid GeoJSON", str(context.exception))

    def test_create_from_geojson_empty_feature_collection(self):
        """Test creating geofence from empty FeatureCollection raises error."""
        feature_collection = {
            "type": "FeatureCollection",
            "features": [],
        }

        with self.assertRaises(ValidationError) as context:
            self.env["spp.gis.geofence"].create_from_geojson(
                geojson_str=json.dumps(feature_collection),
                name="Empty",
                geofence_type="custom",
            )

        self.assertIn("must contain at least one feature", str(context.exception))

    def test_create_from_geojson_no_geometry(self):
        """Test creating geofence without geometry raises error."""
        feature = {
            "type": "Feature",
            "geometry": None,
            "properties": {},
        }

        with self.assertRaises(ValidationError) as context:
            self.env["spp.gis.geofence"].create_from_geojson(
                geojson_str=json.dumps(feature),
                name="No Geometry",
                geofence_type="custom",
            )

        self.assertIn("No geometry found", str(context.exception))

    def test_create_from_geojson_with_additional_fields(self):
        """Test creating geofence with additional field values."""
        geofence = self.env["spp.gis.geofence"].create_from_geojson(
            geojson_str=json.dumps(self.sample_polygon),
            name="With Fields",
            geofence_type="area_of_interest",
            created_from="qgis",
            description="Test description",
        )

        self.assertEqual(geofence.description, "Test description")
        self.assertEqual(geofence.created_from, "qgis")

    def test_geofence_multipolygon(self):
        """Test creating geofence with multipolygon geometry."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "MultiPolygon Test",
                "geometry": json.dumps(self.sample_multipolygon),
                "geofence_type": "custom",
            }
        )

        self.assertTrue(geofence)
        feature = geofence.to_geojson()
        self.assertEqual(feature["geometry"]["type"], "MultiPolygon")

    def test_geofence_area_computation(self):
        """Test that area is computed (may be 0 if PostGIS not available)."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Area Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        # Area should be computed (may be 0 if PostGIS not available in test env)
        self.assertIsNotNone(geofence.area_sqkm)
        self.assertGreaterEqual(geofence.area_sqkm, 0)

    def test_geofence_created_by_default(self):
        """Test that create_uid is set to current user by default."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Created By Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        self.assertEqual(geofence.create_uid, self.env.user)

    def test_geofence_type_label_in_properties(self):
        """Test that geofence_type_label is included in properties."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Type Label Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "area_of_interest",
            }
        )

        feature = geofence.to_geojson()
        props = feature["properties"]

        self.assertEqual(props["geofence_type"], "area_of_interest")
        self.assertEqual(props["geofence_type_label"], "Area of Interest")

    def test_geofence_uuid_generated(self):
        """Test that UUID is auto-generated on create."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "UUID Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        self.assertTrue(geofence.uuid)
        # Verify it looks like a UUID (36 chars with dashes)
        self.assertEqual(len(geofence.uuid), 36)
        self.assertEqual(geofence.uuid.count("-"), 4)

    def test_geofence_uuid_unique(self):
        """Test that UUIDs are unique across records."""
        geofence1 = self.env["spp.gis.geofence"].create(
            {
                "name": "UUID Unique 1",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        geofence2 = self.env["spp.gis.geofence"].create(
            {
                "name": "UUID Unique 2",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        self.assertNotEqual(geofence1.uuid, geofence2.uuid)

    def test_geofence_with_tags(self):
        """Test creating geofence with tags."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Tagged Geofence",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
                "tag_ids": [(6, 0, [self.tag1.id])],
            }
        )

        self.assertEqual(len(geofence.tag_ids), 1)
        self.assertIn(self.tag1, geofence.tag_ids)

        # Verify tags appear in GeoJSON properties
        feature = geofence.to_geojson()
        self.assertIn("Test Tag 1", feature["properties"]["tags"])

    def test_geofence_uuid_in_properties(self):
        """Test that uuid appears in GeoJSON properties instead of id."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "UUID Props Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        feature = geofence.to_geojson()
        props = feature["properties"]

        self.assertIn("uuid", props)
        self.assertNotIn("id", props)
        self.assertEqual(props["uuid"], geofence.uuid)

    def test_geofence_uuid_copy_generates_new(self):
        """Test that copying a geofence generates a new UUID."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "UUID Copy Original",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        copied = geofence.copy({"name": "UUID Copy Clone"})

        self.assertTrue(copied.uuid)
        self.assertNotEqual(geofence.uuid, copied.uuid)
        self.assertEqual(len(copied.uuid), 36)

    def test_geofence_rename_to_duplicate_raises(self):
        """Test that renaming a geofence to an existing active name raises error."""
        self.env["spp.gis.geofence"].create(
            {
                "name": "Existing Name",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        geofence2 = self.env["spp.gis.geofence"].create(
            {
                "name": "Different Name",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        with self.assertRaises(ValidationError):
            geofence2.write({"name": "Existing Name"})

    def test_geofence_reactivate_duplicate_name_raises(self):
        """Test that reactivating an archived geofence with a duplicate name raises error."""
        self.env["spp.gis.geofence"].create(
            {
                "name": "Active Name",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        archived = self.env["spp.gis.geofence"].create(
            {
                "name": "Temp Name",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )
        archived.write({"active": False, "name": "Active Name"})

        with self.assertRaises(ValidationError):
            archived.write({"active": True})

    def test_create_from_geojson_dict_input(self):
        """Test creating geofence from dict input (not string)."""
        geofence = self.env["spp.gis.geofence"].create_from_geojson(
            geojson_str=self.sample_polygon,
            name="Dict Input",
            geofence_type="custom",
        )

        self.assertTrue(geofence)
        self.assertEqual(geofence.name, "Dict Input")

    def test_geofence_area_varies_by_geometry_size(self):
        """Test that different sized geometries produce different areas."""
        small_geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Small Area",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        # 2x2 degree polygon (roughly 4x the area of 1x1)
        larger_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [100.0, 0.0],
                    [102.0, 0.0],
                    [102.0, 2.0],
                    [100.0, 2.0],
                    [100.0, 0.0],
                ]
            ],
        }
        large_geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Large Area",
                "geometry": json.dumps(larger_polygon),
                "geofence_type": "custom",
            }
        )

        self.assertGreater(small_geofence.area_sqkm, 0)
        self.assertGreater(large_geofence.area_sqkm, small_geofence.area_sqkm)

    def test_to_geojson_collection_empty_recordset(self):
        """Test to_geojson_collection with empty recordset."""
        empty = self.env["spp.gis.geofence"].browse([])
        collection = empty.to_geojson_collection()

        self.assertEqual(collection["type"], "FeatureCollection")
        self.assertEqual(collection["features"], [])

    def test_geojson_properties_values_correct(self):
        """Test that GeoJSON property values are correct, not just present."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Values Check",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "area_of_interest",
                "created_from": "api",
                "tag_ids": [(6, 0, [self.tag1.id])],
            }
        )

        props = geofence.to_geojson()["properties"]

        self.assertEqual(props["uuid"], geofence.uuid)
        self.assertEqual(props["name"], "Values Check")
        self.assertEqual(props["description"], "")
        self.assertEqual(props["geofence_type"], "area_of_interest")
        self.assertEqual(props["geofence_type_label"], "Area of Interest")
        self.assertIsInstance(props["area_sqkm"], float)
        self.assertEqual(props["tags"], ["Test Tag 1"])
        self.assertEqual(props["created_from"], "api")
        self.assertEqual(props["created_by"], self.env.user.name)
        self.assertIsNotNone(props["create_date"])

    def test_geofence_description_none_becomes_empty_string(self):
        """Test that missing description becomes empty string in properties."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "No Description",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        props = geofence.to_geojson()["properties"]
        self.assertEqual(props["description"], "")

    def test_geofence_type_defaults_to_custom(self):
        """Test that geofence_type defaults to custom when not specified."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Default Type Test",
                "geometry": json.dumps(self.sample_polygon),
            }
        )

        self.assertEqual(geofence.geofence_type, "custom")

    def test_geofence_area_positive_for_known_polygon(self):
        """Test that area is strictly positive for the known ~12,300 sqkm test polygon."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Positive Area Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        # 1 degree x 1 degree near equator is roughly 12,300 sq km
        self.assertGreater(geofence.area_sqkm, 0)

    def test_geofence_archive_excludes_from_search(self):
        """Test that archived geofences are excluded from default search."""
        geofence = self.env["spp.gis.geofence"].create(
            {
                "name": "Archive Search Test",
                "geometry": json.dumps(self.sample_polygon),
                "geofence_type": "custom",
            }
        )

        # Should be found by default search
        found = self.env["spp.gis.geofence"].search([("name", "=", "Archive Search Test")])
        self.assertEqual(len(found), 1)

        # Archive it
        geofence.write({"active": False})

        # Should no longer appear in default search
        found = self.env["spp.gis.geofence"].search([("name", "=", "Archive Search Test")])
        self.assertEqual(len(found), 0)

        # Should appear when explicitly searching inactive
        found = (
            self.env["spp.gis.geofence"].with_context(active_test=False).search([("name", "=", "Archive Search Test")])
        )
        self.assertEqual(len(found), 1)
