# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from unittest.mock import mock_open, patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_demo_phl_luzon.models.population_weights import DemoPopulationWeights


def _reset_cache():
    """Reset the class-level weights cache."""
    DemoPopulationWeights._weights_cache = None


@tagged("post_install", "-at_install")
class TestPopulationWeights(TransactionCase):
    """Test the population weights model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _reset_cache()

    def tearDown(self):
        super().tearDown()
        _reset_cache()

    def test_get_weights_returns_dict(self):
        """get_weights returns a dict mapping pcode to population."""
        weights = DemoPopulationWeights.get_weights()
        self.assertIsInstance(weights, dict)
        self.assertGreater(len(weights), 0, "Expected at least one weight entry")

    def test_get_weights_parses_csv_correctly(self):
        """Known entries from the CSV are present with correct values."""
        weights = DemoPopulationWeights.get_weights()
        # Adams municipality, Ilocos Norte
        self.assertEqual(weights.get("PH0102801"), 1835)
        # Bacarra municipality
        self.assertEqual(weights.get("PH0102802"), 32994)

    def test_get_weights_count(self):
        """CSV has 771 municipalities (772 lines minus header)."""
        weights = DemoPopulationWeights.get_weights()
        self.assertEqual(len(weights), 771)

    def test_get_weights_caching(self):
        """Second call returns cached result without re-reading CSV."""
        weights1 = DemoPopulationWeights.get_weights()
        weights2 = DemoPopulationWeights.get_weights()
        self.assertIs(weights1, weights2, "Expected same dict object from cache")

    def test_get_weights_skips_invalid_rows(self):
        """Rows with non-integer population are skipped."""
        csv_content = (
            "pcode,name,province_pcode,region_pcode,population\nPH001,Test,PH00,PH0,abc\nPH002,Valid,PH00,PH0,100\n"
        )
        _reset_cache()

        with patch("odoo.tools.misc.file_path", return_value="/fake/path"):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                weights = DemoPopulationWeights.get_weights()

        self.assertNotIn("PH001", weights)
        self.assertEqual(weights.get("PH002"), 100)

    def test_get_weights_empty_csv(self):
        """Empty CSV (header only) returns empty dict."""
        csv_content = "pcode,name,province_pcode,region_pcode,population\n"
        _reset_cache()

        with patch("odoo.tools.misc.file_path", return_value="/fake/path"):
            with patch("builtins.open", mock_open(read_data=csv_content)):
                weights = DemoPopulationWeights.get_weights()

        self.assertEqual(weights, {})

    def test_get_weights_by_area_id_returns_dict(self):
        """get_weights_by_area_id returns a dict mapping area IDs to population."""
        result = self.env["spp.demo.population.weights"].get_weights_by_area_id()
        self.assertIsInstance(result, dict)

    def test_get_weights_by_area_id_maps_to_area_records(self):
        """When matching spp.area records exist, their IDs are used as keys."""
        area = self.env["spp.area"].create(
            {
                "draft_name": "Test Municipality",
                "code": "PH0102801",
            }
        )

        result = self.env["spp.demo.population.weights"].get_weights_by_area_id()
        self.assertIn(area.id, result)
        self.assertEqual(result[area.id], 1835)

    def test_get_weights_by_area_id_skips_unmatched_pcodes(self):
        """Pcodes without matching spp.area records are not in the result."""
        result = self.env["spp.demo.population.weights"].get_weights_by_area_id()
        for key in result:
            self.assertIsInstance(key, int)
