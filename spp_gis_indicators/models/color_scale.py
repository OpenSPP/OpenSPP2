# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GisColorScale(models.Model):
    """GIS Color Scale for Choropleth Visualization.

    Defines color schemes for mapping data values to colors in choropleth maps.
    Based on ColorBrewer schemes optimized for data visualization.
    """

    _name = "spp.gis.color.scale"
    _description = "GIS Color Scale"
    _order = "sequence, name"

    name = fields.Char(
        string="Scale Name",
        required=True,
        translate=True,
        help="Name of the color scale (e.g., 'Blues', 'RdYlGn')",
    )

    scale_type = fields.Selection(
        [
            ("sequential", "Sequential (low to high)"),
            ("diverging", "Diverging (negative to positive)"),
            ("categorical", "Categorical (distinct values)"),
        ],
        required=True,
        default="sequential",
        help="Type of color scale: sequential for ordered data, "
        "diverging for data with a meaningful center, "
        "categorical for distinct categories",
    )

    colors_json = fields.Text(
        string="Colors (JSON)",
        required=True,
        help='JSON array of hex colors, e.g., ["#f7fbff", "#deebf7", "#c6dbef"]',
    )

    description = fields.Text(
        string="Description",
        translate=True,
        help="Description of the color scale and recommended use cases",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display order in selection lists",
    )

    active = fields.Boolean(
        default=True,
        help="Inactive scales are hidden from selection",
    )

    @api.constrains("colors_json")
    def _check_colors_json(self):
        """Validate that colors_json is valid JSON array of hex colors."""
        for rec in self:
            if not rec.colors_json:
                continue

            try:
                colors = json.loads(rec.colors_json)
            except json.JSONDecodeError as e:
                raise ValidationError(_("Invalid JSON in colors_json: %s", str(e))) from e

            if not isinstance(colors, list):
                raise ValidationError(_("colors_json must be a JSON array"))

            if len(colors) < 2:
                raise ValidationError(_("Color scale must have at least 2 colors"))

            # Validate hex color format
            for color in colors:
                if not isinstance(color, str):
                    raise ValidationError(_("All colors must be strings, got: %s", type(color).__name__))
                if not color.startswith("#") or len(color) not in (4, 7):
                    raise ValidationError(
                        _(
                            "Invalid hex color format: %s. " "Expected #RGB or #RRGGBB",
                            color,
                        )
                    )

    def get_colors(self):
        """Return list of color strings from JSON.

        Returns:
            list: List of hex color strings
        """
        self.ensure_one()
        if not self.colors_json:
            return []
        return json.loads(self.colors_json)

    def get_color_for_value(self, value, min_val, max_val, num_classes=None, center=None):
        """Get color for a specific value based on the scale.

        For sequential scales, maps linearly from min to max.
        For diverging scales, maps relative to a center point (default: midpoint).

        Args:
            value: The data value to map to a color
            min_val: Minimum value in the dataset
            max_val: Maximum value in the dataset
            num_classes: Number of color classes (defaults to scale length)
            center: Center value for diverging scales (default: midpoint)

        Returns:
            str: Hex color code
        """
        self.ensure_one()
        colors = self.get_colors()

        if num_classes is None:
            num_classes = len(colors)

        # Handle edge cases
        if max_val == min_val:
            # For diverging, return center color; for sequential, return first
            if self.scale_type == "diverging":
                return colors[len(colors) // 2]
            return colors[0]

        if value <= min_val:
            return colors[0]

        if value >= max_val:
            return colors[-1]

        # Handle diverging scales with center point
        if self.scale_type == "diverging":
            if center is None:
                center = (min_val + max_val) / 2

            center_idx = len(colors) // 2

            if value < center:
                # Map to lower half of colors
                if center == min_val:
                    normalized = 0
                else:
                    normalized = (value - min_val) / (center - min_val)
                color_idx = int(normalized * center_idx)
            else:
                # Map to upper half of colors
                if max_val == center:
                    normalized = 1
                else:
                    normalized = (value - center) / (max_val - center)
                color_idx = center_idx + int(normalized * (len(colors) - center_idx - 1))

            color_idx = max(0, min(color_idx, len(colors) - 1))
            return colors[color_idx]

        # Sequential scale: linear mapping
        normalized = (value - min_val) / (max_val - min_val)
        color_idx = int(normalized * (num_classes - 1))
        color_idx = min(color_idx, len(colors) - 1)

        return colors[color_idx]
