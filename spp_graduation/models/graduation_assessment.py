from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class GraduationAssessment(models.Model):
    _name = "spp.graduation.assessment"
    _description = "Graduation Assessment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "assessment_date desc"
    _check_company_auto = True

    name = fields.Char(
        compute="_compute_name",
        store=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Beneficiary",
        required=True,
        tracking=True,
        domain=[("is_registrant", "=", True)],
    )
    pathway_id = fields.Many2one(
        "spp.graduation.pathway",
        required=True,
        tracking=True,
        check_company=True,
    )

    assessment_date = fields.Date(
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

    # Criteria responses
    response_ids = fields.One2many(
        "spp.graduation.criteria.response",
        "assessment_id",
        string="Responses",
    )

    # Computed scores
    readiness_score = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Overall readiness score (0-1)",
    )
    is_required_criteria_met = fields.Boolean(
        compute="_compute_scores",
        store=True,
    )

    # Recommendation
    recommendation = fields.Selection(
        [
            ("graduate", "Ready to Graduate"),
            ("extend", "Extend Participation"),
            ("exit", "Exit (Non-graduation)"),
            ("defer", "Defer Assessment"),
        ],
        tracking=True,
    )

    recommendation_notes = fields.Text()

    # Approval workflow
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
    )

    approved_by_id = fields.Many2one("res.users", string="Approved By")
    approved_date = fields.Datetime()

    # Graduation outcome
    graduation_date = fields.Date()
    monitoring_end_date = fields.Date(
        compute="_compute_monitoring_end",
        store=True,
    )

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("partner_id", "pathway_id")
    def _compute_name(self):
        for rec in self:
            if rec.partner_id and rec.pathway_id:
                rec.name = f"{rec.partner_id.name} - {rec.pathway_id.name}"
            else:
                rec.name = "New Assessment"

    @api.depends(
        "response_ids.score",
        "response_ids.criteria_id.weight",
        "response_ids.criteria_id.is_required",
    )
    def _compute_scores(self):
        for assessment in self:
            if not assessment.response_ids:
                assessment.readiness_score = 0
                assessment.is_required_criteria_met = False
                continue

            total_weight = sum(r.criteria_id.weight for r in assessment.response_ids)
            weighted_score = sum(r.score * r.criteria_id.weight for r in assessment.response_ids)

            assessment.readiness_score = (weighted_score / total_weight) if total_weight else 0

            # Check required criteria
            required_responses = assessment.response_ids.filtered(lambda r: r.criteria_id.is_required)
            assessment.is_required_criteria_met = all(r.is_met for r in required_responses)

    @api.depends("graduation_date", "pathway_id.post_graduation_monitoring_months")
    def _compute_monitoring_end(self):
        for rec in self:
            if rec.graduation_date and rec.pathway_id.post_graduation_monitoring_months:
                rec.monitoring_end_date = rec.graduation_date + relativedelta(
                    months=rec.pathway_id.post_graduation_monitoring_months
                )
            else:
                rec.monitoring_end_date = False

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft assessments can be submitted."))
            rec.state = "submitted"

    def action_approve(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted assessments can be approved."))
            rec.write(
                {
                    "state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_date": fields.Datetime.now(),
                }
            )
            if rec.recommendation == "graduate":
                rec.graduation_date = fields.Date.today()

    def action_reject(self):
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Only submitted assessments can be rejected."))
            rec.state = "rejected"

    def action_reset_draft(self):
        for rec in self:
            if rec.state not in ("submitted", "rejected"):
                raise UserError(_("Only submitted or rejected assessments can be reset to draft."))
            rec.state = "draft"


class GraduationCriteriaResponse(models.Model):
    _name = "spp.graduation.criteria.response"
    _description = "Criteria Response"

    assessment_id = fields.Many2one(
        "spp.graduation.assessment",
        required=True,
        ondelete="cascade",
    )
    criteria_id = fields.Many2one(
        "spp.graduation.criteria",
        required=True,
    )

    score = fields.Float(
        help="Score from 0 to 1",
    )
    is_met = fields.Boolean()

    value = fields.Char(help="Actual value observed")
    notes = fields.Text()
    evidence_attachment_ids = fields.Many2many(
        "ir.attachment",
        relation="spp_graduation_response_attachment_rel",
        string="Evidence Attachments",
    )

    @api.constrains("score")
    def _check_score_range(self):
        for response in self:
            if response.score < 0 or response.score > 1:
                raise ValidationError(_("Score must be between 0 and 1. Got %(score)s.", score=response.score))
