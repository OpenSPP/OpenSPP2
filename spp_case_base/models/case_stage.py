"""Case Stage Model."""

from odoo import fields, models


class CaseStage(models.Model):
    """Stages for case management workflow."""

    _name = "spp.case.stage"
    _description = "Case Stage"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    phase = fields.Selection(
        [
            ("intake", "Intake"),
            ("assessment", "Assessment"),
            ("planning", "Planning"),
            ("implementation", "Implementation"),
            ("monitoring", "Monitoring"),
            ("evaluation", "Evaluation"),
            ("closure", "Closure"),
        ],
        required=True,
        default="intake",
        help="The phase of the case management process",
    )
    is_closed = fields.Boolean(
        string="Is Closed Stage",
        default=False,
        help="Cases in this stage are considered closed",
    )
    is_requires_plan = fields.Boolean(
        string="Requires Intervention Plan",
        default=False,
        help="Cases must have an approved intervention plan to enter this stage",
    )
    is_requires_assessment = fields.Boolean(
        string="Requires Assessment",
        default=False,
        help="Cases must have a completed assessment to enter this stage",
    )
    is_requires_approval = fields.Boolean(
        string="Requires Approval",
        default=False,
        help="Stage change requires supervisor approval",
    )
    min_intensity = fields.Selection(
        [
            ("1", "Level 1"),
            ("2", "Level 2"),
            ("3", "Level 3"),
        ],
        string="Minimum Intensity Level",
        help="Minimum case intensity level required for this stage",
    )
    fold = fields.Boolean(
        string="Folded in Kanban",
        default=False,
        help="This stage is folded in the kanban view",
    )
    color = fields.Integer(string="Color Index")
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    # Computed field for case counts
    case_count = fields.Integer(
        compute="_compute_case_count",
        string="Cases",
    )

    def _compute_case_count(self):
        """Compute number of cases in this stage."""
        for stage in self:
            stage.case_count = self.env["spp.case"].search_count([("stage_id", "=", stage.id)])
