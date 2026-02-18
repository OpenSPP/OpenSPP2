import logging

from markupsafe import Markup

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SimulationRun(models.Model):
    """Aggregated simulation results. Non-deletable for audit compliance."""

    _name = "spp.simulation.run"
    _description = "Simulation Run"
    _order = "executed_at desc"
    _rec_name = "display_name"

    @api.depends("scenario_id", "scenario_id.name", "executed_at", "beneficiary_count")
    def _compute_display_name(self):
        for record in self:
            if record.scenario_id and record.executed_at:
                date_str = record.executed_at.strftime("%b %d, %Y %H:%M")
                record.display_name = (
                    f"{record.scenario_id.name} - {date_str} ({record.beneficiary_count:,} beneficiaries)"
                )
            elif record.scenario_id:
                record.display_name = f"{record.scenario_id.name} - Run #{record.id}"
            else:
                record.display_name = f"Run #{record.id}"

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )

    scenario_id = fields.Many2one(
        comodel_name="spp.simulation.scenario",
        string="Scenario",
        required=True,
        ondelete="restrict",
        index=True,
    )
    # Headline scalar fields
    beneficiary_count = fields.Integer(
        string="Beneficiary Count",
        readonly=True,
        index=True,
        help="Number of registrants who would receive benefits.",
    )
    total_registry_count = fields.Integer(
        string="Total Registry Count",
        readonly=True,
        help="Total eligible registrants in the registry.",
    )
    coverage_rate = fields.Float(
        string="Coverage Rate",
        readonly=True,
        help="Percentage of registry targeted (beneficiary_count / total_registry_count).",
    )
    total_cost = fields.Float(
        string="Total Cost",
        readonly=True,
        index=True,
        help="Sum of all entitlement amounts.",
    )
    budget_utilization = fields.Float(
        string="Budget Utilization",
        readonly=True,
        help="Percentage of budget used.",
    )
    gini_coefficient = fields.Float(
        string="Gini Coefficient",
        readonly=True,
        help="Measures benefit inequality. 0 = perfectly equal distribution, "
        "1 = maximum inequality. Lower values indicate more equal distribution.",
    )
    equity_score = fields.Float(
        string="Parity Score",
        readonly=True,
        help="0-100 score measuring demographic coverage parity. "
        "100 = all groups covered proportionally. Points deducted for under-represented groups. "
        "Most meaningful for universal programs, not targeted interventions.",
    )
    has_disparity = fields.Boolean(
        string="Has Under-representation",
        readonly=True,
        help="True if any demographic group has coverage ratio below 0.70 of overall coverage. "
        "For targeted programs, under-representation of non-target groups is expected.",
    )
    leakage_rate = fields.Float(
        string="Leakage Rate",
        readonly=True,
        help="Percentage of recipients who are not part of the ideal population. "
        "Requires ideal_population_expression to be set.",
    )
    undercoverage_rate = fields.Float(
        string="Undercoverage Rate",
        readonly=True,
        help="Percentage of the ideal population that was not targeted. "
        "Requires ideal_population_expression to be set.",
    )
    # Detailed JSON fields
    distribution_json = fields.Json(
        string="Distribution Data",
        readonly=True,
    )
    fairness_json = fields.Json(
        string="Fairness Data",
        readonly=True,
    )
    targeting_efficiency_json = fields.Json(
        string="Targeting Efficiency Data",
        readonly=True,
    )
    geographic_json = fields.Json(
        string="Geographic Data",
        readonly=True,
    )
    metric_results_json = fields.Json(
        string="Custom Metric Results",
        readonly=True,
    )
    # Natural language summaries
    summary_html = fields.Html(
        string="Executive Summary",
        compute="_compute_summary_html",
        store=True,
        readonly=True,
    )
    distribution_summary_html = fields.Html(
        string="Distribution Summary",
        compute="_compute_distribution_summary_html",
        store=True,
        readonly=True,
    )
    distribution_details_html = fields.Html(
        string="Distribution Details",
        compute="_compute_distribution_details_html",
        store=True,
        readonly=True,
    )
    geographic_html = fields.Html(
        string="Geographic Breakdown",
        compute="_compute_geographic_html",
        store=True,
        readonly=True,
    )
    metric_results_html = fields.Html(
        string="Custom Metrics Results",
        compute="_compute_metric_results_html",
        store=True,
        readonly=True,
    )
    targeting_efficiency_html = fields.Html(
        string="Targeting Efficiency Details",
        compute="_compute_targeting_efficiency_html",
        store=True,
        readonly=True,
    )
    # Metadata
    executed_at = fields.Datetime(
        string="Executed At",
        readonly=True,
        default=fields.Datetime.now,
        index=True,
    )
    execution_duration_seconds = fields.Float(
        string="Execution Duration (seconds)",
        readonly=True,
    )
    scenario_snapshot_json = fields.Json(
        string="Scenario Snapshot",
        readonly=True,
        help="Snapshot of scenario configuration at time of execution.",
    )
    # Computed fields for displaying snapshot values in UI
    scenario_snapshot_target_type = fields.Char(
        string="Target Type (Snapshot)",
        compute="_compute_scenario_snapshot_fields",
    )
    scenario_snapshot_targeting_expression = fields.Text(
        string="Targeting Expression (Snapshot)",
        compute="_compute_scenario_snapshot_fields",
    )
    scenario_snapshot_budget_amount = fields.Float(
        string="Budget Amount (Snapshot)",
        compute="_compute_scenario_snapshot_fields",
    )
    scenario_snapshot_budget_strategy = fields.Char(
        string="Budget Strategy (Snapshot)",
        compute="_compute_scenario_snapshot_fields",
    )
    scenario_snapshot_ideal_population_expression = fields.Text(
        string="Ideal Population Expression (Snapshot)",
        compute="_compute_scenario_snapshot_fields",
    )
    scenario_snapshot_entitlement_rules_html = fields.Html(
        string="Entitlement Rules (Snapshot)",
        compute="_compute_scenario_snapshot_fields",
    )
    error_message = fields.Text(
        string="Error Message",
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("running", "Running"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        string="State",
        default="running",
        required=True,
        readonly=True,
        index=True,
    )

    @api.depends(
        "beneficiary_count",
        "total_registry_count",
        "coverage_rate",
        "total_cost",
        "budget_utilization",
        "equity_score",
        "scenario_id.name",
        "scenario_id.budget_amount",
    )
    def _compute_summary_html(self):
        for record in self:
            if record.state != "completed":
                record.summary_html = False
                continue
            scenario_name = record.scenario_id.name or "this scenario"
            target_type_label = "households" if record.scenario_id.target_type == "group" else "individuals"
            coverage_pct = f"{record.coverage_rate:.1f}" if record.coverage_rate else "0.0"
            parts = [
                Markup("<strong>{}</strong> targets <strong>{}</strong> {} ({}% of registry).").format(
                    scenario_name,
                    f"{record.beneficiary_count:,}",
                    target_type_label,
                    coverage_pct,
                ),
            ]
            if record.total_cost:
                parts.append(Markup(" Total estimated cost: <strong>{}</strong>.").format(f"{record.total_cost:,.2f}"))
            if record.budget_utilization and record.scenario_id.budget_amount:
                parts.append(Markup(" Budget utilization: {}%.").format(f"{record.budget_utilization:.1f}"))
            if record.equity_score:
                parity_label = (
                    "proportional"
                    if record.equity_score >= 80
                    else ("some variation" if record.equity_score >= 60 else "significant variation")
                )
                parts.append(
                    Markup(" Parity score: <strong>{}/100</strong> ({}).").format(
                        f"{record.equity_score:.0f}", parity_label
                    )
                )
            record.summary_html = Markup("<p>{}</p>").format(Markup("").join(parts))

    @api.depends("gini_coefficient", "distribution_json")
    def _compute_distribution_summary_html(self):
        for record in self:
            if record.state != "completed" or not record.distribution_json:
                record.distribution_summary_html = False
                continue
            distribution = record.distribution_json or {}
            gini = record.gini_coefficient
            gini_label = (
                "nearly equal" if gini < 0.2 else ("moderately distributed" if gini < 0.4 else "unequally distributed")
            )
            parts = [f"Benefits are <strong>{gini_label}</strong> (Gini coefficient: {gini:.2f})."]
            minimum = distribution.get("minimum", 0)
            maximum = distribution.get("maximum", 0)
            mean = distribution.get("mean", 0)
            median = distribution.get("median", 0)
            if mean:
                parts.append(f" Average amount: {mean:,.2f} (range: {minimum:,.2f} to {maximum:,.2f}).")
            if median and mean:
                skew = (
                    "right-skewed" if mean > median * 1.1 else ("left-skewed" if mean < median * 0.9 else "symmetric")
                )
                parts.append(f" Distribution is {skew} (median: {median:,.2f}).")
            record.distribution_summary_html = "<p>" + "".join(parts) + "</p>"

    @api.depends("distribution_json")
    def _compute_distribution_details_html(self):
        """Render distribution statistics and percentiles as HTML tables."""
        for record in self:
            if record.state != "completed" or not record.distribution_json:
                record.distribution_details_html = False
                continue
            dist = record.distribution_json or {}
            if not dist:
                record.distribution_details_html = "<p class='text-muted'>No distribution data</p>"
                continue

            html_parts = ['<div class="row">']

            # Statistics table
            html_parts.append('<div class="col-md-6"><h5>Statistics</h5>')
            html_parts.append('<table class="table table-sm table-bordered">')
            html_parts.append("<tbody>")
            stats = [
                ("Count", dist.get("count", 0), "{:,}"),
                ("Total", dist.get("total", 0), "{:,.2f}"),
                ("Minimum", dist.get("minimum", 0), "{:,.2f}"),
                ("Maximum", dist.get("maximum", 0), "{:,.2f}"),
                ("Mean", dist.get("mean", 0), "{:,.2f}"),
                ("Median", dist.get("median", 0), "{:,.2f}"),
                ("Std Dev", dist.get("standard_deviation", 0), "{:,.2f}"),
            ]
            for label, value, fmt in stats:
                formatted = fmt.format(value) if value else "-"
                html_parts.append(f"<tr><td><strong>{label}</strong></td><td>{formatted}</td></tr>")
            html_parts.append("</tbody></table></div>")

            # Percentiles table
            percentiles = dist.get("percentiles", {})
            if percentiles:
                html_parts.append('<div class="col-md-6"><h5>Percentiles</h5>')
                html_parts.append('<table class="table table-sm table-bordered">')
                html_parts.append("<tbody>")
                percentile_order = ["p10", "p25", "p50", "p75", "p90"]
                percentile_labels = {
                    "p10": "10th percentile",
                    "p25": "25th percentile (Q1)",
                    "p50": "50th percentile (Median)",
                    "p75": "75th percentile (Q3)",
                    "p90": "90th percentile",
                }
                for key in percentile_order:
                    if key in percentiles:
                        label = percentile_labels.get(key, key)
                        value = percentiles[key]
                        html_parts.append(f"<tr><td><strong>{label}</strong></td><td>{value:,.2f}</td></tr>")
                html_parts.append("</tbody></table></div>")

            html_parts.append("</div>")
            record.distribution_details_html = "".join(html_parts)

    @api.depends("geographic_json")
    def _compute_geographic_html(self):
        """Render geographic breakdown as an HTML table."""
        for record in self:
            if record.state != "completed" or not record.geographic_json:
                record.geographic_html = False
                continue
            geo_data = record.geographic_json or {}
            if not geo_data:
                record.geographic_html = "<p class='text-muted'>No geographic data available</p>"
                continue

            html_parts = [
                Markup('<table class="table table-sm table-bordered">'),
                Markup("<thead><tr>"),
                Markup("<th>Area</th><th>Beneficiaries</th><th>Amount</th><th>Coverage</th>"),
                Markup("</tr></thead><tbody>"),
            ]
            # Sort by beneficiary count descending
            sorted_areas = sorted(geo_data.items(), key=lambda x: x[1].get("count", 0), reverse=True)
            for _area_id, area_info in sorted_areas:
                name = area_info.get("name", "Unknown")
                count = area_info.get("count", 0)
                amount = area_info.get("amount", 0)
                coverage = area_info.get("coverage_rate", 0)
                html_parts.append(
                    Markup("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}%</td></tr>").format(
                        name, f"{count:,}", f"{amount:,.2f}", f"{coverage:.1f}"
                    )
                )
            html_parts.append(Markup("</tbody></table>"))
            record.geographic_html = Markup("").join(html_parts)

    @api.depends("metric_results_json")
    def _compute_metric_results_html(self):
        """Render custom metric results as an HTML table."""
        for record in self:
            if record.state != "completed" or not record.metric_results_json:
                record.metric_results_html = False
                continue
            metrics = record.metric_results_json or {}
            if not metrics:
                record.metric_results_html = "<p class='text-muted'>No custom metrics configured</p>"
                continue

            html_parts = [
                Markup('<table class="table table-sm table-bordered">'),
                Markup("<thead><tr>"),
                Markup("<th>Metric</th><th>Value</th><th>Type</th>"),
                Markup("</tr></thead><tbody>"),
            ]
            for metric_name, metric_data in metrics.items():
                value = metric_data.get("value", 0)
                metric_type = metric_data.get("type", "unknown")
                # Format value based on type
                if metric_type == "coverage":
                    formatted_value = f"{value:.1f}%"
                elif metric_type == "ratio":
                    formatted_value = f"{value:.2f}"
                elif isinstance(value, float):
                    formatted_value = f"{value:,.2f}"
                else:
                    formatted_value = str(value)
                html_parts.append(
                    Markup("<tr><td>{}</td><td>{}</td><td>{}</td></tr>").format(
                        metric_name, formatted_value, metric_type
                    )
                )
            html_parts.append(Markup("</tbody></table>"))
            record.metric_results_html = Markup("").join(html_parts)

    @api.depends("targeting_efficiency_json")
    def _compute_targeting_efficiency_html(self):
        """Render targeting efficiency confusion matrix as an HTML table."""
        for record in self:
            if record.state != "completed" or not record.targeting_efficiency_json:
                record.targeting_efficiency_html = False
                continue
            data = record.targeting_efficiency_json or {}
            if not data or "error" in data:
                record.targeting_efficiency_html = (
                    "<p class='text-muted'>Requires ideal population expression to be set</p>"
                )
                continue

            tp = data.get("true_positives", 0)
            fp = data.get("false_positives", 0)
            fn = data.get("false_negatives", 0)
            total_sim = data.get("total_simulated", 0)
            total_ideal = data.get("total_ideal", 0)

            html_parts = ['<div class="row">']

            # Confusion matrix
            html_parts.append('<div class="col-md-6"><h5>Confusion Matrix</h5>')
            html_parts.append('<table class="table table-sm table-bordered">')
            html_parts.append("<tbody>")
            html_parts.append(
                f"<tr><td><strong>True Positives</strong><br/>"
                f"<small class='text-muted'>Correctly included</small></td><td>{tp:,}</td></tr>"
            )
            html_parts.append(
                f"<tr><td><strong>False Positives (Leakage)</strong><br/>"
                f"<small class='text-muted'>Included but shouldn't be</small></td><td>{fp:,}</td></tr>"
            )
            html_parts.append(
                f"<tr><td><strong>False Negatives (Undercoverage)</strong><br/>"
                f"<small class='text-muted'>Should be included but weren't</small></td><td>{fn:,}</td></tr>"
            )
            html_parts.append("</tbody></table></div>")

            # Totals
            html_parts.append('<div class="col-md-6"><h5>Population Totals</h5>')
            html_parts.append('<table class="table table-sm table-bordered">')
            html_parts.append("<tbody>")
            html_parts.append(f"<tr><td><strong>Simulated (targeted)</strong></td><td>{total_sim:,}</td></tr>")
            html_parts.append(f"<tr><td><strong>Ideal (should be targeted)</strong></td><td>{total_ideal:,}</td></tr>")
            html_parts.append("</tbody></table></div>")

            html_parts.append("</div>")
            record.targeting_efficiency_html = "".join(html_parts)

    @api.depends("scenario_snapshot_json")
    def _compute_scenario_snapshot_fields(self):
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
            snapshot = record.scenario_snapshot_json or {}
            record.scenario_snapshot_target_type = target_type_labels.get(
                snapshot.get("target_type"), snapshot.get("target_type", "")
            )
            record.scenario_snapshot_targeting_expression = snapshot.get("targeting_expression") or ""
            record.scenario_snapshot_budget_amount = snapshot.get("budget_amount") or 0.0
            record.scenario_snapshot_budget_strategy = budget_strategy_labels.get(
                snapshot.get("budget_strategy"), snapshot.get("budget_strategy", "")
            )
            record.scenario_snapshot_ideal_population_expression = snapshot.get("ideal_population_expression") or ""

            # Build HTML table for entitlement rules
            rules = snapshot.get("entitlement_rules") or []
            if rules:
                html_parts = [
                    Markup('<table class="table table-sm table-bordered">'),
                    Markup("<thead><tr>"),
                    Markup("<th>Mode</th><th>Amount</th><th>Multiplier Field</th><th>Max Multiplier</th>"),
                    Markup("<th>CEL Expression</th><th>Condition</th>"),
                    Markup("</tr></thead><tbody>"),
                ]
                amount_mode_labels = {
                    "fixed": "Fixed",
                    "multiplier": "Multiplier",
                    "cel": "CEL Expression",
                }
                for rule in rules:
                    mode = amount_mode_labels.get(rule.get("amount_mode"), rule.get("amount_mode", ""))
                    amount = rule.get("amount") or 0
                    mult_field = rule.get("multiplier_field") or "-"
                    max_mult = rule.get("max_multiplier") or "-"
                    cel_expr = rule.get("amount_cel_expression") or "-"
                    condition = rule.get("condition_cel_expression") or "-"
                    html_parts.append(
                        Markup(
                            "<tr><td>{}</td><td>{}</td><td>{}</td>"
                            "<td>{}</td><td><code>{}</code></td>"
                            "<td><code>{}</code></td></tr>"
                        ).format(
                            mode,
                            f"{amount:,.2f}",
                            mult_field,
                            max_mult,
                            cel_expr,
                            condition,
                        )
                    )
                html_parts.append(Markup("</tbody></table>"))
                record.scenario_snapshot_entitlement_rules_html = Markup("").join(html_parts)
            else:
                record.scenario_snapshot_entitlement_rules_html = (
                    "<p class='text-muted'>No entitlement rules defined</p>"
                )

    def unlink(self):
        """Prevent deletion of simulation runs for audit compliance."""
        raise UserError(_("Simulation runs cannot be deleted. They are preserved for audit compliance."))

    def action_open_comparison_wizard(self):
        """Open the comparison wizard with this run pre-selected."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Compare Simulation Runs",
            "res_model": "spp.simulation.compare.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_run_ids": [Command.link(self.id)],
            },
        }

    def action_compare_with_previous(self):
        """Compare this run with the previous completed run of the same scenario."""
        self.ensure_one()
        previous_runs = self.search(
            [
                ("scenario_id", "=", self.scenario_id.id),
                ("state", "=", "completed"),
                ("id", "!=", self.id),
                ("executed_at", "<", self.executed_at),
            ],
            order="executed_at desc",
            limit=1,
        )
        if not previous_runs:
            raise UserError(_("No previous completed run found for comparison."))
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": f"Compare: {self.scenario_id.name}",
                "run_ids": [Command.set([self.id, previous_runs.id])],
            }
        )
        comparison.action_compute_comparison()
        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.simulation.comparison",
            "res_id": comparison.id,
            "view_mode": "form",
            "target": "current",
        }
