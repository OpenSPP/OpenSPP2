# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: WGS84 bounds. Anything outside these is not a place on Earth, and the map
#: widget cannot project it — see _check_gis_lat_long.
LATITUDE_RANGE = (-90.0, 90.0)
LONGITUDE_RANGE = (-180.0, 180.0)


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

    @api.constrains("gis_latitude", "gis_longitude", "coordinates")
    def _check_gis_lat_long(self):
        """Refuse coordinates that are not a place on Earth (OP#1143 QA round 1).

        Without this the value was stored, and the MapTiler widget then threw
        ``Cannot read properties of undefined`` while projecting the point —
        on mouseover, so it fired again on every reopen and the field could not
        be corrected. Rejecting the write keeps the last good value and leaves
        the user on the form to fix their typo.

        Constrained on ``coordinates`` too, so a point arriving from an import
        or from another module writing the geometry directly is checked on the
        same terms as one typed into the form.
        """
        for rec in self:
            if not LATITUDE_RANGE[0] <= rec.gis_latitude <= LATITUDE_RANGE[1]:
                raise ValidationError(
                    _(
                        "Latitude must be between %(low)s and %(high)s degrees; got %(value)s.",
                        low=LATITUDE_RANGE[0],
                        high=LATITUDE_RANGE[1],
                        value=rec.gis_latitude,
                    )
                )
            if not LONGITUDE_RANGE[0] <= rec.gis_longitude <= LONGITUDE_RANGE[1]:
                raise ValidationError(
                    _(
                        "Longitude must be between %(low)s and %(high)s degrees; got %(value)s.",
                        low=LONGITUDE_RANGE[0],
                        high=LONGITUDE_RANGE[1],
                        value=rec.gis_longitude,
                    )
                )
