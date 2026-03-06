# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class GisDataLayerIndicator(models.Model):
    """Extend GIS Data Layer to support choropleth visualization."""

    _inherit = "spp.gis.data.layer"

    geo_repr = fields.Selection(
        selection_add=[
            ("choropleth", "Choropleth (Data-driven colors)"),
        ],
        ondelete={"choropleth": "set default"},
    )

    indicator_layer_id = fields.Many2one(
        "spp.gis.indicator.layer",
        string="Indicator Configuration",
        help="Configure which indicator to visualize as choropleth",
    )
