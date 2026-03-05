# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Case Extension for Graduation Integration.

Links cases to graduation assessments for exit management
and tracking client graduation from programs.
"""

from odoo import api, fields, models


class Case(models.Model):
    """Extension of spp.case to include graduation tracking."""

    _inherit = "spp.case"

    graduation_assessment_ids = fields.One2many(
        comodel_name="spp.graduation.assessment",
        inverse_name="case_id",
        string="Graduation Assessments",
    )

    graduation_assessment_count = fields.Integer(
        compute="_compute_graduation_stats",
        string="Assessment Count",
    )

    latest_graduation_assessment_id = fields.Many2one(
        comodel_name="spp.graduation.assessment",
        compute="_compute_graduation_stats",
        string="Latest Assessment",
    )

    graduation_readiness = fields.Float(
        compute="_compute_graduation_stats",
        string="Readiness Score",
        help="Latest graduation readiness score",
    )

    graduation_status = fields.Selection(
        selection=[
            ("not_assessed", "Not Assessed"),
            ("in_progress", "Assessment In Progress"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved for Graduation"),
            ("graduated", "Graduated"),
            ("deferred", "Deferred"),
        ],
        compute="_compute_graduation_stats",
        string="Graduation Status",
    )

    @api.depends(
        "graduation_assessment_ids",
        "graduation_assessment_ids.state",
        "graduation_assessment_ids.readiness_score",
        "graduation_assessment_ids.recommendation",
    )
    def _compute_graduation_stats(self):
        """Compute graduation statistics from assessments."""
        for case in self:
            assessments = case.graduation_assessment_ids.sorted(key=lambda a: a.assessment_date, reverse=True)

            case.graduation_assessment_count = len(assessments)

            if assessments:
                latest = assessments[0]
                case.latest_graduation_assessment_id = latest
                case.graduation_readiness = latest.readiness_score

                # Determine status
                if latest.state == "approved" and latest.recommendation == "graduate":
                    if latest.graduation_date:
                        case.graduation_status = "graduated"
                    else:
                        case.graduation_status = "approved"
                elif latest.state == "submitted":
                    case.graduation_status = "pending_approval"
                elif latest.state == "draft":
                    case.graduation_status = "in_progress"
                elif latest.recommendation == "defer":
                    case.graduation_status = "deferred"
                else:
                    case.graduation_status = "not_assessed"
            else:
                case.latest_graduation_assessment_id = False
                case.graduation_readiness = 0.0
                case.graduation_status = "not_assessed"

    def action_view_graduation_assessments(self):
        """Open graduation assessments for this case."""
        self.ensure_one()
        return {
            "name": "Graduation Assessments",
            "type": "ir.actions.act_window",
            "res_model": "spp.graduation.assessment",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.id)],
            "context": {
                "default_case_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }

    def action_create_graduation_assessment(self):
        """Create a new graduation assessment for this case."""
        self.ensure_one()
        return {
            "name": "New Graduation Assessment",
            "type": "ir.actions.act_window",
            "res_model": "spp.graduation.assessment",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_case_id": self.id,
                "default_partner_id": self.partner_id.id,
            },
        }
