# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend geofence model with hazard-specific fields."""

from odoo import fields, models


class GisGeofence(models.Model):
    _inherit = "spp.gis.geofence"

    geofence_type = fields.Selection(
        selection_add=[("hazard_zone", "Hazard Zone")],
        ondelete={"hazard_zone": "set default"},
    )

    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Related Incident",
        ondelete="set null",
        help="Hazard incident associated with this geofence",
    )
