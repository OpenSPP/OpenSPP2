# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ScopeResolverService(models.AbstractModel):
    """
    Service to resolve aggregation scopes to partner IDs.

    Uses strategy pattern to handle different scope types.
    Each scope type has a dedicated resolver method.
    """

    _name = "spp.aggregation.scope.resolver"
    _description = "Aggregation Scope Resolver"

    @api.model
    def resolve(self, scope):
        """
        Resolve a scope to a list of partner IDs.

        :param scope: spp.aggregation.scope record or dict for inline scope
        :returns: List of partner IDs
        :rtype: list[int]
        """
        if isinstance(scope, dict):
            return self._resolve_inline(scope)

        scope.ensure_one()
        scope_type = scope.scope_type

        resolver_method = getattr(self, f"_resolve_{scope_type}", None)
        if resolver_method is None:
            _logger.error("No resolver for scope type: %s", scope_type)
            return []

        try:
            return resolver_method(scope)
        except Exception as e:
            _logger.error("Error resolving scope %s: %s", scope.name, e)
            return []

    def _resolve_inline(self, scope_dict):
        """
        Resolve an inline scope definition (dict).

        Creates a temporary scope record to leverage existing resolver methods.
        """
        scope_type = scope_dict.get("scope_type")
        if not scope_type:
            _logger.error("Inline scope missing scope_type")
            return []

        # Map inline scope dict to resolver
        resolver_map = {
            "cel": self._resolve_cel_inline,
            "area": self._resolve_area_inline,
            "area_tag": self._resolve_area_tag_inline,
            "spatial_polygon": self._resolve_spatial_polygon_inline,
            "spatial_buffer": self._resolve_spatial_buffer_inline,
            "explicit": self._resolve_explicit_inline,
        }

        resolver = resolver_map.get(scope_type)
        if not resolver:
            _logger.error("No resolver for inline scope type: %s", scope_type)
            return []

        try:
            return resolver(scope_dict)
        except Exception as e:
            _logger.error("Error resolving inline scope: %s", e)
            return []

    # -------------------------------------------------------------------------
    # CEL Resolution
    # -------------------------------------------------------------------------
    def _resolve_cel(self, scope):
        """Resolve a CEL expression scope."""
        return self._resolve_cel_expression(
            scope.cel_expression,
            scope.cel_profile or "registry_individuals",
        )

    def _resolve_cel_inline(self, scope_dict):
        """Resolve an inline CEL scope."""
        return self._resolve_cel_expression(
            scope_dict.get("cel_expression", ""),
            scope_dict.get("cel_profile", "registry_individuals"),
        )

    def _resolve_cel_expression(self, expression, profile):
        """Execute CEL expression and return matching IDs."""
        if not expression:
            return []

        executor = self.env.get("spp.cel.executor")
        if not executor:
            _logger.error("CEL executor not available")
            return []
        executor = executor.sudo()

        all_ids = []
        try:
            for batch_ids in executor.compile_for_batch("res.partner", expression, batch_size=5000):
                all_ids.extend(batch_ids)
        except Exception as e:
            _logger.error("CEL execution failed: %s", e)
            return []

        return all_ids

    # -------------------------------------------------------------------------
    # Area Resolution
    # -------------------------------------------------------------------------
    def _resolve_area(self, scope):
        """Resolve an area scope to partner IDs."""
        area = scope.area_id
        if not area:
            return []

        return self._resolve_area_ids([area.id], scope.include_child_areas)

    def _resolve_area_inline(self, scope_dict):
        """Resolve an inline area scope."""
        area_id = scope_dict.get("area_id")
        if not area_id:
            return []

        include_children = scope_dict.get("include_child_areas", True)
        return self._resolve_area_ids([area_id], include_children)

    def _resolve_area_ids(self, area_ids, include_children=True):
        """Resolve area IDs to partner IDs.

        Returns registrants directly in the given areas, plus individuals
        whose group (household) is in those areas but who lack their own
        area_id assignment.
        """
        if not area_ids:
            return []

        # Build area domain (sudo for model reads - callers may be unprivileged)
        if include_children:
            # Use parent_path for efficient child lookup
            areas = self.env["spp.area"].sudo().browse(area_ids)
            all_area_ids = set(area_ids)
            for area in areas:
                if area.parent_path:
                    # Find all child areas using parent_path prefix
                    children = self.env["spp.area"].sudo().search([("parent_path", "like", f"{area.parent_path}%")])
                    all_area_ids.update(children.ids)
            area_ids = list(all_area_ids)

        # Find registrants directly in these areas
        domain = [
            ("is_registrant", "=", True),
            ("area_id", "in", area_ids),
        ]
        direct_ids = set(self.env["res.partner"].sudo().search(domain).ids)

        # Also find individuals without area_id whose group is in these areas
        Membership = self.env["spp.group.membership"].sudo()
        memberships = Membership.search(
            [
                ("group.area_id", "in", area_ids),
                ("individual.area_id", "=", False),
                ("individual.is_registrant", "=", True),
                ("is_ended", "=", False),
            ]
        )
        indirect_ids = set(memberships.mapped("individual").ids)

        return list(direct_ids | indirect_ids)

    # -------------------------------------------------------------------------
    # Area Tag Resolution
    # -------------------------------------------------------------------------
    def _resolve_area_tag(self, scope):
        """Resolve an area tag scope to partner IDs."""
        tag_ids = scope.area_tag_ids.ids
        if not tag_ids:
            return []

        include_children = scope.include_child_areas
        return self._resolve_area_tag_ids(tag_ids, include_children)

    def _resolve_area_tag_inline(self, scope_dict):
        """Resolve an inline area tag scope."""
        tag_ids = scope_dict.get("area_tag_ids", [])
        if not tag_ids:
            return []

        include_children = scope_dict.get("include_child_areas", True)
        return self._resolve_area_tag_ids(tag_ids, include_children)

    def _resolve_area_tag_ids(self, tag_ids, include_children=True):
        """Resolve area tag IDs to partner IDs."""
        if not tag_ids:
            return []

        # Find areas with these tags (sudo for model reads - callers may be unprivileged)
        areas = self.env["spp.area"].sudo().search([("tag_ids", "in", tag_ids)])
        if not areas:
            return []

        return self._resolve_area_ids(areas.ids, include_children)

    # -------------------------------------------------------------------------
    # Spatial Resolution (basic, full PostGIS in bridge module)
    # -------------------------------------------------------------------------
    def _resolve_spatial_polygon(self, scope):
        """Resolve a spatial polygon scope."""
        geojson = scope.geometry_geojson
        if not geojson:
            return []

        return self._resolve_spatial_polygon_geometry(geojson)

    def _resolve_spatial_polygon_inline(self, scope_dict):
        """Resolve an inline spatial polygon scope."""
        geojson = scope_dict.get("geometry_geojson")
        if not geojson:
            return []

        return self._resolve_spatial_polygon_geometry(geojson)

    def _resolve_spatial_polygon_geometry(self, geojson_str):
        """
        Resolve spatial polygon to partner IDs.

        This is a basic implementation. For full PostGIS support,
        install the spp_aggregation_spatial bridge module.
        """
        # Check if PostGIS bridge is available
        spatial_resolver = self.env.get("spp.aggregation.spatial.resolver")
        if spatial_resolver:
            return spatial_resolver.resolve_polygon(geojson_str)

        # Fallback: no spatial support
        _logger.warning("Spatial polygon scope requires spp_aggregation_spatial module. " "Returning empty result.")
        return []

    def _resolve_spatial_buffer(self, scope):
        """Resolve a spatial buffer scope."""
        return self._resolve_spatial_buffer_params(
            scope.buffer_center_latitude,
            scope.buffer_center_longitude,
            scope.buffer_radius_km,
        )

    def _resolve_spatial_buffer_inline(self, scope_dict):
        """Resolve an inline spatial buffer scope."""
        return self._resolve_spatial_buffer_params(
            scope_dict.get("buffer_center_latitude"),
            scope_dict.get("buffer_center_longitude"),
            scope_dict.get("buffer_radius_km"),
        )

    def _resolve_spatial_buffer_params(self, latitude, longitude, radius_km):
        """
        Resolve spatial buffer to partner IDs.

        This is a basic implementation. For full PostGIS support,
        install the spp_aggregation_spatial bridge module.
        """
        if not all([latitude, longitude, radius_km]):
            return []

        # Check if PostGIS bridge is available
        spatial_resolver = self.env.get("spp.aggregation.spatial.resolver")
        if spatial_resolver:
            return spatial_resolver.resolve_buffer(latitude, longitude, radius_km)

        # Fallback: no spatial support
        _logger.warning("Spatial buffer scope requires spp_aggregation_spatial module. " "Returning empty result.")
        return []

    # -------------------------------------------------------------------------
    # Simulation Resolution (added by spp_simulation module)
    # -------------------------------------------------------------------------
    # Note: _resolve_simulation method is added by spp_simulation when installed

    # -------------------------------------------------------------------------
    # Explicit Resolution
    # -------------------------------------------------------------------------
    def _resolve_explicit(self, scope):
        """Resolve an explicit ID list scope."""
        return scope.explicit_partner_ids.ids

    def _resolve_explicit_inline(self, scope_dict):
        """Resolve an inline explicit scope."""
        partner_ids = scope_dict.get("explicit_partner_ids", [])
        if not partner_ids:
            return []

        # Validate that these are actual registrants (sudo for model reads - callers may be unprivileged)
        valid_ids = (
            self.env["res.partner"]
            .sudo()
            .search(
                [
                    ("id", "in", partner_ids),
                    ("is_registrant", "=", True),
                ]
            )
            .ids
        )

        return valid_ids

    # -------------------------------------------------------------------------
    # Batch Resolution
    # -------------------------------------------------------------------------
    @api.model
    def resolve_multiple(self, scopes):
        """
        Resolve multiple scopes and return combined IDs.

        :param scopes: List of scope records or dicts
        :returns: Combined list of unique partner IDs
        :rtype: list[int]
        """
        all_ids = set()
        for scope in scopes:
            ids = self.resolve(scope)
            all_ids.update(ids)
        return list(all_ids)

    @api.model
    def resolve_intersect(self, scopes):
        """
        Resolve multiple scopes and return intersection of IDs.

        :param scopes: List of scope records or dicts
        :returns: List of partner IDs present in ALL scopes
        :rtype: list[int]
        """
        if not scopes:
            return []

        result_ids = None
        for scope in scopes:
            ids = set(self.resolve(scope))
            if result_ids is None:
                result_ids = ids
            else:
                result_ids = result_ids.intersection(ids)

            # Short-circuit if intersection is empty
            if not result_ids:
                return []

        return list(result_ids) if result_ids else []
