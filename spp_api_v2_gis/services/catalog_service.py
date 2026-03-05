# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for building catalog from spp.gis.report and spp.gis.data.layer."""

import logging

_logger = logging.getLogger(__name__)


class CatalogService:
    """Service for building GIS catalog."""

    def __init__(self, env):
        """Initialize catalog service."""
        self.env = env

    def get_catalog(self):
        """Build catalog from available reports and data layers.

        Returns:
            dict: Catalog with reports, data_layers, and area_level_names
        """
        reports = self._get_reports()
        data_layers = self._get_data_layers()
        area_level_names = self._get_area_level_names()

        return {
            "reports": reports,
            "data_layers": data_layers,
            "area_level_names": area_level_names,
        }

    def _get_reports(self):
        """Query spp.gis.report for available reports.

        Returns:
            list[dict]: List of report info dictionaries
        """
        Report = self.env["spp.gis.report"].sudo()
        reports = Report.search([("active", "=", True)], order="sequence, name")

        result = []
        for report in reports:
            # Calculate freshness indicator
            freshness = self._get_freshness_indicator(report)

            # Query distinct area levels that have data for this report
            groups = (
                self.env["spp.gis.report.data"]
                .sudo()
                ._read_group(
                    [("report_id", "=", report.id)],
                    groupby=["area_level"],
                    aggregates=[],
                )
            )
            admin_levels_available = sorted([level for (level,) in groups if level is not None])

            report_info = {
                "id": report.code,
                "name": report.name,
                "description": report.description or None,
                "category": report.category_id.name if report.category_id else None,
                "geometry_type": self._normalize_geometry_type(report.geometry_type),
                "area_level": report.base_area_level,
                "last_refresh": report.last_refresh.isoformat() if report.last_refresh else None,
                "freshness": freshness,
                "admin_levels_available": admin_levels_available,
            }
            result.append(report_info)

        _logger.info("Found %d GIS reports for catalog", len(result))
        return result

    def _get_data_layers(self):
        """Query spp.gis.data.layer for available layers.

        Returns:
            list[dict]: List of data layer info dictionaries
        """
        Layer = self.env["spp.gis.data.layer"].sudo()
        layers = Layer.search([], order="sequence, name")

        result = []
        for layer in layers:
            layer_info = {
                "id": str(layer.id),
                "name": layer.name,
                "geometry_type": self._map_geo_repr_to_geometry_type(layer.geo_repr),
                "source_model": layer.model_name or None,
                "source_type": layer.source_type if hasattr(layer, "source_type") else None,
                "report_code": layer.report_id.code if hasattr(layer, "report_id") and layer.report_id else None,
            }
            result.append(layer_info)

        _logger.info("Found %d GIS data layers for catalog", len(result))
        return result

    def _normalize_geometry_type(self, geometry_type):
        """Normalize geometry type to standard GeoJSON types.

        Args:
            geometry_type: Report geometry type (polygon, point, cluster, heatmap)

        Returns:
            str: Normalized geometry type (polygon, point, line)
        """
        geometry_type_map = {
            "polygon": "polygon",
            "point": "point",
            "cluster": "point",  # Clusters are still points
            "heatmap": "point",  # Heatmaps are based on points
        }
        return geometry_type_map.get(geometry_type, "polygon")

    def _map_geo_repr_to_geometry_type(self, geo_repr):
        """Map data layer geo_repr to standard geometry type.

        Args:
            geo_repr: Layer representation mode (basic, choropleth)

        Returns:
            str: Geometry type (polygon, point, line)
        """
        # Data layers use geo_repr for rendering mode, not geometry type
        # Default to polygon as most common for area-based layers
        return "polygon"

    def _get_area_level_names(self):
        """Build mapping from area_level to area type name.

        Queries distinct area levels and their associated type names
        from the area table.

        Returns:
            dict: {area_level: type_name} mapping
        """
        self.env.cr.execute(
            """
            SELECT DISTINCT a.area_level, at.name
            FROM spp_area a
            LEFT JOIN spp_area_type at ON at.id = a.area_type_id
            WHERE a.area_level IS NOT NULL AND at.name IS NOT NULL
            ORDER BY a.area_level
            """
        )
        result = {}
        for level, name in self.env.cr.fetchall():
            if level not in result:
                result[level] = name
        return result

    def _get_freshness_indicator(self, report):
        """Calculate freshness indicator for a report.

        Args:
            report: spp.gis.report record

        Returns:
            str: Freshness indicator (fresh, stale, never_refreshed)
        """
        if not report.last_refresh:
            return "never_refreshed"

        if report.is_stale:
            return "stale"

        return "fresh"
