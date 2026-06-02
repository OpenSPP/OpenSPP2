# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Detail model + sub-models for the Create New Group CR (OP#876)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SPPCRDetailCreateGroup(models.Model):
    """Detail model for Create New Group CR type."""

    _name = "spp.cr.detail.create_group"
    _description = "CR Detail: Create New Group"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ──────────────────────────────────────────────────────────────────────
    # Group Identification
    # ──────────────────────────────────────────────────────────────────────
    group_name = fields.Char(
        string="Group Name",
        tracking=True,
    )
    group_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Group Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-type')]",
        tracking=True,
    )
    # When the vocabulary has more than one active code we surface the picker;
    # with exactly one option we auto-default and hide it.
    group_type_option_count = fields.Integer(
        compute="_compute_group_type_option_count",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Group Contact Information
    # ──────────────────────────────────────────────────────────────────────
    area_id = fields.Many2one("spp.area", string="Area", tracking=True)
    address_line1 = fields.Char(string="Address Line 1", tracking=True)
    address_line2 = fields.Char(string="Address Line 2", tracking=True)
    city = fields.Char(string="City", tracking=True)
    state_id = fields.Many2one("res.country.state", string="State/Province", tracking=True)
    postal_code = fields.Char(string="Postal Code", tracking=True)
    country_id = fields.Many2one("res.country", string="Country", tracking=True)
    email = fields.Char(string="Email", tracking=True)
    phone_line_ids = fields.One2many(
        "spp.cr.detail.create_group.phone",
        "detail_id",
        string="Phone Numbers",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Group Location (coordinates only — see OP#876 plan note)
    # ──────────────────────────────────────────────────────────────────────
    latitude = fields.Float(string="Latitude", digits=(13, 10), tracking=True)
    longitude = fields.Float(string="Longitude", digits=(13, 10), tracking=True)

    # ──────────────────────────────────────────────────────────────────────
    # Group Financial Information
    # ──────────────────────────────────────────────────────────────────────
    bank_line_ids = fields.One2many(
        "spp.cr.detail.create_group.bank",
        "detail_id",
        string="Bank Accounts",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Group Identity Documents
    # ──────────────────────────────────────────────────────────────────────
    id_doc_line_ids = fields.One2many(
        "spp.cr.detail.create_group.id_doc",
        "detail_id",
        string="Identity Documents",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Membership flow
    # Two parallel sub-tables: existing individuals to attach, and new
    # individuals to create. Both carry the role (membership_type_id) so
    # the Roles requirement can be enforced uniformly at apply time.
    # ──────────────────────────────────────────────────────────────────────
    member_existing_ids = fields.One2many(
        "spp.cr.detail.create_group.member_existing",
        "detail_id",
        string="Existing Members",
    )
    member_new_ids = fields.One2many(
        "spp.cr.detail.create_group.member_new",
        "detail_id",
        string="New Members",
    )

    # Mirrors of the CR type config so the view can reference them via
    # related fields rather than reading parent.request_type_id.* each time.
    type_allow_empty_members = fields.Boolean(
        related="change_request_id.request_type_id.allow_empty_members",
        string="Allows Empty Groups",
    )
    type_requires_head = fields.Boolean(
        related="change_request_id.request_type_id.requires_head",
        string="Requires Head",
    )
    roles_available = fields.Boolean(
        compute="_compute_roles_available",
        string="Has Membership Roles",
        help="True when the urn:openspp:vocab:group-membership-type vocabulary has any active code.",
    )

    # Reference to created group (set after apply).
    created_group_id = fields.Many2one(
        "res.partner",
        string="Created Group",
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────────
    # Computes
    # ──────────────────────────────────────────────────────────────────────
    @api.depends_context("uid")
    def _compute_group_type_option_count(self):
        count = self.env["spp.vocabulary.code"].search_count(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-type")]
        )
        for rec in self:
            rec.group_type_option_count = count

    @api.depends_context("uid")
    def _compute_roles_available(self):
        has_any = bool(
            self.env["spp.vocabulary.code"].search_count(
                [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type")]
            )
        )
        for rec in self:
            rec.roles_available = has_any

    # ──────────────────────────────────────────────────────────────────────
    # Member-wizard openers (one button per mode on the detail form)
    # ──────────────────────────────────────────────────────────────────────
    def _open_member_wizard(self, mode):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Existing Individual") if mode == "existing" else _("Add New Individual"),
            "res_model": "spp.cr.detail.create_group.member.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_detail_id": self.id,
                "default_mode": mode,
            },
        }

    def action_open_add_existing_wizard(self):
        return self._open_member_wizard("existing")

    def action_open_add_new_wizard(self):
        return self._open_member_wizard("new")

    # ──────────────────────────────────────────────────────────────────────
    # Helpers used by the apply strategy
    # ──────────────────────────────────────────────────────────────────────
    def _heads(self):
        """Return a tuple ``(existing_heads, new_heads)`` of recordsets.

        ``member_existing_ids`` and ``member_new_ids`` are different models
        so we can't merge them into one recordset — but the caller usually
        wants to know "how many heads total" and "which row is the head",
        which both work cleanly off the tuple.
        """
        self.ensure_one()
        return (
            self.member_existing_ids.filtered(lambda m: m.is_head),
            self.member_new_ids.filtered(lambda m: m.is_head),
        )

    def _head_count(self):
        """Total number of rows flagged as head across both sub-tables."""
        self.ensure_one()
        existing_heads, new_heads = self._heads()
        return len(existing_heads) + len(new_heads)

    @api.constrains("member_existing_ids", "member_new_ids")
    def _check_at_most_one_head(self):
        for rec in self:
            if rec._head_count() > 1:
                raise ValidationError(_("A group can have at most one Head of Household."))


class SPPCRDetailCreateGroupPhone(models.Model):
    _name = "spp.cr.detail.create_group.phone"
    _description = "CR Detail: Create Group — Phone Number"
    _order = "is_primary desc, id"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        required=True,
        ondelete="cascade",
    )
    phone_no = fields.Char(string="Phone Number", required=True)
    country_id = fields.Many2one("res.country", string="Country")
    is_primary = fields.Boolean(
        string="Primary",
        help="The first primary phone is also written to the group's header phone field.",
    )


class SPPCRDetailCreateGroupBank(models.Model):
    _name = "spp.cr.detail.create_group.bank"
    _description = "CR Detail: Create Group — Bank Account"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        required=True,
        ondelete="cascade",
    )
    acc_number = fields.Char(string="Account Number", required=True)
    acc_holder_name = fields.Char(string="Account Holder")
    bank_id = fields.Many2one("res.bank", string="Bank")


class SPPCRDetailCreateGroupIdDoc(models.Model):
    _name = "spp.cr.detail.create_group.id_doc"
    _description = "CR Detail: Create Group — Identity Document"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        required=True,
        ondelete="cascade",
    )
    id_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="ID Type",
        required=True,
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:id-type')]",
    )
    value = fields.Char(string="Value", required=True)
    expiry_date = fields.Date(string="Expiry Date")


class SPPCRDetailCreateGroupMemberExisting(models.Model):
    """Existing individual being added to the new group."""

    _name = "spp.cr.detail.create_group.member_existing"
    _description = "CR Detail: Create Group — Existing Member"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        required=True,
        ondelete="cascade",
    )
    individual_id = fields.Many2one(
        "res.partner",
        string="Individual",
        required=True,
        domain="[('is_group', '=', False), ('is_registrant', '=', True)]",
    )
    membership_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
    )
    is_head = fields.Boolean(
        string="Is Head",
        compute="_compute_is_head",
        store=True,
    )

    @api.depends("membership_type_id")
    def _compute_is_head(self):
        for rec in self:
            rec.is_head = bool(rec.membership_type_id and rec.membership_type_id.code == "head")


class SPPCRDetailCreateGroupMemberNew(models.Model):
    """New individual to create and attach to the new group."""

    _name = "spp.cr.detail.create_group.member_new"
    _description = "CR Detail: Create Group — New Member"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        required=True,
        ondelete="cascade",
    )
    given_name = fields.Char(string="Given Name", required=True)
    family_name = fields.Char(string="Family Name", required=True)
    full_name = fields.Char(
        string="Full Name",
        compute="_compute_full_name",
        store=True,
    )
    birthdate = fields.Date(string="Date of Birth")
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
    )
    phone = fields.Char(string="Phone")
    membership_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
    )
    is_head = fields.Boolean(
        string="Is Head",
        compute="_compute_is_head",
        store=True,
    )

    @api.depends("given_name", "family_name")
    def _compute_full_name(self):
        for rec in self:
            given = (rec.given_name or "").strip()
            family = (rec.family_name or "").strip()
            if given and family:
                rec.full_name = f"{family.upper()}, {given}"
            else:
                rec.full_name = (given or family).upper() or False

    @api.depends("membership_type_id")
    def _compute_is_head(self):
        for rec in self:
            rec.is_head = bool(rec.membership_type_id and rec.membership_type_id.code == "head")

    def action_open_edit_wizard(self):
        """Re-open the Add Member wizard pre-populated to edit this row."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Edit New Individual"),
            "res_model": "spp.cr.detail.create_group.member.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_detail_id": self.detail_id.id,
                "default_mode": "new",
                "default_editing_member_new_id": self.id,
                "default_given_name": self.given_name,
                "default_family_name": self.family_name,
                "default_birthdate": self.birthdate,
                "default_gender_id": self.gender_id.id if self.gender_id else False,
                "default_phone": self.phone,
                "default_membership_type_id": self.membership_type_id.id if self.membership_type_id else False,
            },
        }
