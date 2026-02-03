from odoo import fields, models


class SPPCRDetailExitRegistrant(models.Model):
    """Detail model for Exit/Deactivate Registrant CR type."""

    _name = "spp.cr.detail.exit_registrant"
    _description = "CR Detail: Exit Registrant"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # EXIT INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    exit_reason = fields.Selection(
        [
            ("deceased", "Deceased"),
            ("emigrated", "Emigrated"),
            ("duplicate", "Duplicate Record"),
            ("ineligible", "No Longer Eligible"),
            ("voluntary", "Voluntary Exit"),
            ("fraud", "Fraudulent Registration"),
            ("other", "Other"),
        ],
        string="Exit Reason",
        tracking=True,
    )
    exit_date = fields.Date(
        string="Exit Date",
        default=fields.Date.today,
        tracking=True,
    )
    death_date = fields.Date(
        string="Date of Death",
        tracking=True,
        help="Required if exit reason is Deceased",
    )
    destination_country_id = fields.Many2one(
        "res.country",
        string="Destination Country",
        tracking=True,
        help="Required if exit reason is Emigrated",
    )
    is_end_active_memberships = fields.Boolean(
        string="End Active Memberships",
        default=True,
        tracking=True,
        help="Automatically end all active group memberships",
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED/RELATED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    registrant_name = fields.Char(
        string="Registrant Name",
        related="change_request_id.registrant_id.name",
        readonly=True,
    )
    is_group = fields.Boolean(
        string="Is Group",
        related="change_request_id.registrant_id.is_group",
        readonly=True,
    )
    active_membership_count = fields.Integer(
        string="Active Memberships",
        compute="_compute_active_membership_count",
    )

    def _compute_active_membership_count(self):
        """Count active memberships for this registrant."""
        for rec in self:
            count = 0
            registrant = rec.change_request_id.registrant_id
            if registrant and not registrant.is_group:
                count = self.env["spp.group.membership"].search_count(
                    [
                        ("individual", "=", registrant.id),
                        ("status", "=", "active"),
                    ]
                )
            rec.active_membership_count = count
