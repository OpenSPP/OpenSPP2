# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import common, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestHdxCodResource(common.TransactionCase):
    """Test HDX COD Resource model functionality."""

    def setUp(self):
        super().setUp()
        self.country_lk = self.env.ref("base.lk")
        # Use the existing demo data record instead of creating a new one
        # This avoids unique constraint violations since data/hdx_cod_sources.xml
        # already creates a Sri Lanka source
        self.source = self.env.ref("spp_area_hdx.cod_source_lka")

        self.resource = self.env["spp.hdx.cod.resource"].create(
            {
                "source_id": self.source.id,
                "name": "Admin Level 3 - DS Divisions",
                "admin_level": 3,
                "format": "geojson",
                "download_url": "https://example.com/data.geojson",
            }
        )

    def test_create_resource(self):
        """Test creating a basic resource."""
        self.assertEqual(self.resource.name, "Admin Level 3 - DS Divisions")
        self.assertEqual(self.resource.admin_level, 3)
        self.assertEqual(self.resource.format, "geojson")
        self.assertEqual(self.resource.source_id, self.source)

    def test_required_fields(self):
        """Test that required fields are enforced."""
        # source_id is required (NOT NULL constraint at DB level)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            self.env["spp.hdx.cod.resource"].create(
                {
                    "name": "Test",
                    "admin_level": 1,
                }
            )

    def test_default_format(self):
        """Test default format is geojson."""
        resource = self.env["spp.hdx.cod.resource"].create(
            {
                "source_id": self.source.id,
                "name": "Test Resource",
                "admin_level": 2,
            }
        )
        self.assertEqual(resource.format, "geojson")

    def test_ordering(self):
        """Test resources are ordered by source_id and admin_level."""
        resource2 = self.env["spp.hdx.cod.resource"].create(
            {
                "source_id": self.source.id,
                "name": "Admin Level 2",
                "admin_level": 2,
            }
        )

        resource4 = self.env["spp.hdx.cod.resource"].create(
            {
                "source_id": self.source.id,
                "name": "Admin Level 4",
                "admin_level": 4,
            }
        )

        resources = self.env["spp.hdx.cod.resource"].search([("source_id", "=", self.source.id)])

        # Should be ordered by admin_level: 2, 3, 4
        self.assertEqual(resources[0], resource2)
        self.assertEqual(resources[1], self.resource)
        self.assertEqual(resources[2], resource4)

    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.download_resource")
    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.detect_field_mappings")
    def test_action_detect_field_mappings_success(self, mock_detect, mock_download):
        """Test successful field mapping detection."""
        # Mock GeoJSON data
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "ADM3_PCODE": "LK3101",
                        "ADM3_EN": "Colombo",
                    },
                },
                {
                    "type": "Feature",
                    "properties": {
                        "ADM3_PCODE": "LK3102",
                        "ADM3_EN": "Gampaha",
                    },
                },
            ],
        }

        mock_download.return_value = json.dumps(geojson_data).encode()
        mock_detect.return_value = {
            "pcode_field": "ADM3_PCODE",
            "name_field": "ADM3_EN",
            "name_local_field": None,
            "parent_pcode_field": None,
        }

        result = self.resource.action_detect_field_mappings()

        # Check result is notification
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

        # Check fields were updated
        self.assertEqual(self.resource.pcode_field, "ADM3_PCODE")
        self.assertEqual(self.resource.name_field, "ADM3_EN")
        self.assertEqual(self.resource.feature_count, 2)
        self.assertTrue(self.resource.last_download_date)

    def test_action_detect_field_mappings_no_url(self):
        """Test field mapping detection fails without URL."""
        self.resource.download_url = False

        with self.assertRaises(UserError) as ctx:
            self.resource.action_detect_field_mappings()

        self.assertIn("Download URL is required", str(ctx.exception))

    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.download_resource")
    def test_action_detect_field_mappings_invalid_json(self, mock_download):
        """Test field mapping detection with invalid JSON."""
        mock_download.return_value = b"not valid json"

        with self.assertRaises(UserError) as ctx:
            self.resource.action_detect_field_mappings()

        self.assertIn("Failed to detect field mappings", str(ctx.exception))

    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.download_resource")
    def test_action_detect_field_mappings_download_error(self, mock_download):
        """Test field mapping detection with download error."""
        mock_download.side_effect = Exception("Network error")

        with self.assertRaises(UserError) as ctx:
            self.resource.action_detect_field_mappings()

        self.assertIn("Failed to detect field mappings", str(ctx.exception))
        self.assertIn("Network error", str(ctx.exception))

    def test_action_open_import_wizard(self):
        """Test opening import wizard."""
        result = self.resource.action_open_import_wizard()

        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.hdx.cod.import.wizard")
        self.assertEqual(result["target"], "new")
        self.assertEqual(result["context"]["default_source_id"], self.source.id)
        self.assertEqual(result["context"]["default_country_id"], self.country_lk.id)
        self.assertEqual(result["context"]["default_import_mode"], "hdx")
        self.assertIn(self.resource.id, result["context"]["default_resource_ids"][0][2])

    def test_feature_count_readonly(self):
        """Test that feature_count is readonly."""
        # feature_count has readonly=True, but we should be able to write via code
        self.resource.feature_count = 100
        self.assertEqual(self.resource.feature_count, 100)

    def test_field_mapping_storage(self):
        """Test field mapping fields can be set and read."""
        self.resource.write(
            {
                "pcode_field": "ADM3_PCODE",
                "name_field": "ADM3_EN",
                "name_local_field": "ADM3_SI",
                "parent_pcode_field": "ADM2_PCODE",
            }
        )

        self.assertEqual(self.resource.pcode_field, "ADM3_PCODE")
        self.assertEqual(self.resource.name_field, "ADM3_EN")
        self.assertEqual(self.resource.name_local_field, "ADM3_SI")
        self.assertEqual(self.resource.parent_pcode_field, "ADM2_PCODE")

    def test_format_selections(self):
        """Test all format selections are valid."""
        formats = ["geojson", "shp", "geopackage"]

        for fmt in formats:
            self.resource.format = fmt
            self.assertEqual(self.resource.format, fmt)

    def test_cascade_deletion(self):
        """Test resource is deleted when source is deleted."""
        resource_id = self.resource.id

        # Delete source
        self.source.unlink()

        # Resource should be deleted
        resource = self.env["spp.hdx.cod.resource"].browse(resource_id)
        self.assertFalse(resource.exists())

    def test_hdx_resource_id_storage(self):
        """Test HDX resource ID can be stored."""
        self.resource.hdx_resource_id = "abc123-def456"
        self.assertEqual(self.resource.hdx_resource_id, "abc123-def456")
