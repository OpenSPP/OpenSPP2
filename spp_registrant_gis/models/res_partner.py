# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    """Extend res.partner to add GIS coordinates for registrants."""

    _inherit = "res.partner"

    coordinates = fields.GeoPointField(
        string="GPS Coordinates",
        help="Geographic coordinates (latitude/longitude) for spatial queries and mapping. "
        "Used for proximity-based targeting and geographic analysis of registrants.",
    )
