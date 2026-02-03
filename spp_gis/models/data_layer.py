from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Color ramp definitions for choropleth visualization
COLOR_RAMPS = {
    "green_yellow_red": ["#2ecc71", "#f1c40f", "#e74c3c"],
    "red_yellow_green": ["#e74c3c", "#f1c40f", "#2ecc71"],
    "blue_scale": ["#ebf5fb", "#3498db", "#1a5276"],
    "red_scale": ["#fadbd8", "#e74c3c", "#922b21"],
    "purple_scale": ["#f5eef8", "#9b59b6", "#4a235a"],
    "viridis": ["#440154", "#21918c", "#fde725"],
}


class OpenSPPGisDataLayer(models.Model):
    _name = "spp.gis.data.layer"
    _description = "Data Layer"
    _order = "sequence ASC, name"

    geo_repr = fields.Selection(
        [
            ("basic", "Basic"),
            ("choropleth", "Choropleth (Color by Value)"),
        ],
        default="basic",
        string="Representation mode",
        required=True,
    )

    name = fields.Char("Layer Name", translate=True, required=True)
    begin_color = fields.Char("Data Color ", required=False, help="hex value")

    # Choropleth configuration fields
    choropleth_field_id = fields.Many2one(
        "ir.model.fields",
        string="Value Field",
        domain="[('model_id', '=', model_id), ('ttype', 'in', ('integer', 'float', 'monetary'))]",
        help="Numeric field to use for coloring features. Must be a number field on the layer's model.",
    )
    choropleth_color_ramp = fields.Selection(
        [
            ("green_yellow_red", "Green-Yellow-Red"),
            ("red_yellow_green", "Red-Yellow-Green"),
            ("blue_scale", "Blue Scale (Light to Dark)"),
            ("red_scale", "Red Scale (Light to Dark)"),
            ("purple_scale", "Purple Scale (Light to Dark)"),
            ("viridis", "Viridis (Scientific)"),
            ("custom", "Custom (Two Colors)"),
        ],
        default="green_yellow_red",
        string="Color Ramp",
        help="Color gradient for visualizing values",
    )
    choropleth_color_low = fields.Char(
        string="Low Value Color",
        default="#00ff00",
        help="Hex color for minimum values (e.g., #00ff00)",
    )
    choropleth_color_high = fields.Char(
        string="High Value Color",
        default="#ff0000",
        help="Hex color for maximum values (e.g., #ff0000)",
    )
    choropleth_min_value = fields.Float(
        string="Min Value",
        help="Minimum value for color scale. Leave empty to auto-calculate from data.",
    )
    choropleth_max_value = fields.Float(
        string="Max Value",
        help="Maximum value for color scale. Leave empty to auto-calculate from data.",
    )
    choropleth_classification = fields.Selection(
        [
            ("linear", "Linear (Continuous)"),
            ("quantile", "Quantile (Equal Count)"),
            ("manual", "Manual Breaks"),
        ],
        default="linear",
        string="Classification",
        help="How to distribute values across the color scale",
    )
    choropleth_class_count = fields.Integer(
        string="Number of Classes",
        default=5,
        help="Number of color classes for non-linear classification (3-10)",
    )
    choropleth_manual_breaks = fields.Char(
        string="Manual Breaks",
        help="Comma-separated values for manual classification (e.g., '10,50,100,500')",
    )
    choropleth_show_legend = fields.Boolean(
        string="Show Legend",
        default=True,
    )
    choropleth_legend_title = fields.Char(
        string="Legend Title",
        translate=True,
        help="Title displayed above the legend. Defaults to field label if empty.",
    )
    geo_field_id = fields.Many2one(
        "ir.model.fields",
        "Geo field",
        required=True,
        ondelete="cascade",
        domain=[("ttype", "ilike", "geo_")],
    )
    model_id = fields.Many2one(
        "ir.model",
        "Model to use",
        store=True,
        readonly=False,
        compute="_compute_model_id",
    )
    model_name = fields.Char(related="model_id.model", readonly=True)

    view_id = fields.Many2one("ir.ui.view", "Related View", domain=[("type", "=", "gis")], required=True)
    sequence = fields.Integer("Layer Priority", default=6)
    active_on_startup = fields.Boolean(help="Layer will be shown on startup if checked.")
    layer_opacity = fields.Float(default=1.0)
    model_view_id = fields.Many2one(
        "ir.ui.view",
        "Model view",
        domain=[("type", "=", "gis")],
        compute="_compute_model_view_id",
        readonly=False,
    )
    layer_transparent = fields.Boolean()
    domain = fields.Char(
        string="Domain Filter",
        help="Filter records shown in this layer (e.g., [('area_level', '=', 2)])",
    )

    @api.constrains("geo_field_id", "model_id")
    def _check_geo_field_id(self):
        for rec in self:
            if rec.model_id:
                if not rec.geo_field_id.model_id == rec.model_id:
                    raise ValidationError(
                        _(
                            "The geo_field_id must be a field in %s model",
                            rec.model_id.display_name,
                        )
                    )

    @api.depends("model_id")
    def _compute_model_view_id(self):
        for rec in self:
            if rec.model_id:
                for view in rec.model_id.view_ids:
                    if view.type == "gis":
                        rec.model_view_id = view
            else:
                rec.model_view_id = ""

    @api.depends("geo_field_id")
    def _compute_model_id(self):
        """Compute model from geo_field_id.

        Data layers can reference geo fields from any model, enabling
        multi-model maps where a single view displays layers from
        different models (e.g., areas + warehouses + dispatches).
        """
        for rec in self:
            rec.model_id = rec.geo_field_id.model_id if rec.geo_field_id else False

    @api.constrains("geo_repr", "choropleth_field_id")
    def _check_choropleth_config(self):
        """Validate choropleth layers have required configuration."""
        for rec in self:
            if rec.geo_repr == "choropleth" and not rec.choropleth_field_id:
                raise ValidationError(_("Choropleth layers require a Value Field to be specified."))

    def _get_color_ramp_definition(self):
        """Return the color stops for the selected color ramp."""
        self.ensure_one()
        if self.choropleth_color_ramp == "custom":
            return [
                self.choropleth_color_low or "#00ff00",
                self.choropleth_color_high or "#ff0000",
            ]
        return COLOR_RAMPS.get(
            self.choropleth_color_ramp,
            COLOR_RAMPS["green_yellow_red"],
        )

    def _get_choropleth_config(self):
        """Return choropleth configuration dictionary for frontend.

        This is called by get_gis_layers() to pass choropleth settings
        to the JavaScript renderer.
        """
        self.ensure_one()
        if self.geo_repr != "choropleth" or not self.choropleth_field_id:
            return None

        return {
            "field_name": self.choropleth_field_id.name,
            "field_label": self.choropleth_field_id.field_description,
            "color_ramp": self._get_color_ramp_definition(),
            "classification": self.choropleth_classification,
            "class_count": self.choropleth_class_count,
            "manual_breaks": self.choropleth_manual_breaks,
            "min_value": self.choropleth_min_value,
            "max_value": self.choropleth_max_value,
            "show_legend": self.choropleth_show_legend,
            "legend_title": (self.choropleth_legend_title or self.choropleth_field_id.field_description),
        }
