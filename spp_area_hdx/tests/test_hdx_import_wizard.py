# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import base64
import json
from unittest.mock import patch

from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestHdxImportWizard(common.TransactionCase):
    """Test HDX COD Import Wizard functionality."""

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
                "name": "Admin Level 3",
                "admin_level": 3,
                "format": "geojson",
                "download_url": "https://example.com/data.geojson",
                "pcode_field": "ADM3_PCODE",
                "name_field": "ADM3_EN",
            }
        )

        # Create existing area for matching
        self.area_existing = self.env["spp.area"].create(
            {
                "draft_name": "Colombo",
                "code": "LK3101",
                "hdx_pcode": "LK3101",
                "level": 3,
            }
        )

    def test_wizard_creation(self):
        """Test wizard can be created."""
        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "hdx",
                "source_id": self.source.id,
            }
        )

        self.assertEqual(wizard.import_mode, "hdx")
        self.assertEqual(wizard.source_id, self.source)
        self.assertEqual(wizard.state, "config")

    def test_onchange_source_id(self):
        """Test source selection updates country."""
        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "hdx",
            }
        )

        wizard.source_id = self.source
        wizard._onchange_source_id()

        self.assertEqual(wizard.country_id, self.country_lk)

    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.download_resource")
    def test_preview_hdx_import(self, mock_download):
        """Test preview generation for HDX import."""
        # Mock GeoJSON data
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"ADM3_PCODE": "LK3101", "ADM3_EN": "Colombo"},
                    "geometry": {"type": "Point", "coordinates": [80.0, 7.0]},
                },
                {
                    "type": "Feature",
                    "properties": {"ADM3_PCODE": "LK3102", "ADM3_EN": "Gampaha"},
                    "geometry": {"type": "Point", "coordinates": [80.0, 7.2]},
                },
            ],
        }

        mock_download.return_value = json.dumps(geojson_data).encode()

        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "hdx",
                "source_id": self.source.id,
                "resource_ids": [(6, 0, [self.resource.id])],
                "create_missing": True,
            }
        )

        wizard.action_preview()

        # Should match 1 existing area and find 1 missing
        self.assertEqual(wizard.preview_matched, 1)
        self.assertEqual(wizard.preview_missing, 1)
        self.assertEqual(wizard.preview_new, 1)
        self.assertEqual(wizard.state, "preview")

    def test_preview_file_import(self):
        """Test preview generation for file upload."""
        # Create GeoJSON file
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"ADM3_PCODE": "LK3101", "ADM3_EN": "Colombo"},
                    "geometry": {"type": "Point", "coordinates": [80.0, 7.0]},
                },
            ],
        }

        file_content = json.dumps(geojson_data)
        file_data = base64.b64encode(file_content.encode())

        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "file",
                "file_data": file_data,
                "file_name": "test.geojson",
                "file_admin_level": 3,
                "pcode_field": "ADM3_PCODE",
                "name_field": "ADM3_EN",
            }
        )

        wizard.action_preview()

        # Should match 1 existing area
        self.assertEqual(wizard.preview_matched, 1)
        self.assertEqual(wizard.preview_missing, 0)
        self.assertEqual(wizard.state, "preview")

    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.download_resource")
    def test_import_from_hdx_update_existing(self, mock_download):
        """Test importing from HDX updates existing areas."""
        # Mock GeoJSON data with polygon
        polygon = {
            "type": "Polygon",
            "coordinates": [[[79.8, 6.8], [80.2, 6.8], [80.2, 7.2], [79.8, 7.2], [79.8, 6.8]]],
        }

        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "ADM3_PCODE": "LK3101",
                        "ADM3_EN": "Colombo Updated",
                    },
                    "geometry": polygon,
                }
            ],
        }

        mock_download.return_value = json.dumps(geojson_data).encode()

        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "hdx",
                "source_id": self.source.id,
                "resource_ids": [(6, 0, [self.resource.id])],
                "update_existing": True,
                "update_names": True,
            }
        )

        wizard.action_import()

        # Check area was updated
        self.area_existing.invalidate_recordset()
        self.assertTrue(self.area_existing.geo_polygon)
        self.assertTrue(self.area_existing.hdx_last_update)
        self.assertEqual(self.area_existing.draft_name, "Colombo Updated")

    @patch("odoo.addons.spp_area_hdx.services.hdx_client.HdxClient.download_resource")
    def test_import_from_hdx_create_missing(self, mock_download):
        """Test importing from HDX creates missing areas."""
        # Mock GeoJSON data with new area
        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"ADM3_PCODE": "LK3199", "ADM3_EN": "New Area"},
                    "geometry": {"type": "Point", "coordinates": [80.0, 7.0]},
                }
            ],
        }

        mock_download.return_value = json.dumps(geojson_data).encode()

        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "hdx",
                "source_id": self.source.id,
                "resource_ids": [(6, 0, [self.resource.id])],
                "create_missing": True,
            }
        )

        wizard.action_import()

        # Check new area was created
        new_area = self.env["spp.area"].search([("hdx_pcode", "=", "LK3199")])
        self.assertTrue(new_area)
        self.assertEqual(new_area.draft_name, "New Area")
        self.assertEqual(new_area.level, 3)

    def test_import_from_file(self):
        """Test importing from uploaded file."""
        # Create GeoJSON file
        polygon = {
            "type": "Polygon",
            "coordinates": [[[79.8, 6.8], [80.2, 6.8], [80.2, 7.2], [79.8, 7.2], [79.8, 6.8]]],
        }

        geojson_data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"ADM3_PCODE": "LK3101", "ADM3_EN": "Colombo"},
                    "geometry": polygon,
                }
            ],
        }

        file_content = json.dumps(geojson_data)
        file_data = base64.b64encode(file_content.encode())

        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "file",
                "file_data": file_data,
                "file_name": "test.geojson",
                "file_admin_level": 3,
                "pcode_field": "ADM3_PCODE",
                "name_field": "ADM3_EN",
                "update_existing": True,
            }
        )

        wizard.action_import()

        # Check area was updated
        self.area_existing.invalidate_recordset()
        self.assertTrue(self.area_existing.geo_polygon)
        self.assertTrue(self.area_existing.hdx_last_update)

    def test_action_back_to_config(self):
        """Test going back to configuration."""
        wizard = self.env["spp.hdx.cod.import.wizard"].create(
            {
                "import_mode": "hdx",
                "state": "preview",
            }
        )

        wizard.action_back_to_config()

        self.assertEqual(wizard.state, "config")
