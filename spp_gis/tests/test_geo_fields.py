# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestGeoFields(TransactionCase):
    """Test GeoField parsing and conversion methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                test_queue_job_no_delay=True,
            )
        )

    def test_is_wkb_hex_valid_point(self):
        """Test _is_wkb_hex correctly identifies valid WKB hex strings."""
        from odoo.addons.spp_gis.fields import _is_wkb_hex

        # Valid WKB hex for a Point (little-endian)
        # This is POINT(79.8612 6.9271) in WKB hex
        wkb_hex = "01010000002CD49AE61DF75340857CD0B359B51B40"
        self.assertTrue(_is_wkb_hex(wkb_hex))

        # Valid WKB hex (big-endian starts with 00)
        wkb_hex_big_endian = "00000000014053F71DE69AD42C401BB559B3D07C85"
        self.assertTrue(_is_wkb_hex(wkb_hex_big_endian))

    def test_is_wkb_hex_rejects_invalid(self):
        """Test _is_wkb_hex correctly rejects non-WKB strings."""
        from odoo.addons.spp_gis.fields import _is_wkb_hex

        # GeoJSON string
        geojson = '{"type": "Point", "coordinates": [79.8612, 6.9271]}'
        self.assertFalse(_is_wkb_hex(geojson))

        # WKT string
        wkt = "POINT(79.8612 6.9271)"
        self.assertFalse(_is_wkb_hex(wkt))

        # Too short
        self.assertFalse(_is_wkb_hex("0101"))

        # Invalid first byte (not 00 or 01)
        self.assertFalse(_is_wkb_hex("02010000002CD49AE61DF75340"))

        # Empty/None
        self.assertFalse(_is_wkb_hex(""))
        self.assertFalse(_is_wkb_hex(None))

    def test_value_to_shape_auto_detects_wkb_hex(self):
        """Test value_to_shape automatically detects WKB hex format.

        This tests the fix for ParseException when WKB hex is passed
        without use_wkb=True flag.
        """
        from odoo.addons.spp_gis.fields import value_to_shape

        # WKB hex for POINT(79.8612 6.9271)
        wkb_hex = "01010000002CD49AE61DF75340857CD0B359B51B40"

        # This should NOT raise ParseException even without use_wkb=True
        shape = value_to_shape(wkb_hex, use_wkb=False)

        self.assertIsNotNone(shape)
        self.assertEqual(shape.geom_type, "Point")
        # Check coordinates (with floating point tolerance)
        self.assertAlmostEqual(shape.x, 79.8612, places=4)
        self.assertAlmostEqual(shape.y, 6.9271, places=4)

    def test_value_to_shape_handles_geojson(self):
        """Test value_to_shape correctly parses GeoJSON."""
        from odoo.addons.spp_gis.fields import value_to_shape

        geojson = '{"type": "Point", "coordinates": [79.8612, 6.9271]}'
        shape = value_to_shape(geojson)

        self.assertIsNotNone(shape)
        self.assertEqual(shape.geom_type, "Point")
        self.assertAlmostEqual(shape.x, 79.8612, places=4)
        self.assertAlmostEqual(shape.y, 6.9271, places=4)

    def test_value_to_shape_handles_wkt(self):
        """Test value_to_shape correctly parses WKT."""
        from odoo.addons.spp_gis.fields import value_to_shape

        wkt = "POINT(79.8612 6.9271)"
        shape = value_to_shape(wkt)

        self.assertIsNotNone(shape)
        self.assertEqual(shape.geom_type, "Point")
        self.assertAlmostEqual(shape.x, 79.8612, places=4)
        self.assertAlmostEqual(shape.y, 6.9271, places=4)

    def test_geo_field_round_trip_with_cache(self):
        """Test GeoField survives cache round-trip without ParseException.

        This is the actual bug scenario: GeoJSON is cached as WKB hex,
        then convert_to_column receives the WKB hex and must handle it.
        """
        from odoo.addons.spp_gis.fields import GeoPointField

        field = GeoPointField()

        # Simulate the flow:
        # 1. User sets GeoJSON
        geojson_input = json.dumps({"type": "Point", "coordinates": [79.8612, 6.9271]})

        # 2. convert_to_cache converts to WKB hex
        class MockRecord:
            pass

        cached_value = field.convert_to_cache(geojson_input, MockRecord())
        self.assertIsInstance(cached_value, str)
        # Cached value should be WKB hex (starts with 01 for little-endian)
        self.assertTrue(cached_value.startswith("01"))

        # 3. convert_to_column receives the cached WKB hex WITH validation enabled
        # This is where the bug occurred - it should NOT raise ParseException
        # even when validate=True (the default)
        column_value = field.convert_to_column(cached_value, MockRecord(), validate=True)

        self.assertIsNotNone(column_value)
        # Column value should be SRID-prefixed WKT
        self.assertTrue(column_value.startswith("SRID="))
        self.assertIn("POINT", column_value)

    def test_convert_to_column_validates_geojson(self):
        """Test that convert_to_column still validates GeoJSON input."""
        from odoo.exceptions import ValidationError

        from odoo.addons.spp_gis.fields import GeoPointField

        field = GeoPointField()

        class MockRecord:
            pass

        # Valid GeoJSON should work
        valid_geojson = json.dumps({"type": "Point", "coordinates": [79.8612, 6.9271]})
        column_value = field.convert_to_column(valid_geojson, MockRecord(), validate=True)
        self.assertIsNotNone(column_value)
        self.assertIn("POINT", column_value)

        # Invalid GeoJSON should raise ValidationError
        invalid_geojson = json.dumps({"invalid": "data"})
        with self.assertRaises(ValidationError):
            field.convert_to_column(invalid_geojson, MockRecord(), validate=True)


class TestOperatorTableAlias(TransactionCase):
    """Test that the Operator generates table-qualified column names in SQL."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                test_queue_job_no_delay=True,
            )
        )

    def _make_field(self, name="geo_polygon", srid=4326):
        """Create a mock field for the Operator."""
        from odoo.addons.spp_gis.fields import GeoPolygonField

        field = GeoPolygonField()
        field.name = name
        field.srid = srid
        return field

    def test_operator_without_alias_uses_bare_field_name(self):
        """Operator without table_alias uses bare field name (backward compat)."""
        from odoo.addons.spp_gis.operators import Operator

        field = self._make_field()
        operator = Operator(field)
        self.assertEqual(operator.qualified_field_name, "geo_polygon")

    def test_operator_with_alias_qualifies_field_name(self):
        """Operator with table_alias generates table-qualified column reference."""
        from odoo.addons.spp_gis.operators import Operator

        field = self._make_field()
        operator = Operator(field, table_alias="spp_area")
        self.assertEqual(operator.qualified_field_name, '"spp_area"."geo_polygon"')

    def test_domain_query_with_alias_uses_qualified_name(self):
        """domain_query generates SQL with table-qualified column names."""
        from odoo.addons.spp_gis.operators import Operator

        field = self._make_field()
        operator = Operator(field, table_alias="spp_area")

        geojson = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }

        result = operator.domain_query("gis_intersects", geojson)
        sql_string = str(result)

        self.assertIn("ST_Intersects", sql_string)
        self.assertIn('"spp_area"."geo_polygon"', sql_string)
        self.assertNotRegex(sql_string, r'(?<!")\bgeo_polygon\b(?!")')

    def test_domain_query_without_alias_uses_bare_name(self):
        """domain_query without alias uses bare field name for backward compat."""
        from odoo.addons.spp_gis.operators import Operator

        field = self._make_field()
        operator = Operator(field)

        geojson = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }

        result = operator.domain_query("gis_intersects", geojson)
        sql_string = str(result)

        self.assertIn("ST_Intersects", sql_string)
        self.assertIn("geo_polygon", sql_string)

    def test_get_postgis_query_with_alias_and_distance(self):
        """get_postgis_query with distance also uses qualified field name."""
        from odoo.addons.spp_gis.operators import Operator

        field = self._make_field()
        operator = Operator(field, table_alias="spp_area")

        result = operator.get_postgis_query(
            operation="intersects",
            coordinates=[79.86, 6.93],
            distance=1000,
            layer_type="point",
        )

        self.assertIn('"spp_area"."geo_polygon"', result)
