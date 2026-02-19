from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailTransferMember(models.Model):
    """Detail model for Transfer Member CR type."""

    _name = "spp.cr.detail.transfer_member"
    _description = "CR Detail: Transfer Member"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # TRANSFER INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    source_group_id = fields.Many2one(
        "res.partner",
        string="Source Group",
        related="change_request_id.registrant_id",
        store=True,
        readonly=True,
    )
    available_individual_ids = fields.Many2many(
        "res.partner",
        string="Available Individuals",
        compute="_compute_available_individuals",
        help="Active members excluding head of household",
    )
    individual_id = fields.Many2one(
        "res.partner",
        string="Member to Transfer",
        tracking=True,
        domain="[('is_group', '=', False), ('is_registrant', '=', True)]",
        help="Select the individual to transfer to another group",
    )
    membership_id = fields.Many2one(
        "spp.group.membership",
        string="Member Membership",
        readonly=True,
        help="Membership record for the individual (automatically set)",
    )
    target_group_id = fields.Many2one(
        "res.partner",
        string="Target Group",
        tracking=True,
        domain="[('is_group', '=', True), ('is_registrant', '=', True), ('id', '!=', registrant_id)]",
    )
    new_role_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role in New Group",
        domain=(
            "[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type'), ('code', '!=', 'head')]"
        ),
        tracking=True,
        help="The role/relationship in the new group",
    )
    transfer_reason = fields.Selection(
        [
            ("marriage", "Marriage"),
            ("separation", "Separation/Divorce"),
            ("relocation", "Relocation"),
            ("household_split", "Household Split"),
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Transfer Reason",
        tracking=True,
    )
    transfer_date = fields.Date(
        string="Transfer Date",
        default=fields.Date.today,
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
    source_group_name = fields.Char(
        string="Source Group Name",
        related="source_group_id.name",
        readonly=True,
    )
    target_group_name = fields.Char(
        string="Target Group Name",
        related="target_group_id.name",
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

    @api.constrains("target_group_id", "source_group_id")
    def _check_different_groups(self):
        """Ensure source and target groups are different."""
        for rec in self:
            if rec.target_group_id and rec.source_group_id:
                if rec.target_group_id == rec.source_group_id:
                    raise ValidationError("Target group must be different from source group.")
