# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class HazardIncidentArea(models.Model):
    """Extend incident area with GIS polygon for map visualization."""

    _inherit = "spp.hazard.incident.area"

    # Related geo_polygon from the linked area for GIS display
    # Must be stored for searchRead access in GIS cross-model layers
    geo_polygon = fields.GeoPolygonField(
        related="area_id.geo_polygon",
        string="Area Polygon",
        store=True,
        help="Geographic polygon of the affected area for GIS visualization",
    )

    # Computed severity that falls back to incident severity
    effective_severity = fields.Selection(
        [
            ("1", "Level 1 - Minor"),
            ("2", "Level 2 - Moderate"),
            ("3", "Level 3 - Significant"),
            ("4", "Level 4 - Severe"),
            ("5", "Level 5 - Catastrophic"),
        ],
        compute="_compute_effective_severity",
        store=True,
        help="Area-specific severity or inherited from incident",
    )

    # Additional fields for GIS popup display and grouping
    incident_name = fields.Char(
        related="incident_id.name",
        string="Incident Name",
    )
    incident_status = fields.Selection(
        related="incident_id.status",
        string="Status",
    )
    hazard_category_id = fields.Many2one(
        related="incident_id.category_id",
        string="Hazard Type",
        store=True,
    )
    hazard_category_name = fields.Char(
        related="incident_id.category_id.name",
        string="Hazard Category",
    )
    area_name = fields.Char(
        related="area_id.name",
        string="Area Name",
    )

    # Numeric severity for choropleth visualization
    severity_numeric = fields.Integer(
        string="Severity Level",
        compute="_compute_severity_numeric",
        store=True,
        help="Numeric severity (1-5) for choropleth map visualization",
    )

    @api.depends("severity_override", "incident_id.severity")
    def _compute_effective_severity(self):
        """Compute effective severity from override or incident default."""
        for rec in self:
            rec.effective_severity = rec.severity_override or rec.incident_id.severity or "3"

    @api.depends("effective_severity")
    def _compute_severity_numeric(self):
        """Compute numeric severity from selection value for choropleth."""
        for rec in self:
            rec.severity_numeric = int(rec.effective_severity) if rec.effective_severity else 3
