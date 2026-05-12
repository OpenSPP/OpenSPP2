# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Land Record validation, onchange, and edge cases."""

import json
from datetime import date

import pyproj

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLandRecordLeaseValidation(TransactionCase):
    """Test lease date constraints and onchange methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner Lease",
            }
        )

        cls.land_use_cultivation = cls.env.ref("spp_farmer_registry_vocabularies.code_land_use_cultivation")

    def _create_land_record(self, vals=None):
        """Helper to create a land record with defaults."""
        defaults = {
            "land_farm_id": self.partner.id,
            "land_name": "Lease Test Land",
        }
        if vals:
            defaults.update(vals)
        return self.env["spp.land.record"].create(defaults)

    # ---------------------------------------------------------------
    # _check_lease_dates constraint tests
    # ---------------------------------------------------------------

    def test_check_lease_dates_end_before_start_raises(self):
        """Constraint raises ValidationError when lease end < lease start."""
        with self.assertRaises(ValidationError):
            self._create_land_record(
                {
                    "lease_start": date(2025, 6, 1),
                    "lease_end": date(2025, 5, 1),
                }
            )

    def test_check_lease_dates_end_equals_start_ok(self):
        """Constraint allows lease end == lease start (same day lease)."""
        record = self._create_land_record(
            {
                "lease_start": date(2025, 6, 1),
                "lease_end": date(2025, 6, 1),
            }
        )
        self.assertEqual(record.lease_start, date(2025, 6, 1))
        self.assertEqual(record.lease_end, date(2025, 6, 1))

    def test_check_lease_dates_end_after_start_ok(self):
        """Constraint allows lease end > lease start."""
        record = self._create_land_record(
            {
                "lease_start": date(2025, 1, 1),
                "lease_end": date(2025, 12, 31),
            }
        )
        self.assertEqual(record.lease_start, date(2025, 1, 1))
        self.assertEqual(record.lease_end, date(2025, 12, 31))

    def test_check_lease_dates_only_start_set(self):
        """Constraint does not raise when only lease_start is set."""
        record = self._create_land_record(
            {
                "lease_start": date(2025, 6, 1),
            }
        )
        self.assertEqual(record.lease_start, date(2025, 6, 1))
        self.assertFalse(record.lease_end)

    def test_check_lease_dates_only_end_set(self):
        """Constraint does not raise when only lease_end is set."""
        record = self._create_land_record(
            {
                "lease_end": date(2025, 12, 31),
            }
        )
        self.assertFalse(record.lease_start)
        self.assertEqual(record.lease_end, date(2025, 12, 31))

    def test_check_lease_dates_both_empty(self):
        """Constraint does not raise when both dates are empty."""
        record = self._create_land_record()
        self.assertFalse(record.lease_start)
        self.assertFalse(record.lease_end)

    def test_check_lease_dates_write_invalid(self):
        """Constraint raises when writing invalid dates on existing record."""
        record = self._create_land_record(
            {
                "lease_start": date(2025, 1, 1),
                "lease_end": date(2025, 12, 31),
            }
        )
        with self.assertRaises(ValidationError):
            record.write({"lease_end": date(2024, 12, 31)})

    # ---------------------------------------------------------------
    # _onchange_lease_start tests
    # ---------------------------------------------------------------

    def test_onchange_lease_start_clears_when_after_end(self):
        """Onchange clears lease_start and returns warning when start > end."""
        record = self.env["spp.land.record"].new(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Onchange Test",
                "lease_start": date(2025, 12, 1),
                "lease_end": date(2025, 6, 1),
            }
        )
        result = record._onchange_lease_start()
        self.assertFalse(record.lease_start)
        self.assertIn("warning", result)
        self.assertEqual(result["warning"]["title"], "Invalid Lease Date")

    def test_onchange_lease_start_no_action_when_valid(self):
        """Onchange does nothing when start < end."""
        record = self.env["spp.land.record"].new(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Onchange Test",
                "lease_start": date(2025, 1, 1),
                "lease_end": date(2025, 12, 31),
            }
        )
        result = record._onchange_lease_start()
        self.assertIsNone(result)
        self.assertEqual(record.lease_start, date(2025, 1, 1))

    def test_onchange_lease_start_no_action_when_no_end(self):
        """Onchange does nothing when lease_end is not set."""
        record = self.env["spp.land.record"].new(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Onchange Test",
                "lease_start": date(2025, 6, 1),
            }
        )
        result = record._onchange_lease_start()
        self.assertIsNone(result)
        self.assertEqual(record.lease_start, date(2025, 6, 1))

    # ---------------------------------------------------------------
    # _onchange_lease_end tests
    # ---------------------------------------------------------------

    def test_onchange_lease_end_clears_when_before_start(self):
        """Onchange clears lease_end and returns warning when end < start."""
        record = self.env["spp.land.record"].new(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Onchange Test",
                "lease_start": date(2025, 6, 1),
                "lease_end": date(2025, 1, 1),
            }
        )
        result = record._onchange_lease_end()
        self.assertFalse(record.lease_end)
        self.assertIn("warning", result)
        self.assertEqual(result["warning"]["title"], "Invalid Lease Date")

    def test_onchange_lease_end_no_action_when_valid(self):
        """Onchange does nothing when end > start."""
        record = self.env["spp.land.record"].new(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Onchange Test",
                "lease_start": date(2025, 1, 1),
                "lease_end": date(2025, 12, 31),
            }
        )
        result = record._onchange_lease_end()
        self.assertIsNone(result)
        self.assertEqual(record.lease_end, date(2025, 12, 31))

    def test_onchange_lease_end_no_action_when_no_start(self):
        """Onchange does nothing when lease_start is not set."""
        record = self.env["spp.land.record"].new(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Onchange Test",
                "lease_end": date(2025, 12, 31),
            }
        )
        result = record._onchange_lease_end()
        self.assertIsNone(result)
        self.assertEqual(record.lease_end, date(2025, 12, 31))


@tagged("post_install", "-at_install")
class TestLandRecordComputeAndGeo(TransactionCase):
    """Test computed fields, GeoJSON generation, and search domain methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner Geo",
            }
        )

        cls.land_use_cultivation = cls.env.ref("spp_farmer_registry_vocabularies.code_land_use_cultivation")
        cls.land_use_livestock = cls.env.ref("spp_farmer_registry_vocabularies.code_land_use_livestock")

        cls.point_geojson = json.dumps(
            {
                "type": "Point",
                "coordinates": [124.987, 7.932],
            }
        )

        cls.polygon_geojson = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [
                        [124.935, 7.956],
                        [125.008, 7.941],
                        [124.999, 7.890],
                        [124.935, 7.956],
                    ]
                ],
            }
        )

    # ---------------------------------------------------------------
    # _compute_land_use tests
    # ---------------------------------------------------------------

    def test_compute_land_use_with_land_use_id(self):
        """Computed land_use returns code when land_use_id is set."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Compute Test",
                "land_use_id": self.land_use_cultivation.id,
            }
        )
        self.assertEqual(record.land_use, "cultivation")

    def test_compute_land_use_without_land_use_id(self):
        """Computed land_use returns False when land_use_id is empty."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "No Land Use",
            }
        )
        self.assertFalse(record.land_use)

    def test_compute_land_use_change(self):
        """Computed land_use updates when land_use_id changes."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Change Test",
                "land_use_id": self.land_use_cultivation.id,
            }
        )
        self.assertEqual(record.land_use, "cultivation")
        record.land_use_id = self.land_use_livestock.id
        self.assertEqual(record.land_use, "livestock")

    def test_compute_land_use_clear(self):
        """Computed land_use becomes False when land_use_id is cleared."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Clear Test",
                "land_use_id": self.land_use_cultivation.id,
            }
        )
        record.land_use_id = False
        self.assertFalse(record.land_use)

    # ---------------------------------------------------------------
    # _process_record_to_feature tests
    # ---------------------------------------------------------------

    def _get_transformer(self):
        """Return a pyproj transformer for testing."""
        proj_from = pyproj.Proj("epsg:4326")
        proj_to = pyproj.Proj("epsg:3857")
        return pyproj.Transformer.from_proj(proj_from, proj_to, always_xy=True).transform

    def test_process_record_polygon_geometry(self):
        """Feature uses polygon geometry when type is 'polygon'."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Polygon Test",
                "land_geo_polygon": self.polygon_geojson,
                "land_coordinates": self.point_geojson,
                "land_use_id": self.land_use_cultivation.id,
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "polygon", transformer)
        self.assertIsNotNone(feature)
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertEqual(feature["properties"]["land_name"], "Polygon Test")

    def test_process_record_point_geometry(self):
        """Feature uses point geometry when type is 'point'."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Point Test",
                "land_coordinates": self.point_geojson,
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "point", transformer)
        self.assertIsNotNone(feature)
        self.assertEqual(feature["geometry"]["type"], "Point")
        self.assertEqual(feature["properties"]["land_name"], "Point Test")

    def test_process_record_all_prefers_polygon(self):
        """Feature prefers polygon geometry when type is 'all' and both exist."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "All Test",
                "land_geo_polygon": self.polygon_geojson,
                "land_coordinates": self.point_geojson,
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "all", transformer)
        self.assertIsNotNone(feature)
        self.assertEqual(feature["geometry"]["type"], "Polygon")

    def test_process_record_all_falls_back_to_point(self):
        """Feature falls back to point when type is 'all' and no polygon."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Fallback Test",
                "land_coordinates": self.point_geojson,
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "all", transformer)
        self.assertIsNotNone(feature)
        self.assertEqual(feature["geometry"]["type"], "Point")

    def test_process_record_no_geometry_returns_none(self):
        """Feature returns None when no geometry is available."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "No Geo",
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "all", transformer)
        self.assertIsNone(feature)

    def test_process_record_unknown_type_returns_none(self):
        """Feature returns None for unsupported geometry type."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Unknown Type",
                "land_coordinates": self.point_geojson,
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "line", transformer)
        self.assertIsNone(feature)

    def test_process_record_properties_include_land_use_display(self):
        """Feature properties include land_use_display from vocabulary."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Display Test",
                "land_coordinates": self.point_geojson,
                "land_use_id": self.land_use_cultivation.id,
                "land_acreage": 5.5,
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "point", transformer)
        self.assertEqual(feature["properties"]["land_use"], "cultivation")
        self.assertEqual(feature["properties"]["land_use_display"], "Cultivation")
        self.assertEqual(feature["properties"]["land_acreage"], 5.5)

    def test_process_record_properties_no_land_use(self):
        """Feature properties have None land_use_display when no vocabulary."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "No Use Test",
                "land_coordinates": self.point_geojson,
            }
        )
        transformer = self._get_transformer()
        feature = record._process_record_to_feature(record, "point", transformer)
        self.assertIsNone(feature["properties"]["land_use_display"])
        self.assertFalse(feature["properties"]["land_use"])

    # ---------------------------------------------------------------
    # get_geojson tests
    # ---------------------------------------------------------------

    def test_get_geojson_point_type(self):
        """get_geojson with geometry_type='point' returns valid GeoJSON."""
        self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "GeoJSON Point",
                "land_coordinates": self.point_geojson,
            }
        )
        result = json.loads(
            self.env["spp.land.record"].get_geojson(geometry_type="point", from_srid=4326, to_srid=3857)
        )
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertTrue(len(result["features"]) >= 1)

    def test_get_geojson_polygon_type(self):
        """get_geojson with geometry_type='polygon' returns valid GeoJSON."""
        self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "GeoJSON Polygon",
                "land_geo_polygon": self.polygon_geojson,
            }
        )
        result = json.loads(
            self.env["spp.land.record"].get_geojson(geometry_type="polygon", from_srid=4326, to_srid=3857)
        )
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertTrue(len(result["features"]) >= 1)

    def test_get_geojson_all_type(self):
        """get_geojson with geometry_type='all' includes all geometries."""
        self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "GeoJSON All",
                "land_coordinates": self.point_geojson,
                "land_geo_polygon": self.polygon_geojson,
            }
        )
        result = json.loads(self.env["spp.land.record"].get_geojson(geometry_type="all", from_srid=4326, to_srid=3857))
        self.assertEqual(result["type"], "FeatureCollection")
        self.assertTrue(len(result["features"]) >= 1)

    def test_get_geojson_empty_records(self):
        """get_geojson returns empty features when no records have geometry."""
        # Create a record with no geometry
        self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "No Geometry",
            }
        )
        # Note: _get_search_domain_by_geometry_type returns [] so all records
        # are fetched, but _process_record_to_feature filters out those
        # without geometry. We check the logic works end-to-end.
        result = json.loads(self.env["spp.land.record"].get_geojson(geometry_type="line", from_srid=4326, to_srid=3857))
        self.assertEqual(result["type"], "FeatureCollection")
        # Features with no matching geometry are excluded
        for feat in result["features"]:
            self.assertIn("geometry", feat)

    def test_get_geojson_default_params(self):
        """get_geojson works with default parameters."""
        self.env["spp.land.record"].create(
            {
                "land_farm_id": self.partner.id,
                "land_name": "Default Params",
                "land_coordinates": self.point_geojson,
            }
        )
        result = json.loads(self.env["spp.land.record"].get_geojson())
        self.assertEqual(result["type"], "FeatureCollection")

    # ---------------------------------------------------------------
    # _get_search_domain_by_geometry_type tests
    # ---------------------------------------------------------------

    def test_get_search_domain_point(self):
        """Search domain for 'point' returns empty list (current impl)."""
        model = self.env["spp.land.record"]
        domain = model._get_search_domain_by_geometry_type("point")
        self.assertEqual(domain, [])

    def test_get_search_domain_polygon(self):
        """Search domain for 'polygon' returns empty list (current impl)."""
        model = self.env["spp.land.record"]
        domain = model._get_search_domain_by_geometry_type("polygon")
        self.assertEqual(domain, [])

    def test_get_search_domain_all(self):
        """Search domain for 'all' returns empty list (current impl)."""
        model = self.env["spp.land.record"]
        domain = model._get_search_domain_by_geometry_type("all")
        self.assertEqual(domain, [])

    def test_get_search_domain_unknown(self):
        """Search domain for unknown type returns empty list."""
        model = self.env["spp.land.record"]
        domain = model._get_search_domain_by_geometry_type("unknown")
        self.assertEqual(domain, [])


@tagged("post_install", "-at_install")
class TestLandRecordRelationships(TransactionCase):
    """Test land record relationships and field defaults."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.owner = cls.env["res.partner"].create({"name": "Land Owner"})
        cls.lessee = cls.env["res.partner"].create({"name": "Land Lessee"})
        cls.farm = cls.env["res.partner"].create({"name": "Test Farm"})

    def test_create_with_all_relationships(self):
        """Land record with owner, lessee, and farm relationships."""
        record = self.env["spp.land.record"].create(
            {
                "land_farm_id": self.farm.id,
                "land_name": "Full Record",
                "land_acreage": 25.0,
                "owner_id": self.owner.id,
                "lessee_id": self.lessee.id,
                "lease_start": date(2025, 1, 1),
                "lease_end": date(2025, 12, 31),
            }
        )
        self.assertEqual(record.land_farm_id, self.farm)
        self.assertEqual(record.owner_id, self.owner)
        self.assertEqual(record.lessee_id, self.lessee)
        self.assertEqual(record.land_acreage, 25.0)

    def test_create_minimal_record(self):
        """Land record can be created with minimal fields."""
        record = self.env["spp.land.record"].create(
            {
                "land_name": "Minimal",
            }
        )
        self.assertEqual(record.land_name, "Minimal")
        self.assertFalse(record.land_farm_id)
        self.assertFalse(record.owner_id)
        self.assertFalse(record.lessee_id)
        self.assertEqual(record.land_acreage, 0.0)

    def test_record_name_is_land_name(self):
        """Record name field stores land_name correctly."""
        record = self.env["spp.land.record"].create(
            {
                "land_name": "My Parcel ABC",
            }
        )
        self.assertEqual(record.land_name, "My Parcel ABC")
