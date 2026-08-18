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

# Farmland anchors for the 8 demo areas — visually-verified spots in
# open agricultural land (rice paddies, pasture, fishponds, pineapple
# plantations) matched to each story persona's farm. Seeded volume farms
# are anchored to these points + jitter so every pin lands in real
# farmland instead of a city centroid's residential belt. Coordinates
# are (lng, lat) in GeoJSON order.
_AREA_CENTERS = {
    "PH-NUE": (121.054903, 15.672087),  # Llanera, Nueva Ecija - rice paddies
    "PH-LAG": (121.455690, 14.284290),  # E. Laguna (Magdalena/Pagsanjan) - mixed crops
    "PH-BTG": (121.219381, 13.893127),  # Padre Garcia, Batangas - cattle pasture
    "PH-MAG": (124.280635, 7.241492),  # Sultan Kudarat / DOS - Pulangi plain cropland
    "PH-BEN": (120.688108, 16.590347),  # Atok, Benguet - vegetable terraces
    "PH-PAN": (120.152127, 16.024353),  # Labrador / Sual - fishpond grid
    "PH-LAS": (124.144513, 7.874498),  # Balindong / Bacolod-Kalawi - SW Lake Lanao
    "PH-BUK": (125.174848, 8.115242),  # Malaybalay outskirts - plateau farms
}

# Which area codes a given blueprint zone can land in. peri_urban is
# biased to lowland Luzon (closer to Manila); rural can go anywhere.
_AREAS_BY_ZONE = {
    "rural": ["PH-NUE", "PH-LAG", "PH-BTG", "PH-MAG", "PH-BEN", "PH-PAN", "PH-LAS", "PH-BUK"],
    "peri_urban": ["PH-NUE", "PH-LAG", "PH-BTG", "PH-PAN"],
}

# Max GPS jitter in degrees (~0.10° ≈ ~10-11 km) — wide enough to spread
# volume farms across surrounding farmland, tight enough that pins stay
# in the same kind of terrain as the verified anchor point.
_GPS_JITTER = 0.10


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

# OP#915 round-3 followup: link each volume farm to the service points
# that match its primary farm type. Cash + Extension are universal
# (always linked); each farm picks a deterministic subset from its
# type's specialised pool based on the farm name hash so different
# farms of the same type aren't identical clones.
_UNIVERSAL_SERVICE_POINTS = ["Rural Bank Branch", "Agricultural Extension Office"]
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

# OP#1114: realistic, owner-style farm-name descriptors per farm type. Farms
# are named "{given} {family} {descriptor}" (e.g. "Maria Santos Farm",
# "Amir Mangudadatu Fishpond"). The first entry is the primary word; the rest
# break collisions with another realistic word instead of a numeric suffix.
_FARM_NAME_DESCRIPTORS = {
    "crop": ["Farm", "Rice Farm", "Family Farm", "Agri Farm", "Farmstead"],
    "livestock": ["Poultry Farm", "Livestock Farm", "Ranch", "Family Farm", "Farmstead"],
    "aquaculture": ["Fishpond", "Aquafarm", "Fisheries", "Fish Farm"],
    "mixed": ["Integrated Farm", "Agri Farm", "Family Farm", "Farm"],
}
_DEFAULT_FARM_DESCRIPTORS = ["Farm", "Family Farm", "Farmstead", "Agri Farm"]


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

        # OP#1114: names already handed out this run, so the ~730 farms drawn
        # from an 86-surname pool don't end up with duplicate farm names (and,
        # because registry IDs are derived from the name, duplicate IDs).
        self._used_names = set()

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

        # Pre-resolve demo area records by code so we can pick an area AND
        # anchor GPS to that area's centroid in the same loop. Doing the
        # area assignment inline (instead of in a separate pass after
        # create) guarantees the pin always sits within the assigned area.
        demo_areas = self.env["spp.area"].search([("code", "like", "PH-%")])
        area_id_by_code = {a.code: a.id for a in demo_areas}

        for bp in blueprints:
            for i in range(bp["count"]):
                # OP#1114: name the farm after its head member and remember the
                # head's given + family name so Phase 3 can (a) make the head an
                # actual member of the group and (b) give every other member the
                # same family name (the household is a family of the head).
                farm_name, head_given, family_name, head_gender = self._generate_household_identity(
                    bp.get("farm_type"), bp.get("head_gender")
                )
                size = round(self.rng.uniform(*bp["size_range"]), 1)
                experience = self.rng.randint(*bp["experience_range"])
                area_id, gps = self._pick_area_and_gps(bp["zone"], area_id_by_code)

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
                if area_id:
                    gvals["area_id"] = area_id

                # OP#915 round-3: realistic phone + bank for every farm group.
                # Phone goes onto the bare partner.phone char AND will be
                # mirrored to a spp.phone.number row after creation.
                group_phone = self._generate_phone()
                group_bank_name = DEMO_BANKS[self.rng.randint(0, len(DEMO_BANKS) - 1)]
                group_acc_no = f"{self.rng.randint(0, 10**12 - 1):012d}"
                gvals["phone"] = group_phone

                group_vals_list.append(gvals)
                member_specs.append(
                    (bp, i, size, gps, group_phone, group_bank_name, group_acc_no, head_given, family_name, head_gender)
                )

        # Phase 2: Batch-create farm groups (farm details auto-created via _inherits)
        # Area is already set in vals (Phase 1) so the GPS pin sits inside
        # the assigned area — no separate area-assignment pass needed.
        _logger.info("Phase 2/5: Creating %d farm groups in batches...", len(group_vals_list))
        groups = self._batch_create("res.partner", group_vals_list)

        # Phase 3: Prepare individual (farmer) member values
        _logger.info("Phase 3/5: Preparing individual members...")
        all_individual_vals = []
        individual_to_group = []
        # OP#915 round-3: parallel list of per-member contact info
        # (phone + head bank account number). Always draw both even for
        # non-head members so the rng sequence is deterministic regardless
        # of role distribution.
        member_contact = []

        for group_idx, (
            bp,
            _instance_idx,
            _size,
            _gps,
            _gphone,
            _gbank,
            _gacc,
            head_given,
            family_name,
            head_gender,
        ) in enumerate(member_specs):
            group_record = groups[group_idx]
            # Given names already used in this household — seeded with the head's
            # so other members don't accidentally reuse it (OP#1114).
            used_given = {head_given}
            for member_spec in bp["members"]:
                # The head takes the gender resolved in Phase 1 (which drove the
                # head name), so the name and gender_id always match — even when
                # the blueprint's head_gender is "any" (OP#1114).
                if member_spec["role"] == "head":
                    gender = head_gender
                else:
                    gender = self._resolve_gender(member_spec.get("gender", "any"))
                # Draw age and turn it into a deterministic birthdate.
                # Month/day are derived from the same rng so the date is
                # stable but varied across members.
                age = self.rng.randint(*member_spec["age_range"])
                birth_month = self.rng.randint(1, 12)
                birth_day = self.rng.randint(1, 28)
                today = datetime.date.today()
                birthdate = datetime.date(today.year - age, birth_month, birth_day)

                # The head is the person the farm is named after; other members
                # get a distinct given name but share the head's family name.
                if member_spec["role"] == "head":
                    given_name = head_given
                else:
                    given_name = self._pick_given_name(gender, used_given)
                used_given.add(given_name)

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
                    "birthdate": birthdate,
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
        for group_idx, member_spec in enumerate(member_specs):
            bp, _instance_idx, size, gps, _gphone, _gbank, _gacc, _hg, _fam, _gen = member_spec
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

    def _create_contact_records(self, groups, individuals, member_specs, member_contact):  # noqa: C901
        """Batch-create spp.phone.number rows + res.partner.bank accounts.

        - Every farm group gets 1 phone row + 1 bank account.
        - Every individual gets 1 phone row.
        - Only head individuals get a bank account (shared bank with their farm).
        """
        Bank = self.env["res.bank"].sudo()  # nosemgrep

        # Resolve / create bank entities once (small fixed list).
        bank_id_by_name = {}
        for bank_name in DEMO_BANKS:
            bank = Bank.search([("name", "=", bank_name)], limit=1)
            if not bank:
                bank = Bank.create({"name": bank_name})
            bank_id_by_name[bank_name] = bank.id

        # ---- Phase: phone numbers ----
        phone_vals = []
        for group, (_bp, _i, _s, _g, gphone, _gb, _ga, _hg, _fam, _gen) in zip(groups, member_specs, strict=False):
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
        for group, (_bp, _i, _s, _g, _gphone, gbank, gacc, _hg, _fam, _gen) in zip(groups, member_specs, strict=False):
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

        # ---- Phase: registry IDs ----
        # Group: national_id + tax_id
        # Head individual: national_id + birth_certificate
        # Non-head individual: national_id
        # Values are derived from the partner name via zlib.crc32 so they
        # are stable across runs without depending on Python's randomised
        # hash().
        import zlib

        def _make_value(kind, salt):
            d = zlib.crc32((kind + "|" + salt).encode("utf-8"))
            if kind == "national_id":
                return f"{d % 10000:04d}-{(d // 10000) % 10000000:07d}-{d % 10}"
            if kind == "passport":
                return f"P{d % 10000000:07d}"
            if kind == "tax_id":
                return f"{d % 1000000000:09d}"
            if kind == "birth_certificate":
                return f"BC-{d % 10000000:07d}"
            return f"{d:010d}"

        # Resolve id-type vocabulary codes once.
        id_type_ids = {}
        for code in ("national_id", "tax_id", "passport", "birth_certificate"):
            ref = self.env.ref(f"spp_vocabulary.code_id_type_{code}", raise_if_not_found=False)
            if ref:
                id_type_ids[code] = ref.id

        id_vals = []
        for group in groups:
            for kind in ("national_id", "tax_id"):
                if kind in id_type_ids:
                    id_vals.append(
                        {
                            "partner_id": group.id,
                            "id_type_id": id_type_ids[kind],
                            # OP#1114: salt with the partner id as well as the
                            # name so the value is unique even if two partners
                            # ever share a name (it stays deterministic per run).
                            "value": _make_value(kind, f"{group.name or 'G'}|{group.id}"),
                            "status": "valid",
                            "verification_method": "self_declared",
                        }
                    )

        for individual, contact in zip(individuals, member_contact, strict=False):
            kinds = ["national_id"]
            if contact["is_head"] and "birth_certificate" in id_type_ids:
                kinds.append("birth_certificate")
            for kind in kinds:
                if kind in id_type_ids:
                    id_vals.append(
                        {
                            "partner_id": individual.id,
                            "id_type_id": id_type_ids[kind],
                            # OP#1114: include the partner id so members who
                            # happen to share a name still get distinct IDs.
                            "value": _make_value(kind, f"{individual.name or 'I'}|{individual.id}"),
                            "status": "valid",
                            "verification_method": "self_declared",
                        }
                    )

        if id_vals:
            self._batch_create("spp.registry.id", id_vals)

        # ---- Phase: service point linkage ----
        # Bank + Extension are universal (always linked). From the type's
        # specialised pool, each farm picks a deterministic subset of size
        # 1..N anchored to its name hash — addresses the QA observation
        # that all groups had the same Service Points count. The subset is
        # stable across reruns because the hash is deterministic.
        sp_records = self.env["spp.service.point"].sudo().search([])  # nosemgrep
        sp_by_name = {sp.name: sp.id for sp in sp_records}
        if sp_by_name:
            for group, (bp, _i, _s, _g, _gphone, _gb, _ga, _hg, _fam, _gen) in zip(groups, member_specs, strict=False):
                pool = sorted(_FARM_TYPE_SPECIALISED_POINTS.get(bp.get("farm_type"), []))
                if pool:
                    digest = zlib.crc32((group.name or "").encode("utf-8"))
                    n_pick = (digest % len(pool)) + 1
                    picked = []
                    for i in range(n_pick):
                        idx = (digest >> (i * 5)) % len(pool)
                        if pool[idx] not in picked:
                            picked.append(pool[idx])
                else:
                    picked = []
                names = _UNIVERSAL_SERVICE_POINTS + picked
                ids = [sp_by_name[n] for n in names if n in sp_by_name]
                if ids:
                    group.write({"service_point_ids": [Command.set(ids)]})

    # =========================================================================
    # Internal: Farm name generation
    # =========================================================================

    def _generate_household_identity(self, farm_type=None, head_gender=None):
        """Generate a unique farm name tied to its head member (OP#1114).

        Returns ``(farm_name, head_given, family_name, head_gender)`` — head_gender
        is resolved to a concrete "male"/"female" here (an "any"/None input is
        resolved) so the given-name pool matches the gender assigned to the head
        member in Phase 3. The farm is named after
        its head — "{head_given} {family_name} {descriptor}", e.g. "Maria Santos
        Farm" — and ``family_name`` is the surname shared by every member of the
        household, so the group reads as a family of the head. The named owner is
        therefore an actual member (the head), not an unrelated invented name.

        Uniqueness of the farm name is preserved by rotating the realistic
        descriptor pool and then re-rolling the owner — never a bare numeric
        suffix.
        """
        descriptors = _FARM_NAME_DESCRIPTORS.get(farm_type, _DEFAULT_FARM_DESCRIPTORS)
        # Resolve the head's gender up front (an "any"/None input becomes a
        # concrete gender) so the given-name pool matches the gender the head
        # member is assigned in Phase 3 — avoids e.g. a male head named "Maria".
        head_gender = self._resolve_gender(head_gender or "any")
        given_pool = _FILIPINO_FEMALE_FIRST_NAMES if head_gender == "female" else _FILIPINO_MALE_FIRST_NAMES

        given = self.rng.choice(given_pool)
        family = self.rng.choice(_FILIPINO_LAST_NAMES)
        for _ in range(30):
            owner = f"{given} {family}"
            # Skip owners reserved as story personas — the owner is now a real
            # member, so it must not clash with a hand-authored persona name.
            if owner not in self._reserved_names:
                for descriptor in descriptors:
                    name = f"{owner} {descriptor}"
                    if name not in self._reserved_names and name not in self._used_names:
                        self._used_names.add(name)
                        return name, given, family, head_gender
            # Whole descriptor pool taken for this owner — re-roll the owner.
            given = self.rng.choice(given_pool)
            family = self.rng.choice(_FILIPINO_LAST_NAMES)

        # Exhausted realistic combinations (practically unreachable) — guarantee
        # a unique value so demo generation never fails.
        base = f"{given} {family} {descriptors[0]}"
        name = base
        suffix = 2
        while name in self._reserved_names or name in self._used_names:
            name = f"{base} {suffix}"
            suffix += 1
        self._used_names.add(name)
        return name, given, family, head_gender

    def _generate_farm_name(self, farm_type=None, head_gender=None):
        """Backwards-compatible wrapper returning just the farm name."""
        return self._generate_household_identity(farm_type, head_gender)[0]

    def _pick_given_name(self, gender, exclude=()):
        """Pick a deterministic given name from the gender-appropriate pool,
        avoiding names already used in the same household where possible."""
        pool = _FILIPINO_MALE_FIRST_NAMES if gender == "male" else _FILIPINO_FEMALE_FIRST_NAMES
        given = self.rng.choice(pool)
        for _ in range(20):
            if given not in exclude:
                return given
            given = self.rng.choice(pool)
        return given

    def _resolve_gender(self, gender_spec):
        """Resolve 'any' gender to 'male' or 'female' deterministically."""
        if gender_spec == "any":
            return self.rng.choice(["male", "female"])
        return gender_spec

    # =========================================================================
    # Internal: GPS generation
    # =========================================================================

    def _pick_area_and_gps(self, zone, area_id_by_code):
        """Pick a demo area for this farm and generate GPS within it.

        Returns:
            tuple(area_id or None, (lng, lat) or None)
        """
        candidates = _AREAS_BY_ZONE.get(zone, _AREAS_BY_ZONE["rural"])
        eligible = [c for c in candidates if c in area_id_by_code]
        if not eligible:
            return None, None
        code = eligible[self.rng.randint(0, len(eligible) - 1)]
        center_lng, center_lat = _AREA_CENTERS[code]
        lng = round(center_lng + self.rng.uniform(-_GPS_JITTER, _GPS_JITTER), 6)
        lat = round(center_lat + self.rng.uniform(-_GPS_JITTER, _GPS_JITTER), 6)
        return area_id_by_code[code], (lng, lat)

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
        """Look up gender vocabulary code ID.

        The res.partner.gender_id Many2one is domain-locked to ISO 5218
        (`urn:iso:std:iso:5218`), which uses numeric codes ('1'=Male,
        '2'=Female). Map the human-readable label to the numeric code.
        """
        iso_code = {"male": "1", "female": "2"}.get(gender, "0")
        return self._get_vocab_code("urn:iso:std:iso:5218", iso_code)

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
