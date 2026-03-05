# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Case Management Demo Data Generator.

Generates realistic case management demo data including:
- Cases with full lifecycle progression
- Intervention plans and interventions
- Case visits and notes
- Service referrals
"""

import logging
import random
from datetime import timedelta

from faker import Faker

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCaseDemoGenerator(models.TransientModel):
    _name = "spp.case.demo.generator"
    _description = "Case Management Demo Data Generator"

    name = fields.Char(default="Case Management Demo Data", required=True)
    number_of_cases = fields.Integer(string="Number of Cases", default=25, required=True)
    include_stories = fields.Boolean(
        string="Include Demo Stories",
        default=True,
        help="Generate fixed demo stories with predictable names",
    )
    cases_days_back = fields.Integer(
        string="Days Back",
        default=120,
        required=True,
        help="Generate cases within the last N days",
    )

    # Distribution settings
    percentage_with_plans = fields.Float(
        string="% with Plans",
        default=70.0,
        help="Percentage of cases with intervention plans",
    )
    percentage_with_visits = fields.Float(
        string="% with Visits",
        default=60.0,
        help="Percentage of cases with home visits",
    )
    percentage_with_notes = fields.Float(
        string="% with Notes",
        default=80.0,
        help="Percentage of cases with progress notes",
    )
    percentage_closed = fields.Float(
        string="% Closed",
        default=40.0,
        help="Percentage of cases that are closed",
    )

    # Linking options
    link_to_beneficiaries = fields.Boolean(
        string="Link to Beneficiaries",
        default=True,
        help="Link cases to existing registrants",
    )

    locale_origin = fields.Many2one(
        "res.country",
        default=lambda self: self.env.user.company_id.country_id or self.env.ref("base.us"),
        help="Country for Faker locale",
    )
    locale_origin_faker_locale = fields.Char(
        string="Faker Locale",
        related="locale_origin.faker_locale",
        readonly=True,
    )

    @api.constrains("number_of_cases")
    def _check_number_of_cases(self):
        for rec in self:
            if rec.number_of_cases < 1:
                raise UserError(_("Number of cases must be at least 1"))
            if rec.number_of_cases > 5000:
                raise UserError(_("Number of cases cannot exceed 5,000"))

    def generate_cases(self):
        """Main method to generate case management demo data."""
        self.ensure_one()

        # Initialize Faker
        faker_locale = self.locale_origin_faker_locale or "en_US"
        fake = Faker(faker_locale)

        _logger.info("Starting case generation: %d cases over %d days", self.number_of_cases, self.cases_days_back)

        # Get available beneficiaries
        beneficiaries = self._get_available_beneficiaries() if self.link_to_beneficiaries else []

        if self.link_to_beneficiaries and not beneficiaries:
            raise UserError(_("No beneficiaries (registrants) found. Please create some registrants first."))

        created_cases = self.env["spp.case"]

        # Generate fixed demo stories first
        if self.include_stories:
            story_cases = self._generate_demo_stories(fake, beneficiaries)
            created_cases |= story_cases
            _logger.info("Generated %d demo story cases", len(story_cases))

        # Generate random volume cases
        remaining = self.number_of_cases - len(created_cases)
        if remaining > 0:
            for i in range(remaining):
                try:
                    case = self._create_random_case(fake, beneficiaries)
                    if case:
                        created_cases |= case

                    if (i + 1) % 10 == 0:
                        _logger.info("Generated %d/%d random cases", i + 1, remaining)

                except Exception as e:
                    _logger.error("Error generating case %d: %s", i + 1, e, exc_info=True)
                    continue

        _logger.info("Successfully generated %d cases", len(created_cases))

        # Return action to view generated cases
        return {
            "type": "ir.actions.act_window",
            "name": "Generated Cases",
            "res_model": "spp.case",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", created_cases.ids)],
            "context": {"search_default_group_by_stage": 1},
        }

    def _generate_demo_stories(self, fake, beneficiaries):
        """Generate cases from fixed demo stories."""
        from . import case_demo_stories

        cases = self.env["spp.case"]
        stories = case_demo_stories.get_main_case_stories()

        for story in stories:
            try:
                case = self._create_case_from_story(story, fake, beneficiaries)
                if case:
                    cases |= case
                    _logger.info("Created demo story case: %s", story["case_name"])
            except Exception as e:
                _logger.error("Error creating story '%s': %s", story.get("case_name", "unknown"), e)

        return cases

    def _create_case_from_story(self, story, fake, beneficiaries):
        """Create a case from a demo story definition."""
        case_profile = story.get("case_profile", {})
        journey = story.get("journey", [])

        # Find opened date (formerly intake)
        intake_action = next((a for a in journey if a.get("action") == "intake"), None)
        intake_days_back = intake_action.get("days_back", 90) if intake_action else 90
        opened_date = fields.Date.today() - timedelta(days=intake_days_back)

        # Get or create case type
        case_type = self._get_or_create_case_type(case_profile.get("case_type", "General Support"))

        # Get stage based on journey
        stage = self._determine_stage_from_journey(journey)

        # Find or create client
        client_info = story.get("client", {})
        client = self._find_or_create_client(client_info, beneficiaries, fake)

        # Create case
        vals = {
            "case_type_id": case_type.id if case_type else False,
            "stage_id": stage.id if stage else False,
            "partner_id": client.id if client else False,
            "presenting_issue": case_profile.get("presenting_issue", "Demo case"),
            "intake_source": case_profile.get("intake_source", "referral"),
            "opened_date": opened_date,
            "priority": case_profile.get("priority", "medium"),
            "intensity_level": case_profile.get("intensity_level", "1"),
            "case_worker_id": self.env.user.id,
        }

        case = self.env["spp.case"].sudo().create(vals)
        # Backdate creation
        self.env.cr.execute(
            "UPDATE spp_case SET create_date = %s WHERE id = %s",
            (opened_date, case.id),
        )

        # Process journey
        self._process_case_journey(case, journey, fake)

        return case

    def _process_case_journey(self, case, journey, fake):
        """Process journey steps for a case."""
        Plan = self.env["spp.case.intervention.plan"]
        Intervention = self.env["spp.case.intervention"]
        Visit = self.env["spp.case.visit"]
        Note = self.env["spp.case.note"]
        Referral = self.env["spp.case.referral"]

        current_plan = None

        for step in journey:
            action = step.get("action")
            days_back = step.get("days_back", 0)
            action_date = fields.Date.today() - timedelta(days=days_back)

            if action == "create_plan":
                current_plan = Plan.sudo().create(
                    {
                        "case_id": case.id,
                        "name": step.get("plan_name", f"Plan for {case.partner_id.name}"),
                        "is_current": True,
                        "state": "active",
                        "start_date": action_date,
                        "goals": step.get("goals", fake.paragraph()),
                    }
                )

            elif action == "add_intervention" and current_plan:
                Intervention.sudo().create(
                    {
                        "plan_id": current_plan.id,
                        "name": step.get("intervention", "Intervention"),
                        "description": fake.sentence(),
                        "target_date": action_date + timedelta(days=random.randint(7, 30)),
                        "state": "planned",
                    }
                )

            elif action == "complete_intervention" and current_plan:
                intervention = Intervention.search(
                    [
                        ("plan_id", "=", current_plan.id),
                        ("name", "=", step.get("intervention")),
                    ],
                    limit=1,
                )
                if intervention:
                    intervention.sudo().write({"state": "completed"})
            elif action in ("home_visit", "office_visit", "final_visit"):
                visit_type = "home" if action != "office_visit" else "office"
                Visit.sudo().create(
                    {
                        "case_id": case.id,
                        "visit_type": visit_type,
                        "purpose": step.get("purpose", "Check-in visit"),
                        "visit_date": fields.Datetime.to_datetime(action_date),
                        "notes": step.get("notes", fake.paragraph()),
                    }
                )

            elif action == "progress_note":
                Note.sudo().create(
                    {
                        "case_id": case.id,
                        "note_type": "progress",
                        "content": step.get("note", fake.paragraph()),
                        "note_date": fields.Datetime.to_datetime(action_date),
                    }
                )

            elif action in ("assessment", "emergency_assessment", "safety_assessment"):
                Note.sudo().create(
                    {
                        "case_id": case.id,
                        "note_type": "assessment",
                        "content": step.get(
                            "notes", f"{action.replace('_', ' ').title()} completed. {fake.paragraph()}"
                        ),
                        "note_date": fields.Datetime.to_datetime(action_date),
                    }
                )

            elif action == "add_referral":
                service = self._get_or_create_service(step.get("service", "External Service"))
                if service:
                    Referral.sudo().create(
                        {
                            "case_id": case.id,
                            "service_id": service.id,
                            "referral_reason": step.get("reason", "Service needed"),
                            "referral_date": action_date,
                            "state": "pending",
                        }
                    )

            elif action == "close_case":
                closure_stage = self.env["spp.case.stage"].search(
                    [
                        ("phase", "=", "closure"),
                    ],
                    limit=1,
                )
                if closure_stage:
                    case.sudo().write(
                        {
                            "stage_id": closure_stage.id,
                            "actual_closure_date": action_date,
                        }
                    )
                if current_plan:
                    current_plan.sudo().write({"state": "completed"})

    def _create_random_case(self, fake, beneficiaries):
        """Create a random case with realistic data."""
        # Random date within range
        days_back = random.randint(0, self.cases_days_back)
        opened_date = fields.Date.today() - timedelta(days=days_back)

        # Get random case type and stage
        case_type = self._get_random_case_type()
        stage = self._get_random_stage()

        # Get random beneficiary
        partner = random.choice(beneficiaries) if beneficiaries else None

        presenting_issues = [
            "Family experiencing financial hardship",
            "Need for housing assistance",
            "Health support coordination needed",
            "Child welfare concerns",
            "Employment assistance requested",
            "Food insecurity issues",
            "Elder care coordination",
            "Disability support services needed",
        ]

        vals = {
            "case_type_id": case_type.id if case_type else False,
            "stage_id": stage.id if stage else False,
            "partner_id": partner.id if partner else False,
            "presenting_issue": random.choice(presenting_issues),
            "intake_source": random.choice(["walk_in", "referral", "outreach", "grm", "program", "other"]),
            "opened_date": opened_date,
            "priority": random.choice(["low", "medium", "high", "urgent"]),
            "intensity_level": random.choice(["1", "2", "3"]),
            "case_worker_id": self.env.user.id,
        }

        case = self.env["spp.case"].sudo().create(vals)
        # Backdate creation
        self.env.cr.execute(
            "UPDATE spp_case SET create_date = %s WHERE id = %s",
            (opened_date, case.id),
        )

        # Add related data based on percentages
        if random.random() < (self.percentage_with_plans / 100):
            self._add_random_plan(case, fake, opened_date)

        if random.random() < (self.percentage_with_visits / 100):
            self._add_random_visits(case, fake, opened_date)

        if random.random() < (self.percentage_with_notes / 100):
            self._add_random_notes(case, fake, opened_date)

        # Close case if needed
        if random.random() < (self.percentage_closed / 100):
            self._close_random_case(case, fake, opened_date)

        return case

    def _add_random_plan(self, case, fake, intake_date):
        """Add random intervention plan to case."""
        Plan = self.env["spp.case.intervention.plan"]
        Intervention = self.env["spp.case.intervention"]

        plan = Plan.sudo().create(
            {
                "case_id": case.id,
                "name": f"Support Plan - {case.partner_id.name or 'Client'}",
                "is_current": True,
                "state": random.choice(["draft", "active", "completed"]),
                "start_date": intake_date + timedelta(days=random.randint(1, 7)),
                "goals": fake.paragraph(),
            }
        )

        # Add 2-4 interventions
        intervention_names = [
            "Needs assessment",
            "Resource connection",
            "Counseling referral",
            "Document assistance",
            "Service coordination",
            "Follow-up support",
        ]

        for _i in range(random.randint(2, 4)):
            Intervention.sudo().create(
                {
                    "plan_id": plan.id,
                    "name": random.choice(intervention_names),
                    "description": fake.sentence(),
                    "target_date": intake_date + timedelta(days=random.randint(7, 60)),
                    "state": random.choice(["planned", "in_progress", "completed"]),
                }
            )

    def _add_random_visits(self, case, fake, intake_date):
        """Add random visits to case."""
        Visit = self.env["spp.case.visit"]

        for _i in range(random.randint(1, 3)):
            visit_date = intake_date + timedelta(days=random.randint(5, 60))
            Visit.sudo().create(
                {
                    "case_id": case.id,
                    "visit_type": random.choice(["home", "office", "phone", "virtual"]),
                    "purpose": fake.sentence(nb_words=5),
                    "visit_date": fields.Datetime.to_datetime(visit_date),
                    "notes": fake.paragraph() if random.random() < 0.7 else False,
                }
            )

    def _add_random_notes(self, case, fake, intake_date):
        """Add random notes to case."""
        Note = self.env["spp.case.note"]

        for _i in range(random.randint(1, 4)):
            note_date = intake_date + timedelta(days=random.randint(1, 60))
            Note.sudo().create(
                {
                    "case_id": case.id,
                    "note_type": random.choice(["progress", "assessment", "general", "supervision"]),
                    "content": fake.paragraph(nb_sentences=random.randint(2, 5)),
                    "note_date": fields.Datetime.to_datetime(note_date),
                }
            )

    def _close_random_case(self, case, fake, intake_date):
        """Close a case with random outcome."""
        closure_stage = self.env["spp.case.stage"].search(
            [
                ("phase", "=", "closure"),
            ],
            limit=1,
        )

        if closure_stage:
            closure_date = intake_date + timedelta(days=random.randint(30, 90))
            case.sudo().write(
                {
                    "stage_id": closure_stage.id,
                    "actual_closure_date": closure_date,
                }
            )

    def _get_available_beneficiaries(self):
        """Get list of available beneficiaries (registrants)."""
        return self.env["res.partner"].search([("is_registrant", "=", True)], limit=1000)

    def _find_or_create_client(self, client_info, beneficiaries, fake):
        """Find existing client or return random beneficiary."""
        name = client_info.get("name")
        if name:
            existing = self.env["res.partner"].search(
                [
                    ("name", "=", name),
                    ("is_registrant", "=", True),
                ],
                limit=1,
            )
            if existing:
                return existing

        # Return random beneficiary
        return random.choice(beneficiaries) if beneficiaries else None

    def _get_or_create_case_type(self, type_name):
        """Get or create a case type."""
        CaseType = self.env["spp.case.type"]
        case_type = CaseType.search([("name", "=", type_name)], limit=1)
        if not case_type:
            case_type = CaseType.sudo().create(
                {
                    "name": type_name,
                    "code": type_name.upper().replace(" ", "_")[:10],
                }
            )
        return case_type

    def _get_random_case_type(self):
        """Get a random case type."""
        case_types = self.env["spp.case.type"].search([])
        return random.choice(case_types) if case_types else None

    def _get_random_stage(self):
        """Get a random case stage."""
        stages = self.env["spp.case.stage"].search([])
        if stages:
            # Weight toward middle stages
            idx = min(int(random.triangular(0, len(stages) - 1, len(stages) // 3)), len(stages) - 1)
            return stages[idx]
        return None

    def _determine_stage_from_journey(self, journey):
        """Determine appropriate stage based on journey."""
        Stage = self.env["spp.case.stage"]

        # Check if case is closed
        if any(step.get("action") == "close_case" for step in journey):
            return Stage.search([("phase", "=", "closure")], limit=1)

        # Check for monitoring
        if len([s for s in journey if s.get("action") in ("home_visit", "progress_note")]) > 3:
            return Stage.search([("phase", "=", "monitoring")], limit=1)

        # Check for implementation
        if any(step.get("action") == "complete_intervention" for step in journey):
            return Stage.search([("phase", "=", "implementation")], limit=1)

        # Check for planning
        if any(step.get("action") == "create_plan" for step in journey):
            return Stage.search([("phase", "=", "planning")], limit=1)

        # Check for assessment
        if any("assessment" in step.get("action", "") for step in journey):
            return Stage.search([("phase", "=", "assessment")], limit=1)

        # Default to intake
        return Stage.search([("phase", "=", "intake")], limit=1)

    def _get_or_create_service(self, service_name):
        """Get or create a service for referrals."""
        if "spp.service" not in self.env:
            return None

        Service = self.env["spp.service"]
        service = Service.search([("name", "=", service_name)], limit=1)
        if not service:
            service = Service.sudo().create(
                {
                    "name": service_name,
                    "service_type": "external",
                }
            )
        return service
