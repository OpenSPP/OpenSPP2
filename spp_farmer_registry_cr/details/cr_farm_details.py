# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Detail: Update Farm Details.

Allows updating farm classification, size, and land tenure through
the change request approval workflow.
"""

from odoo import api, fields, models


class SPPCRDetailFarmDetails(models.Model):
    """Detail model for Update Farm Details CR type."""

    _name = "spp.cr.detail.farm_details"
    _description = "CR Detail: Update Farm Details"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ══════════════════════════════════════════════════════════════════════════
    # FARM CLASSIFICATION (Vocabulary-based)
    # ══════════════════════════════════════════════════════════════════════════

    farm_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Farm Type",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:farm-type')]",
        tracking=True,
    )
    holder_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Holder Type",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:holder-type')]",
        tracking=True,
    )
    land_tenure_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Land Tenure",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:land-tenure')]",
        tracking=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # FARM SIZE
    # ══════════════════════════════════════════════════════════════════════════

    farm_total_size = fields.Float(string="Total Farm Size (hectares)", tracking=True)
    farm_size_under_crops = fields.Float(string="Acreage Under Crops", tracking=True)
    farm_size_under_livestock = fields.Float(string="Acreage Under Livestock", tracking=True)
    farm_size_under_aquaculture = fields.Float(string="Acreage Under Aquaculture", tracking=True)
    farm_size_leased_out = fields.Float(string="Acreage Leased Out", tracking=True)
    farm_size_idle = fields.Float(string="Acreage Fallow/Idle", tracking=True)

    data_source_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Data Source",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:data-source')]",
        tracking=True,
    )
    last_field_visit = fields.Date(string="Last Field Visit", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # EXPERIENCE
    # ══════════════════════════════════════════════════════════════════════════

    experience_years = fields.Integer(string="Years of Experience", tracking=True)

    # ══════════════════════════════════════════════════════════════════════════
    # PREFILL MAPPING
    # ══════════════════════════════════════════════════════════════════════════

    def _get_prefill_mapping(self):
        """Return the field mapping for pre-filling from registrant."""
        return {
            "farm_type_id": "farm_type_id",
            "holder_type_id": "holder_type_id",
            "land_tenure_id": "land_tenure_id",
            "farm_total_size": "farm_total_size",
            "farm_size_under_crops": "farm_size_under_crops",
            "farm_size_under_livestock": "farm_size_under_livestock",
            "farm_size_under_aquaculture": "farm_size_under_aquaculture",
            "farm_size_leased_out": "farm_size_leased_out",
            "farm_size_idle": "farm_size_idle",
            "experience_years": "experience_years",
            "data_source_id": "data_source_id",
            "last_field_visit": "last_field_visit",
        }

    @api.onchange("registrant_id")
    def _onchange_registrant_id(self):
        """Pre-fill current values from registrant."""
        if self.registrant_id:
            mapping = self._get_prefill_mapping()
            for detail_field, registrant_field in mapping.items():
                registrant_value = getattr(self.registrant_id, registrant_field, False)
                if registrant_value:
                    setattr(self, detail_field, registrant_value)
