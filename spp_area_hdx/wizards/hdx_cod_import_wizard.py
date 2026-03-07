# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import base64
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..services.hdx_client import HdxClient

_logger = logging.getLogger(__name__)


class HdxCodImportWizard(models.TransientModel):
    """
    Wizard to download and import COD from HDX.

    Supports two modes:
    1. Download from HDX: Fetch GeoJSON from HDX API
    2. Upload file: Import from manually uploaded GeoJSON file

    Multi-step process:
    - Configuration: Select mode, country/source, levels
    - Preview: Show matched/missing/new counts
    - Import: Process features and update areas
    """

    _name = "spp.hdx.cod.import.wizard"
    _description = "HDX COD Import Wizard"

    # Step 1: Source selection
    import_mode = fields.Selection(
        [
            ("hdx", "Download from HDX"),
            ("file", "Upload GeoJSON File"),
        ],
        default="hdx",
        required=True,
        string="Import Mode",
    )

    country_id = fields.Many2one("res.country", string="Country")
    source_id = fields.Many2one("spp.hdx.cod.source", string="COD Source")

    # For file upload mode
    file_data = fields.Binary(string="GeoJSON File")
    file_name = fields.Char(string="File Name")
    file_admin_level = fields.Integer(string="Admin Level", default=1)

    # For HDX mode - field mappings
    pcode_field = fields.Char(string="P-code Field", help="Field containing P-codes (e.g., 'ADM3_PCODE')")
    name_field = fields.Char(string="Name Field", help="Field containing area names (e.g., 'ADM3_EN')")
    name_local_field = fields.Char(string="Local Name Field", help="Field containing local names")
    parent_pcode_field = fields.Char(string="Parent P-code Field", help="Field containing parent P-codes")

    # Step 2: Level selection (for HDX mode)
    resource_ids = fields.Many2many("spp.hdx.cod.resource", string="Admin Levels to Import")

    # Step 3: Options
    update_existing = fields.Boolean(
        default=True,
        string="Update Existing Areas",
        help="Update existing areas matched by P-code with polygons",
    )
    create_missing = fields.Boolean(
        default=False,
        string="Create Missing Areas",
        help="Create new spp.area records for P-codes not found",
    )
    update_names = fields.Boolean(
        default=False,
        string="Update Names",
        help="Update area names from COD (may override local names)",
    )

    # Progress
    state = fields.Selection(
        [
            ("config", "Configuration"),
            ("preview", "Preview"),
            ("importing", "Importing"),
            ("done", "Done"),
        ],
        default="config",
        string="State",
    )

    preview_matched = fields.Integer(string="Areas to Update", readonly=True)
    preview_missing = fields.Integer(string="P-codes Not Found", readonly=True)
    preview_new = fields.Integer(string="Areas to Create", readonly=True)

    import_log = fields.Text(string="Import Log", readonly=True)

    @api.onchange("source_id")
    def _onchange_source_id(self):
        """Load resources when source changes."""
        if self.source_id:
            self.country_id = self.source_id.country_id
            self.resource_ids = False

    def action_preview(self):
        """Generate preview of import."""
        self.ensure_one()

        try:
            if self.import_mode == "hdx":
                self._preview_hdx_import()
            else:
                self._preview_file_import()

            self.state = "preview"

            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        except Exception as error:
            _logger.error("Error generating preview: %s", str(error))
            raise UserError(_("Failed to generate preview: %s") % str(error)) from error

    def _preview_hdx_import(self):
        """Preview HDX import."""
        if not self.resource_ids:
            raise UserError(_("Please select at least one admin level to import"))

        matched = 0
        missing = 0
        new = 0

        for resource in self.resource_ids:
            if not resource.download_url:
                continue

            # Download and parse GeoJSON
            client = HdxClient()
            content = client.download_resource(resource.download_url)
            geojson_data = json.loads(content)

            # Get field mappings
            pcode_field = resource.pcode_field
            if not pcode_field:
                mappings = client.detect_field_mappings(geojson_data)
                pcode_field = mappings.get("pcode_field")

            if not pcode_field:
                raise UserError(_("Cannot detect P-code field for %s") % resource.name)

            # Count matched/missing
            features = geojson_data.get("features", [])
            for feature in features:
                pcode = feature.get("properties", {}).get(pcode_field)
                if not pcode:
                    continue

                area = self.env["spp.area"].find_by_pcode(pcode)
                if area:
                    matched += 1
                else:
                    missing += 1
                    if self.create_missing:
                        new += 1

        self.preview_matched = matched
        self.preview_missing = missing
        self.preview_new = new

    def _preview_file_import(self):
        """Preview file import."""
        if not self.file_data:
            raise UserError(_("Please upload a GeoJSON file"))

        # Decode and parse GeoJSON
        content = base64.b64decode(self.file_data)
        geojson_data = json.loads(content)

        # Detect field mappings if not set
        if not self.pcode_field:
            client = HdxClient()
            mappings = client.detect_field_mappings(geojson_data)
            self.pcode_field = mappings.get("pcode_field")
            self.name_field = mappings.get("name_field")
            self.name_local_field = mappings.get("name_local_field")
            self.parent_pcode_field = mappings.get("parent_pcode_field")

        if not self.pcode_field:
            raise UserError(_("Cannot detect P-code field. Please set manually."))

        # Count matched/missing
        matched = 0
        missing = 0
        new = 0

        features = geojson_data.get("features", [])
        for feature in features:
            pcode = feature.get("properties", {}).get(self.pcode_field)
            if not pcode:
                continue

            area = self.env["spp.area"].find_by_pcode(pcode)
            if area:
                matched += 1
            else:
                missing += 1
                if self.create_missing:
                    new += 1

        self.preview_matched = matched
        self.preview_missing = missing
        self.preview_new = new

    def action_import(self):
        """Execute import."""
        self.ensure_one()

        try:
            if self.import_mode == "hdx":
                self._import_from_hdx()
            else:
                self._import_from_file()

            self.state = "done"

            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        except Exception as error:
            _logger.error("Error importing: %s", str(error))
            self.import_log = f"{self.import_log or ''}\nERROR: {str(error)}"
            raise UserError(_("Failed to import: %s") % str(error)) from error

    def _import_from_hdx(self):
        """Import from HDX."""
        if not self.resource_ids:
            raise UserError(_("Please select at least one admin level to import"))

        log_lines = []
        total_updated = 0
        total_created = 0
        total_errors = 0

        for resource in self.resource_ids:
            if not resource.download_url:
                log_lines.append(f"WARNING: No download URL for {resource.name}")
                continue

            log_lines.append(f"\nProcessing {resource.name} (Level {resource.admin_level})...")

            # Download and parse GeoJSON
            client = HdxClient()
            content = client.download_resource(resource.download_url)
            geojson_data = json.loads(content)

            # Get field mappings
            pcode_field = resource.pcode_field
            name_field = resource.name_field
            name_local_field = resource.name_local_field
            parent_pcode_field = resource.parent_pcode_field

            if not pcode_field:
                mappings = client.detect_field_mappings(geojson_data)
                pcode_field = mappings.get("pcode_field")
                name_field = mappings.get("name_field")
                name_local_field = mappings.get("name_local_field")
                parent_pcode_field = mappings.get("parent_pcode_field")

            if not pcode_field:
                log_lines.append(f"ERROR: Cannot detect P-code field for {resource.name}")
                total_errors += 1
                continue

            # Process features
            result = self._process_features(
                geojson_data,
                resource.admin_level,
                pcode_field,
                name_field,
                name_local_field,
                parent_pcode_field,
            )

            total_updated += result["updated"]
            total_created += result["created"]
            total_errors += result["errors"]

            log_lines.append(f"Updated: {result['updated']}, Created: {result['created']}, Errors: {result['errors']}")

            # Update resource metadata
            resource.write(
                {
                    "last_download_date": fields.Datetime.now(),
                    "feature_count": len(geojson_data.get("features", [])),
                }
            )

        # Update source metadata
        if self.source_id:
            self.source_id.write(
                {
                    "last_import_date": fields.Datetime.now(),
                    "areas_updated": total_updated + total_created,
                }
            )

        log_lines.append(f"\n\nTOTAL: Updated: {total_updated}, Created: {total_created}, Errors: {total_errors}")
        self.import_log = "\n".join(log_lines)

    def _import_from_file(self):
        """Import from uploaded file."""
        if not self.file_data:
            raise UserError(_("Please upload a GeoJSON file"))

        # Decode and parse GeoJSON
        content = base64.b64decode(self.file_data)
        geojson_data = json.loads(content)

        if not self.pcode_field:
            raise UserError(_("P-code field is required"))

        log_lines = [f"Processing {self.file_name}..."]

        # Process features
        result = self._process_features(
            geojson_data,
            self.file_admin_level,
            self.pcode_field,
            self.name_field,
            self.name_local_field,
            self.parent_pcode_field,
        )

        log_lines.append(f"Updated: {result['updated']}, Created: {result['created']}, Errors: {result['errors']}")

        self.import_log = "\n".join(log_lines)

    def _process_features(
        self,
        geojson_data,
        admin_level,
        pcode_field,
        name_field=None,
        name_local_field=None,
        parent_pcode_field=None,
    ):
        """
        Process GeoJSON features and update/create areas.

        Args:
            geojson_data: Parsed GeoJSON dictionary
            admin_level: Admin level for areas
            pcode_field: Field name for P-code
            name_field: Field name for name (optional)
            name_local_field: Field name for local name (optional)
            parent_pcode_field: Field name for parent P-code (optional)

        Returns:
            dict: Statistics with keys: updated, created, errors
        """
        stats = {"updated": 0, "created": 0, "errors": 0}

        features = geojson_data.get("features", [])
        Area = self.env["spp.area"]
        now = fields.Datetime.now()

        # Pre-fetch all existing areas by P-code for efficiency
        all_pcodes = [
            f.get("properties", {}).get(pcode_field) for f in features if f.get("properties", {}).get(pcode_field)
        ]
        existing_areas = Area.search([("hdx_pcode", "in", all_pcodes)])
        pcode_to_area = {a.hdx_pcode: a for a in existing_areas}

        # Also check code field for fallback matching
        existing_by_code = Area.search([("code", "in", all_pcodes)])
        for a in existing_by_code:
            if a.code not in pcode_to_area:
                pcode_to_area[a.code] = a

        # Process in batches
        batch_size = 100
        for i in range(0, len(features), batch_size):
            batch = features[i : i + batch_size]
            to_create = []

            for feature in batch:
                try:
                    properties = feature.get("properties", {})
                    geometry = feature.get("geometry")

                    # Get P-code
                    pcode = properties.get(pcode_field)
                    if not pcode:
                        stats["errors"] += 1
                        continue

                    # Find existing area from pre-fetched map
                    area = pcode_to_area.get(pcode)

                    # Prepare values
                    vals = {
                        "hdx_pcode": pcode,
                        "hdx_last_update": now,
                        "level": admin_level,
                    }

                    # Add polygon if geometry exists
                    if geometry:
                        vals["geo_polygon"] = json.dumps(geometry)

                    # Add name if requested and available
                    if self.update_names and name_field and properties.get(name_field):
                        vals["draft_name"] = properties.get(name_field)

                    # Find parent if parent P-code available
                    if parent_pcode_field and properties.get(parent_pcode_field):
                        parent_pcode = properties.get(parent_pcode_field)
                        parent = pcode_to_area.get(parent_pcode) or Area.find_by_pcode(parent_pcode)
                        if parent:
                            vals["parent_id"] = parent.id

                    if area:
                        # Update existing area
                        if self.update_existing:
                            area.write(vals)
                            stats["updated"] += 1
                    else:
                        # Queue for batch creation
                        if self.create_missing:
                            # Need at least a name
                            if "draft_name" not in vals:
                                if name_field and properties.get(name_field):
                                    vals["draft_name"] = properties.get(name_field)
                                else:
                                    vals["draft_name"] = pcode  # Use P-code as fallback

                            to_create.append(vals)

                except Exception as error:
                    _logger.error("Error processing feature: %s", str(error))
                    stats["errors"] += 1
                    continue

            # Batch create new areas
            if to_create:
                try:
                    created = Area.create(to_create)
                    stats["created"] += len(created)
                    # Add newly created areas to the lookup map
                    for area in created:
                        pcode_to_area[area.hdx_pcode] = area
                except Exception as error:
                    _logger.error("Error batch creating areas: %s", str(error))
                    stats["errors"] += len(to_create)

            # Note: No manual commit here - let Odoo handle the transaction
            # atomically. For very large imports, consider using job_worker
            # to process in background with proper transaction management.

        return stats

    def action_back_to_config(self):
        """Go back to configuration."""
        self.state = "config"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
