# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
DRIMS Sri Lanka Demo Generator

Generates demo data for disaster response inventory management:
1. Sri Lanka Areas - Imports from official admin boundary Excel file
2. Fixed Demo Incidents - Based on realistic SL disaster scenarios
3. Demo Donations - From various donor types (UN, NGO, Private)
4. Demo Requests - At various stages (draft, pending, approved, dispatched)
5. Demo Stock - Populates warehouses with sample inventory
"""

import base64
import json
import logging
import os
import random
from datetime import date, timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _simplify_geometry(geometry, tolerance=0.001):
    """Simplify geometry to reduce point count while preserving shape.

    Large polygons can have tens of thousands of points which impacts
    performance. This simplifies the geometry while preserving topology.

    Args:
        geometry: GeoJSON geometry dict (Polygon or MultiPolygon)
        tolerance: Simplification tolerance in degrees (~100m at equator)

    Returns:
        GeoJSON geometry dict (simplified, same type as input)
    """
    # Import here to avoid issues if shapely not installed
    try:
        from shapely.geometry import mapping, shape
    except ImportError:
        _logger.warning("shapely not available - returning geometry as-is")
        return geometry

    # Convert to shapely, simplify, convert back
    shp = shape(geometry)
    simplified = shp.simplify(tolerance, preserve_topology=True)
    return mapping(simplified)


class DrimsDemoGenerator(models.TransientModel):
    _name = "spp.drims.demo.generator"
    _description = "DRIMS Demo Data Generator"

    name = fields.Char(
        string="Name",
        default="DRIMS Sri Lanka Demo",
        required=True,
    )

    # Demo mode selection (simplified UI always uses "full")
    demo_mode = fields.Selection(
        [
            ("quick", "Quick Demo (minimal data)"),
            ("standard", "Standard Demo (recommended)"),
            ("full", "Full Demo (comprehensive)"),
        ],
        string="Demo Mode",
        default="full",
        required=True,
        help="Quick: 1 incident, few records\n"
        "Standard: 2 incidents, balanced data\n"
        "Full: 3 incidents, complete scenario",
    )

    # Area import options
    is_import_areas = fields.Boolean(
        string="Import Sri Lanka Areas",
        default=True,
        help="Import areas from official admin boundary data (Provinces, Districts, DS/GN Divisions)",
    )

    # Incident options
    create_incidents = fields.Boolean(
        string="Create Demo Incidents",
        default=True,
        help="Create sample disaster incidents",
    )
    incident_count = fields.Integer(
        string="Number of Incidents",
        default=2,
    )

    # Donation options
    create_donations = fields.Boolean(
        string="Create Demo Donations",
        default=True,
        help="Create sample donations from various donors",
    )
    donations_per_incident = fields.Integer(
        string="Donations per Incident",
        default=5,
    )

    # Request options
    create_requests = fields.Boolean(
        string="Create Demo Requests",
        default=True,
        help="Create sample requests at various stages",
    )
    requests_per_incident = fields.Integer(
        string="Requests per Incident",
        default=10,
    )

    # Stock options
    is_populate_stock = fields.Boolean(
        string="Populate Warehouse Stock",
        default=True,
        help="Add initial stock to warehouses",
    )

    # Personnel options
    create_personnel = fields.Boolean(
        string="Create Demo Personnel",
        default=True,
        help="Create sample deployed personnel for incidents",
    )
    personnel_per_incident = fields.Integer(
        string="Personnel per Incident",
        default=8,
    )

    # State tracking
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
        ],
        string="State",
        default="draft",
    )

    def action_ensure_demo_user_groups(self):
        """Ensure DRIMS demo users have correct security groups.

        This is a lightweight action for E2E setup: assigns DRIMS-specific
        groups to demo users and clears menu cache without generating data.
        """
        for rec in self:
            rec._ensure_demo_user_groups()
        return True

    def _ensure_demo_user_groups(self):
        """Assign DRIMS security groups to demo users."""
        Users = self.env["res.users"].sudo()
        Groups = self.env["res.groups"].sudo()
        IrModelData = self.env["ir.model.data"].sudo()

        # Map demo user logins to required DRIMS groups
        user_group_map = {
            # spp_drims_sl users
            "admin.dmc@drims.gov.lk": [
                "spp_drims.group_drims_manager",
                "stock.group_stock_manager",
            ],
            "wh.colombo@drims.gov.lk": [
                "spp_drims.group_drims_manager",
                "stock.group_stock_manager",
            ],
            "wh.kandy@drims.gov.lk": [
                "spp_drims.group_drims_manager",
                "stock.group_stock_manager",
            ],
            "approver.national@drims.gov.lk": [
                "spp_drims.group_drims_approver",
            ],
            "approver.western@drims.gov.lk": [
                "spp_drims.group_drims_approver",
            ],
            "officer.colombo@drims.gov.lk": [
                "spp_drims.group_drims_officer",
            ],
            "officer.gampaha@drims.gov.lk": [
                "spp_drims.group_drims_officer",
            ],
            "secretary@drims.gov.lk": [
                "spp_drims.group_drims_viewer",
            ],
            # spp_drims_sl_demo users (simpler logins)
            "kumari": [
                "spp_drims.group_drims_field_officer",
            ],
            "rajitha": [
                "spp_drims.group_drims_approver",
            ],
            "silva": [
                "spp_drims.group_drims_manager",
            ],
            "secretary": [
                "spp_drims.group_drims_viewer",
            ],
        }

        def get_group_by_xmlid(xmlid):
            """Get group by XML ID, returns False if not found."""
            try:
                module, name = xmlid.split(".")
                data = IrModelData.search(
                    [
                        ("module", "=", module),
                        ("name", "=", name),
                        ("model", "=", "res.groups"),
                    ],
                    limit=1,
                )
                if data:
                    return Groups.browse(data.res_id)
            except Exception:
                pass
            return False

        for login, group_xmlids in user_group_map.items():
            user = Users.search([("login", "=", login)], limit=1)
            if not user:
                continue

            groups_to_add = Groups
            for xmlid in group_xmlids:
                group = get_group_by_xmlid(xmlid)
                if group and group not in user.group_ids:
                    groups_to_add |= group

            if groups_to_add:
                user.write({"group_ids": [(4, g.id) for g in groups_to_add]})
                _logger.info(
                    "Assigned groups to %s: %s",
                    login,
                    ", ".join(groups_to_add.mapped("name")),
                )

        # Clear menu cache to ensure new groups take effect
        self.env["ir.ui.menu"].clear_caches()

    @api.onchange("demo_mode")
    def _onchange_demo_mode(self):
        """Adjust settings based on demo mode."""
        if self.demo_mode == "quick":
            self.incident_count = 1
            self.donations_per_incident = 3
            self.requests_per_incident = 5
            self.personnel_per_incident = 5
        elif self.demo_mode == "standard":
            self.incident_count = 2
            self.donations_per_incident = 5
            self.requests_per_incident = 10
            self.personnel_per_incident = 8
        elif self.demo_mode == "full":
            self.incident_count = 3
            self.donations_per_incident = 8
            self.requests_per_incident = 15
            self.personnel_per_incident = 15

    def action_generate(self):
        """Main entry point to generate demo data."""
        self.ensure_one()
        self.state = "in_progress"

        try:
            areas_imported = 0
            incidents = self.env["spp.hazard.incident"]
            donations = self.env["spp.drims.donation"]
            requests = self.env["spp.drims.request"]

            if self.is_import_areas:
                areas_imported = self._import_sl_areas()
                _logger.info("Imported %d Sri Lanka areas", areas_imported)

                # Import HDX polygons if module is installed
                polygons_imported = self._import_hdx_polygons()
                if polygons_imported:
                    _logger.info("Loaded HDX polygons for %d areas", polygons_imported)

            if self.create_incidents:
                incidents = self._generate_incidents()
                _logger.info("Created %d demo incidents", len(incidents))

            if self.create_donations and incidents:
                donations = self._generate_donations(incidents)
                _logger.info("Created %d demo donations", len(donations))

            if self.create_requests and incidents:
                requests = self._generate_requests(incidents)
                _logger.info("Created %d demo requests", len(requests))

            # Create completed dispatches for approved requests (for dashboard KPIs)
            dispatches = self._generate_completed_dispatches(incidents)
            _logger.info("Created %d completed dispatches", len(dispatches))

            if self.is_populate_stock:
                self._populate_warehouse_stock()
                _logger.info("Populated warehouse stock")

            # Create demo personnel
            personnel = self.env["spp.drims.personnel"]
            if self.create_personnel and incidents:
                personnel = self._generate_personnel(incidents)
                _logger.info("Created %d demo personnel", len(personnel))

            # Create demo alerts and run alert checks
            self._create_demo_alerts(incidents)
            _logger.info("Created demo alerts")

            # Refresh GIS reports for choropleth visualization
            self._refresh_gis_reports()

            self.state = "completed"

            message_parts = []
            if areas_imported:
                message_parts.append(_("%d areas") % areas_imported)
            message_parts.append(_("%d incidents") % len(incidents))
            message_parts.append(_("%d donations") % len(donations))
            message_parts.append(_("%d requests") % len(requests))
            message_parts.append(_("%d dispatches") % len(dispatches))
            message_parts.append(_("%d personnel") % len(personnel))

            # Redirect to DRIMS Dashboard after loading demo data
            action = self.env.ref("spp_drims.drims_dashboard_action", raise_if_not_found=False)
            if action:
                result = action.sudo().read()[0]
                result["target"] = "main"
                return result

            # Fallback to notification if dashboard action not found
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Demo Data Generated"),
                    "message": _("Created: %s") % ", ".join(message_parts),
                    "sticky": False,
                    "type": "success",
                },
            }

        except Exception as e:
            self.state = "draft"
            _logger.exception("Demo generation failed")
            raise UserError(_("Demo generation failed: %s") % str(e)) from e

    def _get_sl_area_excel_path(self):
        """Get path to Sri Lanka admin boundary Excel file."""
        # File is in spp_drims_sl/data/
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sl_module_path = os.path.join(os.path.dirname(module_path), "spp_drims_sl", "data")
        return os.path.join(sl_module_path, "lka_adminboundaries_tabulardata.xlsx")

    def _import_sl_areas(self):
        """Import Sri Lanka areas from official admin boundary Excel file.

        Uses the spp.area.import model to parse and import areas, then
        assigns the correct SL-specific area kinds based on admin level.

        Returns:
            int: Number of areas imported/updated
        """
        # Use context to bypass queue_job delays for synchronous processing
        AreaImport = self.env["spp.area.import"].with_context(queue_job__no_delay=True)
        Area = self.env["spp.area"]

        # Check if areas already exist
        existing_count = Area.search_count([])
        if existing_count > 100:
            _logger.info("Skipping area import - %d areas already exist", existing_count)
            return 0

        # Activate Sinhala and Tamil languages for translations
        for iso_code in ["si", "ta"]:
            lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", iso_code)], limit=1)
            if lang and not lang.active:
                lang.active = True
                _logger.info("Activated language ID %s for area translations", lang.id)

        # Get Excel file
        excel_path = self._get_sl_area_excel_path()
        if not os.path.exists(excel_path):
            _logger.warning("SL area Excel file not found: %s", excel_path)
            return 0

        # Read and encode file
        with open(excel_path, "rb") as f:
            excel_data = base64.b64encode(f.read())

        # Create import record
        area_import = AreaImport.create(
            {
                "excel_file": excel_data,
                "name": "lka_adminboundaries_tabulardata.xlsx",
                "state": "Uploaded",
            }
        )

        # Run import workflow synchronously (bypass job queue)
        _logger.info("Parsing Sri Lanka area Excel file...")
        area_import.parse_excel_to_json()

        # Import data synchronously (bypass job queue)
        _logger.info("Importing area data from %d JSON files...", len(area_import.json_file_ids))
        for json_file in area_import.json_file_ids:
            area_import._import_data_from_json(json_file.id)
        area_import._import_mark_done()

        # Validate raw data synchronously (bypass job queue)
        _logger.info("Validating %d area records...", len(area_import.raw_data_ids))
        area_import.raw_data_ids.validate_raw_data()
        area_import._validate_mark_done()

        # Save to area synchronously (bypass job queue)
        _logger.info("Saving areas...")
        area_import.raw_data_ids.save_to_area()
        area_import._save_to_area_mark_done()

        # Get imported areas and assign SL-specific area types
        imported_areas = area_import.raw_data_ids.mapped("area_id")
        self._assign_sl_area_types(imported_areas)

        # Link warehouses to their areas
        self._link_warehouses_to_areas()

        return len(imported_areas)

    def _import_hdx_polygons(self):
        """Import polygon boundaries for Sri Lanka areas from local GeoJSON files.

        Uses bundled GeoJSON files from HDX COD dataset to update existing areas
        with geo_polygon data. This avoids network dependency on HDX API.

        Files expected in spp_drims_sl_demo/data/:
        - lka_admin0.geojson (Country)
        - lka_admin1.geojson (Provinces)
        - lka_admin2.geojson (Districts)

        This enables choropleth visualization in GIS views and polygon
        rendering in the GeoJSON API.

        Returns:
            int: Number of areas updated with polygons, or 0 if not available
        """
        # Check if spp_area_hdx module is installed
        if "spp.hdx.cod.import.wizard" not in self.env:
            _logger.debug("spp_area_hdx not installed - skipping polygon import")
            return 0

        # Check if geo_polygon field exists on spp.area
        if "geo_polygon" not in self.env["spp.area"]._fields:
            _logger.debug("geo_polygon field not found on spp.area - skipping polygon import")
            return 0

        # Get module data directory
        module_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_path = os.path.join(module_path, "data")

        # GeoJSON files to import with their admin levels and field mappings
        # Field names follow HDX COD format: adm{N}_pcode, adm{N}_name, etc.
        geojson_files = [
            {
                "filename": "lka_admin1.geojson",
                "admin_level": 1,
                "pcode_field": "adm1_pcode",
                "name_field": "adm1_name",
                "parent_pcode_field": "adm0_pcode",
            },
            {
                "filename": "lka_admin2.geojson",
                "admin_level": 2,
                "pcode_field": "adm2_pcode",
                "name_field": "adm2_name",
                "parent_pcode_field": "adm1_pcode",
            },
        ]

        for file_config in geojson_files:
            file_path = os.path.join(data_path, file_config["filename"])

            if not os.path.exists(file_path):
                _logger.warning("GeoJSON file not found: %s", file_path)
                continue

            try:
                # Read and preprocess GeoJSON file
                with open(file_path, encoding="utf-8") as f:
                    geojson_data = json.load(f)

                # Simplify geometries to reduce point count (improves performance)
                for feature in geojson_data.get("features", []):
                    if feature.get("geometry"):
                        feature["geometry"] = _simplify_geometry(feature["geometry"])

                # Re-encode as base64 for the wizard
                file_data = base64.b64encode(json.dumps(geojson_data).encode("utf-8"))

                # Create and execute import wizard in file mode
                # Use sudo() to bypass HDX Manager ACL restriction
                wizard = (
                    self.env["spp.hdx.cod.import.wizard"]
                    .sudo()
                    .create(
                        {
                            "import_mode": "file",
                            "file_data": file_data,
                            "file_name": file_config["filename"],
                            "file_admin_level": file_config["admin_level"],
                            "pcode_field": file_config["pcode_field"],
                            "name_field": file_config["name_field"],
                            "parent_pcode_field": file_config["parent_pcode_field"],
                            "update_existing": True,
                            "create_missing": False,  # Only update existing areas
                            "update_names": False,  # Keep local names
                        }
                    )
                )

                # Run import
                wizard._import_from_file()

                _logger.info(
                    "Imported polygons from %s: %s",
                    file_config["filename"],
                    wizard.import_log or "completed",
                )

            except Exception as e:
                _logger.warning("Failed to import %s: %s", file_config["filename"], str(e))
                continue

        # Count areas with polygons
        areas_with_polygons = self.env["spp.area"].search_count([("geo_polygon", "!=", False)])

        _logger.info("Polygon import complete: %d areas have polygons", areas_with_polygons)
        return areas_with_polygons

    def _assign_sl_area_types(self, areas):
        """Assign Sri Lanka-specific area types based on admin level.

        Maps:
            Level 0 -> Province
            Level 1 -> District
            Level 2 -> DS Division
            Level 3 -> GN Division
        """
        # Get SL area types
        type_province = self.env.ref("spp_drims_sl.area_type_province", raise_if_not_found=False)
        type_district = self.env.ref("spp_drims_sl.area_type_district", raise_if_not_found=False)
        type_ds = self.env.ref("spp_drims_sl.area_type_ds_division", raise_if_not_found=False)
        type_gn = self.env.ref("spp_drims_sl.area_type_gn_division", raise_if_not_found=False)

        level_to_type = {
            0: type_province,
            1: type_district,
            2: type_ds,
            3: type_gn,
        }

        for area in areas:
            area_type = level_to_type.get(area.area_level)
            if area_type and area.area_type_id != area_type:
                area.area_type_id = area_type
                _logger.debug("Assigned type ID %s to area ID %s (level %d)", area_type.id, area.id, area.area_level)

    def _link_warehouses_to_areas(self):
        """Link DRIMS warehouses to their respective areas by name matching."""
        Warehouse = self.env["stock.warehouse"]
        Area = self.env["spp.area"]

        # Map warehouse names to area names
        warehouse_area_map = {
            "Central Warehouse - Colombo": "Colombo",
            "National Reserve Warehouse - Anuradhapura": "Anuradhapura",
            "Western Province Warehouse - Colombo": "Colombo",
            "Central Province Warehouse - Kandy": "Kandy",
            "Southern Province Warehouse - Galle": "Galle",
            "Northern Province Warehouse - Jaffna": "Jaffna",
            "Eastern Province Warehouse - Batticaloa": "Batticaloa",
            "North Western Province Warehouse - Kurunegala": "Kurunegala",
            "North Central Province Warehouse - Anuradhapura": "Anuradhapura",
            "Uva Province Warehouse - Badulla": "Badulla",
            "Sabaragamuwa Province Warehouse - Ratnapura": "Ratnapura",
        }

        for wh_name, area_name in warehouse_area_map.items():
            warehouse = Warehouse.search([("name", "=", wh_name)], limit=1)
            if warehouse and not warehouse.area_id:
                area = Area.search(
                    [
                        "|",
                        ("draft_name", "ilike", area_name),
                        ("name", "ilike", area_name),
                    ],
                    limit=1,
                )
                if area:
                    warehouse.area_id = area
                    _logger.debug("Linked warehouse %s to area ID %s", wh_name, area.id)

        # Add GPS coordinates if spp_drims_gis is installed
        self._add_warehouse_gps_coordinates()

    def _add_warehouse_gps_coordinates(self):
        """Add GPS coordinates to warehouses if spp_drims_gis module is installed.

        GPS coordinates are based on major Sri Lanka city locations.
        Format: [longitude, latitude] in GeoJSON Point format.
        """
        Warehouse = self.env["stock.warehouse"]

        # Check if gis_location field exists (spp_drims_gis installed)
        if "gis_location" not in Warehouse._fields:
            _logger.debug("gis_location field not found - spp_drims_gis not installed")
            return

        # Sri Lanka warehouse GPS coordinates
        # Format: warehouse name -> (longitude, latitude)
        warehouse_gps = {
            "Central Warehouse - Colombo": (79.8612, 6.9271),
            "National Reserve Warehouse - Anuradhapura": (80.4037, 8.3114),
            "Western Province Warehouse - Colombo": (79.8428, 6.9344),
            "Central Province Warehouse - Kandy": (80.6337, 7.2906),
            "Southern Province Warehouse - Galle": (80.2210, 6.0535),
            "Northern Province Warehouse - Jaffna": (80.0255, 9.6615),
            "Eastern Province Warehouse - Batticaloa": (81.6924, 7.7102),
            "North Western Province Warehouse - Kurunegala": (80.3647, 7.4863),
            "North Central Province Warehouse - Anuradhapura": (80.3833, 8.3500),
            "Uva Province Warehouse - Badulla": (81.0550, 6.9934),
            "Sabaragamuwa Province Warehouse - Ratnapura": (80.3992, 6.6828),
        }

        import json

        for wh_name, (longitude, latitude) in warehouse_gps.items():
            warehouse = Warehouse.search([("name", "=", wh_name)], limit=1)
            if warehouse and not warehouse.gis_location:
                warehouse.gis_location = json.dumps(
                    {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    }
                )
                _logger.debug("Added GPS coordinates to warehouse %s", wh_name)

    def _generate_incidents(self):
        """Generate demo hazard incidents."""
        Incident = self.env["spp.hazard.incident"]
        Category = self.env["spp.hazard.category"]

        # Get hazard categories from spp_drims_sl module
        category_flood = self.env.ref("spp_drims_sl.category_flood", raise_if_not_found=False)
        category_geological = self.env.ref("spp_drims_sl.category_geological", raise_if_not_found=False)
        category_drought = self.env.ref("spp_drims_sl.category_drought", raise_if_not_found=False)

        # Fallback: get any available category if demo categories not loaded
        fallback_category = None
        if not (category_flood or category_geological or category_drought):
            fallback_category = Category.search([], limit=1)
            if not fallback_category:
                raise UserError(
                    _(
                        "No hazard categories found. Please install spp_hazard demo data "
                        "or create hazard categories before generating demo incidents."
                    )
                )
            _logger.info("Using fallback category ID %s - spp_hazard demo data not loaded", fallback_category.id)

        # Get coordination modes for multi-agency coordination
        coord_modes = self._get_coordination_modes()

        # Demo incident scenarios using area names from real SL admin data
        # Names are searched dynamically to support both XML and imported data
        # Each incident has a different coordination mode to demonstrate multi-agency setup
        # Severity levels: 1=Minor, 2=Moderate, 3=Significant, 4=Severe, 5=Catastrophic
        scenarios = [
            {
                "name": "2025 Southwest Monsoon Floods",
                "code": "SL-2025-MONSOON-FLOOD",
                "category_id": (category_flood or fallback_category).id,
                "severity": "4",  # Severe
                "start_date": date.today() - timedelta(days=14),
                "description": "Heavy rainfall from southwest monsoon causing widespread flooding "
                "in Western and Southern provinces. Over 50,000 families affected.",
                "affected_areas": [
                    {"name": "Colombo", "severity": "5", "population": 25000},  # Catastrophic
                    {"name": "Gampaha", "severity": "4", "population": 15000},  # Severe
                    {"name": "Galle", "severity": "3", "population": 10000},  # Significant
                ],
                "coordination_mode": "lead_agency",  # Government-led response
            },
            {
                "name": "2025 Ratnapura Landslides",
                "code": "SL-2025-RATNAPURA-LS",
                "category_id": (category_geological or fallback_category).id,
                "severity": "4",  # Severe
                "start_date": date.today() - timedelta(days=7),
                "description": "Multiple landslides in Ratnapura district following heavy rains. "
                "Several villages evacuated, relief operations underway.",
                "affected_areas": [
                    {"name": "Ratnapura", "severity": "5", "population": 8000},  # Catastrophic
                    {"name": "Kegalle", "severity": "3", "population": 3000},  # Significant
                ],
                "coordination_mode": "cluster",  # UN cluster coordination
            },
            {
                "name": "2025 Northern Drought",
                "code": "SL-2025-NORTH-DROUGHT",
                "category_id": (category_drought or fallback_category).id,
                "severity": "3",  # Significant
                "start_date": date.today() - timedelta(days=30),
                "description": "Extended dry spell affecting Northern and North Central provinces. "
                "Agricultural losses and water shortages reported.",
                "affected_areas": [
                    {"name": "Jaffna", "severity": "4", "population": 12000},  # Severe
                    {"name": "Anuradhapura", "severity": "3", "population": 8000},  # Significant
                ],
                "coordination_mode": "consortium",  # NGO consortium
            },
        ]

        Area = self.env["spp.area"]
        IncidentArea = self.env["spp.hazard.incident.area"]
        incidents = Incident
        for i in range(min(self.incident_count, len(scenarios))):
            scenario = scenarios[i]

            # Get areas by name and build area data for incident_area_ids
            # Supports both XML data and imported Excel data
            # Search for district-level areas (level 2) specifically
            area_ids = []
            area_details = []  # For creating incident_area_ids records
            for area_info in scenario.get("affected_areas", []):
                area_name = area_info["name"] if isinstance(area_info, dict) else area_info
                # Search by draft_name (used by area importer) or name
                # Prioritize district-level (area_level=2), fallback to any level
                area = Area.search(
                    [
                        ("area_level", "=", 2),
                        "|",
                        ("draft_name", "ilike", area_name),
                        ("name", "ilike", area_name),
                    ],
                    limit=1,
                )
                # Fallback to any level if no district found
                if not area:
                    area = Area.search(
                        [
                            "|",
                            ("draft_name", "ilike", area_name),
                            ("name", "ilike", area_name),
                        ],
                        limit=1,
                    )
                if area:
                    area_ids.append(area.id)
                    if isinstance(area_info, dict):
                        area_details.append(
                            {
                                "area_id": area.id,
                                "severity_override": area_info.get("severity"),
                                "affected_population_estimate": area_info.get("population", 0),
                                "notes": f"Affected area in {scenario['name']}",
                            }
                        )

            # Get coordination mode for this incident
            coord_mode = coord_modes.get(scenario.get("coordination_mode"))

            vals = {
                "name": scenario["name"],
                "code": scenario["code"],
                "category_id": scenario["category_id"],
                "severity": scenario.get("severity", "3"),
                "start_date": scenario["start_date"],
                "description": scenario.get("description", ""),
                "status": "active",
                "area_ids": [Command.set(area_ids)],  # Link areas via many2many
            }
            if coord_mode:
                vals["coordination_mode_id"] = coord_mode.id

            incident = Incident.create(vals)

            # Create detailed incident_area_ids records with per-area severity
            for area_detail in area_details:
                IncidentArea.create(
                    {
                        "incident_id": incident.id,
                        **area_detail,
                    }
                )
            _logger.debug(
                "Created incident %s with %d affected areas",
                incident.name,
                len(area_details),
            )

            # Link warehouses to incident
            self._link_warehouses_to_incident(incident, area_ids)

            incidents |= incident

        return incidents

    def _link_warehouses_to_incident(self, incident, area_ids):
        """Link relevant warehouses to an incident."""
        Warehouse = self.env["stock.warehouse"]

        # Find warehouses in affected areas or nearby
        warehouses = Warehouse.search(
            [
                ("is_drims_warehouse", "=", True),
                "|",
                ("area_id", "in", area_ids),
                ("area_id.parent_id", "in", area_ids),
            ]
        )

        # Also include central warehouse
        central = self.env.ref("spp_drims_sl.warehouse_colombo_central", raise_if_not_found=False)
        if central:
            warehouses |= central

        for wh in warehouses:
            wh.incident_ids = [Command.link(incident.id)]

    def _generate_donations(self, incidents):
        """Generate demo donations for incidents."""
        Donation = self.env["spp.drims.donation"]
        donations = Donation

        # Get donors
        donors = self._get_demo_donors()
        products = self._get_demo_products()
        warehouses = self._get_demo_warehouses()

        if not donors or not products or not warehouses:
            _logger.warning("Missing donors, products, or warehouses for demo")
            return donations

        for incident in incidents:
            # Find warehouses linked to this incident
            incident_warehouses = self.env["stock.warehouse"].browse()
            for warehouse in warehouses:
                if incident in warehouse.incident_ids:
                    incident_warehouses |= warehouse
            if not incident_warehouses:
                incident_warehouses = warehouses[:1]

            for _i in range(self.donations_per_incident):
                donor = random.choice(donors)
                warehouse = random.choice(incident_warehouses.ids)
                warehouse = self.env["stock.warehouse"].browse(warehouse)

                # Random donation date within incident timeline
                days_ago = random.randint(1, 10)
                donation_date = date.today() - timedelta(days=days_ago)

                # Random target state for progression
                target_state = random.choice(["announced", "received", "inspected", "stocked"])

                donation = Donation.create(
                    {
                        "incident_id": incident.id,
                        "warehouse_id": warehouse.id,
                        "donor_id": donor.id,
                        "donor_name": donor.name,
                        "date_announced": donation_date,
                        "line_ids": self._generate_donation_lines(products),
                    }
                )

                # Progress to target state
                self._progress_donation_state(donation, target_state)

                donations |= donation

        return donations

    def _generate_donation_lines(self, products):
        """Generate random donation line items."""
        lines = []
        num_lines = random.randint(2, 5)
        selected_products = random.sample(list(products), min(num_lines, len(products)))

        # Prefetch related fields to avoid N+1 queries
        selected_products = self.env["product.product"].browse([p.id for p in selected_products])
        selected_products.mapped("uom_id")
        selected_products.mapped("standard_price")

        for product in selected_products:
            quantity = random.choice([50, 100, 200, 500, 1000])
            lines.append(
                Command.create(
                    {
                        "product_id": product.id,
                        "quantity_pledged": quantity,
                        "uom_id": product.uom_id.id,
                        "unit_value": product.standard_price,
                    }
                )
            )

        return lines

    def _progress_donation_state(self, donation, target_state):
        """Progress donation through states.

        Actual workflow: announced → received → inspected → stocked
        """
        states = ["announced", "received", "inspected", "stocked"]
        current_idx = 0  # Start at announced (default state)
        target_idx = states.index(target_state) if target_state in states else 0

        while current_idx < target_idx:
            current_idx += 1
            if states[current_idx] == "received":
                donation.action_mark_received()
            elif states[current_idx] == "inspected":
                donation.action_inspect()
            elif states[current_idx] == "stocked":
                # Prepare lots for lot-tracked products before stocking
                self._prepare_donation_lots(donation)
                donation.action_stock()

    def _prepare_donation_lots(self, donation):
        """Create lots for lot-tracked products in donation pickings.

        When validating stock pickings for lot-tracked products,
        Odoo requires lot/serial numbers. This method creates demo
        lots for products that require tracking.
        """
        Lot = self.env["stock.lot"]

        # Prefetch company_id to avoid N+1 queries
        pickings = donation.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        pickings.mapped("company_id")

        for picking in pickings:
            # Assign the picking first to create move lines
            picking.action_assign()

            # Prefetch move and product fields to avoid N+1 queries
            picking.move_ids.mapped("product_id")
            picking.move_ids.mapped("product_id.tracking")
            picking.move_ids.mapped("product_id.default_code")
            picking.move_ids.mapped("move_line_ids")

            for move in picking.move_ids:
                product = move.product_id
                if product.tracking == "none":
                    continue

                # Create a demo lot for this product
                lot_name = f"DEMO-{donation.reference}-{product.default_code or product.id}"
                lot = Lot.search(
                    [
                        ("name", "=", lot_name),
                        ("product_id", "=", product.id),
                        ("company_id", "=", picking.company_id.id),
                    ],
                    limit=1,
                )

                if not lot:
                    lot = Lot.create(
                        {
                            "name": lot_name,
                            "product_id": product.id,
                            "company_id": picking.company_id.id,
                        }
                    )

                # Set lot on move lines
                for move_line in move.move_line_ids:
                    move_line.lot_id = lot.id

    def _generate_requests(self, incidents):
        """Generate demo requests for incidents.

        Assigns OCHA/IASC humanitarian clusters to requests for 4W reporting.
        """
        Request = self.env["spp.drims.request"]
        requests = Request

        products = self._get_demo_products()
        areas = self._get_demo_areas()
        priorities = self._get_priority_codes()
        clusters = list(self._get_ocha_clusters())

        if not products or not areas:
            _logger.warning("Missing products or areas for demo requests")
            return requests

        for incident in incidents:
            for i in range(self.requests_per_incident):
                # Random area
                area = random.choice(areas)

                # Random priority
                priority = random.choice(priorities) if priorities else False

                # Create variety: some overdue (for SLA breach demo), some urgent, some future
                date_requested = None  # Will use default (today) unless overridden
                if i < 2:
                    # First 2 requests: overdue for SLA breach demo
                    # Set request date in the past so date_needed can also be in the past
                    days_overdue = random.randint(3, 10)  # 3-10 days overdue
                    date_requested = date.today() - timedelta(days=days_overdue + 5)
                    date_needed = date.today() - timedelta(days=days_overdue)
                    target_state = "approved"  # Must be approved to show as SLA breach
                elif i < 4:
                    # Next 2 requests: urgent (within 2 days for SLA warning)
                    date_needed = date.today() + timedelta(days=random.randint(0, 2))
                    target_state = random.choice(["pending", "approved"])
                else:
                    # Rest: normal future dates
                    date_needed = date.today() + timedelta(days=random.randint(3, 14))
                    target_state = random.choice(["draft", "pending", "approved", "rejected"])

                # Life threatening flag (10% chance)
                is_life_threatening = random.random() < 0.1

                # Assign a cluster (80% chance) for 4W reporting
                cluster = random.choice(clusters) if clusters and random.random() < 0.8 else False

                request_vals = {
                    "incident_id": incident.id,
                    "destination_area_id": area.id,
                    "date_needed": date_needed,
                    "priority_id": priority.id if priority else False,
                    "cluster_id": cluster.id if cluster else False,
                    "is_life_threatening": is_life_threatening,
                    "justification": f"Demo request for {area.name} - Disaster relief supplies needed",
                    "affected_population": random.randint(50, 500),
                    "line_ids": self._generate_request_lines(products),
                }
                # Add date_requested for overdue requests (must be before date_needed)
                if date_requested:
                    request_vals["date_requested"] = date_requested

                request = Request.create(request_vals)

                # Progress to target state
                self._progress_request_state(request, target_state)

                requests |= request

        return requests

    def _generate_request_lines(self, products):
        """Generate random request line items."""
        lines = []
        num_lines = random.randint(2, 6)
        selected_products = random.sample(list(products), min(num_lines, len(products)))

        # Prefetch related fields to avoid N+1 queries
        selected_products = self.env["product.product"].browse([p.id for p in selected_products])
        selected_products.mapped("uom_id")

        for product in selected_products:
            quantity = random.choice([20, 50, 100, 200])
            lines.append(
                Command.create(
                    {
                        "product_id": product.id,
                        "quantity_requested": quantity,
                        "uom_id": product.uom_id.id,
                    }
                )
            )

        return lines

    def _progress_request_state(self, request, target_state):
        """Progress request through approval states."""
        if target_state == "draft":
            return  # Already draft

        # Submit for approval
        try:
            request.action_submit()
        except Exception:
            return  # Can't progress without lines

        if target_state == "pending":
            return  # Already pending after submit

        if target_state == "approved":
            try:
                request.action_approve()
            except Exception:
                pass  # May not have approval permissions

        elif target_state == "rejected":
            try:
                request.rejection_reason = "Demo rejection - insufficient stock"
                request.action_reject()
            except Exception:
                pass

    def _populate_warehouse_stock(self):
        """Add initial stock to DRIMS warehouses.

        Note: Only storable products (type='product') can have quants.
        Consumable products are skipped as they don't track inventory.
        """
        Quant = self.env["stock.quant"]
        Lot = self.env["stock.lot"]
        warehouses = self._get_demo_warehouses()
        products = self._get_demo_products()

        if not warehouses or not products:
            return

        # Filter to storable products only
        storable_products = products.filtered(lambda p: p.is_storable)
        if not storable_products:
            _logger.warning("No storable products found for warehouse stock")
            return

        # Prefetch related fields to avoid N+1 queries
        warehouses.mapped("company_id")
        warehouses.mapped("lot_stock_id")

        for warehouse in warehouses:
            location = warehouse.lot_stock_id
            if not location:
                continue

            for product in storable_products:
                # Random stock level
                quantity = random.choice([100, 200, 500, 1000, 2000])

                # For lot-tracked products, create a lot first
                lot = None
                if product.tracking in ("lot", "serial"):
                    lot_name = f"INIT-{warehouse.code}-{product.default_code or product.id}"
                    lot = Lot.search(
                        [
                            ("name", "=", lot_name),
                            ("product_id", "=", product.id),
                            ("company_id", "=", warehouse.company_id.id),
                        ],
                        limit=1,
                    )
                    if not lot:
                        lot_vals = {
                            "name": lot_name,
                            "product_id": product.id,
                            "company_id": warehouse.company_id.id,
                        }
                        # Add expiry dates for demo (some near expiry, some far)
                        # Only if product_expiry module provides the field
                        if "expiration_date" in Lot._fields:
                            # Make some lots expire soon for alert demo
                            if random.random() < 0.2:  # 20% chance of near expiry
                                days_until_expiry = random.randint(7, 30)
                            else:
                                days_until_expiry = random.randint(90, 365)
                            lot_vals["expiration_date"] = fields.Datetime.now() + timedelta(days=days_until_expiry)
                        lot = Lot.create(lot_vals)

                # Check if quant exists
                search_domain = [
                    ("product_id", "=", product.id),
                    ("location_id", "=", location.id),
                ]
                if lot:
                    search_domain.append(("lot_id", "=", lot.id))

                existing = Quant.search(search_domain, limit=1)

                if existing:
                    existing.quantity += quantity
                else:
                    quant_vals = {
                        "product_id": product.id,
                        "location_id": location.id,
                        "quantity": quantity,
                    }
                    if lot:
                        quant_vals["lot_id"] = lot.id
                    Quant.create(quant_vals)

    def _get_demo_donors(self):
        """Get available donor partners."""
        donors = []
        donor_refs = [
            "spp_drims_sl.agency_unicef",
            "spp_drims_sl.agency_wfp",
            "spp_drims_sl.agency_red_cross",
            "spp_drims_sl.agency_care",
            "spp_drims_sl.agency_oxfam",
        ]
        for ref in donor_refs:
            donor = self.env.ref(ref, raise_if_not_found=False)
            if donor:
                donors.append(donor)
        return donors

    def _get_demo_products(self):
        """Get demo relief products."""
        products = self.env["product.product"]
        product_refs = [
            "product_rice_5kg",
            "product_rice_25kg",
            "product_dhal",
            "product_bottled_water",
            "product_first_aid_kit",
            "product_blanket",
            "product_hygiene_kit",
            "product_family_tent",
            "product_tarpaulin",
            "product_solar_lamp",
        ]
        for ref in product_refs:
            template = self.env.ref(f"spp_drims_sl_demo.{ref}", raise_if_not_found=False)
            if template:
                # Get product variant
                variant = template.product_variant_id
                if variant:
                    products |= variant
        return products

    def _get_demo_warehouses(self):
        """Get DRIMS warehouses."""
        return self.env["stock.warehouse"].search(
            [
                ("is_drims_warehouse", "=", True),
            ]
        )

    def _get_demo_areas(self):
        """Get demo areas (Sri Lanka districts from imported area data)."""
        Area = self.env["spp.area"]

        # Get the district area type from SL configuration
        district_type = self.env.ref("spp_drims_sl.area_type_district", raise_if_not_found=False)

        if district_type:
            # Query all districts dynamically from imported area data
            areas = Area.search(
                [
                    ("area_type_id", "=", district_type.id),
                ]
            )
            if areas:
                return list(areas)

        # Fallback: return any areas if no district type configured
        _logger.warning("District area type not found, using all available areas")
        return list(Area.search([], limit=25))

    def _get_priority_codes(self):
        """Get priority vocabulary codes."""
        return self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:priority-levels"),
            ]
        )

    def _get_coordination_modes(self):
        """Get coordination modes as dict keyed by code."""
        modes = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:coordination-modes"),
            ]
        )
        return {m.code: m for m in modes}

    def _get_ocha_clusters(self):
        """Get OCHA/IASC humanitarian clusters as list."""
        return self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:ocha:iasc:clusters"),
            ]
        )

    def _create_demo_alerts(self, incidents):
        """Create demo alerts and run alert engine checks.

        Creates variety of alerts for demonstration:
        - Low stock alerts (guaranteed sample + cron-generated)
        - SLA breach/warning alerts (guaranteed sample + cron-generated)
        - Expiry alerts (if product_expiry installed)
        """
        Alert = self.env["spp.drims.alert"]
        AlertType = self.env["spp.vocabulary.code"]
        created_count = 0

        # Get alert types
        alert_types = AlertType.search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:alert-types"),
            ]
        )
        type_map = {t.code: t for t in alert_types}

        # Create guaranteed sample alerts for demo
        warehouses = self._get_demo_warehouses()
        products = self._get_demo_products()

        # 1. Create low stock alert
        if "low_stock" in type_map and warehouses and products and incidents:
            product = products[0] if products else None
            warehouse = warehouses[0] if warehouses else None
            incident = incidents[0] if incidents else None
            if product and warehouse and incident:
                Alert.create(
                    {
                        "alert_type_id": type_map["low_stock"].id,
                        "priority": "high",
                        "title": f"Low Stock: {product.name}",
                        "description": (
                            f"Stock level for {product.name} at {warehouse.name} is critically low.\n"
                            "Available: 15.00, Needed: 200.00, Threshold: 100.00"
                        ),
                        "incident_id": incident.id,
                        "warehouse_id": warehouse.id,
                        "product_id": product.id,
                        "current_value": 15.0,
                        "threshold_value": 100.0,
                    }
                )
                created_count += 1
                _logger.debug("Created demo low stock alert for product ID %s", product.id)

        # 2. Create SLA breach alert from an overdue request
        Request = self.env["spp.drims.request"]
        overdue_requests = Request.search(
            [
                ("incident_id", "in", incidents.ids if incidents else []),
                ("date_needed", "<", date.today()),
                ("approval_state", "=", "approved"),
            ],
            limit=1,
        )
        if "sla_breach" in type_map and overdue_requests:
            request = overdue_requests[0]
            days_overdue = (date.today() - request.date_needed).days
            Alert.create(
                {
                    "alert_type_id": type_map["sla_breach"].id,
                    "priority": "critical",
                    "title": f"SLA Breach: {request.reference}",
                    "description": (
                        f"Request {request.reference} was due on {request.date_needed} "
                        f"but is still not delivered.\nDays overdue: {days_overdue}\n"
                        f"Destination: {request.destination_area_id.name}"
                    ),
                    "incident_id": request.incident_id.id,
                    "request_id": request.id,
                    "days_until": -days_overdue,
                }
            )
            created_count += 1
            _logger.debug("Created demo SLA breach alert for %s", request.reference)

        # 3. Create SLA warning alert for at-risk requests
        upcoming = date.today() + timedelta(days=2)
        at_risk_requests = Request.search(
            [
                ("incident_id", "in", incidents.ids if incidents else []),
                ("date_needed", "<=", upcoming),
                ("date_needed", ">=", date.today()),
                ("approval_state", "in", ("approved", "pending")),
                ("state", "not in", ("delivered", "dispatched")),
            ],
            limit=1,
        )
        if "sla_warning" in type_map and at_risk_requests:
            request = at_risk_requests[0]
            days_until = (request.date_needed - date.today()).days
            Alert.create(
                {
                    "alert_type_id": type_map["sla_warning"].id,
                    "priority": "high",
                    "title": f"SLA Warning: {request.reference}",
                    "description": (
                        f"Request {request.reference} is due in {days_until} day(s) "
                        f"and is not yet dispatched.\nDestination: {request.destination_area_id.name}"
                    ),
                    "incident_id": request.incident_id.id,
                    "request_id": request.id,
                    "days_until": days_until,
                }
            )
            created_count += 1
            _logger.debug("Created demo SLA warning alert for %s", request.reference)

        # 4. Create additional low stock alert for another warehouse (for health status demo)
        if "low_stock" in type_map and len(warehouses) > 1 and len(products) > 1 and incidents:
            product = products[1]
            warehouse = warehouses[1]
            incident = incidents[0]
            Alert.create(
                {
                    "alert_type_id": type_map["low_stock"].id,
                    "priority": "medium",
                    "title": f"Low Stock: {product.name}",
                    "description": (
                        f"Stock level for {product.name} at {warehouse.name} is below threshold.\n"
                        "Available: 45.00, Needed: 150.00, Threshold: 75.00"
                    ),
                    "incident_id": incident.id,
                    "warehouse_id": warehouse.id,
                    "product_id": product.id,
                    "current_value": 45.0,
                    "threshold_value": 75.0,
                }
            )
            created_count += 1

        # Run alert engine cron jobs to generate additional real alerts
        try:
            Alert._cron_check_low_stock()
            _logger.info("Ran low stock alert check")
        except Exception as e:
            _logger.warning("Low stock check failed: %s", e)

        try:
            Alert._cron_check_sla()
            _logger.info("Ran SLA alert check")
        except Exception as e:
            _logger.warning("SLA check failed: %s", e)

        try:
            Alert._cron_check_expiry()
            _logger.info("Ran expiry alert check")
        except Exception as e:
            _logger.warning("Expiry check failed: %s", e)

        # Count total alerts
        total_alert_count = Alert.search_count(
            [
                ("state", "in", ("active", "acknowledged")),
            ]
        )
        _logger.info("Demo alerts created: %d direct, %d total active", created_count, total_alert_count)

    def _generate_completed_dispatches(self, incidents):
        """Generate completed dispatch pickings with beneficiary data.

        This is critical for dashboard KPIs:
        - drims_distributed_value: computed from completed dispatches
        - drims_beneficiaries_30d: computed from beneficiary_count on dispatches

        Creates dispatches for approved requests with:
        - beneficiary_count filled (required for validation)
        - beneficiary_area_id set to destination area
        - state = 'done' (validated)
        - POD fields partially filled
        """
        Picking = self.env["stock.picking"]
        Request = self.env["spp.drims.request"]
        dispatches = Picking

        # Get the request_dispatch DRIMS type
        drims_type_dispatch = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:drims-types"),
                ("code", "=", "request_dispatch"),
            ],
            limit=1,
        )

        if not drims_type_dispatch:
            _logger.warning("request_dispatch DRIMS type not found, skipping dispatch generation")
            return dispatches

        # Find approved requests to create dispatches for
        approved_requests = Request.search(
            [
                ("incident_id", "in", incidents.ids if incidents else []),
                ("approval_state", "=", "approved"),
            ],
            limit=10,
        )  # Limit to avoid too many

        if not approved_requests:
            _logger.info("No approved requests found for dispatch generation")
            return dispatches

        # Prefetch related fields to avoid N+1 queries
        approved_requests.mapped("incident_id")
        approved_requests.mapped("destination_area_id")
        approved_requests.mapped("line_ids")
        # Prefetch product and uom for all request lines
        all_lines = approved_requests.mapped("line_ids")
        all_lines.mapped("product_id")
        all_lines.mapped("product_id.is_storable")
        all_lines.mapped("product_id.name")
        all_lines.mapped("uom_id")
        # Prefetch warehouse fields
        all_warehouses = self._get_demo_warehouses()
        all_warehouses.mapped("incident_ids")
        all_warehouses.mapped("out_type_id")
        all_warehouses.mapped("lot_stock_id")

        for request in approved_requests:
            # Get source warehouse
            all_warehouses = self._get_demo_warehouses()
            warehouses = self.env["stock.warehouse"].browse()
            for warehouse in all_warehouses:
                if request.incident_id in warehouse.incident_ids:
                    warehouses |= warehouse
            if not warehouses:
                warehouses = self._get_demo_warehouses()[:1]
            if not warehouses:
                continue

            warehouse = warehouses[0]
            picking_type = warehouse.out_type_id

            # Random beneficiary count for demo
            beneficiary_counts = [500, 750, 1000, 1500, 2000, 2500, 3000]
            beneficiary_count = random.choice(beneficiary_counts)

            # Generate POD GPS coordinates near destination area
            pod_gps = self._generate_pod_gps_for_area(request.destination_area_id)

            # Create dispatch picking
            picking_vals = {
                "picking_type_id": picking_type.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "incident_id": request.incident_id.id,
                "drims_type_id": drims_type_dispatch.id,
                "drims_request_id": request.id,
                "beneficiary_area_id": request.destination_area_id.id,
                "beneficiary_count": beneficiary_count,
                # POD fields
                "pod_received_by": f"Demo Receiver - {request.destination_area_id.name}",
                "pod_receiver_title": "Camp Coordinator",
                "pod_notes": "Demo dispatch - relief supplies delivered successfully",
            }

            # Add POD GPS if available
            if pod_gps:
                picking_vals["pod_gps_latitude"] = pod_gps[0]
                picking_vals["pod_gps_longitude"] = pod_gps[1]

            picking = Picking.create(picking_vals)

            # Create move lines from request lines
            for req_line in request.line_ids:
                # Ensure product is storable for quant support
                if not req_line.product_id.is_storable:
                    continue

                move_vals = {
                    "product_id": req_line.product_id.id,
                    "product_uom_qty": req_line.quantity_requested,
                    "product_uom": req_line.uom_id.id,
                    "picking_id": picking.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                }
                if "description_picking" in self.env["stock.move"]._fields:
                    move_vals["description_picking"] = req_line.product_id.name
                self.env["stock.move"].create(move_vals)

            # Complete the dispatch if there are moves
            if picking.move_ids:
                try:
                    picking.action_confirm()
                    picking.action_assign()

                    # Set quantities for all moves
                    for move in picking.move_ids:
                        move.quantity = move.product_uom_qty

                    # Validate the picking
                    picking.button_validate()

                    # Mark POD as confirmed
                    if picking.state == "done":
                        picking.is_pod_confirmed = True
                        picking.date_departed = fields.Datetime.now() - timedelta(hours=random.randint(1, 48))
                        picking.date_arrived = fields.Datetime.now() - timedelta(hours=random.randint(0, 1))

                    dispatches |= picking
                    _logger.debug(
                        "Created completed dispatch %s for request %s (beneficiaries: %d)",
                        picking.name,
                        request.reference,
                        beneficiary_count,
                    )
                except Exception as e:
                    _logger.warning("Failed to complete dispatch for %s: %s", request.reference, e)
                    # Delete failed picking
                    picking.unlink()

        return dispatches

    def _generate_personnel(self, incidents):
        """Generate demo deployed personnel for incidents.

        Creates variety of personnel with different:
        - Roles (coordinators, logistics officers, drivers, etc.)
        - Organizations (UN agencies, NGOs)
        - Statuses (deployed, standby, on_leave)
        - Clusters (for multi-sector coordination)
        """
        Personnel = self.env["spp.drims.personnel"]
        personnel_records = Personnel

        # Get personnel roles
        roles = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:drims:personnel-roles"),
            ]
        )
        role_list = list(roles)

        # Get OCHA clusters
        clusters = list(self._get_ocha_clusters())

        # Get organizations (donors are also organizations)
        organizations = self._get_demo_donors()

        # Get demo areas
        areas = self._get_demo_areas()

        # Get warehouses
        warehouses = list(self._get_demo_warehouses())

        if not role_list:
            _logger.warning("No personnel roles found - skipping personnel generation")
            return personnel_records

        # Sri Lankan names for realism
        first_names = [
            "Kamal",
            "Nimal",
            "Saman",
            "Chaminda",
            "Ruwan",
            "Dilani",
            "Kumari",
            "Sanduni",
            "Thisara",
            "Lakmal",
            "Priyantha",
            "Suresh",
            "Manjula",
            "Dinesh",
            "Nalaka",
            "Gayani",
            "Iresha",
            "Sachini",
            "Madhavi",
            "Ruwanthi",
        ]
        last_names = [
            "Perera",
            "Silva",
            "Fernando",
            "Wickramasinghe",
            "Jayawardena",
            "Dissanayake",
            "Bandara",
            "Rathnayake",
            "Gunasekara",
            "Wijesinghe",
            "Rajapaksa",
            "Senanayake",
            "Herath",
            "Amarasinghe",
            "Karunaratne",
        ]

        statuses = ["deployed", "deployed", "deployed", "standby", "on_leave"]  # Weighted toward deployed

        for incident in incidents:
            # Get warehouses linked to this incident
            incident_warehouses = [w for w in warehouses if incident in w.incident_ids]
            if not incident_warehouses:
                incident_warehouses = warehouses[:2] if len(warehouses) >= 2 else warehouses

            for _i in range(self.personnel_per_incident):
                # Generate realistic name
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)
                name = f"{first_name} {last_name}"

                # Random role
                role = random.choice(role_list) if role_list else None

                # Random organization (70% chance)
                org = random.choice(organizations) if organizations and random.random() < 0.7 else None

                # Random cluster (60% chance)
                cluster = random.choice(clusters) if clusters and random.random() < 0.6 else None

                # Random area
                area = random.choice(areas) if areas else None

                # Random warehouse (80% chance)
                warehouse = (
                    random.choice(incident_warehouses) if incident_warehouses and random.random() < 0.8 else None
                )

                # Random status
                status = random.choice(statuses)

                # Deployment date (within past 30 days)
                days_ago = random.randint(1, 30)
                deployment_date = date.today() - timedelta(days=days_ago)

                # Generate phone and email
                phone = f"+94 7{random.randint(1, 9)} {random.randint(100, 999)} {random.randint(1000, 9999)}"
                email_domain = org.email.split("@")[1] if org and org.email and "@" in org.email else "relief.lk"
                email = f"{first_name.lower()}.{last_name.lower()}@{email_domain}"

                personnel_vals = {
                    "name": name,
                    "incident_id": incident.id,
                    "role_id": role.id if role else False,
                    "organization_id": org.id if org else False,
                    "cluster_id": cluster.id if cluster else False,
                    "deployment_area_id": area.id if area else False,
                    "warehouse_id": warehouse.id if warehouse else False,
                    "status": status,
                    "deployment_date": deployment_date,
                    "phone": phone,
                    "email": email,
                }

                personnel = Personnel.create(personnel_vals)
                personnel_records |= personnel

        return personnel_records

    def _refresh_gis_reports(self):
        """Refresh GIS reports for choropleth visualization.

        This is called after generating demo data to refresh the GIS report
        data. The spp_gis_report module provides dynamic aggregation and
        visualization - this method triggers a data refresh for DRIMS-related
        reports.
        """
        GISReport = self.env["spp.gis.report"]

        # Find all active DRIMS-related reports
        drims_reports = GISReport.search([
            ("source_model", "in", ["spp.drims.request", "spp.hazard.incident.area"]),
            ("active", "=", True),
        ])

        if not drims_reports:
            _logger.debug("No DRIMS-related GIS reports found - skipping refresh")
            return

        # Refresh each report's data
        for report in drims_reports:
            try:
                report._refresh_data()
                _logger.info("Refreshed GIS report: %s", report.name)
            except Exception:
                _logger.exception("Failed to refresh GIS report: %s", report.name)

    def _generate_pod_gps_for_area(self, area):
        """Generate POD GPS coordinates for a destination area.

        Uses approximate district center coordinates with random offset
        to simulate delivery locations within the area.

        Args:
            area: spp.area record for the destination

        Returns:
            tuple: (latitude, longitude) or None if area not recognized
        """
        # Sri Lanka district approximate center coordinates
        # Format: area name (lowercase) -> (latitude, longitude)
        district_centers = {
            "colombo": (6.9271, 79.8612),
            "gampaha": (7.0873, 80.0144),
            "kalutara": (6.5854, 79.9607),
            "kandy": (7.2906, 80.6337),
            "matale": (7.4675, 80.6234),
            "nuwara eliya": (6.9497, 80.7891),
            "galle": (6.0535, 80.2210),
            "matara": (5.9485, 80.5353),
            "hambantota": (6.1246, 81.1185),
            "jaffna": (9.6615, 80.0255),
            "kilinochchi": (9.3803, 80.3770),
            "mannar": (8.9810, 79.9044),
            "mullaitivu": (9.2671, 80.8142),
            "vavuniya": (8.7542, 80.4982),
            "batticaloa": (7.7102, 81.6924),
            "ampara": (7.2975, 81.6820),
            "trincomalee": (8.5874, 81.2152),
            "kurunegala": (7.4863, 80.3647),
            "puttalam": (8.0362, 79.8283),
            "anuradhapura": (8.3114, 80.4037),
            "polonnaruwa": (7.9403, 81.0188),
            "badulla": (6.9934, 81.0550),
            "monaragala": (6.8728, 81.3507),
            "ratnapura": (6.6828, 80.3992),
            "kegalle": (7.2513, 80.3464),
        }

        if not area:
            return None

        # Try to match area name to district centers
        area_name = (area.draft_name or area.name or "").lower()

        for district_name, (base_lat, base_lon) in district_centers.items():
            if district_name in area_name or area_name in district_name:
                # Add random offset (±0.05 degrees ≈ ±5km)
                lat_offset = random.uniform(-0.05, 0.05)
                lon_offset = random.uniform(-0.05, 0.05)
                return (base_lat + lat_offset, base_lon + lon_offset)

        # Fallback: use Sri Lanka center with larger random offset
        # Sri Lanka approximate center: 7.8731° N, 80.7718° E
        lat_offset = random.uniform(-1.0, 1.0)
        lon_offset = random.uniform(-0.5, 0.5)
        return (7.8731 + lat_offset, 80.7718 + lon_offset)
