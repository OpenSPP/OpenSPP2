# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AggregationScope(models.Model):
    """
    Unified targeting scope for aggregation queries.

    Defines WHAT to aggregate by resolving to a set of registrant IDs.
    Supports multiple scope types:
    - CEL expressions
    - Spatial polygons/buffers (requires spp_spatial bridge)
    - Administrative areas
    - Simulation results
    - Explicit ID lists
    """

    _name = "spp.analytics.scope"
    _description = "Aggregation Scope"
    _order = "name"

    name = fields.Char(
        required=True,
        index=True,
        help="Human-readable name for this scope.",
    )
    description = fields.Text(
        help="Optional description of what this scope targets.",
    )
    active = fields.Boolean(
        default=True,
        index=True,
    )

    scope_type = fields.Selection(
        selection=[
            ("cel", "CEL Expression"),
            ("spatial_polygon", "Within Polygon"),
            ("spatial_buffer", "Within Distance"),
            ("area", "Administrative Area"),
            ("area_tag", "Area Tags"),
            ("explicit", "Explicit IDs"),
            # ("simulation", "Simulation Result") - added by spp_simulation
        ],
        required=True,
        default="cel",
        help="How to determine which registrants are in scope.",
    )

    # -------------------------------------------------------------------------
    # CEL targeting
    # -------------------------------------------------------------------------
    cel_expression = fields.Text(
        string="CEL Expression",
        help="CEL expression to filter registrants (e.g., 'r.age >= 18 && r.gender_id.code == \"M\"').",
    )
    cel_profile = fields.Selection(
        selection=[
            ("registry_individuals", "Individuals"),
            ("registry_groups", "Groups/Households"),
        ],
        default="registry_individuals",
        help="CEL profile determines base domain and available fields.",
    )

    # -------------------------------------------------------------------------
    # Spatial targeting (basic storage, PostGIS via bridge module)
    # -------------------------------------------------------------------------
    geometry_geojson = fields.Text(
        string="Geometry (GeoJSON)",
        help="GeoJSON polygon for spatial_polygon scope type.",
    )
    buffer_center_latitude = fields.Float(
        string="Center Latitude",
        digits=(10, 7),
        help="Latitude of buffer center for spatial_buffer scope type.",
    )
    buffer_center_longitude = fields.Float(
        string="Center Longitude",
        digits=(10, 7),
        help="Longitude of buffer center for spatial_buffer scope type.",
    )
    buffer_radius_km = fields.Float(
        string="Buffer Radius (km)",
        digits=(10, 3),
        help="Radius in kilometers for spatial_buffer scope type.",
    )

    # -------------------------------------------------------------------------
    # Area targeting
    # -------------------------------------------------------------------------
    area_id = fields.Many2one(
        comodel_name="spp.area",
        string="Area",
        ondelete="restrict",
        help="Administrative area for area scope type.",
    )
    area_tag_ids = fields.Many2many(
        comodel_name="spp.area.tag",
        relation="spp_aggregation_scope_area_tag_rel",
        column1="scope_id",
        column2="tag_id",
        string="Area Tags",
        help="Areas with these tags for area_tag scope type.",
    )
    include_child_areas = fields.Boolean(
        default=True,
        help="Include registrants in child areas when using area scope.",
    )

    # -------------------------------------------------------------------------
    # Simulation targeting (extended by spp_simulation if installed)
    # -------------------------------------------------------------------------
    # Note: simulation_run_id field is added by spp_simulation module
    # when it extends this model

    # -------------------------------------------------------------------------
    # Explicit ID targeting
    # -------------------------------------------------------------------------
    explicit_partner_ids = fields.Many2many(
        comodel_name="res.partner",
        relation="spp_aggregation_scope_partner_rel",
        column1="scope_id",
        column2="partner_id",
        string="Explicit Registrants",
        domain="[('is_registrant', '=', True)]",
        help="Explicit list of registrants for explicit scope type.",
    )

    # -------------------------------------------------------------------------
    # Cache configuration
    # -------------------------------------------------------------------------
    is_cache_enabled = fields.Boolean(
        string="Enable Caching",
        default=True,
        help="Enable result caching for this scope. Disable for scopes that change frequently.",
    )
    cache_ttl = fields.Integer(
        string="Cache TTL (seconds)",
        default=0,
        help="Custom cache TTL in seconds. 0 means use default system TTL.",
    )
    last_cache_refresh = fields.Datetime(
        string="Last Cache Refresh",
        readonly=True,
        help="Timestamp of last cache refresh for this scope.",
    )

    # -------------------------------------------------------------------------
    # Computed fields
    # -------------------------------------------------------------------------
    registrant_count = fields.Integer(
        compute="_compute_registrant_count",
        string="Registrant Count",
        help="Approximate count of registrants in scope (may be cached).",
    )

    @api.depends("scope_type", "cel_expression", "area_id", "area_tag_ids", "explicit_partner_ids")
    def _compute_registrant_count(self):
        """Compute approximate registrant count for display."""
        for scope in self:
            if scope.scope_type == "explicit":
                scope.registrant_count = len(scope.explicit_partner_ids)
            else:
                # For other types, resolve and count
                try:
                    ids = self.env["spp.analytics.scope.resolver"].resolve(scope)
                    scope.registrant_count = len(ids)
                except (ValidationError, UserError) as e:
                    _logger.debug("Could not compute registrant count for scope %s: %s", scope.id, e)
                    scope.registrant_count = 0

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------
    @api.constrains("scope_type", "cel_expression")
    def _check_cel_expression(self):
        """Validate CEL expression is provided for CEL scope type."""
        for scope in self:
            if scope.scope_type == "cel" and not scope.cel_expression:
                raise ValidationError(_("CEL expression is required for CEL scope type."))

    @api.constrains("scope_type", "geometry_geojson")
    def _check_spatial_polygon(self):
        """Validate GeoJSON is provided and valid for spatial_polygon scope type."""
        for scope in self:
            if scope.scope_type == "spatial_polygon":
                if not scope.geometry_geojson:
                    raise ValidationError(_("GeoJSON geometry is required for spatial polygon scope type."))
                try:
                    geojson = json.loads(scope.geometry_geojson)
                    valid_types = ("Polygon", "MultiPolygon", "Feature", "FeatureCollection")
                    if geojson.get("type") not in valid_types:
                        message = _("GeoJSON must be a Polygon, MultiPolygon, Feature, or FeatureCollection.")
                        raise ValidationError(message)
                except json.JSONDecodeError as e:
                    raise ValidationError(_("Invalid GeoJSON: %s") % str(e)) from e

    @api.constrains("scope_type", "buffer_center_latitude", "buffer_center_longitude", "buffer_radius_km")
    def _check_spatial_buffer(self):
        """Validate buffer parameters for spatial_buffer scope type."""
        for scope in self:
            if scope.scope_type == "spatial_buffer":
                if not scope.buffer_radius_km or scope.buffer_radius_km <= 0:
                    raise ValidationError(_("Buffer radius must be a positive number."))
                if not scope.buffer_center_latitude or not scope.buffer_center_longitude:
                    raise ValidationError(_("Buffer center coordinates are required."))
                if not -90 <= scope.buffer_center_latitude <= 90:
                    raise ValidationError(_("Latitude must be between -90 and 90."))
                if not -180 <= scope.buffer_center_longitude <= 180:
                    raise ValidationError(_("Longitude must be between -180 and 180."))

    @api.constrains("scope_type", "area_id")
    def _check_area(self):
        """Validate area is provided for area scope type."""
        for scope in self:
            if scope.scope_type == "area" and not scope.area_id:
                raise ValidationError(_("Area is required for area scope type."))

    @api.constrains("scope_type", "area_tag_ids")
    def _check_area_tags(self):
        """Validate area tags are provided for area_tag scope type."""
        for scope in self:
            if scope.scope_type == "area_tag" and not scope.area_tag_ids:
                raise ValidationError(_("At least one area tag is required for area tag scope type."))

    # Note: _check_simulation_run constraint is added by spp_simulation module

    @api.constrains("scope_type", "explicit_partner_ids")
    def _check_explicit_ids(self):
        """Validate explicit IDs are provided for explicit scope type."""
        for scope in self:
            if scope.scope_type == "explicit" and not scope.explicit_partner_ids:
                raise ValidationError(_("At least one registrant is required for explicit scope type."))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def resolve_registrant_ids(self):
        """
        Resolve this scope to a list of partner IDs.

        This is the core unification method - all scope types resolve
        to a list of res.partner IDs.

        :returns: List of partner IDs
        :rtype: list[int]
        """
        self.ensure_one()
        return self.env["spp.analytics.scope.resolver"].resolve(self)

    def action_preview_registrants(self):
        """Action to preview registrants in this scope."""
        self.ensure_one()
        ids = self.resolve_registrant_ids()
        return {
            "name": _("Registrants in Scope: %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("id", "in", ids)],
            "context": {"create": False, "delete": False},
        }

    def action_refresh_cache(self):
        """
        Manually invalidate all cache entries for this scope.

        Invalidates all cache entries for this scope's type and
        updates the last_cache_refresh timestamp.
        """
        self.ensure_one()
        cache_service = self.env["spp.analytics.cache"]
        count = cache_service.invalidate_scope(self)
        if count:
            scope_name = self.name
            _logger.info("Invalidated %d cache entries for scope %s", count, scope_name)

        self.write({"last_cache_refresh": fields.Datetime.now()})
        return True
