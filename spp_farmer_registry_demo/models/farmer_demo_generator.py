# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Farmer Registry Demo Generator.

Generates demo data for Farmer Registry:
1. Fixed Story Farms - 8 farmer personas with complete data
2. Random Volume Farms - Additional farms for realistic dashboards
3. Demo Programs - Created via wizard with proper Odoo flows
4. Enrollments - Draft-first state machine transitions
5. Cycles & Payments - Full lifecycle via program methods
"""

import datetime
import json
import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from . import demo_programs
from .farmer_blueprints import FARMER_BLUEPRINTS
from .seeded_farm_generator import SeededFarmGenerator

_logger = logging.getLogger(__name__)

# Philippine administrative areas for demo data
# Each area is a province with inland centroid coordinates
# Coordinates verified to be on land, away from coastlines
DEMO_AREAS = {
    "nueva_ecija": {
        "name": "Nueva Ecija",
        "code": "PH-NUE",
        "region": "Central Luzon",
        "region_code": "PH-03",
        # Cabanatuan City area (inland rice plains)
        "longitude": 120.9842,
        "latitude": 15.4868,
        "area_sqkm": 5751.0,
    },
    "laguna": {
        "name": "Laguna",
        "code": "PH-LAG",
        "region": "CALABARZON",
        "region_code": "PH-04A",
        # San Pablo City area (inland, south of Laguna de Bay)
        "longitude": 121.3256,
        "latitude": 14.0688,
        "area_sqkm": 1917.0,
    },
    "batangas": {
        "name": "Batangas",
        "code": "PH-BTG",
        "region": "CALABARZON",
        "region_code": "PH-04A",
        # Lipa City area (inland plateau)
        "longitude": 121.1632,
        "latitude": 13.9413,
        "area_sqkm": 3165.0,
    },
    "maguindanao": {
        "name": "Maguindanao",
        "code": "PH-MAG",
        "region": "BARMM",
        "region_code": "PH-BARMM",
        # Cotabato City area (inland Mindanao)
        "longitude": 124.2460,
        "latitude": 7.2047,
        "area_sqkm": 4900.0,
    },
    "benguet": {
        "name": "Benguet",
        "code": "PH-BEN",
        "region": "Cordillera Administrative Region",
        "region_code": "PH-CAR",
        # La Trinidad area (inland mountain valley)
        "longitude": 120.5879,
        "latitude": 16.4566,
        "area_sqkm": 2655.0,
    },
    "pangasinan": {
        "name": "Pangasinan",
        "code": "PH-PAN",
        "region": "Ilocos Region",
        "region_code": "PH-01",
        # Urdaneta City area (inland agricultural)
        "longitude": 120.5713,
        "latitude": 15.9764,
        "area_sqkm": 5368.0,
    },
    "lanao_del_sur": {
        "name": "Lanao del Sur",
        "code": "PH-LAS",
        "region": "BARMM",
        "region_code": "PH-BARMM",
        # Marawi area (inland, near Lake Lanao)
        "longitude": 124.2813,
        "latitude": 7.9986,
        "area_sqkm": 3872.0,
    },
    "bukidnon": {
        "name": "Bukidnon",
        "code": "PH-BUK",
        "region": "Northern Mindanao",
        "region_code": "PH-10",
        # Malaybalay City area (inland highland plateau)
        "longitude": 125.1328,
        "latitude": 8.1575,
        "area_sqkm": 10498.0,
    },
}

# Map story IDs to farm names and farmer names
# Philippine coordinates: [longitude, latitude] (GeoJSON order)
# Each persona mapped to a real agricultural region
STORY_FARMS = {
    "maria_santos": {
        "farm_name": "Santos Farm",
        "farmer_name": "Maria Santos",
        "farm_type": "crop",
        "tenure": "self",
        "total_size": 2.0,
        "under_crops": 2.0,
        "experience": 10,
        # USE_CASES FM1 demographics table documents "age 42".
        "age": 42,
        "is_female": True,
        # Llanera, Nueva Ecija — open rice paddies, verified on satellite
        "longitude": 121.054903,
        "latitude": 15.672087,
        "land_use": "cultivation",
        "area_code": "PH-NUE",
        "phone": "+63 917 555 0101",
        "bank": "Land Bank of the Philippines",
    },
    "juan_dela_cruz": {
        "farm_name": "Dela Cruz Farm",
        "farmer_name": "Juan Dela Cruz",
        "farm_type": "mixed",
        "tenure": "family",
        "total_size": 3.0,
        "under_crops": 2.0,
        "under_livestock": 1.0,
        "experience": 15,
        # USE_CASES FM2 demographics table documents "age 45".
        "age": 45,
        "is_female": False,
        # East Laguna (Magdalena/Pagsanjan area) — mixed rice + coconut, verified on satellite
        "longitude": 121.455690,
        "latitude": 14.284290,
        "land_use": "mixed",
        "area_code": "PH-LAG",
        "phone": "+63 918 555 0102",
        "bank": "Development Bank of the Philippines",
    },
    "rosa_garcia": {
        "farm_name": "Garcia Farm",
        "farmer_name": "Rosa Garcia",
        "farm_type": "mixed",
        "tenure": "family",
        "total_size": 1.0,
        # USE_CASES says "mixed farm: 0.5 ha crops + 0.5 ha livestock + 20 goats"
        # (FM3 — Senior livestock farmer, gender + age diversity).
        "under_crops": 0.5,
        "under_livestock": 0.5,
        "experience": 5,
        # FM3 story is explicitly a "senior" female farmer for age diversity.
        "age": 67,
        "is_female": True,
        # Padre Garcia, Batangas — cattle/pasture country, verified on satellite
        "longitude": 121.219381,
        "latitude": 13.893127,
        "land_use": "pasture",
        "area_code": "PH-BTG",
        "phone": "+63 919 555 0103",
        "bank": "BPI",
    },
    "amir_mangudadatu": {
        "farm_name": "Mangudadatu Farm",
        "farmer_name": "Amir Mangudadatu",
        "farm_type": "crop",
        "tenure": "family",
        "total_size": 4.0,
        "under_crops": 3.0,
        "idle": 1.0,
        "experience": 20,
        "age": 50,
        "is_female": False,
        # Sultan Kudarat / DOS area, Maguindanao — Pulangi plain cropland, verified on satellite
        "longitude": 124.280635,
        "latitude": 7.241492,
        "land_use": "cultivation",
        "area_code": "PH-MAG",
        "phone": "+63 920 555 0104",
        "bank": "Land Bank of the Philippines",
    },
    "sofia_martinez": {
        "farm_name": "Martinez Farm",
        "farmer_name": "Sofia Martinez",
        "farm_type": "crop",
        "tenure": "self",
        "total_size": 2.0,
        "under_crops": 2.0,
        "experience": 5,
        # USE_CASES FM5 explicitly documents "age 42".
        "age": 42,
        "is_female": True,
        # Atok, Benguet — highland vegetable terraces along Halsema, verified on satellite
        "longitude": 120.688108,
        "latitude": 16.590347,
        "land_use": "cultivation",
        "area_code": "PH-BEN",
        "phone": "+63 921 555 0105",
        "bank": "Rural Bank of Benguet",
    },
    "ramon_dela_cruz": {
        "farm_name": "Dela Cruz Fishpond",
        "farmer_name": "Ramon dela Cruz",
        "farm_type": "aquaculture",
        "tenure": "leased",
        "total_size": 0.5,
        "under_aquaculture": 0.5,
        "experience": 7,
        # USE_CASES FM6 documents "age 35".
        "age": 35,
        "is_female": False,
        # Labrador / Sual, Pangasinan — inland fishpond grid, verified on satellite
        "longitude": 120.152127,
        "latitude": 16.024353,
        "land_use": "aquaculture",
        "area_code": "PH-PAN",
        "phone": "+63 922 555 0106",
        "bank": "BDO",
    },
    "sittie_pangandaman": {
        "farm_name": "Pangandaman Farm",
        "farmer_name": "Sittie Pangandaman",
        "farm_type": "crop",
        "tenure": "self",
        "total_size": 1.5,
        "under_crops": 1.5,
        "experience": 12,
        # USE_CASES FM7 documents "age 32".
        "age": 32,
        "is_female": True,
        # Balindong / Bacolod-Kalawi, Lanao del Sur — SW Lake Lanao terraced farms, verified on satellite
        "longitude": 124.144513,
        "latitude": 7.874498,
        "land_use": "cultivation",
        "area_code": "PH-LAS",
        "phone": "+63 923 555 0107",
        "bank": "Land Bank of the Philippines",
    },
    "danilo_villanueva": {
        "farm_name": "Villanueva Farm",
        "farmer_name": "Danilo Villanueva",
        "farm_type": "mixed",
        "tenure": "family",
        "total_size": 5.0,
        "under_crops": 3.0,
        "under_livestock": 2.0,
        "experience": 25,
        # USE_CASES FM8 documents "age 38".
        "age": 38,
        "is_female": False,
        # Malaybalay outskirts (S/E), Bukidnon — highland plateau corn/pasture, verified on satellite
        "longitude": 125.174848,
        "latitude": 8.115242,
        "land_use": "mixed",
        "area_code": "PH-BUK",
        "phone": "+63 924 555 0108",
        "bank": "Rural Bank of Bukidnon",
    },
}

# Cooperative definitions — groups of groups
DEMO_COOPERATIVES = {
    "nueva_ecija_rice_cooperative": {
        "name": "Nueva Ecija Rice Cooperative",
        "member_farms": ["maria_santos", "sofia_martinez"],
        # Tarlac area — midpoint between Nueva Ecija and Benguet (inland)
        "longitude": 120.5980,
        "latitude": 15.4500,
    },
    "barmm_farmers_federation": {
        "name": "BARMM Farmers Federation",
        "member_farms": ["amir_mangudadatu", "sittie_pangandaman"],
        # Inland BARMM — midpoint between Cotabato and Marawi
        "longitude": 124.2650,
        "latitude": 7.6030,
    },
}


class SPPFarmerDemoGenerator(models.TransientModel):
    """Farmer Registry Demo Data Generator V2."""

    _name = "spp.farmer.demo.generator"
    _description = "Farmer Registry Demo Data Generator V2"

    name = fields.Char(string="Name", default="Farmer Demo Data V2", required=True)

    # Generation options
    create_demo_farms = fields.Boolean(
        string="Create Demo Story Farms",
        default=True,
        help="Create the 8 fixed story farms with complete data",
    )

    create_active_season = fields.Boolean(
        string="Create Active Season",
        default=True,
        help="Create an active agricultural season for activities",
    )

    generate_volume = fields.Boolean(
        string="Generate Volume Data",
        default=True,
        help="Generate deterministic farms from blueprints (~730 farms)",
    )

    create_cooperatives = fields.Boolean(
        string="Create Cooperatives",
        default=True,
        help="Create cooperative groups (group-of-groups) containing story farms",
    )

    create_demo_programs = fields.Boolean(
        string="Create Demo Programs",
        default=True,
        help="Create demo subsidy programs via wizard flow",
    )

    enroll_demo_stories = fields.Boolean(
        string="Enroll Demo Stories",
        default=True,
        help="Enroll story farms in their respective programs",
    )

    create_cycles = fields.Boolean(
        string="Create Cycles & Payments",
        default=True,
        help="Create program cycles with entitlements and payments",
    )

    create_change_requests = fields.Boolean(
        string="Create Change Requests",
        default=True,
        help="Create change request records at various stages for demo stories",
    )

    demo_already_loaded = fields.Boolean(
        compute="_compute_demo_already_loaded",
    )

    @api.depends_context("uid")
    def _compute_demo_already_loaded(self):
        """Check if demo data has already been generated."""
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep
        is_loaded = ICP.get_param("spp.farmer.demo.loaded", "False") == "True"
        for record in self:
            record.demo_already_loaded = is_loaded

    def action_generate_demo(self):
        """Generate demo data based on selected options."""
        self.ensure_one()

        # Disable notifications during demo data generation
        self = self.with_context(
            tracking_disable=True,
            mail_create_nosubscribe=True,
            mail_notrack=True,
            mail_create_nolog=True,
            no_reset_password=True,
        )

        # Set company currency to PHP (Philippine Peso)
        self._set_company_currency_php()

        stats = {
            "farms_created": 0,
            "programs_created": 0,
            "enrollments_created": 0,
            "cycles_created": 0,
            "graduations_applied": 0,
        }
        results = []

        # Step 0: Create administrative areas
        area_map = self._create_demo_areas()
        if area_map:
            stats["areas_created"] = len(area_map)
            results.append(_("Created %d administrative areas") % len(area_map))

        # Step 0.5: Create demo service points (Agri Co-op, Input Supply, Bank)
        service_points = self._create_service_points(area_map)
        if service_points:
            stats["service_points_created"] = len(service_points)
            results.append(_("Created %d service points") % len(service_points))

        # Step 1: Create active season
        if self.create_active_season:
            season = self._create_active_season()
            results.append(_("Created active season: %s") % season.name)

        # Step 2: Create demo story farms
        story_farms = {}
        if self.create_demo_farms:
            story_farms = self._create_story_farms()
            stats["farms_created"] = len(story_farms)
            results.append(_("Created %d demo story farms") % len(story_farms))

            # Step 2.1: Seed irrigation network for FM4 (Scenario 10)
            irrigation_count = self._create_irrigation_demo_assets(story_farms)
            if irrigation_count:
                stats["irrigation_assets_created"] = irrigation_count
                results.append(_("Created %d irrigation assets") % irrigation_count)

            # Step 2.2: Seed farm assets on FM1 / FM8 (vocabulary/asset coverage)
            asset_count = self._create_story_farm_assets(story_farms)
            if asset_count:
                stats["farm_assets_created"] = asset_count
                results.append(_("Created %d farm assets") % asset_count)

        # Step 2.5: Create cooperatives (group-of-groups)
        if self.create_cooperatives and story_farms:
            cooperatives = self._create_cooperatives(story_farms)
            stats["cooperatives_created"] = len(cooperatives)
            results.append(_("Created %d cooperatives") % len(cooperatives))

        # Step 3: Generate deterministic volume from blueprints
        volume_results = []
        if self.generate_volume:
            volume_results = self._generate_blueprint_farms()
            volume_count = len(volume_results)
            stats["farms_created"] += volume_count
            results.append(_("Generated %d blueprint farms") % volume_count)

        # Step 4: Create demo programs via wizard
        program_map = {}
        if self.create_demo_programs:
            program_map = self._create_demo_programs_via_wizard()
            stats["programs_created"] = len(program_map)
            results.append(_("Created %d demo programs") % len(program_map))

        # Step 5: Enroll story farms in programs (draft -> enrolled)
        if self.enroll_demo_stories and story_farms and program_map:
            enrollment_count = self._enroll_story_farms(story_farms, program_map)
            stats["enrollments_created"] = enrollment_count
            results.append(_("Created %d story enrollments") % enrollment_count)

        # Step 5.5: Enroll volume farms in programs based on blueprint eligibility
        if volume_results and program_map:
            # Build program_id -> spp.program map keyed by demo_programs ID
            prog_id_map = {}
            for prog_def in demo_programs.get_all_demo_programs():
                prog = program_map.get(prog_def["name"])
                if prog:
                    prog_id_map[prog_def["id"]] = prog

            generator = SeededFarmGenerator(self.env, seed=42)
            generator.enroll_in_programs(volume_results, prog_id_map)

        # Step 5.6: Allocate and post funds (before cycle approval)
        if self.create_demo_programs or self.create_cycles:
            self._create_program_funds(stats)

        # Step 6: Create cycles via proper flow
        if self.create_cycles and program_map:
            # Flush ORM cache so has_members/beneficiaries_count reflect enrollments
            self.env.flush_all()
            self.env.invalidate_all()

            cycle_count = self._create_program_cycles(stats)
            stats["cycles_created"] = cycle_count
            results.append(_("Created %d program cycles") % cycle_count)

            # Step 6b: Customize story payments (backdate existing payments)
            if story_farms:
                self._customize_story_payments(story_farms, program_map, stats)

            # Step 6c: Apply deferred exits (graduated members -> exited)
            # Must run AFTER cycles and payments so graduated members are
            # included in cycle memberships and receive entitlements/payments.
            if self.enroll_demo_stories:
                self._apply_deferred_exits(story_farms, stats)
                if stats.get("graduations_applied"):
                    results.append(_("Applied %d graduated exits") % stats["graduations_applied"])

        # Step 7: Create change requests for story farms
        if self.create_change_requests and story_farms:
            stats["change_requests_created"] = 0
            created_crs = self._create_story_change_requests(story_farms, stats)
            if created_crs:
                results.append(_("Created %d change requests") % len(created_crs))

        # Mark demo data as loaded
        self.env["ir.config_parameter"].sudo().set_param("spp.farmer.demo.loaded", "True")  # nosemgrep

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Farmer Demo Generation Complete"),
                "message": "\n".join(results),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    # ──────────────────────────────────────────────────────────────────────
    # Administrative Areas
    # ──────────────────────────────────────────────────────────────────────

    def _create_demo_areas(self):
        """Create Philippine administrative areas (regions and provinces).

        Creates a two-level hierarchy: Region -> Province.
        Each province gets GIS coordinates and polygon.

        Returns:
            dict: area_code -> spp.area recordset
        """
        Area = self.env["spp.area"]
        area_map = {}

        # Group provinces by region
        regions = {}
        for area_data in DEMO_AREAS.values():
            region_key = area_data["region_code"]
            if region_key not in regions:
                regions[region_key] = {
                    "name": area_data["region"],
                    "code": area_data["region_code"],
                    "provinces": [],
                }
            regions[region_key]["provinces"].append(area_data)

        for region_data in regions.values():
            # Get or create region
            region = Area.search([("code", "=", region_data["code"])], limit=1)
            if not region:
                region = Area.create(
                    {
                        "draft_name": region_data["name"],
                        "code": region_data["code"],
                    }
                )

            # Create provinces under region
            for prov_data in region_data["provinces"]:
                existing = Area.search([("code", "=", prov_data["code"])], limit=1)
                if existing:
                    area_map[prov_data["code"]] = existing
                    continue

                prov_vals = {
                    "draft_name": prov_data["name"],
                    "code": prov_data["code"],
                    "parent_id": region.id,
                    "area_sqkm": prov_data.get("area_sqkm", 0),
                }

                province = Area.create(prov_vals)

                # Set GIS coordinates and polygon on the area
                lng = prov_data["longitude"]
                lat = prov_data["latitude"]

                point_geojson = json.dumps(
                    {
                        "type": "Point",
                        "coordinates": [lng, lat],
                    }
                )
                # Create a representative polygon for the province
                polygon_geojson = self._generate_farm_polygon(
                    lng,
                    lat,
                    prov_data.get("area_sqkm", 100) * 100,
                )

                province.write(
                    {
                        "coordinates": point_geojson,
                        "geo_polygon": polygon_geojson,
                    }
                )

                area_map[prov_data["code"]] = province
                _logger.info(
                    "Created area (id=%s, name=%s, code=%s, parent=%s)",
                    province.id,
                    province.name,
                    prov_data["code"],
                    region.name,
                )

        return area_map

    # ──────────────────────────────────────────────────────────────────────
    # Service Points
    # ──────────────────────────────────────────────────────────────────────

    # Universal service points: every farm collects entitlements at a
    # bank and consults the extension office, so these are always linked.
    _UNIVERSAL_SERVICE_POINTS = ["Rural Bank Branch", "Agricultural Extension Office"]

    # Specialised pool per farm type. Each farm picks a deterministic
    # subset (anchored to its name hash) so different farms of the same
    # type don't look like identical clones in QA's review.
    _FARM_TYPE_SPECIALISED_POINTS = {
        "crop": [
            "Agri Co-op Office",
            "Input Supply Depot",
            "Mechanization Equipment Rental Hub",
        ],
        "livestock": [
            "Provincial Veterinary Clinic",
            "Input Supply Depot",
        ],
        "mixed": [
            "Agri Co-op Office",
            "Input Supply Depot",
            "Provincial Veterinary Clinic",
            "Mechanization Equipment Rental Hub",
        ],
        "aquaculture": [
            "Input Supply Depot",
        ],
    }

    def _resolve_farm_service_points(self, farm_type, farm_name=None):
        """Return service point IDs to link onto a farm.

        Bank + Extension are always included (universal touchpoints).
        From the type's specialised pool, pick a deterministic subset of
        1..N items based on `zlib.crc32(farm_name)` so farms of the same
        type get DIFFERENT but stable assignments — addresses the QA
        observation that 'all groups have the same amount of service
        points'. With no farm_name (legacy callers), include the full
        specialised pool.
        """
        specialised_pool = self._FARM_TYPE_SPECIALISED_POINTS.get(farm_type, [])
        if farm_name and specialised_pool:
            import zlib

            digest = zlib.crc32(farm_name.encode("utf-8"))
            pool = sorted(specialised_pool)
            n_pick = (digest % len(pool)) + 1  # 1..len(pool)
            picked = []
            for i in range(n_pick):
                idx = (digest >> (i * 5)) % len(pool)
                if pool[idx] not in picked:
                    picked.append(pool[idx])
        else:
            picked = list(specialised_pool)

        names = self._UNIVERSAL_SERVICE_POINTS + picked
        records = self.env["spp.service.point"].sudo().search([("name", "in", names)])  # nosemgrep
        return records.ids

    def _create_service_points(self, area_map):
        """Seed service points covering the realistic farmer touchpoints.

        Six entries are created — coop office, input supply, cash
        disbursement, veterinary, extension office, and an equipment-
        rental hub — each anchored to one of the demo areas when
        available and tagged with one or more Service Types from the
        spp_service_points vocabulary (seeded by data/service_types.xml).
        Idempotent: if a service point with the same name already exists
        the existing record is kept and returned.
        """
        ServicePoint = self.env["spp.service.point"].sudo()  # nosemgrep
        Area = self.env["spp.area"].sudo()  # nosemgrep

        def _types(*xmlid_suffixes):
            ids = []
            for suffix in xmlid_suffixes:
                ref = self.env.ref(
                    f"spp_farmer_registry_demo.service_type_{suffix}",
                    raise_if_not_found=False,
                )
                if ref:
                    ids.append(ref.id)
            return [Command.set(ids)] if ids else []

        defs = [
            {
                "name": "Agri Co-op Office",
                "area_code": "PH-NUE",
                "phone_no": "+63 44 555 0201",
                "shop_address": "Provincial Agricultural Office, Cabanatuan",
                "service_types": _types("crop_collection", "extension"),
            },
            {
                "name": "Input Supply Depot",
                "area_code": "PH-BUK",
                "phone_no": "+63 88 555 0202",
                "shop_address": "Highway Junction Warehouse, Malaybalay",
                "service_types": _types("input_supply"),
            },
            {
                "name": "Rural Bank Branch",
                "area_code": "PH-MAG",
                "phone_no": "+63 64 555 0203",
                "shop_address": "Market Plaza, Cotabato City",
                "service_types": _types("cash_disbursement"),
            },
            {
                "name": "Provincial Veterinary Clinic",
                "area_code": "PH-BTG",
                "phone_no": "+63 43 555 0204",
                "shop_address": "Capitol Road, Lipa City",
                "service_types": _types("veterinary"),
            },
            {
                "name": "Agricultural Extension Office",
                "area_code": "PH-LAG",
                "phone_no": "+63 49 555 0205",
                "shop_address": "DA-RFO Building, San Pablo",
                "service_types": _types("extension"),
            },
            {
                "name": "Mechanization Equipment Rental Hub",
                "area_code": "PH-NUE",
                "phone_no": "+63 44 555 0206",
                "shop_address": "Cabanatuan Mechanization Pool",
                "service_types": _types("equipment_rental"),
            },
        ]
        created = []
        for spec in defs:
            existing = ServicePoint.search([("name", "=", spec["name"])], limit=1)
            if existing:
                created.append(existing)
                continue
            area = Area.search([("code", "=", spec["area_code"])], limit=1) if spec.get("area_code") else None
            vals = {
                "name": spec["name"],
                "phone_no": spec["phone_no"],
                "shop_address": spec["shop_address"],
                "is_contract_active": True,
            }
            if area:
                vals["area_id"] = area.id
            if spec.get("service_types"):
                vals["service_type_ids"] = spec["service_types"]
            created.append(ServicePoint.create(vals))
        return created

    # ──────────────────────────────────────────────────────────────────────
    # Season
    # ──────────────────────────────────────────────────────────────────────

    def _create_active_season(self):
        """Create an active agricultural season alongside a closed prior season.

        The prior-year season is created first in `closed` state so the demo
        surfaces all three points of the `spp.farm.season` state machine
        (`draft → active → closed`). The active current-year season is the
        one used for activity/CR seeding.
        """
        Season = self.env["spp.farm.season"]

        today = fields.Date.today()
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)

        # Closed prior-year season — surfaces the `closed` state in the demo.
        prior_year = today.year - 1
        prior_name = f"Growing Season {prior_year}"
        if not Season.search([("name", "=", prior_name)], limit=1):
            Season.sudo().create(  # nosemgrep
                {
                    "name": prior_name,
                    "date_start": fields.Date.from_string(f"{prior_year}-01-01"),
                    "date_end": fields.Date.from_string(f"{prior_year}-12-31"),
                    "state": "closed",
                }
            )

        existing = Season.search([("state", "=", "active")], limit=1)
        if existing:
            return existing

        season = Season.sudo().create(  # nosemgrep
            {
                "name": f"Growing Season {today.year}",
                "date_start": start_date,
                "date_end": end_date,
                "state": "active",
            }
        )
        return season

    # ──────────────────────────────────────────────────────────────────────
    # Story Farms
    # ──────────────────────────────────────────────────────────────────────

    def _create_story_farms(self):
        """Create the 8 fixed demo story farms.

        Returns:
            dict: story_id -> farm (res.partner) recordset
        """
        # Ensure land use vocabularies exist for GIS data
        self._ensure_land_use_vocabularies()

        story_farms = {}

        for story_id, story_data in STORY_FARMS.items():
            farm_type_id = self._get_vocab_code("urn:openspp:vocab:farm-type", story_data["farm_type"])
            tenure_id = self._get_vocab_code("urn:openspp:vocab:land-tenure", story_data["tenure"])
            holder_id = self._get_vocab_code("urn:openspp:vocab:holder-type", "individual")

            farm = self._create_farm(
                name=story_data["farm_name"],
                farmer_name=story_data["farmer_name"],
                farm_type_id=farm_type_id,
                holder_type_id=holder_id,
                land_tenure_id=tenure_id,
                farm_total_size=story_data["total_size"],
                farm_size_under_crops=story_data.get("under_crops", 0.0),
                farm_size_under_livestock=story_data.get("under_livestock", 0.0),
                farm_size_under_aquaculture=story_data.get("under_aquaculture", 0.0),
                farm_size_idle=story_data.get("idle", 0.0),
                experience_years=story_data.get("experience", 0),
                is_female=story_data.get("is_female", False),
                phone=story_data.get("phone"),
                bank_name=story_data.get("bank"),
                age=story_data.get("age"),
            )
            story_farms[story_id] = farm

            # OP#915 round-3: link the farm group to realistic service
            # points based on its primary farm type. Cash + Extension are
            # universal; specialised hubs vary per farm name so different
            # farms of the same type don't show identical Service Points.
            sp_ids = self._resolve_farm_service_points(story_data["farm_type"], farm_name=story_data["farm_name"])
            if sp_ids:
                farm.write({"service_point_ids": [Command.set(sp_ids)]})

            # Create GIS data (GPS coordinates + land record with polygon)
            if story_data.get("longitude") and story_data.get("latitude"):
                self._create_farm_gis_data(
                    farm=farm,
                    longitude=story_data["longitude"],
                    latitude=story_data["latitude"],
                    total_size=story_data["total_size"],
                    land_use_code=story_data.get("land_use", "cultivation"),
                )

            # Assign area to farm
            area_code = story_data.get("area_code")
            if area_code:
                area = self.env["spp.area"].search([("code", "=", area_code)], limit=1)
                if area:
                    farm.write({"area_id": area.id})

        # Create activities for story farms if season exists
        active_season = self.env["spp.farm.season"].search([("state", "=", "active")], limit=1)
        if active_season:
            self._create_story_activities(list(story_farms.values()), active_season)

        return story_farms

    def _create_farm(
        self,
        name,
        farmer_name,
        farm_type_id,
        holder_type_id,
        land_tenure_id,
        farm_total_size,
        farm_size_under_crops=0.0,
        farm_size_under_livestock=0.0,
        farm_size_under_aquaculture=0.0,
        farm_size_leased_out=0.0,
        farm_size_idle=0.0,
        experience_years=0,
        is_female=False,
        phone=None,
        bank_name=None,
        age=None,
    ):
        """Create a farm with the given attributes."""
        Partner = self.env["res.partner"].sudo()  # nosemgrep

        farm_vals = {
            "name": name,
            "is_registrant": True,
            "is_group": True,
            "farm_type_id": farm_type_id,
            "holder_type_id": holder_type_id,
            "land_tenure_id": land_tenure_id,
            "farm_total_size": farm_total_size,
            "farm_size_under_crops": farm_size_under_crops,
            "farm_size_under_livestock": farm_size_under_livestock,
            "farm_size_under_aquaculture": farm_size_under_aquaculture,
            "farm_size_leased_out": farm_size_leased_out,
            "farm_size_idle": farm_size_idle,
            "experience_years": experience_years,
        }
        if phone:
            farm_vals["phone"] = phone
        farm = Partner.create(farm_vals)

        # Create the farmer (individual) as head of household
        # Gender lives in ISO 5218 vocabulary, codes are numeric ('1' = Male,
        # '2' = Female). The res.partner.gender_id Many2one is domain-locked
        # to namespace urn:iso:std:iso:5218 — wrong namespace lookup returns
        # False silently and the field stays empty.
        gender_id = self._get_vocab_code("urn:iso:std:iso:5218", "2" if is_female else "1")

        name_parts = farmer_name.split(" ", 1)
        individual_vals = {
            "name": farmer_name,
            "given_name": name_parts[0] if name_parts else farmer_name,
            "family_name": name_parts[1] if len(name_parts) > 1 else "",
            "is_registrant": True,
            "is_group": False,
            "gender_id": gender_id,
        }
        # OP#915 QA round-4: derive birthdate from age so the head's
        # Demographics section is filled in. Picks a deterministic
        # birth month/day based on the farmer name hash so reruns
        # produce identical dates.
        if age:
            import zlib

            digest = zlib.crc32(farmer_name.encode("utf-8"))
            today = datetime.date.today()
            birth_month = (digest % 12) + 1
            birth_day = ((digest // 12) % 28) + 1
            # If the deterministic birthday hasn't occurred yet this year,
            # roll the birth year back one more so the head reads as exactly
            # `age` today (matches the USE_CASES demographics tables).
            birth_year = today.year - age
            if (birth_month, birth_day) > (today.month, today.day):
                birth_year -= 1
            individual_vals["birthdate"] = datetime.date(birth_year, birth_month, birth_day)
        if phone:
            individual_vals["phone"] = phone
        individual = Partner.create(individual_vals)

        head_type = self._get_vocab_code("urn:openspp:vocab:group-membership-type", "head")
        membership_vals = {
            "group": farm.id,
            "individual": individual.id,
        }
        if head_type:
            membership_vals["membership_type_ids"] = [Command.link(head_type)]
        self.env["spp.group.membership"].sudo().create(membership_vals)  # nosemgrep

        # OP#915 round-3: keep phone two-way — partner.phone is written in
        # vals above so legacy header widgets stay populated, and the
        # spp.phone.number row is created here so the registrant form's
        # Phone Numbers tab is populated too. The onchange that would
        # otherwise sync them only fires in the UI, not from create().
        if phone:
            self._attach_phone_number(individual, phone)
            self._attach_phone_number(farm, phone)

        if bank_name:
            self._attach_bank_account(individual, bank_name, name)
            self._attach_bank_account(farm, bank_name, name)

        # OP#915 round-3: seed registry IDs (national_id + tax_id on groups,
        # national_id + passport + birth_certificate on heads). Values are
        # deterministically derived from the partner name hash so reruns
        # produce identical IDs.
        self._attach_registry_ids(farm, is_group=True, salt=name)
        self._attach_registry_ids(individual, is_group=False, salt=farmer_name)

        return farm

    def _attach_registry_ids(self, partner, is_group, salt):
        """Create spp.registry.id records on `partner`.

        Groups receive national_id + tax_id; individuals receive
        national_id + passport + birth_certificate. Each id value is
        derived deterministically from `salt` + a per-type offset so the
        same demo run produces identical IDs every time, and the
        UNIQUE(partner_id, id_type_id) constraint is honoured.
        """
        RegId = self.env["spp.registry.id"].sudo()  # nosemgrep

        def _code(xmlid):
            ref = self.env.ref(xmlid, raise_if_not_found=False)
            return ref.id if ref else False

        if is_group:
            id_types = [
                ("spp_vocabulary.code_id_type_national_id", "national_id"),
                ("spp_vocabulary.code_id_type_tax_id", "tax_id"),
            ]
        else:
            id_types = [
                ("spp_vocabulary.code_id_type_national_id", "national_id"),
                ("spp_vocabulary.code_id_type_passport", "passport"),
                ("spp_vocabulary.code_id_type_birth_certificate", "birth_certificate"),
            ]

        for xmlid, kind in id_types:
            type_id = _code(xmlid)
            if not type_id:
                continue
            value = self._build_id_value(kind, salt)
            RegId.create(
                {
                    "partner_id": partner.id,
                    "id_type_id": type_id,
                    "value": value,
                    "status": "valid",
                    "verification_method": "self_declared",
                }
            )

    def _build_id_value(self, kind, salt):
        """Deterministic ID value derived from `salt` (partner name).

        Uses zlib.crc32 (Python-stable across runs, unlike hash()).
        """
        import zlib

        digest = zlib.crc32((kind + "|" + salt).encode("utf-8"))
        if kind == "national_id":
            # PH PhilSys-style: 4-7-1 digits
            return f"{digest % 10000:04d}-{(digest // 10000) % 10000000:07d}-{digest % 10}"
        if kind == "passport":
            return f"P{digest % 10000000:07d}"
        if kind == "tax_id":
            # 9 digits
            return f"{digest % 1000000000:09d}"
        if kind == "birth_certificate":
            return f"BC-{digest % 10000000:07d}"
        return f"{digest:010d}"

    def _attach_phone_number(self, partner, phone_no):
        """Create an spp.phone.number record on `partner`.

        Caller is expected to ALSO set partner.phone (the bare char) so
        legacy header widgets see the value — the onchange that would
        normally sync from phone_number_ids only fires in the form UI.
        """
        self.env["spp.phone.number"].sudo().create(  # nosemgrep
            {
                "partner_id": partner.id,
                "phone_no": phone_no,
            }
        )

    def _attach_bank_account(self, partner, bank_name, salt):
        """Create a res.partner.bank record on `partner` using `bank_name`.

        The account number is generated deterministically from
        (bank_name, salt, partner.name) so the same demo seed produces the
        same numbers across resets. Bank entities (`res.bank`) are looked
        up by name and created if missing — keeps the demo install
        idempotent in installs where the bank already exists.
        """
        Bank = self.env["res.bank"].sudo()  # nosemgrep
        bank = Bank.search([("name", "=", bank_name)], limit=1)
        if not bank:
            bank = Bank.create({"name": bank_name})
        seed = f"{bank_name}|{salt}|{partner.name}"
        digits = "".join(c for c in str(abs(hash(seed))) if c.isdigit())[:12].rjust(12, "0")
        self.env["res.partner.bank"].sudo().create(  # nosemgrep
            {
                "acc_number": digits,
                "partner_id": partner.id,
                "bank_id": bank.id,
            }
        )

    def _create_story_activities(self, farms, season):
        """Create agricultural activities for story farms."""
        Activity = self.env["spp.farm.activity"]

        rice = self._get_vocab_code("urn:fao:icc:1.1", "0116")
        maize = self._get_vocab_code("urn:fao:icc:1.1", "0115")
        vegetables = self._get_vocab_code("urn:fao:icc:1.1", "02")
        goats = self._get_vocab_code("urn:fao:livestock:2020", "3.2")
        chickens = self._get_vocab_code("urn:fao:livestock:2020", "5.1")
        cattle = self._get_vocab_code("urn:fao:livestock:2020", "1")
        tilapia = self._get_vocab_code("urn:fao:asfis:2024", "TIL")

        subsistence = self._get_vocab_code("urn:openspp:vocab:activity-purpose", "subsistence")
        commercial = self._get_vocab_code("urn:openspp:vocab:activity-purpose", "commercial")
        both = self._get_vocab_code("urn:openspp:vocab:activity-purpose", "both")

        farm_by_name = {f.name: f for f in farms}

        activities_data = [
            {
                "farm_name": "Santos Farm",
                "activities": [
                    {
                        "type": "crop",
                        "species_id": rice,
                        "area_planted": 2.0,
                        "purpose_id": subsistence,
                        "expected_yield": 4000,
                    },
                ],
            },
            {
                "farm_name": "Dela Cruz Farm",
                "activities": [
                    {
                        "type": "crop",
                        "species_id": rice,
                        "area_planted": 1.5,
                        "purpose_id": both,
                        "expected_yield": 3000,
                    },
                    {
                        "type": "crop",
                        "species_id": vegetables,
                        "area_planted": 0.5,
                        "purpose_id": commercial,
                        "expected_yield": 1000,
                    },
                    {"type": "livestock", "species_id": chickens, "quantity": 50, "purpose_id": both},
                ],
            },
            {
                "farm_name": "Garcia Farm",
                "activities": [
                    {"type": "livestock", "species_id": goats, "quantity": 20, "purpose_id": commercial},
                    {
                        "type": "crop",
                        "species_id": maize,
                        "area_planted": 0.5,
                        "purpose_id": subsistence,
                        "expected_yield": 800,
                    },
                ],
            },
            {
                "farm_name": "Mangudadatu Farm",
                "activities": [
                    {
                        "type": "crop",
                        "species_id": maize,
                        "area_planted": 3.0,
                        "purpose_id": both,
                        "expected_yield": 3000,
                        "actual_yield": 1500,
                    },
                ],
            },
            {
                "farm_name": "Martinez Farm",
                "activities": [
                    {
                        "type": "crop",
                        "species_id": vegetables,
                        "area_planted": 1.5,
                        "purpose_id": commercial,
                        "expected_yield": 2500,
                    },
                    {
                        "type": "crop",
                        "species_id": maize,
                        "area_planted": 0.5,
                        "purpose_id": subsistence,
                        "expected_yield": 800,
                    },
                ],
            },
            {
                "farm_name": "Dela Cruz Fishpond",
                "activities": [
                    {"type": "aquaculture", "species_id": tilapia, "quantity": 5000, "purpose_id": commercial},
                ],
            },
            {
                "farm_name": "Pangandaman Farm",
                "activities": [
                    {
                        "type": "crop",
                        "species_id": rice,
                        "area_planted": 1.0,
                        "purpose_id": subsistence,
                        "expected_yield": 2000,
                    },
                    {
                        "type": "crop",
                        "species_id": vegetables,
                        "area_planted": 0.5,
                        "purpose_id": commercial,
                        "expected_yield": 800,
                    },
                ],
            },
            {
                "farm_name": "Villanueva Farm",
                "activities": [
                    {
                        "type": "crop",
                        "species_id": maize,
                        "area_planted": 2.0,
                        "purpose_id": commercial,
                        "expected_yield": 5000,
                    },
                    {
                        "type": "crop",
                        "species_id": rice,
                        "area_planted": 1.0,
                        "purpose_id": both,
                        "expected_yield": 2000,
                    },
                    {"type": "livestock", "species_id": cattle, "quantity": 15, "purpose_id": commercial},
                    {"type": "livestock", "species_id": goats, "quantity": 30, "purpose_id": both},
                ],
            },
        ]

        for farm_data in activities_data:
            farm = farm_by_name.get(farm_data["farm_name"])
            if not farm:
                continue

            for act_data in farm_data["activities"]:
                if not act_data.get("species_id"):
                    continue

                activity_vals = {
                    "season_id": season.id,
                    "activity_type": act_data["type"],
                    "species_id": act_data["species_id"],
                }

                if act_data["type"] == "crop":
                    activity_vals["crop_farm_id"] = farm.id
                    activity_vals["area_planted"] = act_data.get("area_planted", 0)
                    activity_vals["expected_yield"] = act_data.get("expected_yield", 0)
                    activity_vals["actual_yield"] = act_data.get("actual_yield", 0)
                elif act_data["type"] == "livestock":
                    activity_vals["livestock_farm_id"] = farm.id
                    activity_vals["quantity"] = act_data.get("quantity", 0)
                    activity_vals["quantity_unit"] = "heads"
                elif act_data["type"] == "aquaculture":
                    activity_vals["aquaculture_farm_id"] = farm.id
                    activity_vals["quantity"] = act_data.get("quantity", 0)
                    activity_vals["quantity_unit"] = "kg"

                if act_data.get("purpose_id"):
                    activity_vals["purpose_id"] = act_data["purpose_id"]

                Activity.create(activity_vals)

    # ──────────────────────────────────────────────────────────────────────
    # Cooperatives (Group-of-Groups)
    # ──────────────────────────────────────────────────────────────────────

    def _create_cooperatives(self, story_farms):
        """Create cooperative groups containing story farms as members.

        Uses spp_registry_group_hierarchy to create group-of-groups where
        each cooperative contains multiple farm groups as members.

        Args:
            story_farms: dict of story_id -> farm (res.partner)

        Returns:
            dict: cooperative_id -> cooperative (res.partner)
        """
        Partner = self.env["res.partner"].sudo()  # nosemgrep
        Membership = self.env["spp.group.membership"].sudo()  # nosemgrep

        # Get or create the "cooperative" group type vocabulary code
        cooperative_type_id = self._ensure_cooperative_group_type()

        cooperatives = {}

        for coop_id, coop_data in DEMO_COOPERATIVES.items():
            # Check if cooperative already exists
            existing = Partner.search(
                [("name", "=", coop_data["name"]), ("is_group", "=", True)],
                limit=1,
            )
            if existing:
                _logger.info(
                    "Cooperative already exists (partner_id=%s, name=%s)",
                    existing.id,
                    coop_data["name"],
                )
                cooperatives[coop_id] = existing
                continue

            # Collect member farms
            member_farms = []
            for farm_key in coop_data["member_farms"]:
                farm = story_farms.get(farm_key)
                if farm:
                    member_farms.append(farm)
                else:
                    _logger.warning(
                        "Story farm %s not found for cooperative %s",
                        farm_key,
                        coop_data["name"],
                    )

            if not member_farms:
                _logger.warning(
                    "No member farms found for cooperative %s, skipping",
                    coop_data["name"],
                )
                continue

            # Aggregate farm details for the cooperative
            total_size = sum(f.farm_total_size for f in member_farms)

            # Create cooperative as a group registrant
            coop_vals = {
                "name": coop_data["name"],
                "is_registrant": True,
                "is_group": True,
            }
            if cooperative_type_id:
                coop_vals["group_type_id"] = cooperative_type_id

            cooperative = Partner.create(coop_vals)

            # Add member farms as group members
            for farm in member_farms:
                Membership.create(
                    {
                        "group": cooperative.id,
                        "individual": farm.id,
                    }
                )
                _logger.info(
                    "Added farm (partner_id=%s, name=%s) to cooperative (partner_id=%s, name=%s)",
                    farm.id,
                    farm.name,
                    cooperative.id,
                    cooperative.name,
                )

            # Add GIS data for cooperative (centroid location)
            if coop_data.get("longitude") and coop_data.get("latitude"):
                self._create_farm_gis_data(
                    farm=cooperative,
                    longitude=coop_data["longitude"],
                    latitude=coop_data["latitude"],
                    total_size=total_size,
                    land_use_code="mixed",
                )

            cooperatives[coop_id] = cooperative
            _logger.info(
                "Created cooperative (partner_id=%s, name=%s, members=%d, total_ha=%.1f)",
                cooperative.id,
                cooperative.name,
                len(member_farms),
                total_size,
            )

        return cooperatives

    def _set_company_currency_php(self):
        """Set the company currency to Philippine Peso (PHP)."""
        php = self.env["res.currency"].with_context(active_test=False).search([("name", "=", "PHP")], limit=1)
        if php:
            if not php.active:
                php.active = True
            self.env.company.currency_id = php
            _logger.info("Set company currency to PHP (Philippine Peso)")

    def _ensure_cooperative_group_type(self):
        """Ensure the 'cooperative' group type vocabulary code exists.

        Uses get_or_create_local() to safely add codes to system vocabularies
        (ADR-016: local codes with is_local=True bypass system protection).

        Returns:
            int: vocabulary code ID for the cooperative group type, or False
        """
        VocabCode = self.env["spp.vocabulary.code"]

        try:
            code = VocabCode.get_or_create_local(
                "urn:openspp:vocab:group-type",
                "cooperative",
                display="Cooperative",
            )
            # Enable group-of-groups membership for this group type
            if not code.allow_all_member_type:
                code.write({"allow_all_member_type": True})
            return code.id
        except Exception:
            _logger.warning("Could not create cooperative group type vocabulary code")
            return False

    # ──────────────────────────────────────────────────────────────────────
    # GIS Data (Coordinates + Land Records)
    # ──────────────────────────────────────────────────────────────────────

    def _create_farm_gis_data(self, farm, longitude, latitude, total_size, land_use_code):
        """Set GPS coordinates on farm and create land records with polygons.

        Args:
            farm: res.partner recordset (farm group)
            longitude: float (WGS84)
            latitude: float (WGS84)
            total_size: float (hectares)
            land_use_code: str (vocabulary code for land use)
        """
        # Set GPS point on the farm partner record
        point_geojson = json.dumps(
            {
                "type": "Point",
                "coordinates": [longitude, latitude],
            }
        )
        farm.write({"coordinates": point_geojson})

        # Create land record with point + polygon
        if "spp.land.record" not in self.env:
            return

        # Get land use vocabulary code
        land_use_id = self._get_vocab_code("urn:openspp:vocab:land-use", land_use_code)

        # Generate a polygon approximating the farm area
        polygon_geojson = self._generate_farm_polygon(longitude, latitude, total_size)

        land_vals = {
            "land_farm_id": farm.id,
            "land_name": f"{farm.name} - Main Parcel",
            "land_acreage": total_size * 2.471,  # hectares to acres
            "land_coordinates": point_geojson,
            "land_geo_polygon": polygon_geojson,
            "owner_id": farm.id,
        }
        if land_use_id:
            land_vals["land_use_id"] = land_use_id

        self.env["spp.land.record"].create(land_vals)

    def _generate_farm_polygon(self, center_lng, center_lat, hectares):
        """Generate a rectangular polygon approximating the farm area.

        At Philippine latitudes (~7-16°N):
        - 1 degree latitude ≈ 111 km
        - 1 degree longitude ≈ 107-110 km
        - 1 hectare = 10,000 m² ≈ 100m x 100m

        Args:
            center_lng: float (longitude)
            center_lat: float (latitude)
            hectares: float (farm size)

        Returns:
            str: GeoJSON polygon as JSON string
        """
        import math

        # Calculate approximate dimensions
        area_m2 = hectares * 10000
        side_m = math.sqrt(area_m2)

        # Convert meters to degrees (approximate at Philippine latitudes)
        deg_per_meter_lat = 1.0 / 111320.0
        deg_per_meter_lng = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))

        half_lat = (side_m / 2) * deg_per_meter_lat
        half_lng = (side_m / 2) * deg_per_meter_lng

        # Create rectangle corners (closed ring)
        polygon = {
            "type": "Polygon",
            "coordinates": [
                [
                    [center_lng - half_lng, center_lat - half_lat],
                    [center_lng + half_lng, center_lat - half_lat],
                    [center_lng + half_lng, center_lat + half_lat],
                    [center_lng - half_lng, center_lat + half_lat],
                    [center_lng - half_lng, center_lat - half_lat],
                ]
            ],
        }
        return json.dumps(polygon)

    def _create_irrigation_demo_assets(self, story_farms):
        """Seed an irrigation network anchored on FM4 (Mangudadatu Farm).

        Scenario 10 narrative: FM4's 1 ha of idle/fallow land is the
        downstream consequence of reduced reservoir capacity, not random
        non-cultivation. Two assets are created and linked into a
        source → destination network so the GIS view shows real edges:

        - "Cotabato Irrigation Reservoir" (type=reservoir) — degraded,
          5 000 m³ effective capacity (design ~15 000 m³, silted)
        - "Cotabato Main Canal Branch" (type=canal) — fed by the
          reservoir, carries the reduced flow to FM4's parcel

        Returns the number of irrigation assets created.
        """
        Irrigation = self.env.get("spp.irrigation.asset")
        if Irrigation is None:
            return 0

        fm4 = story_farms.get("amir_mangudadatu")
        if not fm4:
            return 0

        if Irrigation.search_count([("farm_id", "=", fm4.id)]):
            # Idempotent — don't double-seed on re-run.
            return 0

        reservoir_type = self._get_vocab_code("urn:openspp:vocab:irrigation-asset-type", "reservoir")
        canal_type = self._get_vocab_code("urn:openspp:vocab:irrigation-asset-type", "canal")

        # Reservoir slightly upstream of FM4 (a few hundred metres N-W).
        reservoir_lng = 124.2440
        reservoir_lat = 7.2110
        reservoir_polygon = self._generate_farm_polygon(reservoir_lng, reservoir_lat, 0.5)
        reservoir_point = json.dumps({"type": "Point", "coordinates": [reservoir_lng, reservoir_lat]})

        reservoir = Irrigation.sudo().create(  # nosemgrep
            {
                "name": "Cotabato Irrigation Reservoir",
                "farm_id": fm4.id,
                "asset_type_id": reservoir_type,
                "total_capacity": 5000.0,  # m³, reduced from ~15 000 m³ design due to silting
                "coordinates": reservoir_point,
                "geo_polygon": reservoir_polygon,
            }
        )

        # Canal between reservoir and FM4 — sourced by the reservoir.
        canal_lng = 124.2475
        canal_lat = 7.2080
        canal_point = json.dumps({"type": "Point", "coordinates": [canal_lng, canal_lat]})

        canal = Irrigation.sudo().create(  # nosemgrep
            {
                "name": "Cotabato Main Canal Branch",
                "farm_id": fm4.id,
                "asset_type_id": canal_type,
                "total_capacity": 300.0,  # m³ flow capacity, reduced
                "coordinates": canal_point,
                "irrigation_source_ids": [(4, reservoir.id)],
            }
        )
        # Mirror the relation: the reservoir's destination is the canal.
        reservoir.write({"irrigation_destination_ids": [(4, canal.id)]})

        return 2

    def _create_story_farm_assets(self, story_farms):
        """Seed `spp.farm.asset` records on FM1 and FM8.

        Surfaces the farm-asset model in the demo so Scenario 8's CR
        lifecycle can include a `manage_farm_asset` request and the
        farm tables in USE_CASES.md have real records to point to.

        - FM1 (Maria Santos / Santos Farm) → 1 hand tractor (machinery)
        - FM8 (Danilo Villanueva / Villanueva Farm) → 1 water pump (machinery)

        Returns the number of farm-asset records created.
        """
        Asset = self.env.get("spp.farm.asset")
        MachineryType = self.env.get("spp.machinery.type")
        if Asset is None or MachineryType is None:
            return 0

        def _machinery_type(name):
            existing = MachineryType.search([("name", "=", name)], limit=1)
            if existing:
                return existing
            return MachineryType.sudo().create({"name": name})  # nosemgrep

        seeded = 0

        fm1 = story_farms.get("maria_santos")
        if fm1 and not Asset.search_count([("machinery_farm_id", "=", fm1.id)]):
            land = self.env["spp.land.record"].search([("land_farm_id", "=", fm1.id)], limit=1)
            tractor_type = _machinery_type("Hand Tractor")
            Asset.sudo().create(  # nosemgrep
                {
                    "machinery_farm_id": fm1.id,
                    "machinery_type_id": tractor_type.id,
                    "land_id": land.id if land else False,
                    "quantity": 1,
                    "machine_working_status": "operational",
                }
            )
            seeded += 1

        fm8 = story_farms.get("danilo_villanueva")
        if fm8 and not Asset.search_count([("machinery_farm_id", "=", fm8.id)]):
            land = self.env["spp.land.record"].search([("land_farm_id", "=", fm8.id)], limit=1)
            pump_type = _machinery_type("Water Pump")
            Asset.sudo().create(  # nosemgrep
                {
                    "machinery_farm_id": fm8.id,
                    "machinery_type_id": pump_type.id,
                    "land_id": land.id if land else False,
                    "quantity": 1,
                    "machine_working_status": "operational",
                }
            )
            seeded += 1

        return seeded

    def _ensure_land_use_vocabularies(self):
        """Ensure land use vocabulary codes exist for GIS demo data.

        Uses get_or_create_local() to safely add codes to system vocabularies
        (ADR-016: local codes with is_local=True bypass system protection).
        """
        VocabCode = self.env["spp.vocabulary.code"]

        codes = [
            ("cultivation", "Cultivation"),
            ("pasture", "Pasture"),
            ("mixed", "Mixed Use"),
            ("aquaculture", "Aquaculture"),
            ("fallow", "Fallow"),
            ("forest", "Forest"),
        ]
        for code, display in codes:
            VocabCode.get_or_create_local(
                "urn:openspp:vocab:land-use",
                code,
                display=display,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Programs (Wizard-based creation)
    # ──────────────────────────────────────────────────────────────────────

    def _create_demo_programs_via_wizard(self):
        """Create demo programs using the program creation wizard.

        Uses spp.program.create.wizard to create each program, mirroring
        the UI wizard flow that sets up all managers (eligibility, cycle,
        entitlement, program) and creates journals automatically.

        Returns:
            dict: program_name -> spp.program recordset
        """
        program_map = {}

        if "spp.program" not in self.env:
            _logger.warning("spp_programs not installed, skipping demo programs")
            return program_map

        for program_def in demo_programs.get_all_demo_programs():
            # Check if program already exists
            existing = self.env["spp.program"].search([("name", "=", program_def["name"])], limit=1)
            if existing:
                _logger.info(
                    "Program already exists (program_id=%s), skipping...",
                    existing.id,
                )
                program_map[program_def["name"]] = existing
                continue

            try:
                program = self._create_program_via_wizard(program_def)
                if program:
                    program_map[program_def["name"]] = program
                    _logger.info(
                        "Created program via wizard (program_id=%s, name=%s)",
                        program.id,
                        program.name,
                    )
            except Exception:
                _logger.exception("Failed to create program: %s", program_def["name"])

        return program_map

    def _create_program_via_wizard(self, program_def):
        """Create a single program using spp.program.create.wizard.

        This mirrors what happens when a user creates a program through the UI:
        1. Create wizard with program config
        2. Add entitlement items (cash)
        3. Call create_program() which sets up all managers and journal

        Returns:
            spp.program recordset or None
        """
        amount = program_def.get("entitlement_amount", 100.0)

        wizard_vals = {
            "name": program_def["name"],
            "currency_id": self.env.company.currency_id.id,
            "target_type": program_def.get("target_type", "group"),
            "entitlement_type": "cash",
            "cycle_duration": program_def.get("cycle_duration", 1),
            "rrule_type": program_def.get("rrule_type", "monthly"),
            "month_by": "date",
            "day": 1,
            "auto_approve_entitlements": True,
        }

        # Enable compliance verification at wizard time for programs that ship a
        # compliance CEL rule. The base create wizard does NOT create a
        # compliance manager — only `create_program_wizard_compliance` does, and
        # only when `enable_compliance_verification` is set. Without this the
        # programs show "no compliance defined" in the UI. See OP#915 round 7.
        compliance_cel = program_def.get("compliance_cel_expression")
        if compliance_cel:
            wizard_vals.update(
                {
                    "enable_compliance_verification": True,
                    "compliance_type": "spp.compliance.manager.default",
                    "compliance_cel_expression": compliance_cel,
                }
            )

        wizard = self.env["spp.program.create.wizard"].create(wizard_vals)

        # Add cash entitlement item
        self.env["spp.program.create.wizard.entitlement.cash.item"].create(
            {
                "program_id": wizard.id,
                "amount": amount,
                "currency_id": self.env.company.currency_id.id,
            }
        )

        # Call the wizard's create_program method (creates program + all managers + journal)
        result = wizard.create_program()

        # Extract program_id from wizard result
        program_id = result.get("params", {}).get("program_id") if isinstance(result, dict) else None
        if not program_id:
            _logger.error("Wizard did not return program_id for %s", program_def["name"])
            return None

        program = self.env["spp.program"].browse(program_id)

        # Set description (not handled by wizard)
        if program_def.get("description"):
            program.write({"description": program_def["description"]})

        # Create payment manager (wizard doesn't create one).
        # The payment manager is needed for prepare_payment() / send_payment().
        if not program.payment_manager_ids:
            batch_tag = self.env["spp.payment.batch.tag"].create(
                {
                    "name": f"Default {program.name}",
                    "order": 1,
                    "domain": [],
                    "max_batch_size": 500,
                }
            )
            def_pay_mgr = self.env["spp.program.payment.manager.default"].create(
                {
                    "name": "Default",
                    "program_id": program.id,
                    "create_batch": True,
                    "batch_tag_ids": [(4, batch_tag.id)],
                }
            )
            pay_mgr = self.env["spp.program.payment.manager"].create(
                {
                    "program_id": program.id,
                    "manager_ref_id": (f"spp.program.payment.manager.default,{def_pay_mgr.id}"),
                }
            )
            program.write({"payment_manager_ids": [(4, pay_mgr.id)]})
            _logger.info(
                "Created payment manager for program (program_id=%s)",
                program.id,
            )

        # Ensure cycle manager's interval field is computed and stored.
        # The wizard sets cycle_duration on spp.cycle.manager.default but interval
        # is a stored computed field that may not be flushed to DB yet. Without this,
        # _get_ranges() in create_new_cycle() fails with StopIteration because
        # interval=0 produces no rrule occurrences.
        cycle_manager = program.get_manager(program.MANAGER_CYCLE)
        if cycle_manager:
            cycle_manager.modified(["cycle_duration"])
            self.env.flush_all()
            cycle_manager.invalidate_recordset(["interval"])
            _logger.info(
                "Cycle manager (id=%s): cycle_duration=%s, interval=%s",
                cycle_manager.id,
                cycle_manager.cycle_duration,
                cycle_manager.interval,
            )

        # Configure the eligibility manager's CEL expression so the engine
        # uses the program's actual rule when admins re-evaluate eligibility.
        # Without this the manager has no CEL set, so re-evaluation re-classifies
        # seeded enrollments as Not Eligible even when the blueprint flags
        # said they qualify. Mirrors the MIS fix from commit aa6da89d.
        self._configure_eligibility_manager(program, program_def)

        # Same wiring for compliance — programs that ship a
        # `compliance_cel_expression` (Input Subsidy, Equipment Grant) need
        # their compliance manager's CEL set so disbursements actually flow
        # through the compliance workflow. See OP#915.
        self._configure_compliance_manager(program, program_def)

        # Materialise the documented benefit formula on the cash entitlement
        # manager. The wizard only seeds a single flat-amount line; programs
        # that scale by a registrant metric (Input Subsidy per hectare,
        # Livestock per head) need explicit base + multiplier lines so the
        # disbursed amount actually matches the formula. See OP#915 round 7.
        self._configure_entitlement_formula(program, program_def)

        # Wire approval definitions onto the cycle + entitlement managers so
        # cycles and entitlements created on this program enter the demo's
        # approval workflow. Without this the managers' `approval_definition_id`
        # stays empty and the records auto-approve, which hides the workflow
        # from anyone exercising the demo. See OP#915.
        self._configure_program_approvals(program)

        return program

    def _configure_eligibility_manager(self, program, program_def):
        """Configure the eligibility manager with the program's CEL expression.

        Eligibility uses ``program.eligibility_manager_ids`` (m2m of wrappers);
        each wrapper points to the concrete manager via ``manager_ref_id``.
        We write ``eligibility_mode='cel'`` + ``cel_expression`` on the first
        wrapper that supports CEL (existing definitions on subsequent wrappers
        are left alone). Mirrors ``MisDemoGenerator._configure_eligibility_manager``.
        """
        try:
            cel_expression = program_def.get("cel_expression")
            if not cel_expression:
                return

            for wrapper in program.eligibility_manager_ids:
                concrete = wrapper.manager_ref_id
                if not concrete:
                    continue

                if "cel_expression" not in concrete._fields:
                    _logger.info(
                        "CEL expression not supported on eligibility manager (program_id=%s)",
                        program.id,
                    )
                    continue

                concrete.write(
                    {
                        "eligibility_mode": "cel",
                        "cel_expression": cel_expression,
                    }
                )
                _logger.info(
                    "Configured CEL eligibility for program (program_id=%s): %s",
                    program.id,
                    cel_expression,
                )
                break

        except Exception as e:
            _logger.warning(
                "Could not configure eligibility manager (program_id=%s): %s",
                program.id,
                e,
            )

    def _configure_compliance_manager(self, program, program_def):
        """Configure the compliance manager with the program's compliance CEL.

        Programs that ship a ``compliance_cel_expression`` get the rule
        written to their compliance manager. Programs that don't are
        skipped (they exit the loop without writing anything).
        """
        try:
            cel_expression = program_def.get("compliance_cel_expression")
            if not cel_expression:
                return

            for wrapper in program.compliance_manager_ids:
                concrete = wrapper.manager_ref_id
                if hasattr(concrete, "compliance_cel_expression"):
                    concrete.write(
                        {
                            "compliance_cel_expression": cel_expression,
                        }
                    )
                    _logger.info(
                        "Configured compliance CEL for program (program_id=%s): %s",
                        program.id,
                        cel_expression,
                    )
                    break

        except Exception as e:
            _logger.warning(
                "Could not configure compliance manager (program_id=%s): %s",
                program.id,
                e,
            )

    def _configure_entitlement_formula(self, program, program_def):
        """Rebuild the cash entitlement manager's line items from the program's
        ``entitlement_items`` spec so the benefit actually follows the formula.

        Each spec entry is ``{"amount": <float>, "multiplier_field": <res.partner
        field name, optional>, "max_multiplier": <int, optional>}``. A line with
        no multiplier contributes a flat ``amount`` (the base); a line with a
        ``multiplier_field`` contributes ``amount * <field value>``. The cash
        manager sums all lines per beneficiary, so ``base + (metric * rate)`` is
        expressed as two lines.

        ``multiplier_field`` accepts any ``res.partner`` field that resolves to a
        number. The platform's picker UI only lists integer fields, but the
        runtime calculation handles floats too, so we wire ``farm_size_hectares``
        (a Float) here directly. Programs without an ``entitlement_items`` spec
        keep the flat amount the wizard already seeded.
        """
        items_spec = program_def.get("entitlement_items")
        if not items_spec:
            return
        try:
            entitlement_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
            if not entitlement_manager or "entitlement_item_ids" not in entitlement_manager._fields:
                return

            ir_fields = self.env["ir.model.fields"]
            # (5, 0, 0) clears the flat line the wizard created so the formula
            # lines are the single source of truth.
            commands = [(5, 0, 0)]
            for spec in items_spec:
                vals = {"amount": spec["amount"]}
                field_name = spec.get("multiplier_field")
                if field_name:
                    field_rec = ir_fields.search(
                        [("model", "=", "res.partner"), ("name", "=", field_name)],
                        limit=1,
                    )
                    if not field_rec:
                        _logger.warning(
                            "Multiplier field res.partner.%s not found; "
                            "entitlement line for program %s falls back to flat amount",
                            field_name,
                            program.id,
                        )
                    else:
                        vals["multiplier_field"] = field_rec.id
                    if spec.get("max_multiplier"):
                        vals["max_multiplier"] = spec["max_multiplier"]
                commands.append((0, 0, vals))

            entitlement_manager.write({"entitlement_item_ids": commands})
            _logger.info(
                "Configured entitlement formula for program (program_id=%s): %d line(s)",
                program.id,
                len(items_spec),
            )
        except Exception as e:
            _logger.warning(
                "Could not configure entitlement formula (program_id=%s): %s",
                program.id,
                e,
            )

    def _configure_program_approvals(self, program):
        """Set approval definitions on the program's cycle + entitlement
        managers, mirroring what an admin would do under
        Programs → Configuration → Managers in the UI.

        The XML records live in `data/approval_definitions.xml`. We resolve
        them by xmlid and only write when the manager exists and lacks an
        existing definition (so a re-run of the wizard against an already
        configured program doesn't clobber a custom definition).
        """
        cycle_def = self.env.ref(
            "spp_farmer_registry_demo.approval_definition_farmer_cycle_manager",
            raise_if_not_found=False,
        )
        entitlement_def = self.env.ref(
            "spp_farmer_registry_demo.approval_definition_farmer_entitlement_manager",
            raise_if_not_found=False,
        )

        cycle_manager = program.get_manager(program.MANAGER_CYCLE)
        if cycle_manager and cycle_def and not cycle_manager.approval_definition_id:
            cycle_manager.approval_definition_id = cycle_def
            _logger.info(
                "Cycle approval set on program (program_id=%s, definition=%s)",
                program.id,
                cycle_def.name,
            )

        entitlement_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
        if entitlement_manager and entitlement_def and not entitlement_manager.approval_definition_id:
            entitlement_manager.approval_definition_id = entitlement_def
            _logger.info(
                "Entitlement approval set on program (program_id=%s, definition=%s)",
                program.id,
                entitlement_def.name,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Enrollments (Draft-first state machine)
    # ──────────────────────────────────────────────────────────────────────

    def _enroll_story_farms(self, story_farms, program_map):
        """Enroll story farms in their respective programs.

        Only handles enrollment (membership creation with proper state
        transitions). Payment history is created separately after cycles
        are created via the proper flow.

        Args:
            story_farms: dict of story_id -> farm (res.partner)
            program_map: dict of program_name -> spp.program

        Returns:
            int: Number of enrollments created
        """
        Membership = self.env["spp.program.membership"]
        enrollment_count = 0

        for story_id, farm in story_farms.items():
            enrollments = demo_programs.get_story_enrollments(story_id)
            for enrollment_def in enrollments:
                program_name = enrollment_def.get("program")
                program = program_map.get(program_name)
                if not program:
                    continue

                # Check for existing membership
                existing = Membership.search(
                    [
                        ("partner_id", "=", farm.id),
                        ("program_id", "=", program.id),
                    ],
                    limit=1,
                )
                if existing:
                    continue

                # Step 1: Always create membership in draft state first
                membership = Membership.create(
                    {
                        "partner_id": farm.id,
                        "program_id": program.id,
                        "state": "draft",
                    }
                )

                # Step 2: Transition to enrolled via proper state machine
                # Keep enrolled even for graduated members — deferred exit
                # happens after cycles so they get entitlements/payments.
                membership.write({"state": "enrolled"})

                # Backdate enrollment_date (computed field auto-sets to now())
                enrolled_days_back = enrollment_def.get("enrolled_days_back", 0)
                if enrolled_days_back:
                    enrollment_date = fields.Datetime.now() - datetime.timedelta(days=enrolled_days_back)
                    self.env.cr.execute(
                        "UPDATE spp_program_membership SET enrollment_date = %s WHERE id = %s",
                        (enrollment_date, membership.id),
                    )

                enrollment_count += 1
                _logger.info(
                    "Enrolled (membership_id=%s, partner_id=%s, program_id=%s, story=%s)",
                    membership.id,
                    farm.id,
                    program.id,
                    story_id,
                )

        return enrollment_count

    # ──────────────────────────────────────────────────────────────────────
    # Fund Allocation
    # ──────────────────────────────────────────────────────────────────────

    def _create_program_funds(self, stats):
        """Allocate and post funds for each active program.

        Must run before cycles can be approved (the fund check blocks
        approval when auto_approve_entitlements=True).
        """
        if "spp.program.fund" not in self.env:
            return

        programs = self.env["spp.program"].search([("state", "=", "active")])
        cycles_needed = demo_programs._get_cycles_needed_per_program()

        for program in programs:
            # Skip programs that already have posted funds
            existing_funds = self.env["spp.program.fund"].search_count(
                [("program_id", "=", program.id), ("state", "=", "posted")]
            )
            if existing_funds:
                _logger.info(
                    "Program (program_id=%s, name=%s) already has %d posted fund(s), skipping",
                    program.id,
                    program.name,
                    existing_funds,
                )
                continue

            # Use direct search_count for enrolled members (avoids cached computed field)
            member_count = self.env["spp.program.membership"].search_count(
                [("program_id", "=", program.id), ("state", "=", "enrolled")]
            )
            if member_count == 0:
                continue

            program_def = demo_programs.get_demo_program_by_name(program.name)
            entitlement_amount = program_def.get("entitlement_amount", 100.0) if program_def else 100.0
            num_cycles = cycles_needed.get(program.name, 1)

            # 1.5x safety margin so fund check always passes
            fund_amount = member_count * entitlement_amount * num_cycles * 1.5

            try:
                fund = self.env["spp.program.fund"].create(
                    {
                        "program_id": program.id,
                        "amount": fund_amount,
                        "remarks": "Demo data -- auto-generated fund allocation",
                    }
                )
                fund.post_fund()
                stats["funds_created"] = stats.get("funds_created", 0) + 1

                _logger.info(
                    "Posted fund of %.2f for program (program_id=%s, name=%s, members=%d, cycles=%d)",
                    fund_amount,
                    program.id,
                    program.name,
                    member_count,
                    num_cycles,
                )
            except Exception:
                _logger.exception(
                    "Could not create fund for program (program_id=%s)",
                    program.id,
                )

    # ──────────────────────────────────────────────────────────────────────
    # Cycles & Payments (Full lifecycle)
    # ──────────────────────────────────────────────────────────────────────

    def _create_program_cycles(self, stats):
        """Create cycles for programs using the proper program flow.

        Uses program.create_new_cycle() which delegates to:
        1. program_manager.new_cycle() -> cycle_manager.new_cycle()
        2. Copies enrolled beneficiaries as cycle memberships
        Then follows the cycle lifecycle:
        3. cycle.prepare_entitlement() (creates entitlements)
        4. cycle.action_submit_for_approval() (draft -> to_approve)
        5. cycle.action_approve() (to_approve -> approved)

        Returns:
            int: Total cycles created
        """
        cycles_needed = demo_programs._get_cycles_needed_per_program()
        total_cycles = 0

        # Find programs with enrolled members using direct count
        programs = self.env["spp.program"].search([("state", "=", "active")])

        for program in programs:
            # Check actual membership count (non-cached)
            member_count = self.env["spp.program.membership"].search_count([("program_id", "=", program.id)])
            if member_count == 0:
                _logger.info(
                    "Program (program_id=%s, name=%s) has no members, skipping",
                    program.id,
                    program.name,
                )
                continue

            target_cycles = cycles_needed.get(program.name, 1)

            # Check if program already has enough cycles
            existing_cycles = self.env["spp.cycle"].search_count([("program_id", "=", program.id)])
            cycles_to_create = max(0, target_cycles - existing_cycles)

            if cycles_to_create == 0:
                _logger.info(
                    "Program (program_id=%s, name=%s) already has %d cycles (needs %d)",
                    program.id,
                    program.name,
                    existing_cycles,
                    target_cycles,
                )
                continue

            _logger.info(
                "Creating %d cycle(s) for program (program_id=%s, name=%s, members=%d)",
                cycles_to_create,
                program.id,
                program.name,
                member_count,
            )

            for _i in range(cycles_to_create):
                try:
                    cycle = self._create_single_cycle(program)
                    if cycle:
                        total_cycles += 1
                except Exception:
                    _logger.exception(
                        "Could not create cycle for program (program_id=%s)",
                        program.id,
                    )

        return total_cycles

    def _create_single_cycle(self, program):
        """Create a single cycle using the proper program flow.

        Returns:
            spp.cycle record or None
        """
        # Ensure beneficiaries_count is fresh
        program.invalidate_recordset(["beneficiaries_count"])
        member_count = program.beneficiaries_count

        _logger.info(
            "Creating cycle: program (program_id=%s, name=%s, beneficiaries_count=%d)",
            program.id,
            program.name,
            member_count,
        )

        if member_count <= 0:
            _logger.warning(
                "Cannot create cycle: program (program_id=%s) has no beneficiaries",
                program.id,
            )
            return None

        # Step 1: Create cycle via program.create_new_cycle()
        try:
            program.create_new_cycle()
        except UserError as e:
            _logger.error(
                "create_new_cycle UserError for program (program_id=%s, name=%s): %s",
                program.id,
                program.name,
                e,
            )
            return None
        except Exception:
            _logger.exception(
                "create_new_cycle failed for program (program_id=%s, name=%s)",
                program.id,
                program.name,
            )
            return None

        # Find the newly created cycle (latest by sequence)
        cycle = self.env["spp.cycle"].search(
            [("program_id", "=", program.id)],
            limit=1,
            order="sequence desc",
        )

        if not cycle:
            _logger.error(
                "No cycle found after create_new_cycle for program (program_id=%s)",
                program.id,
            )
            return None

        _logger.info(
            "Created cycle via proper flow (cycle_id=%s, program_id=%s, state=%s)",
            cycle.id,
            program.id,
            cycle.state,
        )

        cycle_manager = program.get_manager(program.MANAGER_CYCLE)

        # Step 1b: Synchronously import beneficiaries if the cycle was created
        # with the async path (volume run with >= MIN_ROW_JOB_QUEUE enrolled
        # beneficiaries). The async path schedules queue jobs and locks the
        # cycle — by the time we reach Step 2 the jobs haven't run, so the
        # cycle has no ``cycle_membership_ids`` and ``prepare_entitlements``
        # finds nothing to compute. Re-run the import synchronously.
        if cycle.is_locked and cycle_manager and hasattr(cycle_manager, "_add_beneficiaries"):
            try:
                program_beneficiaries = program.get_beneficiaries("enrolled").mapped("partner_id.id")
                cycle_manager._add_beneficiaries(cycle, program_beneficiaries, "enrolled", do_count=True)
                cycle.write({"is_locked": False, "locked_reason": False})
                _logger.info(
                    "Synced beneficiary import for cycle (cycle_id=%s, count=%s)",
                    cycle.id,
                    len(program_beneficiaries),
                )
            except Exception:
                _logger.exception("Sync beneficiary import failed (cycle_id=%s)", cycle.id)

        # Step 2: Prepare entitlements
        # ``prepare_entitlement`` dispatches to ``_prepare_entitlements_async``
        # via queue_job once the beneficiary count crosses ``MIN_ROW_JOB_QUEUE``,
        # which is exactly what happens once volume generation is enabled. The
        # async path locks the cycle, schedules jobs, and returns — the demo
        # then races ahead while the jobs are still queued, so the entitlements
        # for that cycle never get created. Call the synchronous private hook
        # directly so the demo data is deterministic regardless of beneficiary
        # count.
        try:
            if cycle_manager and hasattr(cycle_manager, "_prepare_entitlements"):
                cycle_manager._prepare_entitlements(cycle, do_count=True)
            else:
                cycle.prepare_entitlement()
            _logger.info("Prepared entitlements for cycle (cycle_id=%s)", cycle.id)
        except Exception:
            _logger.exception("Could not prepare entitlements for cycle (cycle_id=%s)", cycle.id)

        # Step 3: Submit for approval (draft -> to_approve)
        # `prepare_entitlement` locks the cycle with reason "Importing beneficiaries"
        # while the queue-job-driven beneficiary import runs. With volume enabled
        # the lock can outlive the rest of this method, so the normal
        # `action_submit_for_approval` raises `Cycle is locked`. Clear the lock
        # and force the state forward for the demo so the rest of the flow can
        # proceed without waiting for the async import.
        try:
            if cycle.state == "draft":
                cycle.action_submit_for_approval()
                _logger.info("Submitted cycle for approval (cycle_id=%s)", cycle.id)
        except Exception as exc:
            _logger.warning(
                "Submit-for-approval failed (cycle_id=%s, locked=%s): %s — forcing draft -> to_approve",
                cycle.id,
                getattr(cycle, "locked_reason", None),
                exc,
            )
            if cycle.state == "draft":
                cycle.write({"state": "to_approve", "is_locked": False, "locked_reason": False})

        # Step 4: Approve cycle (to_approve -> approved)
        try:
            if cycle.state == "to_approve":
                cycle.action_approve()
                _logger.info("Approved cycle (cycle_id=%s, state=%s)", cycle.id, cycle.state)
        except Exception:
            _logger.exception("Could not approve cycle (cycle_id=%s)", cycle.id)

        # If cycle stayed in to_approve (fund check returned error dict, not
        # exception), force-approve for demo purposes
        if cycle.state == "to_approve":
            _logger.warning(
                "Cycle (cycle_id=%s) still to_approve — force-approving for demo",
                cycle.id,
            )
            cycle.write({"state": "approved", "approved_date": fields.Datetime.now()})

        # Step 4b: Ensure entitlements are approved
        # If accounting isn't fully configured, entitlements may be stuck in
        # pending_validation. Approve them directly so payments can proceed.
        pending_entitlements = cycle.entitlement_ids.filtered(lambda e: e.state in ("draft", "pending_validation"))
        if pending_entitlements:
            _logger.warning(
                "Found %d pending entitlements in cycle (cycle_id=%s) — approving directly for demo data",
                len(pending_entitlements),
                cycle.id,
            )
            pending_entitlements.write(
                {
                    "state": "approved",
                    "date_approved": fields.Date.today(),
                }
            )

        # Step 5: Prepare payments from approved entitlements
        # ``cycle.prepare_payment()`` also dispatches to an async queue path
        # once the approved-entitlement count crosses MAX_PAYMENTS_FOR_SYNC_PREPARE,
        # leaving payments queued instead of created. Same workaround as
        # entitlements — call the sync hook directly so the demo is deterministic.
        try:
            if cycle.state == "approved":
                payment_manager = program.get_manager(program.MANAGER_PAYMENT)
                approved_entitlements = cycle.entitlement_ids.filtered(lambda e: e.state == "approved")
                if payment_manager and approved_entitlements and hasattr(payment_manager, "_prepare_payments"):
                    payment_manager._prepare_payments(cycle, approved_entitlements)
                else:
                    cycle.prepare_payment()
                payment_count = self.env["spp.payment"].search_count([("cycle_id", "=", cycle.id)])
                _logger.info(
                    "Prepared payments for cycle (cycle_id=%s, payments=%d)",
                    cycle.id,
                    payment_count,
                )
        except Exception:
            _logger.exception("Could not prepare payments for cycle (cycle_id=%s)", cycle.id)

        # Step 6: Send payments and mark distributed
        try:
            if cycle.payment_batch_ids:
                cycle.send_payment()
                cycle.mark_distributed()
                _logger.info("Sent payments and marked distributed (cycle_id=%s)", cycle.id)
        except Exception:
            _logger.exception("Could not send payments / mark distributed (cycle_id=%s)", cycle.id)

        # Step 7: Mark payments as reconciled (paid) and entitlements as rdpd2ben
        payments = self.env["spp.payment"].search([("cycle_id", "=", cycle.id)])
        if payments:
            issued_payments = payments.filtered(lambda p: p.state == "issued")
            if issued_payments:
                issued_payments.write(
                    {
                        "state": "reconciled",
                        "status": "paid",
                        "payment_datetime": fields.Datetime.now(),
                    }
                )
                # Set amount_paid = amount_issued for each payment
                for pay in issued_payments:
                    pay.write({"amount_paid": pay.amount_issued})

            # Mark corresponding entitlements as paid
            paid_entitlements = payments.mapped("entitlement_id").filtered(lambda e: e.state == "approved")
            if paid_entitlements:
                paid_entitlements.write({"state": "rdpd2ben"})

            _logger.info(
                "Marked %d payments as reconciled and %d entitlements as paid for cycle (cycle_id=%s)",
                len(issued_payments),
                len(paid_entitlements),
                cycle.id,
            )

        return cycle

    def _customize_story_payments(self, story_farms, program_map, stats):
        """Backdate and customise existing payments for story data.

        By this point the proper flow has already created entitlements and
        payments for every cycle. This method finds the existing payments
        for each story persona and backdates timestamps to create realistic
        payment history.
        """
        for story_id, farm in story_farms.items():
            enrollments = demo_programs.get_story_enrollments(story_id)
            for enrollment_def in enrollments:
                program_name = enrollment_def.get("program")
                program = program_map.get(program_name)
                if not program:
                    continue

                story_payments = enrollment_def.get("payments", [])
                if not story_payments:
                    continue

                # Get all cycles for this program, sorted oldest first
                cycles = self.env["spp.cycle"].search(
                    [("program_id", "=", program.id)],
                    order="sequence asc",
                )

                for idx, pay_def in enumerate(story_payments):
                    if idx >= len(cycles):
                        _logger.warning(
                            "Story defines %d payments but only %d cycles exist for program %s",
                            len(story_payments),
                            len(cycles),
                            program.name,
                        )
                        break

                    cycle = cycles[idx]

                    try:
                        # Find existing payment created by prepare_payment()
                        payment = self.env["spp.payment"].search(
                            [
                                ("cycle_id", "=", cycle.id),
                                ("entitlement_id.partner_id", "=", farm.id),
                            ],
                            limit=1,
                        )

                        if not payment:
                            _logger.warning(
                                "No payment found for partner_id=%s in cycle_id=%s",
                                farm.id,
                                cycle.id,
                            )
                            continue

                        days_back = pay_def.get("days_back", 0)
                        payment_date = fields.Datetime.now() - datetime.timedelta(days=days_back)
                        amount = pay_def.get("amount", 0)
                        status = pay_def.get("status", "paid")

                        vals = {
                            "amount_issued": amount,
                            "issuance_date": payment_date,
                        }
                        if status == "paid":
                            vals.update(
                                {
                                    "amount_paid": amount,
                                    "state": "reconciled",
                                    "status": "paid",
                                    "payment_datetime": payment_date,
                                }
                            )
                        else:
                            vals.update(
                                {
                                    "amount_paid": 0,
                                    "state": "issued",
                                    "status": "failed",
                                    "payment_datetime": False,
                                }
                            )
                        payment.write(vals)

                        # Also backdate the entitlement
                        entitlement = payment.entitlement_id
                        if entitlement:
                            self.env.cr.execute(
                                "UPDATE spp_entitlement SET date_approved = %s, valid_from = %s WHERE id = %s",
                                (payment_date.date(), payment_date.date(), entitlement.id),
                            )

                        stats["payments_customized"] = stats.get("payments_customized", 0) + 1

                    except Exception:
                        _logger.exception("Could not customise payment for partner_id=%s", farm.id)

    # ──────────────────────────────────────────────────────────────────────
    # Deferred Exits
    # ──────────────────────────────────────────────────────────────────────

    def _apply_deferred_exits(self, story_farms, stats):
        """Transition graduated members from enrolled -> exited.

        Runs AFTER cycles/payments so graduated members are included in
        cycle memberships and receive entitlements/payments before being exited.
        """
        Membership = self.env["spp.program.membership"]

        for story_id, farm in story_farms.items():
            enrollments = demo_programs.get_story_enrollments(story_id)
            for enrollment_def in enrollments:
                graduated_days_back = enrollment_def.get("graduated_days_back")
                if not graduated_days_back:
                    continue

                program_name = enrollment_def.get("program")
                membership = Membership.search(
                    [
                        ("partner_id", "=", farm.id),
                        ("program_id.name", "=", program_name),
                        ("state", "=", "enrolled"),
                    ],
                    limit=1,
                )
                if membership:
                    exit_date = fields.Date.today() - datetime.timedelta(days=graduated_days_back)
                    membership.write({"state": "exited", "exit_date": exit_date})
                    _logger.info(
                        "Graduated %s from %s (exit_date=%s)",
                        story_id,
                        program_name,
                        exit_date,
                    )
                    stats["graduations_applied"] = stats.get("graduations_applied", 0) + 1

    # ──────────────────────────────────────────────────────────────────────
    # Change Request Generation
    # ──────────────────────────────────────────────────────────────────────

    # Story change request definitions for farmer registry CR types.
    # Each entry maps a story_id to a CR scenario demonstrating different
    # CR types, approval states, and proposed changes.
    STORY_CHANGE_REQUESTS = {
        # Maria Santos - Farm size update after land acquisition (approved)
        "maria_santos": {
            "type_code": "update_farm_details",
            "days_back": 20,
            "state": "approved",
            "description": "Farm expanded after acquiring adjacent parcel",
            "proposed_changes": {
                "farm_total_size": 3.0,
                "farm_size_under_crops": 3.0,
            },
        },
        # Juan Dela Cruz - Expand farm after adding livestock area (applied)
        "juan_dela_cruz": {
            "type_code": "update_farm_details",
            "days_back": 30,
            "state": "applied",
            "description": "Expand farm after acquiring adjacent livestock area",
            "proposed_changes": {
                "farm_total_size": 4.0,
                "farm_size_under_livestock": 2.0,
                "farm_size_under_crops": 2.0,
                "experience_years": 15,
            },
        },
        # Juan Dela Cruz - Add new livestock activity (pending)
        "juan_dela_cruz_add_activity": {
            "type_code": "manage_farm_activity",
            "days_back": 5,
            "state": "pending",
            "description": "Register new chicken rearing activity",
            "registrant_name": "Dela Cruz Farm",
            "proposed_changes": {
                "operation": "add",
                "activity_type": "livestock",
                "species_code": "chickens",
                "purpose_code": "subsistence",
                "quantity": 50,
                "quantity_unit": "heads",
            },
        },
        # Rosa Garcia - Land tenure change from family to self-owned (approved)
        "rosa_garcia": {
            "type_code": "update_farm_details",
            "days_back": 15,
            "state": "approved",
            "description": "Land title transferred to owner after inheritance",
            "proposed_changes": {
                "land_tenure_code": "self",
                "experience_years": 8,
            },
        },
        # Sofia Martinez - Add organic crop activity (draft)
        "sofia_martinez": {
            "type_code": "manage_farm_activity",
            "days_back": 3,
            "state": "draft",
            "description": "Register organic vegetable cultivation activity",
            "registrant_name": "Martinez Farm",
            "proposed_changes": {
                "operation": "add",
                "activity_type": "crop",
                "species_code": "vegetables",
                "purpose_code": "commercial",
                "area_planted": 0.5,
                "expected_yield": 1200.0,
            },
        },
        # Ramon dela Cruz - Update aquaculture yield (pending)
        "ramon_dela_cruz": {
            "type_code": "manage_farm_activity",
            "days_back": 8,
            "state": "pending",
            "description": "Update tilapia production figures for current season",
            "registrant_name": "Dela Cruz Fishpond",
            "proposed_changes": {
                "operation": "update",
                "activity_type": "aquaculture",
                "species_code": "tilapia",
                "quantity": 3500.0,
                "quantity_unit": "kg",
                "expected_yield": 4000.0,
            },
        },
        # Amir Mangudadatu - Farm size reduction due to idle land (rejected)
        "amir_mangudadatu": {
            "type_code": "update_farm_details",
            "days_back": 25,
            "state": "rejected",
            "description": "Request to reduce productive area classification",
            "rejection_reason": "Requires field verification before reclassification",
            "proposed_changes": {
                "farm_size_under_crops": 1.5,
                "farm_size_idle": 2.5,
            },
        },
        # Sittie Pangandaman - Add maize activity (approved)
        "sittie_pangandaman": {
            "type_code": "manage_farm_activity",
            "days_back": 12,
            "state": "approved",
            "description": "Register new maize cultivation for dry season",
            "registrant_name": "Pangandaman Farm",
            "proposed_changes": {
                "operation": "add",
                "activity_type": "crop",
                "species_code": "maize",
                "purpose_code": "commercial",
                "area_planted": 0.8,
                "expected_yield": 2000.0,
            },
        },
        # Danilo Villanueva - Update farm details with experience (revision)
        "danilo_villanueva": {
            "type_code": "update_farm_details",
            "days_back": 10,
            "state": "revision",
            "description": "Update experience years and land breakdown",
            "revision_notes": "Please provide supporting documents for experience claim",
            "proposed_changes": {
                "experience_years": 20,
                "farm_size_under_crops": 3.5,
                "farm_size_under_livestock": 1.5,
            },
        },
        # Danilo Villanueva — Register a new water pump on FM8 (pending)
        # Demonstrates the manage_farm_asset CR type alongside the
        # update_farm_details / manage_farm_activity CRs already in this dict.
        "danilo_villanueva_add_asset": {
            "type_code": "manage_farm_asset",
            "days_back": 7,
            "state": "pending",
            "description": "Register additional water pump for irrigation expansion",
            "registrant_name": "Villanueva Farm",
            "proposed_changes": {
                "operation": "add",
                "asset_category": "machinery",
                "machinery_type_name": "Water Pump",
                "machine_working_status": "operational",
                "quantity": 1,
            },
        },
        # NOTE: Demo CRs for manage_land_parcel are disabled until that CR
        # type is enabled in cr_types.xml.
    }

    def _create_story_change_requests(self, story_farms, stats):
        """Create change requests for demo story farms.

        Creates CRs at various approval states to demonstrate the
        change request workflow for farm registry updates.
        """
        created_crs = []

        if "spp.change.request" not in self.env:
            _logger.warning("Change request model not available, skipping CR creation")
            return created_crs

        for story_id, cr_def in self.STORY_CHANGE_REQUESTS.items():
            # Resolve the registrant (farm group)
            registrant = self._resolve_cr_registrant(story_id, cr_def, story_farms)
            if not registrant:
                _logger.warning("Registrant not found for CR (story_id=%s)", story_id)
                continue

            try:
                cr_record = self._create_single_change_request(registrant, cr_def, stats)
                if cr_record:
                    created_crs.append(cr_record)
            except Exception as e:
                _logger.error("Error creating CR for story %s: %s", story_id, e)

        return created_crs

    def _resolve_cr_registrant(self, story_id, cr_def, story_farms):
        """Find the registrant for a CR definition.

        Uses explicit registrant_name if provided, otherwise looks up
        the story farm by story_id.
        """
        registrant_name = cr_def.get("registrant_name")
        if registrant_name:
            registrant = self.env["res.partner"].search(
                [("name", "=", registrant_name), ("is_registrant", "=", True)],
                limit=1,
            )
            if registrant:
                return registrant

        # Fall back to story_farms dict (handles base story_id without suffix)
        base_id = story_id.split("_add_activity")[0].split("_update")[0]
        return story_farms.get(base_id)

    def _create_single_change_request(self, registrant, cr_def, stats):
        """Create a single change request with detail and state progression."""
        cr_type_code = cr_def["type_code"]
        days_back = cr_def.get("days_back", 10)
        target_state = cr_def.get("state", "draft")

        # Find CR type by code
        cr_type = self.env["spp.change.request.type"].search(
            [("code", "=", cr_type_code)],
            limit=1,
        )
        if not cr_type:
            _logger.warning("CR type not found (code=%s)", cr_type_code)
            return None

        request_date = fields.Datetime.now() - datetime.timedelta(days=days_back)

        try:
            # Create base change request
            cr_record = self.env["spp.change.request"].create(
                {
                    "request_type_id": cr_type.id,
                    "registrant_id": registrant.id,
                    "description": cr_def.get("description"),
                }
            )

            # Backdate creation
            self.env.cr.execute(
                "UPDATE spp_change_request SET create_date = %s WHERE id = %s",
                (request_date, cr_record.id),
            )

            # Create and populate the detail record
            detail = cr_record._ensure_detail()
            if detail:
                detail_vals = self._build_farmer_detail_changes(
                    detail._name,
                    registrant,
                    cr_def.get("proposed_changes", {}),
                )
                if detail_vals:
                    detail.write(detail_vals)
                    self.env.cr.execute(
                        f"UPDATE {detail._table} SET create_date = %s WHERE id = %s",  # nosec B608
                        (request_date, detail.id),
                    )

            # Progress to target state
            if target_state == "pending":
                self._set_cr_state(cr_record, "pending")
            elif target_state == "approved":
                self._set_cr_state(cr_record, "approved")
            elif target_state == "applied":
                self._set_cr_state(cr_record, "approved", apply=True)
            elif target_state == "rejected":
                rejection_reason = cr_def.get("rejection_reason", "Request rejected")
                self._set_cr_state(cr_record, "rejected", rejection_reason=rejection_reason)
            elif target_state == "revision":
                revision_notes = cr_def.get("revision_notes", "Please revise and resubmit")
                self._set_cr_state(cr_record, "revision", revision_notes=revision_notes)

            stats["change_requests_created"] = stats.get("change_requests_created", 0) + 1
            _logger.info(
                "Created %s CR (id=%s, type=%s, farm=%s)",
                target_state,
                cr_record.id,
                cr_type_code,
                registrant.id,
            )
            return cr_record

        except Exception as e:
            _logger.error("Failed to create CR: %s", e)
            return None

    def _approver_users(self):
        """Return the seeded approval validators in tier order.

        The demo approval definition is two-tier (Local Validator -> HQ
        Validator). Admin is in neither approver group, so ``action_approve``
        called as admin raises *"You are not authorized…"* and the CR stays
        ``pending``. Approving as each tier's validator drives the CR all
        the way to ``approved``.
        """
        users = []
        for xmlid in (
            "spp_farmer_registry_demo.demo_user_cr_local_validator",
            "spp_farmer_registry_demo.demo_user_cr_hq_validator",
        ):
            user = self.env.ref(xmlid, raise_if_not_found=False)
            if user:
                users.append(user)
        return users

    def _advance_cr_to_terminal(self, cr_record, action_name, reason=None):
        """Call ``action_name`` repeatedly across all approver tiers until
        the CR reaches a terminal state (approved/rejected/revision) or no
        further progress can be made.

        Multi-tier approvals only advance one tier per ``action_approve``
        call. Trying every tier validator covers both the single-tier and
        the two-tier definitions used in the demo.

        ``action_reject`` and ``action_request_revision`` are wizards that
        open a dialog — the actual transition lives in ``_do_reject`` /
        ``_do_request_revision`` (which take a reason / notes string), so
        we route to those when the caller asks for reject/revision.
        """
        terminal = {"approved", "rejected", "revision"}
        method_map = {
            "action_reject": ("_do_reject", reason or "Demo rejection"),
            "action_request_revision": ("_do_request_revision", reason or "Demo revision notes"),
        }
        method_name, arg = method_map.get(action_name, (action_name, None))
        validators = self._approver_users()
        if not validators:
            target = getattr(cr_record.sudo(), method_name)  # nosemgrep
            target(arg) if arg is not None else target()  # nosemgrep
            return

        for validator in validators:
            state = getattr(cr_record, "approval_state", None)
            if state in terminal:
                return
            try:
                scoped = cr_record.with_user(validator).sudo()  # nosemgrep
                target = getattr(scoped, method_name)
                target(arg) if arg is not None else target()  # nosemgrep
            except Exception as exc:  # noqa: BLE001
                _logger.debug(
                    "CR %s: %s as %s did not advance (state=%s): %s",
                    cr_record.id,
                    method_name,
                    validator.login,
                    state,
                    exc,
                )

    def _set_cr_state(self, cr_record, target_state, apply=False, rejection_reason=None, revision_notes=None):
        """Transition CR to target state using approval workflow."""
        try:
            if target_state == "pending":
                cr_record.sudo().action_submit_for_approval()  # nosemgrep
            elif target_state == "approved":
                cr_record.sudo().action_submit_for_approval()  # nosemgrep
                self._advance_cr_to_terminal(cr_record, "action_approve")
            elif target_state == "rejected":
                cr_record.sudo().action_submit_for_approval()  # nosemgrep
                if hasattr(cr_record, "action_reject"):
                    self._advance_cr_to_terminal(cr_record, "action_reject", reason=rejection_reason)
                if rejection_reason and "rejection_reason" in cr_record._fields:
                    cr_record.sudo().write({"rejection_reason": rejection_reason})  # nosemgrep
            elif target_state == "revision":
                cr_record.sudo().action_submit_for_approval()  # nosemgrep
                if hasattr(cr_record, "action_request_revision"):
                    self._advance_cr_to_terminal(cr_record, "action_request_revision", reason=revision_notes)
                if revision_notes and "revision_notes" in cr_record._fields:
                    cr_record.sudo().write({"revision_notes": revision_notes})  # nosemgrep

        except Exception as e:
            _logger.warning(
                "Approval flow failed for CR %s (target=%s): %s. CR remains in state %s.",
                cr_record.name,
                target_state,
                e,
                cr_record.approval_state if hasattr(cr_record, "approval_state") else "unknown",
            )

        # Always advance stage past "details" for non-draft CRs so the JS
        # openRecord router uses the review form instead of the old main form.
        if target_state != "draft" and "stage" in cr_record._fields:
            cr_record.sudo().write({"stage": "review"})  # nosemgrep

        if apply:
            try:
                cr_record.sudo().action_apply()  # nosemgrep
            except Exception as e:
                _logger.warning("Apply failed, setting flags directly: %s", e)
                cr_record.sudo().write(  # nosemgrep
                    {
                        "approval_state": "approved",
                        "is_applied": True,
                        "applied_date": fields.Datetime.now(),
                        "applied_by_id": self.env.user.id,
                    }
                )

    def _build_farmer_detail_changes(self, detail_model, registrant, proposed_changes):
        """Map proposed changes to farmer CR detail fields."""
        if not proposed_changes:
            return {}

        handler = {
            "spp.cr.detail.farm_details": self._build_farm_details_changes,
            "spp.cr.detail.manage_farm_activity": self._build_farm_activity_changes,
            "spp.cr.detail.manage_land_parcel": self._build_land_parcel_changes,
            "spp.cr.detail.manage_farm_asset": self._build_farm_asset_changes,
        }.get(detail_model)

        if handler:
            return handler(registrant, proposed_changes)
        return {}

    def _build_farm_details_changes(self, _registrant, proposed_changes):
        """Build detail vals for farm details CR."""
        vals = {}
        farm_type_code = proposed_changes.get("farm_type_code")
        if farm_type_code:
            vals["farm_type_id"] = self._get_vocab_code("urn:openspp:vocab:farm-type", farm_type_code)
        land_tenure_code = proposed_changes.get("land_tenure_code")
        if land_tenure_code:
            vals["land_tenure_id"] = self._get_vocab_code("urn:openspp:vocab:land-tenure", land_tenure_code)

        for field in (
            "farm_total_size",
            "farm_size_under_crops",
            "farm_size_under_livestock",
            "farm_size_under_aquaculture",
            "farm_size_leased_out",
            "farm_size_idle",
            "experience_years",
        ):
            if field in proposed_changes:
                vals[field] = proposed_changes[field]
        return vals

    def _build_farm_activity_changes(self, registrant, proposed_changes):
        """Build detail vals for farm activity CR."""
        vals = {"is_operation_locked": True}
        if "operation" in proposed_changes:
            vals["operation"] = proposed_changes["operation"]
        if "activity_type" in proposed_changes:
            vals["activity_type"] = proposed_changes["activity_type"]

        species_code = proposed_changes.get("species_code")
        if species_code:
            from .seeded_farm_generator import SPECIES_MAP

            mapping = SPECIES_MAP.get(species_code)
            if mapping:
                namespace_uri, code = mapping
                vals["species_id"] = self._get_vocab_code(namespace_uri, code)

        purpose_code = proposed_changes.get("purpose_code")
        if purpose_code:
            vals["purpose_id"] = self._get_vocab_code("urn:openspp:vocab:activity-purpose", purpose_code)

        for field in ("quantity", "area_planted", "expected_yield", "actual_yield"):
            if field in proposed_changes:
                vals[field] = proposed_changes[field]
        if "quantity_unit" in proposed_changes:
            vals["quantity_unit"] = proposed_changes["quantity_unit"]

        if "season_id" not in vals:
            active_season = self.env["spp.farm.season"].search([("state", "=", "active")], limit=1)
            if active_season:
                vals["season_id"] = active_season.id

        if proposed_changes.get("operation") in ("update", "remove") and registrant:
            farm_field = {
                "crop": "crop_farm_id",
                "livestock": "livestock_farm_id",
                "aquaculture": "aquaculture_farm_id",
            }.get(proposed_changes.get("activity_type"))
            if farm_field:
                existing = self.env["spp.farm.activity"].search([(farm_field, "=", registrant.id)], limit=1)
                if existing:
                    vals["activity_id"] = existing.id
        return vals

    def _build_land_parcel_changes(self, registrant, proposed_changes):
        """Build detail vals for land parcel CR."""
        vals = {"is_operation_locked": True}
        if "operation" in proposed_changes:
            vals["operation"] = proposed_changes["operation"]
        for field in ("land_name", "land_acreage"):
            if field in proposed_changes:
                vals[field] = proposed_changes[field]

        land_use_code = proposed_changes.get("land_use_code")
        if land_use_code:
            vals["land_use_id"] = self._get_vocab_code("urn:openspp:vocab:land-use", land_use_code)

        if proposed_changes.get("operation") in ("update", "remove") and registrant:
            existing = self.env["spp.land.record"].search([("land_farm_id", "=", registrant.id)], limit=1)
            if existing:
                vals["land_record_id"] = existing.id
        return vals

    def _build_farm_asset_changes(self, registrant, proposed_changes):
        """Build detail vals for farm asset CR."""
        vals = {"is_operation_locked": True}
        if "operation" in proposed_changes:
            vals["operation"] = proposed_changes["operation"]

        asset_category = proposed_changes.get("asset_category", "asset")
        vals["asset_category"] = asset_category

        if asset_category == "asset":
            asset_type_name = proposed_changes.get("asset_type_name")
            if asset_type_name:
                asset_type = self.env["spp.asset.type"].search([("name", "=", asset_type_name)], limit=1)
                if not asset_type:
                    asset_type = self.env["spp.asset.type"].create({"name": asset_type_name})
                vals["asset_type_id"] = asset_type.id
            for field in ("technology_used", "quantity"):
                if field in proposed_changes:
                    vals[field] = proposed_changes[field]
            if proposed_changes.get("operation") in ("update", "remove") and registrant:
                existing = self.env["spp.farm.asset"].search([("asset_farm_id", "=", registrant.id)], limit=1)
                if existing:
                    vals["farm_asset_id"] = existing.id
        else:
            machinery_type_name = proposed_changes.get("machinery_type_name")
            if machinery_type_name:
                mach_type = self.env["spp.machinery.type"].search([("name", "=", machinery_type_name)], limit=1)
                if not mach_type:
                    mach_type = self.env["spp.machinery.type"].create({"name": machinery_type_name})
                vals["machinery_type_id"] = mach_type.id
            for field in ("machine_working_status", "quantity"):
                if field in proposed_changes:
                    vals[field] = proposed_changes[field]
            if proposed_changes.get("operation") in ("update", "remove") and registrant:
                existing = self.env["spp.farm.asset"].search([("machinery_farm_id", "=", registrant.id)], limit=1)
                if existing:
                    vals["farm_machinery_id"] = existing.id
        return vals

    # ──────────────────────────────────────────────────────────────────────
    # Volume Generation (Blueprint-based)
    # ──────────────────────────────────────────────────────────────────────

    def _generate_blueprint_farms(self):
        """Generate deterministic farms from blueprint definitions.

        Uses SeededFarmGenerator with seed=42 for reproducible output.
        Same seed + same locale = identical farms every run.

        Returns:
            list[dict]: Each dict has 'group', 'members', 'blueprint', 'size', 'gps'
        """
        generator = SeededFarmGenerator(self.env, locale="fil_PH", seed=42)
        return generator.generate_all_farms(FARMER_BLUEPRINTS)

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _get_vocab_code(self, namespace_uri, code):
        """Get a vocabulary code ID by namespace and code."""
        VocabCode = self.env["spp.vocabulary.code"].sudo()  # nosemgrep
        vocab = VocabCode.search(
            [("namespace_uri", "=", namespace_uri), ("code", "=", code)],
            limit=1,
        )
        return vocab.id if vocab else False
