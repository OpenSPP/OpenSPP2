# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for exporting GIS data as GeoPackage or ZIP."""

import io
import json
import logging
import tempfile
import zipfile
from pathlib import Path

_logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting GIS layers to various formats."""

    def __init__(self, env):
        """Initialize export service."""
        self.env = env

    def export_geopackage(
        self,
        layer_ids=None,
        include_geofences=True,
        admin_level=None,
    ):
        """Export layers and geofences as GeoPackage or ZIP of GeoJSON files.

        Args:
            layer_ids: List of report codes to export (optional, all if None)
            include_geofences: Include user's geofences (default: True)
            admin_level: Filter layers by admin level (optional)

        Returns:
            tuple: (bytes, filename, content_type)
                - bytes: File content
                - filename: Suggested filename
                - content_type: MIME type

        Raises:
            ValueError: If no layers found or invalid parameters
        """
        # Collect layers to export
        layers_data = self._collect_layers(layer_ids, admin_level)

        # Collect geofences if requested
        geofences_data = []
        if include_geofences:
            geofences_data = self._collect_geofences()

        if not layers_data and not geofences_data:
            raise ValueError("No data available to export")

        # Try to create GeoPackage with fiona
        try:
            return self._create_geopackage(layers_data, geofences_data)
        except ImportError:
            _logger.info("fiona not available, falling back to GeoJSON ZIP export")
            return self._create_geojson_zip(layers_data, geofences_data)
        except Exception as e:
            _logger.warning("GeoPackage creation failed: %s, falling back to GeoJSON ZIP", e)
            return self._create_geojson_zip(layers_data, geofences_data)

    def _collect_layers(self, layer_ids, admin_level):
        """Collect layer data for export.

        Args:
            layer_ids: List of report codes or None for all
            admin_level: Admin level filter

        Returns:
            list: List of (name, geojson) tuples
        """
        layers_data = []

        # Get layers service
        from .layers_service import LayersService

        layers_service = LayersService(self.env)

        # If specific layer_ids provided, use those
        if layer_ids:
            for layer_code in layer_ids:
                try:
                    geojson = layers_service.get_layer_geojson(
                        layer_id=layer_code,
                        layer_type="report",
                        admin_level=admin_level,
                        include_geometry=True,
                        include_disaggregation=False,
                    )
                    # Sanitize name for filename
                    layer_name = self._sanitize_filename(layer_code)
                    layers_data.append((layer_name, geojson))
                    _logger.info("Collected layer: %s with %d features", layer_code, len(geojson.get("features", [])))
                except Exception as e:
                    _logger.warning("Failed to collect layer %s: %s", layer_code, e)
        else:
            # Export all available reports
            # nosemgrep: odoo-sudo-without-context
            reports = self.env["spp.gis.report"].sudo().search([("active", "=", True)])
            for report in reports:
                try:
                    geojson = layers_service.get_layer_geojson(
                        layer_id=report.code,
                        layer_type="report",
                        admin_level=admin_level,
                        include_geometry=True,
                        include_disaggregation=False,
                    )
                    layer_name = self._sanitize_filename(report.code or f"layer_{report.id}")
                    layers_data.append((layer_name, geojson))
                    _logger.info("Collected report: %s with %d features", report.code, len(geojson.get("features", [])))
                except Exception as e:
                    _logger.warning("Failed to collect report %s: %s", report.code, e)

        return layers_data

    def _collect_geofences(self):
        """Collect active geofences for export.

        Returns:
            list: GeoJSON FeatureCollection for geofences
        """
        geofence_model = self.env["spp.gis.geofence"]
        geofences = geofence_model.search([("active", "=", True)])

        if not geofences:
            return []

        features = []
        for geofence in geofences:
            try:
                feature = geofence.to_geojson()
                features.append(feature)
            except Exception as e:
                _logger.warning("Failed to export geofence %s: %s", geofence.id, e)

        if not features:
            return []

        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "layer": "geofences",
                "count": len(features),
            },
        }

        _logger.info("Collected %d geofences", len(features))
        return [("geofences", geojson)]

    def _create_geopackage(self, layers_data, geofences_data):
        """Create GeoPackage file using fiona.

        Args:
            layers_data: List of (name, geojson) tuples
            geofences_data: List of (name, geojson) tuples

        Returns:
            tuple: (bytes, filename, content_type)
        """
        import fiona
        from fiona.crs import from_epsg

        # Create temporary file for GeoPackage
        with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp_file:
            gpkg_path = tmp_file.name

        try:
            # Combine all data
            all_data = layers_data + geofences_data

            # Write each layer to GeoPackage
            for layer_name, geojson in all_data:
                features = geojson.get("features", [])
                if not features:
                    _logger.info("Skipping empty layer: %s", layer_name)
                    continue

                # Determine geometry type from first feature
                geometry_type = self._get_geometry_type(features[0])

                # Build schema from first feature
                schema = self._build_schema(features[0], geometry_type)

                # Write layer to GeoPackage
                with fiona.open(
                    gpkg_path,
                    mode="w",
                    driver="GPKG",
                    layer=layer_name,
                    crs=from_epsg(4326),  # WGS84
                    schema=schema,
                ) as layer:
                    for feature in features:
                        # Ensure feature has valid structure
                        if feature.get("geometry") and feature.get("properties"):
                            layer.write(feature)

                _logger.info("Wrote layer %s with %d features to GeoPackage", layer_name, len(features))

            # Read GeoPackage file
            with open(gpkg_path, "rb") as f:
                gpkg_bytes = f.read()

            return (
                gpkg_bytes,
                "openspp_export.gpkg",
                "application/geopackage+sqlite3",
            )

        finally:
            # Clean up temporary file
            try:
                Path(gpkg_path).unlink()
            except Exception as e:
                _logger.warning("Failed to delete temporary GeoPackage: %s", e)

    def _create_geojson_zip(self, layers_data, geofences_data):
        """Create ZIP of GeoJSON files as fallback.

        Args:
            layers_data: List of (name, geojson) tuples
            geofences_data: List of (name, geojson) tuples

        Returns:
            tuple: (bytes, filename, content_type)
        """
        # Create ZIP file in memory
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            # Combine all data
            all_data = layers_data + geofences_data

            for layer_name, geojson in all_data:
                # Write GeoJSON to ZIP
                geojson_str = json.dumps(geojson, indent=2)
                zip_file.writestr(f"{layer_name}.geojson", geojson_str)
                _logger.info("Added %s.geojson to ZIP", layer_name)

        zip_bytes = zip_buffer.getvalue()

        return (
            zip_bytes,
            "openspp_export.zip",
            "application/zip",
        )

    def _get_geometry_type(self, feature):
        """Extract geometry type from feature.

        Args:
            feature: GeoJSON feature

        Returns:
            str: Geometry type (Point, LineString, Polygon, etc.)
        """
        geometry = feature.get("geometry")
        if not geometry:
            return "Point"  # Default

        geom_type = geometry.get("type", "Point")

        # Map GeoJSON types to fiona types
        type_mapping = {
            "Point": "Point",
            "MultiPoint": "MultiPoint",
            "LineString": "LineString",
            "MultiLineString": "MultiLineString",
            "Polygon": "Polygon",
            "MultiPolygon": "MultiPolygon",
        }

        return type_mapping.get(geom_type, "Polygon")

    def _build_schema(self, feature, geometry_type):
        """Build fiona schema from feature properties.

        Args:
            feature: GeoJSON feature
            geometry_type: Geometry type string

        Returns:
            dict: Fiona schema definition
        """
        properties = feature.get("properties", {})

        # Build property schema
        prop_schema = {}
        for key, value in properties.items():
            if isinstance(value, bool):
                prop_schema[key] = "bool"
            elif isinstance(value, int):
                prop_schema[key] = "int"
            elif isinstance(value, float):
                prop_schema[key] = "float"
            else:
                prop_schema[key] = "str"

        return {
            "geometry": geometry_type,
            "properties": prop_schema,
        }

    def _sanitize_filename(self, name):
        """Sanitize string for use as filename.

        Args:
            name: Original name

        Returns:
            str: Sanitized name
        """
        # Replace problematic characters
        sanitized = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        # Remove any non-alphanumeric except underscore and dash
        sanitized = "".join(c for c in sanitized if c.isalnum() or c in ("_", "-"))
        return sanitized or "layer"
