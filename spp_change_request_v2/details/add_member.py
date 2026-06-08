# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Detail model for the Add Member CR (OP#871).

Adds a single new individual to an existing group. The detail captures the
spec-mandated field set (names, demographics, contact, location, financials,
ID docs, role) and reuses the per-line phone/bank/id_doc sub-models that
already exist for Create Group (see OP#876).
"""

from datetime import date

from odoo import api, fields, models


class SPPCRDetailAddMember(models.Model):
    """Detail model for Add Member CR type."""

    _name = "spp.cr.detail.add_member"
    _description = "CR Detail: Add Group Member"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ──────────────────────────────────────────────────────────────────────
    # Names
    # ──────────────────────────────────────────────────────────────────────
    given_name = fields.Char(string="Given Name", tracking=True, required=False)
    family_name = fields.Char(string="Family Name", tracking=True, required=False)
    middle_name = fields.Char(
        string="Middle Name",
        tracking=True,
        help="Stored on the CR. On apply, prepended to the given name when "
        "composing the partner's display name (res.partner has no native "
        "middle_name field).",
    )
    member_name = fields.Char(
        string="Full Name",
        compute="_compute_member_name",
        store=True,
        help="Auto-computed: FAMILY, GIVEN MIDDLE. Read-only.",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Demographics
    # ──────────────────────────────────────────────────────────────────────
    birthdate = fields.Date(string="Date of Birth", tracking=True)
    is_approximate_birthdate = fields.Boolean(
        string="Approximate Birthdate",
        help="Flag the birthdate as approximate; downstream stats may exclude "
        "approximate records or treat them with reduced precision.",
    )
    age = fields.Integer(
        string="Age",
        compute="_compute_age",
        help="Auto-computed from Date of Birth.",
    )
    birth_place = fields.Char(string="Birth Place", tracking=True)
    occupation_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Occupation",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:ilo:isco-08')]",
        tracking=True,
    )
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
        tracking=True,
    )
    civil_status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Civil Status",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:un:unsd:pop-census:marital-status')]",
        tracking=True,
    )
    income = fields.Float(string="Income", tracking=True)

    # ──────────────────────────────────────────────────────────────────────
    # Contact
    # ──────────────────────────────────────────────────────────────────────
    area_id = fields.Many2one("spp.area", string="Area", tracking=True)
    # The registry stores a single free-text address (res.partner.address), so the
    # CR collects it the same way to map cleanly on apply (OP#871 QA round 1).
    address = fields.Text(string="Address", tracking=True)
    email = fields.Char(string="Email", tracking=True)

    phone_line_ids = fields.One2many(
        "spp.cr.detail.create_group.phone",
        "add_member_detail_id",
        string="Phone Numbers",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Location
    # ──────────────────────────────────────────────────────────────────────
    latitude = fields.Float(string="Latitude", digits=(13, 10), tracking=True)
    longitude = fields.Float(string="Longitude", digits=(13, 10), tracking=True)

    # ──────────────────────────────────────────────────────────────────────
    # Financial
    # ──────────────────────────────────────────────────────────────────────
    bank_line_ids = fields.One2many(
        "spp.cr.detail.create_group.bank",
        "add_member_detail_id",
        string="Bank Accounts",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Identity Documents
    # ──────────────────────────────────────────────────────────────────────
    id_doc_line_ids = fields.One2many(
        "spp.cr.detail.create_group.id_doc",
        "add_member_detail_id",
        string="Identity Documents",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Role (per-member, single row)
    # ──────────────────────────────────────────────────────────────────────
    membership_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
        tracking=True,
        help="Role of the new member in the group. Optionality controlled by the CR type.",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Type-config mirrors (for view conditionals)
    # ──────────────────────────────────────────────────────────────────────
    type_requires_head = fields.Boolean(
        related="change_request_id.request_type_id.requires_head",
        string="Requires Head",
    )
    roles_available = fields.Boolean(
        compute="_compute_roles_available",
        string="Has Membership Roles",
        help="True when the urn:openspp:vocab:group-membership-type vocabulary has any active code.",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Head-of-household replacement (OP#871 QA round 1)
    # When the target group already has a head, making this new member the head
    # is an explicit, confirmed action rather than a silent auto-demotion.
    # ──────────────────────────────────────────────────────────────────────
    group_has_head = fields.Boolean(
        compute="_compute_current_head",
        string="Group Already Has a Head",
    )
    current_head_name = fields.Char(
        compute="_compute_current_head",
        string="Current Head of Household",
    )
    replace_existing_head = fields.Boolean(
        string="Replace current Head of Household",
        help="When set, applying this change request removes the Head role from "
        "the group's current head and assigns it to this new member.",
    )
    selected_role_is_head = fields.Boolean(
        compute="_compute_selected_role_is_head",
        string="Selected Role Is Head",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Read-only context: existing members of the group (for the spec's
    # "display a table with all members" requirement). Computed, not stored.
    # ──────────────────────────────────────────────────────────────────────
    existing_membership_ids = fields.Many2many(
        "spp.group.membership",
        string="Existing Members",
        compute="_compute_existing_memberships",
    )

    # Reference to created individual (set after apply).
    created_individual_id = fields.Many2one(
        "res.partner",
        string="Created Individual",
        readonly=True,
    )

    # ──────────────────────────────────────────────────────────────────────
    # Computes
    # ──────────────────────────────────────────────────────────────────────
    @api.depends("given_name", "family_name", "middle_name")
    def _compute_member_name(self):
        for rec in self:
            given = (rec.given_name or "").strip()
            family = (rec.family_name or "").strip()
            middle = (rec.middle_name or "").strip()
            first_part = " ".join(filter(None, [given, middle]))
            if family and first_part:
                rec.member_name = f"{family.upper()}, {first_part}".strip()
            elif family:
                rec.member_name = family.upper()
            elif first_part:
                rec.member_name = first_part.upper()
            else:
                rec.member_name = False

    @api.depends("birthdate")
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if not rec.birthdate:
                rec.age = 0
                continue
            bd = rec.birthdate
            years = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            rec.age = max(years, 0)

    @api.depends_context("uid")
    def _compute_roles_available(self):
        has_any = bool(
            self.env["spp.vocabulary.code"].search_count(
                [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type")]
            )
        )
        for rec in self:
            rec.roles_available = has_any

    @api.depends("change_request_id", "change_request_id.registrant_id")
    def _compute_existing_memberships(self):
        Membership = self.env["spp.group.membership"]
        for rec in self:
            group = rec.change_request_id.registrant_id
            if group and group.is_group:
                rec.existing_membership_ids = Membership.search([("group", "=", group.id), ("status", "=", "active")])
            else:
                rec.existing_membership_ids = Membership.browse([])

    @api.depends("change_request_id", "change_request_id.registrant_id")
    def _compute_current_head(self):
        Membership = self.env["spp.group.membership"]
        head_code = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type"),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        for rec in self:
            head = Membership.browse()
            group = rec.change_request_id.registrant_id
            if group and group.is_group and head_code:
                head = Membership.search(
                    [
                        ("group", "=", group.id),
                        ("status", "=", "active"),
                        ("membership_type_ids", "=", head_code.id),
                    ],
                    limit=1,
                )
            rec.group_has_head = bool(head)
            rec.current_head_name = head.individual.name if head else False

    @api.depends("membership_type_id")
    def _compute_selected_role_is_head(self):
        for rec in self:
            rec.selected_role_is_head = bool(rec.membership_type_id and rec.membership_type_id.code == "head")
