from odoo import api, fields, models
from odoo.exceptions import ValidationError

ROLE_NAMESPACE = "urn:openspp:vocab:group-membership-type"
HEAD_ROLE_CODE = "head"


class SPPCRDetailSplitHousehold(models.Model):
    """Detail model for Split Household CR type (OP#877).

    Splits members out of a source household into a brand-new household. The new
    household captures the same group fields as Create Group (OP#876); the
    members to move are an editable table (member + role + per-member edits via
    a modal). A head for the new group is NOT mandatory.
    """

    _name = "spp.cr.detail.split_household"
    _description = "CR Detail: Split Household"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ──────────────────────────────────────────────────────────────────────
    # Source household (prefilled from the registrant) + reason
    # ──────────────────────────────────────────────────────────────────────
    source_group_id = fields.Many2one(
        "res.partner",
        string="Source Household",
        related="change_request_id.registrant_id",
        store=True,
        readonly=True,
    )
    source_group_name = fields.Char(related="source_group_id.name", readonly=True)
    split_reason = fields.Selection(
        [
            ("marriage", "Marriage"),
            ("separation", "Separation/Divorce"),
            ("independence", "Member Independence"),
            ("relocation", "Relocation"),
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Reason for Split",
        tracking=True,
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # Source members that may be moved (active, non-head). Used by the move-line
    # member picker's domain via parent reference in the view.
    available_member_ids = fields.Many2many(
        "res.partner",
        string="Available Members",
        compute="_compute_available_member_ids",
        help="Active members of the source household, excluding the head (who cannot be moved).",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Members to move (table with per-member role + edit modal)
    # ──────────────────────────────────────────────────────────────────────
    member_line_ids = fields.One2many(
        "spp.cr.detail.split_household.member",
        "detail_id",
        string="Members to Move",
    )

    # ──────────────────────────────────────────────────────────────────────
    # New household — same group fields as Create Group (OP#876)
    # ──────────────────────────────────────────────────────────────────────
    new_group_name = fields.Char(string="New Household Name", tracking=True)
    new_group_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Group Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-type')]",
        tracking=True,
        help="Leave empty to use the same type as the source household.",
    )
    new_area_id = fields.Many2one("spp.area", string="Area", tracking=True)
    new_address = fields.Text(string="Address", tracking=True)
    new_email = fields.Char(string="Email", tracking=True)
    new_latitude = fields.Float(string="Latitude", digits=(13, 10), tracking=True)
    new_longitude = fields.Float(string="Longitude", digits=(13, 10), tracking=True)
    new_phone_line_ids = fields.One2many(
        "spp.cr.detail.create_group.phone", "split_household_detail_id", string="Phone Numbers"
    )
    new_bank_line_ids = fields.One2many(
        "spp.cr.detail.create_group.bank", "split_household_detail_id", string="Bank Accounts"
    )
    new_id_doc_line_ids = fields.One2many(
        "spp.cr.detail.create_group.id_doc", "split_household_detail_id", string="Identity Documents"
    )

    created_group_id = fields.Many2one("res.partner", string="Created Household", readonly=True)

    # ──────────────────────────────────────────────────────────────────────
    # Stat counters
    # ──────────────────────────────────────────────────────────────────────
    members_to_split_count = fields.Integer(compute="_compute_members_count", string="Moving")
    remaining_members_count = fields.Integer(compute="_compute_members_count", string="Remaining")

    # ──────────────────────────────────────────────────────────────────────
    # Computes / constraints
    # ──────────────────────────────────────────────────────────────────────
    @api.depends("source_group_id")
    def _compute_available_member_ids(self):
        head = self.env["spp.vocabulary.code"].get_code(ROLE_NAMESPACE, HEAD_ROLE_CODE)
        for rec in self:
            individuals = self.env["res.partner"]
            if rec.source_group_id and rec.source_group_id.is_group:
                memberships = self.env["spp.group.membership"].search(
                    [("group", "=", rec.source_group_id.id), ("status", "=", "active")]
                )
                non_head = memberships.filtered(lambda m, h=head: not h or h not in m.membership_type_ids)
                individuals = non_head.mapped("individual")
            rec.available_member_ids = individuals

    @api.depends("member_line_ids", "source_group_id")
    def _compute_members_count(self):
        for rec in self:
            rec.members_to_split_count = len(rec.member_line_ids)
            total = 0
            if rec.source_group_id:
                total = self.env["spp.group.membership"].search_count(
                    [("group", "=", rec.source_group_id.id), ("status", "=", "active")]
                )
            rec.remaining_members_count = total - rec.members_to_split_count

    @api.constrains("member_line_ids", "source_group_id")
    def _check_minimum_remaining(self):
        """At least one member must remain in the source household."""
        for rec in self:
            if rec.source_group_id and rec.member_line_ids:
                total = self.env["spp.group.membership"].search_count(
                    [("group", "=", rec.source_group_id.id), ("status", "=", "active")]
                )
                if len(rec.member_line_ids) >= total:
                    raise ValidationError(
                        "Cannot move all members. At least one member must remain in the source household."
                    )


class SPPCRDetailSplitHouseholdMember(models.Model):
    """A member moved to the new household, with role and optional edits (OP#877).

    The editable fields capture proposed changes to the individual (applied on
    CR apply, like the Edit Member CR); they are surfaced through the
    "Edit Member Information" modal and default to the member's current values.
    """

    _name = "spp.cr.detail.split_household.member"
    _description = "CR Detail: Split Household - Member to Move"

    detail_id = fields.Many2one("spp.cr.detail.split_household", required=True, ondelete="cascade")
    individual_id = fields.Many2one("res.partner", string="Member", required=True)
    membership_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
    )

    # Editable member info (proposed edits, prefilled from the member).
    given_name = fields.Char(string="Given Name")
    family_name = fields.Char(string="Family Name")
    middle_name = fields.Char(string="Middle Name")
    birthdate = fields.Date(string="Date of Birth")
    birth_place = fields.Char(string="Birth Place")
    gender_id = fields.Many2one(
        "spp.vocabulary.code", string="Gender", domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]"
    )
    civil_status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Civil Status",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:un:unsd:pop-census:marital-status')]",
    )
    occupation_id = fields.Many2one(
        "spp.vocabulary.code", string="Occupation", domain="[('vocabulary_id.namespace_uri', '=', 'urn:ilo:isco-08')]"
    )
    income = fields.Float(string="Income")

    @api.onchange("individual_id")
    def _onchange_individual_id(self):
        """Prefill the editable fields from the selected member's current values."""
        p = self.individual_id
        if not p:
            return
        self.given_name = p.given_name if "given_name" in p._fields else False
        self.family_name = p.family_name if "family_name" in p._fields else False
        for fname in ("birthdate", "birth_place", "gender_id", "civil_status_id", "occupation_id", "income"):
            if fname in p._fields:
                self[fname] = p[fname]
