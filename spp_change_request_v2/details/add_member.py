# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Detail model for the Add Member CR (OP#871).

The first page searches for an existing individual registrant and adds them to
the group with a role. (The earlier create-a-new-individual flow was replaced
per the updated #871 spec — Add Member now selects an existing member.)
"""

from odoo import api, fields, models


class SPPCRDetailAddMember(models.Model):
    """Detail model for Add Member CR type."""

    _name = "spp.cr.detail.add_member"
    _description = "CR Detail: Add Group Member"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ──────────────────────────────────────────────────────────────────────
    # Member to add (existing individual)
    # ──────────────────────────────────────────────────────────────────────
    individual_id = fields.Many2one(
        "res.partner",
        string="Member",
        tracking=True,
        help="Search for an existing individual registrant to add to the group.",
    )
    # Domain string (computed) restricting the picker to existing individual
    # registrants who are not already active members of the group. A computed
    # domain is used instead of a materialised Many2many so the picker scales
    # with a large registry (mirrors spp.change.request.registrant_domain).
    individual_domain = fields.Char(compute="_compute_individual_domain")

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
    allowed_role_ids = fields.Many2many(
        "spp.vocabulary.code",
        string="Allowed Roles",
        compute="_compute_allowed_role_ids",
        help="Roles selectable for the new member; the Head role is excluded when "
        "the group already has a Head of Household (OP#871).",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Read-only context: existing members of the group
    # ──────────────────────────────────────────────────────────────────────
    existing_membership_ids = fields.Many2many(
        "spp.group.membership",
        string="Existing Members",
        compute="_compute_existing_memberships",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Computes
    # ──────────────────────────────────────────────────────────────────────
    def _active_member_individual_ids(self, group):
        """ids of individuals who are active members of the group."""
        if not group or not group.is_group:
            return []
        memberships = self.env["spp.group.membership"].search([("group", "=", group.id), ("status", "=", "active")])
        return memberships.mapped("individual").ids

    @api.depends("change_request_id", "change_request_id.registrant_id")
    def _compute_individual_domain(self):
        for rec in self:
            member_ids = rec._active_member_individual_ids(rec.change_request_id.registrant_id)
            rec.individual_domain = str(
                [
                    ("is_registrant", "=", True),
                    ("is_group", "=", False),
                    ("id", "not in", member_ids),
                ]
            )

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
    def _compute_allowed_role_ids(self):
        """Restrict the Role selection: a group can have only one Head, so the
        Head role is removed from the options when the target group already has
        an active Head of Household (OP#871)."""
        Code = self.env["spp.vocabulary.code"]
        Membership = self.env["spp.group.membership"]
        all_roles = Code.search([("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type")])
        for rec in self:
            roles = all_roles
            group = rec.change_request_id.registrant_id
            if group and group.is_group:
                group_has_head = bool(
                    Membership.search_count(
                        [
                            ("group", "=", group.id),
                            ("status", "=", "active"),
                            ("membership_type_ids.code", "=", "head"),
                        ]
                    )
                )
                if group_has_head:
                    roles = all_roles.filtered(lambda r: r.code != "head")
            rec.allowed_role_ids = roles
