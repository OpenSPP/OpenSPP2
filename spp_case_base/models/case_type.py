"""Case Type Model."""

from odoo import api, fields, models


class CaseType(models.Model):
    """Types of cases in the case management system."""

    _name = "spp.case.type"
    _description = "Case Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Unique code for the case type")
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    domain = fields.Selection(
        [
            ("social_protection", "Social Protection"),
            ("child_protection", "Child Protection"),
            ("gbv", "Gender-Based Violence"),
            ("disability", "Disability"),
            ("elderly", "Elderly Care"),
            ("livelihoods", "Livelihoods"),
            ("agriculture", "Agriculture"),
            ("health", "Health"),
            ("education", "Education"),
            ("other", "Other"),
        ],
        required=True,
        default="social_protection",
        help="Domain or sector of the case type",
    )

    default_intensity = fields.Selection(
        [
            ("1", "Level 1"),
            ("2", "Level 2"),
            ("3", "Level 3"),
        ],
        string="Default Intensity Level",
        default="2",
        help="Default intensity level for cases of this type",
    )

    stage_ids = fields.Many2many(
        "spp.case.stage",
        "case_type_stage_rel",
        "type_id",
        "stage_id",
        string="Available Stages",
        help="Stages available for this case type",
    )

    review_frequency_days = fields.Integer(
        string="Review Frequency (Days)",
        default=30,
        help="Number of days between case reviews",
    )

    recommended_caseload = fields.Integer(
        string="Recommended Caseload",
        default=25,
        help="Recommended number of active cases per case worker",
    )

    max_caseload = fields.Integer(
        string="Maximum Caseload",
        default=40,
        help="Maximum number of active cases per case worker",
    )

    color = fields.Integer(string="Color Index")

    # Computed fields for statistics
    case_count = fields.Integer(
        compute="_compute_case_count",
        string="Total Cases",
    )
    active_case_count = fields.Integer(
        compute="_compute_case_count",
        string="Active Cases",
    )

    _code_unique = models.Constraint(
        "unique (code)",
        "Case type code must be unique!",
    )

    @api.depends("active")
    def _compute_case_count(self):
        """Compute case counts for this case type."""
        for case_type in self:
            domain = [("case_type_id", "=", case_type.id)]
            case_type.case_count = self.env["spp.case"].search_count(domain)
            case_type.active_case_count = self.env["spp.case"].search_count(
                domain + [("stage_id.is_closed", "=", False)]
            )

    def action_view_cases(self):
        """Open view with cases of this type."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Cases - {self.name}",
            "res_model": "spp.case",
            "view_mode": "kanban,list,form",
            "domain": [("case_type_id", "=", self.id)],
            "context": {"default_case_type_id": self.id},
        }
