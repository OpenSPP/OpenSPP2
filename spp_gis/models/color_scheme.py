# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json

from odoo import api, fields, models


class GisColorScheme(models.Model):
    """Color schemes for GIS visualizations.

    Provides centralized color palette management for choropleth maps,
    point markers, and other thematic visualizations. Supports sequential,
    diverging, and qualitative color schemes.

    Color-blind safe schemes are marked and recommended for public-facing
    visualizations to ensure accessibility.
    """

    _name = "spp.gis.color.scheme"
    _description = "GIS Color Scheme"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        help="Display name for the color scheme",
    )
    code = fields.Char(
        required=True,
        index=True,
        help="Unique identifier used in code and API",
    )

    scheme_type = fields.Selection(
        [
            ("sequential", "Sequential (low to high)"),
            ("diverging", "Diverging (negative to positive)"),
            ("qualitative", "Qualitative (categories)"),
        ],
        required=True,
        default="sequential",
        help="Sequential: single direction gradient. "
        "Diverging: two directions from center. "
        "Qualitative: distinct colors for categories.",
    )

    # Color definitions - JSON array of hex colors
    # Sequential: ["#low", "#mid", "#high"] - interpolated
    # Diverging: ["#negative", "#zero", "#positive"] - with midpoint
    # Qualitative: ["#cat1", "#cat2", ...] - distinct colors
    colors = fields.Text(
        "Colors (JSON)",
        required=True,
        default='["#440154", "#21918c", "#fde725"]',
        help="JSON array of hex color values. "
        "For sequential/diverging: minimum 2 colors for gradient. "
        "For qualitative: one color per category.",
    )

    # Number of discrete steps when rendering gradient
    # Higher = smoother gradient but more processing
    default_steps = fields.Integer(
        "Default Steps",
        default=5,
        help="Number of discrete color steps when classifying data. "
        "Used as default for reports using this scheme.",
    )

    # Accessibility
    is_colorblind_safe = fields.Boolean(
        "Color-blind Safe",
        default=False,
        help="Scheme is accessible to users with color vision deficiencies. "
        "Recommended for public-facing visualizations.",
    )

    # Default scheme flag
    is_default = fields.Boolean(
        "Default Scheme",
        default=False,
        help="Use as the default scheme for new reports",
    )

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Computed preview for UI
    preview_gradient = fields.Html(
        compute="_compute_preview_gradient",
        string="Preview",
    )

    _code_unique = models.Constraint("UNIQUE(code)", "Color scheme code must be unique")

    @api.depends("colors", "scheme_type")
    def _compute_preview_gradient(self):
        """Generate CSS gradient preview for list view."""
        for scheme in self:
            try:
                colors = json.loads(scheme.colors) if scheme.colors else []
            except (json.JSONDecodeError, TypeError):
                colors = []

            if not colors:
                scheme.preview_gradient = '<div style="width:100px;height:20px;background:#ccc;border-radius:3px;"></div>'
                continue

            if scheme.scheme_type == "qualitative":
                # Show discrete color blocks
                width = 100 // len(colors)
                blocks = "".join(
                    f'<div style="display:inline-block;width:{width}px;height:20px;background:{c};"></div>'
                    for c in colors
                )
                scheme.preview_gradient = f'<div style="border-radius:3px;overflow:hidden;">{blocks}</div>'
            else:
                # Show gradient
                gradient = ", ".join(colors)
                scheme.preview_gradient = (
                    f'<div style="width:100px;height:20px;'
                    f'background:linear-gradient(to right, {gradient});'
                    f'border-radius:3px;"></div>'
                )

    def get_colors_list(self):
        """Return colors as Python list."""
        self.ensure_one()
        try:
            return json.loads(self.colors) if self.colors else []
        except (json.JSONDecodeError, TypeError):
            return []

    def interpolate_color(self, value, min_val=0, max_val=1):
        """Interpolate a color for a value within the range.

        Args:
            value: The value to get color for
            min_val: Minimum value in range
            max_val: Maximum value in range

        Returns:
            Hex color string
        """
        self.ensure_one()
        colors = self.get_colors_list()
        if not colors:
            return "#808080"

        if len(colors) == 1:
            return colors[0]

        # Normalize value to 0-1 range
        if max_val == min_val:
            t = 0.5
        else:
            t = (value - min_val) / (max_val - min_val)
            t = max(0, min(1, t))  # Clamp to 0-1

        # For diverging, handle negative-positive split
        if self.scheme_type == "diverging" and len(colors) >= 3:
            if t < 0.5:
                # Negative side
                t2 = t * 2
                return self._interpolate_between(colors[0], colors[1], t2)
            else:
                # Positive side
                t2 = (t - 0.5) * 2
                return self._interpolate_between(colors[1], colors[2], t2)

        # Sequential: interpolate through all colors
        segment_count = len(colors) - 1
        segment = int(t * segment_count)
        segment = min(segment, segment_count - 1)

        local_t = (t * segment_count) - segment
        return self._interpolate_between(colors[segment], colors[segment + 1], local_t)

    def _interpolate_between(self, color1, color2, t):
        """Linear interpolation between two hex colors."""
        # Parse hex colors
        r1, g1, b1 = self._hex_to_rgb(color1)
        r2, g2, b2 = self._hex_to_rgb(color2)

        # Interpolate
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)

        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _hex_to_rgb(hex_color):
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    def get_discrete_colors(self, count):
        """Get a list of discrete colors for classification.

        Args:
            count: Number of colors needed

        Returns:
            List of hex color strings
        """
        self.ensure_one()
        colors = self.get_colors_list()

        if self.scheme_type == "qualitative":
            # For qualitative, just return colors (cycle if needed)
            if len(colors) >= count:
                return colors[:count]
            return (colors * ((count // len(colors)) + 1))[:count]

        # For sequential/diverging, interpolate
        if count <= 1:
            return [colors[len(colors) // 2]] if colors else ["#808080"]

        return [
            self.interpolate_color(i / (count - 1), 0, 1) for i in range(count)
        ]

    @api.model
    def get_default_scheme(self):
        """Get the default color scheme."""
        scheme = self.search([("is_default", "=", True)], limit=1)
        if not scheme:
            scheme = self.search([("code", "=", "viridis")], limit=1)
        if not scheme:
            scheme = self.search([], limit=1)
        return scheme
