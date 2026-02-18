# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import base64
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)

try:
    import libhxl
    from libhxl.io import make_stream
except ImportError:
    _logger.warning("libhxl library not found")
    libhxl = None


class HxlAreaImportWizard(models.TransientModel):
    """Wizard for importing HXL data with area aggregation.

    Multi-step wizard:
    1. Select profile and upload file
    2. Preview data and area matching
    3. Confirm and import
    """

    _name = "spp.hxl.area.import.wizard"
    _description = "HXL Area Import Wizard"

    # ─── Step 1: Profile and File ───────────────────────────────────
    profile_id = fields.Many2one(
        "spp.hxl.import.profile",
        required=True,
        string="Import Profile",
        help="Select the import profile defining aggregation rules",
    )

    file_data = fields.Binary(
        string="HXL File",
        required=True,
        help="Upload HXL-tagged CSV or Excel file",
    )
    file_name = fields.Char(string="File Name")

    # ─── Step 2: Context ───────────────────────────────────
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident",
        help="Optionally link to an incident/disaster event",
    )

    period_key = fields.Char(
        string="Period",
        default=lambda self: fields.Date.today().strftime("%Y-%m"),
        help="Period identifier (e.g., '2024-03' for March 2024)",
    )

    batch_name = fields.Char(
        string="Batch Name",
        help="Name for this import batch (auto-generated if not provided)",
    )

    # ─── Preview Data ───────────────────────────────────
    preview_html = fields.Html(
        string="Data Preview",
        readonly=True,
        help="Preview of first few rows from the file",
    )

    detected_hxl_row = fields.Integer(
        string="HXL Row",
        readonly=True,
        help="Row number where HXL hashtags were detected",
    )

    total_rows = fields.Integer(
        string="Total Rows",
        readonly=True,
        help="Total data rows in the file",
    )

    # ─── Area Matching Preview ───────────────────────────────────
    preview_matched = fields.Integer(
        string="Preview Rows Matched",
        readonly=True,
        help="Number of rows that could be matched to areas (sample)",
    )

    preview_unmatched = fields.Integer(
        string="Preview Unmatched",
        readonly=True,
        help="Number of rows that couldn't be matched (sample)",
    )

    unmatched_areas = fields.Text(
        string="Unmatched Area Values",
        readonly=True,
        help="Sample of area values that couldn't be matched",
    )

    @api.onchange("file_data", "profile_id")
    def _onchange_file(self):
        """Parse file and generate preview when file is uploaded."""
        if self.file_data and self.profile_id:
            self._parse_and_preview()

    def _parse_and_preview(self):
        """Parse the uploaded file and generate preview."""
        if not self.file_data:
            return

        if libhxl is None:
            raise UserError(_("libhxl library not installed"))

        try:
            # Decode file
            file_content = base64.b64decode(self.file_data)
            file_stream = io.BytesIO(file_content)

            # Parse with libhxl
            hxl_stream = make_stream(file_stream)

            # Read first N rows for preview
            preview_rows = []
            sample_size = 10

            for idx, hxl_row in enumerate(hxl_stream):
                if idx >= sample_size:
                    break

                row_dict = {}
                for col in hxl_stream.columns:
                    tag = col.display_tag
                    value = hxl_row.get(col.display_tag)
                    if tag:
                        row_dict[tag] = value

                preview_rows.append(row_dict)

            # Generate HTML preview
            if preview_rows:
                html = self._generate_preview_html(preview_rows)
                self.preview_html = html
                self.total_rows = idx + 1  # Approximate

            # Preview area matching
            if self.profile_id:
                self._preview_area_matching(preview_rows)

        except Exception as e:
            _logger.error("Failed to parse file: %s", e, exc_info=True)
            self.preview_html = f"<p style='color: red;'>Error parsing file: {html_escape(str(e))}</p>"

    def _generate_preview_html(self, rows):
        """Generate HTML table preview of rows.

        Args:
            rows: List of row dicts

        Returns:
            HTML string
        """
        if not rows:
            return "<p>No data to preview</p>"

        # Extract columns from first row
        columns = list(rows[0].keys())

        html = ["<table class='table table-sm table-bordered'>"]

        # Header
        html.append("<thead><tr>")
        for col in columns:
            html.append(f"<th>{html_escape(col)}</th>")
        html.append("</tr></thead>")

        # Rows
        html.append("<tbody>")
        for row in rows:
            html.append("<tr>")
            for col in columns:
                value = row.get(col, "")
                html.append(f"<td>{html_escape(str(value))}</td>")
            html.append("</tr>")
        html.append("</tbody>")

        html.append("</table>")

        return "".join(html)

    def _preview_area_matching(self, rows):
        """Preview how well areas will match.

        Args:
            rows: Sample rows to test matching
        """
        if not rows:
            return

        from ..services.area_matcher import AreaMatcher

        # Initialize matcher
        matcher = AreaMatcher(
            self.env,
            strategy=self.profile_id.area_matching_strategy,
            level=self.profile_id.area_level,
        )

        area_col_tag = self.profile_id.area_column_tag
        matched = 0
        unmatched = 0
        unmatched_values = set()

        for row in rows:
            area_value = row.get(area_col_tag, "")

            if not area_value:
                unmatched += 1
                continue

            area = matcher.match(area_value)

            if area:
                matched += 1
            else:
                unmatched += 1
                unmatched_values.add(area_value)

        self.preview_matched = matched
        self.preview_unmatched = unmatched

        if unmatched_values:
            self.unmatched_areas = "\n".join(sorted(unmatched_values)[:20])
            if len(unmatched_values) > 20:
                self.unmatched_areas += f"\n... and {len(unmatched_values) - 20} more"

    def action_import(self):
        """Create batch and process import."""
        self.ensure_one()

        if not self.file_data:
            raise UserError(_("Please upload a file"))

        if not self.profile_id:
            raise UserError(_("Please select an import profile"))

        # Validate profile
        self.profile_id.validate_configuration()

        # Generate batch name if not provided
        batch_name = self.batch_name or f"Import {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}"

        # Create batch
        batch = self.env["spp.hxl.import.batch"].create(
            {
                "name": batch_name,
                "profile_id": self.profile_id.id,
                "file_data": self.file_data,
                "file_name": self.file_name,
                "incident_id": self.incident_id.id if self.incident_id else False,
                "period_key": self.period_key,
            }
        )

        # Detect columns
        batch.action_detect_columns()

        # Process
        batch.action_process()

        # Return action to view batch
        return {
            "type": "ir.actions.act_window",
            "name": _("Import Batch"),
            "res_model": "spp.hxl.import.batch",
            "res_id": batch.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_cancel(self):
        """Cancel wizard."""
        return {"type": "ir.actions.act_window_close"}
