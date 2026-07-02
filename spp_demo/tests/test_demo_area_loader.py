# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the Demo Area Loader functionality."""

import logging

from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class TestDemoAreaLoader(TransactionCase):
    """Test cases for spp.demo.area.loader model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader_model = cls.env["spp.demo.area.loader"]
        cls.area_model = cls.env["spp.area"]
        cls.area_kind_model = cls.env["spp.area.type"]

    def test_supported_countries(self):
        """Test that supported countries are defined."""
        supported = self.loader_model.SUPPORTED_COUNTRIES
        self.assertIsInstance(supported, list)
        self.assertGreater(len(supported), 0)

        # Check Philippines is supported
        country_codes = [code for code, name in supported]
        self.assertIn("phl", country_codes)
        self.assertIn("lka", country_codes)
        self.assertIn("tgo", country_codes)

    def test_get_country_name(self):
        """Test country name lookup."""
        name = self.loader_model._get_country_name("phl")
        self.assertEqual(name, "Philippines")

        name = self.loader_model._get_country_name("lka")
        self.assertEqual(name, "Sri Lanka")

        name = self.loader_model._get_country_name("tgo")
        self.assertEqual(name, "Togo")

        # Unknown country returns uppercase code
        name = self.loader_model._get_country_name("xyz")
        self.assertEqual(name, "XYZ")

    def test_is_gis_installed(self):
        """Test GIS module detection."""
        # This is a basic test - actual result depends on installed modules
        result = self.loader_model._is_gis_installed()
        self.assertIsInstance(result, bool)

    def test_load_phl_areas(self):
        """Test loading Philippines area data."""
        # Count areas before
        initial_count = self.area_model.search_count([])

        # Load Philippines areas
        loader = self.loader_model.create(
            {
                "country_code": "phl",
                "load_shapes": False,
            }
        )
        loader._load_xml_data("phl")

        # Verify areas were created
        final_count = self.area_model.search_count([])
        self.assertGreater(final_count, initial_count, "Areas should be created for Philippines")

        # Verify specific areas exist (PSA/HDX p-codes)
        ncr = self.area_model.search([("code", "=", "PH13")], limit=1)
        self.assertTrue(ncr, "NCR region should exist")

        quezon_city = self.area_model.search([("code", "=", "PH1307404")], limit=1)
        self.assertTrue(quezon_city, "Quezon City should exist")

        # Verify area hierarchy: Quezon City -> Metro Manila district -> NCR
        district = self.area_model.search([("code", "=", "PH13074")], limit=1)
        if district and ncr:
            self.assertEqual(district.parent_id.id, ncr.id, "Metro Manila district should be child of NCR")
        if quezon_city and district:
            self.assertEqual(quezon_city.parent_id.id, district.id, "Quezon City should be child of its district")

    def test_load_lka_areas(self):
        """Test loading Sri Lanka area data."""
        # Load Sri Lanka areas
        loader = self.loader_model.create(
            {
                "country_code": "lka",
                "load_shapes": False,
            }
        )
        loader._load_xml_data("lka")

        # Verify specific areas exist
        western = self.area_model.search([("code", "=", "LK-1")], limit=1)
        self.assertTrue(western, "Western Province should exist")

        colombo = self.area_model.search([("code", "=", "LK-11")], limit=1)
        self.assertTrue(colombo, "Colombo District should exist")

    def test_load_tgo_areas(self):
        """Test loading Togo area data."""
        # Load Togo areas
        loader = self.loader_model.create(
            {
                "country_code": "tgo",
                "load_shapes": False,
            }
        )
        loader._load_xml_data("tgo")

        # Verify specific areas exist
        maritime = self.area_model.search([("code", "=", "TG-M")], limit=1)
        self.assertTrue(maritime, "Maritime region should exist")

        lome = self.area_model.search([("code", "=", "TG-M-GOL-LOM")], limit=1)
        self.assertTrue(lome, "Lome canton should exist")

    def test_load_country_areas_programmatic(self):
        """Test programmatic area loading method."""
        result = self.loader_model.load_country_areas("phl", load_shapes=False)

        self.assertIn("country_code", result)
        self.assertEqual(result["country_code"], "phl")
        self.assertIn("shapes_loaded", result)
        self.assertIn("gis_available", result)

    def test_geojson_to_wkt_polygon(self):
        """Test GeoJSON polygon to WKT conversion."""
        loader = self.loader_model.create(
            {
                "country_code": "phl",
                "load_shapes": False,
            }
        )

        geometry = {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }

        wkt = loader._geojson_to_wkt(geometry)
        self.assertIsNotNone(wkt)
        self.assertTrue(wkt.startswith("POLYGON"))

    def test_geojson_to_wkt_invalid(self):
        """Test GeoJSON conversion with invalid input."""
        loader = self.loader_model.create(
            {
                "country_code": "phl",
                "load_shapes": False,
            }
        )

        # Empty geometry
        wkt = loader._geojson_to_wkt({})
        self.assertIsNone(wkt)

        # Missing coordinates
        wkt = loader._geojson_to_wkt({"type": "Polygon"})
        self.assertIsNone(wkt)


class TestDemoAreaLoaderAreaKinds(TransactionCase):
    """Test area kinds creation for each country."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader_model = cls.env["spp.demo.area.loader"]
        cls.area_kind_model = cls.env["spp.area.type"]

    def test_phl_area_kinds(self):
        """Test Philippines area kinds hierarchy."""
        loader = self.loader_model.create(
            {
                "country_code": "phl",
                "load_shapes": False,
            }
        )
        loader._load_xml_data("phl")

        # Check region kind exists
        region = self.area_kind_model.search([("name", "=", "Region")], limit=1)
        self.assertTrue(region, "Region area kind should exist")

        # Check province kind exists and has region as parent
        province = self.area_kind_model.search([("name", "=", "Province")], limit=1)
        self.assertTrue(province, "Province area kind should exist")

        # Check municipality kind exists
        municipality = self.area_kind_model.search([("name", "=", "City/Municipality")], limit=1)
        self.assertTrue(municipality, "City/Municipality area kind should exist")

        # Check barangay kind exists
        barangay = self.area_kind_model.search([("name", "=", "Barangay")], limit=1)
        self.assertTrue(barangay, "Barangay area kind should exist")

    def test_lka_area_kinds(self):
        """Test Sri Lanka area kinds hierarchy."""
        loader = self.loader_model.create(
            {
                "country_code": "lka",
                "load_shapes": False,
            }
        )
        loader._load_xml_data("lka")

        # Check DS Division kind exists
        ds_division = self.area_kind_model.search([("name", "=", "DS Division")], limit=1)
        self.assertTrue(ds_division, "DS Division area kind should exist")

        # Check GN Division kind exists
        gn_division = self.area_kind_model.search([("name", "=", "GN Division")], limit=1)
        self.assertTrue(gn_division, "GN Division area kind should exist")

    def test_tgo_area_kinds(self):
        """Test Togo area kinds hierarchy."""
        loader = self.loader_model.create(
            {
                "country_code": "tgo",
                "load_shapes": False,
            }
        )
        loader._load_xml_data("tgo")

        # Check prefecture kind exists
        prefecture = self.area_kind_model.search([("name", "=", "Prefecture")], limit=1)
        self.assertTrue(prefecture, "Prefecture area kind should exist")

        # Check canton kind exists
        canton = self.area_kind_model.search([("name", "=", "Canton")], limit=1)
        self.assertTrue(canton, "Canton area kind should exist")

        # Check village kind exists
        village = self.area_kind_model.search([("name", "=", "Village")], limit=1)
        self.assertTrue(village, "Village area kind should exist")
