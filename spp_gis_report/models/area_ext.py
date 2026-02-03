import json
import logging

from shapely.geometry import mapping as shapely_mapping
from shapely.geometry.base import BaseGeometry

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Area(models.Model):
    """Extension of spp.area to add GIS report reference data."""

    _inherit = "spp.area"

    # ===== Reference Data for Normalization =====
    population = fields.Integer(
        "Population",
        help="Total population from census or estimate",
    )
    population_date = fields.Date(
        "Population Data Date",
        help="Date of population data",
    )
    population_source = fields.Char(
        "Population Data Source",
        help="Source of population data (e.g., 'National Census 2020')",
    )

    household_count = fields.Integer(
        "Household Count",
        help="Number of households in this area",
    )

    # ===== Registry Counts (Updated via scheduled refresh) =====
    registrant_count = fields.Integer(
        "Registered Individuals",
        readonly=True,
        help="Number of individual registrants in this area. Updated periodically.",
    )
    group_count = fields.Integer(
        "Registered Groups/Households",
        readonly=True,
        help="Number of group/household registrants in this area. Updated periodically.",
    )

    def action_refresh_registry_counts(self):
        """Refresh registry counts for selected areas."""
        self._compute_registry_counts()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Counts Refreshed",
                "message": f"Registry counts updated for {len(self)} area(s).",
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _cron_refresh_registry_counts(self):
        """Cron job to refresh all area registry counts."""
        _logger.info("Starting scheduled refresh of area registry counts")
        areas = self.search([])
        areas._compute_registry_counts()
        _logger.info("Completed refresh of registry counts for %d areas", len(areas))

    def _compute_registry_counts(self):
        """Efficiently compute registry counts using read_group.

        This method aggregates registrant and group counts for each area
        using Odoo's optimized read_group query.
        """
        # Clear all counts first
        for area in self:
            area.registrant_count = 0
            area.group_count = 0

        # Get areas with IDs (skip new records)
        areas_with_ids = self.filtered(lambda a: a.id)
        if not areas_with_ids:
            return

        # Compute individual registrant counts
        individual_counts = self.env["res.partner"].read_group(
            domain=[
                ("area_id", "in", areas_with_ids.ids),
                ("is_registrant", "=", True),
                ("is_group", "=", False),
                ("active", "=", True),
            ],
            fields=["area_id"],
            groupby=["area_id"],
        )

        # Build lookup dict
        individual_count_map = {group["area_id"][0]: group["area_id_count"] for group in individual_counts}

        # Compute group registrant counts
        group_counts = self.env["res.partner"].read_group(
            domain=[
                ("area_id", "in", areas_with_ids.ids),
                ("is_registrant", "=", True),
                ("is_group", "=", True),
                ("active", "=", True),
            ],
            fields=["area_id"],
            groupby=["area_id"],
        )

        # Build lookup dict
        group_count_map = {group["area_id"][0]: group["area_id_count"] for group in group_counts}

        # Assign counts
        for area in areas_with_ids:
            area.registrant_count = individual_count_map.get(area.id, 0)
            area.group_count = group_count_map.get(area.id, 0)

    @api.model
    def get_gis_layers(self, view_id=None, view_type="gis", **options):
        """Override to add report data for report-based layers.

        For layers with source_type='report', we add:
        - geo_repr='choropleth' to enable choropleth rendering
        - choropleth_config with color info from report thresholds
        - report_features: pre-built GeoJSON features with colors
        """
        result = super().get_gis_layers(view_id=view_id, view_type=view_type, **options)

        # Process each data layer to add report data
        for layer_dict in result.get("actives", []):
            if layer_dict.get("source_type") != "report":
                continue

            report_id = layer_dict.get("report_id")
            if not report_id:
                continue

            # Get report record
            report_id_value = report_id[0] if isinstance(report_id, list | tuple) else report_id
            report = self.env["spp.gis.report"].browse(report_id_value)
            if not report.exists():
                continue

            # Set geo_repr to choropleth for report layers
            layer_dict["geo_repr"] = "choropleth"

            # For report layers, we use pre-computed colors from report data
            # so we don't need complex choropleth_config with step expressions.
            # Instead, we'll use a match expression on report_color in JS.
            # Build legend info from thresholds for display purposes only.
            thresholds = report.threshold_ids.sorted("sequence")
            if thresholds:
                layer_dict["report_legend"] = [{"color": t.color, "label": t.label} for t in thresholds]
                layer_dict["report_legend_title"] = report.name

            # Build pre-computed features for report layer
            report_data = self.env["spp.gis.report.data"].search(
                [
                    ("report_id", "=", report.id),
                    ("is_stale", "=", False),
                ]
            )

            features = []
            for data_record in report_data:
                area = data_record.area_id
                if not area or not area.geo_polygon:
                    continue

                # Parse geometry - geo_polygon can be:
                # - Shapely geometry object (from ORM field access)
                # - GeoJSON string (from .read() serialization)
                # - GeoJSON dict
                try:
                    geo_value = area.geo_polygon
                    if isinstance(geo_value, BaseGeometry):
                        # Convert Shapely geometry to GeoJSON dict
                        geometry = shapely_mapping(geo_value)
                    elif isinstance(geo_value, str):
                        geometry = json.loads(geo_value)
                    elif isinstance(geo_value, dict):
                        geometry = geo_value
                    else:
                        _logger.warning("Unexpected geo_polygon type for area %s: %s", area.id, type(geo_value))
                        continue

                    # Validate geometry has required GeoJSON structure
                    if not isinstance(geometry, dict) or "type" not in geometry or "coordinates" not in geometry:
                        _logger.warning("Invalid geometry structure for area %s", area.id)
                        continue

                    # Ensure geometry type is valid for turf.js
                    valid_types = {"Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"}
                    if geometry.get("type") not in valid_types:
                        _logger.warning("Unknown geometry type '%s' for area %s", geometry.get("type"), area.id)
                        continue

                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    _logger.warning("Failed to parse geometry for area %s: %s", area.id, e)
                    continue

                feature = {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "resModel": "spp.area",
                        "resId": area.id,
                        "layerId": layer_dict["id"],
                        "choropleth_value": float(data_record.raw_value or 0),
                        "report_color": data_record.bucket_color,
                        "report_label": data_record.bucket_label,
                    },
                }
                features.append(feature)

            layer_dict["report_features"] = features

        return result
