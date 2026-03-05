"""Case Management Core Model."""

import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class Case(models.Model):
    """Core case management model."""

    _name = "spp.case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Case Management Case"
    _order = "create_date desc"

    # Basic Information
    name = fields.Char(
        string="Case Number",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self._get_next_case_number(),
    )

    case_type_id = fields.Many2one(
        "spp.case.type",
        string="Case Type",
        required=True,
        tracking=True,
    )

    intensity_level = fields.Selection(
        [
            ("1", "Level 1 - Low Intensity"),
            ("2", "Level 2 - Medium Intensity"),
            ("3", "Level 3 - High Intensity"),
        ],
        default="2",
        required=True,
        tracking=True,
        help="Level of case management intensity required",
    )

    priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        default="medium",
        required=True,
        tracking=True,
    )

    # Client Information
    client_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("household", "Household"),
            ("group", "Group"),
        ],
        default="individual",
        required=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Client",
        required=True,
        tracking=True,
    )

    # Workflow
    stage_id = fields.Many2one(
        "spp.case.stage",
        string="Stage",
        tracking=True,
        group_expand="_read_group_stage_ids",
    )

    # Assignment
    case_worker_id = fields.Many2one(
        "res.users",
        string="Case Worker",
        required=True,
        tracking=True,
        domain=[("share", "=", False)],
    )

    supervisor_id = fields.Many2one(
        "res.users",
        string="Supervisor",
        tracking=True,
        domain=[("share", "=", False)],
    )

    team_id = fields.Many2one(
        "spp.case.team",
        string="Team",
        tracking=True,
    )

    # Dates
    opened_date = fields.Date(
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    target_closure_date = fields.Date(
        tracking=True,
    )

    actual_closure_date = fields.Date(
        readonly=True,
        tracking=True,
    )

    # Intake Information
    intake_source = fields.Selection(
        [
            ("walk_in", "Walk-in"),
            ("referral", "Referral"),
            ("outreach", "Outreach"),
            ("grm", "GRM/Complaint"),
            ("program", "Program Enrollment"),
            ("other", "Other"),
        ],
        tracking=True,
    )

    referral_source = fields.Char(
        help="Name or organization that referred the client",
    )

    presenting_issue = fields.Html(
        help="Main issue or need that led to case opening",
    )

    # Risk and Vulnerability
    risk_factor_ids = fields.Many2many(
        "spp.case.risk.factor",
        "case_risk_factor_rel",
        "case_id",
        "risk_factor_id",
        string="Risk Factors",
    )

    vulnerability_ids = fields.Many2many(
        "spp.case.vulnerability",
        "case_vulnerability_rel",
        "case_id",
        "vulnerability_id",
        string="Vulnerabilities",
    )

    # Related Records
    assessment_ids = fields.One2many(
        "spp.case.assessment",
        "case_id",
        string="Assessments",
    )

    intervention_plan_ids = fields.One2many(
        "spp.case.intervention.plan",
        "case_id",
        string="Intervention Plans",
    )

    visit_ids = fields.One2many(
        "spp.case.visit",
        "case_id",
        string="Visits",
    )

    note_ids = fields.One2many(
        "spp.case.note",
        "case_id",
        string="Case Notes",
    )

    referral_ids = fields.One2many(
        "spp.case.referral",
        "case_id",
        string="Referrals",
    )

    # Count fields for stat buttons
    assessment_count = fields.Integer(
        compute="_compute_related_counts",
    )
    intervention_plan_count = fields.Integer(
        compute="_compute_related_counts",
    )
    visit_count = fields.Integer(
        compute="_compute_related_counts",
    )
    note_count = fields.Integer(
        compute="_compute_related_counts",
    )
    referral_count = fields.Integer(
        compute="_compute_related_counts",
    )

    # Closure Information
    closure_reason_id = fields.Many2one(
        "spp.case.closure.reason",
        string="Closure Reason",
    )

    closure_outcome = fields.Selection(
        [
            ("goals_achieved", "Goals Achieved"),
            ("partial", "Partial Achievement"),
            ("disengaged", "Client Disengaged"),
            ("transferred", "Transferred"),
            ("ineligible", "Ineligible"),
            ("deceased", "Deceased"),
            ("lost_contact", "Lost Contact"),
            ("other", "Other"),
        ],
    )

    closure_summary = fields.Html()

    # Review Dates
    next_review_date = fields.Date(
        tracking=True,
    )

    last_review_date = fields.Date()

    # Company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # UI Fields
    active = fields.Boolean(
        default=True,
        help="If unchecked, this record will be hidden from active views.",
    )

    color = fields.Integer(
        string="Color Index",
        help="Color used for kanban view.",
    )

    # Computed Fields
    days_open = fields.Integer(
        compute="_compute_days_open",
        store=False,
    )

    is_active = fields.Boolean(
        compute="_compute_is_active",
        store=True,
    )

    has_active_plan = fields.Boolean(
        compute="_compute_has_active_plan",
        store=False,
    )

    current_plan_id = fields.Many2one(
        "spp.case.intervention.plan",
        string="Current Plan",
        compute="_compute_current_plan",
        store=False,
    )

    @api.model
    def _get_next_case_number(self):
        """Generate next case number."""
        sequence = self.env["ir.sequence"].sudo()
        # Try to get existing sequence, create if doesn't exist
        seq = sequence.search([("code", "=", "spp.case")], limit=1)
        if not seq:
            seq = sequence.create(
                {
                    "name": "Case Number",
                    "code": "spp.case",
                    "prefix": "CASE-%(year)s-",
                    "padding": 5,
                    "company_id": False,
                }
            )
        return seq.next_by_id()

    @api.depends("assessment_ids", "intervention_plan_ids", "visit_ids", "note_ids", "referral_ids")
    def _compute_related_counts(self):
        """Compute counts for related records (for stat buttons)."""
        for case in self:
            case.assessment_count = len(case.assessment_ids)
            case.intervention_plan_count = len(case.intervention_plan_ids)
            case.visit_count = len(case.visit_ids)
            case.note_count = len(case.note_ids)
            case.referral_count = len(case.referral_ids)

    @api.depends("opened_date", "actual_closure_date")
    def _compute_days_open(self):
        """Compute number of days case has been open."""
        today = fields.Date.context_today(self)
        for case in self:
            if case.actual_closure_date:
                end_date = case.actual_closure_date
            else:
                end_date = today
            if case.opened_date:
                delta = end_date - case.opened_date
                case.days_open = delta.days
            else:
                case.days_open = 0

    @api.depends("stage_id", "stage_id.is_closed")
    def _compute_is_active(self):
        """Compute if case is active (not in closed stage)."""
        for case in self:
            case.is_active = not case.stage_id.is_closed if case.stage_id else True

    @api.depends("intervention_plan_ids", "intervention_plan_ids.is_current", "intervention_plan_ids.state")
    def _compute_has_active_plan(self):
        """Compute if case has an active intervention plan."""
        for case in self:
            case.has_active_plan = bool(
                case.intervention_plan_ids.filtered(lambda p: p.is_current and p.state in ["approved", "active"])
            )

    @api.depends("intervention_plan_ids", "intervention_plan_ids.is_current")
    def _compute_current_plan(self):
        """Get the current active intervention plan."""
        for case in self:
            case.current_plan_id = case.intervention_plan_ids.filtered(lambda p: p.is_current)[:1]

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Support kanban view with all stages."""
        return stages.search([])

    @api.onchange("case_type_id")
    def _onchange_case_type_id(self):
        """Set default intensity when case type changes."""
        if self.case_type_id and self.case_type_id.default_intensity:
            self.intensity_level = self.case_type_id.default_intensity

    @api.onchange("team_id")
    def _onchange_team_id(self):
        """Set supervisor when team changes."""
        if self.team_id and self.team_id.supervisor_id:
            self.supervisor_id = self.team_id.supervisor_id

    @api.constrains("presenting_issue")
    def _check_presenting_issue(self):
        """Validate that presenting issue is provided."""
        for case in self:
            # Html fields may contain empty tags like <p><br></p>, strip them
            content = case.presenting_issue or ""
            stripped = re.sub(r"<[^>]+>", "", content).strip()
            if not stripped:
                raise ValidationError(_("Please provide a Presenting Issue before saving the case."))

    @api.constrains("stage_id")
    def _check_stage_requirements(self):
        """Validate stage change requirements."""
        for case in self:
            if not case.stage_id:
                continue

            # Check if plan is required
            if case.stage_id.is_requires_plan and not case.has_active_plan:
                raise ValidationError(
                    _("Stage '%(stage)s' requires an approved intervention plan.", stage=case.stage_id.name)
                )

            # Check minimum intensity level
            if case.stage_id.min_intensity:
                if int(case.intensity_level) < int(case.stage_id.min_intensity):
                    raise ValidationError(
                        _(
                            "Stage '%(stage)s' requires minimum intensity level %(level)s.",
                            stage=case.stage_id.name,
                            level=case.stage_id.min_intensity,
                        )
                    )

    def action_close_case(self):
        """Close the case."""
        self.ensure_one()
        closed_stage = self.env["spp.case.stage"].search([("is_closed", "=", True)], limit=1)
        if not closed_stage:
            raise ValidationError(_("No closed stage found. Please configure a closed stage."))
        self.write(
            {
                "stage_id": closed_stage.id,
                "actual_closure_date": fields.Date.context_today(self),
            }
        )
        return True

    def action_reopen_case(self):
        """Reopen a closed case."""
        self.ensure_one()
        intake_stage = self.env["spp.case.stage"].search([("phase", "=", "intake"), ("is_closed", "=", False)], limit=1)
        if not intake_stage:
            raise ValidationError(_("No intake stage found. Please configure an intake stage."))
        self.write(
            {
                "stage_id": intake_stage.id,
                "actual_closure_date": False,
            }
        )
        return True

    @api.model
    def _cron_check_reviews(self):
        """Cron job to check for overdue case reviews and send reminders."""
        today = fields.Date.today()

        # Find cases with overdue reviews
        overdue_cases = self.search(
            [
                ("stage_id.is_closed", "=", False),
                ("next_review_date", "<=", today),
            ]
        )

        for case in overdue_cases:
            # Create activity for case worker
            case.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=today,
                summary=_("Case review overdue"),
                note=_(
                    "Case %(case_name)s is due for review. Last review: %(last_review)s",
                    case_name=case.name,
                    last_review=case.last_review_date or _("Never"),
                ),
                user_id=case.case_worker_id.id,
            )

        # Find cases approaching review (3 days warning)
        warning_date = today + timedelta(days=3)
        upcoming_cases = self.search(
            [
                ("stage_id.is_closed", "=", False),
                ("next_review_date", ">", today),
                ("next_review_date", "<=", warning_date),
            ]
        )

        for case in upcoming_cases:
            # Check if activity already exists
            existing = self.env["mail.activity"].search(
                [
                    ("res_model", "=", "spp.case"),
                    ("res_id", "=", case.id),
                    ("summary", "ilike", "review upcoming"),
                ],
                limit=1,
            )

            if not existing:
                case.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=case.next_review_date,
                    summary=_("Case review upcoming"),
                    note=_(
                        "Case %(case_name)s review is scheduled for %(review_date)s",
                        case_name=case.name,
                        review_date=case.next_review_date,
                    ),
                    user_id=case.case_worker_id.id,
                )

        return True

    def action_schedule_review(self):
        """Schedule the next review based on case type settings."""
        self.ensure_one()
        today = fields.Date.today()

        # Update last review date
        self.last_review_date = today

        # Calculate next review date from case type
        if self.case_type_id and self.case_type_id.review_frequency_days:
            self.next_review_date = today + timedelta(days=self.case_type_id.review_frequency_days)
        else:
            # Default 30 days
            self.next_review_date = today + timedelta(days=30)

        return True
