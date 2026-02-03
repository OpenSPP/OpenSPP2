# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

from ..services.hdx_client import HdxClient

_logger = logging.getLogger(__name__)


class HdxCodResource(models.Model):
    """
    Individual admin level resource within a COD.

    Represents a specific administrative level dataset (e.g., Admin Level 3)
    within a COD package from HDX.
    """

    _name = "spp.hdx.cod.resource"
    _description = "HDX COD Resource"
    _order = "source_id, admin_level"

    source_id = fields.Many2one("spp.hdx.cod.source", required=True, ondelete="cascade", string="COD Source")
    name = fields.Char(required=True, string="Resource Name")
    admin_level = fields.Integer(required=True, string="Admin Level", help="Administrative level (0, 1, 2, 3, 4)")

    format = fields.Selection(
        [
            ("geojson", "GeoJSON"),
            ("shp", "Shapefile"),
            ("geopackage", "GeoPackage"),
        ],
        default="geojson",
        string="Format",
    )

    hdx_resource_id = fields.Char(string="HDX Resource ID")
    download_url = fields.Char(string="Download URL")

    # Field mappings (detected from HXL or manual)
    pcode_field = fields.Char(
        string="P-code Field",
        help="Field name containing P-codes (e.g., 'ADM3_PCODE')",
    )
    name_field = fields.Char(
        string="Name Field",
        help="Field name containing area names (e.g., 'ADM3_EN')",
    )
    name_local_field = fields.Char(
        string="Local Name Field",
        help="Field name containing local language names (e.g., 'ADM3_SI')",
    )
    parent_pcode_field = fields.Char(
        string="Parent P-code Field",
        help="Field name containing parent P-codes (e.g., 'ADM2_PCODE')",
    )

    feature_count = fields.Integer(string="Feature Count", default=0, readonly=True)
    last_download_date = fields.Datetime(readonly=True, string="Last Downloaded")

    def action_detect_field_mappings(self):
        """
        Detect field mappings from GeoJSON.

        Downloads the resource and analyzes the first feature to detect
        field names for P-codes, names, and parent P-codes.
        """
        self.ensure_one()

        if not self.download_url:
            raise UserError(_("Download URL is required to detect field mappings"))

        try:
            client = HdxClient()
            content = client.download_resource(self.download_url)

            # Parse GeoJSON
            geojson_data = json.loads(content)

            # Detect field mappings
            mappings = client.detect_field_mappings(geojson_data)

            # Update fields
            self.write(
                {
                    "pcode_field": mappings.get("pcode_field"),
                    "name_field": mappings.get("name_field"),
                    "name_local_field": mappings.get("name_local_field"),
                    "parent_pcode_field": mappings.get("parent_pcode_field"),
                    "last_download_date": fields.Datetime.now(),
                }
            )

            # Count features
            features = geojson_data.get("features", [])
            self.feature_count = len(features)

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Field mappings detected. Found %d features.") % len(features),
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as error:
            _logger.error("Error detecting field mappings: %s", str(error))
            raise UserError(_("Failed to detect field mappings: %s") % str(error)) from error

    def action_open_import_wizard(self):
        """Open import wizard for this resource."""
        self.ensure_one()

        return {
            "name": _("Import COD Resource"),
            "type": "ir.actions.act_window",
            "res_model": "spp.hdx.cod.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_source_id": self.source_id.id,
                "default_country_id": self.source_id.country_id.id,
                "default_import_mode": "hdx",
                "default_resource_ids": [Command.set([self.id])],
            },
        }
