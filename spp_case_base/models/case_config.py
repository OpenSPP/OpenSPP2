"""Case Management Configuration Models."""

from odoo import api, fields, models


class CaseRiskFactor(models.Model):
    """Risk factors that can be associated with cases."""

    _name = "spp.case.risk.factor"
    _description = "Case Risk Factor"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    severity_weight = fields.Float(
        default=1.0,
        help="Weight for risk severity calculation (0.0-1.0)",
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index")

    _code_unique = models.Constraint(
        "unique (code)",
        "Risk factor code must be unique!",
    )


class CaseVulnerability(models.Model):
    """Vulnerabilities that can be associated with cases."""

    _name = "spp.case.vulnerability"
    _description = "Case Vulnerability"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Color Index")

    _code_unique = models.Constraint(
        "unique (code)",
        "Vulnerability code must be unique!",
    )


class CaseClosureReason(models.Model):
    """Reasons for case closure."""

    _name = "spp.case.closure.reason"
    _description = "Case Closure Reason"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    outcome_type = fields.Selection(
        [
            ("positive", "Positive"),
            ("neutral", "Neutral"),
            ("negative", "Negative"),
        ],
        required=True,
        default="neutral",
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "unique (code)",
        "Closure reason code must be unique!",
    )


class CaseTeam(models.Model):
    """Case management teams."""

    _name = "spp.case.team"
    _description = "Case Management Team"
    _order = "name"

    name = fields.Char(required=True)
    supervisor_id = fields.Many2one(
        "res.users",
        string="Team Supervisor",
        domain=[("share", "=", False)],
    )
    member_ids = fields.Many2many(
        "res.users",
        "case_team_user_rel",
        "team_id",
        "user_id",
        string="Team Members",
        domain=[("share", "=", False)],
    )
    case_type_ids = fields.Many2many(
        "spp.case.type",
        "case_team_type_rel",
        "team_id",
        "type_id",
        string="Case Types",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    color = fields.Integer(string="Color Index")

    # Computed fields for statistics
    active_case_count = fields.Integer(
        compute="_compute_case_counts",
        string="Active Cases",
    )
    total_case_count = fields.Integer(
        compute="_compute_case_counts",
        string="Total Cases",
    )

    @api.depends("member_ids")
    def _compute_case_counts(self):
        """Compute case counts for the team."""
        for team in self:
            domain = [("team_id", "=", team.id)]
            team.total_case_count = self.env["spp.case"].search_count(domain)
            team.active_case_count = self.env["spp.case"].search_count(domain + [("stage_id.is_closed", "=", False)])

    def action_view_cases(self):
        """Open view with cases assigned to this team."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Cases - {self.name}",
            "res_model": "spp.case",
            "view_mode": "kanban,list,form",
            "domain": [("team_id", "=", self.id)],
            "context": {"search_default_team_id": self.id},
        }
