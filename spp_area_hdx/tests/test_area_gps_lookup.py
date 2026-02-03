# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json

from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestAreaGpsLookup(common.TransactionCase):
    """Test GPS-based area lookup functionality."""

    def setUp(self):
        super().setUp()

        # Create test areas with polygons
        # Colombo district polygon (simplified)
        colombo_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [79.8, 6.8],
                    [80.2, 6.8],
                    [80.2, 7.2],
                    [79.8, 7.2],
                    [79.8, 6.8],
                ]
            ],
        }

        self.area_colombo = self.env["spp.area"].create(
            {
                "draft_name": "Colombo",
                "code": "LK31",
                "hdx_pcode": "LK31",
                "level": 2,
                "geo_polygon": json.dumps(colombo_polygon),
            }
        )

        # Gampaha district polygon (simplified, adjacent to Colombo)
        gampaha_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [79.8, 7.2],
                    [80.2, 7.2],
                    [80.2, 7.6],
                    [79.8, 7.6],
                    [79.8, 7.2],
                ]
            ],
        }

        self.area_gampaha = self.env["spp.area"].create(
            {
                "draft_name": "Gampaha",
                "code": "LK32",
                "hdx_pcode": "LK32",
                "level": 2,
                "geo_polygon": json.dumps(gampaha_polygon),
            }
        )

    def test_find_by_coordinates_colombo(self):
        """Test finding area by GPS coordinates within Colombo."""
        # Point inside Colombo polygon
        latitude = 7.0
        longitude = 80.0

        area = self.env["spp.area"].find_by_coordinates(latitude, longitude)

        self.assertEqual(area, self.area_colombo)

    def test_find_by_coordinates_gampaha(self):
        """Test finding area by GPS coordinates within Gampaha."""
        # Point inside Gampaha polygon
        latitude = 7.4
        longitude = 80.0

        area = self.env["spp.area"].find_by_coordinates(latitude, longitude)

        self.assertEqual(area, self.area_gampaha)

    def test_find_by_coordinates_not_found(self):
        """Test GPS coordinates outside any area."""
        # Point outside both polygons
        latitude = 8.0
        longitude = 80.0

        area = self.env["spp.area"].find_by_coordinates(latitude, longitude)

        self.assertFalse(area)

    def test_find_by_coordinates_with_level_filter(self):
        """Test finding area with level filter."""
        latitude = 7.0
        longitude = 80.0

        # Should find Colombo (level 2)
        area = self.env["spp.area"].find_by_coordinates(latitude, longitude, level=2)
        self.assertEqual(area, self.area_colombo)

        # Should not find anything at level 3
        area = self.env["spp.area"].find_by_coordinates(latitude, longitude, level=3)
        self.assertFalse(area)

    def test_find_all_containing(self):
        """Test finding all areas containing a point."""
        # Create parent country area
        country_polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [79.5, 6.5],
                    [81.0, 6.5],
                    [81.0, 8.0],
                    [79.5, 8.0],
                    [79.5, 6.5],
                ]
            ],
        }

        area_country = self.env["spp.area"].create(
            {
                "draft_name": "Sri Lanka",
                "code": "LK",
                "hdx_pcode": "LK",
                "level": 0,
                "geo_polygon": json.dumps(country_polygon),
            }
        )

        # Point inside both country and Colombo
        latitude = 7.0
        longitude = 80.0

        areas = self.env["spp.area"].find_all_containing(latitude, longitude)

        # Should find both country and Colombo
        self.assertIn(area_country, areas)
        self.assertIn(self.area_colombo, areas)
        self.assertEqual(len(areas), 2)

    def test_find_by_pcode(self):
        """Test finding area by P-code."""
        # Find by HDX P-code
        area = self.env["spp.area"].find_by_pcode("LK31")
        self.assertEqual(area, self.area_colombo)

        # Find by code field
        area = self.env["spp.area"].find_by_pcode("LK32")
        self.assertEqual(area, self.area_gampaha)

        # Not found
        area = self.env["spp.area"].find_by_pcode("INVALID")
        self.assertFalse(area)

    def test_hdx_pcode_unique_constraint(self):
        """Test that HDX P-codes must be unique."""
        with self.assertRaises(Exception):
            self.env["spp.area"].create(
                {
                    "draft_name": "Duplicate",
                    "code": "DUP",
                    "hdx_pcode": "LK31",  # Duplicate P-code
                    "level": 2,
                }
            )
