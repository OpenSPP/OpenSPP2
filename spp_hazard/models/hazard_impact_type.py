# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HazardImpactType(models.Model):
    """
    Represents the classification of impact types in the OpenSPP system.

    This model defines the types of impacts that can be recorded
    (e.g., displacement, property damage, livelihood loss, injury).
    """

    _name = "spp.hazard.impact.type"
    _description = "Hazard Impact Type"
    _order = "category, sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Display name (e.g., 'Displacement', 'Property Damage')",
    )
    code = fields.Char(
        required=True,
        help="Unique system code",
    )
    category = fields.Selection(
        [
            ("physical", "Physical"),
            ("economic", "Economic"),
            ("health", "Health"),
            ("social", "Social"),
        ],
        required=True,
        help="Grouping category for the impact type",
    )
    description = fields.Text(
        translate=True,
        help="Detailed description of what this impact type means",
    )
    sequence = fields.Integer(
        default=10,
        help="Order in which impact types appear",
    )
    active = fields.Boolean(
        default=True,
        help="Enable or disable this impact type",
    )
    impact_ids = fields.One2many(
        "spp.hazard.impact",
        "impact_type_id",
        string="Impacts",
    )
    impact_count = fields.Integer(
        compute="_compute_impact_count",
        string="Number of Impacts",
    )

    _code_unique = models.Constraint(
        "unique (code)",
        "An impact type with this code already exists!",
    )

    @api.depends("impact_ids")
    def _compute_impact_count(self):
        """Compute the number of impact records using this type."""
        data = self.env["spp.hazard.impact"].read_group(
            [("impact_type_id", "in", self.ids)],
            ["impact_type_id"],
            ["impact_type_id"],
        )
        mapped = {d["impact_type_id"][0]: d["impact_type_id_count"] for d in data}
        for rec in self:
            rec.impact_count = mapped.get(rec.id, 0)
