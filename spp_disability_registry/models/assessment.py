import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Washington Group difficulty levels
WG_DIFFICULTY_LEVELS = [
    ("none", "No difficulty"),
    ("some", "Some difficulty"),
    ("a_lot", "A lot of difficulty"),
    ("cannot", "Cannot do at all"),
]

# Severe difficulty levels that indicate disability per WG standard
WG_SEVERE_DIFFICULTY_LEVELS = ("a_lot", "cannot")

# Review category to months mapping
REVIEW_CATEGORY_MONTHS = {
    "mie": 12,  # Medical Improvement Expected: 6-18 months (using 12)
    "mip": 36,  # Medical Improvement Possible: 3 years
    "mine": 72,  # Medical Improvement Not Expected: 5-7 years (using 72 = 6 years)
}


class SppDisabilityAssessment(models.Model):
    _name = "spp.disability.assessment"
    _description = "Disability Assessment"
    _inherit = ["mail.thread", "mail.activity.mixin", "spp.approval.mixin"]
    _order = "assessment_date desc, id desc"

    # === Identity ===
    name = fields.Char(
        compute="_compute_name",
        store=True,
        readonly=True,
    )
    registrant_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        index=True,
        domain="[('is_registrant', '=', True), ('is_group', '=', False)]",
        tracking=True,
    )
    assessment_date = fields.Date(
        string="Assessment Date",
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    assessor_id = fields.Many2one(
        "res.users",
        string="Assessor",
        default=lambda self: self.env.user,
        tracking=True,
    )

    # === Assessment Type (age-based) ===
    assessment_type = fields.Selection(
        [
            ("wg_ss", "Adult (WG-SS)"),
            ("cfm_5_17", "Child 5-17 (CFM)"),
            ("cfm_2_4", "Child 2-4 (CFM)"),
        ],
        string="Assessment Type",
        compute="_compute_assessment_type",
        store=True,
        readonly=False,
        tracking=True,
    )
    age_at_assessment = fields.Integer(
        string="Age at Assessment",
        compute="_compute_age_at_assessment",
        store=True,
    )
    age_restriction_enforced = fields.Boolean(
        string="Age Restriction Enforced",
        compute="_compute_age_restriction_enforced",
        help="Technical flag driving the form: True when the assessment type is "
        "auto-determined by age (default). Toggled by the 'Allow manual assessment "
        "type' setting in Disability Registry configuration.",
    )

    # === WG-SS Responses (6 domains) ===
    wg_seeing = fields.Selection(
        WG_DIFFICULTY_LEVELS,
        string="Seeing",
        help="Do you have difficulty seeing, even if wearing glasses?",
    )
    wg_hearing = fields.Selection(
        WG_DIFFICULTY_LEVELS,
        string="Hearing",
        help="Do you have difficulty hearing, even if using a hearing aid?",
    )
    wg_walking = fields.Selection(
        WG_DIFFICULTY_LEVELS,
        string="Walking",
        help="Do you have difficulty walking or climbing steps?",
    )
    wg_remembering = fields.Selection(
        WG_DIFFICULTY_LEVELS,
        string="Remembering",
        help="Do you have difficulty remembering or concentrating?",
    )
    wg_selfcare = fields.Selection(
        WG_DIFFICULTY_LEVELS,
        string="Self-care",
        help="Do you have difficulty with self-care (washing, dressing)?",
    )
    wg_communicating = fields.Selection(
        WG_DIFFICULTY_LEVELS,
        string="Communicating",
        help="Do you have difficulty communicating (understanding or being understood)?",
    )

    # === Impairment Classification (DCI DO.DR.02) ===
    impairment_type_ids = fields.Many2many(
        "spp.vocabulary.code",
        "spp_disability_assessment_impairment_type_rel",
        "assessment_id",
        "code_id",
        string="Impairment Types",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:01')]",
    )
    impairment_cause_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Impairment Cause",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:03')]",
    )
    severity_level_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Severity Level",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:02')]",
        tracking=True,
    )

    # === Review Schedule (categorical) ===
    review_category = fields.Selection(
        [
            ("mie", "Improvement Expected (6-18 mo)"),
            ("mip", "Improvement Possible (3 yr)"),
            ("mine", "Improvement Not Expected (5+ yr)"),
        ],
        string="Review Category",
        help="Determines reassessment frequency based on medical improvement expectation",
        tracking=True,
    )
    next_review_date = fields.Date(
        string="Next Review Date",
        compute="_compute_next_review_date",
        store=True,
    )

    # === Support Needs (flexible) ===
    support_needs = fields.Text(
        string="Support Needs",
        help="Free-text description of support needs. Countries can extend with structured fields.",
    )

    # === Proxy Response Tracking ===
    is_proxy_response = fields.Boolean(
        string="Proxy Response",
        compute="_compute_is_proxy_response",
        store=True,
        readonly=False,
        help="True if responses were provided by a proxy. Forced on for CFM 2-4 and "
        "(unless self-report is enabled) CFM 5-17; optional for WG-SS.",
    )
    proxy_locked = fields.Boolean(
        string="Proxy Locked",
        compute="_compute_proxy_locked",
        help="Technical flag: True when the proxy response checkbox is forced and "
        "must not be edited (driven by assessment type, age and configuration).",
    )
    proxy_respondent_id = fields.Many2one(
        "res.partner",
        string="Proxy Respondent",
        help="Person who provided responses on behalf of the registrant",
    )
    proxy_relationship = fields.Selection(
        [
            ("parent", "Parent/Guardian"),
            ("spouse", "Spouse"),
            ("child", "Adult Child"),
            ("caregiver", "Caregiver"),
            ("other", "Other"),
        ],
        string="Proxy Relationship",
    )
    proxy_reason = fields.Selection(
        [
            (
                "functional_limitation",
                "Unable to respond due to functional limitation (hearing, communication, cognitive, etc.)",
            ),
            ("caregiver", "Individual not present - caregiver responding"),
            ("household_head", "Individual not present - household head responding"),
            ("other", "Other"),
        ],
        string="Reason for Proxy",
        help="Why a proxy responded instead of the individual (WG-SS).",
    )

    # === Computed Disability Indicator ===
    has_disability = fields.Boolean(
        string="Has Disability",
        compute="_compute_disability_indicator",
        store=True,
        help="WG standard: any domain with 'a lot of difficulty' or 'cannot do at all'",
    )
    wg_domain_count = fields.Integer(
        string="Domains with Difficulty",
        compute="_compute_disability_indicator",
        store=True,
        help="Number of WG domains with 'a lot' or 'cannot' response",
    )

    @api.constrains("assessment_date")
    def _check_assessment_date_not_future(self):
        """Ensure assessment date is not in the future."""
        today = fields.Date.today()
        for rec in self:
            if rec.assessment_date and rec.assessment_date > today:
                raise ValidationError(_("Assessment date cannot be in the future."))

    @api.constrains("assessment_date", "registrant_id")
    def _check_assessment_date_after_birthdate(self):
        """Ensure assessment date is not before registrant's birthdate."""
        for rec in self:
            if (
                rec.registrant_id
                and rec.registrant_id.birthdate
                and rec.assessment_date
                and rec.assessment_date < rec.registrant_id.birthdate
            ):
                raise ValidationError(_("Assessment date cannot be before the registrant's birthdate."))

    @api.depends("registrant_id", "assessment_date")
    def _compute_name(self):
        for rec in self:
            if not rec.registrant_id or not rec.assessment_date:
                rec.name = "New Assessment"
                continue
            rec.name = f"{rec.registrant_id.name} - {rec.assessment_date}"

    @api.depends("registrant_id.birthdate", "assessment_date")
    def _compute_age_at_assessment(self):
        for rec in self:
            if not rec.registrant_id.birthdate or not rec.assessment_date:
                rec.age_at_assessment = 0
                continue
            delta = relativedelta(rec.assessment_date, rec.registrant_id.birthdate)
            rec.age_at_assessment = delta.years

    @api.model
    def _disability_config(self):
        """Read the Disability Registry configuration parameters with defaults."""
        # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
        icp = self.env["ir.config_parameter"].sudo()
        get = icp.get_param
        return {
            "disregard_age": get("spp_disability_registry.disregard_age", "False") == "True",
            "allow_self_report_cfm": get("spp_disability_registry.allow_self_report_cfm_5_17", "False") == "True",
            "self_report_min_age": int(get("spp_disability_registry.self_report_min_age", "0") or 0),
            "allow_proxy_wg_ss": get("spp_disability_registry.allow_proxy_wg_ss", "True") == "True",
        }

    @api.model
    def _disability_disregard_age(self):
        """Read the 'disregard age for assessment type' configuration flag."""
        return self._disability_config()["disregard_age"]

    def _proxy_is_locked(self):
        """Whether the proxy response flag is forced (non-editable) for this record.

        - CFM 2-4: always locked (proxy mandatory).
        - CFM 5-17: locked unless self-report is enabled and the child meets the
          optional minimum self-report age.
        - WG-SS: locked only when proxy reporting is disabled by configuration.
        """
        self.ensure_one()
        cfg = self._disability_config()
        if self.assessment_type == "cfm_2_4":
            return True
        if self.assessment_type == "cfm_5_17":
            min_age = cfg["self_report_min_age"]
            old_enough = (not min_age) or (self.age_at_assessment >= min_age)
            return not (cfg["allow_self_report_cfm"] and old_enough)
        # WG-SS (adult) and any fallback.
        return not cfg["allow_proxy_wg_ss"]

    @api.depends("assessment_type")
    def _compute_is_proxy_response(self):
        """Seed the proxy flag from the assessment type (children = proxy by default,
        adults = self-report). This default also matches the forced value in every
        locked case, so locked records always carry the correct flag. Editable for
        unlocked types — user toggles persist until the assessment type changes.
        """
        for rec in self:
            rec.is_proxy_response = rec.assessment_type in ("cfm_2_4", "cfm_5_17")

    @api.depends("assessment_type", "age_at_assessment")
    def _compute_proxy_locked(self):
        for rec in self:
            rec.proxy_locked = rec._proxy_is_locked()

    def _assessment_type_for_age(self):
        """Return the WG/CFM assessment type implied by the age at assessment."""
        self.ensure_one()
        age = self.age_at_assessment
        if age >= 18:
            return "wg_ss"
        elif age >= 5:
            return "cfm_5_17"
        # Under 5 (including under 2) defaults to the CFM 2-4 instrument.
        return "cfm_2_4"

    def _compute_age_restriction_enforced(self):
        enforced = not self._disability_disregard_age()
        for rec in self:
            rec.age_restriction_enforced = enforced

    @api.depends("age_at_assessment")
    def _compute_assessment_type(self):
        disregard_age = self._disability_disregard_age()
        for rec in self:
            if disregard_age:
                # Manual mode: preserve the user's selection; only seed a
                # sensible default when nothing has been chosen yet.
                if not rec.assessment_type:
                    rec.assessment_type = rec._assessment_type_for_age()
                continue
            rec.assessment_type = rec._assessment_type_for_age()

    @api.constrains("registrant_id")
    def _check_birthdate_required_for_age(self):
        """Require a date of birth when the assessment type is age-driven."""
        if self._disability_disregard_age():
            return
        for rec in self:
            if rec.registrant_id and not rec.registrant_id.birthdate:
                raise ValidationError(
                    _(
                        "A date of birth is required for %s to determine the assessment type by age. "
                        "Set the registrant's date of birth, or enable 'Allow manual assessment type' "
                        "in the Disability Registry settings.",
                        rec.registrant_id.display_name,
                    )
                )

    @api.depends("review_category", "assessment_date")
    def _compute_next_review_date(self):
        for rec in self:
            if not rec.review_category or not rec.assessment_date:
                rec.next_review_date = False
                continue
            months = REVIEW_CATEGORY_MONTHS.get(rec.review_category, REVIEW_CATEGORY_MONTHS["mip"])
            rec.next_review_date = rec.assessment_date + relativedelta(months=months)

    @api.depends(
        "wg_seeing",
        "wg_hearing",
        "wg_walking",
        "wg_remembering",
        "wg_selfcare",
        "wg_communicating",
    )
    def _compute_disability_indicator(self):
        """WG standard: any domain with 'a_lot' or 'cannot' indicates disability."""
        for rec in self:
            responses = [
                rec.wg_seeing,
                rec.wg_hearing,
                rec.wg_walking,
                rec.wg_remembering,
                rec.wg_selfcare,
                rec.wg_communicating,
            ]
            # Count domains with severe difficulty
            domain_count = sum(1 for r in responses if r in WG_SEVERE_DIFFICULTY_LEVELS)
            rec.wg_domain_count = domain_count
            rec.has_disability = domain_count > 0

    def action_view_registrant(self):
        """Open the registrant form."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.registrant_id.id,
            "view_mode": "form",
            "target": "current",
        }
