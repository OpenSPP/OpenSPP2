# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.hdx_client import HdxClient

_logger = logging.getLogger(__name__)


class HdxCodSource(models.Model):
    """
    Track COD datasets available from HDX.

    This model maintains a registry of Common Operational Datasets (COD)
    for administrative boundaries available from the Humanitarian Data Exchange (HDX).
    """

    _name = "spp.hdx.cod.source"
    _description = "HDX COD Source"
    _order = "country_id"

    country_id = fields.Many2one("res.country", required=True, ondelete="cascade", string="Country")
    country_iso3 = fields.Char(compute="_compute_country_iso3", store=True, string="ISO3 Code")
    hdx_dataset_id = fields.Char(
        string="HDX Dataset ID",
        help="HDX dataset identifier (e.g., 'cod-ab-lka')",
    )
    hdx_dataset_url = fields.Char(string="HDX Dataset URL")

    resource_ids = fields.One2many("spp.hdx.cod.resource", "source_id", string="Admin Levels")

    last_sync_date = fields.Datetime(string="Last Sync", readonly=True)
    last_import_date = fields.Datetime(string="Last Import", readonly=True)
    areas_updated = fields.Integer(string="Areas Updated", default=0, readonly=True)

    active = fields.Boolean(default=True)

    _country_unique = models.Constraint("UNIQUE(country_id)", "Only one COD source per country is allowed")

    @api.depends("country_id", "hdx_dataset_id")
    def _compute_country_iso3(self):
        """Compute ISO3 code from HDX dataset ID or country.

        HDX dataset IDs follow the pattern ``cod-ab-{iso3}`` (e.g., ``cod-ab-phl``),
        which contains the correct 3-letter ISO code.  Falls back to the 2-letter
        ``res.country.code`` when the dataset ID is not set.
        """
        for record in self:
            if record.hdx_dataset_id and record.hdx_dataset_id.startswith("cod-ab-"):
                record.country_iso3 = record.hdx_dataset_id[len("cod-ab-") :].upper()
            elif record.country_id:
                record.country_iso3 = record.country_id.code
            else:
                record.country_iso3 = False

    def action_sync_from_hdx(self):
        """
        Sync resources from HDX.

        Fetches dataset metadata from HDX API and creates/updates
        resource records for each admin level.
        """
        self.ensure_one()

        if not self.country_iso3:
            raise UserError(_("Country ISO3 code is required to sync from HDX"))

        try:
            client = HdxClient()

            # Use existing dataset ID if available, otherwise search by ISO3
            if self.hdx_dataset_id:
                dataset = client.get_dataset(self.hdx_dataset_id)
            else:
                dataset = client.search_cod_datasets(self.country_iso3)

            if not dataset:
                raise UserError(_("No COD dataset found for country %s") % self.country_id.name)

            # Update dataset info
            self.hdx_dataset_id = dataset.get("name")
            self.hdx_dataset_url = f"https://data.humdata.org/dataset/{dataset.get('name')}"

            # Get GeoJSON resources
            geojson_resources = client.get_geojson_resources(dataset)

            if not geojson_resources:
                raise UserError(_("No GeoJSON resources found in dataset"))

            # Create/update resource records
            for resource_data in geojson_resources:
                resource_name = resource_data.get("name", "")
                resource_id = resource_data.get("id")
                download_url = resource_data.get("url")

                # Detect admin level from resource name
                admin_level = client.detect_admin_level(resource_name)

                # Check if resource already exists
                _rid, _lvl = resource_id, admin_level
                existing_resource = self.resource_ids.filtered(
                    lambda r, rid=_rid, lvl=_lvl: r.hdx_resource_id == rid or r.admin_level == lvl
                )

                resource_vals = {
                    "source_id": self.id,
                    "name": resource_name,
                    "admin_level": admin_level or 0,
                    "format": "geojson",
                    "hdx_resource_id": resource_id,
                    "download_url": download_url,
                }

                if existing_resource:
                    existing_resource.write(resource_vals)
                else:
                    self.env["spp.hdx.cod.resource"].create(resource_vals)

            self.last_sync_date = fields.Datetime.now()

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Synced %d resources from HDX") % len(geojson_resources),
                    "type": "success",
                    "sticky": False,
                },
            }

        except Exception as error:
            _logger.error("Error syncing from HDX: %s", str(error))
            raise UserError(_("Failed to sync from HDX: %s") % str(error)) from error

    def action_open_import_wizard(self):
        """Open import wizard for this COD source."""
        self.ensure_one()

        return {
            "name": _("Import COD from HDX"),
            "type": "ir.actions.act_window",
            "res_model": "spp.hdx.cod.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_source_id": self.id,
                "default_country_id": self.country_id.id,
                "default_import_mode": "hdx",
            },
        }
