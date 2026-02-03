# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extension of spp.gis.data.layer to support report-driven thematic layers.

This module extends the base GIS data layer model to support:
- Report-driven choropleth/thematic layers
- Multiple geometry types (polygon, point, cluster, heatmap)
- Color scheme integration for thematic mapping
"""

from odoo import api, fields, models


class DataLayerReportExtension(models.Model):
    """Extend data layer to support GIS report as data source."""

    _inherit = "spp.gis.data.layer"

    # ===== Source Type =====
    source_type = fields.Selection(
        [
            ("model", "Model Field"),
            ("report", "GIS Report"),
        ],
        string="Data Source",
        default="model",
        required=True,
        help="Model: Traditional layer from model geo field. "
        "Report: Thematic layer driven by GIS report data.",
    )

    # ===== Report Integration =====
    report_id = fields.Many2one(
        "spp.gis.report",
        string="GIS Report",
        ondelete="cascade",
        help="The GIS report providing data for this layer",
    )
    report_code = fields.Char(
        related="report_id.code",
        string="Report Code",
        store=True,
    )

    # ===== Geometry Type =====
    geometry_type = fields.Selection(
        [
            ("polygon", "Polygon (Choropleth)"),
            ("point", "Point Markers"),
            ("cluster", "Clustered Points"),
            ("heatmap", "Heatmap"),
        ],
        string="Geometry Type",
        default="polygon",
        help="How to visualize the data on the map",
    )

    # ===== Styling =====
    color_scheme_id = fields.Many2one(
        "spp.gis.color.scheme",
        string="Color Scheme",
        help="Color scheme for thematic visualization. "
        "If not set, uses the report's color scheme.",
    )
    fill_opacity = fields.Float(
        string="Fill Opacity",
        default=0.7,
        help="Opacity of polygon fill (0-1)",
    )
    stroke_color = fields.Char(
        string="Stroke Color",
        default="#333333",
        help="Border color for polygons (hex)",
    )
    stroke_width = fields.Float(
        string="Stroke Width",
        default=1.0,
        help="Border width in pixels",
    )

    # ===== Point-specific settings =====
    point_radius = fields.Integer(
        string="Point Radius",
        default=8,
        help="Radius for point markers in pixels",
    )
    cluster_radius = fields.Integer(
        string="Cluster Radius",
        default=50,
        help="Distance in pixels for clustering points",
    )

    # ===== Heatmap-specific settings =====
    heatmap_radius = fields.Integer(
        string="Heatmap Radius",
        default=25,
        help="Radius of influence for each point in pixels",
    )
    heatmap_blur = fields.Integer(
        string="Heatmap Blur",
        default=15,
        help="Amount of blur for the heatmap",
    )
    heatmap_max_intensity = fields.Float(
        string="Max Intensity",
        default=1.0,
        help="Maximum intensity value for the heatmap",
    )

    # ===== Computed =====
    is_report_layer = fields.Boolean(
        compute="_compute_is_report_layer",
        store=True,
        help="Whether this is a report-driven layer",
    )

    @api.depends("source_type")
    def _compute_is_report_layer(self):
        """Compute whether this is a report-driven layer."""
        for layer in self:
            layer.is_report_layer = layer.source_type == "report"

    @api.onchange("source_type")
    def _onchange_source_type(self):
        """Clear irrelevant fields when source type changes."""
        if self.source_type == "report":
            # Clear model-specific fields
            self.geo_field_id = False
        else:
            # Clear report-specific fields
            self.report_id = False

    @api.onchange("report_id")
    def _onchange_report_id(self):
        """Sync settings from report when selected."""
        if self.report_id:
            # Use report's color scheme if not set
            if not self.color_scheme_id and self.report_id.color_scheme_id:
                self.color_scheme_id = self.report_id.color_scheme_id
            # Update layer name to match report
            if not self.name or self.name == "New":
                self.name = self.report_id.name

    def get_effective_color_scheme(self):
        """Get the effective color scheme for this layer.

        Returns the layer's color scheme if set, otherwise falls back
        to the report's color scheme.

        Returns:
            spp.gis.color.scheme record or False
        """
        self.ensure_one()
        if self.color_scheme_id:
            return self.color_scheme_id
        if self.report_id and self.report_id.color_scheme_id:
            return self.report_id.color_scheme_id
        return self.env["spp.gis.color.scheme"].get_default_scheme()

    def get_layer_style(self):
        """Get the complete style configuration for this layer.

        Returns:
            dict: Style configuration for map rendering
        """
        self.ensure_one()
        color_scheme = self.get_effective_color_scheme()

        style = {
            "geometry_type": self.geometry_type,
            "fill_opacity": self.fill_opacity,
            "stroke_color": self.stroke_color,
            "stroke_width": self.stroke_width,
        }

        if color_scheme:
            style["color_scheme"] = {
                "code": color_scheme.code,
                "type": color_scheme.scheme_type,
                "colors": color_scheme.get_colors_list(),
            }

        if self.geometry_type == "point":
            style["point_radius"] = self.point_radius
        elif self.geometry_type == "cluster":
            style["point_radius"] = self.point_radius
            style["cluster_radius"] = self.cluster_radius
        elif self.geometry_type == "heatmap":
            style["heatmap_radius"] = self.heatmap_radius
            style["heatmap_blur"] = self.heatmap_blur
            style["heatmap_max_intensity"] = self.heatmap_max_intensity

        return style
