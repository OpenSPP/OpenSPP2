# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Demo Area Loader

Handles loading curated geographic data (areas and shapes) for demo environments.
Supports multiple countries with conditional GIS shape loading.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)


class DemoAreaLoader(models.TransientModel):
    """Load curated demo areas for supported countries."""

    _name = "spp.demo.area.loader"
    _description = "Demo Area Data Loader"

    SUPPORTED_COUNTRIES = [
        ("phl", "Philippines"),
        ("lka", "Sri Lanka"),
        ("tgo", "Togo"),
    ]

    country_code = fields.Selection(
        selection=SUPPORTED_COUNTRIES,
        string="Country",
        required=True,
        default="phl",
    )

    load_shapes = fields.Boolean(
        string="Load Shapes (GIS)",
        default=True,
        help="Load polygon shapes for GIS visualization. "
        "Requires spp_gis module to be installed.",
    )

    @api.model
    def _is_gis_installed(self):
        """Check if spp_gis module is installed."""
        return bool(
            self.env["ir.module.module"].search(
                [("name", "=", "spp_gis"), ("state", "=", "installed")]
            )
        )

    @api.model
    def _get_country_name(self, country_code):
        """Get the display name for a country code."""
        for code, name in self.SUPPORTED_COUNTRIES:
            if code == country_code:
                return name
        return country_code.upper()

    def action_load_areas(self):
        """Load area kinds and areas for the selected country.

        This method:
        1. Loads area kinds (hierarchy definition) from XML via ir.model.data
        2. Loads curated areas from XML via ir.model.data
        3. Optionally loads GeoJSON shapes if spp_gis is installed

        Returns:
            dict: Notification action showing results
        """
        self.ensure_one()
        country_code = self.country_code

        # Check if area data files exist
        try:
            file_path(f"spp_demo/data/countries/{country_code}/area_kinds.xml")
            file_path(f"spp_demo/data/countries/{country_code}/areas.xml")
        except FileNotFoundError:
            raise UserError(
                _("Area data files not found for country: %s")
                % self._get_country_name(country_code)
            )

        # Count existing areas before loading
        existing_count = self.env["spp.area"].search_count([])

        # Load XML data files using convert_file
        self._load_xml_data(country_code)

        # Count new areas
        new_count = self.env["spp.area"].search_count([])
        areas_created = new_count - existing_count

        # Load shapes if requested and GIS is available
        shapes_loaded = 0
        if self.load_shapes and self._is_gis_installed():
            shapes_loaded = self._load_shapes(country_code)

        # Build notification message
        country_name = self._get_country_name(country_code)
        message = _(
            "Successfully loaded geographic data for %(country)s:\n"
            "- %(areas)d areas created/updated\n"
        ) % {"country": country_name, "areas": areas_created}

        if shapes_loaded > 0:
            message += _("- %(shapes)d polygon shapes loaded\n") % {"shapes": shapes_loaded}
        elif self.load_shapes and not self._is_gis_installed():
            message += _("- Shapes not loaded (spp_gis not installed)\n")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Geographic Data Loaded"),
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def _load_xml_data(self, country_code):
        """Load area kinds and areas XML files for a country.

        The XML files are structured to be loaded via Odoo's data loading mechanism.
        We use convert_file to process them properly with noupdate handling.

        Args:
            country_code: ISO 3166-1 alpha-3 country code (lowercase)
        """
        from odoo.tools import convert_file

        # Load area kinds first (hierarchy definition)
        area_kinds_path = f"data/countries/{country_code}/area_kinds.xml"
        try:
            convert_file(
                self.env,
                "spp_demo",
                area_kinds_path,
                idref={},
                mode="init",
                noupdate=True,
            )
            _logger.info("Loaded area kinds for %s", country_code)
        except Exception as e:
            _logger.warning("Could not load area kinds for %s: %s", country_code, e)

        # Load areas (the actual geographic entities)
        areas_path = f"data/countries/{country_code}/areas.xml"
        try:
            convert_file(
                self.env,
                "spp_demo",
                areas_path,
                idref={},
                mode="init",
                noupdate=False,
            )
            _logger.info("Loaded areas for %s", country_code)
        except Exception as e:
            _logger.warning("Could not load areas for %s: %s", country_code, e)

    def _load_shapes(self, country_code):
        """Load GeoJSON shapes for areas.

        Reads the curated GeoJSON file and updates matching spp.area records
        with their polygon geometries.

        Args:
            country_code: ISO 3166-1 alpha-3 country code (lowercase)

        Returns:
            int: Number of shapes successfully loaded
        """
        try:
            geojson_path = file_path(f"spp_demo/data/shapes/{country_code}_curated.geojson")
        except FileNotFoundError:
            _logger.warning("GeoJSON file not found for %s", country_code)
            return 0

        try:
            with open(geojson_path, encoding="utf-8") as f:
                geojson_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            _logger.warning("Could not read GeoJSON file for %s: %s", country_code, e)
            return 0

        features = geojson_data.get("features", [])
        shapes_loaded = 0

        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry")

            if not properties.get("code") or not geometry:
                continue

            area_code = properties["code"]

            # Find matching area by code
            area = self.env["spp.area"].search([("code", "=", area_code)], limit=1)
            if not area:
                _logger.debug("Area not found for code: %s", area_code)
                continue

            # Check if area has geo_polygon field (spp_gis installed)
            if "geo_polygon" not in area._fields:
                _logger.debug("geo_polygon field not available on spp.area")
                break

            # Convert GeoJSON geometry to WKT format for PostGIS
            try:
                wkt = self._geojson_to_wkt(geometry)
                if wkt:
                    area.write({"geo_polygon": wkt})
                    shapes_loaded += 1
            except Exception as e:
                _logger.warning("Could not set shape for %s: %s", area_code, e)

        _logger.info("Loaded %d shapes for %s", shapes_loaded, country_code)
        return shapes_loaded

    def _geojson_to_wkt(self, geometry):
        """Convert GeoJSON geometry to WKT format.

        Supports Polygon and MultiPolygon geometries.

        Args:
            geometry: GeoJSON geometry dict

        Returns:
            str: WKT string or None if conversion fails
        """
        geom_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if not geom_type or not coordinates:
            return None

        if geom_type == "Polygon":
            return self._polygon_to_wkt(coordinates)
        elif geom_type == "MultiPolygon":
            polygons = [self._polygon_to_wkt(poly) for poly in coordinates]
            polygons = [p for p in polygons if p]
            if polygons:
                # Extract just the coordinate parts from each polygon WKT
                poly_coords = [p.replace("POLYGON", "").strip() for p in polygons]
                return f"MULTIPOLYGON({','.join(poly_coords)})"
        return None

    def _polygon_to_wkt(self, coordinates):
        """Convert polygon coordinates to WKT.

        Args:
            coordinates: List of rings (first is exterior, rest are holes)

        Returns:
            str: WKT POLYGON string
        """
        if not coordinates:
            return None

        rings = []
        for ring in coordinates:
            points = [f"{p[0]} {p[1]}" for p in ring]
            rings.append(f"({','.join(points)})")

        return f"POLYGON({','.join(rings)})"

    @api.model
    def load_country_areas(self, country_code, load_shapes=True):
        """Programmatic method to load areas for a country.

        This method can be called from other modules or scripts
        to load geographic data without going through the wizard.

        Args:
            country_code: ISO 3166-1 alpha-3 country code (lowercase)
            load_shapes: Whether to load GIS shapes (default True)

        Returns:
            dict: Result with counts of loaded data
        """
        loader = self.create({"country_code": country_code, "load_shapes": load_shapes})
        loader._load_xml_data(country_code)

        shapes_loaded = 0
        if load_shapes and self._is_gis_installed():
            shapes_loaded = loader._load_shapes(country_code)

        return {
            "country_code": country_code,
            "shapes_loaded": shapes_loaded,
            "gis_available": self._is_gis_installed(),
        }
