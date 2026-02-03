# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Wizard to preview changes before applying a change request."""

import json

from odoo import api, fields, models


class CRPreviewChangesWizard(models.TransientModel):
    """Wizard to display preview of changes from a CR."""

    _name = "spp.cr.preview.wizard"
    _description = "Preview CR Changes"

    change_request_id = fields.Many2one(
        "spp.change.request",
        string="Change Request",
        required=True,
        readonly=True,
    )
    registrant_name = fields.Char(
        related="change_request_id.registrant_id.name",
        string="Registrant",
    )
    request_type = fields.Char(
        related="change_request_id.request_type_id.name",
        string="Request Type",
    )
    preview_html = fields.Html(
        string="Preview",
        compute="_compute_preview_html",
        sanitize=False,
    )
    preview_json = fields.Text(
        string="Preview Data (JSON)",
        compute="_compute_preview_html",
    )

    @api.depends("change_request_id")
    def _compute_preview_html(self):
        for rec in self:
            if not rec.change_request_id:
                rec.preview_html = "<p>No change request selected.</p>"
                rec.preview_json = "{}"
                continue

            cr = rec.change_request_id

            # If CR is applied and has snapshots, use them
            if cr.is_applied and cr.preview_json_snapshot:
                rec.preview_json = cr.preview_json_snapshot
                # Parse the snapshot to build HTML
                changes = json.loads(cr.preview_json_snapshot)
            else:
                # Generate fresh preview
                strategy = cr.request_type_id.get_apply_strategy()
                changes = strategy.preview(cr) or {}
                rec.preview_json = json.dumps(changes, indent=2, default=str)

            # Build HTML preview
            html_parts = ['<div class="o_preview_changes">']

            action = changes.pop("_action", "update")
            html_parts.append(f'<p class="mb-3"><strong>Action:</strong> {action}</p>')

            if changes:
                html_parts.append('<table class="table table-sm table-striped">')
                html_parts.append("<thead><tr><th>Field</th><th>Value</th></tr></thead>")
                html_parts.append("<tbody>")

                for key, value in changes.items():
                    # Format the key
                    display_key = key.replace("_", " ").title()
                    # Format the value
                    if isinstance(value, list):
                        display_value = "<br/>".join(str(v) for v in value)
                    elif value is None:
                        display_value = '<span class="text-muted">Not set</span>'
                    elif isinstance(value, bool):
                        display_value = (
                            '<span class="badge text-bg-success">Yes</span>'
                            if value
                            else '<span class="badge text-bg-secondary">No</span>'
                        )
                    else:
                        display_value = str(value)

                    html_parts.append(f"<tr><td><strong>{display_key}</strong></td>" f"<td>{display_value}</td></tr>")

                html_parts.append("</tbody></table>")
            else:
                html_parts.append('<p class="text-muted">No preview data available.</p>')

            html_parts.append("</div>")
            rec.preview_html = "".join(html_parts)
