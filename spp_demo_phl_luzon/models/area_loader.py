# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Luzon Area Loader

Loads the full Luzon administrative boundary hierarchy (8 regions, 42 provinces,
771 municipalities) from bundled XML data. Requires that spp_demo's area_kinds
have been loaded first (provides the area_type_id references).
"""

import json
import logging

from lxml import etree

from odoo import api, models
from odoo.tools.convert import convert_file
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)


class DemoLuzonAreaLoader(models.TransientModel):
    _name = "spp.demo.luzon.area.loader"
    _description = "Luzon Area Data Loader"

    @api.model
    def load_luzon_areas(self, load_shapes=True):
        """Load Luzon area hierarchy and optionally GeoJSON shapes.

        Must be called AFTER spp_demo's area_kinds have been loaded
        (they provide the area_type_id references used in areas_luzon.xml).

        Args:
            load_shapes: Whether to load GIS polygon shapes

        Returns:
            dict: Result with counts of loaded data
        """
        existing_count = self.env["spp.area"].search_count([])

        # Pre-link overlapping areas so convert_file updates instead of inserting
        self._link_existing_areas()

        # Load XML area records via convert_file
        try:
            convert_file(
                self.env,
                "spp_demo_phl_luzon",
                "data/areas_luzon.xml",
                idref={},
                mode="init",
                noupdate=False,
            )
            _logger.info("Loaded Luzon areas XML")
        except Exception as e:
            _logger.warning("Could not load Luzon areas: %s", e)
            return {"areas_created": 0, "shapes_loaded": 0}

        new_count = self.env["spp.area"].search_count([])
        areas_created = new_count - existing_count

        # Load shapes if requested and GIS is available
        shapes_loaded = 0
        if load_shapes and "geo_polygon" in self.env["spp.area"]._fields:
            shapes_loaded = self._load_shapes()

        _logger.info(
            "Luzon area loading complete: %d areas created, %d shapes loaded",
            areas_created,
            shapes_loaded,
        )
        return {"areas_created": areas_created, "shapes_loaded": shapes_loaded}

    def _link_existing_areas(self):
        """Create ir.model.data records for areas that already exist.

        The base spp_demo module may have already loaded some areas (e.g. NCR
        and CALABARZON regions/provinces/municipalities) with XML IDs like
        spp_demo.area_phl_ph04. The Luzon XML uses different XML IDs
        (spp_demo_phl_luzon.area_luzon_ph04) for the same area codes.

        By pre-creating ir.model.data entries pointing to the existing
        spp.area records, convert_file will update them instead of
        trying to insert duplicates (which would violate the UNIQUE
        constraint on spp_area.code).
        """
        xml_path = file_path("spp_demo_phl_luzon/data/areas_luzon.xml")
        # Harden against XXE: disable entity resolution and network access.
        parser = etree.XMLParser(resolve_entities=False, no_network=True)
        tree = etree.parse(xml_path, parser=parser)  # nosec B320 — bundled module data, restricted parser (no entities, no network)
        root = tree.getroot()

        # Collect (xml_id, code) pairs from the XML
        xml_entries = []
        for record in root.iter("record"):
            if record.get("model") != "spp.area":
                continue
            xml_id = record.get("id")
            code = None
            for field in record.iter("field"):
                if field.get("name") == "code":
                    code = field.text
                    break
            if xml_id and code:
                xml_entries.append((xml_id, code))

        if not xml_entries:
            return

        # Find which codes already exist as spp.area records
        codes = [code for _, code in xml_entries]
        existing_areas = self.env["spp.area"].search([("code", "in", codes)])
        area_by_code = {a.code: a.id for a in existing_areas}

        # Check which xml_ids already have ir.model.data entries
        IMD = self.env["ir.model.data"]
        module = "spp_demo_phl_luzon"
        existing_imd = IMD.search([("module", "=", module), ("model", "=", "spp.area")])
        existing_names = {r.name for r in existing_imd}

        # Create ir.model.data entries for overlapping areas
        to_create = []
        for xml_id, code in xml_entries:
            if xml_id in existing_names:
                continue
            area_id = area_by_code.get(code)
            if area_id:
                to_create.append(
                    {
                        "module": module,
                        "name": xml_id,
                        "model": "spp.area",
                        "res_id": area_id,
                        "noupdate": False,
                    }
                )

        if to_create:
            IMD.create(to_create)
            _logger.info("Pre-linked %d existing areas for Luzon XML loading", len(to_create))

    def _load_shapes(self):
        """Load GeoJSON polygon shapes for Luzon areas."""
        try:
            geojson_path = file_path("spp_demo_phl_luzon/data/shapes/phl_luzon.geojson")
        except FileNotFoundError:
            _logger.warning("Luzon GeoJSON file not found")
            return 0

        try:
            with open(geojson_path, encoding="utf-8") as f:
                geojson_data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            _logger.warning("Could not read Luzon GeoJSON: %s", e)
            return 0

        features = geojson_data.get("features", [])
        shapes_loaded = 0

        # Batch-fetch all referenced areas once; a per-feature search would
        # issue hundreds of queries for Luzon's administrative areas.
        codes = [f.get("properties", {}).get("code") for f in features]
        codes = [c for c in codes if c]
        areas_by_code = {area.code: area for area in self.env["spp.area"].search([("code", "in", codes)])}

        for feature in features:
            properties = feature.get("properties", {})
            geometry = feature.get("geometry")

            code = properties.get("code")
            if not code or not geometry:
                continue

            area = areas_by_code.get(code)
            if not area:
                continue

            try:
                from shapely.geometry import shape

                geom = shape(geometry)
                area.write({"geo_polygon": geom.wkt})
                shapes_loaded += 1
            except Exception as e:
                _logger.warning("Could not set shape for %s: %s", code, e)

        return shapes_loaded
