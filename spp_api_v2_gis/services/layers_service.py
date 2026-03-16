# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for retrieving GIS layer data as GeoJSON."""

import copy
import json
import logging
import threading
import time

from odoo.exceptions import MissingError

_logger = logging.getLogger(__name__)

# Thread-safe TTL cache for report GeoJSON.
# Key: (report_code, admin_level)
# Value: {"data": <geojson_dict>, "timestamp": <float>}
_report_geojson_cache = {}
_report_cache_lock = threading.Lock()
_REPORT_CACHE_TTL = 60  # seconds


class LayersService:
    """Service for retrieving GIS layer data."""

    def __init__(self, env):
        """Initialize layers service."""
        self.env = env

    def get_layer_geojson(
        self,
        layer_id,
        layer_type="report",
        admin_level=None,
        area_codes=None,
        parent_area_code=None,
        include_geometry=True,
        include_disaggregation=False,
        limit=None,
        offset=0,
        bbox=None,
    ):
        """Get layer data as GeoJSON FeatureCollection.

        Args:
            layer_id: Layer identifier (report code or layer database ID)
            layer_type: Type of layer - "report" or "layer"
            admin_level: Filter to specific admin level (optional)
            area_codes: List of area codes to filter (optional)
            parent_area_code: Parent area code to filter children (optional)
            include_geometry: Include polygon geometry (default: True)
            include_disaggregation: Include disaggregation data (default: False)
            limit: Maximum number of features to return (optional)
            offset: Number of features to skip (default: 0)
            bbox: Bounding box filter [west, south, east, north] (optional)

        Returns:
            dict: GeoJSON FeatureCollection with styling hints

        Raises:
            MissingError: If layer not found
            ValueError: If layer_type is invalid
        """
        if layer_type == "report":
            return self._get_report_geojson(
                layer_id,
                admin_level=admin_level,
                area_codes=area_codes,
                parent_area_code=parent_area_code,
                include_geometry=include_geometry,
                include_disaggregation=include_disaggregation,
                bbox=bbox,
            )
        elif layer_type == "layer":
            return self._get_data_layer_geojson(
                layer_id,
                include_geometry=include_geometry,
                limit=limit,
                offset=offset,
                bbox=bbox,
            )
        else:
            raise ValueError(f"Invalid layer_type: {layer_type}. Must be 'report' or 'layer'")

    def _get_report_geojson(
        self,
        report_code,
        admin_level=None,
        area_codes=None,
        parent_area_code=None,
        include_geometry=True,
        include_disaggregation=False,
        bbox=None,
    ):
        """Get GIS report data as GeoJSON.

        For the common OAPIF path (no area_codes, no parent_area_code, default
        geometry and disaggregation settings), the full report GeoJSON is cached
        in memory with a short TTL. Bbox filtering is then applied in Python on
        the cached data, avoiding repeated expensive report generation when QGIS
        sends parallel tiled requests.

        Args:
            report_code: Report code (external identifier)
            admin_level: Filter to specific admin level
            area_codes: List of area codes to filter
            parent_area_code: Parent area code to filter children
            include_geometry: Include polygon geometry
            include_disaggregation: Include disaggregation data
            bbox: Bounding box filter [west, south, east, north] (optional)

        Returns:
            dict: GeoJSON FeatureCollection with styling hints
        """
        # Fast path: common OAPIF requests (no area/parent filters, default settings)
        # can use cached report GeoJSON with Python-level bbox filtering.
        is_cacheable = not area_codes and not parent_area_code and include_geometry and not include_disaggregation

        if is_cacheable:
            return self._get_report_geojson_cached(report_code, admin_level, bbox)

        # Slow path: custom filters bypass cache
        return self._get_report_geojson_uncached(
            report_code,
            admin_level,
            area_codes,
            parent_area_code,
            include_geometry,
            include_disaggregation,
            bbox,
        )

    def _get_report_geojson_cached(self, report_code, admin_level, bbox):
        """Get report GeoJSON using cache, with Python bbox filtering.

        Args:
            report_code: Report code
            admin_level: Admin level filter
            bbox: Bounding box [west, south, east, north] or None

        Returns:
            dict: GeoJSON FeatureCollection (deep-copied from cache)
        """
        cache_key = (report_code, admin_level)

        # Check cache
        with _report_cache_lock:
            entry = _report_geojson_cache.get(cache_key)
            if entry and (time.time() - entry["timestamp"]) < _REPORT_CACHE_TTL:
                geojson = copy.deepcopy(entry["data"])
                _logger.debug("Cache hit for report %s admin_level=%s", report_code, admin_level)
                if bbox:
                    geojson["features"] = filter_features_by_bbox(geojson.get("features", []), bbox)
                return geojson

        # Cache miss — generate full GeoJSON (no bbox filter at DB level)
        geojson = self._get_report_geojson_uncached(
            report_code,
            admin_level,
            area_codes=None,
            parent_area_code=None,
            include_geometry=True,
            include_disaggregation=False,
            bbox=None,
        )

        # Store in cache
        with _report_cache_lock:
            _report_geojson_cache[cache_key] = {
                "data": copy.deepcopy(geojson),
                "timestamp": time.time(),
            }

        # Apply bbox filtering in Python on the result
        if bbox:
            geojson["features"] = filter_features_by_bbox(geojson.get("features", []), bbox)

        return geojson

    def _get_report_geojson_uncached(
        self,
        report_code,
        admin_level=None,
        area_codes=None,
        parent_area_code=None,
        include_geometry=True,
        include_disaggregation=False,
        bbox=None,
    ):
        """Generate report GeoJSON without caching.

        Args:
            report_code: Report code (external identifier)
            admin_level: Filter to specific admin level
            area_codes: List of area codes to filter
            parent_area_code: Parent area code to filter children
            include_geometry: Include polygon geometry
            include_disaggregation: Include disaggregation data
            bbox: Bounding box filter [west, south, east, north] (optional)

        Returns:
            dict: GeoJSON FeatureCollection with styling hints
        """
        # nosemgrep: odoo-sudo-without-context
        Report = self.env["spp.gis.report"].sudo()
        report = Report.search([("code", "=", report_code)], limit=1)

        if not report:
            raise MissingError(f"Report not found: {report_code}")

        # Resolve area codes to IDs
        area_ids = self._resolve_area_codes(area_codes) if area_codes else None

        # Resolve parent area code
        parent_area_id = None
        if parent_area_code:
            # nosemgrep: odoo-sudo-without-context
            parent_area = self.env["spp.area"].sudo().search([("code", "=", parent_area_code)], limit=1)
            parent_area_id = parent_area.id if parent_area else None

        # Apply bbox spatial filter via PostGIS ST_Intersects
        if bbox:
            bbox_geojson = self._bbox_to_geojson(bbox)
            # nosemgrep: odoo-sudo-without-context
            matching_areas = self.env["spp.area"].sudo().search([("geo_polygon", "gis_intersects", bbox_geojson)])
            if area_ids:
                area_ids = list(set(area_ids) & set(matching_areas.ids))
            else:
                area_ids = matching_areas.ids

        # Get GeoJSON from report
        geojson = report._to_geojson(
            admin_level=admin_level,
            area_ids=area_ids,
            parent_area_id=parent_area_id,
            include_geometry=include_geometry,
            include_disaggregation=include_disaggregation,
        )

        # Add styling hints to metadata
        styling = self._build_report_styling(report)
        if "metadata" not in geojson:
            geojson["metadata"] = {}
        geojson["metadata"]["styling"] = styling

        # Also add styling at root level for convenience
        geojson["styling"] = styling

        _logger.info("Generated GeoJSON for report: %s with %d features", report_code, len(geojson.get("features", [])))

        return geojson

    def _get_data_layer_geojson(self, layer_id, include_geometry=True, limit=None, offset=0, bbox=None):
        """Get data layer features as GeoJSON.

        Args:
            layer_id: Layer database ID
            include_geometry: Include polygon geometry
            limit: Maximum features to return (optional)
            offset: Number of features to skip (default: 0)
            bbox: Bounding box filter [west, south, east, north] (optional)

        Returns:
            dict: GeoJSON FeatureCollection with styling hints
        """
        try:
            layer_id_int = int(layer_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid layer_id: {layer_id}") from e

        # nosemgrep: odoo-sudo-without-context
        Layer = self.env["spp.gis.data.layer"].sudo()
        layer = Layer.browse(layer_id_int)

        if not layer.exists():
            raise MissingError(f"Layer not found: {layer_id}")

        # If this is a report-driven layer, delegate to report handler
        if hasattr(layer, "source_type") and layer.source_type == "report":
            if layer.report_id:
                return self._get_report_geojson(
                    layer.report_id.code,
                    include_geometry=include_geometry,
                    bbox=bbox,
                )
            raise MissingError(f"Layer {layer_id} is report-driven but has no report configured")

        # For model-driven layers, fetch features from the source model
        features = self._fetch_layer_features(layer, include_geometry, limit=limit, offset=offset, bbox=bbox)

        # Build styling hints
        styling = self._build_layer_styling(layer)

        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "layer": {
                    "id": layer.id,
                    "name": layer.name,
                    "model": layer.model_name,
                },
                "styling": styling,
            },
            "styling": styling,
        }

        _logger.info("Generated GeoJSON for layer: %s with %d features", layer.id, len(features))

        return geojson

    def _fetch_layer_features(self, layer, include_geometry, limit=None, offset=0, bbox=None):
        """Fetch features from a model-driven layer.

        Args:
            layer: spp.gis.data.layer record
            include_geometry: Include geometry in features
            limit: Maximum records to return (default: 5000 safety limit)
            offset: Number of records to skip (default: 0)
            bbox: Bounding box filter [west, south, east, north] (optional)

        Returns:
            list: List of GeoJSON features
        """
        if not layer.model_name or not layer.geo_field_id:
            _logger.warning("Layer %s has no model or geo field configured", layer.id)
            return []

        # nosemgrep: odoo-sudo-without-context
        Model = self.env[layer.model_name].sudo()

        # Build domain
        domain = []
        if layer.domain:
            try:
                from ast import literal_eval

                domain = literal_eval(layer.domain)
            except (ValueError, SyntaxError) as e:
                _logger.warning("Invalid domain on layer %s: %s", layer.id, e)

        # Apply bbox spatial filter via PostGIS ST_Intersects
        if bbox:
            geo_field_name = layer.geo_field_id.name
            bbox_geojson = self._bbox_to_geojson(bbox)
            domain.append((geo_field_name, "gis_intersects", bbox_geojson))

        # Apply safety limit if none specified
        search_limit = min(limit, 5000) if limit else 5000

        # Search for records with pagination pushed to database
        records = Model.search(domain, limit=search_limit, offset=offset)

        features = []
        geo_field_name = layer.geo_field_id.name

        for record in records:
            # Build properties
            properties = {
                "id": record.id,
                "name": record.display_name,
            }

            # Add choropleth value if configured
            if hasattr(layer, "choropleth_field_id") and layer.choropleth_field_id:
                field_name = layer.choropleth_field_id.name
                if hasattr(record, field_name):
                    properties["value"] = getattr(record, field_name)

            # Build feature
            feature = {
                "type": "Feature",
                "id": record.id,
                "properties": properties,
                "geometry": None,
            }

            # Add geometry if requested
            if include_geometry and hasattr(record, geo_field_name):
                geo_value = getattr(record, geo_field_name)
                if geo_value:
                    try:
                        # GeoField returns Shapely geometry objects
                        if hasattr(geo_value, "__geo_interface__"):
                            feature["geometry"] = geo_value.__geo_interface__
                        else:
                            # Fallback for string values (GeoJSON or WKT)
                            try:
                                feature["geometry"] = json.loads(geo_value)
                            except (json.JSONDecodeError, TypeError):
                                from shapely import wkt

                                shape = wkt.loads(geo_value)
                                feature["geometry"] = shape.__geo_interface__
                    except Exception as e:
                        _logger.warning("Failed to parse geometry: %s", e)

            features.append(feature)

        return features

    def get_feature_count(self, layer_id, layer_type="report", admin_level=None):
        """Get total feature count without loading data.

        Args:
            layer_id: Layer identifier (report code or layer database ID)
            layer_type: Type of layer - "report" or "layer"
            admin_level: Filter to specific admin level (optional, reports only)

        Returns:
            int: Total number of features

        Raises:
            MissingError: If layer not found
        """
        if layer_type == "report":
            # nosemgrep: odoo-sudo-without-context
            report = self.env["spp.gis.report"].sudo().search([("code", "=", layer_id)], limit=1)
            if not report:
                raise MissingError(f"Report not found: {layer_id}")
            domain = [("report_id", "=", report.id)]
            if admin_level is not None:
                domain.append(("area_level", "=", admin_level))
            # nosemgrep: odoo-sudo-without-context
            return self.env["spp.gis.report.data"].sudo().search_count(domain)
        elif layer_type == "layer":
            try:
                layer_id_int = int(layer_id)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid layer_id: {layer_id}") from e

            # nosemgrep: odoo-sudo-without-context
            layer = self.env["spp.gis.data.layer"].sudo().browse(layer_id_int)
            if not layer.exists():
                raise MissingError(f"Layer not found: {layer_id}")

            # nosemgrep: odoo-sudo-without-context
            Model = self.env[layer.model_name].sudo()
            domain = []
            if layer.domain:
                try:
                    from ast import literal_eval

                    domain = literal_eval(layer.domain)
                except (ValueError, SyntaxError):
                    pass
            return Model.search_count(domain)
        else:
            raise ValueError(f"Invalid layer_type: {layer_type}")

    def get_feature_by_id(self, layer_id, feature_id, layer_type="report"):
        """Get a single feature by ID without loading the full collection.

        Args:
            layer_id: Layer identifier (report code or layer database ID)
            feature_id: Feature identifier (area_code for reports, record ID for layers)
            layer_type: Type of layer - "report" or "layer"

        Returns:
            dict: GeoJSON Feature

        Raises:
            MissingError: If layer or feature not found
        """
        if layer_type == "report":
            return self._get_report_feature_by_id(layer_id, feature_id)
        elif layer_type == "layer":
            return self._get_layer_feature_by_id(layer_id, feature_id)
        else:
            raise ValueError(f"Invalid layer_type: {layer_type}")

    def _get_report_feature_by_id(self, report_code, feature_id):
        """Get a single report feature by area_code.

        Args:
            report_code: Report code
            feature_id: Area code (used as feature ID in report GeoJSON)

        Returns:
            dict: GeoJSON Feature

        Raises:
            MissingError: If report or feature not found
        """
        # nosemgrep: odoo-sudo-without-context
        report = self.env["spp.gis.report"].sudo().search([("code", "=", report_code)], limit=1)
        if not report:
            raise MissingError(f"Report not found: {report_code}")

        data = (
            # nosemgrep: odoo-sudo-without-context
            self.env["spp.gis.report.data"]
            .sudo()
            .search(
                [("report_id", "=", report.id), ("area_code", "=", str(feature_id))],
                limit=1,
            )
        )
        if not data:
            raise MissingError(f"Feature {feature_id} not found in report {report_code}")

        # Build properties
        has_data = data.raw_value is not None
        properties = {
            "area_id": data.area_id.id,
            "area_code": data.area_code,
            "area_name": data.area_name,
            "area_level": data.area_level,
            "has_data": has_data,
            "raw_value": data.raw_value,
            "normalized_value": data.normalized_value,
            "display_value": data.display_value if has_data else "No Data",
            "record_count": data.record_count,
        }

        # Build geometry
        geometry = None
        if data.area_id.geo_polygon:
            try:
                geo = data.area_id.geo_polygon
                # GeoPolygonField may return a Shapely geometry object
                # or a WKT/WKB string depending on the spp_gis version.
                if hasattr(geo, "__geo_interface__"):
                    geometry = geo.__geo_interface__
                else:
                    from shapely import wkt

                    shape = wkt.loads(geo)
                    geometry = shape.__geo_interface__
            except (ImportError, Exception) as e:
                _logger.warning("Failed to parse geometry for area %s: %s", data.area_code, e)

        return {
            "type": "Feature",
            "id": data.area_code,
            "properties": properties,
            "geometry": geometry,
        }

    def _get_layer_feature_by_id(self, layer_id, feature_id):
        """Get a single data layer feature by record ID.

        Args:
            layer_id: Layer database ID
            feature_id: Record ID in the source model

        Returns:
            dict: GeoJSON Feature

        Raises:
            MissingError: If layer or feature not found
        """
        try:
            layer_id_int = int(layer_id)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid layer_id: {layer_id}") from e

        # nosemgrep: odoo-sudo-without-context
        layer = self.env["spp.gis.data.layer"].sudo().browse(layer_id_int)
        if not layer.exists():
            raise MissingError(f"Layer not found: {layer_id}")

        try:
            feature_id_int = int(feature_id)
        except (ValueError, TypeError) as e:
            raise MissingError(f"Feature {feature_id} not found in layer {layer_id}") from e

        # nosemgrep: odoo-sudo-without-context
        Model = self.env[layer.model_name].sudo()
        record = Model.browse(feature_id_int)
        if not record.exists():
            raise MissingError(f"Feature {feature_id} not found in layer {layer_id}")

        geo_field_name = layer.geo_field_id.name
        properties = {
            "id": record.id,
            "name": record.display_name,
        }

        geometry = None
        if hasattr(record, geo_field_name):
            geo_value = getattr(record, geo_field_name)
            if geo_value:
                try:
                    # GeoField returns Shapely geometry objects
                    if hasattr(geo_value, "__geo_interface__"):
                        geometry = geo_value.__geo_interface__
                    else:
                        # Fallback for string values (GeoJSON or WKT)
                        try:
                            geometry = json.loads(geo_value)
                        except (json.JSONDecodeError, TypeError):
                            from shapely import wkt

                            shape = wkt.loads(geo_value)
                            geometry = shape.__geo_interface__
                except Exception as e:
                    _logger.warning("Failed to parse geometry: %s", e)

        # nosemgrep: odoo-expose-database-id
        return {
            "type": "Feature",
            "id": record.id,
            "properties": properties,
            "geometry": geometry,
        }

    def _build_report_styling(self, report):
        """Build styling hints from report configuration.

        Args:
            report: spp.gis.report record

        Returns:
            dict: Styling configuration
        """
        styling = {
            "geometry_type": report.geometry_type,
            "color_scheme": None,
            "thresholds": [],
            "threshold_mode": report.threshold_mode,
        }

        # Add color scheme
        if report.color_scheme_id:
            styling["color_scheme"] = {
                "code": report.color_scheme_id.code,
                "name": report.color_scheme_id.name,
                "type": report.color_scheme_id.scheme_type,
                "colors": report.color_scheme_id.get_colors_list()
                if hasattr(report.color_scheme_id, "get_colors_list")
                else [],
            }

        # Add thresholds
        for threshold in report.threshold_ids.sorted("sequence"):
            styling["thresholds"].append(
                {
                    "min_value": threshold.min_value,
                    "max_value": threshold.max_value,
                    "color": threshold.color,
                    "label": threshold.label,
                }
            )

        return styling

    def _build_layer_styling(self, layer):
        """Build styling hints from data layer configuration.

        Args:
            layer: spp.gis.data.layer record

        Returns:
            dict: Styling configuration
        """
        styling = {
            "geometry_type": "polygon",  # Default
            "representation": layer.geo_repr,
        }

        # Add choropleth configuration if available
        if hasattr(layer, "_get_choropleth_config"):
            choropleth_config = layer._get_choropleth_config()
            if choropleth_config:
                styling["choropleth"] = choropleth_config

        # Add report-driven layer styling if available
        if hasattr(layer, "get_layer_style"):
            try:
                layer_style = layer.get_layer_style()
                styling.update(layer_style)
            except Exception as e:
                _logger.warning("Failed to get layer style: %s", e)

        return styling

    def _bbox_to_geojson(self, bbox):
        """Convert bounding box to GeoJSON Polygon for gis_intersects operator.

        Args:
            bbox: [west, south, east, north]

        Returns:
            dict: GeoJSON Polygon geometry
        """
        west, south, east, north = bbox
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    [west, south],
                    [east, south],
                    [east, north],
                    [west, north],
                    [west, south],
                ]
            ],
        }

    def _resolve_area_codes(self, area_codes):
        """Convert area codes to IDs.

        Args:
            area_codes: List of area codes

        Returns:
            list: Area IDs or None
        """
        if not area_codes:
            return None

        # nosemgrep: odoo-sudo-without-context
        areas = self.env["spp.area"].sudo().search([("code", "in", area_codes)])
        return areas.ids if areas else None


def filter_features_by_bbox(features, bbox):
    """Filter GeoJSON features by bounding box overlap.

    Uses bounding-box-of-geometry vs query-bbox intersection test.
    This is an approximation (same as PostGIS && operator) that is
    fast and sufficient for OAPIF tiled fetching.

    Args:
        features: List of GeoJSON Feature dicts
        bbox: [west, south, east, north]

    Returns:
        list: Features whose geometry bbox overlaps the query bbox
    """
    west, south, east, north = bbox
    result = []

    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue

        coords = _extract_all_coordinates(geometry)
        if not coords:
            continue

        # Compute feature's bounding box from coordinates
        feature_west = min(c[0] for c in coords)
        feature_east = max(c[0] for c in coords)
        feature_south = min(c[1] for c in coords)
        feature_north = max(c[1] for c in coords)

        # Bounding box overlap test
        if feature_east >= west and feature_west <= east and feature_north >= south and feature_south <= north:
            result.append(feature)

    return result


def _extract_all_coordinates(geometry):
    """Extract all coordinate pairs from a GeoJSON geometry.

    Handles Polygon, MultiPolygon, Point, MultiPoint, LineString,
    and MultiLineString geometry types.

    Args:
        geometry: GeoJSON geometry dict with "type" and "coordinates"

    Returns:
        list: Flat list of [lon, lat] coordinate pairs, or empty list
    """
    geom_type = geometry.get("type", "")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        return []

    coords = []
    if geom_type == "Point":
        coords.append(coordinates)
    elif geom_type in ("MultiPoint", "LineString"):
        coords.extend(coordinates)
    elif geom_type in ("Polygon", "MultiLineString"):
        for ring in coordinates:
            coords.extend(ring)
    elif geom_type == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon:
                coords.extend(ring)
    return coords
