import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SimulationComparison(models.Model):
    """Side-by-side comparison of multiple simulation runs."""

    _name = "spp.simulation.comparison"
    _description = "Simulation Comparison"
    _order = "create_date desc"

    name = fields.Char(string="Name", required=True)
    run_ids = fields.Many2many(
        comodel_name="spp.simulation.run",
        string="Runs to Compare",
        required=True,
    )
    comparison_json = fields.Json(
        string="Comparison Data",
        readonly=True,
    )
    parameters_comparison_json = fields.Json(
        string="Parameters Comparison",
        readonly=True,
        help="Side-by-side comparison of scenario parameters",
    )
    parameters_comparison_html = fields.Html(
        string="Parameters Comparison Table",
        compute="_compute_parameters_comparison_html",
    )
    overlap_count_json = fields.Json(
        string="Overlap Counts",
        readonly=True,
        help="Aggregated overlap counts between scenarios. "
        "Computed from current registry data, not historical state.",
    )
    staleness_warning = fields.Text(
        string="Staleness Warning",
        compute="_compute_staleness_warning",
    )

    @api.constrains("run_ids")
    def _check_minimum_runs(self):
        for record in self:
            if len(record.run_ids) < 2:
                raise ValidationError(_("A comparison requires at least 2 simulation runs."))

    @api.onchange("run_ids")
    def _onchange_run_ids(self):
        """Auto-recompute comparison when runs are added or removed."""
        if len(self.run_ids) >= 2:
            # Build comparison data
            comparison_data = {"runs": []}
            for run in self.run_ids:
                run_data = {
                    "run_id": run.id,
                    "scenario_name": run.scenario_id.name,
                    "beneficiary_count": run.beneficiary_count,
                    "total_cost": run.total_cost,
                    "coverage_rate": run.coverage_rate,
                    "equity_score": run.equity_score,
                    "gini_coefficient": run.gini_coefficient,
                    "has_disparity": run.has_disparity,
                    "leakage_rate": run.leakage_rate,
                    "undercoverage_rate": run.undercoverage_rate,
                    "budget_utilization": run.budget_utilization,
                    "executed_at": run.executed_at.isoformat() if run.executed_at else None,
                }
                comparison_data["runs"].append(run_data)
            self.comparison_json = comparison_data

            # Build parameters comparison from snapshots
            parameters_data = {"runs": []}
            for run in self.run_ids:
                snapshot = run.scenario_snapshot_json or {}
                param_data = {
                    "run_id": run.id,
                    "scenario_name": run.scenario_id.name,
                    "executed_at": run.executed_at.isoformat() if run.executed_at else None,
                    "target_type": snapshot.get("target_type"),
                    "targeting_expression": snapshot.get("targeting_expression"),
                    "budget_amount": snapshot.get("budget_amount"),
                    "budget_strategy": snapshot.get("budget_strategy"),
                    "entitlement_rules": snapshot.get("entitlement_rules") or [],
                    "ideal_population_expression": snapshot.get("ideal_population_expression"),
                }
                parameters_data["runs"].append(param_data)
            self.parameters_comparison_json = parameters_data

    @api.depends("run_ids", "run_ids.executed_at")
    def _compute_staleness_warning(self):
        for record in self:
            if len(record.run_ids) < 2:
                record.staleness_warning = False
                continue
            dates = record.run_ids.mapped("executed_at")
            dates = [d for d in dates if d]
            if len(dates) < 2:
                record.staleness_warning = False
                continue
            max_date = max(dates)
            min_date = min(dates)
            delta = (max_date - min_date).days
            if delta > 1:
                record.staleness_warning = (
                    f"These runs were executed {delta} days apart. "
                    "Overlap counts reflect the current registry state, "
                    "not the state at each run's execution time."
                )
            else:
                record.staleness_warning = False

    @api.depends("parameters_comparison_json")
    def _compute_parameters_comparison_html(self):
        """Render parameters comparison as an HTML table."""
        budget_strategy_labels = {
            "none": "No Budget Constraint",
            "cap_total": "Cap at Budget Total",
            "proportional_reduction": "Proportional Reduction",
        }
        target_type_labels = {
            "group": "Group (Household)",
            "individual": "Individual",
        }

        for record in self:
            params = record.parameters_comparison_json
            if not params:
                record.parameters_comparison_html = False
                continue

            runs = params.get("runs", [])
            if not runs:
                record.parameters_comparison_html = "<p class='text-muted'>No parameter data available</p>"
                continue

            # Build comparison table
            html_parts = ['<table class="table table-bordered table-sm">']

            # Header row with scenario names and execution dates
            html_parts.append("<thead><tr><th>Parameter</th>")
            for run_data in runs:
                name = run_data.get("scenario_name", "Unknown")
                executed_at = run_data.get("executed_at")
                if executed_at:
                    # Parse ISO date and format nicely
                    try:
                        dt = datetime.fromisoformat(executed_at.replace("Z", "+00:00"))
                        date_str = dt.strftime("%b %d, %Y %H:%M")
                        html_parts.append(f"<th>{name}<br/><small class='text-muted'>{date_str}</small></th>")
                    except ValueError:
                        html_parts.append(f"<th>{name}</th>")
                else:
                    html_parts.append(f"<th>{name}</th>")
            html_parts.append("</tr></thead><tbody>")

            # Target Type row
            html_parts.append("<tr><td><strong>Target Type</strong></td>")
            for run_data in runs:
                val = target_type_labels.get(run_data.get("target_type"), run_data.get("target_type", "-"))
                html_parts.append(f"<td>{val}</td>")
            html_parts.append("</tr>")

            # Targeting Expression row
            html_parts.append("<tr><td><strong>Targeting Expression</strong></td>")
            for run_data in runs:
                expr = run_data.get("targeting_expression") or "-"
                html_parts.append(f"<td><code style='word-break:break-word'>{expr}</code></td>")
            html_parts.append("</tr>")

            # Budget Amount row
            html_parts.append("<tr><td><strong>Budget Amount</strong></td>")
            for run_data in runs:
                amount = run_data.get("budget_amount") or 0
                html_parts.append(f"<td>{amount:,.2f}</td>")
            html_parts.append("</tr>")

            # Budget Strategy row
            html_parts.append("<tr><td><strong>Budget Strategy</strong></td>")
            for run_data in runs:
                strategy = budget_strategy_labels.get(
                    run_data.get("budget_strategy"), run_data.get("budget_strategy", "-")
                )
                html_parts.append(f"<td>{strategy}</td>")
            html_parts.append("</tr>")

            # Entitlement Rules row
            html_parts.append("<tr><td><strong>Entitlement Rules</strong></td>")
            for run_data in runs:
                rules = run_data.get("entitlement_rules") or []
                if rules:
                    rules_html = "<ul style='margin:0;padding-left:1rem'>"
                    for rule in rules:
                        mode = rule.get("amount_mode", "fixed")
                        amount = rule.get("amount", 0)
                        if mode == "fixed":
                            rules_html += f"<li>Fixed: {amount:,.2f}</li>"
                        elif mode == "multiplier":
                            field = rule.get("multiplier_field", "?")
                            rules_html += f"<li>Multiplier: {amount:,.2f} × {field}</li>"
                        elif mode == "cel":
                            cel = rule.get("amount_cel_expression", "?")
                            rules_html += f"<li>CEL: <code>{cel}</code></li>"
                    rules_html += "</ul>"
                    html_parts.append(f"<td>{rules_html}</td>")
                else:
                    html_parts.append("<td>-</td>")
            html_parts.append("</tr>")

            html_parts.append("</tbody></table>")
            record.parameters_comparison_html = "".join(html_parts)

    def action_compute_comparison(self):
        """Compute the side-by-side comparison data."""
        self.ensure_one()
        comparison_data = {"runs": []}
        for run in self.run_ids:
            run_data = {
                "run_id": run.id,
                "scenario_name": run.scenario_id.name,
                "beneficiary_count": run.beneficiary_count,
                "total_cost": run.total_cost,
                "coverage_rate": run.coverage_rate,
                "equity_score": run.equity_score,
                "gini_coefficient": run.gini_coefficient,
                "has_disparity": run.has_disparity,
                "leakage_rate": run.leakage_rate,
                "undercoverage_rate": run.undercoverage_rate,
                "budget_utilization": run.budget_utilization,
                "executed_at": run.executed_at.isoformat() if run.executed_at else None,
            }
            comparison_data["runs"].append(run_data)
        self.comparison_json = comparison_data

        # Build parameters comparison from snapshots
        parameters_data = {"runs": []}
        for run in self.run_ids:
            snapshot = run.scenario_snapshot_json or {}
            param_data = {
                "run_id": run.id,
                "scenario_name": run.scenario_id.name,
                "executed_at": run.executed_at.isoformat() if run.executed_at else None,
                "target_type": snapshot.get("target_type"),
                "targeting_expression": snapshot.get("targeting_expression"),
                "budget_amount": snapshot.get("budget_amount"),
                "budget_strategy": snapshot.get("budget_strategy"),
                "entitlement_rules": snapshot.get("entitlement_rules") or [],
                "ideal_population_expression": snapshot.get("ideal_population_expression"),
            }
            parameters_data["runs"].append(param_data)
        self.parameters_comparison_json = parameters_data

        # Compute overlap if possible
        self._compute_overlap()

    def _compute_overlap(self):
        """Re-execute targeting expressions to compute overlap counts."""
        registry = self.env["spp.cel.registry"]
        executor = self.env["spp.cel.executor"]
        run_sets = {}
        for run in self.run_ids:
            scenario = run.scenario_id
            if not scenario.targeting_expression:
                continue
            profile = "registry_groups" if scenario.target_type == "group" else "registry_individuals"
            try:
                cfg = registry.load_profile(profile)
                executor_with_cfg = executor.with_context(cel_cfg=cfg)
                all_ids = []
                for batch_ids in executor_with_cfg.compile_for_batch(
                    "res.partner", scenario.targeting_expression, batch_size=5000
                ):
                    all_ids.extend(batch_ids)
                run_sets[run.id] = set(all_ids)
            except Exception:
                _logger.warning(
                    "Could not compute overlap for run %s (scenario '%s')",
                    run.id,
                    scenario.name,
                    exc_info=True,
                )
                run_sets[run.id] = set()

        overlap_data = {}
        run_list = list(self.run_ids)
        for i, run_a in enumerate(run_list):
            for run_b in run_list[i + 1 :]:
                set_a = run_sets.get(run_a.id, set())
                set_b = run_sets.get(run_b.id, set())
                overlap_count = len(set_a & set_b)
                union_count = len(set_a | set_b)
                key = f"{run_a.id}_{run_b.id}"
                overlap_data[key] = {
                    "run_a_id": run_a.id,
                    "run_a_name": run_a.scenario_id.name,
                    "run_b_id": run_b.id,
                    "run_b_name": run_b.scenario_id.name,
                    "overlap_count": overlap_count,
                    "union_count": union_count,
                    "jaccard_index": overlap_count / union_count if union_count else 0,
                }
        self.overlap_count_json = overlap_data
