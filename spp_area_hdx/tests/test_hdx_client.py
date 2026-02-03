# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from unittest.mock import MagicMock, patch

from odoo.tests import common, tagged

from ..services.hdx_client import HdxClient


@tagged("post_install", "-at_install")
class TestHdxClient(common.TransactionCase):
    """Test HDX API client functionality."""

    def setUp(self):
        super().setUp()
        self.client = HdxClient()

    @patch("requests.Session.get")
    def test_get_dataset(self, mock_get):
        """Test fetching dataset metadata."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "name": "cod-ab-lka",
                "title": "Sri Lanka - Subnational Administrative Boundaries",
                "resources": [
                    {
                        "id": "resource-1",
                        "name": "Admin Level 3",
                        "format": "GeoJSON",
                        "url": "https://example.com/data.geojson",
                    }
                ],
            }
        }
        mock_get.return_value = mock_response

        # Call method
        result = self.client.get_dataset("cod-ab-lka")

        # Assertions
        self.assertEqual(result["name"], "cod-ab-lka")
        self.assertEqual(len(result["resources"]), 1)
        mock_get.assert_called_once()

    @patch("requests.Session.get")
    def test_search_cod_datasets(self, mock_get):
        """Test searching COD datasets by country."""
        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "name": "cod-ab-lka",
                "title": "Sri Lanka - Subnational Administrative Boundaries",
            }
        }
        mock_get.return_value = mock_response

        # Call method
        result = self.client.search_cod_datasets("LKA")

        # Assertions
        self.assertEqual(result["name"], "cod-ab-lka")
        # Should convert to lowercase
        call_args = mock_get.call_args
        self.assertIn("cod-ab-lka", str(call_args))

    def test_get_geojson_resources(self):
        """Test filtering GeoJSON resources."""
        dataset = {
            "resources": [
                {"name": "Admin 1", "format": "GeoJSON"},
                {"name": "Admin 2", "format": "Shapefile"},
                {"name": "Admin 3", "format": "geojson"},
                {"name": "Admin 4", "format": "CSV"},
            ]
        }

        geojson_resources = self.client.get_geojson_resources(dataset)

        self.assertEqual(len(geojson_resources), 2)
        self.assertEqual(geojson_resources[0]["name"], "Admin 1")
        self.assertEqual(geojson_resources[1]["name"], "Admin 3")

    def test_detect_admin_level(self):
        """Test detecting admin level from resource name."""
        test_cases = [
            ("Admin Level 3 - Districts", 3),
            ("ADM2 Boundaries", 2),
            ("adm_3_divisions", 3),
            ("Administrative Level 1", 1),
            ("Some other name", None),
        ]

        for name, expected_level in test_cases:
            with self.subTest(name=name):
                result = self.client.detect_admin_level(name)
                self.assertEqual(result, expected_level)

    def test_detect_field_mappings(self):
        """Test detecting field mappings from GeoJSON."""
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "ADM3_PCODE": "LK3101",
                        "ADM3_EN": "Colombo",
                        "ADM3_SI": "කොළඹ",
                        "ADM2_PCODE": "LK31",
                        "AREA_SQKM": 100.5,
                    },
                    "geometry": {"type": "Point", "coordinates": [80.0, 7.0]},
                }
            ],
        }

        mappings = self.client.detect_field_mappings(geojson_data)

        self.assertEqual(mappings["pcode_field"], "ADM3_PCODE")
        self.assertEqual(mappings["name_field"], "ADM3_EN")
        self.assertEqual(mappings["name_local_field"], "ADM3_SI")
        self.assertEqual(mappings["parent_pcode_field"], "ADM2_PCODE")

    def test_detect_field_mappings_empty(self):
        """Test field mapping detection with empty features."""
        geojson_data = {"type": "FeatureCollection", "features": []}

        mappings = self.client.detect_field_mappings(geojson_data)

        self.assertIsNone(mappings["pcode_field"])
        self.assertIsNone(mappings["name_field"])
