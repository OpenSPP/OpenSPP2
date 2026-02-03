from odoo import api, fields, models


class SPPCRDetailCreateGroup(models.Model):
    """Detail model for Create New Group CR type."""

    _name = "spp.cr.detail.create_group"
    _description = "CR Detail: Create New Group"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # GROUP INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

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

    # Head of Household
    head_individual_id = fields.Many2one(
        "res.partner",
        string="Head of Household",
        tracking=True,
        domain="[('is_group', '=', False), ('is_registrant', '=', True)]",
        help="Select existing individual as head, or leave empty to create new",
    )
    create_new_head = fields.Boolean(
        string="Create New Head",
        default=False,
        tracking=True,
    )
    head_name = fields.Char(
        string="Head Name",
        tracking=True,
        help="Name for new head of household",
    )
    head_given_name = fields.Char(string="Head Given Name", tracking=True)
    head_family_name = fields.Char(string="Head Family Name", tracking=True)
    head_birthdate = fields.Date(string="Head Date of Birth", tracking=True)
    head_gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Head Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
        tracking=True,
    )
    head_phone = fields.Char(string="Head Phone", tracking=True)

    # Address
    address_line1 = fields.Char(string="Address Line 1", tracking=True)
    address_line2 = fields.Char(string="Address Line 2", tracking=True)
    city = fields.Char(string="City", tracking=True)
    state_id = fields.Many2one("res.country.state", string="State/Province", tracking=True)
    postal_code = fields.Char(string="Postal Code", tracking=True)
    country_id = fields.Many2one("res.country", string="Country", tracking=True)

    # Contact
    phone = fields.Char(string="Group Phone", tracking=True)
    email = fields.Char(string="Group Email", tracking=True)

    # Reference to created group (set after apply)
    created_group_id = fields.Many2one(
        "res.partner",
        string="Created Group",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("head_given_name", "head_family_name")
    def _onchange_head_names(self):
        """Auto-compute head name from given + family."""
        if self.create_new_head and (self.head_given_name or self.head_family_name):
            name_vals = [
                f"{self.head_family_name},"
                if self.head_family_name and self.head_given_name
                else f"{self.head_family_name}"
                if self.head_family_name
                else "",
                self.head_given_name,
            ]

            name = " ".join(filter(None, name_vals))
            self.head_name = name.upper()

    @api.onchange("create_new_head")
    def _onchange_create_new_head(self):
        """Clear head selection when toggling create mode."""
        if self.create_new_head:
            self.head_individual_id = False
        else:
            self.head_name = False
            self.head_given_name = False
            self.head_family_name = False
            self.head_birthdate = False
            self.head_gender_id = False
            self.head_phone = False
