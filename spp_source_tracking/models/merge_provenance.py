# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MergeProvenance(models.Model):
    """Tracks merge history for auditing.

    When registrants are merged, this model preserves:
    - The relationship between survivor and merged record
    - Original source tracking data from the merged record
    - A snapshot of key data at the time of merge

    This enables auditors to:
    - Trace the history of merged records
    - Understand data provenance even after merges
    - Reconstruct the state of merged records for compliance
    """

    _name = "spp.merge.provenance"
    _description = "Merge Provenance"
    _order = "merge_date desc"
    _rec_name = "display_name"

    survivor_id = fields.Many2one(
        "res.partner",
        string="Surviving Record",
        required=True,
        index=True,
        ondelete="cascade",
        help="The record that absorbed the merged record",
    )
    merged_id = fields.Integer(
        string="Merged Record ID",
        required=True,
        index=True,
        help="Original database ID of merged record (preserved even if record is deleted)",
    )
    merge_date = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        index=True,
    )
    merged_by_id = fields.Many2one(
        "res.users",
        string="Merged By",
        default=lambda self: self.env.user,
        required=True,
    )
    merge_reason = fields.Text(
        help="Reason for the merge (e.g., duplicate detected by MPI, user request)",
    )

    # === Preserved provenance from merged record ===
    merged_source_system = fields.Char(
        string="Merged Record Source",
        help="Original source system of the merged record",
    )
    merged_source_reference = fields.Char(
        string="Merged Record Reference",
        help="Original reference ID in the source system",
    )
    merged_collection_method = fields.Selection(
        selection="_selection_collection_method",
    )
    merged_collection_date = fields.Datetime(
        string="Merged Record Collection Date",
    )

    # === Snapshot of key data at time of merge ===
    merged_data_snapshot = fields.Json(
        string="Data Snapshot",
        help="Key fields from merged record preserved for audit",
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    @api.model
    def _selection_collection_method(self):
        """Get collection methods from the mixin."""
        return self.env["spp.mixin.source.tracking"]._selection_collection_method()

    @api.depends("survivor_id", "merged_id", "merge_date")
    def _compute_display_name(self):
        for rec in self:
            survivor_name = rec.survivor_id.name or str(rec.survivor_id.id)
            merge_date_str = rec.merge_date.date() if rec.merge_date else "N/A"
            rec.display_name = f"Merge #{rec.merged_id} -> {survivor_name} ({merge_date_str})"
