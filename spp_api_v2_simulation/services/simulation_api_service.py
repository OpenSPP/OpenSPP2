# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for simulation scenario management and execution."""

import logging

from odoo import Command

_logger = logging.getLogger(__name__)


class SimulationApiService:
    """Adapter between API layer and spp.simulation.* models."""

    def __init__(self, env):
        """Initialize simulation API service.

        Args:
            env: Odoo environment
        """
        self.env = env

    # --- Templates ---

    def list_templates(self):
        """List active simulation scenario templates.

        Returns:
            list[dict]: List of template info dicts
        """
        templates = (
            self.env["spp.simulation.scenario.template"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [("active", "=", True)],
                order="sequence, name",
            )
        )

        result = []
        for template in templates:
            result.append(
                {
                    "id": template.id,
                    "name": template.name,
                    "description": template.description or None,
                    "category": template.category,
                    "target_type": template.target_type,
                    "targeting_expression": template.targeting_expression,
                    "default_amount": template.default_amount,
                    "default_amount_mode": template.default_amount_mode,
                    "icon": template.icon or "fa-users",
                }
            )

        return result

    # --- Scenario CRUD ---

    def create_scenario(self, data):
        """Create a new simulation scenario.

        If template_id is provided, creates from template with pre-populated
        fields. Otherwise creates with the provided fields and entitlement rules.

        Args:
            data: Dict with scenario creation fields

        Returns:
            dict: Created scenario as serialized dict
        """
        template_id = data.get("template_id")

        if template_id:
            return self._create_from_template(data)
        return self._create_custom(data)

    def _create_from_template(self, data):
        """Create scenario from a template.

        Args:
            data: Dict with at least name and template_id

        Returns:
            dict: Created scenario dict
        """
        template = self.env["spp.simulation.scenario.template"].browse(data["template_id"])
        if not template.exists():
            raise ValueError(f"Template {data['template_id']} not found")

        # Create scenario with template fields
        scenario_vals = {
            "name": data["name"],
            "template_id": template.id,
            "target_type": template.target_type,
            "targeting_expression": template.targeting_expression,
            "ideal_population_expression": template.ideal_population_expression or False,
        }

        if data.get("description"):
            scenario_vals["description"] = data["description"]
        if data.get("category"):
            scenario_vals["category"] = data["category"]
        if data.get("budget_amount"):
            scenario_vals["budget_amount"] = data["budget_amount"]
        if data.get("budget_strategy"):
            scenario_vals["budget_strategy"] = data["budget_strategy"]

        scenario = self.env["spp.simulation.scenario"].create(scenario_vals)

        # Create default entitlement rule from template if it has a default amount
        if template.default_amount:
            self.env["spp.simulation.entitlement.rule"].create(
                {
                    "scenario_id": scenario.id,
                    "name": "Default entitlement",
                    "amount_mode": template.default_amount_mode or "fixed",
                    "amount": template.default_amount,
                }
            )

        return self._serialize_scenario(scenario)

    def _create_custom(self, data):
        """Create a custom scenario without template.

        Args:
            data: Dict with scenario fields and optional entitlement_rules

        Returns:
            dict: Created scenario dict
        """
        scenario_vals = {
            "name": data["name"],
            "target_type": data.get("target_type", "group"),
            "targeting_expression": data.get("targeting_expression", ""),
            "budget_amount": data.get("budget_amount", 0.0),
            "budget_strategy": data.get("budget_strategy", "none"),
        }

        if data.get("description"):
            scenario_vals["description"] = data["description"]
        if data.get("category"):
            scenario_vals["category"] = data["category"]
        if data.get("ideal_population_expression"):
            scenario_vals["ideal_population_expression"] = data["ideal_population_expression"]

        scenario = self.env["spp.simulation.scenario"].create(scenario_vals)

        # Create entitlement rules
        rules_data = data.get("entitlement_rules") or []
        for rule_data in rules_data:
            rule_vals = {
                "scenario_id": scenario.id,
                "name": rule_data.get("name", ""),
                "sequence": rule_data.get("sequence", 10),
                "amount_mode": rule_data.get("amount_mode", "fixed"),
                "amount": rule_data.get("amount", 0.0),
            }
            if rule_data.get("multiplier_field"):
                rule_vals["multiplier_field"] = rule_data["multiplier_field"]
            if rule_data.get("max_multiplier"):
                rule_vals["max_multiplier"] = rule_data["max_multiplier"]
            if rule_data.get("amount_cel_expression"):
                rule_vals["amount_cel_expression"] = rule_data["amount_cel_expression"]
            if rule_data.get("condition_cel_expression"):
                rule_vals["condition_cel_expression"] = rule_data["condition_cel_expression"]

            self.env["spp.simulation.entitlement.rule"].create(rule_vals)

        return self._serialize_scenario(scenario)

    def list_scenarios(self, state=None):
        """List simulation scenarios with optional state filter.

        Args:
            state: Optional state filter ('draft', 'ready', 'archived')

        Returns:
            list[dict]: List of scenario dicts
        """
        domain = []
        if state:
            domain.append(("state", "=", state))

        scenarios = self.env["spp.simulation.scenario"].search(
            domain,
            order="write_date desc",
        )

        return [self._serialize_scenario(s) for s in scenarios]

    def get_scenario(self, scenario_id):
        """Get a single scenario by ID.

        Args:
            scenario_id: Database ID of the scenario

        Returns:
            dict: Scenario dict with full details

        Raises:
            ValueError: If scenario not found
        """
        scenario = self.env["spp.simulation.scenario"].browse(scenario_id)
        if not scenario.exists():
            raise ValueError(f"Scenario {scenario_id} not found")

        return self._serialize_scenario(scenario)

    def update_scenario(self, scenario_id, data):
        """Update a scenario with partial data.

        If entitlement_rules is provided, replaces all existing rules.

        Args:
            scenario_id: Database ID of the scenario
            data: Dict with fields to update

        Returns:
            dict: Updated scenario dict

        Raises:
            ValueError: If scenario not found
        """
        scenario = self.env["spp.simulation.scenario"].browse(scenario_id)
        if not scenario.exists():
            raise ValueError(f"Scenario {scenario_id} not found")

        # Build write vals from non-None fields
        write_vals = {}
        field_mapping = {
            "name": "name",
            "description": "description",
            "category": "category",
            "targeting_expression": "targeting_expression",
            "budget_amount": "budget_amount",
            "budget_strategy": "budget_strategy",
            "ideal_population_expression": "ideal_population_expression",
        }

        for api_field, model_field in field_mapping.items():
            if api_field in data and data[api_field] is not None:
                write_vals[model_field] = data[api_field]

        if write_vals:
            scenario.write(write_vals)

        # Replace entitlement rules if provided
        if "entitlement_rules" in data and data["entitlement_rules"] is not None:
            # Delete existing rules
            scenario.entitlement_rule_ids.unlink()

            # Create new rules
            for rule_data in data["entitlement_rules"]:
                rule_vals = {
                    "scenario_id": scenario.id,
                    "name": rule_data.get("name", ""),
                    "sequence": rule_data.get("sequence", 10),
                    "amount_mode": rule_data.get("amount_mode", "fixed"),
                    "amount": rule_data.get("amount", 0.0),
                }
                if rule_data.get("multiplier_field"):
                    rule_vals["multiplier_field"] = rule_data["multiplier_field"]
                if rule_data.get("max_multiplier"):
                    rule_vals["max_multiplier"] = rule_data["max_multiplier"]
                if rule_data.get("amount_cel_expression"):
                    rule_vals["amount_cel_expression"] = rule_data["amount_cel_expression"]
                if rule_data.get("condition_cel_expression"):
                    rule_vals["condition_cel_expression"] = rule_data["condition_cel_expression"]

                self.env["spp.simulation.entitlement.rule"].create(rule_vals)

        # Refresh to get updated computed fields
        scenario.invalidate_recordset()
        return self._serialize_scenario(scenario)

    # --- Simulation Execution ---

    def run_simulation(self, scenario_id):
        """Execute a simulation on a scenario.

        Auto-transitions draft -> ready if targeting expression is set.
        Then delegates to spp.simulation.service.execute_simulation().

        Args:
            scenario_id: Database ID of the scenario

        Returns:
            dict: Run headline metrics

        Raises:
            ValueError: If scenario not found or cannot be run
        """
        scenario = self.env["spp.simulation.scenario"].browse(scenario_id)
        if not scenario.exists():
            raise ValueError(f"Scenario {scenario_id} not found")

        # Auto-transition draft -> ready if possible
        if scenario.state == "draft" and scenario.targeting_expression:
            scenario.action_set_ready()

        if scenario.state != "ready":
            raise ValueError(f"Scenario must be in 'ready' state to run. Current state: {scenario.state}")

        # Execute simulation
        simulation_service = self.env["spp.simulation.service"]
        run = simulation_service.execute_simulation(scenario)

        return self._serialize_run_headline(run)

    def get_run(self, run_id):
        """Get full details of a simulation run.

        Args:
            run_id: Database ID of the run

        Returns:
            dict: Full run details including JSON breakdowns

        Raises:
            ValueError: If run not found
        """
        run = self.env["spp.simulation.run"].browse(run_id)
        if not run.exists():
            raise ValueError(f"Run {run_id} not found")

        return self._serialize_run_detail(run)

    # --- Comparison ---

    def compare_runs(self, run_ids, name=None):
        """Compare multiple simulation runs.

        Creates an spp.simulation.comparison record, computes comparison
        data, and returns structured result.

        Args:
            run_ids: List of run IDs to compare (minimum 2)
            name: Optional comparison name (auto-generated if None)

        Returns:
            dict: Comparison result with per-run metrics and overlap

        Raises:
            ValueError: If fewer than 2 run IDs provided
        """
        if len(run_ids) < 2:
            raise ValueError("At least 2 run IDs are required for comparison")

        # Verify runs exist
        runs = self.env["spp.simulation.run"].browse(run_ids)
        if len(runs.exists()) != len(run_ids):
            missing = set(run_ids) - set(runs.exists().ids)
            raise ValueError(f"Runs not found: {missing}")

        # Auto-generate name if not provided
        if not name:
            scenario_names = [r.scenario_id.name for r in runs]
            name = f"Comparison: {' vs '.join(scenario_names[:3])}"
            if len(scenario_names) > 3:
                name += f" (+{len(scenario_names) - 3} more)"

        # Create comparison record
        comparison = self.env["spp.simulation.comparison"].create(
            {
                "name": name,
                "run_ids": [Command.set(run_ids)],
            }
        )

        # Compute comparison data
        comparison.action_compute_comparison()

        return self._serialize_comparison(comparison)

    # --- Serializers ---

    def _serialize_scenario(self, scenario):
        """Serialize a scenario record to API dict.

        Args:
            scenario: spp.simulation.scenario record

        Returns:
            dict: Serialized scenario
        """
        return {  # nosemgrep: odoo-expose-database-id
            "id": scenario.id,
            "name": scenario.name,
            "description": scenario.description or None,
            "category": scenario.category or None,
            "template_id": scenario.template_id.id if scenario.template_id else None,
            "target_type": scenario.target_type,
            "targeting_expression": scenario.targeting_expression or None,
            "budget_amount": scenario.budget_amount,
            "budget_strategy": scenario.budget_strategy,
            "ideal_population_expression": scenario.ideal_population_expression or None,
            "state": scenario.state,
            "targeting_preview_count": scenario.targeting_preview_count,
            "entitlement_rules": [self._serialize_entitlement_rule(rule) for rule in scenario.entitlement_rule_ids],
            "run_count": scenario.run_count,
        }

    def _serialize_entitlement_rule(self, rule):
        """Serialize an entitlement rule record to API dict.

        Args:
            rule: spp.simulation.entitlement.rule record

        Returns:
            dict: Serialized rule
        """
        return {  # nosemgrep: odoo-expose-database-id
            "id": rule.id,
            "name": rule.name or None,
            "sequence": rule.sequence,
            "amount_mode": rule.amount_mode,
            "amount": rule.amount,
            "multiplier_field": rule.multiplier_field or None,
            "max_multiplier": rule.max_multiplier,
            "amount_cel_expression": rule.amount_cel_expression or None,
            "condition_cel_expression": rule.condition_cel_expression or None,
        }

    def _serialize_run_headline(self, run):
        """Serialize a run record to headline metrics dict.

        Args:
            run: spp.simulation.run record

        Returns:
            dict: Headline run metrics
        """
        return {  # nosemgrep: odoo-expose-database-id
            "id": run.id,
            "scenario_id": run.scenario_id.id,
            "scenario_name": run.scenario_id.name,
            "state": run.state,
            "beneficiary_count": run.beneficiary_count,
            "total_registry_count": run.total_registry_count,
            "coverage_rate": run.coverage_rate,
            "total_cost": run.total_cost,
            "budget_utilization": run.budget_utilization,
            "gini_coefficient": run.gini_coefficient,
            "equity_score": run.equity_score,
            "has_disparity": run.has_disparity,
            "executed_at": run.executed_at.isoformat() if run.executed_at else None,
            "execution_duration_seconds": run.execution_duration_seconds,
            "error_message": run.error_message or None,
        }

    def _serialize_run_detail(self, run):
        """Serialize a run record to full detail dict.

        Args:
            run: spp.simulation.run record

        Returns:
            dict: Full run details including JSON breakdowns
        """
        result = self._serialize_run_headline(run)
        result.update(
            {
                "leakage_rate": run.leakage_rate,
                "undercoverage_rate": run.undercoverage_rate,
                "distribution_json": run.distribution_json or None,
                "fairness_json": run.fairness_json or None,
                "targeting_efficiency_json": run.targeting_efficiency_json or None,
                "geographic_json": run.geographic_json or None,
                "metric_results_json": run.metric_results_json or None,
                "scenario_snapshot_json": run.scenario_snapshot_json or None,
            }
        )
        return result

    def _serialize_comparison(self, comparison):
        """Serialize a comparison record to API dict.

        Args:
            comparison: spp.simulation.comparison record

        Returns:
            dict: Comparison result
        """
        # Extract per-run metrics from comparison_json
        runs_data = []
        comparison_data = comparison.comparison_json or {}
        for run_info in comparison_data.get("runs", []):
            runs_data.append(
                {
                    "run_id": run_info.get("run_id"),
                    "scenario_name": run_info.get("scenario_name", ""),
                    "beneficiary_count": run_info.get("beneficiary_count", 0),
                    "total_cost": run_info.get("total_cost", 0.0),
                    "coverage_rate": run_info.get("coverage_rate", 0.0),
                    "equity_score": run_info.get("equity_score", 0.0),
                    "gini_coefficient": run_info.get("gini_coefficient", 0.0),
                    "has_disparity": run_info.get("has_disparity", False),
                    "leakage_rate": run_info.get("leakage_rate", 0.0),
                    "undercoverage_rate": run_info.get("undercoverage_rate", 0.0),
                    "budget_utilization": run_info.get("budget_utilization", 0.0),
                    "executed_at": run_info.get("executed_at"),
                }
            )

        # Extract overlap data from overlap_count_json
        overlap_data = []
        overlap_json = comparison.overlap_count_json or {}
        for _key, overlap_info in overlap_json.items():
            overlap_data.append(
                {
                    "run_a_id": overlap_info.get("run_a_id"),
                    "run_a_name": overlap_info.get("run_a_name", ""),
                    "run_b_id": overlap_info.get("run_b_id"),
                    "run_b_name": overlap_info.get("run_b_name", ""),
                    "overlap_count": overlap_info.get("overlap_count", 0),
                    "union_count": overlap_info.get("union_count", 0),
                    "jaccard_index": overlap_info.get("jaccard_index", 0.0),
                }
            )

        return {  # nosemgrep: odoo-expose-database-id
            "id": comparison.id,
            "name": comparison.name,
            "runs": runs_data,
            "overlap": overlap_data,
            "staleness_warning": comparison.staleness_warning or None,
        }
