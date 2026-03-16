# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLuzonAreaLoader(TransactionCase):
    """Test the Luzon area loader model."""

    def _load_base_areas(self):
        """Helper: load base PHL area kinds and areas from spp_demo."""
        self.env["spp.demo.area.loader"].load_country_areas("phl", load_shapes=False)

    def test_loader_model_exists(self):
        """The loader model is registered in the environment."""
        self.assertIn("spp.demo.luzon.area.loader", self.env)

    def test_load_luzon_areas_creates_areas(self):
        """Loading Luzon areas creates spp.area records."""
        self._load_base_areas()

        before_count = self.env["spp.area"].search_count([])
        result = self.env["spp.demo.luzon.area.loader"].load_luzon_areas(load_shapes=False)
        after_count = self.env["spp.area"].search_count([])
        areas_created = after_count - before_count

        self.assertGreater(areas_created, 0, "Expected Luzon areas to be created")
        self.assertEqual(result["areas_created"], areas_created)

    def test_load_luzon_areas_creates_regions(self):
        """Luzon data includes all 8 Luzon regions."""
        self._load_base_areas()
        self.env["spp.demo.luzon.area.loader"].load_luzon_areas(load_shapes=False)

        luzon_region_codes = ["PH01", "PH02", "PH03", "PH04", "PH05", "PH13", "PH14", "PH17"]
        for code in luzon_region_codes:
            area = self.env["spp.area"].search([("code", "=", code)], limit=1)
            self.assertTrue(area, f"Expected region with code {code} to exist")

    def test_load_luzon_areas_creates_municipalities(self):
        """Luzon data includes municipalities."""
        self._load_base_areas()
        self.env["spp.demo.luzon.area.loader"].load_luzon_areas(load_shapes=False)

        # Quezon City
        area = self.env["spp.area"].search([("code", "=", "PH1307404")], limit=1)
        self.assertTrue(area, "Expected Quezon City area to exist")

    def test_load_luzon_areas_handles_overlapping_base_areas(self):
        """Loading Luzon areas does not fail when base PHL areas exist.

        The base spp_demo loads NCR (PH13) and CALABARZON (PH04).
        The Luzon loader must handle these overlapping codes gracefully.
        """
        self._load_base_areas()

        # Verify base areas exist
        ph04 = self.env["spp.area"].search([("code", "=", "PH04")], limit=1)
        self.assertTrue(ph04, "Expected CALABARZON (PH04) from base data")

        # Loading Luzon should not raise
        result = self.env["spp.demo.luzon.area.loader"].load_luzon_areas(load_shapes=False)
        self.assertGreater(result["areas_created"], 0)

        # PH04 should still exist (not duplicated)
        ph04_count = self.env["spp.area"].search_count([("code", "=", "PH04")])
        self.assertEqual(ph04_count, 1, "PH04 should not be duplicated")

    def test_load_luzon_areas_idempotent(self):
        """Loading twice does not create duplicate areas."""
        self._load_base_areas()
        self.env["spp.demo.luzon.area.loader"].load_luzon_areas(load_shapes=False)
        count_after_first = self.env["spp.area"].search_count([])

        self.env["spp.demo.luzon.area.loader"].load_luzon_areas(load_shapes=False)
        count_after_second = self.env["spp.area"].search_count([])

        self.assertEqual(count_after_first, count_after_second, "Second load should not create duplicates")
