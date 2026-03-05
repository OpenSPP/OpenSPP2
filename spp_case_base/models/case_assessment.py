"""Case Assessment Model."""

from odoo import api, fields, models
from odoo.exceptions import UserError


class CaseAssessment(models.Model):
    """Case Assessment for tracking evaluations and risk assessments."""

    _name = "spp.case.assessment"
    _description = "Case Assessment"
    _order = "assessment_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # Basic Information
    name = fields.Char(
        string="Assessment Name",
        compute="_compute_name",
        store=True,
        readonly=True,
    )

    case_id = fields.Many2one(
        "spp.case",
        string="Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )

    assessment_date = fields.Date(
        string="Assessment Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )

    assessor_id = fields.Many2one(
        "res.users",
        string="Assessor",
        default=lambda self: self.env.user,
        required=True,
        domain=[("share", "=", False)],
        tracking=True,
    )

    assessment_type = fields.Selection(
        [
            ("intake", "Intake Assessment"),
            ("periodic", "Periodic Review"),
            ("closure", "Closure Assessment"),
            ("reassessment", "Reassessment"),
        ],
        string="Assessment Type",
        required=True,
        default="periodic",
        tracking=True,
    )

    # Assessment Content
    findings = fields.Html(
        string="Findings",
        help="Key findings from the assessment",
    )

    recommendations = fields.Html(
        string="Recommendations",
        help="Recommended actions based on assessment",
    )

    # Risk Assessment
    risk_score = fields.Float(
        string="Risk Score",
        help="Risk score from 0 to 100",
        tracking=True,
    )

    risk_level = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        string="Risk Level",
        compute="_compute_risk_level",
        store=True,
        tracking=True,
    )

    vulnerability_ids = fields.Many2many(
        "spp.case.vulnerability",
        "case_assessment_vulnerability_rel",
        "assessment_id",
        "vulnerability_id",
        string="Identified Vulnerabilities",
    )

    risk_factor_ids = fields.Many2many(
        "spp.case.risk.factor",
        "case_assessment_risk_factor_rel",
        "assessment_id",
        "risk_factor_id",
        string="Risk Factors",
    )

    # Workflow
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("completed", "Completed"),
            ("reviewed", "Reviewed"),
        ],
        string="State",
        default="draft",
        required=True,
        tracking=True,
    )

    reviewed_by_id = fields.Many2one(
        "res.users",
        string="Reviewed By",
        readonly=True,
        domain=[("share", "=", False)],
        tracking=True,
    )

    reviewed_date = fields.Datetime(
        string="Reviewed Date",
        readonly=True,
        tracking=True,
    )

    # Related Information
    case_name = fields.Char(
        related="case_id.name",
        string="Case Number",
        readonly=True,
    )

    case_worker_id = fields.Many2one(
        related="case_id.case_worker_id",
        string="Case Worker",
        readonly=True,
    )

    # Company
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )

    # UI Fields
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    @api.depends("case_id", "case_id.name", "assessment_type", "assessment_date")
    def _compute_name(self):
        """Generate assessment name from case + type + date."""
        for assessment in self:
            if assessment.case_id and assessment.assessment_type and assessment.assessment_date:
                type_label = dict(assessment._fields["assessment_type"].selection).get(assessment.assessment_type, "")
                assessment.name = f"{assessment.case_id.name} - {type_label} - {assessment.assessment_date}"
            else:
                assessment.name = "New Assessment"

    @api.depends("risk_score")
    def _compute_risk_level(self):
        """Compute risk level from risk score.

        Risk levels:
        - 0-25: Low
        - 26-50: Medium
        - 51-75: High
        - 76-100: Critical
        """
        for assessment in self:
            if assessment.risk_score is False or assessment.risk_score < 0:
                assessment.risk_level = "low"
            elif assessment.risk_score <= 25:
                assessment.risk_level = "low"
            elif assessment.risk_score <= 50:
                assessment.risk_level = "medium"
            elif assessment.risk_score <= 75:
                assessment.risk_level = "high"
            else:
                assessment.risk_level = "critical"

    @api.constrains("risk_score")
    def _check_risk_score(self):
        """Validate risk score is between 0 and 100."""
        for assessment in self:
            if assessment.risk_score and (assessment.risk_score < 0 or assessment.risk_score > 100):
                raise UserError("Risk score must be between 0 and 100.")

    def action_complete(self):
        """Move assessment from draft to completed."""
        for assessment in self:
            if assessment.state != "draft":
                raise UserError("Only draft assessments can be completed.")
            assessment.write({"state": "completed"})
        return True

    def action_review(self):
        """Move assessment from completed to reviewed.

        Requires supervisor permissions.
        """
        for assessment in self:
            if assessment.state != "completed":
                raise UserError("Only completed assessments can be reviewed.")

            # Check if current user is a supervisor
            supervisor_group = self.env.ref("spp_case_base.group_case_supervisor", raise_if_not_found=False)
            if supervisor_group and supervisor_group not in self.env.user.group_ids:
                raise UserError("Only supervisors can review assessments.")

            assessment.write(
                {
                    "state": "reviewed",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_date": fields.Datetime.now(),
                }
            )
        return True

    def action_reset_to_draft(self):
        """Reset assessment to draft state."""
        for assessment in self:
            if assessment.state == "reviewed":
                raise UserError("Reviewed assessments cannot be reset to draft.")
            assessment.write(
                {
                    "state": "draft",
                    "reviewed_by_id": False,
                    "reviewed_date": False,
                }
            )
        return True

    @api.onchange("case_id")
    def _onchange_case_id(self):
        """Pre-populate vulnerabilities and risk factors from case."""
        if self.case_id:
            self.vulnerability_ids = self.case_id.vulnerability_ids
            self.risk_factor_ids = self.case_id.risk_factor_ids

    def action_view_case(self):
        """Open the related case in form view."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Case",
            "res_model": "spp.case",
            "res_id": self.case_id.id,
            "view_mode": "form",
            "target": "current",
        }
