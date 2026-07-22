# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json

from odoo import api, fields, models


class ResPartner(models.Model):
    """Extend res.partner to add GIS coordinates for registrants."""

    _inherit = "res.partner"

    coordinates = fields.GeoPointField(
        string="GPS Coordinates",
        help="Geographic coordinates (latitude/longitude) for spatial queries and mapping. "
        "Used for proximity-based targeting and geographic analysis of registrants.",
    )
    # OP#1143: plain latitude/longitude inputs kept in sync with `coordinates`
    # so the values can be entered (registry create, change requests) and
    # imported without needing the MapTiler map widget configured. Editing the
    # map updates these; editing these rebuilds the point.
    gis_latitude = fields.Float(
        string="Latitude",
        digits=(9, 6),
        compute="_compute_gis_lat_long",
        inverse="_inverse_gis_lat_long",
        store=True,
        help="Latitude in decimal degrees (WGS84). Kept in sync with GPS Coordinates.",
    )
    gis_longitude = fields.Float(
        string="Longitude",
        digits=(9, 6),
        compute="_compute_gis_lat_long",
        inverse="_inverse_gis_lat_long",
        store=True,
        help="Longitude in decimal degrees (WGS84). Kept in sync with GPS Coordinates.",
    )

    @api.depends("coordinates")
    def _compute_gis_lat_long(self):
        """Derive latitude/longitude from the point geometry (x=lon, y=lat)."""
        for rec in self:
            geom = rec.coordinates
            if geom and not geom.is_empty and getattr(geom, "geom_type", None) == "Point":
                rec.gis_longitude = geom.x
                rec.gis_latitude = geom.y
            else:
                rec.gis_longitude = 0.0
                rec.gis_latitude = 0.0

    def _inverse_gis_lat_long(self):
        """Rebuild the point geometry when latitude/longitude are entered.

        Both values are taken from the record, so filling either field commits
        the current pair. (0, 0) is treated as "unset" and clears the point.
        """
        for rec in self:
            if rec.gis_latitude or rec.gis_longitude:
                rec.coordinates = json.dumps({"type": "Point", "coordinates": [rec.gis_longitude, rec.gis_latitude]})
            else:
                rec.coordinates = False
