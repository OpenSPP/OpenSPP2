# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HxlImportProfile(models.Model):
    """Configuration for HXL data import with area aggregation.

    Defines how to match HXL data rows to geographical areas and which
    aggregation rules to apply for generating area-level indicators.
    """

    _name = "spp.hxl.import.profile"
    _description = "HXL Import Profile"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True, help="Unique identifier for this profile")
    description = fields.Text(help="Description of what this profile imports and aggregates")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ─── Area Matching Configuration ───────────────────────────────────
    area_matching_strategy = fields.Selection(
        [
            ("pcode", "P-code Match"),
            ("name", "Name Match"),
            ("gps", "GPS Coordinates"),
            ("fuzzy", "Fuzzy Name Match"),
        ],
        default="pcode",
        required=True,
        help="Strategy for matching HXL data rows to geographical areas",
    )

    area_column_tag = fields.Char(
        string="Area Column HXL Tag",
        default="#adm2+pcode",
        help="HXL tag for the area identifier column (e.g., #adm2+pcode, #adm3+name)",
    )

    area_level = fields.Integer(
        string="Target Admin Level",
        help="Administrative level to match areas at (e.g., 2 for District, 3 for Division)",
    )

    # For GPS matching
    latitude_tag = fields.Char(
        string="Latitude HXL Tag",
        default="#geo+lat",
        help="HXL tag for latitude column (used with GPS matching strategy)",
    )
    longitude_tag = fields.Char(
        string="Longitude HXL Tag",
        default="#geo+lon",
        help="HXL tag for longitude column (used with GPS matching strategy)",
    )

    # ─── Aggregation Rules ───────────────────────────────────────────
    aggregation_ids = fields.One2many(
        "spp.hxl.aggregation.rule",
        "profile_id",
        string="Aggregation Rules",
        help="Define how to aggregate HXL data to area indicators",
    )

    # ─── Default Context ───────────────────────────────────────────
    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Default Incident",
        help="Optionally link imported data to a specific incident/disaster event",
    )

    # ─── Statistics ───────────────────────────────────────────
    batch_count = fields.Integer(
        string="Import Batches",
        compute="_compute_batch_count",
        help="Number of imports using this profile",
    )

    _code_unique = models.Constraint("UNIQUE(code)", "Profile code must be unique")

    def _compute_batch_count(self):
        """Count import batches using this profile."""
        for rec in self:
            rec.batch_count = self.env["spp.hxl.import.batch"].search_count([("profile_id", "=", rec.id)])

    def action_view_batches(self):
        """Show all import batches for this profile."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import Batches"),
            "res_model": "spp.hxl.import.batch",
            "view_mode": "list,form",
            "domain": [("profile_id", "=", self.id)],
            "context": {"default_profile_id": self.id},
        }

    def validate_configuration(self):
        """Validate profile configuration."""
        self.ensure_one()

        if not self.area_column_tag:
            raise ValidationError(_("Area column HXL tag is required"))

        if self.area_matching_strategy == "gps":
            if not self.latitude_tag or not self.longitude_tag:
                raise ValidationError(_("GPS matching requires both latitude and longitude tags"))

        if not self.aggregation_ids:
            raise ValidationError(_("At least one aggregation rule is required"))

        return True
