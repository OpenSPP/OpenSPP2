# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Agricultural Activity Model - V2 with Vocabulary Integration.

Refactored from V1 to use vocabulary codes for species selection.
Key V2 changes:
- Species now uses spp.vocabulary.code with FAO-aligned URIs
- Activity type determines which vocabulary namespace to filter (cascading selection)
- Purpose field uses vocabulary instead of Selection

V1 → V2 Field Mappings:
- species_id (Many2one spp.farm.species) → species_id (Many2one spp.vocabulary.code)
- activity_type (Selection) → activity_type_id (Many2one vocabulary)
- purpose (Selection) → purpose_id (Many2one vocabulary)
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AgriculturalActivity(models.Model):
    """Agricultural Activity with vocabulary-based species selection."""

    _name = "spp.farm.activity"
    _description = "Agricultural Activity"
    _rec_name = "display_name"

    # Farm references (separate for different activity views)
    crop_farm_id = fields.Many2one("res.partner", string="Crop Farm")
    livestock_farm_id = fields.Many2one("res.partner", string="Livestock Farm")
    aquaculture_farm_id = fields.Many2one("res.partner", string="Aquaculture Farm")

    # Computed field for the actual farm (unified access)
    farm_id = fields.Many2one(
        "res.partner",
        string="Farm",
        compute="_compute_farm_id",
        store=True,
    )

    land_id = fields.Many2one(
        "spp.land.record",
        string="Land Parcel",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # VOCABULARY-BASED FIELDS (V2 Upgrade)
    # ═══════════════════════════════════════════════════════════════════════

    # Activity type still uses Selection for clarity (determines species namespace)
    activity_type = fields.Selection(
        [
            ("crop", "Crop Cultivation"),
            ("livestock", "Livestock Rearing"),
            ("aquaculture", "Aquaculture"),
        ],
        string="Activity Type",
        required=True,
    )

    # Computed namespace for cascading species selection
    species_namespace = fields.Char(
        string="Species Namespace",
        compute="_compute_species_namespace",
        store=True,
        help="Vocabulary namespace filtered by activity type",
    )

    # Species uses vocabulary with dynamic domain based on activity_type
    species_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Species/Crop",
        domain="[('namespace_uri', '=', species_namespace)]",
        ondelete="restrict",
        required=True,
        help="Select species from FAO-aligned vocabulary (ICC crops, FAO livestock, ASFIS aquaculture)",
    )

    purpose_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Purpose",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:activity-purpose')]",
        ondelete="restrict",
        help="Subsistence, commercial, or both",
    )

    cultivation_method_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Cultivation Method",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:cultivation-method')]",
        ondelete="restrict",
        help="Irrigated or rainfed (for crop activities)",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # QUANTITY AND MEASUREMENT FIELDS
    # ═══════════════════════════════════════════════════════════════════════

    quantity = fields.Integer(
        string="Quantity",
        help="Number of livestock heads, weight of fish, or area planted",
    )
    quantity_unit = fields.Char(
        string="Unit",
        help="Unit of measurement (heads, kg, hectares)",
    )
    area_planted = fields.Float(
        string="Area Planted (hectares)",
        help="For crop activities: area under cultivation",
    )
    expected_yield = fields.Float(
        string="Expected Yield",
        help="Expected production quantity",
    )
    actual_yield = fields.Float(
        string="Actual Yield",
        help="Actual production quantity (post-harvest)",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # SEASON REFERENCE
    # ═══════════════════════════════════════════════════════════════════════

    season_id = fields.Many2one(
        "spp.farm.season",
        string="Agricultural Season",
        domain="[('state', '=', 'active')]",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ═══════════════════════════════════════════════════════════════════════

    display_name = fields.Char(
        compute="_compute_display_name",
    )

    @api.depends("activity_type", "species_id")
    def _compute_display_name(self):
        """Display as 'Activity Type - Species' e.g. 'Crop Cultivation - Cereals'."""
        type_labels = dict(self._fields["activity_type"].selection)
        for record in self:
            parts = []
            if record.activity_type:
                parts.append(type_labels.get(record.activity_type, record.activity_type))
            if record.species_id:
                parts.append(record.species_id.display_name)
            record.display_name = " - ".join(parts) if parts else _("New Activity")

    @api.depends("crop_farm_id", "livestock_farm_id", "aquaculture_farm_id")
    def _compute_farm_id(self):
        """Compute unified farm reference."""
        for record in self:
            record.farm_id = record.crop_farm_id or record.livestock_farm_id or record.aquaculture_farm_id

    @api.depends("activity_type")
    def _compute_species_namespace(self):
        """Compute the vocabulary namespace based on activity type.

        This enables cascading species selection:
        - crop → urn:fao:icc:1.1 (FAO ICC Crop Classification)
        - livestock → urn:fao:livestock:2020 (FAO Livestock Classification)
        - aquaculture → urn:fao:asfis:2024 (FAO ASFIS Species List)
        """
        namespace_map = {
            "crop": "urn:fao:icc:1.1",
            "livestock": "urn:fao:livestock:2020",
            "aquaculture": "urn:fao:asfis:2024",
        }
        for record in self:
            record.species_namespace = namespace_map.get(record.activity_type, "")

    # ═══════════════════════════════════════════════════════════════════════
    # CONSTRAINTS AND VALIDATION
    # ═══════════════════════════════════════════════════════════════════════

    @api.constrains("species_id", "activity_type")
    def _check_species_namespace(self):
        """Ensure species matches the activity type namespace."""
        namespace_map = {
            "crop": "urn:fao:icc:1.1",
            "livestock": "urn:fao:livestock:2020",
            "aquaculture": "urn:fao:asfis:2024",
        }
        for record in self:
            if record.species_id and record.activity_type:
                expected_ns = namespace_map.get(record.activity_type)
                if record.species_id.namespace_uri != expected_ns:
                    raise ValidationError(
                        _(
                            "Species '%(species)s' does not match activity type '%(type)s'. "
                            "Please select a species from the correct vocabulary."
                        )
                        % {
                            "species": record.species_id.display,
                            "type": record.activity_type,
                        }
                    )

    @api.constrains("season_id")
    def _check_season_state(self):
        """Prevent activities in closed seasons."""
        for record in self:
            if record.season_id and record.season_id.state == "closed":
                raise ValidationError(_("Cannot create or modify activities in closed seasons"))

    @api.model
    def default_get(self, fields_list):
        """Set default season to most recent active season."""
        res = super().default_get(fields_list)
        if "season_id" in fields_list:
            active_season = self.env["spp.farm.season"].search(
                [("state", "=", "active")],
                order="date_start desc",
                limit=1,
            )
            if active_season:
                res["season_id"] = active_season.id
        return res

    def write(self, vals):
        """Prevent modifications in closed seasons."""
        for record in self:
            if record.season_id and record.season_id.state == "closed":
                raise ValidationError(_("Cannot modify activities in closed seasons"))
        return super().write(vals)

    # ═══════════════════════════════════════════════════════════════════════
    # ONCHANGE HANDLERS
    # ═══════════════════════════════════════════════════════════════════════

    @api.onchange("activity_type")
    def _onchange_activity_type(self):
        """Clear species when activity type changes."""
        self.species_id = False

    @api.onchange("crop_farm_id", "livestock_farm_id", "aquaculture_farm_id")
    def _onchange_farm_id(self):
        """Clear land parcel when farm changes."""
        self.land_id = False

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_species_code(self):
        """Get the species vocabulary code string."""
        self.ensure_one()
        return self.species_id.code if self.species_id else None

    def get_species_fao_uri(self):
        """Get the FAO reference URI for the species.

        Returns the AGROVOC or FAO URI for interoperability.
        """
        self.ensure_one()
        return self.species_id.reference_uri if self.species_id else None
