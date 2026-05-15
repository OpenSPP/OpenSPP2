# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Seeded Farm Generator for Deterministic Demo Data

Generates farms and members from blueprint definitions using:
- random.Random(seed) for all structural choices (sizes, ages, genders, names)

Same seed = identical output every run.

Performance optimized with:
- Batched create() calls (~200 records per batch)
- Context flags to disable tracking/mail
"""

import datetime
import json
import logging
import math
import random

from odoo import Command, fields

_logger = logging.getLogger(__name__)

# Filipino name pools for deterministic, locale-appropriate name generation
_FILIPINO_MALE_FIRST_NAMES = [
    "Jose",
    "Juan",
    "Pedro",
    "Antonio",
    "Manuel",
    "Carlos",
    "Eduardo",
    "Roberto",
    "Francisco",
    "Rafael",
    "Fernando",
    "Ricardo",
    "Ernesto",
    "Reynaldo",
    "Rolando",
    "Romeo",
    "Danilo",
    "Ramon",
    "Arturo",
    "Alfredo",
    "Alejandro",
    "Andres",
    "Benjamin",
    "Bernardo",
    "Cesar",
    "Domingo",
    "Edgardo",
    "Felix",
    "Gerardo",
    "Gregorio",
    "Guillermo",
    "Hector",
    "Isidro",
    "Jaime",
    "Joel",
    "Jorge",
    "Leonardo",
    "Lorenzo",
    "Luis",
    "Marco",
    "Mario",
    "Miguel",
    "Nelson",
    "Nestor",
    "Orlando",
    "Oscar",
    "Pablo",
    "Patricio",
    "Raul",
    "Rodel",
    "Rodolfo",
    "Rogelio",
    "Romulo",
    "Ruben",
    "Salvador",
    "Santiago",
    "Sergio",
    "Teodoro",
    "Vicente",
    "Virgilio",
    "Wilfredo",
    "Arnel",
    "Dennis",
    "Edgar",
    "Gilbert",
    "Jayson",
    "Mark",
    "Noel",
    "Randy",
    "Ricky",
    "Ronaldo",
]

_FILIPINO_FEMALE_FIRST_NAMES = [
    "Maria",
    "Ana",
    "Rosa",
    "Carmen",
    "Rosario",
    "Luz",
    "Elena",
    "Teresa",
    "Gloria",
    "Lourdes",
    "Mercedes",
    "Corazon",
    "Esperanza",
    "Milagros",
    "Concepcion",
    "Dolores",
    "Remedios",
    "Josefina",
    "Cristina",
    "Virginia",
    "Imelda",
    "Teresita",
    "Leonora",
    "Julieta",
    "Angelita",
    "Felicidad",
    "Estrella",
    "Aurora",
    "Perla",
    "Natividad",
    "Sonia",
    "Norma",
    "Linda",
    "Lilia",
    "Edna",
    "Myrna",
    "Yolanda",
    "Cecilia",
    "Leticia",
    "Beatriz",
    "Alma",
    "Cynthia",
    "Maribel",
    "Marilyn",
    "Divina",
    "Aida",
    "Sylvia",
    "Luzviminda",
    "Florencia",
    "Evangeline",
    "Sittie",
    "Amina",
    "Fatima",
    "Norhana",
    "Bai",
    "Rowena",
    "Cherry",
    "Jocelyn",
    "Michelle",
    "Jennifer",
    "Karen",
    "Rochelle",
    "Mary Grace",
    "Mary Ann",
    "Mary Jane",
    "Jasmine",
    "April",
    "Lovely",
    "Princess",
    "Jonalyn",
]

_FILIPINO_LAST_NAMES = [
    "Santos",
    "Reyes",
    "Cruz",
    "Bautista",
    "Ocampo",
    "Garcia",
    "Mendoza",
    "Torres",
    "Ramos",
    "Aquino",
    "Fernandez",
    "Lopez",
    "Gonzales",
    "Perez",
    "Castillo",
    "Rivera",
    "Flores",
    "Villanueva",
    "Soriano",
    "Navarro",
    "Aguilar",
    "Mercado",
    "Castro",
    "Salvador",
    "Pascual",
    "Tolentino",
    "Domingo",
    "Ignacio",
    "Manalo",
    "Francisco",
    "Magno",
    "Corpuz",
    "Padilla",
    "Concepcion",
    "Enriquez",
    "Adriano",
    "Angeles",
    "Cabrera",
    "Dizon",
    "Espino",
    "Gutierrez",
    "Hernandez",
    "Lim",
    "Tan",
    "Chua",
    "Ong",
    "Villaluz",
    "Magtanggol",
    "Dalisay",
    "Bayani",
    "Dimaculangan",
    "Macapagal",
    "Pangilinan",
    "Tañada",
    "Legaspi",
    "Lacson",
    "Magsaysay",
    "Roxas",
    "Laurel",
    "Osmeña",
    "Quezon",
    "Dimagiba",
    "Macaraeg",
    "Del Rosario",
    "De Leon",
    "De Guzman",
    "De Castro",
    "Del Valle",
    "De Jesus",
    "De Vera",
    "Dela Cruz",
    "Dela Peña",
    "Dela Rosa",
    "Mangudadatu",
    "Pangandaman",
    "Dimaporo",
    "Alonto",
    "Adiong",
    "Lucman",
    "Mastura",
    "Sinsuat",
    "Ampatuan",
    "Balindong",
    "Cabugatan",
    "Datumanong",
    "Gandamra",
]

BATCH_SIZE = 200

# Species code -> (namespace_uri, code) mapping for FAO vocabularies
SPECIES_MAP = {
    "rice_irrigated": ("urn:fao:icc:1.1", "0116"),
    "maize": ("urn:fao:icc:1.1", "0115"),
    "vegetables": ("urn:fao:icc:1.1", "02"),
    "goats": ("urn:fao:livestock:2020", "3.2"),
    "chickens": ("urn:fao:livestock:2020", "5.1"),
    "cattle": ("urn:fao:livestock:2020", "1"),
    "tilapia": ("urn:fao:asfis:2024", "TIL"),
}

# Philippine agricultural bounds (inland)
_PH_ZONES = {
    "rural": {
        "lat_min": 7.0,
        "lat_max": 16.5,
        "lng_min": 120.3,
        "lng_max": 125.5,
    },
    "peri_urban": {
        "lat_min": 13.5,
        "lat_max": 15.5,
        "lng_min": 120.5,
        "lng_max": 121.5,
    },
}


# OP#915 round-3: realistic bank names for seeded volume farms. Rotates
# deterministically via rng so the same seed produces the same assignment
# every run. Banks covering PH agricultural lending in practice.
DEMO_BANKS = [
    "Land Bank of the Philippines",
    "Development Bank of the Philippines",
    "BDO Unibank",
    "Bank of the Philippine Islands",
    "Metropolitan Bank and Trust Company",
]


class SeededFarmGenerator:
    """Deterministic farm/member generator using seeded RNG.

    Not an ORM model -- a utility class instantiated by the wizard.
    """

    def __init__(self, env, locale="fil_PH", seed=42):
        self.env = env
        self.locale = locale
        self.seed = seed
        self.rng = random.Random(seed)

        # Caches
        self._vocab_cache = {}
        self._species_cache = {}
        self._head_type_id = None

        # Reserved story farm names (avoid collisions)
        self._reserved_names = {
            "Santos Farm",
            "Dela Cruz Farm",
            "Garcia Farm",
            "Mangudadatu Farm",
            "Martinez Farm",
            "Dela Cruz Fishpond",
            "Pangandaman Farm",
            "Villanueva Farm",
            "Maria Santos",
            "Juan Dela Cruz",
            "Rosa Garcia",
            "Amir Mangudadatu",
            "Sofia Martinez",
            "Ramon dela Cruz",
            "Sittie Pangandaman",
            "Danilo Villanueva",
        }

    # =========================================================================
    # Public API
    # =========================================================================

    def generate_all_farms(self, blueprints):
        """Generate all farms from blueprint definitions.

        Returns:
            list[dict]: Each dict has 'group' (farm partner record),
                        'members' (list of partner records),
                        'blueprint' (original blueprint dict)
        """
        total_farms = sum(bp["count"] for bp in blueprints)
        total_members = sum(bp["count"] * len(bp["members"]) for bp in blueprints)
        _logger.info(
            "Starting farm volume generation: %d blueprints, %d farms, ~%d members",
            len(blueprints),
            total_farms,
            total_members,
        )

        # Ensure vocabularies exist
        self._ensure_land_use_vocabularies()

        # Phase 1: Prepare group (farm) values
        _logger.info("Phase 1/5: Preparing %d farm records...", total_farms)
        group_vals_list = []

        member_specs = []  # (blueprint, instance_index)

        for bp in blueprints:
            for i in range(bp["count"]):
                farm_name = self._generate_farm_name()
                size = round(self.rng.uniform(*bp["size_range"]), 1)
                experience = self.rng.randint(*bp["experience_range"])
                gps = self._generate_gps_for_zone(bp["zone"])

                # Compute land breakdown from size
                idle_pct = bp.get("idle_pct", 0.0)
                idle = round(size * idle_pct, 1)
                productive = size - idle

                # Farm type determines land breakdown
                farm_type = bp["farm_type"]
                under_crops = 0.0
                under_livestock = 0.0
                under_aquaculture = 0.0

                if farm_type == "crop":
                    under_crops = productive
                elif farm_type == "livestock":
                    under_livestock = productive
                elif farm_type == "aquaculture":
                    under_aquaculture = productive
                elif farm_type == "mixed":
                    # Split productive land based on activities
                    crop_activities = [a for a in bp["activities"] if a["type"] == "crop"]
                    livestock_activities = [a for a in bp["activities"] if a["type"] == "livestock"]
                    aqua_activities = [a for a in bp["activities"] if a["type"] == "aquaculture"]

                    total_crop_pct = sum(a.get("area_pct", 0) for a in crop_activities)
                    has_livestock = len(livestock_activities) > 0
                    has_aqua = len(aqua_activities) > 0

                    under_crops = round(productive * min(total_crop_pct, 1.0), 1)
                    remaining = productive - under_crops
                    if has_aqua and has_livestock:
                        under_aquaculture = round(remaining * 0.5, 1)
                        under_livestock = round(remaining - under_aquaculture, 1)
                    elif has_aqua:
                        under_aquaculture = remaining
                    elif has_livestock:
                        under_livestock = remaining

                farm_type_id = self._get_vocab_code("urn:openspp:vocab:farm-type", farm_type)
                tenure_id = self._get_vocab_code("urn:openspp:vocab:land-tenure", bp["land_tenure"])
                holder_id = self._get_vocab_code("urn:openspp:vocab:holder-type", "individual")

                gvals = {
                    "name": farm_name,
                    "is_registrant": True,
                    "is_group": True,
                    "farm_type_id": farm_type_id,
                    "holder_type_id": holder_id,
                    "land_tenure_id": tenure_id,
                    "farm_total_size": size,
                    "farm_size_under_crops": under_crops,
                    "farm_size_under_livestock": under_livestock,
                    "farm_size_under_aquaculture": under_aquaculture,
                    "farm_size_idle": idle,
                    "experience_years": experience,
                }
                if gps:
                    gvals["coordinates"] = json.dumps({"type": "Point", "coordinates": [gps[0], gps[1]]})

                # OP#915 round-3: realistic phone + bank for every farm group.
                # Phone goes onto the bare partner.phone char AND will be
                # mirrored to a spp.phone.number row after creation.
                group_phone = self._generate_phone()
                group_bank_name = DEMO_BANKS[self.rng.randint(0, len(DEMO_BANKS) - 1)]
                group_acc_no = f"{self.rng.randint(0, 10**12 - 1):012d}"
                gvals["phone"] = group_phone

                group_vals_list.append(gvals)
                member_specs.append((bp, i, size, gps, group_phone, group_bank_name, group_acc_no))

        # Phase 2: Batch-create farm groups (farm details auto-created via _inherits)
        _logger.info("Phase 2/5: Creating %d farm groups in batches...", len(group_vals_list))
        groups = self._batch_create("res.partner", group_vals_list)

        # Assign areas
        demo_areas = self.env["spp.area"].search([("code", "like", "PH-%")], order="id")
        if demo_areas:
            for group in groups:
                area = demo_areas[self.rng.randint(0, len(demo_areas) - 1)]
                group.write({"area_id": area.id})

        # Phase 3: Prepare individual (farmer) member values
        _logger.info("Phase 3/5: Preparing individual members...")
        all_individual_vals = []
        individual_to_group = []
        # OP#915 round-3: parallel list of per-member contact info
        # (phone + head bank account number). Always draw both even for
        # non-head members so the rng sequence is deterministic regardless
        # of role distribution.
        member_contact = []

        for group_idx, (bp, _instance_idx, _size, _gps, _gphone, _gbank, _gacc) in enumerate(member_specs):
            group_record = groups[group_idx]
            for member_spec in bp["members"]:
                gender = self._resolve_gender(member_spec.get("gender", "any"))
                # Consume RNG state for age to keep deterministic sequence
                self.rng.randint(*member_spec["age_range"])
                given_name, family_name = self._generate_member_name(gender)

                gender_id = self._get_gender_id(gender)

                # New rng draws AFTER existing ones — keeps prior sequence
                # untouched. acc_no only used when role == head; drawn
                # unconditionally to keep rng state consistent.
                member_phone = self._generate_phone()
                member_acc_no = f"{self.rng.randint(0, 10**12 - 1):012d}"

                ival = {
                    "name": f"{given_name} {family_name}",
                    "given_name": given_name,
                    "family_name": family_name,
                    "is_registrant": True,
                    "is_group": False,
                    "gender_id": gender_id,
                    "phone": member_phone,
                }

                all_individual_vals.append(ival)
                individual_to_group.append((group_record, member_spec))
                member_contact.append(
                    {
                        "phone": member_phone,
                        "acc_no": member_acc_no,
                        "is_head": member_spec["role"] == "head",
                        "group_idx": group_idx,
                    }
                )

        # Phase 4: Batch-create individuals + memberships
        _logger.info("Phase 4/5: Creating %d individuals in batches...", len(all_individual_vals))
        individuals = self._batch_create("res.partner", all_individual_vals)

        # Create memberships
        head_type_id = self._get_head_type_id()
        membership_vals = []
        for ind_idx, individual in enumerate(individuals):
            group_record, member_spec = individual_to_group[ind_idx]
            mvals = {
                "group": group_record.id,
                "individual": individual.id,
            }
            if member_spec["role"] == "head" and head_type_id:
                mvals["membership_type_ids"] = [Command.link(head_type_id)]
            membership_vals.append(mvals)

        self._batch_create("spp.group.membership", membership_vals)

        # Phase 4.5: Batch-create spp.phone.number rows + res.partner.bank
        # accounts. partner.phone was already set in vals (Phase 1 + 3) so
        # legacy header widgets show the number; this phase fills the
        # registrant's Phone Numbers tab and Bank Accounts smart button.
        self._create_contact_records(groups, individuals, member_specs, member_contact)

        # Build result list
        results = []
        ind_offset = 0
        for group_idx, (bp, _instance_idx, size, gps, _gphone, _gbank, _gacc) in enumerate(member_specs):
            group_record = groups[group_idx]
            member_count = len(bp["members"])
            farm_members = list(individuals[ind_offset : ind_offset + member_count])
            ind_offset += member_count
            results.append(
                {
                    "group": group_record,
                    "members": farm_members,
                    "blueprint": bp,
                    "size": size,
                    "gps": gps,
                }
            )

        # Phase 5: Create farm activities and land records
        _logger.info("Phase 5/5: Creating activities and land records...")
        active_season = self.env["spp.farm.season"].search([("state", "=", "active")], limit=1)
        self._create_farm_activities(results, active_season)
        self._create_land_records(results)

        _logger.info(
            "Volume generation complete: %d farms, %d individuals",
            len(groups),
            len(individuals),
        )
        return results

    def enroll_in_programs(self, farm_results, program_map):
        """Enroll farms in programs based on blueprint eligibility flags.

        Args:
            farm_results: list of dicts from generate_all_farms()
            program_map: dict of program_id_str -> spp.program record
        """
        if not farm_results or not program_map:
            return

        enrollment_vals = []
        enrollment_dates = []

        for result in farm_results:
            bp = result["blueprint"]
            group = result["group"]

            for prog_id, is_eligible in bp.get("eligibility", {}).items():
                if not is_eligible:
                    continue
                program = program_map.get(prog_id)
                if not program:
                    continue

                enrollment_vals.append(
                    {
                        "program_id": program.id,
                        "partner_id": group.id,
                        "state": "enrolled",
                    }
                )
                enrollment_dates.append(fields.Date.today())

        if not enrollment_vals:
            return

        _logger.info("Enrolling %d farm-program memberships...", len(enrollment_vals))
        memberships = self._batch_create("spp.program.membership", enrollment_vals)

        # Backdate enrollment dates and add state variety via SQL
        self.env.flush_all()
        self._apply_membership_realism(memberships, enrollment_dates)

    # =========================================================================
    # Internal: Contact info (phone + bank) creation
    # =========================================================================

    def _generate_phone(self):
        """Deterministic +63 9XX XXX XXXX phone number using rng (3 draws)."""
        prefix = self.rng.randint(10, 99)
        mid = self.rng.randint(100, 999)
        end = self.rng.randint(0, 9999)
        return f"+63 9{prefix} {mid} {end:04d}"

    def _create_contact_records(self, groups, individuals, member_specs, member_contact):
        """Batch-create spp.phone.number rows + res.partner.bank accounts.

        - Every farm group gets 1 phone row + 1 bank account.
        - Every individual gets 1 phone row.
        - Only head individuals get a bank account (shared bank with their farm).
        """
        PhoneNumber = self.env["spp.phone.number"].sudo()  # nosemgrep
        Bank = self.env["res.bank"].sudo()  # nosemgrep
        PartnerBank = self.env["res.partner.bank"].sudo()  # nosemgrep

        # Resolve / create bank entities once (small fixed list).
        bank_id_by_name = {}
        for bank_name in DEMO_BANKS:
            bank = Bank.search([("name", "=", bank_name)], limit=1)
            if not bank:
                bank = Bank.create({"name": bank_name})
            bank_id_by_name[bank_name] = bank.id

        # ---- Phase: phone numbers ----
        phone_vals = []
        for group, (bp, _i, _s, _g, gphone, _gb, _ga) in zip(groups, member_specs, strict=False):
            if gphone:
                phone_vals.append({"partner_id": group.id, "phone_no": gphone})

        for individual, contact in zip(individuals, member_contact, strict=False):
            if contact["phone"]:
                phone_vals.append({"partner_id": individual.id, "phone_no": contact["phone"]})

        if phone_vals:
            self._batch_create("spp.phone.number", phone_vals)

        # ---- Phase: bank accounts ----
        bank_vals = []
        # One bank account per farm group.
        for group, (bp, _i, _s, _g, _gphone, gbank, gacc) in zip(groups, member_specs, strict=False):
            if gbank and gacc:
                bank_vals.append(
                    {
                        "partner_id": group.id,
                        "acc_number": gacc,
                        "bank_id": bank_id_by_name[gbank],
                    }
                )

        # One bank account per head individual, sharing the farm's bank.
        for individual, contact in zip(individuals, member_contact, strict=False):
            if not contact["is_head"]:
                continue
            gbank = member_specs[contact["group_idx"]][5]
            if gbank and contact.get("acc_no"):
                bank_vals.append(
                    {
                        "partner_id": individual.id,
                        "acc_number": contact["acc_no"],
                        "bank_id": bank_id_by_name[gbank],
                    }
                )

        if bank_vals:
            self._batch_create("res.partner.bank", bank_vals)

    # =========================================================================
    # Internal: Farm name generation
    # =========================================================================

    def _generate_farm_name(self):
        """Generate a farm name from seeded RNG + Filipino name pool."""
        max_attempts = 20
        for _ in range(max_attempts):
            family_name = self.rng.choice(_FILIPINO_LAST_NAMES)
            farm_name = f"{family_name} Farm"
            if farm_name not in self._reserved_names:
                return farm_name
        return farm_name

    def _generate_member_name(self, gender):
        """Generate a (given_name, family_name) tuple from Filipino name pools."""
        max_attempts = 20
        for _ in range(max_attempts):
            if gender == "male":
                given = self.rng.choice(_FILIPINO_MALE_FIRST_NAMES)
            else:
                given = self.rng.choice(_FILIPINO_FEMALE_FIRST_NAMES)
            family = self.rng.choice(_FILIPINO_LAST_NAMES)
            full_name = f"{given} {family}"
            if full_name not in self._reserved_names:
                return given, family
        return given, family

    def _resolve_gender(self, gender_spec):
        """Resolve 'any' gender to 'male' or 'female' deterministically."""
        if gender_spec == "any":
            return self.rng.choice(["male", "female"])
        return gender_spec

    # =========================================================================
    # Internal: GPS generation
    # =========================================================================

    def _generate_gps_for_zone(self, zone):
        """Generate GPS coordinates based on zone type.

        Returns:
            tuple(lng, lat) or None
        """
        bounds = _PH_ZONES.get(zone, _PH_ZONES["rural"])
        lat = round(self.rng.uniform(bounds["lat_min"], bounds["lat_max"]), 6)
        lng = round(self.rng.uniform(bounds["lng_min"], bounds["lng_max"]), 6)
        return (lng, lat)

    # =========================================================================
    # Internal: Activities
    # =========================================================================

    def _create_farm_activities(self, farm_results, season):
        """Create agricultural activities for generated farms."""
        if not season:
            _logger.warning("No active season, skipping activity creation")
            return

        activity_vals_list = []

        subsistence_id = self._get_vocab_code("urn:openspp:vocab:activity-purpose", "subsistence")
        commercial_id = self._get_vocab_code("urn:openspp:vocab:activity-purpose", "commercial")
        both_id = self._get_vocab_code("urn:openspp:vocab:activity-purpose", "both")
        purposes = [p for p in [subsistence_id, commercial_id, both_id] if p]

        for result in farm_results:
            bp = result["blueprint"]
            farm = result["group"]
            size = result["size"]

            for act_spec in bp.get("activities", []):
                species_id = self._resolve_species(act_spec["species_code"])
                if not species_id:
                    continue

                purpose_id = purposes[self.rng.randint(0, len(purposes) - 1)] if purposes else False

                avals = {
                    "season_id": season.id,
                    "activity_type": act_spec["type"],
                    "species_id": species_id,
                }

                if act_spec["type"] == "crop":
                    area_pct = act_spec.get("area_pct", 0.5)
                    area = round(size * area_pct, 1)
                    avals["crop_farm_id"] = farm.id
                    avals["area_planted"] = area
                    avals["expected_yield"] = round(area * self.rng.randint(1500, 3000))
                elif act_spec["type"] == "livestock":
                    qty_range = act_spec.get("quantity_range", (5, 20))
                    avals["livestock_farm_id"] = farm.id
                    avals["quantity"] = self.rng.randint(*qty_range)
                    avals["quantity_unit"] = "heads"
                elif act_spec["type"] == "aquaculture":
                    qty_range = act_spec.get("quantity_range", (1000, 5000))
                    avals["aquaculture_farm_id"] = farm.id
                    avals["quantity"] = self.rng.randint(*qty_range)
                    avals["quantity_unit"] = "kg"

                if purpose_id:
                    avals["purpose_id"] = purpose_id

                activity_vals_list.append(avals)

        if activity_vals_list:
            self._batch_create("spp.farm.activity", activity_vals_list)
            _logger.info("Created %d farm activities", len(activity_vals_list))

    # =========================================================================
    # Internal: Land records
    # =========================================================================

    def _create_land_records(self, farm_results):
        """Create land records with polygons for generated farms."""
        if "spp.land.record" not in self.env:
            return

        land_vals_list = []
        for result in farm_results:
            farm = result["group"]
            size = result["size"]
            gps = result["gps"]
            bp = result["blueprint"]

            if not gps:
                continue

            lng, lat = gps
            land_use_id = self._get_vocab_code("urn:openspp:vocab:land-use", bp.get("land_use", "cultivation"))
            polygon_geojson = self._generate_farm_polygon(lng, lat, size)
            point_geojson = json.dumps({"type": "Point", "coordinates": [lng, lat]})

            lvals = {
                "land_farm_id": farm.id,
                "land_name": f"{farm.name} - Main Parcel",
                "land_acreage": round(size * 2.471, 2),
                "land_coordinates": point_geojson,
                "land_geo_polygon": polygon_geojson,
                "owner_id": farm.id,
            }
            if land_use_id:
                lvals["land_use_id"] = land_use_id

            land_vals_list.append(lvals)

        if land_vals_list:
            self._batch_create("spp.land.record", land_vals_list)
            _logger.info("Created %d land records", len(land_vals_list))

    def _generate_farm_polygon(self, center_lng, center_lat, hectares):
        """Generate a rectangular polygon approximating the farm area."""
        area_m2 = hectares * 10000
        side_m = math.sqrt(area_m2)

        deg_per_meter_lat = 1.0 / 111320.0
        deg_per_meter_lng = 1.0 / (111320.0 * math.cos(math.radians(center_lat)))

        half_lat = (side_m / 2) * deg_per_meter_lat
        half_lng = (side_m / 2) * deg_per_meter_lng

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

    # =========================================================================
    # Internal: Membership realism
    # =========================================================================

    def _apply_membership_realism(self, memberships, enrollment_dates):
        """Apply state variety and backdate enrollment dates via SQL."""
        if not memberships:
            return

        membership_ids = memberships.ids
        exited_count = paused_count = not_eligible_count = 0

        for idx, mem_id in enumerate(membership_ids):
            roll = self.rng.random()
            state = "enrolled"
            if roll < 0.02:
                state = "not_eligible"
                not_eligible_count += 1
            elif roll < 0.05:
                state = "paused"
                paused_count += 1
            elif roll < 0.10:
                state = "exited"
                exited_count += 1

            if idx < len(enrollment_dates):
                reg_date = enrollment_dates[idx]
                enrollment_dt = datetime.datetime.combine(reg_date, datetime.time(8, 0, 0))
            else:
                enrollment_dt = datetime.datetime.now()

            self.env.cr.execute(
                "UPDATE spp_program_membership SET state = %s, enrollment_date = %s WHERE id = %s",
                (state, enrollment_dt, mem_id),
            )

        memberships.invalidate_recordset(["state", "enrollment_date"])
        _logger.info(
            "Realism for %d memberships: %d exited, %d paused, %d not_eligible",
            len(membership_ids),
            exited_count,
            paused_count,
            not_eligible_count,
        )

    # =========================================================================
    # Internal: Vocabulary helpers
    # =========================================================================

    def _get_vocab_code(self, namespace_uri, code):
        """Get a vocabulary code ID by namespace and code, with caching."""
        cache_key = (namespace_uri, code)
        if cache_key not in self._vocab_cache:
            VocabCode = self.env["spp.vocabulary.code"].sudo()  # nosemgrep
            vocab = VocabCode.search(
                [("namespace_uri", "=", namespace_uri), ("code", "=", code)],
                limit=1,
            )
            self._vocab_cache[cache_key] = vocab.id if vocab else False
        return self._vocab_cache[cache_key]

    def _resolve_species(self, species_code):
        """Map a species code string to a vocabulary code ID."""
        if species_code in self._species_cache:
            return self._species_cache[species_code]

        mapping = SPECIES_MAP.get(species_code)
        if not mapping:
            self._species_cache[species_code] = False
            return False

        namespace_uri, code = mapping
        species_id = self._get_vocab_code(namespace_uri, code)
        self._species_cache[species_code] = species_id
        return species_id

    def _get_gender_id(self, gender):
        """Look up gender vocabulary code ID."""
        namespace = "urn:openspp:vocab:gender"
        return self._get_vocab_code(namespace, gender)

    def _get_head_type_id(self):
        """Get the 'head' membership type ID, with caching."""
        if self._head_type_id is None:
            self._head_type_id = self._get_vocab_code("urn:openspp:vocab:group-membership-type", "head")
        return self._head_type_id

    def _ensure_land_use_vocabularies(self):
        """Ensure land use vocabulary codes exist for GIS demo data."""
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
            try:
                VocabCode.get_or_create_local(
                    "urn:openspp:vocab:land-use",
                    code,
                    display=display,
                )
            except Exception:
                _logger.debug("Land use vocab code %s already exists or cannot be created", code)

    # =========================================================================
    # Internal: Batch create
    # =========================================================================

    def _batch_create(self, model_name, vals_list):
        """Create records in batches for performance."""
        if not vals_list:
            return self.env[model_name]

        all_records = self.env[model_name]
        for i in range(0, len(vals_list), BATCH_SIZE):
            batch = vals_list[i : i + BATCH_SIZE]
            records = self.env[model_name].sudo().create(batch)  # nosemgrep
            all_records |= records
            if len(vals_list) > BATCH_SIZE:
                _logger.info(
                    "  %s: batch %d/%d (%d records)",
                    model_name,
                    (i // BATCH_SIZE) + 1,
                    (len(vals_list) + BATCH_SIZE - 1) // BATCH_SIZE,
                    len(batch),
                )
        return all_records
