from odoo import api, fields, models


class SPPCRDetailChangeHOH(models.Model):
    """Detail model for Change Head of Household CR type."""

    _name = "spp.cr.detail.change_hoh"
    _description = "CR Detail: Change Head of Household"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # HEAD OF HOUSEHOLD INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    current_head_id = fields.Many2one(
        "res.partner",
        string="Current Head of Household",
        compute="_compute_current_head",
        store=True,
        readonly=True,
    )
    available_individual_ids = fields.Many2many(
        "res.partner",
        string="Available Individuals",
        compute="_compute_available_individuals",
        help="Active members excluding current head of household",
    )
    new_head_id = fields.Many2one(
        "res.partner",
        string="New Head of Household",
        tracking=True,
        domain="[('is_group', '=', False), ('is_registrant', '=', True)]",
        help="Select the individual who will become the new head of household",
    )
    new_head_membership_id = fields.Many2one(
        "spp.group.membership",
        string="New Head Membership",
        readonly=True,
        help="Membership record for the new head (automatically set)",
    )
    previous_head_new_role_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Previous Head's New Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type'), ('code', '!=', 'head')]",
        tracking=True,
        help="The new role for the previous head (e.g., Spouse, Other Adult)",
    )
    reason = fields.Selection(
        [
            ("deceased", "Head Deceased"),
            ("incapacitated", "Head Incapacitated"),
            ("left_household", "Head Left Household"),
            ("age_change", "Age-based Change"),
            ("voluntary", "Voluntary Transfer"),
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Reason for Change",
        tracking=True,
    )
    effective_date = fields.Date(
        string="Effective Date",
        default=fields.Date.today,
        tracking=True,
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    @api.depends("change_request_id.registrant_id")
    def _compute_current_head(self):
        """Find the current head of household."""
        head_kind = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
        for rec in self:
            current_head = False
            if rec.change_request_id.registrant_id and head_kind:
                memberships = self.env["spp.group.membership"].search(
                    [
                        ("group", "=", rec.change_request_id.registrant_id.id),
                        ("membership_type_ids", "in", [head_kind.id]),
                        ("status", "=", "active"),
                    ],
                    limit=1,
                )
                if memberships:
                    current_head = memberships.individual
            rec.current_head_id = current_head

    @api.depends("change_request_id.registrant_id", "current_head_id")
    def _compute_available_individuals(self):
        """Compute available individuals excluding current head of household."""
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
                # Exclude current head
                if head_kind:
                    available_memberships = all_memberships.filtered(lambda m: head_kind not in m.membership_type_ids)
                else:
                    available_memberships = all_memberships
                # Get the individuals from these memberships
                available_individuals = available_memberships.mapped("individual")
            rec.available_individual_ids = available_individuals

    @api.onchange("new_head_id")
    def _onchange_new_head_id(self):
        """Set the membership_id when individual is selected."""
        self.new_head_membership_id = False
        if self.new_head_id and self.change_request_id.registrant_id:
            # Find the membership for this individual in this group
            membership = self.env["spp.group.membership"].search(
                [
                    ("group", "=", self.change_request_id.registrant_id.id),
                    ("individual", "=", self.new_head_id.id),
                    ("status", "=", "active"),
                ],
                limit=1,
            )
            if membership:
                self.new_head_membership_id = membership
