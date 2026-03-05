"""Case Intervention Model."""

from odoo import api, fields, models


class CaseIntervention(models.Model):
    """Individual interventions within a case intervention plan."""

    _name = "spp.case.intervention"
    _description = "Case Intervention"
    _order = "plan_id, sequence, id"

    name = fields.Char(
        string="Intervention",
        required=True,
        help="Name or title of the intervention",
    )

    plan_id = fields.Many2one(
        "spp.case.intervention.plan",
        string="Intervention Plan",
        required=True,
        ondelete="cascade",
    )

    case_id = fields.Many2one(
        "spp.case",
        string="Case",
        related="plan_id.case_id",
        store=True,
        readonly=True,
    )

    sequence = fields.Integer(
        default=10,
        help="Order of interventions in the plan",
    )

    description = fields.Text(
        help="Detailed description of the intervention",
    )

    target_outcome = fields.Char(
        help="Expected result or outcome of this intervention",
    )

    responsible = fields.Selection(
        [
            ("client", "Client"),
            ("worker", "Case Worker"),
            ("provider", "Service Provider"),
            ("joint", "Joint Responsibility"),
        ],
        string="Responsible Party",
        default="joint",
        required=True,
        help="Who is primarily responsible for completing this intervention",
    )

    provider_id = fields.Many2one(
        "res.partner",
        string="Service Provider",
        help="External service provider (if applicable)",
    )

    # Dates
    target_date = fields.Date(
        help="Target completion date",
    )

    completed_date = fields.Date(
        readonly=True,
    )

    # Status
    state = fields.Selection(
        [
            ("planned", "Planned"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("not_completed", "Not Completed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="planned",
        required=True,
    )

    completion_notes = fields.Text(
        help="Notes about the completion or outcome of the intervention",
    )

    # Computed fields
    is_overdue = fields.Boolean(
        compute="_compute_is_overdue",
        store=False,
    )

    days_until_due = fields.Integer(
        compute="_compute_days_until_due",
        store=False,
    )

    @api.depends("target_date", "state")
    def _compute_is_overdue(self):
        """Check if intervention is overdue."""
        today = fields.Date.context_today(self)
        for intervention in self:
            intervention.is_overdue = (
                intervention.target_date
                and intervention.target_date < today
                and intervention.state not in ["completed", "cancelled", "not_completed"]
            )

    @api.depends("target_date")
    def _compute_days_until_due(self):
        """Compute days until target date."""
        today = fields.Date.context_today(self)
        for intervention in self:
            if intervention.target_date:
                delta = intervention.target_date - today
                intervention.days_until_due = delta.days
            else:
                intervention.days_until_due = 0

    def action_start(self):
        """Mark intervention as in progress."""
        for intervention in self:
            intervention.state = "in_progress"
        return True

    def action_complete(self):
        """Mark intervention as completed."""
        for intervention in self:
            intervention.write(
                {
                    "state": "completed",
                    "completed_date": fields.Date.context_today(self),
                }
            )
        return True

    def action_mark_not_completed(self):
        """Mark intervention as not completed."""
        for intervention in self:
            intervention.state = "not_completed"
        return True

    def action_cancel(self):
        """Cancel the intervention."""
        for intervention in self:
            intervention.state = "cancelled"
        return True

    def action_reset(self):
        """Reset intervention to planned."""
        for intervention in self:
            intervention.write(
                {
                    "state": "planned",
                    "completed_date": False,
                }
            )
        return True

    @api.onchange("responsible")
    def _onchange_responsible(self):
        """Clear provider if not applicable."""
        if self.responsible != "provider":
            self.provider_id = False
