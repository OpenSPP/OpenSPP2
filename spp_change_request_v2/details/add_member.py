from odoo import api, fields, models


class SPPCRDetailAddMember(models.Model):
    """Detail model for Add Member CR type."""

    _name = "spp.cr.detail.add_member"
    _description = "CR Detail: Add Group Member"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # MEMBER INFORMATION - Real Odoo fields with full features
    # ══════════════════════════════════════════════════════════════════════════

    member_name = fields.Char(
        string="Full Name",
        tracking=True,
        help="Required before apply. Auto-computed from given/family names.",
    )
    given_name = fields.Char(string="Given Name", tracking=True)
    family_name = fields.Char(string="Family Name", tracking=True)
    birthdate = fields.Date(string="Date of Birth", tracking=True)
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
        tracking=True,
    )
    relationship_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Relationship to Head",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type'),"
        " ('code', '!=', 'head')]",
        tracking=True,
    )
    id_number = fields.Char(string="ID Number", tracking=True)
    phone = fields.Char(string="Phone Number", tracking=True)

    # Reference to created individual (set after apply)
    created_individual_id = fields.Many2one(
        "res.partner",
        string="Created Individual",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE - Full Odoo functionality
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("given_name", "family_name")
    def _onchange_names(self):
        """Auto-compute full name from given + family."""
        if self.given_name or self.family_name:
            name_vals = [
                f"{self.family_name},"
                if self.family_name and self.given_name
                else f"{self.family_name}"
                if self.family_name
                else "",
                self.given_name,
            ]

            name = " ".join(filter(None, name_vals))
            self.member_name = name.upper()
