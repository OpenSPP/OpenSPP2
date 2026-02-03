from odoo import api, fields, models


class SPPCRDetailRemoveMember(models.Model):
    """Detail model for Remove Member CR type."""

    _name = "spp.cr.detail.remove_member"
    _description = "CR Detail: Remove Group Member"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # MEMBER INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    available_individual_ids = fields.Many2many(
        "res.partner",
        string="Available Individuals",
        compute="_compute_available_individuals",
        help="Active members excluding head of household",
    )
    individual_id = fields.Many2one(
        "res.partner",
        string="Member to Remove",
        tracking=True,
        domain="[('is_group', '=', False), ('is_registrant', '=', True)]",
        help="Select the individual to remove from the group",
    )
    membership_id = fields.Many2one(
        "spp.group.membership",
        string="Member Membership",
        readonly=True,
        help="Membership record for the individual (automatically set)",
    )
    end_date = fields.Date(
        string="End Date",
        default=fields.Date.today,
        tracking=True,
    )
    end_reason = fields.Selection(
        [
            ("left_household", "Left Household"),
            ("deceased", "Deceased"),
            ("married_out", "Married Out"),
            ("migrated", "Migrated"),
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Reason for Removal",
        tracking=True,
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    member_name = fields.Char(
        string="Member Name",
        related="individual_id.name",
        readonly=True,
    )

    @api.depends("change_request_id.registrant_id")
    def _compute_available_individuals(self):
        """Compute available individuals excluding head of household."""
        head_kind = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
        for rec in self:
            available_individuals = self.env["res.partner"]
            if rec.change_request_id.registrant_id:
                # Get all active memberships for this group
                all_memberships = self.env["spp.group.membership"].search(
                    [
                        ("group", "=", rec.change_request_id.registrant_id.id),
                        ("status", "=", "active"),
                    ]
                )
                # Exclude head of household
                if head_kind:
                    available_memberships = all_memberships.filtered(lambda m: head_kind not in m.membership_type_ids)
                else:
                    available_memberships = all_memberships
                # Get the individuals from these memberships
                available_individuals = available_memberships.mapped("individual")
            rec.available_individual_ids = available_individuals

    @api.onchange("individual_id")
    def _onchange_individual_id(self):
        """Set the membership_id when individual is selected."""
        self.membership_id = False
        if self.individual_id and self.change_request_id.registrant_id:
            # Find the membership for this individual in this group
            membership = self.env["spp.group.membership"].search(
                [
                    ("group", "=", self.change_request_id.registrant_id.id),
                    ("individual", "=", self.individual_id.id),
                    ("status", "=", "active"),
                ],
                limit=1,
            )
            if membership:
                self.membership_id = membership
