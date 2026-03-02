from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailMergeRegistrants(models.Model):
    """Detail model for Merge Registrants CR type."""

    _name = "spp.cr.detail.merge_registrants"
    _description = "CR Detail: Merge Registrants"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # MERGE INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    primary_registrant_id = fields.Many2one(
        "res.partner",
        string="Primary Registrant (Keep)",
        related="change_request_id.registrant_id",
        store=True,
        readonly=True,
        help="This registrant will be kept as the master record",
    )

    available_duplicate_ids = fields.Many2many(
        "res.partner",
        string="Available Duplicates",
        compute="_compute_available_duplicate_ids",
        help="Registrants of the same type (individual/group) available for merging",
    )

    duplicate_registrant_ids = fields.Many2many(
        "res.partner",
        "spp_cr_merge_duplicate_rel",
        "detail_id",
        "partner_id",
        string="Duplicate Registrants (Merge)",
        tracking=True,
        help="These registrants will be merged into the primary",
    )
    merge_strategy = fields.Selection(
        [
            ("keep_primary", "Keep Primary Values"),
            ("keep_newest", "Keep Newest Values"),
            ("manual", "Manual Selection"),
        ],
        string="Merge Strategy",
        default="keep_primary",
        tracking=True,
        help="How to handle conflicting field values",
    )
    is_merge_memberships = fields.Boolean(
        string="Merge Memberships",
        default=True,
        tracking=True,
        help="Transfer group memberships from duplicates to primary",
    )
    is_merge_ids = fields.Boolean(
        string="Merge IDs",
        default=True,
        tracking=True,
        help="Transfer ID documents from duplicates to primary",
    )
    is_deactivate_duplicates = fields.Boolean(
        string="Deactivate Duplicates",
        default=True,
        tracking=True,
        help="Mark duplicate registrants as inactive after merge",
    )
    reason = fields.Selection(
        [
            ("duplicate_entry", "Duplicate Data Entry"),
            ("system_migration", "System Migration"),
            ("household_merge", "Household Merge"),
            ("data_quality", "Data Quality Cleanup"),
            ("other", "Other"),
        ],
        string="Merge Reason",
        tracking=True,
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    primary_name = fields.Char(
        string="Primary Name",
        related="primary_registrant_id.name",
        readonly=True,
    )
    duplicate_count = fields.Integer(
        string="Duplicates to Merge",
        compute="_compute_duplicate_count",
    )
    is_group_merge = fields.Boolean(
        string="Is Group Merge",
        related="primary_registrant_id.is_group",
        readonly=True,
    )

    @api.depends("primary_registrant_id", "primary_registrant_id.is_group")
    def _compute_available_duplicate_ids(self):
        """Compute available duplicates of the same type as primary."""
        for rec in self:
            if not rec.primary_registrant_id:
                rec.available_duplicate_ids = False
                continue

            # Get all registrants of the same type, excluding the primary
            duplicates = self.env["res.partner"].search(
                [
                    ("is_registrant", "=", True),
                    ("is_group", "=", rec.primary_registrant_id.is_group),
                    ("id", "!=", rec.primary_registrant_id.id),
                    ("disabled", "=", False),  # Only active registrants
                ]
            )
            rec.available_duplicate_ids = duplicates

    @api.depends("duplicate_registrant_ids")
    def _compute_duplicate_count(self):
        for rec in self:
            rec.duplicate_count = len(rec.duplicate_registrant_ids)

    @api.constrains("duplicate_registrant_ids", "primary_registrant_id")
    def _check_registrant_types(self):
        """Ensure all registrants are of the same type (individual or group)."""
        for rec in self:
            if rec.primary_registrant_id and rec.duplicate_registrant_ids:
                primary_is_group = rec.primary_registrant_id.is_group
                for dup in rec.duplicate_registrant_ids:
                    if dup.is_group != primary_is_group:
                        raise ValidationError(
                            "Cannot merge individuals with groups. " "All registrants must be of the same type."
                        )
                    if dup.id == rec.primary_registrant_id.id:
                        raise ValidationError("Primary registrant cannot be in the duplicates list.")
