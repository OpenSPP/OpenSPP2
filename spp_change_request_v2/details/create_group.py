# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Detail model + sub-models for the Create New Group CR (OP#876)."""

from datetime import date

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
    # The registry stores a single free-text address (res.partner.address), so the
    # CR collects it the same way to map cleanly on apply (OP#876 QA round 1).
    address = fields.Text(string="Address", tracking=True)
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
    _description = "CR Detail: Phone Number (Create Group / Add Member)"
    _order = "is_primary desc, id"

    # The same row shape is reused by the group detail (Create Group), the Add
    # Member detail, and a Create-Group new-member row. Exactly one parent FK
    # must be set — enforced by ``_check_one_parent`` (OP#871/#876).
    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        ondelete="cascade",
    )
    add_member_detail_id = fields.Many2one(
        "spp.cr.detail.add_member",
        ondelete="cascade",
    )
    member_new_id = fields.Many2one(
        "spp.cr.detail.create_group.member_new",
        ondelete="cascade",
    )
    phone_no = fields.Char(string="Phone Number", required=True)
    country_id = fields.Many2one("res.country", string="Country")
    is_primary = fields.Boolean(
        string="Primary",
        help="The first primary phone is also written to the partner's header phone field.",
    )

    @api.constrains("detail_id", "add_member_detail_id", "member_new_id")
    def _check_one_parent(self):
        # Only reject a row linked to more than one context. A row with no
        # parent is harmless (an unreferenced orphan) and can occur transiently
        # while Odoo rewrites a one2many, so it must not raise — requiring
        # exactly one surfaced a confusing "parent" error to users editing a
        # member's phone list.
        for rec in self:
            if sum(1 for p in (rec.detail_id, rec.add_member_detail_id, rec.member_new_id) if p) > 1:
                raise ValidationError(_("A phone-number row cannot belong to more than one record."))


class SPPCRDetailCreateGroupBank(models.Model):
    _name = "spp.cr.detail.create_group.bank"
    _description = "CR Detail: Bank Account (Create Group / Add Member)"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        ondelete="cascade",
    )
    add_member_detail_id = fields.Many2one(
        "spp.cr.detail.add_member",
        ondelete="cascade",
    )
    acc_number = fields.Char(string="Account Number", required=True)
    acc_holder_name = fields.Char(string="Account Holder")
    bank_id = fields.Many2one("res.bank", string="Bank")

    @api.constrains("detail_id", "add_member_detail_id")
    def _check_one_parent(self):
        # Only reject multi-parenting; a transient zero-parent state during a
        # one2many rewrite is harmless (see the phone row note).
        for rec in self:
            if rec.detail_id and rec.add_member_detail_id:
                raise ValidationError(_("A bank-account row cannot belong to more than one record."))


class SPPCRDetailCreateGroupIdDoc(models.Model):
    _name = "spp.cr.detail.create_group.id_doc"
    _description = "CR Detail: Identity Document (Create Group / Add Member)"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        ondelete="cascade",
    )
    add_member_detail_id = fields.Many2one(
        "spp.cr.detail.add_member",
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

    @api.constrains("detail_id", "add_member_detail_id")
    def _check_one_parent(self):
        # Only reject multi-parenting; a transient zero-parent state during a
        # one2many rewrite is harmless (see the phone row note).
        for rec in self:
            if rec.detail_id and rec.add_member_detail_id:
                raise ValidationError(_("An ID document row cannot belong to more than one record."))


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

    @api.constrains("membership_type_id")
    def _check_single_head(self):
        # The parent's @api.constrains on the o2m only fires when the o2m is
        # written through the parent. Rows added via the member wizard are
        # created directly with detail_id set, bypassing it — so guard here too.
        for rec in self:
            if rec.is_head and rec.detail_id._head_count() > 1:
                raise ValidationError(_("A group can have at most one Head of Household."))


class SPPCRDetailCreateGroupMemberNew(models.Model):
    """New individual to create and attach to the new group."""

    _name = "spp.cr.detail.create_group.member_new"
    _description = "CR Detail: Create Group — New Member"

    detail_id = fields.Many2one(
        "spp.cr.detail.create_group",
        required=True,
        ondelete="cascade",
    )
    # Names
    given_name = fields.Char(string="Given Name", required=True)
    family_name = fields.Char(string="Family Name", required=True)
    middle_name = fields.Char(
        string="Middle Name",
        help="res.partner has no native middle name; on apply it is prepended to "
        "the given name when composing the individual's display name.",
    )
    full_name = fields.Char(
        string="Full Name",
        compute="_compute_full_name",
        store=True,
    )
    # Demographics (mirrors the registry's individual overview — OP#876 QA round 1)
    birthdate = fields.Date(string="Date of Birth")
    is_approximate_birthdate = fields.Boolean(string="Approximate Birthdate")
    age = fields.Integer(string="Age", compute="_compute_age")
    birth_place = fields.Char(string="Birth Place")
    occupation_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Occupation",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:ilo:isco-08')]",
    )
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
    )
    civil_status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Civil Status",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:un:unsd:pop-census:marital-status')]",
    )
    income = fields.Float(string="Income")
    # Contact
    area_id = fields.Many2one("spp.area", string="Area")
    address = fields.Text(string="Address")
    email = fields.Char(string="Email")
    phone_line_ids = fields.One2many(
        "spp.cr.detail.create_group.phone",
        "member_new_id",
        string="Phone Numbers",
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

    @api.depends("given_name", "family_name", "middle_name")
    def _compute_full_name(self):
        for rec in self:
            given = (rec.given_name or "").strip()
            family = (rec.family_name or "").strip()
            middle = (rec.middle_name or "").strip()
            first_part = " ".join(filter(None, [given, middle]))
            if family and first_part:
                rec.full_name = f"{family.upper()}, {first_part}"
            else:
                rec.full_name = (first_part or family).upper() or False

    @api.depends("birthdate")
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if not rec.birthdate:
                rec.age = 0
                continue
            bd = rec.birthdate
            rec.age = max(today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day)), 0)

    @api.depends("membership_type_id")
    def _compute_is_head(self):
        for rec in self:
            rec.is_head = bool(rec.membership_type_id and rec.membership_type_id.code == "head")

    @api.constrains("membership_type_id")
    def _check_single_head(self):
        # See note on the existing-member model: wizard rows bypass the
        # parent-level constraint, so enforce one-head at the row level too.
        for rec in self:
            if rec.is_head and rec.detail_id._head_count() > 1:
                raise ValidationError(_("A group can have at most one Head of Household."))

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
                "default_middle_name": self.middle_name,
                "default_birthdate": self.birthdate,
                "default_is_approximate_birthdate": self.is_approximate_birthdate,
                "default_birth_place": self.birth_place,
                "default_occupation_id": self.occupation_id.id if self.occupation_id else False,
                "default_gender_id": self.gender_id.id if self.gender_id else False,
                "default_civil_status_id": self.civil_status_id.id if self.civil_status_id else False,
                "default_income": self.income,
                "default_area_id": self.area_id.id if self.area_id else False,
                "default_address": self.address,
                "default_email": self.email,
                "default_phone_line_ids": [
                    (0, 0, {"phone_no": p.phone_no, "country_id": p.country_id.id, "is_primary": p.is_primary})
                    for p in self.phone_line_ids
                ],
                "default_membership_type_id": self.membership_type_id.id if self.membership_type_id else False,
            },
        }
