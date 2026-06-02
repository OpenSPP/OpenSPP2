# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import datetime
import logging
import random
import re

from faker import Faker

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.job_worker.delay import group

_logger = logging.getLogger(__name__)


class SPPDemoDataGenerator(models.Model):
    _name = "spp.demo.data.generator"
    _description = "SPP Demo Data Generator"

    # Cache for compiled regex patterns to avoid recompilation
    _regex_cache = {}

    def _default_number_of_groups(self):
        default_settings = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        return int(default_settings.get_param("spp_demo.number_of_groups", 10))

    def _default_members_range_from(self):
        default_settings = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        return int(default_settings.get_param("spp_demo.members_range_from", 1))

    def _default_members_range_to(self):
        default_settings = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        return int(default_settings.get_param("spp_demo.members_range_to", 10))

    def _default_batch_size(self):
        default_settings = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        return int(default_settings.get_param("spp_demo.batch_size", 100))

    def _default_locale_origin(self):
        country = self.env.user.company_id.country_id
        if country:
            return country.id
        return self.env.ref("base.us").id

    def _default_queue_job_minimum_size(self):
        default_settings = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        return int(default_settings.get_param("spp_demo.queue_job_minimum_size", 500))

    def _default_days_back(self):
        default_settings = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        return int(default_settings.get_param("spp_demo.days_back", 90))

    # Gender codes matching ISO 5218 vocabulary (urn:iso:std:iso:5218)
    # Code 1 = Male, Code 2 = Female
    GENDERS = [
        "Male",
        "Female",
    ]
    # Mapping from display name to ISO 5218 code
    GENDER_CODE_MAP = {
        "male": "1",
        "female": "2",
        "Male": "1",
        "Female": "2",
    }

    name = fields.Char(string="Name", required=True)
    is_remember_settings = fields.Boolean(string="Remember Settings", default=False)
    number_of_groups = fields.Integer(string="Number of Groups", default=_default_number_of_groups, required=True)
    members_range_from = fields.Integer(
        string="Members per Group (From)", default=_default_members_range_from, required=True
    )
    members_range_to = fields.Integer(string="Members per Group (To)", default=_default_members_range_to, required=True)
    locale_origin = fields.Many2one(
        "res.country", string="Locale Origin", required=True, default=_default_locale_origin
    )
    locale_origin_faker_locale = fields.Char(string="Locale Origin Faker Locale", related="locale_origin.faker_locale")
    batch_size = fields.Integer(string="Batch Size", default=_default_batch_size, required=True)
    days_back = fields.Integer(
        string="Days Back",
        default=_default_days_back,
        required=True,
        help="Generate data within the last N days. Used for time-based demo data generation.",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("in_progress", "In Progress"), ("completed", "Completed"), ("cancelled", "Cancelled")],
        string="State",
        default="draft",
        required=True,
    )
    group_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Group Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-type')]",
    )
    id_type_ids = fields.One2many("spp.demo.data.id.types", "demo_data_generator_id", string="ID Types")
    bank_type_ids = fields.One2many("spp.demo.data.bank.types", "demo_data_generator_id", string="Bank Types")
    percentage_with_bank_account = fields.Integer(string="% with Banks", default=100, required=True)
    percentage_with_ids = fields.Integer(string="% with IDs", default=100, required=True)
    percentage_with_gps = fields.Integer(string="% with GPS Coordinates", default=100, required=True)

    # Geographic demo data settings
    demo_country = fields.Selection(
        [
            ("phl", "Philippines"),
            ("lka", "Sri Lanka"),
            ("tgo", "Togo"),
        ],
        string="Demo Country",
        default="phl",
        help="Country for geographic demo data (areas, shapes)",
    )
    load_geographic_data = fields.Boolean(
        string="Load Geographic Data",
        default=True,
        help="Load curated areas for the selected country during demo generation",
    )

    is_locked = fields.Boolean(string="Locked", default=False)
    locked_reason = fields.Text(string="Locked Reason")

    queue_job_minimum_size = fields.Integer(
        string="Queue Job Minimum Size",
        default=_default_queue_job_minimum_size,
    )
    use_job_queue = fields.Boolean(
        string="Use Job Queue",
        compute="_compute_use_job_queue",
    )
    generated_group_ids = fields.One2many(
        "res.partner",
        "demo_data_group_generator_id",
        string="Generated Registrants",
        readonly=True,
    )
    generated_individual_ids = fields.One2many(
        "res.partner",
        "demo_data_individual_generator_id",
        string="Generated Individuals",
        readonly=True,
    )
    generation_log_ids = fields.One2many(
        "spp.demo.data.generation.log",
        "demo_data_generator_id",
        string="Generation Logs",
        readonly=True,
    )
    generation_log_count = fields.Integer(
        string="Failed Generations",
        compute="_compute_generation_log_count",
    )

    def _compute_generation_log_count(self):
        for rec in self:
            rec.generation_log_count = len(rec.generation_log_ids)

    def generate_demo_data(self):
        self.ensure_one()

        # Load geographic data if enabled
        if self.load_geographic_data and self.demo_country:
            self._load_geographic_data()

        faker_code = self.locale_origin.faker_locale or "en_US"
        fake = Faker(faker_code)
        if self.members_range_from > self.members_range_to:
            self.members_range_from = self._default_members_range_from()
            self.members_range_to = self._default_members_range_to()
            raise ValidationError(
                "Members per Group (From) cannot be greater than Members per Group (To). Resetting to default values."
            )

        self.state = "in_progress"
        self.is_locked = True
        self.locked_reason = "Data generation in progress..."
        if not self.use_job_queue:
            for _ in range(self.number_of_groups):
                self._generate_demo_data(fake)
            self.state = "completed"
            self.is_locked = False
            message = "The data generation has been completed."
            self.locked_reason = message
            kind = "success"
        else:
            self._async_generate_demo_data()
            message = "The data generation has been started and is running in the background."
            kind = "info"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Data Generation",
                "message": message,
                "sticky": False,
                "type": kind,
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def _load_geographic_data(self):
        """Load curated geographic data for the selected country.

        Uses the DemoAreaLoader to load area kinds, areas, and optionally
        GIS polygon shapes for the demo country.
        """
        if not self.demo_country:
            return

        loader = self.env["spp.demo.area.loader"]
        try:
            loader.load_country_areas(self.demo_country, load_shapes=True)
            _logger.info("Loaded geographic data for %s", self.demo_country)
        except Exception as e:
            _logger.warning("Could not load geographic data for %s: %s", self.demo_country, e)

    def _generate_demo_data(self, fake):
        group = self.generate_groups(fake)
        num_members = fake.random_int(self.members_range_from, self.members_range_to)
        have_head_member = False
        new_group_name = False
        for _ in range(num_members):
            head_membership = self.head_member_getter(group)
            is_head_member = random.choice([True, False]) if not have_head_member else False

            # Check if last member and no head member assigned yet
            if _ == num_members - 1 and not have_head_member:
                is_head_member = True

            individual = self.generate_individuals(fake)

            # Members inherit area from their group
            if group.area_id and individual.area_id != group.area_id:
                individual.write({"area_id": group.area_id.id})

            membership_vals = self.get_group_membership_vals(fake, group, individual)
            if is_head_member and not head_membership:
                have_head_member = True
                new_group_name = individual.family_name
                group.name = new_group_name
                head_type = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
                membership_vals["membership_type_ids"] = [(4, head_type.id)]

            self.env["spp.group.membership"].create(membership_vals)

    def head_member_getter(self, group):
        memberships = self.env["spp.group.membership"].search([("group", "=", group.id)])
        head_membership_type = self.env["spp.vocabulary.code"].get_code(
            "urn:openspp:vocab:group-membership-type", "head"
        )
        head_membership = memberships.filtered(lambda x: head_membership_type in x.membership_type_ids)
        return head_membership

    def _async_generate_demo_data(self):
        jobs = []
        batch_size = self.batch_size
        batches = [
            (start, min(start + batch_size, self.number_of_groups))
            for start in range(0, self.number_of_groups, batch_size)
        ]
        for batch in batches:
            jobs.append(self.delayable()._process_batch(batch))
        main_job = group(*jobs)
        main_job.on_done(self.delayable()._mark_done())
        main_job.delay()

    def _process_batch(self, batch):
        self.ensure_one()
        faker_code = self.locale_origin.faker_locale or "en_US"
        fake = Faker(faker_code)
        for _ in range(batch[0], batch[1]):
            self._generate_demo_data(fake)

    def _mark_done(self):
        # Refresh GIS reports if the module is installed
        self._refresh_gis_reports()

        self.state = "completed"
        self.is_locked = False
        message = "The data generation has been completed."
        self.locked_reason = message

    def _refresh_gis_reports(self):
        """Refresh all active GIS reports so map data is available immediately.

        Only runs if spp_gis_report is installed (not a hard dependency).
        """
        if "spp.gis.report" not in self.env:
            return

        GISReport = self.env["spp.gis.report"]
        reports = GISReport.search([("active", "=", True)])

        if not reports:
            _logger.info("No active GIS reports found to refresh")
            return

        for report in reports:
            report_name = report.name
            try:
                report._refresh_data()
                _logger.info("Refreshed GIS report: %s", report_name)
            except Exception:
                _logger.exception("Failed to refresh GIS report: %s", report_name)

    def generate_groups(self, fake):
        group_vals = self.get_group_vals(fake)
        group = self.env["res.partner"].create(group_vals)
        self.create_ids(fake, group)
        self.create_phone_numbers(fake, group)
        self.create_bank_accounts(fake, group)
        self.create_gps_coordinates(fake, group)
        return group

    def generate_individuals(self, fake):
        individual_vals = self.get_individual_vals(fake)
        # Store the values we want to ensure are set
        family_name = individual_vals.get("family_name")
        given_name = individual_vals.get("given_name")
        addl_name = individual_vals.get("addl_name", "")

        # Create the individual record
        individual = self.env["res.partner"].create(individual_vals)

        # CRITICAL: Explicitly write the fields after creation
        # This ensures they persist even if something clears them during create
        if not individual.is_group and (family_name or given_name):
            # Always write family_name and given_name to ensure they're set
            write_vals = {}
            if family_name:
                write_vals["family_name"] = family_name
            if given_name:
                write_vals["given_name"] = given_name
            if addl_name:
                write_vals["addl_name"] = addl_name

            # Recompute and set name in correct format
            if family_name or given_name:
                name_vals = [
                    f"{family_name},"
                    if family_name and (given_name or addl_name)
                    else f"{family_name}"
                    if family_name
                    else "",
                    given_name or "",
                    addl_name or "",
                ]
                final_name = " ".join(filter(None, name_vals)).upper()
                write_vals["name"] = final_name

            # Write all fields - this is critical to ensure persistence
            if write_vals:
                individual.write(write_vals)

        self.create_ids(fake, individual)
        self.create_phone_numbers(fake, individual)
        self.create_bank_accounts(fake, individual)
        self.create_gps_coordinates(fake, individual)
        return individual

    def _get_leaf_areas(self):
        """Get leaf-level areas (areas with no children) for assignment.

        Prefers the deepest level of the area hierarchy so that
        GIS reports can aggregate upward through parent areas.

        Returns:
            recordset: spp.area records at the deepest available level
        """
        Area = self.env["spp.area"]
        all_areas = Area.search([])
        if not all_areas:
            return all_areas
        max_level = max(all_areas.mapped("area_level"))
        return all_areas.filtered(lambda a: a.area_level == max_level)

    def get_group_vals(self, fake):
        registration_date = self.get_random_date(
            fake,
            datefrom=fields.Date.today().replace(year=fields.Date.today().year - 5),
            dateto=fields.Date.today(),
        )
        address = fake.address()

        group_vals = {
            "demo_data_group_generator_id": self.id,
            "name": fake.company(),
            "is_registrant": True,
            "is_group": True,
            "registration_date": registration_date,
            "create_date": registration_date,
            "address": address,
        }
        if self.group_type_id:
            group_vals["group_type_id"] = self.group_type_id.id
        else:
            group_types = self.env["spp.vocabulary.code"].search(
                [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-type")]
            )
            if group_types:
                group_vals["group_type_id"] = random.choice(group_types).id

        # Assign area (prefer leaf-level for proper GIS report aggregation)
        leaf_areas = self._get_leaf_areas()
        if leaf_areas:
            group_vals["area_id"] = random.choice(leaf_areas).id

        return group_vals

    def get_individual_vals(self, fake):
        birth_date = self.get_random_date(
            fake,
            datefrom=fields.Date.today().replace(year=fields.Date.today().year - 50),
            dateto=fields.Date.today().replace(year=fields.Date.today().year - 1),
        )
        registration_date = self.get_random_date(
            fake,
            datefrom=birth_date + datetime.timedelta(days=365),
            dateto=fields.Date.today(),
        )
        gender = random.choice(self.GENDERS)
        gender_id = self.get_gender_id(gender)
        first_name = fake.first_name_male() if gender == "Male" else fake.first_name_female()
        last_name = fake.last_name()

        # Compute name in the same format as the name_change onchange method
        # Format: "FAMILY_NAME, GIVEN_NAME ADDITIONAL_NAME" (uppercase)
        name_vals = [
            f"{last_name}," if last_name and first_name else f"{last_name}" if last_name else "",
            first_name,
            "",  # addl_name - empty for now
        ]
        name = " ".join(filter(None, name_vals)).upper()

        address = fake.address()

        individual_vals = {
            "demo_data_individual_generator_id": self.id,
            "name": name,
            "family_name": last_name,
            "given_name": first_name,
            "is_registrant": True,
            "is_group": False,
            "gender_id": gender_id,
            "birthdate": birth_date,
            "registration_date": registration_date,
            "create_date": registration_date,
            "address": address,
        }

        # Add optional fields if they exist in the model
        partner_fields = self.env["res.partner"]._fields

        # Email field
        if "email" in partner_fields:
            individual_vals["email"] = fake.email()

        # Area field — prefer leaf-level areas for proper GIS aggregation
        if "area_id" in partner_fields:
            leaf_areas = self._get_leaf_areas()
            if leaf_areas:
                individual_vals["area_id"] = random.choice(leaf_areas).id

        # Birth place
        if "birth_place" in partner_fields:
            individual_vals["birth_place"] = fake.city()

        # Additional name (middle name) - randomly add for some individuals
        addl_name_value = None
        if "addl_name" in partner_fields and random.choice([True, False]):
            addl_name_value = fake.first_name()
            individual_vals["addl_name"] = addl_name_value
            # Recompute name with addl_name
            name_vals = [
                f"{last_name}," if last_name and first_name else f"{last_name}" if last_name else "",
                first_name,
                addl_name_value,
            ]
            individual_vals["name"] = " ".join(filter(None, name_vals)).upper()

        # Civil status
        if "civil_status" in partner_fields:
            civil_statuses = ["single", "married", "divorced", "widowed"]
            individual_vals["civil_status"] = random.choice(civil_statuses)

        # Occupation
        if "occupation" in partner_fields:
            individual_vals["occupation"] = fake.job()

        # Income (random value between 0 and 100000)
        if "income" in partner_fields:
            individual_vals["income"] = round(random.uniform(0, 100000), 2)

        # Log for debugging
        _logger.debug(
            "Creating individual with family_name=%s, given_name=%s, name=%s",
            last_name,
            first_name,
            individual_vals.get("name"),
        )

        return individual_vals

    def get_group_membership_vals(self, fake, group, individual):
        start_date = self.get_random_date(
            fake,
            datefrom=group.registration_date,
            dateto=fields.Date.today(),
        )
        return {
            "group": group.id,
            "individual": individual.id,
            "start_date": start_date,
        }

    def get_gender_id(self, gender):
        """Get gender vocabulary code ID for the given gender string.

        Uses ISO 5218 vocabulary codes (urn:iso:std:iso:5218):
        - Code 1 = Male
        - Code 2 = Female

        Args:
            gender: Gender string ('Male', 'Female', 'male', 'female')

        Returns:
            int: ID of the vocabulary code record
        """
        # Map gender string to ISO 5218 code
        iso_code = self.GENDER_CODE_MAP.get(gender, "1")  # Default to Male if unknown

        # Look up vocabulary code
        VocabCode = self.env["spp.vocabulary.code"]
        gender_code = VocabCode.get_code("urn:iso:std:iso:5218", iso_code)

        if not gender_code:
            # Fallback: search by display name
            gender_code = VocabCode.search(
                [
                    ("namespace_uri", "=", "urn:iso:std:iso:5218"),
                    ("display", "ilike", gender),
                ],
                limit=1,
            )

        return gender_code.id if gender_code else False

    def get_gender(self, gender):
        """Alias for get_gender_id for backward compatibility."""
        return self.get_gender_id(gender)

    @api.model
    def lookup_gender_id(self, gender):
        """Class method to look up gender ID without requiring a generator instance.

        This is a utility method that can be called from other modules.

        Args:
            gender: Gender string ('Male', 'Female', 'male', 'female')

        Returns:
            int: ID of the vocabulary code record, or False if not found
        """
        gender_code_map = {
            "male": "1",
            "female": "2",
            "Male": "1",
            "Female": "2",
        }
        iso_code = gender_code_map.get(gender, "1")
        VocabCode = self.env["spp.vocabulary.code"]
        gender_code = VocabCode.get_code("urn:iso:std:iso:5218", iso_code)
        if not gender_code:
            gender_code = VocabCode.search(
                [("namespace_uri", "=", "urn:iso:std:iso:5218"), ("display", "ilike", gender)],
                limit=1,
            )
        return gender_code.id if gender_code else False

    def _get_area_for_profile(self, profile):
        """Get area_id based on profile configuration.

        Supports three ways to assign areas:
        1. area_ref: Direct XML ID reference (e.g., 'spp_demo.area_phl_ncr_quezon_city')
        2. area_kind: Pick random area of specified kind (e.g., 'municipality')
        3. Fallback: Pick any available area

        Args:
            profile: Dict with optional 'area_ref' or 'area_kind' keys

        Returns:
            int or False: area_id or False if no areas available
        """
        if not profile:
            return False

        # Priority 1: Explicit area reference
        area_ref = profile.get("area_ref")
        if area_ref:
            area = self.env.ref(area_ref, raise_if_not_found=False)
            if area:
                return area.id

        # Priority 2: Random area of specified kind
        area_kind_name = profile.get("area_kind")
        if area_kind_name:
            # Search for area kind by name (case-insensitive partial match)
            kind = self.env["spp.area.type"].search(
                [("name", "ilike", area_kind_name)],
                limit=1,
            )
            if kind:
                areas = self.env["spp.area"].search([("area_type_id", "=", kind.id)])
                if areas:
                    return random.choice(areas).id

        # Priority 3: Any available area (limit search for performance)
        areas = self.env["spp.area"].search([], limit=100)
        if areas:
            return random.choice(areas).id

        return False

    @api.model
    def create_individual_from_params(self, name, gender, age, extra_vals=None):
        """Create an individual registrant from parameters.

        Utility method for creating individuals without a full generator session.
        Can be called from other modules (e.g., spp_mis_demo_v2).

        Args:
            name: Full name (e.g., "John Smith")
            gender: Gender string ('male', 'female')
            age: Age in years
            extra_vals: Optional dict of additional field values

        Returns:
            res.partner: Created partner record
        """
        # Parse name into parts
        name_parts = name.split(" ", 1)
        given_name = name_parts[0]
        family_name = name_parts[1] if len(name_parts) > 1 else ""

        # Compute name in standard format: "FAMILY_NAME, GIVEN_NAME" (uppercase)
        name_vals = [
            f"{family_name}," if family_name and given_name else family_name or "",
            given_name,
        ]
        computed_name = " ".join(filter(None, name_vals)).upper()

        # Calculate birthdate from age
        birth_year = fields.Date.today().year - age
        birth_month = random.randint(1, 12)
        birth_day = random.randint(1, 28)
        birthdate = f"{birth_year}-{birth_month:02d}-{birth_day:02d}"

        partner_vals = {
            "name": computed_name,
            "family_name": family_name,
            "given_name": given_name,
            "is_registrant": True,
            "is_group": False,
            "gender_id": self.lookup_gender_id(gender.capitalize()),
            "birthdate": birthdate,
        }

        # Merge extra values if provided
        if extra_vals:
            partner_vals.update(extra_vals)

        individual = self.env["res.partner"].create(partner_vals)

        # Ensure name fields are persisted
        if family_name or given_name:
            write_vals = {}
            if family_name:
                write_vals["family_name"] = family_name
            if given_name:
                write_vals["given_name"] = given_name
            if write_vals:
                individual.write(write_vals)

        return individual

    @api.model
    def create_group_from_params(self, name, extra_vals=None):
        """Create a group registrant from parameters.

        Utility method for creating groups without a full generator session.
        Can be called from other modules (e.g., spp_mis_demo_v2).

        Args:
            name: Group name
            extra_vals: Optional dict of additional field values

        Returns:
            res.partner: Created partner record
        """
        group_vals = {
            "name": name,
            "is_registrant": True,
            "is_group": True,
        }

        # Merge extra values if provided
        if extra_vals:
            group_vals.update(extra_vals)

        return self.env["res.partner"].create(group_vals)

    def get_random_date(self, fake, datefrom, dateto):
        return fake.date_between_dates(date_start=datefrom, date_end=dateto)

    def _log_generation_failure(
        self,
        registrant,
        operation_type,
        failure_reason,
        error_message,
        attempts=0,
        validation_regex=None,
        generated_value=None,
        exception_details=None,
    ):
        """
        Log a generation failure to the database for tracking and debugging.
        """
        log_vals = {
            "demo_data_generator_id": self.id,
            "registrant_id": registrant.id if registrant else None,
            "registrant_type": "group" if registrant and registrant.is_group else "individual",
            "operation_type": operation_type,
            "failure_reason": failure_reason,
            "error_message": error_message,
            "attempts": attempts,
            "validation_regex": validation_regex,
            "generated_value": generated_value,
            "exception_details": exception_details,
        }
        self.env["spp.demo.data.generation.log"].create(log_vals)

    def get_id_type(self, target_type):
        if self.id_type_ids:
            id_type = self.env["spp.demo.data.id.types"].search(
                [("target_type", "=", target_type), ("demo_data_generator_id", "=", self.id)]
            )
            if id_type:
                if len(self.id_type_ids) == 1:
                    return id_type.id_type_id.id, id_type.id_type_id.id_validation
                # Collect all id_type_id values from the recordset
                id_type_records = id_type.mapped("id_type_id")
                random_id = random.choice(id_type_records)
                return random_id.id, random_id.id_validation
            return None, None

        id_type_id = self.env["spp.id.type"].search([])
        if id_type_id:
            id_type = random.choice(id_type_id)
            return id_type.id if len(id_type_id) > 1 else id_type.id, id_type.id_validation

        return None, None

    def generate_id_from_regex(self, regex_pattern):  # noqa: C901
        """
        Generate a string that matches the given regex pattern.
        Supports common regex patterns used in ID validation.
        """
        _logger.info(f"Generating ID from regex: {regex_pattern}")
        if not regex_pattern:
            return None

        # Remove anchors if present
        pattern = regex_pattern.strip()
        pattern = re.sub(r"^\^", "", pattern)
        pattern = re.sub(r"\$$", "", pattern)

        result = []
        i = 0

        while i < len(pattern):
            char = pattern[i]

            # Handle groups with alternation (...)
            if char == "(":
                # Find the matching closing parenthesis
                depth = 1
                end = i + 1
                while end < len(pattern) and depth > 0:
                    if pattern[end] == "(":
                        depth += 1
                    elif pattern[end] == ")":
                        depth -= 1
                    end += 1

                group_content = pattern[i + 1 : end - 1]
                i = end

                # Check for alternation (|)
                if "|" in group_content:
                    # Split by | and choose one randomly
                    alternatives = group_content.split("|")
                    chosen = random.choice(alternatives)
                    # Recursively generate from the chosen alternative
                    generated = self.generate_id_from_regex("^" + chosen + "$")
                    if generated:
                        result.append(generated)
                else:
                    # No alternation, just recursively generate from the group content
                    generated = self.generate_id_from_regex("^" + group_content + "$")
                    if generated:
                        result.append(generated)

            # Handle character classes [...]
            elif char == "[":
                end = pattern.index("]", i)
                char_class = pattern[i + 1 : end]
                i = end + 1

                # Check for quantifier immediately after ]
                count = 1
                if i < len(pattern) and pattern[i] == "{":
                    q_end = pattern.index("}", i)
                    quantifier = pattern[i + 1 : q_end]

                    if "," in quantifier:
                        min_c, max_c = quantifier.split(",")
                        min_c = int(min_c) if min_c else 0
                        max_c = int(max_c) if max_c else min_c + 5
                    else:
                        min_c = max_c = int(quantifier)

                    count = random.randint(min_c, max_c)
                    i = q_end + 1

                # Generate characters based on character class
                for _ in range(count):
                    # Handle negation [^...]
                    if char_class.startswith("^"):
                        result.append(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))
                    # Handle character classes with ranges (parse them properly)
                    elif "-" in char_class:
                        # Expand all ranges in the character class
                        chars = []
                        j = 0
                        while j < len(char_class):
                            # Check if this is a range (e.g., A-Z or 0-9)
                            if j + 2 < len(char_class) and char_class[j + 1] == "-":
                                start_char = ord(char_class[j])
                                end_char = ord(char_class[j + 2])
                                chars.extend([chr(c) for c in range(start_char, end_char + 1)])
                                j += 3
                            else:
                                # Single character (not part of a range)
                                chars.append(char_class[j])
                                j += 1
                        result.append(random.choice(chars))
                    # Handle explicit character list [ABC123]
                    else:
                        result.append(random.choice(char_class))

            # Handle backslash shortcuts
            elif char == "\\" and i + 1 < len(pattern):
                next_char = pattern[i + 1]
                i += 2

                # Check for quantifier
                count = 1
                if i < len(pattern) and pattern[i] == "{":
                    q_end = pattern.index("}", i)
                    quantifier = pattern[i + 1 : q_end]

                    if "," in quantifier:
                        min_c, max_c = quantifier.split(",")
                        min_c = int(min_c) if min_c else 0
                        max_c = int(max_c) if max_c else min_c + 5
                    else:
                        min_c = max_c = int(quantifier)

                    count = random.randint(min_c, max_c)
                    i = q_end + 1

                # Generate based on shortcut type
                for _ in range(count):
                    if next_char == "d":  # Digit
                        result.append(str(random.randint(0, 9)))
                    elif next_char == "w":  # Word character
                        result.append(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"))
                    elif next_char == "D":  # Non-digit
                        result.append(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
                    elif next_char == "s":  # Whitespace
                        result.append(" ")
                    else:
                        result.append(next_char)

            # Handle dot (any character)
            elif char == ".":
                result.append(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"))
                i += 1

            # Handle quantifiers *, +, ? (for previous character)
            elif char in "*+?" and result:
                if char == "*":
                    count = random.randint(0, 5)
                elif char == "+":
                    count = random.randint(1, 5)
                else:  # ?
                    count = random.randint(0, 1)

                last_char = result[-1]
                result.extend([last_char] * (count - 1))
                i += 1

            # Regular literal character
            else:
                result.append(char)
                i += 1

        return "".join(result)

    def create_ids(self, fake, registrant):
        """
        Create IDs for registrants with dynamic ID number generation based on regex.
        """
        if random.uniform(0, 100) > self.percentage_with_ids:
            return

        id_type_id, id_validation = self.get_id_type("group" if registrant.is_group else "individual")

        if id_type_id:
            # Get the id_validation regex from id_type
            id_validation_regex = None
            if id_validation:
                id_validation_regex = id_validation
            _logger.info(f"ID Validation Regex: {id_validation_regex}")
            # Generate ID number based on regex or fallback to default
            if id_validation_regex:
                try:
                    # Use cached compiled regex for performance
                    if id_validation_regex not in self._regex_cache:
                        self._regex_cache[id_validation_regex] = re.compile(id_validation_regex)
                    compiled_regex = self._regex_cache[id_validation_regex]

                    max_attempts = 10  # Prevent infinite loops
                    attempt = 0
                    id_number = None
                    last_generated = None

                    while attempt < max_attempts:
                        last_generated = self.generate_id_from_regex(id_validation_regex)

                        # Validate generated ID against the compiled regex
                        if compiled_regex.match(last_generated):
                            id_number = last_generated
                            break
                        attempt += 1

                    if id_number is None:
                        # If we exhausted attempts, log to database and skip creation
                        self._log_generation_failure(
                            registrant=registrant,
                            operation_type="id_generation",
                            failure_reason="max_attempts_reached",
                            error_message=(
                                f"Failed to generate valid ID after "
                                f"{max_attempts} attempts for regex: "
                                f"{id_validation_regex}"
                            ),
                            attempts=max_attempts,
                            validation_regex=id_validation_regex,
                            generated_value=last_generated,
                        )
                        _logger.warning(
                            f"Failed to generate valid ID after {max_attempts} attempts "
                            f"for regex: {id_validation_regex}. No record created."
                        )
                        return
                except Exception as e:
                    # Log exception to database and skip creation
                    self._log_generation_failure(
                        registrant=registrant,
                        operation_type="id_generation",
                        failure_reason="generation_error",
                        error_message=f"Error generating ID from regex {id_validation_regex}",
                        attempts=attempt if "attempt" in locals() else 0,
                        validation_regex=id_validation_regex,
                        generated_value=last_generated if "last_generated" in locals() else None,
                        exception_details=str(e),
                    )
                    _logger.error(f"Error generating ID from regex {id_validation_regex}: {e}. No record created.")
                    return
            else:
                # No regex provided, use default generation
                id_number = fake.bothify(text="??######")

            issue_date = self.get_random_date(
                fake,
                datefrom=registrant.registration_date,
                dateto=fields.Date.today(),
            )
            id_expiry_date = issue_date + datetime.timedelta(days=365)

            id_vals = {
                "partner_id": registrant.id,
                "id_type_id": id_type_id,
                "value": id_number,
                "expiry_date": id_expiry_date,
            }
            self.env["spp.registry.id"].create(id_vals)

    def get_bank_type(self, target_type):
        if self.bank_type_ids:
            bank_type = self.env["spp.demo.data.bank.types"].search(
                [("target_type", "=", target_type), ("demo_data_generator_id", "=", self.id)]
            )
            if bank_type:
                if len(self.bank_type_ids) == 1:
                    return bank_type.bank_id.id
                # Collect all bank_id values from the recordset
                bank_records = bank_type.mapped("bank_id")
                return random.choice(bank_records).id
            return None

        bank_type_id = self.env["res.bank"].search([])
        if bank_type_id:
            return random.choice(bank_type_id).id if len(bank_type_id) > 1 else bank_type_id.id

        return None

    def create_bank_accounts(self, fake, registrant):
        if random.uniform(0, 100) > self.percentage_with_bank_account:
            return
        bank_type_id = self.get_bank_type("group" if registrant.is_group else "individual")
        if bank_type_id:
            account_number = fake.bothify(text="??######")
            bank_account_vals = {
                "partner_id": registrant.id,
                "bank_id": bank_type_id,
                "acc_number": account_number,
            }
            self.env["res.partner.bank"].create(bank_account_vals)

    def generate_phone_number(self, fake):
        max_attempts = 10  # Prevent infinite loops
        attempt = 0

        while attempt < max_attempts:
            try:
                phone_number = fake.phone_number()
            except Exception:
                try:
                    phone_number = fake.mobile_number()
                except Exception:
                    phone_number = f"+{random.randint(1000000000, 9999999999)}"

            # Preserve the leading '+' if present, then remove all non-digit characters
            has_plus = phone_number.startswith("+")
            cleaned = re.sub(r"\D", "", phone_number)

            # Add back the '+' prefix if it was originally there
            if has_plus:
                cleaned = f"+{cleaned}"

            # Ensure we have a valid length (at least 10 digits for most phone numbers)
            # Check digit count (excluding the + sign)
            digit_count = len(cleaned.lstrip("+"))
            if cleaned and digit_count >= 10:
                return cleaned
            attempt += 1

        # Return None if we couldn't generate a valid phone number
        _logger.warning("Failed to generate valid phone number after %s attempts. Returning None.", max_attempts)
        return None

    def create_phone_numbers(self, fake, registrant):
        num_phone_numbers = random.randint(1, 5)
        phone_vals_list = []
        failed_count = 0

        for _ in range(num_phone_numbers):
            phone_number = self.generate_phone_number(fake)

            if phone_number is None:
                # Log failure to database
                failed_count += 1
                self._log_generation_failure(
                    registrant=registrant,
                    operation_type="phone_generation",
                    failure_reason="max_attempts_reached",
                    error_message="Failed to generate valid phone number after 10 attempts",
                    attempts=10,
                )
                continue

            date_collected = self.get_random_date(
                fake,
                datefrom=registrant.registration_date,
                dateto=fields.Date.today(),
            )
            phone_vals_list.append(
                {
                    "partner_id": registrant.id,
                    "phone_no": phone_number,
                    "date_collected": date_collected,
                }
            )

        # Batch create all phone numbers for this registrant
        if phone_vals_list:
            self.env["spp.phone.number"].create(phone_vals_list)

        if failed_count > 0:
            _logger.warning("Failed to generate %d phone number(s) for registrant_id=%s", failed_count, registrant.id)

        registrant.phone_number_ids_change()

    def create_gps_coordinates(self, fake, registrant):
        if random.uniform(0, 100) > self.percentage_with_gps:
            return

        lat_min, lat_max = self.locale_origin.lat_min, self.locale_origin.lat_max
        lon_min, lon_max = self.locale_origin.lon_min, self.locale_origin.lon_max

        if None not in (lat_min, lat_max, lon_min, lon_max):
            latitude = round(random.uniform(lat_min, lat_max), 6)
            longitude = round(random.uniform(lon_min, lon_max), 6)
            registrant.gps_coordinates = f"{latitude}, {longitude}"

    def refresh_page(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }

    def cleanup_demo_data(self):
        """Delete all demo-generated data including memberships."""
        self.ensure_one()

        # Find all demo-generated groups and individuals
        groups = self.env["res.partner"].search([("demo_data_group_generator_id", "=", self.id)])
        individuals = self.env["res.partner"].search([("demo_data_individual_generator_id", "=", self.id)])

        # Delete group memberships first (to avoid foreign key constraint errors)
        if groups or individuals:
            membership_ids = []
            if groups:
                memberships = self.env["spp.group.membership"].search([("group", "in", groups.ids)])
                membership_ids.extend(memberships.ids)
            if individuals:
                memberships = self.env["spp.group.membership"].search([("individual", "in", individuals.ids)])
                membership_ids.extend(memberships.ids)

            # Delete unique memberships
            if membership_ids:
                unique_memberships = self.env["spp.group.membership"].browse(list(set(membership_ids)))
                unique_memberships.unlink()
                _logger.info("Deleted %d group memberships", len(unique_memberships))

        # Delete groups (which will cascade delete related data)
        group_count = len(groups) if groups else 0
        if groups:
            groups.unlink()
            _logger.info("Deleted %d demo groups", group_count)

        # Delete individuals
        individual_count = len(individuals) if individuals else 0
        if individuals:
            individuals.unlink()
            _logger.info("Deleted %d demo individuals", individual_count)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Cleanup Complete",
                "message": f"Deleted {group_count} groups and {individual_count} individuals",
                "sticky": False,
                "type": "success",
            },
        }

    def _compute_use_job_queue(self):
        for rec in self:
            rec.use_job_queue = rec.number_of_groups >= rec.queue_job_minimum_size

    # =========================================================================
    # Fixed Demo Stories Generation
    # =========================================================================

    def generate_stories(self):
        """
        Generate fixed demo stories with predictable names and profiles.

        Creates registrants from the predefined demo stories for sales demos
        and training. Each story has a memorable name (e.g., "Maria Santos")
        that can be easily searched during demos.

        Returns:
            dict: Dictionary mapping story IDs to created partner records
        """
        self.ensure_one()
        from . import demo_stories

        _logger.info("Starting fixed demo story generation...")

        created_partners = {}
        stories = demo_stories.get_all_stories()

        for story in stories:
            try:
                # Check if story already exists
                existing = self.env["res.partner"].search(
                    [("name", "=", story["name"]), ("is_registrant", "=", True)],
                    limit=1,
                )
                if existing:
                    _logger.info("Story '%s' already exists, skipping...", story["id"])
                    self._backfill_story_identity(existing, story)
                    created_partners[story["id"]] = existing
                    continue

                # Create the registrant based on story type
                story_type = story.get("type", "individual")

                if story_type == "household":
                    partner = self._create_household_story(story)
                elif story_type == "farmer":
                    partner = self._create_farmer_story(story)
                else:
                    partner = self._create_individual_story(story)

                if partner:
                    created_partners[story["id"]] = partner
                    _logger.info("Created demo story: %s (partner_id=%s)", story["id"], partner.id)

            except Exception as e:
                _logger.error("Error creating story '%s': %s", story.get("id", "unknown"), e, exc_info=True)

        _logger.info(f"Demo story generation completed. Created {len(created_partners)} stories.")
        return created_partners

    def _story_birthdate(self, data, fallback_age=35, month=1, day=15):
        if data.get("birthdate"):
            return fields.Date.to_date(data["birthdate"])
        age = data.get("age", fallback_age)
        birth_year = fields.Date.today().year - age
        return fields.Date.today().replace(year=birth_year, month=month, day=day)

    def _story_member_definitions(self, profile):
        members = []
        if profile.get("head"):
            members.append(profile["head"])
        if profile.get("spouse"):
            members.append(profile["spouse"])
        members.extend(profile.get("adults", []))
        members.extend(profile.get("children", []))
        return members

    def _normalized_story_name(self, value):
        return re.sub(r"[^a-z0-9]", "", (value or "").lower())

    def _story_member_definition_for_partner(self, partner, member_defs):
        partner_names = {
            self._normalized_story_name(partner.name),
            self._normalized_story_name(f"{partner.given_name or ''} {partner.family_name or ''}"),
            self._normalized_story_name(f"{partner.family_name or ''} {partner.given_name or ''}"),
        }
        for member_def in member_defs:
            if self._normalized_story_name(member_def.get("name")) in partner_names:
                return member_def
        return {}

    def _story_id_type(self, identifier):
        code = identifier.get("type") or identifier.get("code")
        uri = identifier.get("uri")
        Code = self.env["spp.vocabulary.code"].sudo()
        if uri:
            return Code.search([("uri", "=", uri)], limit=1)
        if not code:
            return Code.browse()
        return Code.get_code("urn:openspp:vocab:id-type", code)

    def _find_story_partner_by_ids(self, data, is_group=False):
        RegistryId = self.env["spp.registry.id"].sudo()
        for identifier in data.get("ids", []):
            value = identifier.get("value")
            id_type = self._story_id_type(identifier)
            if not value or not id_type:
                continue
            reg_id = RegistryId.search(
                [
                    ("id_type_id", "=", id_type.id),
                    ("value", "=", value),
                    ("partner_id.is_registrant", "=", True),
                    ("partner_id.is_group", "=", is_group),
                ],
                limit=1,
            )
            if reg_id:
                return reg_id.partner_id
        return self.env["res.partner"].browse()

    def _write_missing_story_values(self, partner, values):
        missing_vals = {
            field_name: value
            for field_name, value in values.items()
            if field_name in partner._fields
            and value
            and field_name not in ("name", "is_registrant", "is_group")
            and not partner[field_name]
        }
        if missing_vals:
            partner.with_context(skip_name_format=True).write(missing_vals)

    def _materialize_story_ids(self, partner, data):
        RegistryId = self.env["spp.registry.id"].sudo()
        for identifier in data.get("ids", []):
            value = identifier.get("value")
            id_type = self._story_id_type(identifier)
            if not value or not id_type:
                continue
            existing = RegistryId.search(
                [("partner_id", "=", partner.id), ("id_type_id", "=", id_type.id)],
                limit=1,
            )
            if existing:
                if existing.value != value:
                    existing.write({"value": value})
                continue
            if RegistryId.search(
                [
                    ("partner_id", "!=", partner.id),
                    ("id_type_id", "=", id_type.id),
                    ("value", "=", value),
                ],
                limit=1,
            ):
                continue
            RegistryId.create(
                {
                    "partner_id": partner.id,
                    "id_type_id": id_type.id,
                    "value": value,
                }
            )

    def _apply_story_identity(self, partner, data):
        if not partner or not data:
            return
        vals = {}
        if data.get("birthdate") and "birthdate" in partner._fields:
            vals["birthdate"] = fields.Date.to_date(data["birthdate"])
        if vals:
            partner.write(vals)
        self._materialize_story_ids(partner, data)

    def _backfill_story_identity(self, registrant, story):
        profile = story.get("profile", {})
        self._apply_story_identity(registrant, profile)
        if not registrant.is_group:
            return
        member_defs = self._story_member_definitions(profile)
        memberships = self.env["spp.group.membership"].search([("group", "=", registrant.id)])
        for membership in memberships:
            member_def = self._story_member_definition_for_partner(membership.individual, member_defs)
            self._apply_story_identity(membership.individual, member_def)

    def _create_individual_story(self, story):
        """Create an individual registrant from a story definition."""
        profile = story.get("profile", {})

        # Create Faker instance once for reuse
        faker_code = self.locale_origin.faker_locale or "en_US"
        fake = Faker(faker_code)

        # Calculate dates
        registration_date = fields.Date.today() - datetime.timedelta(
            days=story.get("journey", [{}])[0].get("days_back", 100)
        )

        birthdate = self._story_birthdate(profile, fallback_age=35, month=1, day=15)

        # Get gender ID
        gender = profile.get("gender", "male")
        gender_id = self.get_gender_id(gender.capitalize())

        # Parse name into parts
        name_parts = story["name"].split(" ", 1)
        given_name = name_parts[0]
        family_name = name_parts[1] if len(name_parts) > 1 else ""

        # Preserve story display name (human-friendly order)
        computed_name = story["name"]

        vals = {
            "demo_data_individual_generator_id": self.id,
            "name": computed_name,
            "given_name": given_name,
            "family_name": family_name,
            "is_registrant": True,
            "is_group": False,
            "gender_id": gender_id,
            "birthdate": birthdate,
            "registration_date": registration_date,
            "create_date": registration_date,
            "address": profile.get("district", "Demo District"),
        }

        partner_fields = self.env["res.partner"]._fields

        # Email field
        if "email" in partner_fields and profile.get("email"):
            vals["email"] = profile["email"]
        elif "email" in partner_fields:
            vals["email"] = fake.email()

        # Area field (if spp_area is installed)
        if "area_id" in partner_fields:
            area_id = self._get_area_for_profile(profile)
            if area_id:
                vals["area_id"] = area_id

        # Birth place
        if "birth_place" in partner_fields and profile.get("birth_place"):
            vals["birth_place"] = profile["birth_place"]
        elif "birth_place" in partner_fields:
            vals["birth_place"] = fake.city()

        # Additional name
        if "addl_name" in partner_fields and profile.get("addl_name"):
            vals["addl_name"] = profile["addl_name"]
            # Recompute name with addl_name
            name_vals = [
                f"{family_name}," if family_name and given_name else f"{family_name}" if family_name else "",
                given_name,
                vals["addl_name"],
            ]
            vals["name"] = " ".join(filter(None, name_vals)).upper()

        # Add education if field exists
        education_map = {
            "none": "none",
            "primary": "primary",
            "secondary": "secondary",
            "tertiary": "tertiary",
            "university": "university",
        }
        if profile.get("education") and "highest_education_level" in partner_fields:
            vals["highest_education_level"] = education_map.get(profile["education"], "primary")

        # Add marital status if field exists
        if profile.get("marital_status") and "marital_status" in partner_fields:
            vals["marital_status"] = profile["marital_status"]
        elif "civil_status" in partner_fields:
            # Use civil_status as fallback if marital_status doesn't exist
            civil_statuses = ["single", "married", "divorced", "widowed"]
            vals["civil_status"] = random.choice(civil_statuses)

        # Occupation
        if "occupation" in partner_fields and profile.get("occupation"):
            vals["occupation"] = profile["occupation"]
        elif "occupation" in partner_fields:
            vals["occupation"] = fake.job()

        # Income
        if "income" in partner_fields and profile.get("income") is not None:
            vals["income"] = profile["income"]
        elif "income" in partner_fields:
            vals["income"] = round(random.uniform(0, 100000), 2)

        existing_by_id = self._find_story_partner_by_ids(profile, is_group=False)
        if existing_by_id:
            self._write_missing_story_values(existing_by_id, vals)
            self._apply_story_identity(existing_by_id, profile)
            return existing_by_id

        partner = self.env["res.partner"].create(vals)
        partner.with_context(skip_name_format=True).write({"name": computed_name})

        # Create IDs and phone numbers using Faker

        self.create_ids(fake, partner)
        self._apply_story_identity(partner, profile)
        self.create_phone_numbers(fake, partner)
        self.create_bank_accounts(fake, partner)

        return partner

    def _create_farmer_story(self, story):
        """Create a farmer group registrant from a story definition."""
        profile = story.get("profile", {})

        # Calculate dates
        journey = story.get("journey", [{}])
        first_action = journey[0] if journey else {}
        registration_date = fields.Date.today() - datetime.timedelta(days=first_action.get("days_back", 100))

        birthdate = self._story_birthdate(profile, fallback_age=40, month=6, day=15)

        # Get gender ID
        gender = profile.get("gender", "male")
        gender_id = self.get_gender_id(gender.capitalize())

        # Parse name into parts
        name_parts = story["name"].split(" ", 1)
        given_name = name_parts[0]
        family_name = name_parts[1] if len(name_parts) > 1 else ""

        # Build group values
        vals = {
            "demo_data_group_generator_id": self.id,
            "name": story["name"],
            "is_registrant": True,
            "is_group": True,
            "registration_date": registration_date,
            "create_date": registration_date,
            "address": profile.get("district", "Demo District"),
        }

        # Add farmer-specific fields if they exist
        partner_fields = self.env["res.partner"]._fields

        if "household_size" in partner_fields:
            vals["household_size"] = profile.get("household_size", 4)

        if "farmer_family_name" in partner_fields:
            vals["farmer_family_name"] = family_name

        if "farmer_given_name" in partner_fields:
            vals["farmer_given_name"] = given_name

        if "farmer_sex" in partner_fields:
            vals["farmer_sex"] = gender_id

        if "farmer_birthdate" in partner_fields:
            vals["farmer_birthdate"] = birthdate

        # Education mapping
        education_map = {
            "none": "none",
            "primary": "primary",
            "secondary": "secondary",
            "tertiary": "tertiary",
            "university": "university",
        }
        if profile.get("education"):
            if "highest_education_level" in partner_fields:
                vals["highest_education_level"] = education_map.get(profile["education"], "primary")
            if "farmer_highest_education_level" in partner_fields:
                vals["farmer_highest_education_level"] = education_map.get(profile["education"], "primary")

        # Marital status
        if profile.get("marital_status"):
            if "marital_status" in partner_fields:
                vals["marital_status"] = profile["marital_status"]
            if "farmer_marital_status" in partner_fields:
                vals["farmer_marital_status"] = profile["marital_status"]

        # Get group type
        group_types = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-type")]
        )
        if group_types:
            vals["group_type_id"] = group_types[0].id

        partner = self.env["res.partner"].create(vals)

        # Create IDs and phone numbers using Faker
        faker_code = self.locale_origin.faker_locale or "en_US"
        fake = Faker(faker_code)

        self.create_ids(fake, partner)
        self._apply_story_identity(partner, profile)
        self.create_phone_numbers(fake, partner)
        self.create_bank_accounts(fake, partner)
        self.create_gps_coordinates(fake, partner)

        # Create farm details if available
        if profile.get("farm_size") and "spp.farm.details" in self.env:
            self._create_story_farm_details(partner, profile, fake)

        return partner

    def _create_household_story(self, story):
        """Create a household group with members from a story definition."""
        profile = story.get("profile", {})
        head_info = profile.get("head", {})

        # Calculate dates
        journey = story.get("journey", [{}])
        first_action = journey[0] if journey else {}
        registration_date = fields.Date.today() - datetime.timedelta(days=first_action.get("days_back", 100))

        # Build group values
        vals = {
            "demo_data_group_generator_id": self.id,
            "name": story["name"],
            "is_registrant": True,
            "is_group": True,
            "registration_date": registration_date,
            "create_date": registration_date,
            "address": profile.get("district", "Demo District"),
        }

        # Get group type
        group_types = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-type")]
        )
        if group_types:
            vals["group_type_id"] = group_types[0].id

        # Calculate household size
        household_size = 1  # head
        if profile.get("spouse"):
            household_size += 1
        household_size += len(profile.get("adults", []))
        household_size += len(profile.get("children", []))

        if "household_size" in self.env["res.partner"]._fields:
            vals["household_size"] = household_size

        # Add head information if fields exist
        partner_fields = self.env["res.partner"]._fields
        if head_info:
            name_parts = head_info.get("name", "").split(" ", 1)
            if "farmer_given_name" in partner_fields:
                vals["farmer_given_name"] = name_parts[0] if name_parts else ""
            if "farmer_family_name" in partner_fields:
                vals["farmer_family_name"] = name_parts[1] if len(name_parts) > 1 else ""
            if "farmer_sex" in partner_fields:
                gender = head_info.get("gender", "male")
                vals["farmer_sex"] = self.get_gender_id(gender.capitalize())
            if "farmer_birthdate" in partner_fields:
                vals["farmer_birthdate"] = self._story_birthdate(head_info, fallback_age=45, month=3, day=15)

        group = self.env["res.partner"].create(vals)

        # Create IDs and phone numbers using Faker
        faker_code = self.locale_origin.faker_locale or "en_US"
        fake = Faker(faker_code)

        self.create_ids(fake, group)
        self._apply_story_identity(group, profile)
        self.create_phone_numbers(fake, group)
        self.create_bank_accounts(fake, group)

        # Create household members
        self._create_household_members_from_story(group, profile, registration_date, fake)

        return group

    def _create_household_members_from_story(self, group, profile, registration_date, fake):
        """Create household members from story profile."""
        # Create spouse if defined
        spouse_info = profile.get("spouse", {})
        if spouse_info:
            spouse = self._create_member_from_info(spouse_info, registration_date, fake)
            if spouse:
                membership_vals = {
                    "group": group.id,
                    "individual": spouse.id,
                    "start_date": registration_date,
                }
                self.env["spp.group.membership"].create(membership_vals)

        for adult_info in profile.get("adults", []):
            adult = self._create_member_from_info(adult_info, registration_date, fake)
            if adult:
                membership_vals = {
                    "group": group.id,
                    "individual": adult.id,
                    "start_date": registration_date,
                }
                self.env["spp.group.membership"].create(membership_vals)

        # Create children if defined
        children = profile.get("children", [])
        for child_info in children:
            child = self._create_member_from_info(child_info, registration_date, fake)
            if child:
                membership_vals = {
                    "group": group.id,
                    "individual": child.id,
                    "start_date": registration_date,
                }
                self.env["spp.group.membership"].create(membership_vals)

    def _create_member_from_info(self, member_info, registration_date, fake):
        """Create an individual member from member info dict."""
        name = member_info.get("name", fake.name())
        gender = member_info.get("gender", "male")
        age = member_info.get("age", 30)

        birthdate = self._story_birthdate(member_info, fallback_age=age, month=7, day=1)

        name_parts = name.split(" ", 1)
        given_name = name_parts[0]
        family_name = name_parts[1] if len(name_parts) > 1 else ""

        # Compute name in the same format as the name_change onchange method
        # Format: "FAMILY_NAME, GIVEN_NAME ADDITIONAL_NAME" (uppercase)
        name_vals = [
            f"{family_name}," if family_name and given_name else f"{family_name}" if family_name else "",
            given_name,
            "",  # addl_name - empty for now
        ]
        computed_name = " ".join(filter(None, name_vals)).upper()

        vals = {
            "demo_data_individual_generator_id": self.id,
            "name": computed_name,
            "given_name": given_name,
            "family_name": family_name,
            "is_registrant": True,
            "is_group": False,
            "gender_id": self.get_gender_id(gender.capitalize()),
            "birthdate": birthdate,
            "registration_date": registration_date,
            "create_date": registration_date,
        }

        # Add optional fields if they exist in the model
        partner_fields = self.env["res.partner"]._fields

        # Email field
        if "email" in partner_fields:
            vals["email"] = fake.email()

        # Birth place
        if "birth_place" in partner_fields:
            vals["birth_place"] = fake.city()

        # Additional name (middle name) - randomly add for some individuals
        if "addl_name" in partner_fields and random.choice([True, False]):
            vals["addl_name"] = fake.first_name()
            # Recompute name with addl_name
            name_vals = [
                f"{family_name}," if family_name and given_name else f"{family_name}" if family_name else "",
                given_name,
                vals["addl_name"],
            ]
            vals["name"] = " ".join(filter(None, name_vals)).upper()

        # Civil status
        if "civil_status" in partner_fields:
            civil_statuses = ["single", "married", "divorced", "widowed"]
            vals["civil_status"] = random.choice(civil_statuses)

        # Occupation
        if "occupation" in partner_fields:
            vals["occupation"] = fake.job()

        # Income (random value between 0 and 100000)
        if "income" in partner_fields:
            vals["income"] = round(random.uniform(0, 100000), 2)

        existing_by_id = self._find_story_partner_by_ids(member_info, is_group=False)
        if existing_by_id:
            self._write_missing_story_values(existing_by_id, vals)
            self._apply_story_identity(existing_by_id, member_info)
            return existing_by_id

        individual = self.env["res.partner"].create(vals)
        self.create_ids(fake, individual)
        self._apply_story_identity(individual, member_info)

        return individual

    def _create_story_farm_details(self, partner, profile, fake):
        """Create farm details for a farmer story."""
        try:
            farm_type = profile.get("farm_type", "crop")
            farm_size = profile.get("farm_size", 2.0)

            # Map farm type
            farm_type_map = {
                "crop": "crop",
                "livestock": "livestock",
                "mixed": "mixed",
                "aquaculture": "aquaculture",
            }

            farm_vals = {
                "details_farm_id": partner.id,
                "details_farm_type": farm_type_map.get(farm_type, "crop"),
                "farm_total_size": farm_size,
                "farm_size_under_crops": round(farm_size * 0.7, 2) if farm_type in ["crop", "mixed"] else 0,
                "details_legal_status": "self",
            }

            self.env["spp.farm.details"].create(farm_vals)
            _logger.debug("Created farm details for partner_id=%s", partner.id)

        except Exception as e:
            _logger.warning("Could not create farm details for partner_id=%s: %s", partner.id, e)


class SPPDemoDataIDTypes(models.Model):
    _name = "spp.demo.data.id.types"
    _description = "SPP Demo Data ID Types"
    _rec_name = "id_type_id"

    id_type_id = fields.Many2one("spp.id.type", string="ID Type", required=True)
    target_type = fields.Selection(
        [("individual", "Individual"), ("group", "Group")],
        string="Target Type",
        required=True,
    )
    demo_data_generator_id = fields.Many2one(
        "spp.demo.data.generator", string="Demo Data Generator", ondelete="cascade"
    )


class SPPDemoDataBankTypes(models.Model):
    _name = "spp.demo.data.bank.types"
    _description = "SPP Demo Data Bank Types"
    _rec_name = "bank_id"

    bank_id = fields.Many2one("res.bank", string="Bank Type", required=True)
    target_type = fields.Selection(
        [("individual", "Individual"), ("group", "Group")],
        string="Target Type",
        default="individual",
        required=True,
    )
    demo_data_generator_id = fields.Many2one(
        "spp.demo.data.generator", string="Demo Data Generator", ondelete="cascade"
    )
