# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
MIS Demo Generator V2

Generates demo data for SP-MIS programs following the V2 architecture:
1. Fixed Demo Programs - Predictable programs aligned with demo stories
2. Story-based Enrollments - Enrolls demo personas with payment history
3. Deterministic Volume Data - Blueprint-based households for realistic dashboards
"""

import datetime
import logging
import random
import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config

from . import demo_programs

_logger = logging.getLogger(__name__)


class SPPMISDemoGenerator(models.TransientModel):
    _name = "spp.mis.demo.generator"
    _description = "MIS Demo Data Generator V2"

    name = fields.Char(string="Name", default="MIS Demo Data V2", required=True)

    # Demo mode selection (simplified UI always uses "complete")
    demo_mode = fields.Selection(
        [
            ("sales", "Sales Demo"),
            ("training", "Partner Training"),
            ("testing", "Developer Testing"),
            ("complete", "Complete Demo"),
        ],
        string="Demo Mode",
        default="complete",
        required=True,
        help="Preset configuration for different use cases:\n"
        "- Sales: Fixed stories + minimal programs (fast)\n"
        "- Training: Full programs + Logic Packs (comprehensive)\n"
        "- Testing: Volume data + random generation (scale testing)\n"
        "- Complete: All features enabled",
    )

    # Logic Studio integration
    install_logic_packs = fields.Boolean(
        string="Install Logic Packs",
        default=False,
        help="Install Logic Packs used by demo programs (child_benefit, social_pension, etc.)",
    )
    include_test_personas = fields.Boolean(
        string="Create Test Personas",
        default=False,
        help="Create test personas in Logic Studio for expression testing",
    )

    # Program generation options
    create_demo_programs = fields.Boolean(
        string="Create Demo Programs",
        default=True,
        help="Create the predefined demo programs (Child Grant, Cash Transfer, etc.)",
    )

    # Story enrollment options
    enroll_demo_stories = fields.Boolean(
        string="Enroll Demo Stories",
        default=True,
        help="Enroll demo story personas (Maria Santos, Juan Dela Cruz, etc.) in their programs",
    )

    create_story_payments = fields.Boolean(
        string="Create Story Payments",
        default=True,
        help="Create payment history for demo stories (entitlements and payments)",
    )

    # Volume generation options (uses deterministic blueprints)
    generate_volume = fields.Boolean(
        string="Generate Volume Data",
        default=True,
        help="Generate deterministic households from blueprints (~730 households, ~2500 members)",
    )

    # Cycle and payment options
    create_cycles = fields.Boolean(
        string="Create Cycles",
        default=True,
        help="Create program cycles with entitlements",
    )
    cycles_per_program = fields.Integer(
        string="Cycles per Program",
        default=3,
        help="Number of cycles to create for each program",
    )

    # Event data options
    create_event_data = fields.Boolean(
        string="Create Event Data",
        default=True,
        help="Create event records (training, visits, assessments) for demo stories",
    )

    # Change request options
    create_change_requests = fields.Boolean(
        string="Create Change Requests",
        default=True,
        help="Create change request records at various stages for demo stories",
    )

    # Fairness analysis options
    create_fairness_analysis = fields.Boolean(
        string="Create Fairness Analysis",
        default=True,
        help="Create fairness analysis demo data (requires spp_dashboard_fairness)",
    )

    # Cross-module demo options
    generate_grm_demo = fields.Boolean(
        string="Generate GRM Demo",
        default=True,
        help="Generate GRM tickets for demo stories (requires spp_grm_demo module)",
    )
    grm_volume_tickets = fields.Integer(
        string="GRM Volume Tickets",
        default=30,
        help="Number of additional random GRM tickets to generate",
    )

    generate_case_demo = fields.Boolean(
        string="Generate Case Demo",
        default=True,
        help="Generate cases for demo stories (requires spp_case_demo module)",
    )
    case_volume_count = fields.Integer(
        string="Case Volume Count",
        default=15,
        help="Number of additional random cases to generate",
    )

    # Claim 169 QR Credential options
    generate_claim169_demo = fields.Boolean(
        string="Generate QR Credentials",
        default=True,
        help="Generate Claim 169 signing key, issuer config, and demo credentials",
    )
    generate_credentials_for_stories = fields.Boolean(
        string="Generate Credentials for Stories",
        default=True,
        help="Generate QR credentials for demo story personas (Maria Santos, etc.)",
    )

    # Geographic data options
    load_geographic_data = fields.Boolean(
        string="Load Geographic Data",
        default=True,
        help="Load area data with GIS shapes and assign GPS coordinates to registrants for QGIS plugin demo",
    )
    country_code = fields.Selection(
        [
            ("phl", "Philippines"),
            ("lka", "Sri Lanka"),
            ("tgo", "Togo"),
        ],
        string="Country",
        default="phl",
        required=True,
        help="Determines locale, currency, and geographic data",
    )

    # Locale settings
    locale_origin = fields.Many2one(
        "res.country",
        string="Locale Origin",
        default=lambda self: self.env.user.company_id.country_id or self.env.ref("base.us"),
        help="Country for locale-specific name generation",
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
        """Ensure demo users have correct security groups.

        This is a lightweight action intended for automated E2E setup:
        it assigns module-specific groups to the spp_demo role users and clears
        the menu cache, without generating any demo data records.
        """
        for rec in self:
            rec._ensure_demo_user_groups()
        return True

    @api.constrains("cycles_per_program")
    def _check_positive_integers(self):
        for rec in self:
            if rec.cycles_per_program < 0:
                raise ValidationError(_("Cycles per program must be zero or positive"))

    @api.onchange("demo_mode")
    def _onchange_demo_mode(self):
        """Set default values based on selected demo mode."""
        mode_defaults = {
            "sales": {
                "create_demo_programs": True,
                "enroll_demo_stories": True,
                "create_story_payments": True,
                "generate_volume": True,
                "create_cycles": True,
                "cycles_per_program": 2,
                "create_event_data": True,
                "create_change_requests": True,
                "create_fairness_analysis": True,
                "install_logic_packs": False,
                "include_test_personas": False,
                "generate_grm_demo": True,
                "grm_volume_tickets": 20,
                "generate_case_demo": True,
                "case_volume_count": 10,
                "generate_claim169_demo": True,
                "generate_credentials_for_stories": True,
                "load_geographic_data": True,
                "country_code": "phl",
            },
            "training": {
                "create_demo_programs": True,
                "enroll_demo_stories": True,
                "create_story_payments": True,
                "generate_volume": True,
                "create_cycles": True,
                "cycles_per_program": 3,
                "create_event_data": True,
                "create_change_requests": True,
                "create_fairness_analysis": True,
                "install_logic_packs": True,
                "include_test_personas": True,
                "generate_grm_demo": True,
                "grm_volume_tickets": 50,
                "generate_case_demo": True,
                "case_volume_count": 25,
                "generate_claim169_demo": True,
                "generate_credentials_for_stories": True,
                "load_geographic_data": True,
                "country_code": "phl",
            },
            "testing": {
                "create_demo_programs": True,
                "enroll_demo_stories": True,
                "create_story_payments": True,
                "generate_volume": True,
                "create_cycles": True,
                "cycles_per_program": 3,
                "create_event_data": True,
                "create_change_requests": True,
                "create_fairness_analysis": True,
                "install_logic_packs": False,
                "include_test_personas": True,
                "generate_grm_demo": True,
                "grm_volume_tickets": 500,
                "generate_case_demo": True,
                "case_volume_count": 200,
                "generate_claim169_demo": True,
                "generate_credentials_for_stories": True,
                "load_geographic_data": True,
                "country_code": "phl",
            },
            "complete": {
                "create_demo_programs": True,
                "enroll_demo_stories": True,
                "create_story_payments": True,
                "generate_volume": True,
                "create_cycles": True,
                "cycles_per_program": 3,
                "create_event_data": True,
                "create_change_requests": True,
                "create_fairness_analysis": True,
                "install_logic_packs": True,
                "include_test_personas": True,
                "generate_grm_demo": True,
                "grm_volume_tickets": 100,
                "generate_case_demo": True,
                "case_volume_count": 50,
                "generate_claim169_demo": True,
                "generate_credentials_for_stories": True,
                "load_geographic_data": True,
                "country_code": "phl",
            },
        }
        defaults = mode_defaults.get(self.demo_mode, mode_defaults["sales"])
        for field_name, value in defaults.items():
            setattr(self, field_name, value)

    # Country configuration mapping (keyed by country_code 3-letter ISO)
    COUNTRY_CONFIG = {
        "phl": {"xmlid": "base.ph", "locale": "fil_PH", "currency_xmlid": "base.PHP"},
        "lka": {"xmlid": "base.lk", "locale": "si_LK", "currency_xmlid": "base.LKR"},
        "tgo": {"xmlid": "base.tg", "locale": "fr_TG", "currency_xmlid": "base.XOF"},
    }

    def _get_country_config(self):
        """Get country, locale, and currency based on selected country_code."""
        config = self.COUNTRY_CONFIG.get(self.country_code, self.COUNTRY_CONFIG["phl"])
        country = self.env.ref(config["xmlid"], raise_if_not_found=False)
        currency = self.env.ref(config["currency_xmlid"], raise_if_not_found=False)
        # Ensure currency is active
        if currency and not currency.active:
            currency.active = True
        return {
            "country": country,
            "locale": config["locale"],
            "currency": currency,
        }

    def _install_logic_packs(self):
        """Install Logic Packs used by demo programs.

        Returns:
            list: Installed pack records
        """
        from .demo_programs import get_demo_pack_codes

        Pack = self.env["spp.studio.pack"].sudo()
        installed = []

        for code in get_demo_pack_codes():
            pack = Pack.search([("code", "=", code)], limit=1)
            if pack and pack.state == "available":
                try:
                    # Use the pack's install action
                    pack.action_install()
                    installed.append(pack)
                    _logger.info(f"[spp.mis.demo] Installed Logic Pack: {code}")
                except Exception as e:
                    _logger.warning(f"[spp.mis.demo] Failed to install pack {code}: {e}")
            elif pack and pack.state == "installed":
                _logger.debug(f"[spp.mis.demo] Logic Pack already installed: {code}")
            else:
                _logger.warning(f"[spp.mis.demo] Logic Pack not found: {code}")

        return installed

    def _create_test_personas(self):
        """Create test personas for demo stories in Logic Studio.

        Test personas allow testing CEL expressions against demo story data.
        """
        # Test personas are loaded from demo_personas.xml
        # This method ensures they're created if module data wasn't loaded
        Persona = self.env["spp.studio.test.persona"].sudo()

        # Check if personas already exist
        existing = Persona.search([("name", "ilike", "Maria Santos")], limit=1)
        if existing:
            _logger.debug("[spp.mis.demo] Test personas already exist")
            return

        _logger.info("[spp.mis.demo] Test personas will be created from XML data")

    def _get_gender_id(self, gender_str):
        """Get vocabulary code ID for gender using ISO 5218 codes.

        Delegates to SPPDemoDataGenerator utility method for consistency.

        Args:
            gender_str: Gender string like 'male', 'female', 'Male', 'Female'

        Returns:
            int: ID of the vocabulary code record, or False if not found
        """
        if not gender_str:
            return False
        return self.env["spp.demo.data.generator"].lookup_gender_id(gender_str)

    def action_generate(self):
        """Main entry point for demo data generation."""
        self.ensure_one()

        # Disable notifications during demo data generation
        # This prevents sending emails, SMS, tracking messages, etc.
        self = self.with_context(
            tracking_disable=True,  # Disable chatter tracking
            mail_create_nosubscribe=True,  # Don't auto-subscribe followers
            mail_notrack=True,  # Don't track field changes
            mail_create_nolog=True,  # Don't create chatter log entries
            no_reset_password=True,  # Don't send password reset emails
        )

        self.state = "in_progress"

        # Track statistics
        stats = {
            "stories_created": 0,
            "random_groups_created": 0,
            "random_individuals_created": 0,
            "programs_created": 0,
            "programs_skipped": 0,
            "enrollments_created": 0,
            "enrollments_skipped": 0,
            "payments_created": 0,
            "cycles_created": 0,
            "events_created": 0,
            "change_requests_created": 0,
            "missing_registrants": [],
        }

        try:
            demo_locale, created_data = self._run_generation_steps(stats)

            self.state = "completed"

            # Mark company as having loaded MIS demo data
            self.env.company.mis_demo_loaded = True

            # Return success notification with detailed summary
            return self._show_success_notification(stats)

        except Exception as e:
            _logger.error("Error generating MIS demo data: %s", e, exc_info=True)
            self.state = "draft"
            raise UserError(_("Error generating demo data: %s") % e) from e

    def _run_generation_steps(self, stats):
        """Execute all generation steps. Returns (demo_locale, created_data)."""
        # Resolve country configuration (locale, currency)
        country_cfg = self._get_country_config()
        demo_locale = country_cfg["locale"]
        # Store locale in context for use by story methods (locale-aware names)
        self = self.with_context(demo_locale=demo_locale)

        # Set company country and currency
        if country_cfg["country"]:
            self.env.company.write({"country_id": country_cfg["country"].id})
        if country_cfg["currency"]:
            self.env.company.write({"currency_id": country_cfg["currency"].id})

        _logger.info(
            "Country: %s, Locale: %s, Currency: %s",
            self.country_code,
            demo_locale,
            country_cfg["currency"].name if country_cfg["currency"] else "N/A",
        )

        created_data = {
            "programs": [],
            "enrollments": [],
            "cycles": [],
            "payments": [],
            "events": [],
            "change_requests": [],
        }

        # Step 0: Ensure security groups are assigned FIRST (ALWAYS)
        self._ensure_demo_user_groups()

        # Step 0.25: Install Logic Packs (if enabled)
        if self.install_logic_packs:
            _logger.info("Installing Logic Packs for demo programs...")
            installed_packs = self._install_logic_packs()
            stats["logic_packs_installed"] = len(installed_packs)

        # Step 0.35: Create test personas (if enabled)
        if self.include_test_personas:
            _logger.info("Creating test personas for Logic Studio...")
            self._create_test_personas()
            stats["test_personas_created"] = True

        # Step 0.4: Load geographic data (if enabled)
        if self.load_geographic_data:
            _logger.info("Loading geographic data for %s...", self.country_code)
            geo_result = self._load_geographic_data(stats)
            if geo_result:
                stats["areas_loaded"] = geo_result.get("shapes_loaded", 0)

        # Step 0.5: Ensure demo stories exist (auto-generate if needed)
        stories_created = self._ensure_demo_stories_exist(stats)
        if stories_created:
            _logger.info("Auto-generated %d demo story registrants", stories_created)

        # Step 0.75: Generate deterministic households from blueprints
        volume_households = []
        if self.generate_volume:
            from .household_blueprints import HOUSEHOLD_BLUEPRINTS
            from .seeded_volume_generator import SeededVolumeGenerator

            _logger.info("Generating deterministic households from %d blueprints...", len(HOUSEHOLD_BLUEPRINTS))
            generator = SeededVolumeGenerator(self.env, demo_locale, seed=42)
            volume_households = generator.generate_all_households(HOUSEHOLD_BLUEPRINTS)
            stats["random_groups_created"] = len(volume_households)
            stats["random_individuals_created"] = sum(len(hh["members"]) for hh in volume_households)

        # Step 1: Create demo programs
        if self.create_demo_programs:
            _logger.info("Creating demo programs...")
            programs_result = self._create_demo_programs(stats)
            created_data["programs"] = programs_result

        # Step 2: Enroll demo story personas
        if self.enroll_demo_stories:
            _logger.info("Enrolling demo story personas...")
            story_result = self._enroll_demo_stories(stats)
            created_data["enrollments"] = story_result.get("enrollments", [])
            created_data["payments"] = story_result.get("payments", [])
            created_data["batches"] = story_result.get("batches", [])

        # Step 3: Enroll blueprint households in programs
        if self.generate_volume and volume_households and created_data["programs"]:
            _logger.info("Enrolling blueprint households in programs...")
            program_map = {}
            for prog in created_data["programs"]:
                for prog_def in demo_programs.get_all_demo_programs():
                    if prog_def["name"] == prog.name:
                        program_map[prog_def["id"]] = prog
                        break
            generator.enroll_in_programs(volume_households, program_map)

        # Step 4: Create cycles
        if self.create_cycles:
            _logger.info("Creating program cycles...")
            created_data["cycles"] = self._create_program_cycles(stats)

        # Step 5: Create event data
        if self.create_event_data:
            _logger.info("Creating event data for demo stories...")
            created_data["events"] = self._create_story_events(stats)

        # Step 6: Create change requests
        if self.create_change_requests:
            _logger.info("Creating change requests for demo stories...")
            created_data["change_requests"] = self._create_story_change_requests(stats)

        # Step 7: Create fairness analysis demo data
        if self.create_fairness_analysis:
            _logger.info("Creating fairness analysis demo data...")
            self._create_fairness_analysis_demo(stats)

        # Step 8: Generate GRM demo data (if module installed)
        if self.generate_grm_demo:
            _logger.info("Generating GRM demo data...")
            grm_result = self._generate_grm_demo(stats)
            if grm_result:
                stats["grm_tickets_created"] = grm_result.get("tickets", 0)

        # Step 9: Generate Case demo data (if module installed)
        if self.generate_case_demo:
            _logger.info("Generating Case demo data...")
            case_result = self._generate_case_demo(stats)
            if case_result:
                stats["cases_created"] = case_result.get("cases", 0)

        # Step 10: Generate Claim 169 demo data (signing key, issuer, credentials)
        if self.generate_claim169_demo:
            _logger.info("Generating Claim 169 demo data...")
            self._generate_claim169_demo(stats)

        # Step 11: Assign areas and generate GPS coordinates (if geographic data loaded)
        if self.load_geographic_data:
            _logger.info("Assigning areas to registrants...")
            self._assign_registrant_areas(stats)
            _logger.info("Generating GPS coordinates for registrants...")
            self._generate_coordinates(stats)

        # Step 12: Refresh GIS reports so map data is available immediately
        self._refresh_gis_reports(stats)

        # Step 13: Create PRISM API client with known credentials
        self._create_prism_api_client(stats)

        return demo_locale, created_data

    def _ensure_demo_stories_exist(self, stats):
        """Check if demo story registrants exist and create them if not."""
        try:
            # Import story data from spp_demo
            from odoo.addons.spp_demo.models import demo_stories

            # Check if story registrants exist (locale-aware)
            locale = self.env.context.get("demo_locale")
            stories = demo_stories.get_localized_stories(locale)
            story_names = [s["name"] for s in stories]

            existing = self.env["res.partner"].search(
                [
                    ("name", "in", story_names),
                    ("is_registrant", "=", True),
                ]
            )
            existing_by_name = {r.name: r for r in existing}

            # Find missing stories
            missing_stories = [s for s in stories if s["name"] not in existing_by_name]

            # Also check for existing household groups that are missing members
            # First, collect all household groups that exist
            household_groups = {}
            household_stories_by_name = {}
            for story in stories:
                if story.get("type") == "household" and story["name"] in existing_by_name:
                    group = existing_by_name[story["name"]]
                    if group.is_group:
                        household_groups[group.id] = group
                        household_stories_by_name[group.id] = story

            # Batch query: get membership counts for all household groups in one query
            groups_needing_members = []
            if household_groups:
                group_memberships = self.env["spp.group.membership"]._read_group(
                    domain=[("group", "in", list(household_groups.keys()))],
                    groupby=["group"],
                    aggregates=["__count"],
                )
                groups_with_members = {group.id for group, _count in group_memberships}

                # Find groups that have no members
                for group_id, group in household_groups.items():
                    if group_id not in groups_with_members:
                        groups_needing_members.append((group, household_stories_by_name[group_id]))

            if not missing_stories and not groups_needing_members:
                _logger.info("Demo story registrants already exist")
                return 0

            created_count = 0

            # Create missing story registrants
            if missing_stories:
                _logger.info("Creating %d missing story registrants...", len(missing_stories))
                for story in missing_stories:
                    try:
                        registrant = self._create_story_registrant(story)
                        if registrant:
                            created_count += 1
                    except Exception as e:
                        _logger.warning(
                            "Could not create story registrant (story_id=%s): %s",
                            story.get("id", "unknown"),
                            e,
                        )

            # Create members for existing groups that are missing them
            if groups_needing_members:
                _logger.info("Creating members for %d existing groups...", len(groups_needing_members))
                for group, story in groups_needing_members:
                    try:
                        profile = story.get("profile", {})
                        journey = story.get("journey", [])
                        registration_action = next(
                            (
                                j
                                for j in journey
                                if j.get("action") in ("register", "register_household", "emergency_register")
                            ),
                            {"days_back": 90},
                        )
                        days_back = registration_action.get("days_back", 90)
                        members = self._create_household_members(group, profile, days_back)
                        if members:
                            _logger.info(
                                "Created %d members for group (partner_id=%s, story_id=%s)",
                                len(members),
                                group.id,
                                story.get("id", "unknown"),
                            )
                            # Enrich with demographic data
                            self._enrich_story_household(group, members, profile)
                    except Exception as e:
                        _logger.warning(
                            "Could not create members for group (story_id=%s): %s",
                            story.get("id", "unknown"),
                            e,
                        )

            stats["stories_created"] = created_count

            # Enrich ALL story registrants with demographic data
            # (covers both newly created and pre-existing registrants)
            self._enrich_all_story_registrants(stories)

            return created_count

        except ImportError:
            _logger.warning("Could not import demo_stories from spp_demo")
            return 0
        except Exception as e:
            _logger.error("Error auto-generating demo stories: %s", e)
            return 0

    def _create_story_registrant(self, story):
        """Create a single story registrant from story definition."""
        profile = story.get("profile", {})
        story_type = story.get("type", "individual")

        # Determine if this is a group (household) or individual
        is_group = story_type == "household"

        # Get registration date from journey
        journey = story.get("journey", [])
        registration_action = next(
            (j for j in journey if j.get("action") in ("register", "register_household", "emergency_register")),
            {"days_back": 90},
        )
        days_back = registration_action.get("days_back", 90)
        registration_date = fields.Date.today() - datetime.timedelta(days=days_back)

        # Build partner values
        story_name = story["name"]

        # Parse name into parts for individuals
        if not is_group:
            # Parse name - could be "First Last" or "Last, First" format
            if "," in story_name:
                # Format: "Last, First"
                name_parts = [p.strip() for p in story_name.split(",", 1)]
                family_name = name_parts[0]
                given_name = name_parts[1] if len(name_parts) > 1 else ""
            else:
                # Format: "First Last"
                name_parts = story_name.split(" ", 1)
                given_name = name_parts[0]
                family_name = name_parts[1] if len(name_parts) > 1 else ""
        else:
            family_name = ""
            given_name = ""

        partner_vals = {
            # Keep the human-readable story name so downstream flows (and tests) can find it
            "name": story_name,
            "is_registrant": True,
            "is_group": is_group,
        }

        # Add individual profile data if available
        if not is_group:
            # Set name fields
            if family_name:
                partner_vals["family_name"] = family_name
            if given_name:
                partner_vals["given_name"] = given_name

            # Gender - using vocabulary codes (ISO 5218)
            gender_str = profile.get("gender", "")
            gender_id = self._get_gender_id(gender_str)
            if gender_id:
                partner_vals["gender_id"] = gender_id

            birthdate = self._story_birthdate(profile)
            if birthdate:
                partner_vals["birthdate"] = birthdate

            existing_by_id = self._find_story_partner_by_ids(profile, is_group=False)
            if existing_by_id:
                self._write_missing_story_values(existing_by_id, partner_vals)
                self._apply_story_identity(existing_by_id, profile)
                _logger.info(
                    "Reused story registrant by explicit ID (partner_id=%s, story_id=%s)",
                    existing_by_id.id,
                    story.get("id", "unknown"),
                )
                return existing_by_id

        # Create the registrant
        registrant = self.env["res.partner"].create(partner_vals)
        if not is_group:
            registrant.with_context(skip_name_format=True).write({"name": story_name})

        # Explicitly ensure fields are set after creation for individuals
        if not is_group and (family_name or given_name):
            write_vals = {}
            if family_name:
                write_vals["family_name"] = family_name
            if given_name:
                write_vals["given_name"] = given_name
            if write_vals:
                registrant.with_context(skip_name_format=True).write(write_vals)

        self._apply_story_identity(registrant, profile)

        # Backdate registration
        self.env.cr.execute(
            "UPDATE res_partner SET create_date = %s WHERE id = %s",
            (registration_date, registrant.id),
        )

        _logger.info("Created story registrant (partner_id=%s, story_id=%s)", registrant.id, story.get("id", "unknown"))

        # For households, create family members
        if is_group and "head" in profile:
            self._create_household_members(registrant, profile, days_back)

        return registrant

    def _get_demographic_enricher(self):
        """Build a fresh demographic enricher for the current generation run.

        No caching: an enricher's internal `_bank_ids` / vocab / country
        caches are populated against the current cursor at construction
        time. A class-level cache survives TransactionCase savepoint
        rollbacks between tests, so by the time a later test re-uses the
        cached enricher its `_bank_ids` reference `res.bank` rows that
        no longer exist — the next `res.partner.bank` insert then raises
        a `res_partner_bank_bank_id_fkey` violation. `_ensure_banks` and
        `_cache_vocab_ids` are idempotent (search-then-create), so
        re-instantiating costs only a handful of SELECTs.
        """
        from .demographic_enricher import DemographicEnricher

        locale = self.env.context.get("demo_locale", "fil_PH")
        rng = random.Random(99)  # Separate seed from volume generation
        return DemographicEnricher(self.env, locale, rng)

    def _story_birthdate(self, data):
        if data.get("birthdate"):
            return fields.Date.to_date(data["birthdate"])
        if data.get("age"):
            birth_year = fields.Date.today().year - data["age"]
            return fields.Date.to_date(f"{birth_year}-01-15")
        return False

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
        if data.get("birthdate") and "birthdate" in partner._fields:
            partner.write({"birthdate": fields.Date.to_date(data["birthdate"])})
        self._materialize_story_ids(partner, data)

    def _story_member_definitions(self, profile):
        members = []
        if profile.get("head"):
            members.append(("head", profile["head"]))
        if profile.get("spouse"):
            members.append(("spouse", profile["spouse"]))
        for adult in profile.get("adults", []):
            members.append(("adult", adult))
        for child in profile.get("children", []):
            members.append(("child", child))
        return members

    def _normalized_story_name(self, value):
        return re.sub(r"[^a-z0-9]", "", (value or "").lower())

    def _story_member_definition_for_partner(self, partner, member_defs, fallback_idx=None):
        partner_names = {
            self._normalized_story_name(partner.name),
            self._normalized_story_name(f"{partner.given_name or ''} {partner.family_name or ''}"),
            self._normalized_story_name(f"{partner.family_name or ''} {partner.given_name or ''}"),
        }
        for role, member_def in member_defs:
            if self._normalized_story_name(member_def.get("name")) in partner_names:
                return role, member_def
        if fallback_idx is not None and fallback_idx < len(member_defs):
            return member_defs[fallback_idx]
        return "child", {}

    def _backfill_story_household_identity(self, group, profile):
        self._apply_story_identity(group, profile)
        member_defs = self._story_member_definitions(profile)
        memberships = self.env["spp.group.membership"].search([("group", "=", group.id)])
        for idx, membership in enumerate(memberships):
            _role, member_def = self._story_member_definition_for_partner(
                membership.individual,
                member_defs,
                fallback_idx=idx,
            )
            self._apply_story_identity(membership.individual, member_def)

    def _enrich_all_story_registrants(self, stories):
        """Enrich all story registrants with demographic data if not already set.

        Runs after all story registrants are created/ensured, so it covers
        both newly created and pre-existing registrants.
        """
        try:
            enricher = self._get_demographic_enricher()
        except Exception as e:
            _logger.warning("Could not initialize demographic enricher: %s", e)
            return

        _logger.info("Enriching %d story registrants with demographic data...", len(stories))

        for story in stories:
            story_name = story["name"]
            story_type = story.get("type", "individual")
            profile = story.get("profile", {})

            registrant = self.env["res.partner"].search(
                [("name", "=", story_name), ("is_registrant", "=", True)],
                limit=1,
            )
            if not registrant:
                continue

            if story_type == "household" and registrant.is_group:
                self._backfill_story_household_identity(registrant, profile)
            else:
                self._apply_story_identity(registrant, profile)

            # Skip if already enriched (check for street as proxy)
            if registrant.street:
                continue

            try:
                if story_type == "household" and registrant.is_group:
                    # Enrich the group
                    enricher.enrich_group(registrant)

                    # Enrich individual members
                    memberships = self.env["spp.group.membership"].search([("group", "=", registrant.id)])
                    all_member_defs = self._story_member_definitions(profile)

                    for idx, membership in enumerate(memberships):
                        member = membership.individual
                        role, member_def = self._story_member_definition_for_partner(
                            member,
                            all_member_defs,
                            fallback_idx=idx,
                        )
                        self._apply_story_identity(member, member_def)
                        if member.street:
                            continue  # Already enriched
                        age = member_def.get("age")
                        enricher.enrich_individual(member, age=age, role=role)
                else:
                    # Individual story
                    age = profile.get("age")
                    enricher.enrich_individual(registrant, age=age, role="adult")

            except Exception as e:
                _logger.warning("Could not enrich story registrant %s: %s", story_name, e)

    def _enrich_story_household(self, group, members, profile):
        """Enrich a story household and its members with demographic data."""
        try:
            enricher = self._get_demographic_enricher()
            self._apply_story_identity(group, profile)
            enricher.enrich_group(group)

            # Map members to roles from profile
            all_member_defs = self._story_member_definitions(profile)

            for idx, member in enumerate(members):
                role, member_def = self._story_member_definition_for_partner(member, all_member_defs, fallback_idx=idx)
                self._apply_story_identity(member, member_def)
                age = member_def.get("age")
                enricher.enrich_individual(member, age=age, role=role)
        except Exception as e:
            _logger.warning("Story demographic enrichment failed: %s", e)

    def _create_household_members(self, group, profile, days_back):
        """Create household members for a group registrant."""
        registration_date = fields.Date.today() - datetime.timedelta(days=days_back)
        members_created = []

        VocabCode = self.env["spp.vocabulary.code"]
        type_ids_by_code = {}
        for code in ("head", "spouse", "child", "other"):
            rec = VocabCode.get_code("urn:openspp:vocab:group-membership-type", code)
            type_ids_by_code[code] = rec.id if rec else False

        def _membership_type_commands(code):
            tid = type_ids_by_code.get(code)
            return [Command.link(tid)] if tid else []

        # Create head of household
        head_data = profile.get("head", {})
        if head_data:
            head = self._create_individual_member(head_data, registration_date)
            if head:
                members_created.append(head)
                self.env["spp.group.membership"].create(
                    {
                        "group": group.id,
                        "individual": head.id,
                        "membership_type_ids": _membership_type_commands("head"),
                    }
                )

        # Create spouse if present
        spouse_data = profile.get("spouse", {})
        if spouse_data:
            spouse = self._create_individual_member(spouse_data, registration_date)
            if spouse:
                members_created.append(spouse)
                self.env["spp.group.membership"].create(
                    {
                        "group": group.id,
                        "individual": spouse.id,
                        "membership_type_ids": _membership_type_commands("spouse"),
                    }
                )

        # Create other adults if present (for multi-generational/extended families)
        for adult_data in profile.get("adults", []):
            adult = self._create_individual_member(adult_data, registration_date)
            if adult:
                members_created.append(adult)
                self.env["spp.group.membership"].create(
                    {
                        "group": group.id,
                        "individual": adult.id,
                        "membership_type_ids": _membership_type_commands("other"),
                    }
                )

        # Create children if present
        for child_data in profile.get("children", []):
            child = self._create_individual_member(child_data, registration_date)
            if child:
                members_created.append(child)
                self.env["spp.group.membership"].create(
                    {
                        "group": group.id,
                        "individual": child.id,
                        "membership_type_ids": _membership_type_commands("child"),
                    }
                )

        return members_created

    def _create_individual_member(self, member_data, registration_date):
        """Create an individual member for a household.

        Supports the following fields from member_data:
        - name: Full name (parsed into given_name + family_name)
        - gender: "male" or "female" (mapped to vocabulary code)
        - age: Integer (converted to birthdate)
        - birthdate: ISO date string (wins over age)
        - ids: Explicit registry identifiers to upsert
        - income: Income amount (set as income field)
        - is_head: Boolean (used for membership role, not partner field)
        """
        name = member_data.get("name", "Unknown")

        # Parse name into parts
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

        partner_vals = {
            "name": computed_name,
            "family_name": family_name,
            "given_name": given_name,
            "is_registrant": True,
            "is_group": False,
        }

        # Gender - using vocabulary codes (ISO 5218)
        gender_str = member_data.get("gender", "")
        gender_id = self._get_gender_id(gender_str)
        if gender_id:
            partner_vals["gender_id"] = gender_id

        birthdate = self._story_birthdate(member_data)
        if birthdate:
            partner_vals["birthdate"] = birthdate

        # Income (for economic variables like hh_total_income)
        if member_data.get("income"):
            partner_vals["income"] = float(member_data["income"])

        existing_by_id = self._find_story_partner_by_ids(member_data, is_group=False)
        if existing_by_id:
            self._write_missing_story_values(existing_by_id, partner_vals)
            self._apply_story_identity(existing_by_id, member_data)
            return existing_by_id

        member = self.env["res.partner"].create(partner_vals)

        # Explicitly ensure fields are set after creation
        if not member.is_group and (family_name or given_name):
            write_vals = {}
            if family_name:
                write_vals["family_name"] = family_name
            if given_name:
                write_vals["given_name"] = given_name
            if write_vals:
                member.write(write_vals)

        self._apply_story_identity(member, member_data)

        # Backdate registration
        self.env.cr.execute(
            "UPDATE res_partner SET create_date = %s WHERE id = %s",
            (registration_date, member.id),
        )

        return member

    def _create_demo_programs(self, stats):
        """Create demo programs from definitions."""
        created_programs = []
        program_model = self.env["spp.program"]

        for program_def in demo_programs.get_all_demo_programs():
            # Check if program already exists
            existing = program_model.search([("name", "=", program_def["name"])], limit=1)
            if existing:
                _logger.info("Program already exists (program_id=%s), skipping...", existing.id)
                stats["programs_skipped"] += 1
                # Ensure all default managers are present (cycle, eligibility, entitlement, etc.)
                self._ensure_program_managers(existing)
                created_programs.append(existing)
                continue

            # Create journal for the program
            journal = self._create_program_journal(program_def["name"])

            # Create the program
            program_vals = {
                "name": program_def["name"],
                "description": program_def.get("description", ""),
                "target_type": program_def.get("target_type", "group"),
                "journal_id": journal.id if journal else False,
            }

            try:
                program = program_model.create(program_vals)
                created_programs.append(program)
                stats["programs_created"] += 1
                journal_id = journal.id if journal else None
                _logger.info(
                    "Created program (program_id=%s) with journal (journal_id=%s)",
                    program.id,
                    journal_id,
                )

                # Ensure managers exist on newly created program
                self._ensure_program_managers(program)

                # Configure eligibility: Logic Studio or CEL expression
                if program_def.get("use_logic_studio"):
                    self._configure_logic_studio(program, program_def)
                elif program_def.get("cel_expression"):
                    self._configure_eligibility_manager(program, program_def)

                # Configure entitlement manager (handles both cash and in-kind)
                self._configure_entitlement_manager(program, program_def)

                # Configure cycle manager if duration specified
                if program_def.get("cycle_duration"):
                    self._configure_cycle_manager(program, program_def)

                # Configure compliance manager (CEL expression)
                if program_def.get("compliance_cel_expression"):
                    self._configure_compliance_manager(program, program_def)

                # Configure program-level constant overrides
                if program_def.get("program_constants"):
                    self._configure_program_constants(program, program_def)

            except Exception as e:
                _logger.error("Error creating program (program_id=%s): %s", program_def.get("id", "unknown"), e)

        return created_programs

    def _configure_entitlement_manager(self, program, program_def):
        """Configure the entitlement manager for a program (cash or in-kind).

        For cash entitlements, configures CEL formula for amount calculation.
        """
        try:
            entitlement_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
            if not entitlement_manager:
                return

            entitlement_type = program_def.get("entitlement_type", "cash")

            if entitlement_type == "in_kind":
                # For in-kind programs, set nominal amount for tracking
                entitlement_manager.write(
                    {
                        "amount_per_cycle": 0,
                        "amount_per_individual_in_group": 0,
                    }
                )
                _logger.info("Configured in-kind entitlement for program (program_id=%s)", program.id)
            else:
                # For cash programs - configure CEL formula if available
                amount = program_def.get("entitlement_amount", 100)
                entitlement_formula = program_def.get("entitlement_formula", str(amount))

                # Set base amounts
                entitlement_manager.write(
                    {
                        "amount_per_cycle": amount,
                        "amount_per_individual_in_group": 0,
                    }
                )

                # Configure entitlement item with CEL formula if the module is installed
                if hasattr(entitlement_manager, "entitlement_item_ids"):
                    # Check if items exist, create one if not
                    if not entitlement_manager.entitlement_item_ids:
                        # Create a default entitlement item
                        self.env["spp.program.entitlement.manager.cash.item"].create(
                            {
                                "entitlement_id": entitlement_manager.id,
                                "amount": amount,
                                "currency_id": self.env.company.currency_id.id,
                            }
                        )

                    # Configure CEL formula on entitlement items
                    for item in entitlement_manager.entitlement_item_ids:
                        if "amount_cel_expression" in item._fields:
                            item.write(
                                {
                                    "amount_mode": "cel",
                                    "amount_cel_expression": entitlement_formula,
                                }
                            )
                            _logger.info(
                                "Configured CEL entitlement formula for program (program_id=%s): %s",
                                program.id,
                                entitlement_formula,
                            )

                _logger.info("Configured cash entitlement $%.2f for program (program_id=%s)", amount, program.id)

        except Exception as e:
            _logger.warning("Could not configure entitlement manager for program (program_id=%s): %s", program.id, e)

    def _configure_cycle_manager(self, program, program_def):
        """Configure the cycle manager for a program."""
        try:
            cycle_manager = program.get_manager(program.MANAGER_CYCLE)
            if cycle_manager:
                cycle_manager.write(
                    {
                        "cycle_duration": program_def.get("cycle_duration", 30),
                    }
                )
        except Exception as e:
            _logger.warning("Could not configure cycle manager for program (program_id=%s): %s", program.id, e)

    def _configure_eligibility_manager(self, program, program_def):
        """Configure the eligibility manager with CEL expression.

        Sets the eligibility mode to 'cel' and configures the CEL expression
        for dynamic eligibility evaluation.

        Note: Eligibility uses get_managers() (plural) not get_manager(),
        because the program model routes MANAGER_ELIGIBILITY through get_managers.
        """
        try:
            cel_expression = program_def.get("cel_expression")
            if not cel_expression:
                return

            # Access eligibility managers via the wrapper (same pattern as compliance)
            for wrapper in program.eligibility_manager_ids:
                concrete = wrapper.manager_ref_id
                if not concrete:
                    continue

                if "cel_expression" not in concrete._fields:
                    _logger.info(
                        "CEL expression not supported on eligibility manager for program (program_id=%s)",
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
                "Could not configure eligibility manager for program (program_id=%s): %s",
                program.id,
                e,
            )

    def _configure_compliance_manager(self, program, program_def):
        """Configure the compliance manager with a CEL expression.

        The default compliance manager is already created by _ensure_program_managers().
        This method sets the CEL expression on it.
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
                "Could not configure compliance manager for program (program_id=%s): %s",
                program.id,
                e,
            )

    def _configure_program_constants(self, program, program_def):
        """Configure program-level constant overrides via CEL Program Parameters.

        Creates spp.cel.program.parameter records that override default variable
        values for a specific program (e.g., income_threshold=2000 for Conditional
        Child Grant instead of the global default 5000).
        """
        constants = program_def.get("program_constants", {})
        if not constants:
            return

        CelVariable = self.env["spp.cel.variable"]
        ProgramParam = self.env["spp.cel.program.parameter"]

        for var_name, value in constants.items():
            variable = CelVariable.search([("name", "=", var_name)], limit=1)
            if not variable:
                _logger.warning(
                    "CEL variable '%s' not found, skipping constant override for program (program_id=%s)",
                    var_name,
                    program.id,
                )
                continue

            existing = ProgramParam.search(
                [
                    ("program_id", "=", program.id),
                    ("variable_id", "=", variable.id),
                ],
                limit=1,
            )
            if existing:
                continue

            ProgramParam.create(
                {
                    "program_id": program.id,
                    "variable_id": variable.id,
                    "value": str(value),
                }
            )
            _logger.info(
                "Set program constant %s=%s for program (program_id=%s)",
                var_name,
                value,
                program.id,
            )

    def _configure_logic_studio(self, program, program_def):
        """Configure Logic Studio for program eligibility.

        Creates a reusable logic definition in Logic Studio and configures
        the program to use it instead of inline CEL expressions.
        """
        try:
            # Check if Logic Studio module is installed
            if "spp.cel.expression" not in self.env:
                _logger.info(
                    "Logic Studio not installed, falling back to inline CEL for program (program_id=%s)",
                    program.id,
                )
                # Fall back to inline CEL
                self._configure_eligibility_manager(program, program_def)
                return

            # Check if program supports Logic Studio
            if "use_logic_eligibility" not in program._fields:
                _logger.info(
                    "Program model doesn't support Logic Studio for program (program_id=%s)",
                    program.id,
                )
                self._configure_eligibility_manager(program, program_def)
                return

            logic_name = program_def.get("logic_name", f"{program.name} Eligibility")
            cel_expression = program_def.get("cel_expression", "true")
            context_type = "group" if program_def.get("target_type") == "group" else "individual"
            expression_type = program_def.get("expression_type", "filter")

            # Check if logic already exists
            existing_logic = self.env["spp.cel.expression"].search(
                [
                    ("name", "=", logic_name),
                    ("expression_type", "=", expression_type),
                ],
                limit=1,
            )

            if existing_logic:
                logic = existing_logic
                _logger.info(
                    "Using existing Logic Studio logic (logic_id=%s) for program (program_id=%s)",
                    logic.id,
                    program.id,
                )
            else:
                # Create new logic definition
                logic = self.env["spp.cel.expression"].create(
                    {
                        "name": logic_name,
                        "expression_type": expression_type,
                        "context_type": context_type,
                        "cel_expression": cel_expression,
                        "output_type": "boolean",
                        "state": "published",
                        "is_inline": False,
                    }
                )
                _logger.info(
                    "Created Logic Studio logic (logic_id=%s) for program (program_id=%s): %s",
                    logic.id,
                    program.id,
                    cel_expression,
                )

            # Try to link Logic Studio to program (fields may not exist)
            logic_fields = {"use_logic_eligibility", "logic_mode", "logic_id"}
            if logic_fields.issubset(set(program._fields)):
                program.write(
                    {
                        "use_logic_eligibility": True,
                        "logic_mode": "select",
                        "logic_id": logic.id,
                    }
                )
                _logger.info(
                    "Configured program (program_id=%s) to use Logic Studio eligibility",
                    program.id,
                )

            # Always set CEL on the eligibility manager as well, so the
            # eligibility criteria is visible and functional even if Logic
            # Studio integration fields are not available on the program model.
            self._configure_eligibility_manager(program, program_def)

        except Exception as e:
            _logger.warning(
                "Could not configure Logic Studio for program (program_id=%s): %s. Falling back to CEL.",
                program.id,
                e,
            )
            # Fall back to inline CEL on error
            self._configure_eligibility_manager(program, program_def)

    def _ensure_program_managers(self, program):
        """Create missing default managers (cycle, eligibility, entitlement, etc.) for a program.

        Earlier V2 demo data sometimes missed these because constants.MANAGER_MODELS
        only covered a subset of managers. This is idempotent: if a manager list
        already has entries, we leave it untouched.
        """
        from odoo.addons.spp_programs.models import constants

        for field, mapping in constants.MANAGER_MODELS.items():
            if program[field]:
                continue
            for mgr_obj, def_mgr_obj in mapping.items():
                # Create the concrete manager implementation and link via wrapper
                def_mgr = self.env[def_mgr_obj].create(
                    {
                        "name": "Default",
                        "program_id": program.id,
                    }
                )
                mgr = self.env[mgr_obj].create(
                    {
                        "program_id": program.id,
                        "manager_ref_id": f"{def_mgr_obj},{def_mgr.id}",
                    }
                )
                program.write({field: [Command.link(mgr.id)]})

    def _create_program_journal(self, program_name):
        """Create an accounting journal for a program."""
        from uuid import uuid4

        try:
            # Generate unique code from program name
            words = program_name.split(" ")
            code = "".join([w[0].upper() for w in words if w])[:4]

            # Check if code already exists
            existing = self.env["account.journal"].search([("code", "=", code)])
            if existing:
                code = str(uuid4())[4:12].upper()

            # Find a cash account for the journal
            account_model = self.env["account.account"]
            company_domain = []
            if "company_id" in account_model._fields:
                company_domain = [("company_id", "=", self.env.company.id)]
            elif "company_ids" in account_model._fields:
                company_domain = [("company_ids", "in", self.env.company.id)]

            account_chart = account_model.search(
                company_domain + [("account_type", "=", "asset_cash")],
                limit=1,
            )

            # Get company currency
            currency = self.env.company.currency_id

            # Create journal
            journal = self.env["account.journal"].create(
                {
                    "name": program_name,
                    "is_beneficiary_disb": True,
                    "type": "bank",
                    "default_account_id": account_chart.id if account_chart else False,
                    "code": code,
                    "currency_id": currency.id if currency else False,
                }
            )

            _logger.info("Created journal (journal_id=%s) with code '%s'", journal.id, code)
            return journal

        except Exception as e:
            _logger.error("Could not create journal for program: %s", e)
            return None

    def _enroll_demo_stories(self, stats):
        """Enroll demo story personas in their programs with payment history."""
        result = {
            "enrollments": [],
            "payments": [],
            "batches": [],
        }
        # Track payments by cycle for batch creation
        payments_by_cycle = {}

        # Get demo stories from spp_demo (locale-aware)
        try:
            from odoo.addons.spp_demo.models import demo_stories

            locale = self.env.context.get("demo_locale")
            stories = demo_stories.get_localized_stories(locale)
        except ImportError:
            _logger.warning("Could not import demo_stories from spp_demo")
            return result

        for story in stories:
            story_id = story["id"]
            story_name = story["name"]

            # Find the registrant for this story
            registrant = self.env["res.partner"].search(
                [("name", "=", story_name), ("is_registrant", "=", True)],
                limit=1,
            )

            if not registrant:
                _logger.warning("Registrant not found for story (story_id=%s), skipping enrollment...", story_id)
                stats["missing_registrants"].append(story_name)
                continue

            # Get enrollment details for this story
            story_enrollments = demo_programs.get_story_enrollments(story_id)

            for enrollment_def in story_enrollments:
                program_name = enrollment_def.get("program")
                program = self.env["spp.program"].search([("name", "=", program_name)], limit=1)

                if not program:
                    _logger.warning(
                        "Program not found (program_name=%s) for story (story_id=%s)",
                        program_name,
                        story_id,
                    )
                    continue

                # Determine enrollee: group (default) or individual head member
                enrollee = registrant
                if enrollment_def.get("enroll_individual") and registrant.is_group:
                    # Find the head member of this group (by membership type)
                    head_type = self.env["spp.vocabulary.code"].get_code(
                        "urn:openspp:vocab:group-membership-type", "head"
                    )
                    domain = [("group", "=", registrant.id)]
                    if head_type:
                        domain.append(("membership_type_ids", "in", [head_type.id]))
                    head_membership = self.env["spp.group.membership"].search(
                        domain,
                        limit=1,
                    )
                    if not head_membership:
                        # Fallback: first member if no head type found
                        head_membership = self.env["spp.group.membership"].search(
                            [("group", "=", registrant.id)],
                            limit=1,
                            order="id",
                        )
                    if head_membership:
                        enrollee = head_membership.individual
                        _logger.info(
                            "Individual enrollment: using head member %s (id=%s) from group %s",
                            enrollee.name,
                            enrollee.id,
                            registrant.name,
                        )

                # Check if already enrolled
                existing_membership = self.env["spp.program.membership"].search(
                    [
                        ("partner_id", "=", enrollee.id),
                        ("program_id", "=", program.id),
                    ],
                    limit=1,
                )

                if existing_membership:
                    _logger.info(
                        "Already enrolled (membership_id=%s, story_id=%s, program_id=%s), skipping...",
                        existing_membership.id,
                        story_id,
                        program.id,
                    )
                    stats["enrollments_skipped"] += 1
                    result["enrollments"].append(existing_membership)
                    continue

                # Create enrollment
                enrollment = self._create_story_enrollment(enrollee, program, enrollment_def)
                if enrollment:
                    result["enrollments"].append(enrollment)
                    stats["enrollments_created"] += 1
                    _logger.info(
                        "Enrolled (membership_id=%s, partner_id=%s, program_id=%s, story_id=%s)",
                        enrollment.id,
                        enrollee.id,
                        program.id,
                        story_id,
                    )

                    # Create payment history if enabled and defined (cash programs)
                    if self.create_story_payments and enrollment_def.get("payments"):
                        payments, cycle = self._create_story_payments(
                            enrollee, program, enrollment, enrollment_def, stats
                        )
                        result["payments"].extend(payments)
                        # Track payments by cycle for batch creation
                        if cycle and payments:
                            if cycle.id not in payments_by_cycle:
                                payments_by_cycle[cycle.id] = {"cycle": cycle, "payments": []}
                            payments_by_cycle[cycle.id]["payments"].extend(payments)

                    # Create in-kind entitlements if defined
                    if self.create_story_payments and enrollment_def.get("entitlements"):
                        self._create_story_inkind_entitlements(enrollee, program, enrollment, enrollment_def, stats)

                    # Mark cycle membership as non_compliant (compliance failure)
                    if self.create_story_payments and enrollment_def.get("non_compliant_cycle"):
                        self._mark_cycle_membership_non_compliant(enrollee, program, enrollment_def, stats)

        # Create payment batches for each cycle
        if payments_by_cycle:
            batches = self._create_payment_batches(payments_by_cycle, stats)
            result["batches"] = batches

        return result

    def _create_story_enrollment(self, registrant, program, enrollment_def):
        """Create a program enrollment with proper backdating."""
        try:
            # Handle both enrolled_days_back and application_days_back
            if "application_days_back" in enrollment_def:
                days_back = enrollment_def["application_days_back"]
            else:
                days_back = enrollment_def.get("enrolled_days_back", 30)

            enrollment_date = fields.Datetime.now() - datetime.timedelta(days=days_back)

            # Determine state based on status
            status = enrollment_def.get("status")
            if status == "pending":
                state = "draft"
            elif status == "rejected":
                state = "not_eligible"
            elif enrollment_def.get("graduated_days_back"):
                state = "exited"  # Graduated
            else:
                state = "enrolled"

            membership_vals = {
                "partner_id": registrant.id,
                "program_id": program.id,
                "state": state,
            }

            membership = self.env["spp.program.membership"].create(membership_vals)

            # Backdate enrollment
            if state in ("enrolled", "exited"):
                self.env.cr.execute(
                    "UPDATE spp_program_membership SET enrollment_date = %s WHERE id = %s",
                    (enrollment_date, membership.id),
                )

            # Handle exit date for graduated beneficiaries
            if enrollment_def.get("graduated_days_back"):
                exit_date = fields.Date.today() - datetime.timedelta(days=enrollment_def["graduated_days_back"])
                membership.write({"exit_date": exit_date})

            return membership

        except Exception as e:
            _logger.error("Error creating enrollment: %s", e)
            return None

    def _mark_cycle_membership_non_compliant(self, registrant, program, enrollment_def, stats):
        """Mark an existing cycle membership as non_compliant for compliance failure demo.

        Used when a story requires showing that a beneficiary passed eligibility
        but failed compliance in a cycle (e.g., Santos income improved above threshold).
        Updates the existing cycle membership state from 'enrolled' to 'non_compliant'.
        """
        try:
            nc_def = enrollment_def.get("non_compliant_cycle")
            if not nc_def:
                return

            # Find the cycle for this program (same cycle used for payments)
            cycle = self._get_or_create_demo_cycle(program)
            if not cycle:
                _logger.warning(
                    "No cycle found for non_compliant marking (program_id=%s)",
                    program.id,
                )
                return

            # Find existing cycle membership
            cycle_membership = self.env["spp.cycle.membership"].search(
                [
                    ("partner_id", "=", registrant.id),
                    ("cycle_id", "=", cycle.id),
                ],
                limit=1,
            )

            if cycle_membership:
                cycle_membership.write({"state": "non_compliant"})
                _logger.info(
                    "Marked cycle membership as non_compliant (partner_id=%s, cycle_id=%s, membership_id=%s)",
                    registrant.id,
                    cycle.id,
                    cycle_membership.id,
                )
            else:
                # Create new cycle membership with non_compliant state
                days_back = nc_def.get("days_back", 30)
                enrollment_date = fields.Date.today() - datetime.timedelta(days=days_back)
                self.env["spp.cycle.membership"].create(
                    {
                        "partner_id": registrant.id,
                        "cycle_id": cycle.id,
                        "state": "non_compliant",
                        "enrollment_date": enrollment_date,
                    }
                )
                _logger.info(
                    "Created non_compliant cycle membership (partner_id=%s, cycle_id=%s)",
                    registrant.id,
                    cycle.id,
                )

            stats.setdefault("non_compliant_memberships", 0)
            stats["non_compliant_memberships"] += 1

        except Exception as e:
            _logger.warning(
                "Could not mark cycle membership as non_compliant (partner_id=%s, program_id=%s): %s",
                registrant.id,
                program.id,
                e,
            )

    def _create_story_payments(self, registrant, program, membership, enrollment_def, stats):
        """Create payment history for a story enrollment.

        Creates cycle membership, entitlements, and payments directly
        following the story definitions.

        Returns:
            tuple: (list of created payments, cycle used)
        """
        created_payments = []
        cycle = None
        payments_def = enrollment_def.get("payments", [])

        if not payments_def:
            return created_payments, cycle

        try:
            # Get or create a cycle for this program
            cycle = self._get_or_create_demo_cycle(program)
            if not cycle:
                _logger.warning("Could not get/create cycle for program (program_id=%s)", program.id)
                return created_payments, None

            # Get the journal for entitlements
            journal = program.journal_id
            if not journal:
                _logger.warning("No journal configured for program (program_id=%s), skipping payments", program.id)
                return created_payments, cycle

            # Create cycle membership for the registrant (required before entitlements)
            cycle_membership = self._get_or_create_cycle_membership(registrant, cycle, enrollment_def)
            if not cycle_membership:
                _logger.warning(
                    "Could not create cycle membership (partner_id=%s, cycle_id=%s)",
                    registrant.id,
                    cycle.id,
                )
                return created_payments, cycle

            for payment_def in payments_def:
                try:
                    amount = payment_def.get("amount", 100)
                    days_back = payment_def.get("days_back", 30)
                    status = payment_def.get("status", "paid")

                    payment_date = fields.Datetime.now() - datetime.timedelta(days=days_back)

                    # Create entitlement directly
                    entitlement = self.env["spp.entitlement"].create(
                        {
                            "partner_id": registrant.id,
                            "cycle_id": cycle.id,
                            "initial_amount": amount,
                            "is_cash_entitlement": True,
                            "state": "approved" if status == "paid" else "draft",
                            "date_approved": payment_date.date() if status == "paid" else None,
                            "valid_from": payment_date.date(),
                        }
                    )

                    # Create payment record directly
                    payment_status = "paid" if status == "paid" else "failed"
                    payment = self.env["spp.payment"].create(
                        {
                            "entitlement_id": entitlement.id,
                            "cycle_id": cycle.id,
                            "amount_issued": amount,
                            "amount_paid": amount if status == "paid" else 0,
                            "state": "reconciled" if status == "paid" else "issued",
                            "status": payment_status,
                            "payment_datetime": payment_date if status == "paid" else None,
                            "issuance_date": payment_date,
                        }
                    )

                    created_payments.append(payment)
                    stats["payments_created"] += 1
                    _logger.debug(
                        "Created %s payment of $%.2f (payment_id=%s, partner_id=%s)",
                        status,
                        amount,
                        payment.id,
                        registrant.id,
                    )

                except Exception as e:
                    _logger.warning("Could not create payment: %s", e)

        except Exception as e:
            _logger.error("Error creating story payments: %s", e)

        return created_payments, cycle

    def _create_payment_batches(self, payments_by_cycle, stats):
        """Create payment batches for each cycle.

        Groups payments by cycle and creates a batch record for each.

        Args:
            payments_by_cycle: dict mapping cycle_id to {"cycle": cycle, "payments": [payment records]}
            stats: Statistics dict to update

        Returns:
            list: Created payment batch records
        """
        created_batches = []

        for cycle_id, data in payments_by_cycle.items():
            cycle = data["cycle"]
            payments = data["payments"]

            if not payments:
                continue

            try:
                # Calculate batch statistics
                total_issued = sum(p.amount_issued for p in payments)
                total_paid = sum(p.amount_paid for p in payments)
                paid_payments = [p for p in payments if p.status == "paid"]
                failed_payments = [p for p in payments if p.status == "failed"]
                total_failed = sum(p.amount_issued for p in failed_payments)

                # Create the payment batch
                batch = self.env["spp.payment.batch"].create(
                    {
                        "cycle_id": cycle.id,
                        "payment_ids": [(6, 0, [p.id for p in payments])],
                        "has_batch_started": True,
                        "has_batch_completed": True,
                        "stats_issued_transactions": len(payments),
                        "stats_issued_amount": total_issued,
                        "stats_sent_transactions": len(payments),
                        "stats_sent_amount": total_issued,
                        "stats_paid_transactions": len(paid_payments),
                        "stats_paid_amount": total_paid,
                        "stats_failed_transactions": len(failed_payments),
                        "stats_failed_amount": total_failed,
                    }
                )

                created_batches.append(batch)
                stats["batches_created"] = stats.get("batches_created", 0) + 1
                _logger.info(
                    "Created payment batch (batch_id=%s, cycle_id=%s, payments=%d, amount=%.2f)",
                    batch.id,
                    cycle.id,
                    len(payments),
                    total_issued,
                )

            except Exception as e:
                _logger.warning("Could not create payment batch for cycle (cycle_id=%s): %s", cycle_id, e)

        return created_batches

    def _get_or_create_cycle_membership(self, registrant, cycle, enrollment_def):
        """Get existing or create cycle membership for a registrant."""
        try:
            # Check if membership already exists
            existing = self.env["spp.cycle.membership"].search(
                [
                    ("partner_id", "=", registrant.id),
                    ("cycle_id", "=", cycle.id),
                ],
                limit=1,
            )
            if existing:
                return existing

            # Create new cycle membership
            enrollment_days_back = enrollment_def.get("enrolled_days_back", 30)
            enrollment_date = fields.Date.today() - datetime.timedelta(days=enrollment_days_back)

            membership = self.env["spp.cycle.membership"].create(
                {
                    "partner_id": registrant.id,
                    "cycle_id": cycle.id,
                    "state": "enrolled",
                    "enrollment_date": enrollment_date,
                }
            )
            _logger.debug(
                "Created cycle membership (membership_id=%s, partner_id=%s, cycle_id=%s)",
                membership.id,
                registrant.id,
                cycle.id,
            )
            return membership

        except Exception as e:
            _logger.warning("Could not create cycle membership: %s", e)
            return None

    def _create_story_inkind_entitlements(self, registrant, program, membership, enrollment_def, stats):
        """Create in-kind entitlements for a story enrollment.

        Creates cycle membership and in-kind entitlements directly
        following the story definitions.
        """
        entitlements_def = enrollment_def.get("entitlements", [])

        if not entitlements_def:
            return

        try:
            # Get or create a cycle for this program
            cycle = self._get_or_create_demo_cycle(program)
            if not cycle:
                _logger.warning("Could not get/create cycle for program (program_id=%s)", program.id)
                return

            # Create cycle membership for the registrant
            cycle_membership = self._get_or_create_cycle_membership(registrant, cycle, enrollment_def)
            if not cycle_membership:
                _logger.warning(
                    "Could not create cycle membership for in-kind (partner_id=%s, cycle_id=%s)",
                    registrant.id,
                    cycle.id,
                )
                return

            for ent_def in entitlements_def:
                try:
                    item_name = ent_def.get("item", "Food Basket")
                    days_back = ent_def.get("days_back", 30)
                    status = ent_def.get("status", "delivered")

                    entitlement_date = fields.Date.today() - datetime.timedelta(days=days_back)

                    # Find or create the product
                    product = self.env["product.product"].search(
                        [("name", "=", item_name), ("type", "=", "product")],
                        limit=1,
                    )
                    if not product:
                        # Create a basic product for the in-kind item
                        product = self.env["product.product"].create(
                            {
                                "name": item_name,
                                "type": "product",
                                "list_price": 50.0,  # Nominal value
                            }
                        )
                        _logger.info("Created product for in-kind item: %s", item_name)

                    # Determine state based on status
                    if status == "delivered":
                        state = "rdpd2ben"  # Redeemed/Paid to Beneficiary
                    elif status == "approved":
                        state = "approved"
                    else:
                        state = "draft"

                    # Create in-kind entitlement directly
                    entitlement = self.env["spp.entitlement.inkind"].create(
                        {
                            "partner_id": registrant.id,
                            "cycle_id": cycle.id,
                            "product_id": product.id,
                            "quantity": 1,
                            "state": state,
                            "date_approved": entitlement_date if status in ("delivered", "approved") else None,
                            "valid_from": entitlement_date,
                        }
                    )

                    stats["entitlements_created"] = stats.get("entitlements_created", 0) + 1
                    _logger.debug(
                        "Created in-kind entitlement (entitlement_id=%s, partner_id=%s, item=%s)",
                        entitlement.id,
                        registrant.id,
                        item_name,
                    )

                except Exception as e:
                    _logger.warning("Could not create in-kind entitlement: %s", e)

        except Exception as e:
            _logger.error("Error creating story in-kind entitlements: %s", e)

    def _get_or_create_demo_cycle(self, program):
        """Get existing cycle or create a demo cycle for payment history."""
        # Look for existing cycle
        existing_cycle = self.env["spp.cycle"].search(
            [
                ("program_id", "=", program.id),
            ],
            limit=1,
            order="sequence desc",
        )

        if existing_cycle:
            return existing_cycle

        # Create a new cycle — use today as start_date to satisfy the
        # _check_dates constraint, then backdate via SQL for realistic demo data.
        try:
            today = fields.Date.today()
            cycle_vals = {
                "name": f"{program.name} - Demo Cycle 1",
                "program_id": program.id,
                "start_date": today,
                "end_date": today + datetime.timedelta(days=30),
                "sequence": 1,
                "state": "approved",
            }
            cycle = self.env["spp.cycle"].create(cycle_vals)
            # Backdate start_date for realistic payment history
            past_start = today - datetime.timedelta(days=180)
            self.env.cr.execute(
                "UPDATE spp_cycle SET start_date = %s WHERE id = %s",
                (past_start, cycle.id),
            )
            return cycle
        except Exception as e:
            _logger.error("Could not create demo cycle: %s", e)
            return None

    def _create_program_cycles(self, stats):
        """Create cycles with beneficiaries and entitlements for all programs.

        Uses direct record creation (same pattern as _create_story_payments)
        because the full ORM workflow requires approval definitions and fund
        balances that are not set up in demo data.
        """
        cycles = []
        programs = self.env["spp.program"].search(
            [
                ("state", "=", "active"),
                ("has_members", "=", True),
            ]
        )

        today = fields.Date.today()

        for program in programs:
            try:
                # Get or reuse existing cycle (created by story payments)
                cycle = self.env["spp.cycle"].search(
                    [("program_id", "=", program.id)],
                    limit=1,
                    order="sequence desc",
                )

                if not cycle:
                    # Create cycle with today as start_date (_check_dates requires >= today)
                    cycle = self.env["spp.cycle"].create(
                        {
                            "name": f"{program.name} - Demo Cycle 1",
                            "program_id": program.id,
                            "start_date": today,
                            "end_date": today + datetime.timedelta(days=30),
                            "sequence": 1,
                            "state": "draft",
                        }
                    )
                    stats["cycles_created"] += 1

                # Get all enrolled program members not already in cycle
                enrolled_members = self.env["spp.program.membership"].search(
                    [
                        ("program_id", "=", program.id),
                        ("state", "=", "enrolled"),
                    ]
                )
                existing_cycle_partner_ids = set(cycle.cycle_membership_ids.mapped("partner_id.id"))
                _existing = existing_cycle_partner_ids  # bind for lambda
                new_members = enrolled_members.filtered(lambda m, ex=_existing: m.partner_id.id not in ex)

                if not new_members:
                    _logger.info("Program ID=%s: all %d members already in cycle", program.id, len(enrolled_members))
                    cycles.append(cycle)
                    continue

                # Batch-create cycle memberships (use partner's registration date)
                cm_vals = [
                    {
                        "cycle_id": cycle.id,
                        "partner_id": m.partner_id.id,
                        "enrollment_date": m.partner_id.registration_date or today,
                        "state": "enrolled",
                    }
                    for m in new_members
                ]
                for i in range(0, len(cm_vals), 200):
                    self.env["spp.cycle.membership"].create(cm_vals[i : i + 200])
                stats["cycle_members_created"] = stats.get("cycle_members_created", 0) + len(cm_vals)

                # Determine entitlement amount from entitlement manager config
                base_amount = self._get_entitlement_amount(program)

                # Batch-create entitlements in approved state (bypasses approval workflow)
                ent_vals = [
                    {
                        "cycle_id": cycle.id,
                        "partner_id": m.partner_id.id,
                        "initial_amount": base_amount,
                        "state": "approved",
                        "is_cash_entitlement": True,
                        "valid_from": cycle.start_date,
                        "valid_until": cycle.end_date,
                    }
                    for m in new_members
                ]
                for i in range(0, len(ent_vals), 200):
                    self.env["spp.entitlement"].create(ent_vals[i : i + 200])
                stats["entitlements_created"] = stats.get("entitlements_created", 0) + len(ent_vals)

                # Ensure cycle is in approved state
                if cycle.state == "draft":
                    cycle.write(
                        {
                            "state": "approved",
                            "approved_date": fields.Datetime.now(),
                            "approved_by": self.env.user.id,
                        }
                    )

                # Backdate start_date via SQL (bypass _check_dates ORM constraint)
                backdated_start = today - datetime.timedelta(days=180)
                self.env.cr.execute(
                    "UPDATE spp_cycle SET start_date = %s WHERE id = %s",
                    (backdated_start, cycle.id),
                )
                cycle.invalidate_recordset(["start_date"])

                # Create program fund to cover entitlements (with 20% buffer)
                total_entitlement_amount = base_amount * len(new_members)
                self._create_program_fund(program, total_entitlement_amount * 1.2)

                cycles.append(cycle)
                _logger.info(
                    "Cycle '%s': %d beneficiaries, %d entitlements for program '%s'",
                    cycle.name,
                    len(cm_vals),
                    len(ent_vals),
                    program.name,
                )

            except Exception as e:
                _logger.warning("Could not create cycle for program ID=%s: %s", program.id, e)

        return cycles

    def _create_program_fund(self, program, amount):
        """Create a posted program fund entry to cover entitlements."""
        try:
            fund = self.env["spp.program.fund"].create(
                {
                    "name": f"Initial Fund - {program.name}",
                    "program_id": program.id,
                    "amount": amount,
                    "date_posted": fields.Date.today(),
                    "state": "draft",
                }
            )
            fund.post_fund()
            _logger.info(
                "Created program fund: %s = %.2f for '%s'",
                fund.name,
                amount,
                program.name,
            )
        except Exception as e:
            _logger.warning("Could not create fund for program ID=%s: %s", program.id, e)

    def _get_entitlement_amount(self, program):
        """Get the entitlement amount from program's entitlement manager config."""
        try:
            ent_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
            if ent_manager and hasattr(ent_manager, "manager_ref_id"):
                mgr_ref = ent_manager.manager_ref_id
                if hasattr(mgr_ref, "amount_per_cycle") and mgr_ref.amount_per_cycle:
                    return mgr_ref.amount_per_cycle
        except Exception:
            pass
        # Fallback: sensible demo default
        return 150.0

    # ══════════════════════════════════════════════════════════════
    # EVENT DATA GENERATION
    # ══════════════════════════════════════════════════════════════

    # Event scenarios for demo stories
    STORY_EVENTS = {
        "maria_santos": [
            {
                "event_type_code": "training",
                "days_back": 145,
                "data": {
                    "topic": "Financial Literacy and Livelihood Skills",
                    "duration_hours": 4,
                    "trainer": "Social Welfare Office",
                    "location": "Community Center",
                    "outcome": "Completed successfully",
                },
            },
        ],
        "pedro_reyes": [
            {
                "event_type_code": "extension_visit",
                "days_back": 250,
                "data": {
                    "visit_type": "Initial Assessment",
                    "findings": "Large household with multiple dependents. Good living conditions.",
                    "recommendations": "Consider additional livelihood support programs.",
                    "officer": "Extension Officer Martinez",
                },
            },
            {
                "event_type_code": "extension_visit",
                "days_back": 200,
                "data": {
                    "visit_type": "Follow-up",
                    "findings": "Household conditions improved. Dependents well cared for.",
                    "recommendations": "Continue current practices. Monitor progress.",
                    "officer": "Extension Officer Martinez",
                },
            },
        ],
        "rosa_garcia": [
            {
                "event_type_code": "vulnerability_assessment",
                "days_back": 195,
                "data": {
                    "assessment_score": "high",
                    "factors": ["elderly", "lives_alone", "low_income"],
                    "income_level": "below_poverty",
                    "housing_condition": "adequate",
                    "health_status": "requires_regular_medication",
                    "recommendation": "Priority enrollment in social protection programs",
                },
            },
        ],
        "ibrahim_hassan": [
            {
                "event_type_code": "vulnerability_assessment",
                "days_back": 58,
                "data": {
                    "assessment_score": "very_high",
                    "factors": ["displaced", "lost_assets", "large_family"],
                    "displacement_date": "2024-09-01",
                    "previous_location": "Northern Region",
                    "current_needs": ["shelter", "food", "livelihood_support"],
                    "recommendation": "Immediate enrollment in emergency assistance",
                },
            },
        ],
        "ana_mendoza": [
            {
                "event_type_code": "verification",
                "days_back": 75,
                "data": {
                    "verification_type": "Eligibility Check",
                    "verified_items": ["identity", "residence", "income_level"],
                    "result": "Eligible",
                    "notes": "Young beneficiary with verified documentation. GPS coordinates verified.",
                    "verifier": "Field Officer Chen",
                },
            },
        ],
    }

    def _create_story_events(self, stats):
        """Create event data for demo stories."""
        created_events = []

        for story_id, event_defs in self.STORY_EVENTS.items():
            # Find registrant
            story_name = self._get_story_name(story_id)
            registrant = self.env["res.partner"].search(
                [("name", "=", story_name), ("is_registrant", "=", True)],
                limit=1,
            )

            if not registrant:
                _logger.warning("Registrant not found for events (story_id=%s)", story_id)
                continue

            for event_def in event_defs:
                try:
                    event = self._create_single_event(registrant, event_def, stats)
                    if event:
                        created_events.append(event)
                except Exception as e:
                    _logger.error("Error creating event for story (story_id=%s): %s", story_id, e)

        return created_events

    def _create_single_event(self, registrant, event_def, stats):
        """Create a single event record."""
        event_type_code = event_def.get("event_type_code")
        days_back = event_def.get("days_back", 30)
        event_data = event_def.get("data", {})

        # Find event type
        event_type = self.env["spp.event.type"].search([("code", "=", event_type_code)], limit=1)
        if not event_type:
            _logger.warning("Event type not found (code=%s)", event_type_code)
            return None

        # Calculate dates
        collection_date = fields.Date.today() - datetime.timedelta(days=days_back)

        # Create event
        event_vals = {
            "event_type_id": event_type.id,
            "partner_id": registrant.id,
            "collection_date": collection_date,
            "data_json": event_data,
            "state": "active",
        }

        event = self.env["spp.event.data"].create(event_vals)
        stats["events_created"] += 1
        _logger.info("Created %s event (event_id=%s, partner_id=%s)", event_type_code, event.id, registrant.id)

        return event

    def _get_story_name(self, story_id):
        """Convert story ID to registrant name (locale-aware).

        Looks up the correct registrant name for a story ID by:
        1. Checking the demo_stories module for the localized story name
        2. Falling back to a mapping for CR-specific IDs that reference stories
        3. Using title-case conversion only as a last resort
        """
        locale = self.env.context.get("demo_locale")

        # First, try to get the name from demo_stories (canonical source)
        try:
            from odoo.addons.spp_demo.models import demo_stories

            name = demo_stories.get_localized_name(story_id, locale)
            if name:
                return name
        except ImportError:
            pass

        # Mapping for CR-specific IDs that reference existing stories
        # These are not actual story IDs but CR scenario identifiers
        # Resolve via the base story ID to get locale-aware names
        cr_id_to_story = {
            "amina_osman_draft": "amina_osman_household",
            "chen_large_family_split": "chen_large_family",
            "luis_fernandez_merge": "luis_fernandez",
            "maria_santos_conflict_1": "maria_santos",
            "maria_santos_conflict_2": "maria_santos",
            "carlos_elena_morales_remove": "carlos_elena_morales",
            "grace_okonkwo_create_group": "grace_okonkwo",
        }

        if story_id in cr_id_to_story:
            try:
                from odoo.addons.spp_demo.models import demo_stories

                name = demo_stories.get_localized_name(cr_id_to_story[story_id], locale)
                if name:
                    return name
            except ImportError:
                pass

        # Last resort: title-case the ID (for truly unknown IDs)
        # Log a warning since this may indicate a missing story definition
        _logger.warning(
            "Unknown story ID '%s', using title-case fallback. "
            "Consider adding this story to spp_demo.models.demo_stories.",
            story_id,
        )
        return story_id.replace("_", " ").title()

    def _ensure_demo_user_groups(self):
        """Assign module-specific security groups to role-based demo users.

        This method enriches the basic demo users (created in spp_demo) with
        additional groups based on installed modules. This showcases the access
        control system by giving each role appropriate permissions.

        Role mapping:
        - demo_viewer: Viewer groups (read-only access)
        - demo_officer: Officer/User groups (create/edit own records)
        - demo_supervisor: Supervisor/Validator groups (approve workflows, see team)
        - demo_manager: Manager groups (full domain access)
        - sppadmin: Admin groups (already has spp_admin which implies all)

        IMPORTANT: Menu visibility is cached at login time. Groups must be assigned
        BEFORE any user logs in, and cache must be cleared after assignment.
        """
        groups_assigned = False

        # Define group mappings per role and module
        # Format: (demo_user_xmlid, [(module, group_xmlid), ...])
        # Groups are only added if the module is installed (ref returns False otherwise)
        role_group_mappings = [
            # VIEWER: Read-only access
            (
                "spp_demo.demo_viewer",
                [
                    ("spp_registry", "group_registry_viewer"),  # Registry access
                    ("spp_service_points", "group_service_points_viewer"),  # Registrant form reads service points
                    ("spp_vocabulary", "group_vocabulary_viewer"),  # Vocabulary read access for forms
                    ("spp_programs", "group_programs_viewer"),
                    ("spp_change_request_v2", "group_cr_user"),  # Needs user to see menu
                    ("spp_grm", "group_grm_viewer"),
                    ("spp_case_base", "group_case_viewer"),
                ],
            ),
            # OFFICER: Field worker - creates records, sees own
            (
                "spp_demo.demo_officer",
                [
                    ("spp_registry", "group_registry_officer"),  # Registry access
                    ("spp_service_points", "group_service_points_officer"),
                    ("spp_vocabulary", "group_vocabulary_officer"),  # Vocabulary for editing/creating
                    ("spp_programs", "group_programs_officer"),
                    ("spp_change_request_v2", "group_cr_user"),
                    ("spp_grm", "group_grm_officer"),
                    ("spp_case_base", "group_case_worker"),
                ],
            ),
            # SUPERVISOR: Team lead - approves, sees team records
            (
                "spp_demo.demo_supervisor",
                [
                    ("spp_registry", "group_registry_officer"),  # Registry access (officer level)
                    ("spp_service_points", "group_service_points_officer"),
                    ("spp_vocabulary", "group_vocabulary_officer"),
                    ("spp_programs", "group_programs_officer"),
                    ("spp_change_request_v2", "group_cr_validator"),
                    ("spp_grm", "group_grm_supervisor"),
                    ("spp_case_base", "group_case_supervisor"),
                ],
            ),
            # MANAGER: Full domain access
            (
                "spp_demo.demo_manager",
                [
                    ("spp_registry", "group_registry_manager"),  # Registry access
                    ("spp_registry_search", "group_registry_auditor"),  # Browse-all audit access
                    ("spp_service_points", "group_service_points_manager"),
                    ("spp_vocabulary", "group_vocabulary_manager"),  # Full vocabulary access
                    ("spp_programs", "group_programs_manager"),
                    ("spp_change_request_v2", "group_cr_manager"),
                    ("spp_grm", "group_grm_manager"),
                    ("spp_case_base", "group_case_manager"),
                    ("spp_cel_domain", "group_cel_domain_manager"),  # CEL Domain Manager access
                    ("spp_studio", "group_studio_manager"),  # Studio Manager access
                ],
            ),
        ]

        for user_xmlid, group_refs in role_group_mappings:
            user = self.env.ref(user_xmlid, raise_if_not_found=False)
            if not user:
                continue

            groups_to_add = []
            for module, group_name in group_refs:
                group_xmlid = f"{module}.{group_name}"
                group = self.env.ref(group_xmlid, raise_if_not_found=False)
                if group and group.id not in user.group_ids.ids:
                    groups_to_add.append(group.id)

            if groups_to_add:
                user.write({"group_ids": [Command.link(gid) for gid in groups_to_add]})
                groups_assigned = True
                _logger.info(
                    "Assigned %d groups to demo user %s",
                    len(groups_to_add),
                    user.login,
                )

        # Also ensure admin/sppadmin have proper access to all modules
        admin_groups_assigned = self._ensure_admin_access()

        if groups_assigned or admin_groups_assigned:
            # Commit and clear cache for menu visibility
            # Skip commit in test mode to avoid breaking test isolation
            if not config["test_enable"]:
                self.env.cr.commit()
            self.env.registry.clear_cache()
            _logger.info("Demo user groups assigned and cache cleared")

    def _ensure_admin_access(self):
        """Ensure admin users have proper access to all modules for testing.

        Assigns necessary security groups to admin and sppadmin users so they can
        access all modules and perform all operations needed for E2E tests.

        Returns:
            bool: True if any groups were assigned, False otherwise
        """
        # Find admin users
        admin_users = self.env["res.users"].search(
            [
                ("login", "in", ["admin", "sppadmin"]),
            ]
        )

        if not admin_users:
            return False

        # Define all groups admin should have for full access
        admin_group_mappings = [
            # Registry - Manager level for full access
            ("spp_registry", "group_registry_manager"),
            # Registry Search - Auditor for browse-all menus
            ("spp_registry_search", "group_registry_auditor"),
            # Service points - Manager level for full access (registry form reads it)
            ("spp_service_points", "group_service_points_manager"),
            # Vocabulary - Manager level for full access
            ("spp_vocabulary", "group_vocabulary_manager"),
            # Programs - Manager level for create/edit access
            ("spp_programs", "group_programs_manager"),
            # Change Request - Manager level for full CR access
            ("spp_change_request_v2", "group_cr_manager"),
            # GRM - Manager level for full ticket access
            ("spp_grm", "group_grm_manager"),
            # Case Management - Manager level for full case access
            ("spp_case_base", "group_case_manager"),
        ]

        any_groups_assigned = False
        for user in admin_users:
            groups_to_add = []
            for module, group_name in admin_group_mappings:
                group_xmlid = f"{module}.{group_name}"
                group = self.env.ref(group_xmlid, raise_if_not_found=False)
                if group and group.id not in user.group_ids.ids:
                    groups_to_add.append(group.id)

            if groups_to_add:
                user.write({"group_ids": [Command.link(gid) for gid in groups_to_add]})
                any_groups_assigned = True
                _logger.info(
                    "Assigned %d groups to admin user %s",
                    len(groups_to_add),
                    user.login,
                )

        return any_groups_assigned

    def _get_demo_user(self, role):
        """Get a demo user by role for creating demo data.

        Args:
            role: One of 'viewer', 'officer', 'supervisor', 'manager', 'admin'

        Returns:
            res.users record or False if not found
        """
        user_map = {
            "viewer": "spp_demo.demo_viewer",
            "officer": "spp_demo.demo_officer",
            "supervisor": "spp_demo.demo_supervisor",
            "manager": "spp_demo.demo_manager",
            "admin": "spp_demo.demo_admin",
            "cr_validator": "spp_mis_demo_v2.demo_user_cr_local_validator",
            "cr_validator_hq": "spp_mis_demo_v2.demo_user_cr_hq_validator",
        }
        xmlid = user_map.get(role)
        if not xmlid:
            return False
        return self.env.ref(xmlid, raise_if_not_found=False)

    # ══════════════════════════════════════════════════════════════
    # CHANGE REQUEST GENERATION
    # ══════════════════════════════════════════════════════════════

    # Change request scenarios for demo stories
    STORY_CHANGE_REQUESTS = {
        # Individual edits
        "maria_santos": {
            "type_code": "edit_individual",
            "days_back": 15,
            "state": "approved",
            "description": "Phone/address update after moving (approved)",
            "proposed_changes": {
                "phone": "+1-555-0199",
                "address_line1": "789 New Ave",
                "city": "Newcity",
                "postal_code": "20002",
            },
        },
        # Conflict detection demo - CR1 for Maria Santos (phone update)
        "maria_santos_conflict_1": {
            "type_code": "edit_individual",
            "days_back": 3,
            "state": "pending",
            "description": "Update phone number (pending - conflicts with CR2)",
            "registrant_name": "Maria Santos",
            "proposed_changes": {
                "phone": "+1-555-9999",
            },
        },
        # Conflict detection demo - CR2 for Maria Santos (address update)
        "maria_santos_conflict_2": {
            "type_code": "edit_individual",
            "days_back": 2,
            "state": "pending",
            "description": "Update address (pending - conflicts with CR1)",
            "registrant_name": "Maria Santos",
            "proposed_changes": {
                "address_line1": "456 Conflict Ave",
                "city": "Conflictville",
            },
        },
        # Dedicated draft example to exercise workflow buttons without breaking unit expectations
        # Uses amina_osman_household (single-parent with 3 children) for realistic demo
        "amina_osman_draft": {
            "type_code": "edit_group",
            "days_back": 5,
            "state": "draft",
            "description": "Keep one draft change request for UI workflow demo",
            "registrant_name": "Aquino",
            "is_group": True,
            "proposed_changes": {
                "address_line1": "123 Demo Street",
                "city": "Draftville",
            },
        },
        "juan_dela_cruz": {
            "type_code": "update_id",
            "days_back": 12,
            "state": "approved",
            "description": "Correct national ID number",
            "proposed_changes": {
                "new_id_number": "NAT-2024-998877",
            },
        },
        "rosa_garcia": {
            "type_code": "exit_registrant",
            "days_back": 7,
            "state": "pending",
            "description": "Graduated from assistance program (pending approval)",
            "proposed_changes": {
                "exit_reason": "other",
                "remarks": "Graduated; no longer receiving benefits",
            },
        },
        # Household / group operations
        "carlos_elena_morales": {
            "type_code": "add_member",
            "days_back": 10,
            "state": "approved",
            "description": "Add newborn to Morales household",
            "is_group": True,
            "proposed_changes": {
                "given_name": "Baby Morales",
                "family_name": "Morales",
                "birthdate": fields.Date.today(),
                "relationship_xmlid": "spp_mis_demo_v2.code_membership_type_child",
            },
        },
        # Phase 5.1: Add remove_member CR
        "carlos_elena_morales_remove": {
            "type_code": "remove_member",
            "days_back": 8,
            "state": "pending",
            "description": "Adult child (16) moving out for university studies",
            "registrant_name": "Morales",
            "is_group": True,
            "proposed_changes": {
                "member_name": "Teen Morales",
                "removal_reason": "relocation",
                "remarks": "Moving to university dormitory",
            },
        },
        "chen_large_family": {
            "type_code": "transfer_member",
            "days_back": 8,
            "state": "pending",
            "description": "Transfer Patricia Bautista to elderly relatives for school",
            "is_group": True,
            "proposed_changes": {
                "member_name": "Patricia Bautista",
                "target_group_story": "manuel_gloria_elderly",
                "transfer_reason": "relocation",
            },
        },
        "nguyen_extended_family": {
            "type_code": "change_hoh",
            "days_back": 6,
            # Keep approved to match unit test expectations
            "state": "approved",
            "description": "Set Lourdes Navarro as new head of household (approved)",
            "is_group": True,
            "proposed_changes": {
                "new_head_name": "Lourdes Navarro",
            },
        },
        # Phase 5.1: Add create_group CR
        "grace_okonkwo_create_group": {
            "type_code": "create_group",
            "days_back": 4,
            "state": "draft",
            "description": "Register new household after marriage",
            "registrant_name": "Maricel Ramos",
            "is_group": False,  # Creating from individual
            "proposed_changes": {
                "group_name": "Ramos",
                "head_name": "Maricel Ramos",
                "address_line1": "123 Marriage Lane",
                "city": "New Family City",
            },
        },
        # Phase 5.1 & 5.2: Add split_household CR (REJECTED)
        # Uses chen_large_family (7-member household) for realistic split demo
        "chen_large_family_split": {
            "type_code": "split_household",
            "days_back": 12,
            "state": "rejected",
            "description": "Split Chen household due to family separation",
            "registrant_name": "Bautista",
            "is_group": True,
            "rejection_reason": "Incomplete documentation for property division",
            "proposed_changes": {
                "split_reason": "separation",
                "new_group_name": "Bautista B",
                "members_to_transfer": ["Patricia Bautista", "Fernando Bautista"],
            },
        },
        # Phase 5.1 & 5.2: Add merge_registrants CR (REVISION)
        # Uses luis_fernandez for realistic duplicate detection demo
        "luis_fernandez_merge": {
            "type_code": "merge_registrants",
            "days_back": 9,
            "state": "revision",
            "description": "Merge duplicate registrations found in data quality check",
            "registrant_name": "Luis Fernandez",
            "revision_notes": "Please confirm which record should be primary and verify contact details",
            "proposed_changes": {
                "primary_registrant": "Luis Fernandez",
                "duplicate_registrant": "Luis Fernandez (Mobile)",
                "merge_strategy": "keep_primary",
            },
        },
    }

    def _create_story_change_requests(self, stats):
        """Create change requests for demo stories with realistic workflow.

        This creates a complete audit trail demonstrating access control:
        - demo_officer creates the CR (can only see their own CRs)
        - demo_supervisor submits and validates (can see team CRs)
        - demo_manager approves and applies (can see all CRs)

        The resulting demo data shows proper separation of duties.
        """
        created_crs = []

        # Check if change request model is available
        if "spp.change.request" not in self.env:
            _logger.warning("Change request model not available")
            return created_crs

        # Get demo_officer to create CRs (demonstrates access control)
        # CRs created by officer will be visible to officer (own), supervisor, manager
        demo_officer = self._get_demo_user("officer")
        if demo_officer:
            _logger.info("Creating CRs as demo_officer (user_id=%s)", demo_officer.id)

        for story_id, cr_def in self.STORY_CHANGE_REQUESTS.items():
            # Localize CR definition for current locale
            localized_def = self._localize_cr_def(story_id, cr_def)
            registrant = self._ensure_story_registrant(story_id, localized_def)

            if not registrant:
                _logger.warning("Registrant not found for change request (story_id=%s)", story_id)
                continue

            try:
                cr = self._create_single_change_request(registrant, localized_def, stats, demo_user=demo_officer)
                if cr:
                    created_crs.append(cr)
            except Exception as e:
                _logger.error("Error creating change request for story (story_id=%s): %s", story_id, e)

        return created_crs

    def _localize_cr_def(self, story_id, cr_def):
        """Localize CR definition names for the current locale.

        Replaces hardcoded member names in proposed_changes with locale-aware
        versions by looking up member names from the localized story profiles.
        """
        locale = self.env.context.get("demo_locale")
        if not locale or locale == "fil_PH":
            return cr_def

        try:
            from odoo.addons.spp_demo.models import demo_stories
        except ImportError:
            return cr_def

        locale_map = demo_stories.LOCALE_NAMES.get(locale, {})
        if not locale_map:
            return cr_def

        import copy as _copy

        localized = _copy.deepcopy(cr_def)
        changes = localized.get("proposed_changes", {})

        # Map CR story_id to base story_id for profile lookups
        cr_to_base = {
            "amina_osman_draft": "amina_osman_household",
            "chen_large_family_split": "chen_large_family",
            "luis_fernandez_merge": "luis_fernandez",
            "maria_santos_conflict_1": "maria_santos",
            "maria_santos_conflict_2": "maria_santos",
            "carlos_elena_morales_remove": "carlos_elena_morales",
            "grace_okonkwo_create_group": "grace_okonkwo",
        }
        base_id = cr_to_base.get(story_id, story_id)
        entry = locale_map.get(base_id, {})
        pnames = entry.get("profile_names", {})
        localized_name = entry.get("name", "")

        # Localize member_name (transfer/remove member — matches child or adult)
        if "member_name" in changes and pnames.get("children"):
            # Find which child index matches the original name
            orig_story = demo_stories.get_story_by_id(base_id)
            if orig_story:
                orig_children = orig_story.get("profile", {}).get("children", [])
                for idx, child in enumerate(orig_children):
                    if child["name"] == changes["member_name"] and idx < len(pnames["children"]):
                        changes["member_name"] = pnames["children"][idx]
                        break

        # Localize new_head_name (change_hoh — matches adult)
        if "new_head_name" in changes and pnames.get("adults"):
            orig_story = demo_stories.get_story_by_id(base_id)
            if orig_story:
                orig_adults = orig_story.get("profile", {}).get("adults", [])
                for idx, adult in enumerate(orig_adults):
                    if adult["name"] == changes["new_head_name"] and idx < len(pnames["adults"]):
                        changes["new_head_name"] = pnames["adults"][idx]
                        break

        # Localize head_name and group_name (create_group)
        if "head_name" in changes and localized_name:
            changes["head_name"] = localized_name
        if "group_name" in changes and localized_name:
            # Derive group name from localized surname
            surname = localized_name.split()[-1] if localized_name else ""
            changes["group_name"] = f"{surname} Household"

        # Localize new_group_name (split_household)
        if "new_group_name" in changes and localized_name:
            surname = localized_name.split()[-1] if localized_name else ""
            changes["new_group_name"] = f"{surname} Family - Unit B"

        # Localize given_name / family_name (add_member — new baby)
        if "family_name" in changes and localized_name:
            surname = localized_name.split()[-1] if localized_name else ""
            changes["family_name"] = surname
            if "given_name" in changes:
                changes["given_name"] = f"Baby {surname}"

        # Localize primary_registrant / duplicate_registrant (merge)
        if "primary_registrant" in changes and localized_name:
            changes["primary_registrant"] = localized_name
        if "duplicate_registrant" in changes and localized_name:
            changes["duplicate_registrant"] = f"{localized_name} (Mobile)"

        # Localize members_to_transfer list
        if "members_to_transfer" in changes and pnames.get("children"):
            orig_story = demo_stories.get_story_by_id(base_id)
            if orig_story:
                orig_children = orig_story.get("profile", {}).get("children", [])
                localized_list = []
                for orig_name in changes["members_to_transfer"]:
                    found = False
                    for idx, child in enumerate(orig_children):
                        if child["name"] == orig_name and idx < len(pnames["children"]):
                            localized_list.append(pnames["children"][idx])
                            found = True
                            break
                    if not found:
                        localized_list.append(orig_name)
                changes["members_to_transfer"] = localized_list

        return localized

    def _ensure_story_registrant(self, story_id, cr_def):
        """Ensure registrant exists for a story; create minimal if missing.

        Uses _get_story_name() for locale-aware name resolution.
        """
        # Always use locale-aware name resolution (handles CR-specific IDs too)
        story_name = self._get_story_name(story_id)

        registrant = self.env["res.partner"].search(
            [("name", "=", story_name), ("is_registrant", "=", True)],
            limit=1,
        )
        if registrant:
            return registrant

        # Create minimal registrant if not found
        return self.env["res.partner"].create(
            {
                "name": story_name,
                "is_registrant": True,
                "is_group": cr_def.get("is_group", False),
            }
        )

    def _create_single_change_request(self, registrant, cr_def, stats, demo_user=None):
        """Create a single change request record.

        Args:
            registrant: The registrant partner record
            cr_def: Change request definition dict
            stats: Statistics tracking dict
            demo_user: Optional user to create CR as (for access control demo)
        """
        cr_type_code = cr_def.get("type_code") or ("edit_group" if registrant.is_group else "edit_individual")
        days_back = cr_def.get("days_back", 10)
        target_state = cr_def.get("state", "draft")
        proposed_changes = cr_def.get("proposed_changes", {})

        # Find CR type by code
        cr_type = self.env["spp.change.request.type"].search(
            [("code", "=", cr_type_code)],
            limit=1,
        )
        if not cr_type:
            _logger.warning("Change request type not found (code=%s)", cr_type_code)
            return None

        # Calculate request date
        request_date = fields.Datetime.now() - datetime.timedelta(days=days_back)

        try:
            # Create the base change request (detail auto-created)
            # Uses with_user() to set correct create_uid for access control demo
            cr_vals = {
                "request_type_id": cr_type.id,
                "registrant_id": registrant.id,
                "description": cr_def.get("description"),
            }

            # Use with_user() on the model if demo_user is provided
            cr_model = self.env["spp.change.request"]
            if demo_user:
                # Use with_user() only for demo data generation to simulate
                # different request owners; demo_user is a controlled user
                # provided by the test/demo setup.
                cr_model = cr_model.with_user(demo_user)  # nosemgrep: odoo-with-user-unvalidated
            cr = cr_model.create(cr_vals)

            # Backdate the creation
            self.env.cr.execute(
                "UPDATE spp_change_request SET create_date = %s WHERE id = %s",
                (request_date, cr.id),
            )
            detail = cr._ensure_detail()
            detail_vals = self._build_detail_changes(detail._name, registrant, proposed_changes, cr_def)
            if detail_vals:
                detail.write(detail_vals)
                # Backdate detail creation for timeline consistency
                self.env.cr.execute(
                    f"UPDATE {detail._table} SET create_date = %s WHERE id = %s",  # nosec B608
                    (request_date, detail.id),
                )

            # Progress state if needed (valid states: draft, pending, approved, rejected, revision)
            if target_state == "pending":
                self._set_cr_state(cr, "pending")
            elif target_state == "approved":
                self._set_cr_state(cr, "approved")
            elif target_state == "applied":
                self._set_cr_state(cr, "approved", apply=True)
            elif target_state == "rejected":
                rejection_reason = cr_def.get("rejection_reason", "Request rejected")
                self._set_cr_state(cr, "rejected", rejection_reason=rejection_reason)
            elif target_state == "revision":
                revision_notes = cr_def.get("revision_notes", "Please revise and resubmit")
                self._set_cr_state(cr, "revision", revision_notes=revision_notes)

            stats["change_requests_created"] += 1
            _logger.info("Created %s change request (cr_id=%s, partner_id=%s)", target_state, cr.id, registrant.id)

            return cr

        except Exception as e:
            _logger.error("Failed to create change request: %s", e)
            return None

    def _set_cr_state(self, cr, target_state, apply=False, rejection_reason=None, revision_notes=None):
        """Transition CR to target state using the proper approval workflow.

        The approval system checks actual user group membership (not just ACL),
        so we must use with_user() to switch to a user with the right role:
        - Submit: demo_officer (requestor)
        - Approve/Reject/Revision: demo_cr_validator (has CR validator group)

        Falls back to admin if demo validator user is not available.

        Args:
            cr: Change request record
            target_state: Target state (pending, approved, rejected, revision)
            apply: If True, apply the CR after approval
            rejection_reason: Reason for rejection (for rejected state)
            revision_notes: Notes for revision request (for revision state)
        """
        # Get validator users for approval actions (approve, reject, revision)
        # Multi-tier approvals need both local and HQ validators
        local_validator = self._get_demo_user("cr_validator")
        hq_validator = self._get_demo_user("cr_validator_hq")
        # Fall back to admin if no validator users
        fallback = self.env.ref("base.user_admin", raise_if_not_found=False)
        local_validator = local_validator or fallback
        hq_validator = hq_validator or fallback

        try:
            if target_state == "pending":
                cr.sudo().action_submit_for_approval()
            elif target_state == "approved":
                cr.sudo().action_submit_for_approval()
                # Approve all tiers — multi-tier requires each tier's validator
                cr.with_user(local_validator).sudo().action_approve()
                if cr.approval_state == "pending":
                    # Still pending = more tiers, approve with HQ validator
                    cr.with_user(hq_validator).sudo().action_approve()
            elif target_state == "rejected":
                cr.sudo().action_submit_for_approval()
                # Use _do_reject directly to bypass the wizard
                cr.with_user(local_validator).sudo()._do_reject(rejection_reason or "Request rejected")
            elif target_state == "revision":
                cr.sudo().action_submit_for_approval()
                # Use _do_request_revision directly to bypass the wizard
                cr.with_user(local_validator).sudo()._do_request_revision(
                    revision_notes or "Please revise and resubmit"
                )
        except Exception as e:
            # Don't fall back to direct state write for states that require approval reviews.
            # This would create an inconsistent state (approval_state=pending but no pending reviews).
            _logger.warning(
                "Approval flow failed for CR %s (target_state=%s): %s. "
                "CR will remain in current state (%s) to avoid data inconsistency.",
                cr.name,
                target_state,
                e,
                cr.approval_state,
            )

        if apply:
            try:
                cr.with_user(hq_validator).sudo().action_apply()
            except Exception as e:
                _logger.warning("Apply step failed, setting applied flags directly: %s", e)
                cr.sudo().write(
                    {
                        "approval_state": "approved",
                        "is_applied": True,
                        "applied_date": fields.Datetime.now(),
                        "applied_by_id": self.env.user.id,
                    }
                )

    def _build_detail_changes(self, detail_model, registrant, proposed_changes, cr_def):
        """Map proposed_changes to CR detail fields for V2 CR types."""
        vals = {}
        proposed_changes = proposed_changes or {}

        # Use provided changes when field names match detail fields
        for key, change in proposed_changes.items():
            new_val = change.get("new_value") if isinstance(change, dict) else change
            if key in self.env[detail_model]._fields:
                vals[key] = new_val

        # If nothing mapped, generate simple edits to show a change
        if not vals:
            if detail_model == "spp.cr.detail.edit_individual":
                vals.update(
                    {
                        "phone": proposed_changes.get("phone") or (registrant.phone or "555-0101"),
                        "address_line1": proposed_changes.get("address_line1") or "123 Demo Street",
                        "city": proposed_changes.get("city") or "Demo City",
                        "postal_code": proposed_changes.get("postal_code") or registrant.zip,
                        "gender_id": registrant.gender_id.id,
                    }
                )
            elif detail_model == "spp.cr.detail.edit_group":
                vals.update(
                    {
                        "group_name": proposed_changes.get("group_name") or f"{registrant.name} (updated)",
                        "phone": proposed_changes.get("phone") or (registrant.phone or "555-0202"),
                        "address_line1": proposed_changes.get("address_line1") or "456 Demo Avenue",
                        "postal_code": proposed_changes.get("postal_code") or registrant.zip,
                    }
                )
            elif detail_model == "spp.cr.detail.add_member":
                rel_xmlid = proposed_changes.get("relationship_xmlid")
                relationship_id = False
                if rel_xmlid:
                    relationship_id = self.env.ref(rel_xmlid, raise_if_not_found=False)
                    relationship_id = relationship_id.id if relationship_id else False
                vals.update(
                    {
                        "given_name": proposed_changes.get("given_name"),
                        "family_name": proposed_changes.get("family_name"),
                        "member_name": " ".join(
                            filter(None, [proposed_changes.get("given_name"), proposed_changes.get("family_name")])
                        ),
                        "birthdate": proposed_changes.get("birthdate"),
                        "relationship_id": relationship_id,
                    }
                )
            elif detail_model == "spp.cr.detail.transfer_member":
                member_name = proposed_changes.get("member_name")
                target_story = proposed_changes.get("target_group_story")
                membership = False
                target_group = False
                if member_name:
                    # Search by given_name first (more reliable than computed name)
                    # Names in the system are stored as "FAMILY, GIVEN" uppercase
                    name_parts = member_name.split()
                    given_name = name_parts[0] if name_parts else member_name
                    membership = self.env["spp.group.membership"].search(
                        [
                            ("group", "=", registrant.id),
                            ("individual.given_name", "ilike", given_name),
                            ("status", "=", "active"),
                        ],
                        limit=1,
                    )
                if target_story:
                    target_name = self._get_story_name(target_story)
                    # Search with ilike for case-insensitive match
                    target_group = self.env["res.partner"].search(
                        [("name", "ilike", target_name), ("is_group", "=", True), ("is_registrant", "=", True)],
                        limit=1,
                    )
                vals.update(
                    {
                        "membership_id": membership.id if membership else False,
                        "target_group_id": target_group.id if target_group else False,
                        "transfer_reason": proposed_changes.get("transfer_reason", "relocation"),
                    }
                )
            elif detail_model == "spp.cr.detail.change_hoh":
                new_head_name = proposed_changes.get("new_head_name")
                if new_head_name:
                    # Search by given_name for case-insensitive match
                    name_parts = new_head_name.split()
                    given_name = name_parts[0] if name_parts else new_head_name
                    individual = self.env["res.partner"].search(
                        [
                            ("given_name", "ilike", given_name),
                            ("is_group", "=", False),
                            ("is_registrant", "=", True),
                        ],
                        limit=1,
                    )
                    vals["new_head_id"] = individual.id if individual else False
            # Phase 5.1: Add remove_member support
            elif detail_model == "spp.cr.detail.remove_member":
                member_name = proposed_changes.get("member_name")
                membership = False
                if member_name:
                    # Search by given_name for case-insensitive match
                    name_parts = member_name.split()
                    given_name = name_parts[0] if name_parts else member_name
                    membership = self.env["spp.group.membership"].search(
                        [
                            ("group", "=", registrant.id),
                            ("individual.given_name", "ilike", given_name),
                            ("status", "=", "active"),
                        ],
                        limit=1,
                    )
                vals.update(
                    {
                        "membership_id": membership.id if membership else False,
                        "removal_reason": proposed_changes.get("removal_reason", "other"),
                        "remarks": proposed_changes.get("remarks", ""),
                    }
                )
            # Phase 5.1: Add create_group support
            elif detail_model == "spp.cr.detail.create_group":
                vals.update(
                    {
                        "group_name": proposed_changes.get("group_name", "New Household"),
                        "head_name": proposed_changes.get("head_name", ""),
                        "address_line1": proposed_changes.get("address_line1", ""),
                        "city": proposed_changes.get("city", ""),
                        "postal_code": proposed_changes.get("postal_code", ""),
                    }
                )
            # Phase 5.1: Add split_household support
            elif detail_model == "spp.cr.detail.split_household":
                vals.update(
                    {
                        "split_reason": proposed_changes.get("split_reason", "separation"),
                        "new_group_name": proposed_changes.get("new_group_name", f"{registrant.name} - Split"),
                        "remarks": proposed_changes.get("remarks", ""),
                    }
                )
                # Note: members_to_transfer is typically a list, may need special handling
                members_to_transfer = proposed_changes.get("members_to_transfer", [])
                if members_to_transfer and "member_ids" in self.env[detail_model]._fields:
                    # This would need to map member names to IDs
                    # For demo purposes, we'll leave it empty or handle in future enhancement
                    pass
            # Phase 5.1: Add merge_registrants support
            elif detail_model == "spp.cr.detail.merge_registrants":
                # Find registrants by name if provided
                primary_name = proposed_changes.get("primary_registrant")
                duplicate_name = proposed_changes.get("duplicate_registrant")
                primary_id = False
                duplicate_id = False

                if primary_name:
                    primary = self.env["res.partner"].search(
                        [("name", "ilike", primary_name), ("is_registrant", "=", True)], limit=1
                    )
                    primary_id = primary.id if primary else False

                if duplicate_name:
                    duplicate = self.env["res.partner"].search(
                        [("name", "ilike", duplicate_name), ("is_registrant", "=", True)], limit=1
                    )
                    duplicate_id = duplicate.id if duplicate else False

                vals.update(
                    {
                        "primary_registrant_id": primary_id or registrant.id,
                        "duplicate_registrant_id": duplicate_id or False,
                        "merge_strategy": proposed_changes.get("merge_strategy", "keep_primary"),
                    }
                )

        return vals

    def _create_fairness_analysis_demo(self, stats):
        """Create fairness analysis demo data.

        This creates sample disparity analysis records for demo programs
        if the spp_dashboard_fairness module is installed.
        """
        # Check if fairness module is installed
        if "spp.fairness.analysis" not in self.env:
            _logger.info("spp_dashboard_fairness not installed, skipping fairness demo data")
            stats["fairness_analysis_created"] = 0
            return

        FairnessAnalysis = self.env["spp.fairness.analysis"]
        FairnessSnapshot = self.env.get("spp.fairness.snapshot")

        # Get all demo programs
        programs = self.env["spp.program"].search([])
        if not programs:
            _logger.warning("No programs found for fairness analysis demo")
            stats["fairness_analysis_created"] = 0
            return

        created_count = 0
        snapshot_count = 0
        current_period = datetime.datetime.now().strftime("%Y-%m")
        previous_periods = [
            (datetime.datetime.now() - datetime.timedelta(days=30 * i)).strftime("%Y-%m")
            for i in range(1, 4)  # Last 3 months
        ]

        for program in programs:
            # Create analysis for each attribute
            for attribute, attr_data in self._get_fairness_demo_data().items():
                # Current period analysis
                existing = FairnessAnalysis.search(
                    [
                        ("program_id", "=", program.id),
                        ("attribute", "=", attribute),
                        ("period_key", "=", current_period),
                    ],
                    limit=1,
                )

                if not existing:
                    FairnessAnalysis.create(
                        {
                            "program_id": program.id,
                            "attribute": attribute,
                            "period_key": current_period,
                            "overall_coverage": attr_data["overall_coverage"],
                            "disparities_json": attr_data["disparities"],
                        }
                    )
                    created_count += 1

                # Historical periods (with slight variations)
                for i, period in enumerate(previous_periods):
                    existing = FairnessAnalysis.search(
                        [
                            ("program_id", "=", program.id),
                            ("attribute", "=", attribute),
                            ("period_key", "=", period),
                        ],
                        limit=1,
                    )

                    if not existing:
                        # Add slight variation to historical data
                        variation = 1 + (random.random() - 0.5) * 0.1 * (i + 1)
                        historical_disparities = {}
                        for group, data in attr_data["disparities"].items():
                            historical_disparities[group] = {
                                "count": int(data["count"] * variation),
                                "coverage": min(1.0, data["coverage"] * variation),
                                "ratio": min(1.5, data["ratio"] * variation),
                            }

                        FairnessAnalysis.create(
                            {
                                "program_id": program.id,
                                "attribute": attribute,
                                "period_key": period,
                                "overall_coverage": min(1.0, attr_data["overall_coverage"] * variation),
                                "disparities_json": historical_disparities,
                            }
                        )
                        created_count += 1

            # Create snapshot if model exists
            if FairnessSnapshot:
                existing_snapshot = FairnessSnapshot.search(
                    [
                        ("program_id", "=", program.id),
                        ("snapshot_date", "=", datetime.date.today()),
                    ],
                    limit=1,
                )

                if not existing_snapshot:
                    FairnessSnapshot.create(
                        {
                            "program_id": program.id,
                            "snapshot_date": datetime.date.today(),
                            "total_eligible": random.randint(500, 2000),
                            "total_enrolled": random.randint(300, 1500),
                            "overall_coverage": random.uniform(0.5, 0.9),
                            "gender_ratio": random.uniform(0.85, 1.1),
                            "location_ratio": random.uniform(0.7, 1.0),
                            "disability_ratio": random.uniform(0.6, 0.95),
                        }
                    )
                    snapshot_count += 1

        stats["fairness_analysis_created"] = created_count
        stats["fairness_snapshots_created"] = snapshot_count
        _logger.info("Created %d fairness analysis records and %d snapshots", created_count, snapshot_count)

    def _get_fairness_demo_data(self):
        """Get demo data structure for fairness analysis."""
        return {
            "gender": {
                "overall_coverage": 0.52,
                "disparities": {
                    "female": {"count": 450, "coverage": 0.54, "ratio": 1.04},
                    "male": {"count": 420, "coverage": 0.50, "ratio": 0.96},
                },
            },
            "location": {
                "overall_coverage": 0.52,
                "disparities": {
                    "urban": {"count": 280, "coverage": 0.42, "ratio": 0.81},
                    "rural": {"count": 590, "coverage": 0.58, "ratio": 1.12},
                },
            },
            "disability": {
                "overall_coverage": 0.52,
                "disparities": {
                    "pwd": {"count": 85, "coverage": 0.38, "ratio": 0.73},
                    "non_pwd": {"count": 785, "coverage": 0.54, "ratio": 1.04},
                },
            },
        }

    def _generate_grm_demo(self, stats):
        """Generate GRM demo data if spp_grm_demo module is installed.

        Returns:
            dict: Statistics about generated GRM data, or None if module not installed
        """
        # Check if GRM demo module is installed
        if "spp.grm.demo.generator" not in self.env:
            _logger.info("spp_grm_demo not installed, skipping GRM demo data")
            return None

        try:
            # Create GRM demo generator with appropriate settings
            grm_generator = self.env["spp.grm.demo.generator"].create(
                {
                    "name": "MIS Demo - GRM Tickets",
                    "enroll_demo_stories": True,
                    "generate_volume": self.grm_volume_tickets > 0,
                    "number_of_tickets": self.grm_volume_tickets,
                    "tickets_days_back": 90,
                    "resolved_percentage": 60.0,
                    "escalated_percentage": 15.0,
                    "link_to_beneficiaries": True,
                    "link_to_programs": True,
                    "locale_origin": self.locale_origin.id,
                }
            )

            # Generate tickets
            result = grm_generator.generate_tickets()

            # Count created tickets from the action result
            ticket_count = 0
            if result and result.get("domain"):
                domain = result["domain"]
                for item in domain:
                    if isinstance(item, (list, tuple)) and len(item) == 3:
                        if item[0] == "id" and item[1] == "in":
                            ticket_count = len(item[2])
                            break

            _logger.info("Generated %d GRM tickets via MIS demo", ticket_count)
            return {"tickets": ticket_count}

        except Exception as e:
            _logger.error("Error generating GRM demo data: %s", e, exc_info=True)
            return None

    def _generate_case_demo(self, stats):
        """Generate Case demo data if spp_case_demo module is installed.

        Returns:
            dict: Statistics about generated case data, or None if module not installed
        """
        # Check if Case demo module is installed
        if "spp.case.demo.generator" not in self.env:
            _logger.info("spp_case_demo not installed, skipping Case demo data")
            return None

        try:
            # Create Case demo generator with appropriate settings
            case_generator = self.env["spp.case.demo.generator"].create(
                {
                    "name": "MIS Demo - Cases",
                    "number_of_cases": self.case_volume_count,
                    "cases_days_back": 120,
                    "include_stories": True,
                    "percentage_with_plans": 70,
                    "percentage_with_visits": 60,
                    "percentage_with_notes": 80,
                    "percentage_closed": 40,
                    "link_to_beneficiaries": True,
                }
            )

            # Generate cases
            result = case_generator.generate_cases()

            # Count created cases from the action result
            case_count = 0
            if result and result.get("domain"):
                domain = result["domain"]
                for item in domain:
                    if isinstance(item, (list, tuple)) and len(item) == 3:
                        if item[0] == "id" and item[1] == "in":
                            case_count = len(item[2])
                            break

            _logger.info("Generated %d cases via MIS demo", case_count)
            return {"cases": case_count}

        except Exception as e:
            _logger.error("Error generating Case demo data: %s", e, exc_info=True)
            return None

    def _generate_claim169_demo(self, stats):
        """Generate Claim 169 demo data: signing key, issuer config, and credentials.

        Creates:
        1. A default key provider (if none exists)
        2. An Ed25519 asymmetric key for signing
        3. An issuer configuration
        4. Optionally, credentials for demo story personas

        Returns:
            dict: Statistics about generated data
        """
        result = {
            "signing_key_created": False,
            "issuer_created": False,
            "credentials_created": 0,
        }

        try:
            # Step 1: Ensure default key provider exists
            ProviderRegistry = self.env["spp.key.provider.registry"].sudo()
            default_provider = ProviderRegistry.search([("is_default", "=", True)], limit=1)
            if not default_provider:
                default_provider = ProviderRegistry.create(
                    {
                        "name": "Demo Key Provider",
                        "provider_type": "database",
                        "is_default": True,
                    }
                )
                _logger.info("[spp.mis.demo] Created default key provider")

            # Step 2: Create Ed25519 signing key (if not exists)
            AsymmetricKey = self.env["spp.asymmetric.key"].sudo()
            signing_key = AsymmetricKey.search(
                [("name", "=", "Demo Claim 169 Signing Key")],
                limit=1,
            )
            if not signing_key:
                signing_key = AsymmetricKey.create(
                    {
                        "name": "Demo Claim 169 Signing Key",
                        "key_type": "ed25519",
                        "storage_mode": "local",
                    }
                )
                signing_key.generate_key_pair()
                result["signing_key_created"] = True
                _logger.info("[spp.mis.demo] Created Ed25519 signing key: %s", signing_key.kid)
            else:
                _logger.info("[spp.mis.demo] Using existing signing key: %s", signing_key.kid)

            # Step 3: Create issuer configuration (if not exists)
            IssuerConfig = self.env["spp.claim169.issuer.config"].sudo()
            issuer = IssuerConfig.search(
                [("name", "=", "Demo National ID")],
                limit=1,
            )
            if not issuer:
                issuer = IssuerConfig.create(
                    {
                        "name": "Demo National ID",
                        "issuer_id": "did:openspp:demo:national-id",
                        "signing_key_id": signing_key.id,
                        "default_validity_days": 365,
                        "is_default": True,
                    }
                )
                result["issuer_created"] = True
                _logger.info("[spp.mis.demo] Created issuer config ID=%s", issuer.id)
            else:
                _logger.info("[spp.mis.demo] Using existing issuer config ID=%s", issuer.id)

            # Step 4: Generate credentials for demo story personas
            if self.generate_credentials_for_stories:
                credentials_created = self._generate_story_credentials(issuer, stats)
                result["credentials_created"] = credentials_created

            stats["claim169_signing_key_created"] = result["signing_key_created"]
            stats["claim169_issuer_created"] = result["issuer_created"]
            stats["claim169_credentials_created"] = result["credentials_created"]

            return result

        except Exception as e:
            _logger.error("Error generating Claim 169 demo data: %s", e, exc_info=True)
            return None

    def _generate_story_credentials(self, issuer, stats):
        """Generate QR credentials for demo story personas.

        Args:
            issuer: The issuer configuration to use
            stats: Statistics dict to update

        Returns:
            int: Number of credentials created
        """
        try:
            from odoo.addons.spp_demo.models import demo_stories

            locale = self.env.context.get("demo_locale")
            stories = demo_stories.get_localized_stories(locale)
            story_names = [s["name"] for s in stories]

            # Find story partners
            partners = self.env["res.partner"].search(
                [
                    ("name", "in", story_names),
                    ("is_registrant", "=", True),
                ]
            )

            if not partners:
                _logger.warning("[spp.mis.demo] No demo story partners found for credentials")
                return 0

            Credential = self.env["spp.claim169.credential"].sudo()
            credentials_created = 0

            for partner in partners:
                # Check if credential already exists
                existing = Credential.search(
                    [
                        ("partner_id", "=", partner.id),
                        ("status", "=", "active"),
                    ],
                    limit=1,
                )
                if existing:
                    _logger.debug(
                        "[spp.mis.demo] Credential already exists for partner ID=%s",
                        partner.id,
                    )
                    continue

                # Create credential
                validity_days = issuer.default_validity_days
                now = datetime.datetime.now()
                expires_at = now + datetime.timedelta(days=validity_days)

                credential = Credential.create(
                    {
                        "partner_id": partner.id,
                        "issuer_config_id": issuer.id,
                        "issued_at": now,
                        "expires_at": expires_at,
                    }
                )

                # Generate the CWT and QR code
                credential.generate_credential()
                credentials_created += 1
                _logger.debug(
                    "[spp.mis.demo] Generated credential for partner ID=%s: %s",
                    partner.id,
                    credential.name,
                )

            _logger.info(
                "[spp.mis.demo] Generated %d credentials for demo stories",
                credentials_created,
            )
            return credentials_created

        except Exception as e:
            _logger.error("Error generating story credentials: %s", e, exc_info=True)
            return 0

    def _show_success_notification(self, stats):
        """Show success notification with detailed summary."""
        message_parts = [_("Demo data generation completed!"), ""]

        # Stories (auto-generated)
        if stats.get("stories_created", 0) > 0:
            message_parts.append(_("Stories: %(count)s registrants auto-created", count=stats["stories_created"]))

        # Blueprint households (deterministic volume)
        if stats.get("random_groups_created", 0) > 0:
            message_parts.append(
                _(
                    "Blueprint Households: %(groups)s households, %(individuals)s members created",
                    groups=stats["random_groups_created"],
                    individuals=stats["random_individuals_created"],
                )
            )

        # Programs
        if self.create_demo_programs:
            message_parts.append(
                _(
                    "Programs: %(created)s created, %(skipped)s existing",
                    created=stats["programs_created"],
                    skipped=stats["programs_skipped"],
                )
            )

        # Enrollments
        if self.enroll_demo_stories or self.generate_volume:
            message_parts.append(
                _(
                    "Enrollments: %(created)s created, %(skipped)s skipped",
                    created=stats["enrollments_created"],
                    skipped=stats["enrollments_skipped"],
                )
            )

        # Payments
        if self.create_story_payments and stats["payments_created"] > 0:
            message_parts.append(_("Payments: %(count)s created", count=stats["payments_created"]))

        # Payment Batches
        if self.create_story_payments and stats.get("batches_created", 0) > 0:
            message_parts.append(_("Payment Batches: %(count)s created", count=stats["batches_created"]))

        # Cycles
        if self.create_cycles:
            cycle_msg = _("Cycles: %(count)s created", count=stats["cycles_created"])
            if stats.get("cycle_members_created"):
                cycle_msg += _(
                    " (%(members)s beneficiaries, %(ents)s entitlements)",
                    members=stats["cycle_members_created"],
                    ents=stats.get("entitlements_created", 0),
                )
            message_parts.append(cycle_msg)

        # Events
        if self.create_event_data and stats["events_created"] > 0:
            message_parts.append(_("Events: %(count)s created", count=stats["events_created"]))

        # Change Requests
        if self.create_change_requests and stats["change_requests_created"] > 0:
            message_parts.append(_("Change Requests: %(count)s created", count=stats["change_requests_created"]))

        # Fairness Analysis
        if self.create_fairness_analysis and stats.get("fairness_analysis_created", 0) > 0:
            message_parts.append(
                _("Fairness Analysis: %(count)s records created", count=stats["fairness_analysis_created"])
            )

        # GRM Tickets
        if self.generate_grm_demo and stats.get("grm_tickets_created", 0) > 0:
            message_parts.append(_("GRM Tickets: %(count)s created", count=stats["grm_tickets_created"]))

        # Cases
        if self.generate_case_demo and stats.get("cases_created", 0) > 0:
            message_parts.append(_("Cases: %(count)s created", count=stats["cases_created"]))

        # Claim 169 Credentials
        if self.generate_claim169_demo:
            if stats.get("claim169_skipped"):
                message_parts.append(
                    _("QR Credentials: skipped (%(reason)s)", reason=stats.get("claim169_skip_reason", "unknown"))
                )
            else:
                claim169_parts = []
                if stats.get("claim169_signing_key_created"):
                    claim169_parts.append(_("signing key"))
                if stats.get("claim169_issuer_created"):
                    claim169_parts.append(_("issuer config"))
                if stats.get("claim169_credentials_created", 0) > 0:
                    claim169_parts.append(_("%(count)s credentials", count=stats["claim169_credentials_created"]))
                if claim169_parts:
                    message_parts.append(_("QR Credentials: %s created") % ", ".join(claim169_parts))

        # Geographic Data
        self._append_geographic_summary(stats, message_parts)

        # Warnings
        if stats["missing_registrants"]:
            message_parts.append("")
            message_parts.append(
                _("Warning: Missing registrants: %(names)s", names=", ".join(stats["missing_registrants"]))
            )
            message_parts.append(_("Run 'Generate Stories' in spp_demo first."))

        message = "\n".join(message_parts)

        notification_type = "warning" if stats["missing_registrants"] else "success"

        # Commit transaction to ensure data persists (important for shell/script usage)
        # Skip commit in test mode to avoid breaking test isolation
        if not config["test_enable"]:
            self.env.cr.commit()

        # Redirect to Programs list after loading demo data
        action = self.env.ref("spp_programs.action_program_list", raise_if_not_found=False)
        if action:
            result = action.sudo().read()[0]
            result["target"] = "main"
            return result

        # Fallback to notification if programs action not found
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("MIS Demo Data Generated"),
                "message": message,
                "sticky": bool(stats["missing_registrants"]),
                "type": notification_type,
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def _append_geographic_summary(self, stats, message_parts):
        """Append geographic data summary to notification message parts."""
        if not self.load_geographic_data:
            return
        geo_parts = []
        if stats.get("areas_loaded", 0) > 0:
            geo_parts.append(_("%(count)s areas with GIS shapes", count=stats["areas_loaded"]))
        if stats.get("areas_assigned", 0) > 0:
            geo_parts.append(_("%(count)s groups assigned to areas", count=stats["areas_assigned"]))
        if stats.get("coordinates_generated", 0) > 0:
            geo_parts.append(_("%(count)s registrants with GPS coordinates", count=stats["coordinates_generated"]))
        if geo_parts:
            message_parts.append(_("Geographic Data: %s") % ", ".join(geo_parts))

    def _load_geographic_data(self, stats):
        """Load geographic area data with GIS shapes.

        Uses the DemoAreaLoader from spp_demo to load country-specific
        area hierarchies with GIS polygon data for spatial queries.

        Args:
            stats: Statistics dictionary to update

        Returns:
            dict: Result with counts of loaded data
        """
        try:
            loader = self.env["spp.demo.area.loader"]
            result = loader.load_country_areas(self.country_code, load_shapes=True)
            _logger.info(
                "[spp.mis.demo] Loaded geographic data for %s: %d areas with GIS shapes",
                self.country_code,
                result.get("shapes_loaded", 0),
            )
            return result
        except Exception as e:
            _logger.warning("[spp.mis.demo] Failed to load geographic data: %s", e)
            return None

    # Locale-aware area assignments for story registrants.
    # Each story gets a specific area per country for consistent demo scenarios.
    # Keys: story_id -> {locale: area_xmlid}
    STORY_AREA_MAP = {
        "juan_dela_cruz": {
            "fil_PH": "spp_demo.area_phl_calamba",
            "fr_TG": "spp_demo.area_tgo_lome_tokoin",
            "si_LK": "spp_demo.area_lka_moratuwa",
        },
        "maria_santos": {
            "fil_PH": "spp_demo.area_phl_santa_rosa",
            "fr_TG": "spp_demo.area_tgo_aflao",
            "si_LK": "spp_demo.area_lka_kolonnawa",
        },
        "jose_reyes_multigenerational": {
            "fil_PH": "spp_demo.area_phl_san_pablo",
            "fr_TG": "spp_demo.area_tgo_kpalime",
            "si_LK": "spp_demo.area_lka_kandy_ds",
        },
        "ibrahim_hassan": {
            "fil_PH": "spp_demo.area_phl_antipolo",
            "fr_TG": "spp_demo.area_tgo_sokode",
            "si_LK": "spp_demo.area_lka_galle_ds",
        },
        "david_sofia_martinez": {
            "fil_PH": "spp_demo.area_phl_makati",
            "fr_TG": "spp_demo.area_tgo_lome",
            "si_LK": "spp_demo.area_lka_dehiwala",
        },
        "rosa_garcia": {
            "fil_PH": "spp_demo.area_phl_quezon_city",
            "fr_TG": "spp_demo.area_tgo_lome_be",
            "si_LK": "spp_demo.area_lka_colombo_fort",
        },
        "mary_johnson": {
            "fil_PH": "spp_demo.area_phl_pasig",
            "fr_TG": "spp_demo.area_tgo_lome_nyekonakpoe",
            "si_LK": "spp_demo.area_lka_colombo_pettah",
        },
        "ahmed_said": {
            "fil_PH": "spp_demo.area_phl_taguig",
            "fr_TG": "spp_demo.area_tgo_lome_adidogome",
            "si_LK": "spp_demo.area_lka_dehiwala_gn",
        },
        "nguyen_extended_family": {
            "fil_PH": "spp_demo.area_phl_bacoor",
            "fr_TG": "spp_demo.area_tgo_baguida_centre",
            "si_LK": "spp_demo.area_lka_hikkaduwa",
        },
        "amina_osman_household": {
            "fil_PH": "spp_demo.area_phl_manila",
            "fr_TG": "spp_demo.area_tgo_kpalime_centre",
            "si_LK": "spp_demo.area_lka_mount_lavinia_gn",
        },
        "carlos_elena_morales": {
            "fil_PH": "spp_demo.area_phl_dasmarinas",
            "fr_TG": "spp_demo.area_tgo_kpalime_tove",
            "si_LK": "spp_demo.area_lka_galle_fort",
        },
        "chen_large_family": {
            "fil_PH": "spp_demo.area_phl_qc_commonwealth",
            "fr_TG": "spp_demo.area_tgo_zio",
            "si_LK": "spp_demo.area_lka_gampaha",
        },
        "grace_okonkwo": {
            "fil_PH": "spp_demo.area_phl_makati_poblacion",
            "fr_TG": "spp_demo.area_tgo_ogou",
            "si_LK": "spp_demo.area_lka_kalutara",
        },
        "luis_fernandez": {
            "fil_PH": "spp_demo.area_phl_calamba_real",
            "fr_TG": "spp_demo.area_tgo_lacs",
            "si_LK": "spp_demo.area_lka_matara",
        },
    }

    def _assign_registrant_areas(self, stats):
        """Assign geographic areas to registrants.

        Strategy:
        1. Assign specific areas to story registrants (locale-aware)
        2. Assign random municipalities to remaining groups
        3. Individual members inherit area_id from their group

        Args:
            stats: Statistics dictionary to update
        """
        Area = self.env["spp.area"]
        Partner = self.env["res.partner"]

        # Get all level 3 areas (municipalities) that have geo_polygon data
        municipalities = Area.search([("area_level", "=", 3), ("geo_polygon", "!=", False)])

        if not municipalities:
            # Fall back to any level 3 areas even without polygons
            municipalities = Area.search([("area_level", "=", 3)])

        if not municipalities:
            _logger.warning("[spp.mis.demo] No municipalities found, skipping area assignment")
            stats["areas_assigned"] = 0
            return

        _logger.info("[spp.mis.demo] Found %d municipalities for area assignment", len(municipalities))

        # Step 1: Assign specific areas to story registrants
        locale = self.env.context.get("demo_locale", "fil_PH")
        story_assigned = self._assign_story_areas(locale)

        # Step 2: Get all groups (households) without area_id
        groups = Partner.search(
            [
                ("is_group", "=", True),
                ("is_registrant", "=", True),
                ("area_id", "=", False),
            ]
        )

        if not groups:
            _logger.info("[spp.mis.demo] All groups already have areas assigned")
            stats["areas_assigned"] = story_assigned
            return

        # Assign random municipality to each remaining group
        groups_assigned = story_assigned
        for group in groups:
            municipality = random.choice(municipalities)
            group.write({"area_id": municipality.id})
            groups_assigned += 1

            # Members inherit area from group
            members = Partner.search([("group_membership_ids.group", "=", group.id)])
            if members:
                members.write({"area_id": municipality.id})

        # Also assign areas to standalone individuals without area_id
        individuals = Partner.search(
            [
                ("is_group", "=", False),
                ("is_registrant", "=", True),
                ("area_id", "=", False),
                ("individual_membership_ids", "=", False),
            ]
        )
        for ind in individuals:
            municipality = random.choice(municipalities)
            ind.write({"area_id": municipality.id})

        stats["areas_assigned"] = groups_assigned
        _logger.info("[spp.mis.demo] Assigned areas to %d groups (%d story-specific)", groups_assigned, story_assigned)

    def _assign_story_areas(self, locale):
        """Assign locale-specific areas to story registrants.

        Returns:
            int: Number of stories assigned
        """
        assigned = 0

        try:
            from odoo.addons.spp_demo.models import demo_stories

            stories = demo_stories.get_localized_stories(locale)
        except ImportError:
            return 0

        Partner = self.env["res.partner"]

        for story in stories:
            story_id = story["id"]
            story_name = story["name"]

            area_map = self.STORY_AREA_MAP.get(story_id, {})
            area_xmlid = area_map.get(locale)
            if not area_xmlid:
                continue

            area = self.env.ref(area_xmlid, raise_if_not_found=False)
            if not area:
                _logger.warning("[spp.mis.demo] Area %s not found for story %s", area_xmlid, story_id)
                continue

            # Find the registrant
            registrant = Partner.search(
                [("name", "=", story_name), ("is_registrant", "=", True)],
                limit=1,
            )
            if not registrant:
                continue

            # Assign area
            registrant.write({"area_id": area.id})
            assigned += 1

            # If group, also assign to members
            if registrant.is_group:
                members = Partner.search([("group_membership_ids.group", "=", registrant.id)])
                if members:
                    members.write({"area_id": area.id})

            _logger.debug(
                "[spp.mis.demo] Assigned %s to story %s (%s)",
                area.draft_name,
                story_name,
                story_id,
            )

        _logger.info("[spp.mis.demo] Assigned areas to %d story registrants", assigned)
        return assigned

    def _generate_coordinates(self, stats):
        """Generate GPS coordinates for registrants.

        For each registrant with an area_id that has geo_polygon data,
        generates a random point within the area polygon and sets
        the coordinates field (if spp_registrant_gis is installed).

        Uses shapely to generate random points within polygons.

        Args:
            stats: Statistics dictionary to update
        """
        # Check if spp_registrant_gis is installed
        if "coordinates" not in self.env["res.partner"]._fields:
            _logger.info("[spp.mis.demo] spp_registrant_gis not installed, skipping coordinate generation")
            stats["coordinates_generated"] = 0
            return

        try:
            from shapely.geometry import shape
        except ImportError:
            _logger.warning("[spp.mis.demo] shapely not available, skipping coordinate generation")
            stats["coordinates_generated"] = 0
            return

        Partner = self.env["res.partner"]
        Area = self.env["spp.area"]

        # Get all registrants with an area_id
        registrants = Partner.search(
            [
                ("is_registrant", "=", True),
                ("area_id", "!=", False),
            ]
        )

        if not registrants:
            _logger.warning("[spp.mis.demo] No registrants with areas found")
            stats["coordinates_generated"] = 0
            return

        _logger.info("[spp.mis.demo] Generating coordinates for %d registrants", len(registrants))

        coordinates_generated = 0

        # Group registrants by area to minimize queries
        registrants_by_area = {}
        for registrant in registrants:
            area_id = registrant.area_id.id
            if area_id not in registrants_by_area:
                registrants_by_area[area_id] = []
            registrants_by_area[area_id].append(registrant)

        # Process each area
        for area_id, area_registrants in registrants_by_area.items():
            area = Area.browse(area_id)

            # Skip if no polygon data
            if not area.geo_polygon:
                continue

            try:
                # The ORM returns geo_polygon as a Shapely geometry object
                polygon = area.geo_polygon

                # Generate random points for all registrants in this area
                minx, miny, maxx, maxy = polygon.bounds

                for registrant in area_registrants:
                    # Generate random point within bounding box, retry if outside polygon
                    max_attempts = 10
                    for _attempt in range(max_attempts):
                        point_x = random.uniform(minx, maxx)
                        point_y = random.uniform(miny, maxy)
                        point = shape({"type": "Point", "coordinates": [point_x, point_y]})

                        if polygon.contains(point):
                            # Set the coordinates field (GeoPointField expects WKB)
                            registrant.write(
                                {
                                    "coordinates": f"POINT({point_x} {point_y})",
                                }
                            )
                            coordinates_generated += 1
                            break
                    else:
                        # If we couldn't find a point inside after max_attempts, use centroid
                        centroid = polygon.centroid
                        registrant.write(
                            {
                                "coordinates": f"POINT({centroid.x} {centroid.y})",
                            }
                        )
                        coordinates_generated += 1

            except Exception as e:
                _logger.warning("[spp.mis.demo] Failed to generate coordinates for area %s: %s", area.id, e)
                continue

        stats["coordinates_generated"] = coordinates_generated
        _logger.info("[spp.mis.demo] Generated coordinates for %d registrants", coordinates_generated)

    def _refresh_gis_reports(self, stats):
        """Refresh all active GIS reports so map data is available immediately."""
        GISReport = self.env["spp.gis.report"]
        reports = GISReport.search([("active", "=", True)])

        if not reports:
            _logger.info("[spp.mis.demo] No active GIS reports found to refresh")
            stats["gis_reports_refreshed"] = 0
            return

        refreshed = 0
        for report in reports:
            try:
                report._refresh_data()
                refreshed += 1
                _logger.info("[spp.mis.demo] Refreshed GIS report: %s", report.id)
            except Exception:
                _logger.exception("[spp.mis.demo] Failed to refresh GIS report: %s", report.id)

        stats["gis_reports_refreshed"] = refreshed
        _logger.info("[spp.mis.demo] Refreshed %d GIS reports", refreshed)

    def _create_prism_api_client(self, stats):
        """Create an API client with known credentials for PRISM frontend integration.

        Uses fixed client_id='prism' and client_secret='prism-secret' so the
        docker-compose PRISM service can authenticate without manual configuration.
        Skips creation if a client with client_id='prism' already exists.
        """
        ApiClient = self.env["spp.api.client"]
        existing = ApiClient.search([("client_id", "=", "prism")], limit=1)
        if existing:
            _logger.info("[spp.mis.demo] PRISM API client already exists, skipping")
            stats["prism_api_client"] = "already_exists"
            return

        client = ApiClient.create(
            {
                "name": "PRISM Frontend",
                "description": "API client for PRISM crisis data visualization frontend. "
                "Created by demo generator with known credentials for docker-compose integration.",
                "client_id": "prism",
                "client_secret": "prism-secret",
                "partner_id": self.env.ref("base.main_partner").id,
                "organization_type_id": self.env.ref("spp_consent.org_type_government").id,
            }
        )

        # Create GIS scopes
        ScopeModel = self.env["spp.api.client.scope"]
        for resource, action in [("gis", "read"), ("gis", "all")]:
            ScopeModel.create(
                {
                    "client_id": client.id,
                    "resource": resource,
                    "action": action,
                }
            )

        _logger.info("[spp.mis.demo] Created PRISM API client (client_id=prism) with GIS scopes")
        stats["prism_api_client"] = "created"


class SPPMISDemoWizard(models.TransientModel):
    """Wizard interface for MIS Demo Generator."""

    _name = "spp.mis.demo.wizard"
    _description = "MIS Demo Data Wizard"
    _inherit = "spp.mis.demo.generator"

    mis_demo_loaded = fields.Boolean(
        related="company_id.mis_demo_loaded",
        string="Demo Already Loaded",
    )
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
    )
    has_grm_demo = fields.Boolean(compute="_compute_has_optional_demos")
    has_case_demo = fields.Boolean(compute="_compute_has_optional_demos")

    def _compute_has_optional_demos(self):
        installed_names = set(
            self.env["ir.module.module"]
            .search(
                [
                    ("name", "in", ["spp_grm_demo", "spp_case_demo"]),
                    ("state", "=", "installed"),
                ]
            )
            .mapped("name")
        )
        for rec in self:
            rec.has_grm_demo = "spp_grm_demo" in installed_names
            rec.has_case_demo = "spp_case_demo" in installed_names

    def action_generate_demo_data(self):
        """Action to generate demo data from wizard."""
        return self.action_generate()
