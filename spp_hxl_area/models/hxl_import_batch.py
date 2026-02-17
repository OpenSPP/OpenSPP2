# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import base64
import io
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    import libhxl
    from libhxl.io import make_stream
except ImportError:
    _logger.warning("libhxl library not found. HXL import functionality will be limited.")
    libhxl = None


class HxlImportBatch(models.Model):
    """Track individual HXL import batches.

    Each batch represents one execution of an import profile against
    a specific HXL file, producing area-level indicators.
    """

    _name = "spp.hxl.import.batch"
    _description = "HXL Import Batch"
    _order = "create_date desc"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    profile_id = fields.Many2one(
        "spp.hxl.import.profile",
        required=True,
        tracking=True,
        ondelete="restrict",
    )

    # ─── Source ───────────────────────────────────────────
    file_data = fields.Binary(
        string="HXL File",
        attachment=True,
        help="HXL-tagged CSV/Excel file to import",
    )
    file_name = fields.Char()
    source_url = fields.Char(
        string="Source URL",
        help="URL where the data was downloaded from (for reference)",
    )

    # ─── Context ───────────────────────────────────────────
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        tracking=True,
        help="Link to incident/disaster event",
    )
    period_key = fields.Char(
        string="Period",
        tracking=True,
        help="Period key for historical tracking (e.g., '2024-03')",
    )

    # ─── Status ───────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("mapped", "Columns Mapped"),
            ("processing", "Processing"),
            ("done", "Completed"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    # ─── Statistics ───────────────────────────────────────────
    total_rows = fields.Integer(string="Total Rows", readonly=True)
    matched_rows = fields.Integer(string="Rows Matched to Areas", readonly=True)
    unmatched_rows = fields.Integer(string="Unmatched Rows", readonly=True)
    areas_updated = fields.Integer(string="Areas with Indicators", readonly=True)
    indicators_created = fields.Integer(string="Indicators Created", readonly=True)

    # ─── Column Mapping ───────────────────────────────────────────
    mapping_ids = fields.One2many(
        "spp.hxl.import.mapping",
        "batch_id",
        string="Column Mappings",
        help="Auto-detected HXL column mappings",
    )

    # ─── Results ───────────────────────────────────────────
    indicator_ids = fields.One2many(
        "spp.hxl.area.indicator",
        "batch_id",
        string="Generated Indicators",
    )

    error_log = fields.Text(string="Error Log", readonly=True)

    # ─── HXL Data Cache ───────────────────────────────────────────
    hxl_row_number = fields.Integer(
        string="HXL Row",
        help="Row number where HXL hashtags were detected",
    )
    hxl_columns_json = fields.Text(
        string="HXL Columns",
        help="JSON array of detected HXL columns",
    )

    @api.model
    def create(self, vals):
        """Auto-detect columns on create if file provided."""
        batch = super().create(vals)
        if batch.file_data:
            try:
                batch.action_detect_columns()
            except Exception as e:
                _logger.warning("Failed to auto-detect columns: %s", e)
        return batch

    def action_detect_columns(self):
        """Parse file and auto-detect HXL columns."""
        self.ensure_one()

        if not self.file_data:
            raise UserError(_("No file uploaded"))

        if libhxl is None:
            raise UserError(_("libhxl library not installed. Cannot parse HXL files."))

        try:
            # Decode file
            file_content = base64.b64decode(self.file_data)
            file_stream = io.BytesIO(file_content)

            # Parse with libhxl
            hxl_stream = make_stream(file_stream)

            # Find HXL row and extract tags
            hxl_columns = []
            hxl_row_num = 0

            for idx, col in enumerate(hxl_stream.columns):
                hxl_columns.append(
                    {
                        "index": idx,
                        "header": col.header or "",
                        "tag": col.display_tag or "",
                    }
                )

            if not hxl_columns:
                raise ValidationError(_("No HXL hashtags detected in file"))

            # Store detected columns
            self.write(
                {
                    "hxl_columns_json": json.dumps(hxl_columns),
                    "hxl_row_number": hxl_row_num,
                    "state": "mapped",
                }
            )

            # Create mapping records
            self._create_mappings(hxl_columns)

            self.message_post(
                body=_("Successfully detected %d HXL columns") % len(hxl_columns),
            )

        except Exception as e:
            error_msg = _("Failed to detect columns: %s") % str(e)
            _logger.error(error_msg, exc_info=True)
            self.write(
                {
                    "state": "failed",
                    "error_log": error_msg,
                }
            )
            raise UserError(error_msg) from e

    def _create_mappings(self, hxl_columns):
        """Create mapping records for detected columns."""
        self.ensure_one()

        # Clear existing mappings
        self.mapping_ids.unlink()

        Mapping = self.env["spp.hxl.import.mapping"]

        for col in hxl_columns:
            tag = col.get("tag", "")

            # Determine mapping type
            mapping_type = "skip"
            confidence = 0.0

            # Check if this is the area column
            if self.profile_id.area_column_tag and tag == self.profile_id.area_column_tag:
                mapping_type = "area"
                confidence = 1.0

            # Check if it matches any aggregation rule
            for rule in self.profile_id.aggregation_ids:
                if rule.source_column_tag and tag == rule.source_column_tag:
                    mapping_type = "aggregate"
                    confidence = 0.9
                    break

            Mapping.create(
                {
                    "batch_id": self.id,
                    "sequence": col.get("index", 0),
                    "source_column": col.get("header", ""),
                    "detected_hxl_tag": tag,
                    "mapping_type": mapping_type,
                    "confidence": confidence,
                }
            )

    def action_process(self):
        """Run the import and aggregation."""
        self.ensure_one()

        if not self.file_data:
            raise UserError(_("No file uploaded"))

        if self.state != "mapped":
            raise UserError(_("Please detect columns first"))

        # Validate profile
        self.profile_id.validate_configuration()

        # Use job queue for processing
        self.with_delay(priority=5).process_import()

        self.write({"state": "processing"})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import Started"),
                "message": _("Import is running in background. You will be notified when complete."),
                "type": "info",
                "sticky": False,
            },
        }

    def process_import(self):
        """Process the import (called by job queue)."""
        self.ensure_one()

        if libhxl is None:
            raise UserError(_("libhxl library not installed"))

        try:
            from ..services.aggregation_engine import AggregationEngine
            from ..services.area_matcher import AreaMatcher

            _logger.info("Starting HXL import batch: %s", self.id)

            # Decode file
            file_content = base64.b64decode(self.file_data)
            file_stream = io.BytesIO(file_content)

            # Parse with libhxl
            hxl_stream = make_stream(file_stream)

            # Build column mapping
            hxl_columns = json.loads(self.hxl_columns_json) if self.hxl_columns_json else []
            column_map = {col["tag"]: col["header"] for col in hxl_columns if col.get("tag")}

            # Read rows into memory
            rows = []
            for hxl_row in hxl_stream:
                row_dict = {}
                for col in hxl_stream.columns:
                    tag = col.display_tag
                    value = hxl_row.get(col.display_tag)
                    if tag:
                        row_dict[tag] = value
                rows.append(row_dict)

            total_rows = len(rows)
            _logger.info("Parsed %d data rows", total_rows)

            # Initialize services
            matcher = AreaMatcher(
                self.env,
                strategy=self.profile_id.area_matching_strategy,
                level=self.profile_id.area_level,
            )

            engine = AggregationEngine(self.env, self.profile_id, matcher)

            # Aggregate
            indicators, unmatched = engine.aggregate(rows, column_map)

            _logger.info(
                "Aggregation complete: %d indicators, %d unmatched rows",
                len(indicators),
                len(unmatched),
            )

            # Store indicators
            Indicator = self.env["spp.hxl.area.indicator"]

            # Clear existing indicators for this batch
            self.indicator_ids.unlink()

            indicator_records = []
            for ind_data in indicators:
                ind_data.update(
                    {
                        "batch_id": self.id,
                        "period_key": self.period_key,
                        "incident_id": self.incident_id.id if self.incident_id else False,
                    }
                )
                indicator_records.append(ind_data)

            created_indicators = Indicator.create(indicator_records)

            # Sync to data values
            created_indicators.sync_to_data_value()

            # Count unique areas
            areas_updated = len(set(ind.area_id.id for ind in created_indicators))

            # Update statistics
            self.write(
                {
                    "state": "done",
                    "total_rows": total_rows,
                    "matched_rows": total_rows - len(unmatched),
                    "unmatched_rows": len(unmatched),
                    "areas_updated": areas_updated,
                    "indicators_created": len(created_indicators),
                    "error_log": "",
                }
            )

            self.message_post(
                body=_("Import completed successfully: %d indicators created for %d areas")
                % (len(created_indicators), areas_updated),
            )

            _logger.info("HXL import batch completed: %s", self.id)

        except Exception as e:
            error_msg = _("Import failed: %s") % str(e)
            _logger.error(error_msg, exc_info=True)

            self.write(
                {
                    "state": "failed",
                    "error_log": error_msg,
                }
            )

            self.message_post(
                body=error_msg,
                message_type="notification",
            )

            raise

    def action_view_indicators(self):
        """View generated indicators."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Indicators"),
            "res_model": "spp.hxl.area.indicator",
            "view_mode": "list,form",
            "domain": [("batch_id", "=", self.id)],
            "context": {"default_batch_id": self.id},
        }

    def action_reset(self):
        """Reset to draft and clear results."""
        self.ensure_one()
        self.indicator_ids.unlink()
        self.mapping_ids.unlink()
        self.write(
            {
                "state": "draft",
                "total_rows": 0,
                "matched_rows": 0,
                "unmatched_rows": 0,
                "areas_updated": 0,
                "indicators_created": 0,
                "error_log": "",
                "hxl_columns_json": "",
            }
        )
