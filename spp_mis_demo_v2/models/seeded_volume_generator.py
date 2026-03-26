# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Seeded Volume Generator for Deterministic Demo Data

Generates households and members from blueprint definitions using:
- random.Random(seed) for all structural choices (ages, incomes, genders, names)

Same seed = identical output every run.
Different locale = different names but same household structure.

Performance optimized with:
- Batched create() calls (~200 records per batch)
- Context flags to disable tracking/mail
- Deferred recomputation
"""

import datetime
import logging
import random

from odoo import fields

from odoo.addons.spp_demo.locale_providers import get_faker_provider
from odoo.addons.spp_demo.models.demo_stories import get_localized_reserved_names

_logger = logging.getLogger(__name__)

BATCH_SIZE = 200


class SeededVolumeGenerator:
    """Deterministic household/member generator using seeded RNG.

    Not an ORM model — a utility class instantiated by the wizard.
    """

    def __init__(self, env, locale, seed=42):
        self.env = env
        self.locale = locale
        self.seed = seed
        self.rng = random.Random(seed)
        self.reserved_names = set(get_localized_reserved_names(locale))

        # Load locale-specific name arrays from provider (no Faker dependency)
        provider = get_faker_provider(locale)
        if provider:
            self._male_names = list(provider.first_names_male)
            self._female_names = list(provider.first_names_female)
            all_last_names = list(provider.last_names)
        else:
            # Fallback: generic English names
            self._male_names = ["John", "James", "Robert", "Michael", "David", "William"]
            self._female_names = ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Susan"]
            all_last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]

        # Extract family names from reserved story names to avoid collisions.
        # Seeded groups use family_name as the group name, so a seeded "Santos"
        # group would be confusing next to story group "Maria Santos".
        reserved_family_names = set()
        for name in self.reserved_names:
            parts = name.split()
            if len(parts) >= 2:
                reserved_family_names.add(parts[-1])
        self._last_names = [n for n in all_last_names if n not in reserved_family_names]

        # Caches
        self._gender_cache = {}
        self._head_type_id = None
        self._group_type_id = None

    # =========================================================================
    # Public API
    # =========================================================================

    def generate_all_households(self, blueprints):
        """Generate all households from blueprint definitions.

        Returns:
            list[dict]: Each dict has 'group' (partner record),
                        'members' (list of partner records),
                        'blueprint' (original blueprint dict)
        """
        total_hh = sum(bp["count"] for bp in blueprints)
        total_members = sum(bp["count"] * len(bp["members"]) for bp in blueprints)
        _logger.info(
            "Starting volume generation: %d blueprints, %d households, ~%d members",
            len(blueprints),
            total_hh,
            total_members,
        )

        households = []
        group_vals_list = []
        member_specs = []  # (blueprint, member_index, group_index_in_batch)

        # Phase 1: Prepare all group values
        _logger.info("Phase 1/%d: Preparing %d household records...", 4, total_hh)
        for bp in blueprints:
            for i in range(bp["count"]):
                group_name = self._generate_group_name()
                income = self.rng.randint(*bp["income_range"])
                gps = self._generate_gps_for_zone(bp["zone"])

                gvals = {
                    "name": group_name,
                    "is_registrant": True,
                    "is_group": True,
                    "registration_date": self._random_registration_date(),
                }
                if self._get_group_type_id():
                    gvals["group_type_id"] = self._get_group_type_id()

                partner_fields = self.env["res.partner"]._fields
                if "income" in partner_fields:
                    gvals["income"] = income
                if "household_size" in partner_fields:
                    gvals["household_size"] = len(bp["members"])
                if gps and "gps_coordinates" in partner_fields:
                    gvals["gps_coordinates"] = gps

                group_vals_list.append(gvals)
                member_specs.append((bp, i))

        # Phase 2: Batch-create groups
        _logger.info("Phase 2/%d: Creating %d groups in batches...", 4, len(group_vals_list))
        groups = self._batch_create("res.partner", group_vals_list)

        # Phase 3: Prepare and batch-create all individual members
        _logger.info("Phase 3/%d: Preparing individual members...", 4)
        all_individual_vals = []
        individual_to_group = []  # (group_record, member_spec_from_blueprint)

        for group_idx, (bp, _instance_idx) in enumerate(member_specs):
            group_record = groups[group_idx]
            for member_spec in bp["members"]:
                gender = self._resolve_gender(member_spec.get("gender", "any"))
                age = self.rng.randint(*member_spec["age_range"])
                given_name, family_name = self._generate_member_name(gender)

                # Compute name in standard format
                name_parts = [
                    f"{family_name}," if family_name and given_name else family_name or "",
                    given_name,
                ]
                computed_name = " ".join(filter(None, name_parts)).upper()

                birthdate = self._birthdate_from_age(age, group_record.registration_date)

                ival = {
                    "name": computed_name,
                    "given_name": given_name,
                    "family_name": family_name,
                    "is_registrant": True,
                    "is_group": False,
                    "gender_id": self._get_gender_id(gender),
                    "birthdate": birthdate,
                    "registration_date": group_record.registration_date,
                }

                partner_fields = self.env["res.partner"]._fields
                if "income" in partner_fields and member_spec["role"] in ("head", "spouse", "adult"):
                    ival["income"] = self.rng.randint(0, 30000)

                all_individual_vals.append(ival)
                individual_to_group.append((group_record, member_spec))

        _logger.info("Phase 3/%d: Creating %d individuals in batches...", 4, len(all_individual_vals))
        individuals = self._batch_create("res.partner", all_individual_vals)

        # Phase 4: Create memberships and link to groups
        _logger.info("Phase 4/%d: Creating %d memberships...", 4, len(individuals))
        membership_vals_list = []
        head_type_id = self._get_head_type_id()

        current_group = None
        has_head_for_current_group = False

        for ind_idx, individual in enumerate(individuals):
            group_record, member_spec = individual_to_group[ind_idx]

            # Track head assignment per group
            if group_record != current_group:
                current_group = group_record
                has_head_for_current_group = False

            mval = {
                "group": group_record.id,
                "individual": individual.id,
                "start_date": group_record.registration_date,
            }

            if member_spec["role"] == "head" and not has_head_for_current_group and head_type_id:
                mval["membership_type_ids"] = [(4, head_type_id)]
                has_head_for_current_group = True
                # Update group name to head's family name
                group_record.name = individual.family_name or individual.name

            membership_vals_list.append(mval)

        self._batch_create("spp.group.membership", membership_vals_list)

        # Build result list
        group_households = {}
        for ind_idx, individual in enumerate(individuals):
            group_record = individual_to_group[ind_idx][0]
            if group_record.id not in group_households:
                group_households[group_record.id] = {
                    "group": group_record,
                    "members": [],
                    "blueprint": member_specs[list(groups).index(group_record)][0],
                }
            group_households[group_record.id]["members"].append(individual)

        households = list(group_households.values())
        _logger.info(
            "Volume generation complete: %d households, %d individuals",
            len(groups),
            len(individuals),
        )
        return households

    def enroll_in_programs(self, households, program_map):
        """Enroll households in programs based on eligibility flags.

        Handles both group-target and individual-target programs:
        - Group programs (UCG, CTP, ERF, DSG): enroll the household group
        - Individual programs (ESP): enroll qualifying individual members
        - Food Assistance: enroll individual members from flagged blueprints

        After creation, backdates enrollment_date via SQL (it's a computed
        field that always sets Datetime.now()) and adds state variety for realism.
        """
        # Identify individual-target programs
        individual_programs = set()
        for prog_id, program in program_map.items():
            if program.target_type == "individual":
                individual_programs.add(prog_id)

        enrollment_vals = []
        # Track (partner_id, registration_date) for backdating
        enrollment_dates = []

        for hh in households:
            bp = hh["blueprint"]
            group = hh["group"]
            reg_date = group.registration_date or fields.Date.today()

            for prog_id, is_eligible in bp.get("eligibility", {}).items():
                if not is_eligible:
                    continue
                program = program_map.get(prog_id)
                if not program:
                    continue

                if prog_id in individual_programs:
                    # Individual-target program: enroll qualifying members
                    for member in hh["members"]:
                        # ESP: only enroll elderly members (age >= 60 from blueprint)
                        if prog_id == "elderly_social_pension":
                            member_spec = self._find_member_spec(bp, member)
                            if not member_spec or member_spec.get("age_range", (0, 0))[0] < 60:
                                continue
                        enrollment_vals.append(
                            {
                                "program_id": program.id,
                                "partner_id": member.id,
                                "state": "enrolled",
                            }
                        )
                        enrollment_dates.append(member.registration_date or reg_date)
                else:
                    # Group-target program: enroll the household
                    enrollment_vals.append(
                        {
                            "program_id": program.id,
                            "partner_id": group.id,
                            "state": "enrolled",
                        }
                    )
                    enrollment_dates.append(reg_date)

            # Individual-level food assistance
            if bp.get("individual_food_assistance"):
                fa_program = program_map.get("food_assistance")
                if fa_program:
                    for member in hh["members"]:
                        enrollment_vals.append(
                            {
                                "program_id": fa_program.id,
                                "partner_id": member.id,
                                "state": "enrolled",
                            }
                        )
                        enrollment_dates.append(member.registration_date or reg_date)

        if not enrollment_vals:
            return

        _logger.info("Enrolling %d program memberships...", len(enrollment_vals))
        memberships = self._batch_create("spp.program.membership", enrollment_vals)

        # Add state variety and backdate enrollment dates in one pass.
        # enrollment_date is @api.depends("state") so we must do BOTH via SQL
        # after all ORM operations are complete, to prevent recomputation.
        self.env.flush_all()
        self._apply_membership_realism(memberships, enrollment_dates)

    def _find_member_spec(self, blueprint, member_record):
        """Find the blueprint member spec that matches a created member record."""
        members = blueprint.get("members", [])
        # Match by index in the household — members were created in blueprint order
        for spec in members:
            if spec.get("role") in ("head", "elderly") and spec.get("age_range", (0, 0))[0] >= 60:
                return spec
        return None

    def _apply_membership_realism(self, memberships, enrollment_dates):
        """Apply state variety and backdate enrollment dates via SQL.

        enrollment_date is @api.depends("state") — any ORM state change triggers
        recomputation to Datetime.now(). To prevent this, we:
        1. flush_all() to commit ORM state
        2. Apply state variety + date backdating together in raw SQL
        3. Invalidate the cache so ORM sees our changes
        """
        if not memberships:
            return

        membership_ids = memberships.ids
        exited_count = paused_count = not_eligible_count = 0

        for idx, mem_id in enumerate(membership_ids):
            # Determine state
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

            # Determine enrollment date from registration date
            if idx < len(enrollment_dates):
                reg_date = enrollment_dates[idx]
                enrollment_dt = datetime.datetime.combine(reg_date, datetime.time(8, 0, 0))
            else:
                enrollment_dt = datetime.datetime.now()

            # Single SQL update for both state and enrollment_date
            self.env.cr.execute(
                "UPDATE spp_program_membership SET state = %s, enrollment_date = %s WHERE id = %s",
                (state, enrollment_dt, mem_id),
            )

        memberships.invalidate_recordset(["state", "enrollment_date"])
        _logger.info(
            "Realism for %d memberships: %d exited, %d paused, %d not_eligible, dates backdated",
            len(membership_ids),
            exited_count,
            paused_count,
            not_eligible_count,
        )

    # =========================================================================
    # Internal helpers
    # =========================================================================

    def _batch_create(self, model_name, vals_list):
        """Create records in batches for performance."""
        if not vals_list:
            return self.env[model_name]

        all_records = self.env[model_name]
        for i in range(0, len(vals_list), BATCH_SIZE):
            batch = vals_list[i : i + BATCH_SIZE]
            records = self.env[model_name].create(batch)
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

    def _generate_group_name(self):
        """Generate a household name from seeded RNG."""
        family_name = self.rng.choice(self._last_names)
        return f"{family_name} Household"

    def _generate_member_name(self, gender):
        """Generate a (given_name, family_name) tuple, avoiding reserved names."""
        max_attempts = 20
        for _ in range(max_attempts):
            if gender == "male":
                given = self.rng.choice(self._male_names)
            else:
                given = self.rng.choice(self._female_names)
            family = self.rng.choice(self._last_names)
            full_name = f"{given} {family}"
            if full_name not in self.reserved_names:
                return given, family
        # After max attempts, return anyway (extremely unlikely collision)
        return given, family

    def _resolve_gender(self, gender_spec):
        """Resolve 'any' gender to 'male' or 'female' deterministically."""
        if gender_spec == "any":
            return self.rng.choice(["male", "female"])
        return gender_spec

    def _get_gender_id(self, gender):
        """Look up gender vocabulary code ID, with caching."""
        if gender not in self._gender_cache:
            gender_code_map = {"male": "1", "female": "2"}
            iso_code = gender_code_map.get(gender, "1")
            VocabCode = self.env["spp.vocabulary.code"]
            code = VocabCode.get_code("urn:iso:std:iso:5218", iso_code)
            self._gender_cache[gender] = code.id if code else False
        return self._gender_cache[gender]

    def _get_head_type_id(self):
        """Get the 'head' membership type ID, with caching."""
        if self._head_type_id is None:
            head_type = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
            self._head_type_id = head_type.id if head_type else False
        return self._head_type_id

    def _get_group_type_id(self):
        """Get a default group type ID, with caching."""
        if self._group_type_id is None:
            group_types = self.env["spp.vocabulary.code"].search(
                [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-type")],
                limit=1,
            )
            self._group_type_id = group_types[0].id if group_types else False
        return self._group_type_id

    def _birthdate_from_age(self, age, reference_date=None):
        """Calculate a deterministic birthdate from age using seeded RNG.

        Uses reference_date (registration date) to ensure birthdate < registration_date.
        """
        ref = reference_date or fields.Date.today()
        birth_year = ref.year - age - 1
        birth_month = self.rng.randint(1, 12)
        birth_day = self.rng.randint(1, 28)
        return datetime.date(birth_year, birth_month, birth_day)

    def _random_registration_date(self):
        """Generate a registration date within the last 2 years."""
        days_back = self.rng.randint(30, 730)
        return fields.Date.today() - datetime.timedelta(days=days_back)

    def _generate_gps_for_zone(self, zone):
        """Generate GPS coordinates based on zone type.

        Uses the company's country GPS bounds if available.
        """
        country = self.env.company.country_id
        if not country or not all([country.lat_min, country.lat_max, country.lon_min, country.lon_max]):
            return None

        lat_min, lat_max = country.lat_min, country.lat_max
        lon_min, lon_max = country.lon_min, country.lon_max

        # Narrow the range for urban zones (center of country)
        if zone == "urban":
            lat_center = (lat_min + lat_max) / 2
            lon_center = (lon_min + lon_max) / 2
            lat_range = (lat_max - lat_min) * 0.15
            lon_range = (lon_max - lon_min) * 0.15
            lat_min, lat_max = lat_center - lat_range, lat_center + lat_range
            lon_min, lon_max = lon_center - lon_range, lon_center + lon_range
        elif zone == "peri_urban":
            lat_center = (lat_min + lat_max) / 2
            lon_center = (lon_min + lon_max) / 2
            lat_range = (lat_max - lat_min) * 0.3
            lon_range = (lon_max - lon_min) * 0.3
            lat_min, lat_max = lat_center - lat_range, lat_center + lat_range
            lon_min, lon_max = lon_center - lon_range, lon_center + lon_range

        lat = round(self.rng.uniform(lat_min, lat_max), 6)
        lon = round(self.rng.uniform(lon_min, lon_max), 6)
        return f"{lat}, {lon}"
