# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend geofence model with API-specific types and properties."""

from odoo import fields, models


class GisGeofence(models.Model):
    _inherit = "spp.gis.geofence"

    geofence_type = fields.Selection(
        selection_add=[
            ("service_area", "Service Area"),
            ("targeting_area", "Targeting Area"),
        ],
        ondelete={
            "service_area": "set default",
            "targeting_area": "set default",
        },
    )

    def _get_geojson_properties(self):
        """Extend properties with incident info when spp_hazard is installed."""
        props = super()._get_geojson_properties()
        if "incident_id" in self._fields:
            props["incident_id"] = (
                self.incident_id.uuid if self.incident_id and hasattr(self.incident_id, "uuid") else None
            )
            props["incident_name"] = self.incident_id.name if self.incident_id else None
        return props
