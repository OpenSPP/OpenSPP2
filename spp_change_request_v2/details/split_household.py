from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailSplitHousehold(models.Model):
    """Detail model for Split Household CR type."""

    _name = "spp.cr.detail.split_household"
    _description = "CR Detail: Split Household"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # SOURCE GROUP INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    source_group_id = fields.Many2one(
        "res.partner",
        string="Source Household",
        related="change_request_id.registrant_id",
        store=True,
        readonly=True,
    )
    source_group_name = fields.Char(
        string="Source Group Name",
        related="source_group_id.name",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # MEMBERS TO SPLIT
    # ══════════════════════════════════════════════════════════════════════════

    available_member_ids = fields.Many2many(
        "res.partner",
        string="Available Members",
        compute="_compute_available_member_ids",
        help="Active members of the source household (excluding head)",
    )

    registrant_member_to_split_ids = fields.Many2many(
        "res.partner",
        "spp_cr_split_registrants_rel",
        "detail_id",
        "partner_id",
        string="Members to Move",
        tracking=True,
        help="Select individuals to move to the new household",
    )

    members_to_split_ids = fields.Many2many(
        "spp.group.membership",
        "spp_cr_split_members_rel",
        "detail_id",
        "membership_id",
        string="Membership Records",
        compute="_compute_members_to_split_ids",
        store=True,
        readonly=True,
        help="Membership records for selected individuals (auto-populated)",
    )

    new_head_individual_id = fields.Many2one(
        "res.partner",
        string="New Household Head",
        tracking=True,
        help="Select who will be the head of the new household",
    )

    new_head_membership_id = fields.Many2one(
        "spp.group.membership",
        string="Head Membership Record",
        compute="_compute_new_head_membership_id",
        store=True,
        readonly=True,
        help="Membership record for the selected new head (auto-populated)",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # NEW GROUP INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    new_group_name = fields.Char(
        string="New Household Name",
        tracking=True,
    )
    new_group_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="New Group Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-type')]",
        tracking=True,
        help="Leave empty to use same type as source",
    )

    # New group address
    copy_address = fields.Boolean(
        string="Copy Address from Source",
        default=True,
        tracking=True,
    )
    address_line1 = fields.Char(string="Address Line 1", tracking=True)
    address_line2 = fields.Char(string="Address Line 2", tracking=True)
    city = fields.Char(string="City", tracking=True)
    state_id = fields.Many2one("res.country.state", string="State/Province", tracking=True)
    postal_code = fields.Char(string="Postal Code", tracking=True)
    country_id = fields.Many2one("res.country", string="Country", tracking=True)
    phone = fields.Char(string="Phone", tracking=True)
    email = fields.Char(string="Email", tracking=True)

    # Split metadata
    split_reason = fields.Selection(
        [
            ("marriage", "Marriage"),
            ("separation", "Separation/Divorce"),
            ("independence", "Member Independence"),
            ("relocation", "Relocation"),
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Split Reason",
        tracking=True,
    )
    effective_date = fields.Date(
        string="Effective Date",
        default=fields.Date.today,
        tracking=True,
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # Reference to created group (set after apply)
    created_group_id = fields.Many2one(
        "res.partner",
        string="Created Household",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ══════════════════════════════════════════════════════════════════════════

    members_to_split_count = fields.Integer(
        string="Members to Move",
        compute="_compute_members_count",
    )
    remaining_members_count = fields.Integer(
        string="Remaining Members",
        compute="_compute_members_count",
    )

    @api.depends("source_group_id")
    def _compute_available_member_ids(self):
        """Compute available members from source household (excluding head)."""
        for rec in self:
            if not rec.source_group_id:
                rec.available_member_ids = False
                continue

            # Get head membership type
            head_type = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")

            # Get all active memberships excluding head
            memberships = self.env["spp.group.membership"].search(
                [
                    ("group", "=", rec.source_group_id.id),
                    ("status", "=", "active"),
                ]
            )

            # Filter out head member
            non_head_memberships = memberships.filtered(lambda m: head_type not in m.membership_type_ids)

            rec.available_member_ids = non_head_memberships.mapped("individual")

    @api.depends("registrant_member_to_split_ids", "source_group_id")
    def _compute_members_to_split_ids(self):
        """Convert selected individuals to their membership records."""
        for rec in self:
            if not rec.source_group_id or not rec.registrant_member_to_split_ids:
                rec.members_to_split_ids = False
                continue

            # Find membership records for selected individuals
            memberships = self.env["spp.group.membership"].search(
                [
                    ("group", "=", rec.source_group_id.id),
                    ("individual", "in", rec.registrant_member_to_split_ids.ids),
                    ("status", "=", "active"),
                ]
            )
            rec.members_to_split_ids = memberships

    @api.depends("new_head_individual_id", "source_group_id")
    def _compute_new_head_membership_id(self):
        """Convert selected new head individual to their membership record."""
        for rec in self:
            if not rec.source_group_id or not rec.new_head_individual_id:
                rec.new_head_membership_id = False
                continue

            # Find membership record for the new head
            membership = self.env["spp.group.membership"].search(
                [
                    ("group", "=", rec.source_group_id.id),
                    ("individual", "=", rec.new_head_individual_id.id),
                    ("status", "=", "active"),
                ],
                limit=1,
            )
            rec.new_head_membership_id = membership

    @api.depends("members_to_split_ids", "source_group_id")
    def _compute_members_count(self):
        for rec in self:
            rec.members_to_split_count = len(rec.members_to_split_ids)
            total = 0
            if rec.source_group_id:
                total = self.env["spp.group.membership"].search_count(
                    [
                        ("group", "=", rec.source_group_id.id),
                        ("status", "=", "active"),
                    ]
                )
            rec.remaining_members_count = total - rec.members_to_split_count

    @api.constrains("registrant_member_to_split_ids", "new_head_individual_id")
    def _check_new_head_in_split(self):
        """Ensure new head is in the members being split."""
        for rec in self:
            if rec.new_head_individual_id and rec.registrant_member_to_split_ids:
                if rec.new_head_individual_id not in rec.registrant_member_to_split_ids:
                    raise ValidationError("The new household head must be one of the members being moved.")

    @api.constrains("members_to_split_ids", "source_group_id")
    def _check_minimum_remaining(self):
        """Ensure at least one member remains in source group."""
        for rec in self:
            if rec.source_group_id and rec.members_to_split_ids:
                total = self.env["spp.group.membership"].search_count(
                    [
                        ("group", "=", rec.source_group_id.id),
                        ("status", "=", "active"),
                    ]
                )
                if len(rec.members_to_split_ids) >= total:
                    raise ValidationError(
                        "Cannot move all members. At least one member must remain " "in the source household."
                    )

    @api.onchange("copy_address")
    def _onchange_copy_address(self):
        """Copy address from source group when toggled."""
        if self.copy_address and self.source_group_id:
            self.address_line1 = self.source_group_id.street
            self.address_line2 = self.source_group_id.street2
            self.city = self.source_group_id.city
            self.state_id = self.source_group_id.state_id
            self.postal_code = self.source_group_id.zip
            self.country_id = self.source_group_id.country_id
            self.phone = self.source_group_id.phone
            self.email = self.source_group_id.email
