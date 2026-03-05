# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
import random
from datetime import datetime, timedelta

from faker import Faker

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Story ticket definitions for demo data
# These personas align with spp_mis_demo_v2 and spp_case_demo for cross-module demos
GRM_STORY_TICKETS = {
    "juan_dela_cruz": {
        "tickets": [
            {
                "title": "Payment not received after house fire",
                "description": (
                    "Beneficiary reports missing emergency payment after displacement from house fire. "
                    "Was enrolled in Cash Transfer Program when disaster struck. "
                    "Needs urgent resolution - family currently in temporary shelter."
                ),
                "category": "payment",
                "priority": "high",
                "severity": "high",
                "days_back": 15,
                "program_name": "Cash Transfer Program",
                "escalate_to_case": True,  # Indicates this should create a case
                "resolution": {
                    "decision": "upheld",
                    "notes": [
                        {"text": "Verified displacement status and emergency situation"},
                        {"text": "Expedited emergency payment processing"},
                        {"text": "Escalated to case management for comprehensive support"},
                        {"text": "Payment processed and beneficiary notified"},
                    ],
                },
            }
        ]
    },
    "fatima_al_rahman": {
        "tickets": [
            {
                "title": "How do I qualify for Universal Child Grant?",
                "description": (
                    "Mother of 2 children asking about eligibility for Universal Child Grant. "
                    "Husband works abroad, she manages household alone. "
                    "Wants to understand requirements and application process."
                ),
                "category": "eligibility",
                "priority": "low",
                "days_back": 45,  # Before her case was opened
                "program_name": "Universal Child Grant",
                "escalate_to_case": True,  # Led to case assessment
                "resolution": {
                    "decision": "upheld",
                    "days_to_close": 2,
                    "notes": [
                        {"text": "Provided information about Universal Child Grant eligibility"},
                        {"text": "Beneficiary appears eligible - referred for assessment"},
                        {"text": "Escalated to case management for enrollment support"},
                    ],
                },
            }
        ]
    },
    "ibrahim_hassan": {
        "tickets": [
            {
                "title": "Request for resettlement support",
                "description": (
                    "Displaced farmer from flood-affected coastal village. "
                    "Lost home, crops, and livelihood. Currently in evacuation center. "
                    "Needs assistance with Emergency Relief Fund and permanent resettlement."
                ),
                "category": "service",
                "priority": "medium",
                "severity": "high",
                "days_back": 65,  # Before his case was opened
                "program_name": "Emergency Relief Fund",
                "escalate_to_case": True,
                # No resolution - ticket escalated to case management
            }
        ]
    },
    "ahmed_said": {
        "tickets": [
            {
                "title": "Payment delayed - third occurrence",
                "description": (
                    "Payment for Cash Transfer Program has been delayed again. "
                    "This is the third time in 6 months. "
                    "Suspect issue with bank account or payment processing."
                ),
                "category": "payment",
                "priority": "high",
                "days_back": 20,
                "program_name": "Cash Transfer Program",
                "resolution": {
                    "decision": "upheld",
                    "notes": [
                        {"text": "Verified recurring payment delay pattern"},
                        {"text": "Identified bank account mismatch issue"},
                        {"text": "Payment processed after account correction"},
                    ],
                },
            },
            {
                "title": "Update bank account information",
                "description": ("Need to update bank account to new provider. " "Previous bank closed local branch."),
                "category": "registration",
                "priority": "medium",
                "days_back": 10,
                "resolution": {
                    "decision": "upheld",
                    "notes": [
                        {"text": "Verified identity and account ownership"},
                        {"text": "Bank account information updated in system"},
                    ],
                },
            },
            {
                "title": "Question about next payment schedule",
                "description": "When will the next payment be processed? Need to plan for school expenses.",
                "category": "general",
                "priority": "low",
                "days_back": 3,
                "resolution": {
                    "decision": "upheld",
                    "notes": [
                        {"text": "Provided payment schedule - next payment in 2 weeks"},
                        {"text": "Suggested case management referral for recurring issues"},
                    ],
                },
            },
        ]
    },
    "david_martinez": {
        "tickets": [
            {
                "title": "Disability Support Grant application status",
                "description": (
                    "Inquiry about status of Disability Support Grant application. "
                    "Applied 3 weeks ago for son Miguel who has cerebral palsy. "
                    "Need funds for wheelchair and medical equipment."
                ),
                "category": "eligibility",
                "priority": "medium",
                "days_back": 105,  # Before case was opened
                "program_name": "Disability Support Grant",
                "escalate_to_case": True,
                "resolution": {
                    "decision": "upheld",
                    "days_to_close": 3,
                    "notes": [
                        {"text": "Application in review - additional documentation needed"},
                        {"text": "Referred to case management for comprehensive disability support"},
                        {"text": "Case worker will assist with documentation and equipment referrals"},
                    ],
                },
            }
        ]
    },
    "maria_santos": {
        "tickets": [
            {
                "title": "Graduation from Cash Transfer Program",
                "description": (
                    "Inquiry about graduation process from Cash Transfer Program. "
                    "Has been enrolled for 5 months, income has improved. "
                    "Wants to understand next steps and any continued support available."
                ),
                "category": "general",
                "priority": "low",
                "days_back": 10,
                "program_name": "Cash Transfer Program",
                "resolution": {
                    "decision": "upheld",
                    "days_to_close": 1,
                    "notes": [
                        {"text": "Congratulated on successful program participation"},
                        {"text": "Explained graduation criteria and timeline"},
                        {"text": "Provided information about alumni mentorship program"},
                    ],
                },
            }
        ]
    },
    "rosa_garcia": {
        "tickets": [
            {
                "title": "Food Assistance delivery schedule",
                "description": (
                    "Question about food basket delivery schedule. "
                    "Elderly widow living alone, needs to arrange for someone to receive delivery. "
                    "Also enrolled in Elderly Social Pension."
                ),
                "category": "service",
                "priority": "low",
                "days_back": 50,
                "program_name": "Food Assistance",
                "resolution": {
                    "decision": "upheld",
                    "days_to_close": 1,
                    "notes": [
                        {"text": "Provided delivery schedule for next 3 months"},
                        {"text": "Arranged for neighbor notification on delivery days"},
                        {"text": "Noted in file for case worker follow-up on living situation"},
                    ],
                },
            }
        ]
    },
    "carlos_morales": {
        "tickets": [
            {
                "title": "Universal Child Grant - adding new child",
                "description": (
                    "Household of 5 currently receiving grant for 3 children. "
                    "Wife Elena expecting 4th child next month. "
                    "How do we add new child to benefit calculation?"
                ),
                "category": "registration",
                "priority": "medium",
                "days_back": 30,
                "program_name": "Universal Child Grant",
                "resolution": {
                    "decision": "upheld",
                    "days_to_close": 5,
                    "notes": [
                        {"text": "Explained process for adding newborn to household"},
                        {"text": "Provided list of required documents (birth certificate, etc.)"},
                        {"text": "Grant will increase from $150 to $200/month after registration"},
                    ],
                },
            }
        ]
    },
}


class SPPGRMDemoGenerator(models.TransientModel):
    _name = "spp.grm.demo.generator"
    _description = "GRM Demo Data Generator"

    name = fields.Char(string="Name", default="GRM Demo Data", required=True)
    enroll_demo_stories = fields.Boolean(
        string="Enroll Demo Stories",
        default=True,
        help="Generate tickets based on demo stories (Juan Dela Cruz, Ibrahim Hassan, etc.)",
    )
    generate_volume = fields.Boolean(
        string="Generate Volume Data",
        default=True,
        help="Generate volume tickets in addition to story tickets",
    )
    number_of_tickets = fields.Integer(string="Number of Tickets", default=50, required=True)
    tickets_days_back = fields.Integer(
        string="Days Back",
        default=90,
        required=True,
        help="Generate tickets within the last N days",
    )
    include_resolved = fields.Boolean(string="Include Resolved Tickets", default=True)
    resolved_percentage = fields.Float(
        string="Resolved %",
        default=60.0,
        help="Percentage of tickets that should be resolved",
    )
    escalated_percentage = fields.Float(
        string="Escalated %",
        default=15.0,
        help="Percentage of tickets that should be escalated (of unresolved tickets)",
    )
    assign_teams = fields.Boolean(
        string="Assign Teams",
        default=True,
        help="Assign tickets to random GRM teams",
    )
    team_ids = fields.Many2many(
        comodel_name="spp.grm.team",
        string="Teams",
        help="Specific teams to assign tickets to. If empty, all active teams will be used.",
    )
    include_severity_distribution = fields.Boolean(
        string="Use Severity Distribution",
        default=True,
        help="Distribute ticket severity based on realistic percentages",
    )
    link_to_programs = fields.Boolean(
        string="Link to Programs",
        default=True,
        help="Link tickets to random programs where applicable",
    )
    link_to_beneficiaries = fields.Boolean(
        string="Link to Beneficiaries",
        default=True,
        help="Link tickets to random beneficiaries (registrants)",
    )
    locale_origin = fields.Many2one(
        "res.country",
        string="Locale Origin",
        default=lambda self: self.env.user.company_id.country_id or self.env.ref("base.us"),
        help="Country for Faker locale",
    )
    locale_origin_faker_locale = fields.Char(
        string="Faker Locale",
        related="locale_origin.faker_locale",
        readonly=True,
    )

    @api.constrains("number_of_tickets")
    def _check_number_of_tickets(self):
        for rec in self:
            if rec.number_of_tickets < 1:
                raise UserError(_("Number of tickets must be at least 1"))
            if rec.number_of_tickets > 10000:
                raise UserError(_("Number of tickets cannot exceed 10,000"))

    @api.constrains("resolved_percentage", "escalated_percentage")
    def _check_percentages(self):
        for rec in self:
            if not (0 <= rec.resolved_percentage <= 100):
                raise UserError(_("Resolved percentage must be between 0 and 100"))
            if not (0 <= rec.escalated_percentage <= 100):
                raise UserError(_("Escalated percentage must be between 0 and 100"))

    def generate_tickets(self):
        """Main method to generate GRM tickets"""
        self.ensure_one()

        # Validate that at least one generation option is enabled
        if not self.enroll_demo_stories and not self.generate_volume:
            raise UserError(
                _("Please enable at least one generation option: " "'Enroll Demo Stories' or 'Generate Volume Data'.")
            )

        # Initialize Faker
        faker_locale = self.locale_origin_faker_locale or "en_US"
        fake = Faker(faker_locale)

        # Generate story tickets if enabled
        created_tickets = self.env["spp.grm.ticket"]
        if self.enroll_demo_stories:
            story_tickets = self._generate_story_tickets(fake)
            if not story_tickets:
                raise UserError(
                    _(
                        "No story registrants found. Please create registrants with names matching "
                        "the demo stories (Juan Dela Cruz, Fatima Al-Rahman, Ibrahim Hassan, "
                        "Ahmed Said) or run 'Generate Stories' in spp_demo first."
                    )
                )
            created_tickets |= story_tickets
            _logger.info("Generated %d story tickets", len(story_tickets))

        # Generate volume tickets if enabled
        if self.generate_volume:
            _logger.info(
                "Starting GRM volume ticket generation: %d tickets over %d days",
                self.number_of_tickets,
                self.tickets_days_back,
            )

            # Load scenarios
            scenarios = self._load_scenarios()
            if not scenarios:
                raise UserError(_("No scenarios found. Please install spp_demo_scenarios module."))

            _logger.info("Loaded %d scenarios", len(scenarios))

            # Get available beneficiaries, programs, and teams
            beneficiaries = self._get_available_beneficiaries() if self.link_to_beneficiaries else []
            programs = self._get_available_programs() if self.link_to_programs else []
            teams = self._get_available_teams() if self.assign_teams else []

            if self.link_to_beneficiaries and not beneficiaries:
                raise UserError(_("No beneficiaries (registrants) found. Please create some registrants first."))

            if self.assign_teams:
                _logger.info("Found %d teams for assignment", len(teams))

            # Build repeat pool: ~10% of beneficiaries will file multiple tickets
            repeat_pool = self._build_repeat_pool(beneficiaries) if beneficiaries else []
            if repeat_pool:
                _logger.info(
                    "Built repeat pool of %d registrants for repeat ticket detection",
                    len(repeat_pool),
                )

            # Generate volume tickets
            for i in range(self.number_of_tickets):
                try:
                    # Select scenario
                    scenario = self._select_weighted_scenario(scenarios)

                    # Create ticket
                    ticket = self._create_ticket_from_scenario(
                        scenario,
                        fake,
                        beneficiaries,
                        programs,
                        teams,
                        repeat_pool=repeat_pool,
                    )

                    if ticket:
                        created_tickets |= ticket

                        # Simulate workflow progression
                        self._simulate_ticket_workflow(ticket, scenario, fake)

                    if (i + 1) % 10 == 0:
                        _logger.info("Generated %d/%d tickets", i + 1, self.number_of_tickets)

                except Exception as e:
                    _logger.error("Error generating ticket %d: %s", i + 1, e, exc_info=True)
                    continue

        _logger.info("Successfully generated %d tickets", len(created_tickets))

        # Return action to view generated tickets
        return {
            "type": "ir.actions.act_window",
            "name": "Generated GRM Tickets",
            "res_model": "spp.grm.ticket",
            "view_mode": "list,form,kanban",
            "domain": [("id", "in", created_tickets.ids)],
            "context": {"search_default_group_by_stage": 1},
        }

    def _generate_story_tickets(self, fake):
        """Generate tickets from GRM_STORY_TICKETS definitions"""
        created_tickets = self.env["spp.grm.ticket"]

        # Map story IDs to partner names
        # These names align with spp_mis_demo_v2 personas for cross-module demos
        story_name_mapping = {
            "juan_dela_cruz": "Juan Dela Cruz",
            "ibrahim_hassan": "Ibrahim Hassan",
            "fatima_al_rahman": "Fatima Al-Rahman",
            "ahmed_said": "Ahmed Said",
            "david_martinez": "David Martinez",
            "maria_santos": "Maria Santos",
            "rosa_garcia": "Rosa Garcia",
            "carlos_morales": "Carlos Morales",
        }

        for story_id, story_data in GRM_STORY_TICKETS.items():
            # Find the partner for this story
            partner_name = story_name_mapping.get(story_id)
            if not partner_name:
                continue

            # Search for partner by name
            partner = self.env["res.partner"].search(
                [
                    ("name", "=", partner_name),
                    ("is_registrant", "=", True),
                ],
                limit=1,
            )

            if not partner:
                _logger.warning("Partner '%s' not found, skipping story tickets", partner_name)
                continue

            # Generate tickets for this story
            for ticket_def in story_data.get("tickets", []):
                try:
                    ticket = self._create_story_ticket(ticket_def, partner, fake)
                    if ticket:
                        created_tickets |= ticket
                except Exception as e:
                    _logger.error("Error creating story ticket for %s: %s", story_id, e, exc_info=True)
                    continue

        return created_tickets

    def _create_story_ticket(self, ticket_def, partner, fake):
        """Create a single story ticket from definition"""
        # Calculate ticket date
        days_back = ticket_def.get("days_back", 30)
        ticket_date = self._random_date_in_range(days_back)

        # Get category
        category = self._get_or_create_category(ticket_def.get("category", "general"))

        # Get channel
        channel = self._get_random_channel()

        # Map priority
        priority_map = {"low": "0", "medium": "1", "high": "2", "very_high": "3"}
        priority = priority_map.get(ticket_def.get("priority", "medium"), "1")

        # Get severity and sensitivity
        severity = self._get_severity(ticket_def)
        sensitivity = self._get_sensitivity(ticket_def)

        # Create ticket
        vals = {
            "name": ticket_def.get("title", "Story Ticket"),
            "description": ticket_def.get("description", ""),
            "partner_id": partner.id,
            "category_id": category.id if category else False,
            "channel_id": channel.id if channel else False,
            "priority": priority,
            "severity": severity,
            "sensitivity": sensitivity,
            "create_date": ticket_date,
        }

        # Set registrant/household fields if spp_grm_registry is installed
        vals.update(self._get_registrant_vals(partner))

        ticket = self.env["spp.grm.ticket"].sudo().create(vals)

        # Backdate creation
        self.env.cr.execute(
            "UPDATE spp_grm_ticket SET create_date = %s WHERE id = %s",
            (ticket_date, ticket.id),
        )

        # Handle resolution if present
        resolution = ticket_def.get("resolution")
        if resolution:
            self._apply_story_resolution(ticket, resolution, ticket_date)

        return ticket

    def _apply_story_resolution(self, ticket, resolution, ticket_date):
        """Apply resolution to a story ticket"""
        # Add resolution notes
        notes = resolution.get("notes", [])
        resolution_days = resolution.get("days_to_close", 7)

        for i, note in enumerate(notes):
            note_date = ticket_date + timedelta(days=int((i + 1) * resolution_days / (len(notes) + 1)))
            ticket.sudo().message_post(
                body=f"<p>{note.get('text', '')}</p>",
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            # Backdate message
            message = ticket.message_ids[0] if ticket.message_ids else None
            if message:
                self.env.cr.execute(
                    "UPDATE mail_message SET date = %s WHERE id = %s",
                    (note_date, message.id),
                )

        # Close ticket
        closed_stage = self.env["spp.grm.ticket.stage"].search([("is_closed", "=", True)], limit=1)
        if closed_stage:
            close_date = ticket_date + timedelta(days=resolution_days)
            decision = resolution.get("decision", "upheld")

            ticket.sudo().write(
                {
                    "stage_id": closed_stage.id,
                    "decision": decision,
                }
            )

            # Backdate closure
            self.env.cr.execute(
                "UPDATE spp_grm_ticket SET closed_date = %s, last_stage_update = %s WHERE id = %s",
                (close_date, close_date, ticket.id),
            )

    def _load_scenarios(self):
        """Load GRM ticket scenarios"""
        loader = self.env.get("spp.demo.scenario.loader")

        if loader:
            try:
                scenarios = loader.load_scenarios(category="grm_ticket")
                if scenarios:
                    return scenarios
            except Exception as e:
                _logger.info("spp_demo_scenarios loader unavailable: %s", e)

        # Fallback: minimal built-in scenarios so the demo still works without spp_demo_scenarios
        return self._fallback_scenarios()

    def _fallback_scenarios(self):
        return [
            {
                "name": "Information request",
                "weight": 10,
                "ticket_profile": {"category": "general"},
                "description_templates": [
                    "Beneficiary has a question about their entitlement schedule.",
                    "Caller asks for program contact information.",
                ],
            },
            {
                "name": "Payment not received",
                "weight": 8,
                "ticket_profile": {"category": "payment"},
                "description_templates": [
                    "Beneficiary reports missing payment for last cycle.",
                    "Payment amount does not match expected value.",
                ],
            },
            {
                "name": "Registration update",
                "weight": 6,
                "ticket_profile": {"category": "registration"},
                "description_templates": [
                    "Registrant needs to update household information.",
                    "Change of phone number requested.",
                ],
            },
        ]

    def _select_weighted_scenario(self, scenarios):
        """Select a scenario using weighted random selection"""
        weights = [scenario.get("weight", 10) for scenario in scenarios]
        return random.choices(scenarios, weights=weights, k=1)[0]

    def _create_ticket_from_scenario(self, scenario, fake, beneficiaries, programs, teams, repeat_pool=None):
        """Create a GRM ticket from a scenario"""
        ticket_profile = scenario.get("ticket_profile", {})
        description_templates = scenario.get("description_templates", [])

        # Get ticket date (random within range)
        ticket_date = self._random_date_in_range(self.tickets_days_back)

        # Get beneficiary (biased toward repeat pool)
        partner = self._select_random_beneficiary(beneficiaries, repeat_pool) if beneficiaries else None
        if not partner:
            _logger.warning("No beneficiary found, skipping ticket creation")
            return None

        # Select description template
        description = self._render_description_template(
            random.choice(description_templates) if description_templates else "Generic ticket description",
            fake,
            programs,
        )

        # Generate title from first line of description
        title = description.split("\n")[0][:100] if description else scenario.get("name", "Ticket")

        # Get category
        category = self._get_or_create_category(ticket_profile.get("category", "general"))

        # Get channel
        channel = self._get_random_channel()

        # Get priority
        priority_map = {"low": "0", "medium": "1", "high": "2", "very_high": "3"}
        priority = priority_map.get(ticket_profile.get("priority", "medium"), "1")

        # Get severity and sensitivity based on scenario profile or distribution
        severity = self._get_severity(ticket_profile)
        sensitivity = self._get_sensitivity(ticket_profile)

        # Get team assignment
        team = self._select_random_team(teams, category) if teams else None

        # Create ticket
        vals = {
            "name": title,
            "description": description,
            "partner_id": partner.id,
            "category_id": category.id if category else False,
            "channel_id": channel.id if channel else False,
            "priority": priority,
            "severity": severity,
            "sensitivity": sensitivity,
            "team_id": team.id if team else False,
            "create_date": ticket_date,
        }

        # Set registrant/household fields if spp_grm_registry is installed
        vals.update(self._get_registrant_vals(partner))

        ticket = self.env["spp.grm.ticket"].sudo().create(vals)

        # Backdate creation
        self.env.cr.execute(
            "UPDATE spp_grm_ticket SET create_date = %s WHERE id = %s",
            (ticket_date, ticket.id),
        )

        return ticket

    def _simulate_ticket_workflow(self, ticket, scenario, fake):
        """Simulate ticket workflow progression"""
        # Determine if ticket should be resolved
        should_resolve = random.random() < (self.resolved_percentage / 100.0)

        if should_resolve and self.include_resolved:
            # Select resolution path
            resolution_paths = scenario.get("resolution_paths", [])
            if resolution_paths:
                # Weighted selection based on probability
                probabilities = [path.get("probability", 0.5) for path in resolution_paths]
                resolution_path = random.choices(resolution_paths, weights=probabilities, k=1)[0]

                # Add notes for resolution steps
                self._add_resolution_notes(ticket, resolution_path, fake)

                # Move to closed stage
                self._close_ticket(ticket, resolution_path)
        else:
            # Ticket remains open, might be escalated
            should_escalate = random.random() < (self.escalated_percentage / 100.0)
            if should_escalate:
                # Add escalation note
                self._add_escalation_note(ticket, scenario, fake)

            # Assign to random user
            self._assign_ticket(ticket)

    def _add_resolution_notes(self, ticket, resolution_path, fake):
        """Add notes documenting the resolution process"""
        resolution_steps = resolution_path.get("resolution_steps", [])
        resolution_days_range = resolution_path.get("resolution_days", [3, 7])

        for i, step in enumerate(resolution_steps):
            # Calculate note date (spreading steps over resolution period)
            days_offset = int(
                resolution_days_range[0]
                + (i / len(resolution_steps)) * (resolution_days_range[1] - resolution_days_range[0])
            )
            note_date = ticket.create_date + timedelta(days=days_offset)

            # Post message
            ticket.sudo().message_post(
                body=f"<p>{step}</p>",
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

            # Backdate message
            message = ticket.message_ids[0] if ticket.message_ids else None
            if message:
                self.env.cr.execute(
                    "UPDATE mail_message SET date = %s WHERE id = %s",
                    (note_date, message.id),
                )

    def _add_escalation_note(self, ticket, scenario, fake):
        """Add note about ticket escalation"""
        escalation = scenario.get("escalation", {})
        case_type = escalation.get("case_type", "general_investigation")

        ticket.sudo().message_post(
            body=f"<p>Ticket escalated to case management ({case_type})</p>",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

    def _close_ticket(self, ticket, resolution_path):
        """Move ticket to closed stage"""
        # Find a closed stage
        closed_stage = self.env["spp.grm.ticket.stage"].search([("is_closed", "=", True)], limit=1)
        if closed_stage:
            resolution_days_range = resolution_path.get("resolution_days", [3, 7])
            close_date = ticket.create_date + timedelta(
                days=random.randint(resolution_days_range[0], resolution_days_range[1])
            )

            # Get decision from resolution path or generate one
            decision = resolution_path.get("decision")
            if not decision:
                # Generate weighted random decision
                decisions = [
                    ("upheld", 40),
                    ("partially_upheld", 25),
                    ("rejected", 15),
                    ("withdrawn", 10),
                    ("redirected", 10),
                ]
                decision_choices, weights = zip(*decisions, strict=False)
                decision = random.choices(decision_choices, weights=weights, k=1)[0]

            ticket.sudo().write(
                {
                    "stage_id": closed_stage.id,
                    "decision": decision,
                }
            )

            # Backdate closure
            self.env.cr.execute(
                "UPDATE spp_grm_ticket SET closed_date = %s, last_stage_update = %s WHERE id = %s",
                (close_date, close_date, ticket.id),
            )

    def _assign_ticket(self, ticket):
        """Assign ticket to a random user"""
        users = self.env["res.users"].search([("active", "=", True)], limit=20)
        if users:
            user = random.choice(users)
            ticket.sudo().write({"user_id": user.id})

    def _render_description_template(self, template, fake, programs):
        """Render description template with fake data"""
        # Get random program
        program = random.choice(programs) if programs else None

        # Create context with fake data
        context = {
            "{program_name}": program.name if program else fake.company(),
            "{cycle_name}": f"Cycle {fake.random_int(1, 12)}/{fake.year()}",
            "{last_payment_date}": fake.date_between(start_date="-60d", end_date="-10d").strftime("%Y-%m-%d"),
            "{account_last_4}": str(fake.random_int(1000, 9999)),
            "{bank_name}": fake.company() + " Bank",
            "{occurrence_count}": fake.random_element(["first", "second", "third", "fourth"]),
            "{visit_date}": fake.date_between(start_date="-30d", end_date="-1d").strftime("%Y-%m-%d"),
            "{need_reason}": fake.random_element(
                [
                    "school fees",
                    "medical expenses",
                    "food for my family",
                    "rent payment",
                ]
            ),
            "{children_count}": str(fake.random_int(1, 8)),
            "{income_amount}": f"${fake.random_int(50, 500)}",
            "{termination_date}": fake.date_between(start_date="-90d", end_date="-30d").strftime("%Y-%m-%d"),
            "{application_date}": fake.date_between(start_date="-180d", end_date="-60d").strftime("%Y-%m-%d"),
            "{rejection_reason}": fake.random_element(
                [
                    "income too high",
                    "missing documents",
                    "not in target area",
                    "duplicate registration",
                ]
            ),
            "{months_enrolled}": str(fake.random_int(3, 24)),
        }

        # Replace placeholders
        result = template
        for placeholder, value in context.items():
            result = result.replace(placeholder, value)

        return result

    def _build_repeat_pool(self, beneficiaries, pool_ratio=0.10):
        """Select a subset of beneficiaries who will file multiple tickets.

        Args:
            beneficiaries: Recordset of individual registrants
            pool_ratio: Fraction of beneficiaries to use as repeat filers (default 10%)

        Returns:
            list of partner records that should get multiple tickets
        """
        if not beneficiaries:
            return []
        pool_size = max(3, int(len(beneficiaries) * pool_ratio))
        return random.sample(list(beneficiaries), min(pool_size, len(beneficiaries)))

    def _select_random_beneficiary(self, beneficiaries, repeat_pool=None):
        """Select a beneficiary, biased toward repeat pool.

        ~30% of the time picks from the repeat pool (if available),
        ensuring some registrants get multiple tickets for repeat detection.
        """
        if not beneficiaries:
            return None
        if repeat_pool and random.random() < 0.30:
            return random.choice(repeat_pool)
        return random.choice(beneficiaries)

    def _get_available_beneficiaries(self):
        """Get list of available individual registrants (not groups).

        Returns individual registrants that can be used as complainants.
        When spp_grm_registry is installed, these will be linked via
        registrant_id and their household via household_id.
        """
        return self.env["res.partner"].search(
            [("is_registrant", "=", True), ("is_group", "=", False)],
            limit=1000,
        )

    def _has_registry_fields(self):
        """Check if spp_grm_registry is installed (registrant_id field exists)."""
        return "registrant_id" in self.env["spp.grm.ticket"]._fields

    def _get_registrant_vals(self, partner):
        """Get registrant_id, household_id, and area_id vals for a ticket.

        Args:
            partner: Individual registrant (res.partner with is_group=False)

        Returns:
            dict with registrant/household/area fields to merge into ticket vals
        """
        if not self._has_registry_fields():
            return {}

        vals = {"registrant_id": partner.id}

        # Find household via membership
        if hasattr(partner, "individual_membership_ids") and partner.individual_membership_ids:
            household = partner.individual_membership_ids[0].group
            if household:
                vals["household_id"] = household.id

        # Fill area if available
        if hasattr(partner, "area_id") and partner.area_id:
            vals["area_id"] = partner.area_id.id

        return vals

    def _get_available_programs(self):
        """Get list of available programs"""
        if "spp.program" in self.env:
            return self.env["spp.program"].search([], limit=100)
        return []

    def _random_date_in_range(self, days_back):
        """Generate random datetime within the specified range"""
        now = datetime.now()
        start_date = now - timedelta(days=days_back)
        random_days = random.randint(0, days_back)
        random_hours = random.randint(0, 23)
        random_minutes = random.randint(0, 59)
        return start_date + timedelta(days=random_days, hours=random_hours, minutes=random_minutes)

    def _get_or_create_category(self, category_name):
        """Get or create a ticket category"""
        # Normalize category name for search
        normalized_name = category_name.replace("_", " ").title()

        # Search by normalized name
        category = self.env["spp.grm.ticket.category"].search([("name", "=", normalized_name)], limit=1)
        if not category:
            # Try to find by external ID
            try:
                category = self.env.ref(f"spp_grm_demo.grm_category_{category_name}")
            except Exception:
                # Create new category
                category = (
                    self.env["spp.grm.ticket.category"]
                    .sudo()
                    .create(
                        {
                            "name": normalized_name,
                        }
                    )
                )
        return category

    def _get_random_channel(self):
        """Get a random ticket channel"""
        channels = self.env["spp.grm.ticket.channel"].search([])
        if channels:
            return random.choice(channels)
        return None

    def _get_available_teams(self):
        """Get list of available GRM teams"""
        if self.team_ids:
            return self.team_ids
        return self.env["spp.grm.team"].search([("active", "=", True)], limit=50)

    def _select_random_team(self, teams, category=None):
        """Select a random team from available teams

        Args:
            teams: Recordset of spp.grm.team records
            category: Optional category for team matching

        Returns:
            spp.grm.team record or None
        """
        if not teams:
            return None

        # TODO: In future, could match teams to categories or areas
        return random.choice(teams)

    def _get_severity(self, ticket_profile):
        """Get severity based on profile or realistic distribution

        Args:
            ticket_profile: Scenario ticket profile dict

        Returns:
            str: severity value (low, medium, high, critical)
        """
        # Check if severity is specified in profile
        profile_severity = ticket_profile.get("severity")
        if profile_severity:
            return profile_severity

        # Use distribution if enabled
        if self.include_severity_distribution:
            # Realistic distribution: most tickets are medium/low severity
            severities = [
                ("low", 35),  # 35% low severity
                ("medium", 45),  # 45% medium severity
                ("high", 15),  # 15% high severity
                ("critical", 5),  # 5% critical
            ]
            severity_choices, weights = zip(*severities, strict=False)
            return random.choices(severity_choices, weights=weights, k=1)[0]

        return "medium"

    def _get_sensitivity(self, ticket_profile):
        """Get sensitivity based on profile or distribution

        Args:
            ticket_profile: Scenario ticket profile dict

        Returns:
            str: sensitivity value (standard, sensitive, highly_sensitive)
        """
        # Check if sensitivity is specified in profile
        profile_sensitivity = ticket_profile.get("sensitivity")
        if profile_sensitivity:
            return profile_sensitivity

        # Realistic distribution: most tickets are standard sensitivity
        sensitivities = [
            ("standard", 70),  # 70% standard
            ("sensitive", 25),  # 25% sensitive
            ("highly_sensitive", 5),  # 5% highly sensitive
        ]
        sensitivity_choices, weights = zip(*sensitivities, strict=False)
        return random.choices(sensitivity_choices, weights=weights, k=1)[0]
