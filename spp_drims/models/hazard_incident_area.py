# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

# Map CAP severity vocabulary codes to a 1-5 numeric scale (higher = more
# severe) for choropleth map visualization.
CAP_SEVERITY_NUMERIC = {
    "extreme": 5,
    "severe": 4,
    "moderate": 3,
    "minor": 2,
    "unknown": 1,
}


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
    effective_severity_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Effective Severity",
        compute="_compute_effective_severity",
        store=True,
        help="Area-specific severity override, or inherited from the incident",
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

    @api.depends("severity_override_id", "incident_id.severity_id")
    def _compute_effective_severity(self):
        """Compute effective severity from area override or incident default."""
        for rec in self:
            rec.effective_severity_id = rec.severity_override_id or rec.incident_id.severity_id

    @api.depends("effective_severity_id")
    def _compute_severity_numeric(self):
        """Compute numeric severity from the CAP severity code for choropleth."""
        for rec in self:
            rec.severity_numeric = CAP_SEVERITY_NUMERIC.get(rec.effective_severity_id.code, 0)
