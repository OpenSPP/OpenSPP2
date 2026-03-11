# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.fields import Many2one

_logger = logging.getLogger(__name__)


class GisDataLayerIndicator(models.Model):
    """Extend GIS Data Layer to support indicator-based choropleth visualization."""

    _inherit = "spp.gis.data.layer"

    indicator_layer_id = Many2one(
        "spp.gis.indicator.layer",
        string="Indicator Configuration",
        help="Configure which indicator to visualize as choropleth",
    )

    @api.constrains("geo_repr", "choropleth_field_id", "indicator_layer_id")
    def _check_choropleth_config(self):
        """Validate choropleth layers have required configuration.

        Overrides base constraint to accept EITHER choropleth_field_id
        OR indicator_layer_id for choropleth layers.
        """
        for rec in self:
            if rec.geo_repr == "choropleth" and not rec.choropleth_field_id and not rec.indicator_layer_id:
                raise ValidationError(_("Choropleth layers require a Value Field or Indicator Configuration."))

    def _get_choropleth_config(self):
        """Return choropleth configuration dictionary for frontend.

        Overrides base to return indicator-based config when indicator_layer_id
        is set, falling back to the base field-based config otherwise.
        """
        self.ensure_one()
        if self.geo_repr != "choropleth":
            return None

        if self.indicator_layer_id:
            breaks = json.loads(self.indicator_layer_id.break_values or "[]")
            colors = (
                self.indicator_layer_id.color_scale_id.get_colors() if self.indicator_layer_id.color_scale_id else []
            )
            return {
                "type": "indicator",
                "color_ramp": colors,
                "break_values": breaks,
                "classification": self.indicator_layer_id.classification_method,
                "class_count": self.indicator_layer_id.num_classes,
                "show_legend": True,
                "legend_title": self.indicator_layer_id.name,
                "legend_html": self.indicator_layer_id.legend_html,
            }

        return super()._get_choropleth_config()
