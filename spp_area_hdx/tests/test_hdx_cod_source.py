# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.tests import common, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestHdxCodSource(common.TransactionCase):
    """Test HDX COD Source model functionality."""

    def setUp(self):
        super().setUp()
        self.country_lk = self.env.ref("base.lk")
        # Use the existing demo data record instead of creating a new one
        # This avoids unique constraint violations since data/hdx_cod_sources.xml
        # already creates a Sri Lanka source
        self.source = self.env.ref("spp_area_hdx.cod_source_lka")

    def test_compute_country_iso3(self):
        """Test ISO3 code computation from hdx_dataset_id."""
        self.assertEqual(self.source.country_iso3, "LKA")

    def test_unique_country_constraint(self):
        """Test that only one source per country is allowed."""
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["spp.hdx.cod.source"].create(
                {
                    "country_id": self.country_lk.id,
                    "hdx_dataset_id": "duplicate",
                }
            )

    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.get_dataset")
    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.get_geojson_resources")
    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.detect_admin_level")
    def test_action_sync_from_hdx(self, mock_detect_level, mock_get_resources, mock_get_dataset):
        """Test syncing resources from HDX."""
        # Mock HDX API responses — source has hdx_dataset_id set, so get_dataset is called
        mock_get_dataset.return_value = {
            "name": "cod-ab-lka",
            "title": "Sri Lanka Administrative Boundaries",
        }

        mock_get_resources.return_value = [
            {
                "id": "resource-1",
                "name": "Admin Level 3 - DS Divisions",
                "url": "https://example.com/adm3.geojson",
            }
        ]

        mock_detect_level.return_value = 3

        # Call sync action
        result = self.source.action_sync_from_hdx()

        # Assertions
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertTrue(self.source.last_sync_date)
        self.assertEqual(len(self.source.resource_ids), 1)

        resource = self.source.resource_ids[0]
        self.assertEqual(resource.name, "Admin Level 3 - DS Divisions")
        self.assertEqual(resource.admin_level, 3)
        self.assertEqual(resource.hdx_resource_id, "resource-1")

    def test_action_open_import_wizard(self):
        """Test opening import wizard."""
        result = self.source.action_open_import_wizard()

        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.hdx.cod.import.wizard")
        self.assertEqual(result["context"]["default_source_id"], self.source.id)
        self.assertEqual(result["context"]["default_country_id"], self.country_lk.id)
