import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class SimulationScenario(models.Model):
    """A 'what if' targeting scenario definition."""

    _name = "spp.simulation.scenario"
    _description = "Simulation Scenario"
    _inherit = ["mail.thread"]
    _order = "write_date desc"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
    description = fields.Text(string="Description")
    category = fields.Char(
        string="Category",
        help="Group related scenarios together (e.g., 'Child Grant Variations', 'Budget Testing')",
        index=True,
    )
    template_id = fields.Many2one(
        comodel_name="spp.simulation.scenario.template",
        string="Template",
        ondelete="set null",
        help="Template this scenario was created from.",
    )
    target_type = fields.Selection(
        selection=[
            ("group", "Group"),
            ("individual", "Individual"),
        ],
        string="Target Type",
        required=True,
        default="group",
        tracking=True,
    )
    targeting_expression = fields.Text(
        string="Targeting Expression (CEL)",
        help="CEL expression that defines who is eligible. Required before running.",
    )
    targeting_expression_explanation = fields.Text(
        string="Expression Explanation",
        help="Plain language explanation of what this expression targets.",
    )
    entitlement_rule_ids = fields.One2many(
        comodel_name="spp.simulation.entitlement.rule",
        inverse_name="scenario_id",
        string="Entitlement Rules",
    )
    budget_amount = fields.Float(
        string="Budget Amount",
        tracking=True,
        help="Maximum budget for the scenario. Leave at 0 for no limit.",
    )
    budget_strategy = fields.Selection(
        selection=[
            ("none", "No Budget Constraint"),
            ("cap_total", "Cap at Budget Total"),
            ("proportional_reduction", "Proportional Reduction"),
        ],
        string="Budget Strategy",
        default="none",
        tracking=True,
        help="How to handle when total cost exceeds budget. "
        "'No Constraint' ignores budget. "
        "'Cap at Total' stops adding beneficiaries when budget is reached. "
        "'Proportional Reduction' reduces all amounts proportionally to fit within budget.",
    )
    metric_ids = fields.Many2many(
        comodel_name="spp.simulation.metric",
        string="Custom Metrics",
    )
    program_id = fields.Many2one(
        comodel_name="spp.program",
        string="Reference Program",
        ondelete="set null",
        help="Optional program for comparison context.",
    )
    converted_program_id = fields.Many2one(
        comodel_name="spp.program",
        string="Converted Program",
        ondelete="set null",
        readonly=True,
        help="Program created from this scenario via conversion.",
    )
    ideal_population_expression = fields.Text(
        string="Ideal Population Expression (CEL)",
        help="CEL expression defining who SHOULD receive benefits. "
        "Used to calculate leakage (included but shouldn't be) and "
        "undercoverage (should be included but weren't). "
        "Example: metric('pmt_score') < 2.0",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("ready", "Ready"),
            ("archived", "Archived"),
        ],
        string="State",
        default="draft",
        required=True,
        tracking=True,
    )
    targeting_preview_count = fields.Integer(
        string="Preview Count",
        compute="_compute_targeting_preview_count",
        help="Live count of registrants matching the targeting expression.",
    )
    targeting_preview_error = fields.Text(
        string="Preview Error",
        compute="_compute_targeting_preview_count",
    )
    run_ids = fields.One2many(
        comodel_name="spp.simulation.run",
        inverse_name="scenario_id",
        string="Simulation Runs",
    )
    run_count = fields.Integer(
        string="Run Count",
        compute="_compute_run_count",
    )
    latest_run_id = fields.Many2one(
        comodel_name="spp.simulation.run",
        string="Latest Run",
        compute="_compute_latest_run",
    )
    latest_beneficiary_count = fields.Integer(
        string="Latest Beneficiary Count",
        compute="_compute_latest_run",
    )
    latest_equity_score = fields.Float(
        string="Latest Equity Score",
        compute="_compute_latest_run",
    )
    cel_profile = fields.Char(
        string="CEL Profile",
        compute="_compute_cel_profile",
        store=False,
        help="CEL profile based on target type (registry_groups or registry_individuals)",
    )

    @api.depends("target_type")
    def _compute_cel_profile(self):
        """Compute the CEL profile based on target type."""
        for record in self:
            record.cel_profile = "registry_groups" if record.target_type == "group" else "registry_individuals"

    @api.depends("targeting_expression", "target_type")
    def _compute_targeting_preview_count(self):
        cel_service = self.env["spp.cel.service"]
        for record in self:
            record.targeting_preview_count = 0
            record.targeting_preview_error = False
            if not record.targeting_expression:
                continue
            profile = "registry_groups" if record.target_type == "group" else "registry_individuals"
            try:
                result = cel_service.compile_expression(
                    record.targeting_expression,
                    profile=profile,
                    base_domain=[("disabled", "=", False)],
                    limit=0,
                )
                record.targeting_preview_count = result.get("count", 0)
            except Exception as exc:
                record.targeting_preview_error = str(exc)

    @api.depends("run_ids")
    def _compute_run_count(self):
        for record in self:
            record.run_count = len(record.run_ids)

    @api.depends("run_ids", "run_ids.state", "run_ids.executed_at")
    def _compute_latest_run(self):
        for record in self:
            completed_runs = record.run_ids.filtered(lambda r: r.state == "completed").sorted(
                "executed_at", reverse=True
            )
            if completed_runs:
                record.latest_run_id = completed_runs[0]
                record.latest_beneficiary_count = completed_runs[0].beneficiary_count
                record.latest_equity_score = completed_runs[0].equity_score
            else:
                record.latest_run_id = False
                record.latest_beneficiary_count = 0
                record.latest_equity_score = 0.0

    def action_set_ready(self):
        """Transition scenario from draft to ready."""
        for record in self:
            if not record.targeting_expression:
                raise ValidationError(_("A targeting expression is required to mark a scenario as ready."))
            record.state = "ready"

    def action_set_draft(self):
        """Transition scenario back to draft."""
        self.write({"state": "draft"})

    def action_archive(self):
        """Archive the scenario."""
        self.write({"state": "archived"})

    def action_run_simulation(self):
        """Execute the simulation and create a run record."""
        self.ensure_one()
        if self.state != "ready":
            raise UserError(_("Only scenarios in 'Ready' state can be run."))
        service = self.env["spp.simulation.service"]
        run = service.execute_simulation(self)
        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.simulation.run",
            "res_id": run.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_duplicate_for_comparison(self):
        """Duplicate this scenario for side-by-side comparison."""
        self.ensure_one()
        new_scenario = self.copy(
            default={
                "name": f"{self.name} (Comparison)",
                "state": "draft",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.simulation.scenario",
            "res_id": new_scenario.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_runs(self):
        """Open the list of simulation runs for this scenario."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Simulation Runs",
            "res_model": "spp.simulation.run",
            "view_mode": "list,form",
            "domain": [("scenario_id", "=", self.id)],
            "context": {"default_scenario_id": self.id},
        }

    @api.model
    def action_create_from_template(self, template_id):
        """Create a new scenario pre-populated from a template."""
        template = self.env["spp.simulation.scenario.template"].browse(template_id)
        if not template.exists():
            raise UserError(_("Template not found."))
        vals = {
            "name": template.name,
            "description": template.description,
            "template_id": template.id,
            "target_type": template.target_type,
            "targeting_expression": template.targeting_expression,
            "ideal_population_expression": template.ideal_population_expression or False,
            "state": "draft",
        }
        scenario = self.create(vals)
        # Create default entitlement rule from template
        if template.default_amount:
            self.env["spp.simulation.entitlement.rule"].create(
                {
                    "scenario_id": scenario.id,
                    "amount_mode": template.default_amount_mode or "fixed",
                    "amount": template.default_amount,
                }
            )
        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.simulation.scenario",
            "res_id": scenario.id,
            "view_mode": "form",
            "target": "current",
        }
