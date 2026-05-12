# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Farm Details Model - V2 with Vocabulary Integration.

Refactored from V1 to use vocabulary codes instead of Selection fields.
All selection-based fields now reference spp.vocabulary.code with appropriate
namespace URIs from the FAO-aligned vocabulary module.

V1 → V2 Field Mappings:
- details_farm_type (Selection) → farm_type_id (Many2one vocabulary)
- details_legal_status (Selection) → land_tenure_id (Many2one vocabulary)
- NEW: holder_type_id (Many2one vocabulary) - FAO WCA 2020 compliance
- NEW: data_source_id (Many2one vocabulary) - Audit trail for data provenance
"""

from odoo import fields, models


class FarmDetails(models.Model):
    """Farm Details with vocabulary-based classification."""

    _name = "spp.farm.details"
    _description = "Farm Details"

    # ═══════════════════════════════════════════════════════════════════════
    # VOCABULARY-BASED FIELDS (V2 Upgrade)
    # ═══════════════════════════════════════════════════════════════════════

    farm_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Farm Type",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:farm-type')]",
        help="Primary farm type: crop, livestock, aquaculture, or mixed",
        ondelete="restrict",
    )

    land_tenure_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Land Tenure",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:land-tenure')]",
        help="Legal status of land ownership/use",
        ondelete="restrict",
    )

    holder_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Holder Type",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:holder-type')]",
        help="Type of agricultural holding (FAO WCA 2020): individual, joint, or institutional",
        ondelete="restrict",
    )

    data_source_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Data Source",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:data-source')]",
        help="Source of this data for audit trail: census, self-registration, or field visit",
        ondelete="restrict",
    )

    last_field_visit = fields.Date(
        string="Field Visit",
        help="Date of the last field visit for data verification",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # ACREAGE / SIZE FIELDS
    # ═══════════════════════════════════════════════════════════════════════

    farm_total_size = fields.Float(
        string="Total Farm Size (hectares)",
        help="Total farm area in hectares",
    )
    farm_size_under_crops = fields.Float(
        string="Acreage Under Crops",
        help="Area currently used for crop cultivation",
    )
    farm_size_under_livestock = fields.Float(
        string="Acreage Under Livestock",
        help="Area used for livestock grazing/housing",
    )
    farm_size_under_aquaculture = fields.Float(
        string="Acreage Under Aquaculture",
        help="Area used for aquaculture (ponds, tanks)",
    )
    farm_size_leased_out = fields.Float(
        string="Acreage Leased Out",
        help="Area leased to others",
    )
    farm_size_idle = fields.Float(
        string="Acreage Fallow/Idle",
        help="Area currently not in use",
    )

    # Years of farming experience
    experience_years = fields.Integer(
        string="Years of Experience",
        help="Farmer's years of agricultural experience",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # VOCABULARY HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_farm_type_code(self):
        """Get the farm type vocabulary code string."""
        self.ensure_one()
        return self.farm_type_id.code if self.farm_type_id else None

    def get_land_tenure_code(self):
        """Get the land tenure vocabulary code string."""
        self.ensure_one()
        return self.land_tenure_id.code if self.land_tenure_id else None

    def is_farm_type(self, code):
        """Check if farm matches a specific type code.

        Args:
            code: The vocabulary code to check (e.g., 'crop', 'livestock', 'mixed')

        Returns:
            bool: True if farm type matches
        """
        self.ensure_one()
        return self.farm_type_id and self.farm_type_id.code == code
