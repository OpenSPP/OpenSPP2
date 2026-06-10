# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging
from statistics import quantiles

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class GisIndicatorLayer(models.Model):
    """GIS Indicator Layer Configuration.

    Configures how to visualize area-level indicators as choropleth maps.
    Links a CEL variable to a color scale and classification method.
    """

    _name = "spp.gis.indicator.layer"
    _description = "GIS Indicator Layer Configuration"
    _order = "sequence, name"

    name = fields.Char(
        string="Configuration Name",
        required=True,
        help="Descriptive name for this indicator visualization",
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Display order",
    )

    active = fields.Boolean(
        default=True,
        help="Inactive configurations are hidden",
    )

    # ─── What to Visualize ───────────────────────────────────────

    variable_id = fields.Many2one(
        "spp.cel.variable",
        string="Indicator Variable",
        required=True,
        help="CEL variable containing area-level indicator values",
    )

    variable_name = fields.Char(
        related="variable_id.name",
        string="Variable Name",
        store=True,
    )

    period_key = fields.Char(
        string="Period Key",
        default="current",
        help="Period identifier (e.g., '2024-12', 'current')",
    )

    incident_id = fields.Many2one(
        "spp.hazard.incident",
        string="Incident/Disaster",
        help="Filter indicators by specific incident",
    )

    # ─── How to Visualize ───────────────────────────────────────

    color_scale_id = fields.Many2one(
        "spp.gis.color.scale",
        string="Color Scale",
        required=True,
        help="Color scheme for mapping values to colors",
    )

    classification_method = fields.Selection(
        [
            ("quantile", "Quantile (Equal count per class)"),
            ("equal_interval", "Equal Interval (Equal range per class)"),
            ("manual", "Manual Breaks"),
        ],
        default="quantile",
        required=True,
        help="Method for classifying continuous values into discrete color classes",
    )

    num_classes = fields.Integer(
        string="Number of Classes",
        default=5,
        help="Number of color classes for quantile/equal_interval methods",
    )

    manual_breaks = fields.Char(
        string="Manual Break Points",
        help="Comma-separated break values for manual classification (e.g., '10,50,100,500')",
    )

    # ─── Computed Fields ───────────────────────────────────────

    break_values = fields.Text(
        string="Computed Breaks",
        compute="_compute_break_values",
        help="Computed break values for the legend",
    )

    legend_html = fields.Html(
        string="Legend HTML",
        compute="_compute_legend_html",
        help="HTML representation of the legend for display",
    )

    @api.constrains("num_classes")
    def _check_num_classes(self):
        """Validate number of classes."""
        for rec in self:
            if rec.num_classes < 2:
                raise ValidationError(_("Number of classes must be at least 2"))
            if rec.num_classes > 10:
                raise ValidationError(_("Number of classes must not exceed 10"))

    @api.constrains("manual_breaks", "classification_method")
    def _check_manual_breaks(self):
        """Validate manual break points."""
        for rec in self:
            if rec.classification_method == "manual" and not rec.manual_breaks:
                raise ValidationError(_("Manual breaks are required when using manual classification"))

            if rec.manual_breaks:
                try:
                    # Parse without sorting to validate user input order
                    breaks = self._parse_manual_breaks(rec.manual_breaks, sort=False)
                    if len(breaks) < 1:
                        raise ValidationError(_("Manual breaks must contain at least one value"))
                    # Check that breaks are in ascending order
                    if breaks != sorted(breaks):
                        raise ValidationError(_("Manual breaks must be in ascending order"))
                except ValueError as e:
                    raise ValidationError(_("Invalid manual breaks format: %s", str(e))) from e

    @staticmethod
    def _parse_manual_breaks(breaks_str, sort=True):
        """Parse comma-separated break values.

        Args:
            breaks_str: String of comma-separated numbers
            sort: Whether to sort the result (default True)

        Returns:
            list: List of float values (sorted if sort=True)

        Raises:
            ValueError: If parsing fails
        """
        if not breaks_str:
            return []
        values = [float(x.strip()) for x in breaks_str.split(",")]
        return sorted(values) if sort else values

    @api.depends("variable_id", "period_key", "incident_id", "classification_method", "num_classes", "manual_breaks")
    def _compute_break_values(self):
        """Compute break values based on actual data."""
        for rec in self:
            if not rec.variable_id:
                rec.break_values = ""
                continue

            try:
                # Get all indicator values for this configuration
                values = rec._get_indicator_values()

                # Compute breaks based on classification method
                # Manual breaks don't depend on indicator data
                if rec.classification_method == "manual":
                    breaks = rec._parse_manual_breaks(rec.manual_breaks)
                elif not values:
                    rec.break_values = ""
                    continue
                elif rec.classification_method == "quantile":
                    breaks = rec._compute_quantile_breaks(values, rec.num_classes)
                elif rec.classification_method == "equal_interval":
                    breaks = rec._compute_equal_interval_breaks(values, rec.num_classes)
                else:
                    breaks = []

                rec.break_values = json.dumps(breaks)

            except Exception as e:
                _logger.warning(
                    "Failed to compute break values for indicator layer %s: %s",
                    rec.id,
                    str(e),
                )
                rec.break_values = ""

    @api.depends("break_values", "color_scale_id")
    def _compute_legend_html(self):
        """Generate HTML legend based on breaks and colors."""
        for rec in self:
            if not rec.break_values or not rec.color_scale_id:
                rec.legend_html = ""
                continue

            try:
                breaks = json.loads(rec.break_values)
                colors = rec.color_scale_id.get_colors()

                if not breaks or not colors:
                    rec.legend_html = ""
                    continue

                # Generate legend HTML
                html_parts = ['<div class="gis-choropleth-legend">']

                # Number of classes is breaks + 1
                num_classes = len(breaks) + 1
                num_colors = len(colors)

                for i in range(num_classes):
                    # Get color for this class
                    color_idx = int((i / max(num_classes - 1, 1)) * (num_colors - 1))
                    color = colors[color_idx]

                    # Get range label
                    if i == 0:
                        label = f"< {breaks[0]:.2f}"
                    elif i == num_classes - 1:
                        label = f"≥ {breaks[-1]:.2f}"
                    else:
                        label = f"{breaks[i - 1]:.2f} - {breaks[i]:.2f}"

                    html_parts.append(
                        f'<div class="legend-item">'
                        f'<span class="color-box" style="background-color: {color};"></span>'
                        f'<span class="label">{label}</span>'
                        f"</div>"
                    )

                html_parts.append("</div>")
                rec.legend_html = "\n".join(html_parts)

            except Exception as e:
                _logger.warning(
                    "Failed to compute legend HTML for indicator layer %s: %s",
                    rec.id,
                    str(e),
                )
                rec.legend_html = ""

    def _get_indicator_values(self):
        """Get area-level indicator values for this layer's variable/period/incident.

        Returns:
            list: List of float values

        TODO(remove-hxl): The area-indicator data source (spp.hxl.area.indicator,
        formerly provided by spp_hxl_area) has been removed. Until a replacement
        source is wired in, no indicator data is available and this returns an empty
        list, which disables indicator-driven break and color computation. See
        internal plan remove-hxl-modules.md.
        """
        self.ensure_one()
        return []

    @staticmethod
    def _compute_quantile_breaks(values, num_classes):
        """Compute quantile breaks for equal-count classification.

        Args:
            values: List of numeric values
            num_classes: Number of classes

        Returns:
            list: Break points
        """
        if not values or num_classes < 2:
            return []

        # Remove duplicates and sort
        unique_values = sorted(set(values))

        if len(unique_values) < num_classes:
            # Not enough unique values for requested classes
            return unique_values[:-1]  # Use all but last as breaks

        # Compute quantiles
        # quantiles(data, n=4) gives 3 cut points for 4 groups (quartiles)
        # We want n-1 cut points for n classes
        try:
            breaks = quantiles(values, n=num_classes)
            # quantiles returns n-1 values, which is what we want
            return breaks
        except Exception as e:
            _logger.warning("Failed to compute quantiles: %s", str(e))
            return []

    @staticmethod
    def _compute_equal_interval_breaks(values, num_classes):
        """Compute equal interval breaks.

        Args:
            values: List of numeric values
            num_classes: Number of classes

        Returns:
            list: Break points
        """
        if not values or num_classes < 2:
            return []

        min_val = min(values)
        max_val = max(values)

        if min_val == max_val:
            return []

        # Compute interval size
        interval = (max_val - min_val) / num_classes

        # Generate breaks
        breaks = [min_val + (i * interval) for i in range(1, num_classes)]

        return breaks

    def get_feature_colors(self, area_ids):
        """Return dict mapping area_id to hex color based on indicator values.

        Args:
            area_ids: List of area IDs to get colors for

        Returns:
            dict: Mapping of area_id (int) to color (str)

        TODO(remove-hxl): The area-indicator data source (spp.hxl.area.indicator,
        formerly provided by spp_hxl_area) has been removed. Until a replacement
        source is wired in, there is no per-area indicator data to colorize, so this
        returns an empty mapping. See internal plan remove-hxl-modules.md.
        """
        self.ensure_one()
        return {}
