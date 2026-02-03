from odoo import api, fields, models


class SPPCRDetailEditIndividual(models.Model):
    """Detail model for Edit Individual CR type."""

    _name = "spp.cr.detail.edit_individual"
    _description = "CR Detail: Edit Individual"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # PERSONAL INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    given_name = fields.Char(string="Given Name", tracking=True)
    family_name = fields.Char(string="Family Name", tracking=True)
    birthdate = fields.Date(string="Date of Birth", tracking=True)
    gender_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Gender",
        domain="[('namespace_uri', '=', 'urn:iso:std:iso:5218')]",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CONTACT INFORMATION
    # ══════════════════════════════════════════════════════════════════════════

    phone = fields.Char(string="Phone Number", tracking=True)
    email = fields.Char(string="Email", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ADDRESS
    # ══════════════════════════════════════════════════════════════════════════

    address_line1 = fields.Char(string="Address Line 1", tracking=True)
    address_line2 = fields.Char(string="Address Line 2", tracking=True)
    city = fields.Char(string="City", tracking=True)
    postal_code = fields.Char(string="Postal Code", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # METHODS - Override base prefill mapping
    # ══════════════════════════════════════════════════════════════════════════

    def _get_prefill_mapping(self):
        """Return the field mapping for pre-filling from registrant.

        Returns:
            dict: Mapping of detail field names to registrant field names
        """
        return {
            "given_name": "given_name",
            "family_name": "family_name",
            "birthdate": "birthdate",
            "gender_id": "gender_id",
            "phone": "phone",
            "email": "email",
            "address_line1": "street",
            "address_line2": "street2",
            "city": "city",
            "postal_code": "zip",
        }

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE - Pre-fill from registrant
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("registrant_id")
    def _onchange_registrant_id(self):
        """Pre-fill current values from registrant."""
        if self.registrant_id:
            # Use the base mixin's prefill logic
            mapping = self._get_prefill_mapping()
            for detail_field, registrant_field in mapping.items():
                registrant_value = getattr(self.registrant_id, registrant_field, False)
                if registrant_value:
                    setattr(self, detail_field, registrant_value)
