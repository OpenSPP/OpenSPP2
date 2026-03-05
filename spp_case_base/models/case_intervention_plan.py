"""Case Intervention Plan Model."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CaseInterventionPlan(models.Model):
    """Intervention plans for cases."""

    _name = "spp.case.intervention.plan"
    _inherit = ["mail.thread"]
    _description = "Case Intervention Plan"
    _order = "case_id, version desc"

    name = fields.Char(
        string="Plan Name",
        required=True,
        tracking=True,
    )

    case_id = fields.Many2one(
        "spp.case",
        string="Case",
        required=True,
        ondelete="cascade",
        tracking=True,
    )

    version = fields.Integer(
        string="Version",
        default=1,
        required=True,
        readonly=True,
        help="Plan version number",
    )

    is_current = fields.Boolean(
        string="Is Current Plan",
        default=True,
        help="Whether this is the current active plan for the case",
    )

    previous_version_id = fields.Many2one(
        "spp.case.intervention.plan",
        string="Previous Version",
        readonly=True,
        help="Previous version of this plan",
    )

    # Plan Content
    goals = fields.Html(
        string="Goals",
        required=True,
        help="Case management goals to be achieved",
    )

    expected_outcomes = fields.Html(
        string="Expected Outcomes",
        help="Expected outcomes and success criteria",
    )

    client_responsibilities = fields.Html(
        string="Client Responsibilities",
        help="Client's roles and responsibilities in the plan",
    )

    # Dates
    start_date = fields.Date(
        string="Start Date",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )

    target_end_date = fields.Date(
        string="Target End Date",
        tracking=True,
    )

    actual_end_date = fields.Date(
        string="Actual End Date",
        readonly=True,
    )

    # Status
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_approval", "Pending Approval"),
            ("approved", "Approved"),
            ("active", "Active"),
            ("completed", "Completed"),
            ("revised", "Revised"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    # Approval
    approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
        tracking=True,
    )

    approved_date = fields.Datetime(
        string="Approved Date",
        readonly=True,
        tracking=True,
    )

    # Related Records
    intervention_ids = fields.One2many(
        "spp.case.intervention",
        "plan_id",
        string="Interventions",
    )

    # Computed Fields
    intervention_count = fields.Integer(
        string="Interventions",
        compute="_compute_intervention_count",
    )

    completed_intervention_count = fields.Integer(
        string="Completed Interventions",
        compute="_compute_intervention_count",
    )

    progress_percentage = fields.Float(
        string="Progress %",
        compute="_compute_progress",
    )

    @api.depends("intervention_ids", "intervention_ids.state")
    def _compute_intervention_count(self):
        """Compute intervention counts."""
        for plan in self:
            plan.intervention_count = len(plan.intervention_ids)
            plan.completed_intervention_count = len(plan.intervention_ids.filtered(lambda i: i.state == "completed"))

    @api.depends("intervention_ids", "intervention_ids.state")
    def _compute_progress(self):
        """Compute plan progress percentage."""
        for plan in self:
            if plan.intervention_count > 0:
                plan.progress_percentage = plan.completed_intervention_count / plan.intervention_count * 100
            else:
                plan.progress_percentage = 0.0

    @api.constrains("is_current")
    def _check_single_current_plan(self):
        """Ensure only one current plan per case."""
        for plan in self:
            if plan.is_current:
                other_current = self.search(
                    [
                        ("case_id", "=", plan.case_id.id),
                        ("is_current", "=", True),
                        ("id", "!=", plan.id),
                    ]
                )
                if other_current:
                    raise ValidationError(_("Only one plan can be marked as current for a case."))

    def action_submit_for_approval(self):
        """Submit plan for approval."""
        for plan in self:
            if not plan.intervention_ids:
                raise ValidationError(
                    _("Cannot submit plan without interventions. Please add at least one intervention.")
                )
            plan.state = "pending_approval"
        return True

    def action_approve(self):
        """Approve the plan."""
        for plan in self:
            plan.write(
                {
                    "state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_date": fields.Datetime.now(),
                }
            )
        return True

    def action_activate(self):
        """Activate the plan."""
        for plan in self:
            if plan.state != "approved":
                raise ValidationError(_("Only approved plans can be activated."))
            plan.state = "active"
        return True

    def action_complete(self):
        """Mark plan as completed."""
        for plan in self:
            plan.write(
                {
                    "state": "completed",
                    "actual_end_date": fields.Date.context_today(self),
                }
            )
        return True

    def action_create_revision(self):
        """Create a new version of this plan."""
        self.ensure_one()

        # Mark current plan as revised
        self.write(
            {
                "is_current": False,
                "state": "revised",
            }
        )

        # Create new version
        new_version = self.copy(
            {
                "version": self.version + 1,
                "previous_version_id": self.id,
                "is_current": True,
                "state": "draft",
                "approved_by_id": False,
                "approved_date": False,
                "actual_end_date": False,
                "start_date": fields.Date.context_today(self),
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.case.intervention.plan",
            "res_id": new_version.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_reset_to_draft(self):
        """Reset plan to draft."""
        for plan in self:
            if plan.state in ["completed", "revised"]:
                raise ValidationError(_("Cannot reset completed or revised plans."))
            plan.state = "draft"
        return True

    def action_view_interventions(self):
        """Open view with interventions of this plan."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Interventions - {self.name}",
            "res_model": "spp.case.intervention",
            "view_mode": "list,form",
            "domain": [("plan_id", "=", self.id)],
            "context": {"default_plan_id": self.id},
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate plan name if not provided."""
        for vals in vals_list:
            if not vals.get("name") and vals.get("case_id"):
                case = self.env["spp.case"].browse(vals["case_id"])
                version = vals.get("version", 1)
                vals["name"] = f"{case.name} - Plan v{version}"
        return super().create(vals_list)
