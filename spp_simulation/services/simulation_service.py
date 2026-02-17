import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SimulationService(models.AbstractModel):
    """Orchestration service for running targeting simulations.

    This service orchestrates the simulation workflow but delegates heavy
    computation to spp.aggregation.service for statistics, distribution,
    and fairness analysis.
    """

    _name = "spp.simulation.service"
    _description = "Simulation Service"

    @api.model
    def execute_simulation(self, scenario):
        """Execute a full simulation for a scenario.

        Pipeline:
        1. Targeting (CEL -> compile_for_batch -> IDs)
        2. Entitlements (fixed/multiplier via SQL, CEL via batch eval)
        3. Budget adjustment
        4. Distribution stats
        5. Fairness analysis
        6. Targeting efficiency
        7. Custom metrics
        8. Geographic breakdown
        9. Summary generation

        Returns:
            spp.simulation.run record
        """
        start_time = time.time()

        # Create run record
        snapshot = self._build_scenario_snapshot(scenario)
        run = self.env["spp.simulation.run"].create(
            {
                "scenario_id": scenario.id,
                "state": "running",
                "scenario_snapshot_json": snapshot,
            }
        )

        try:
            # Step 1: Targeting
            beneficiary_ids = self._execute_targeting(scenario)
            total_registry_count = self._get_total_registry_count(scenario)

            beneficiary_count = len(beneficiary_ids)
            coverage_rate = (beneficiary_count / total_registry_count * 100) if total_registry_count else 0.0

            # Step 2: Entitlements
            amounts = self._compute_entitlements(scenario, beneficiary_ids)

            # Step 3: Budget adjustment
            amounts = self._apply_budget_strategy(scenario, amounts)

            # Step 4: Distribution stats
            # Use spp.metrics.distribution for computation
            distribution_service = self.env["spp.metrics.distribution"]
            distribution_data = distribution_service.compute_distribution(amounts)
            gini = distribution_data.get("gini_coefficient", 0.0)

            # Step 5: Fairness analysis
            # Use spp.metrics.fairness for computation
            fairness_service = self.env["spp.metrics.fairness"]
            # Get base domain for population
            profile = "registry_groups" if scenario.target_type == "group" else "registry_individuals"
            registry = self.env["spp.cel.registry"]
            cfg = registry.load_profile(profile)
            base_domain = cfg.get("base_domain", [])
            fairness_data = fairness_service.compute_fairness(beneficiary_ids, base_domain)
            equity_score = fairness_data.get("equity_score", 100.0)
            has_disparity = fairness_data.get("has_disparity", False)

            # Step 6: Targeting efficiency
            targeting_data = {}
            leakage_rate = 0.0
            undercoverage_rate = 0.0
            if scenario.ideal_population_expression:
                efficiency_service = self.env["spp.simulation.targeting.efficiency.service"]
                targeting_data = efficiency_service.compute_targeting_efficiency(scenario, set(beneficiary_ids))
                leakage_rate = targeting_data.get("leakage_rate", 0.0)
                undercoverage_rate = targeting_data.get("undercoverage_rate", 0.0)

            # Step 7: Custom metrics
            metric_results = self._compute_custom_metrics(scenario, beneficiary_ids)

            # Step 8: Geographic breakdown
            geographic_data = self._compute_geographic_breakdown(scenario, beneficiary_ids, amounts)

            # Calculate budget utilization
            total_cost = sum(amounts) if amounts else 0.0
            budget_utilization = 0.0
            if scenario.budget_amount and scenario.budget_amount > 0:
                budget_utilization = total_cost / scenario.budget_amount * 100

            duration = time.time() - start_time

            run.write(
                {
                    "state": "completed",
                    "beneficiary_count": beneficiary_count,
                    "total_registry_count": total_registry_count,
                    "coverage_rate": coverage_rate,
                    "total_cost": total_cost,
                    "budget_utilization": budget_utilization,
                    "gini_coefficient": gini,
                    "equity_score": equity_score,
                    "has_disparity": has_disparity,
                    "leakage_rate": leakage_rate,
                    "undercoverage_rate": undercoverage_rate,
                    "distribution_json": distribution_data,
                    "fairness_json": fairness_data,
                    "targeting_efficiency_json": targeting_data,
                    "geographic_json": geographic_data,
                    "metric_results_json": metric_results,
                    "execution_duration_seconds": duration,
                    "executed_at": fields.Datetime.now(),
                }
            )
            _logger.info(
                "Simulation completed for scenario '%s': %d beneficiaries, cost %.2f, " "equity %.0f, duration %.2fs",
                scenario.name,
                beneficiary_count,
                total_cost,
                equity_score,
                duration,
            )
        except Exception as exc:
            duration = time.time() - start_time
            _logger.error(
                "Simulation failed for scenario '%s': %s",
                scenario.name,
                exc,
                exc_info=True,
            )
            run.write(
                {
                    "state": "failed",
                    "error_message": str(exc),
                    "execution_duration_seconds": duration,
                    "executed_at": fields.Datetime.now(),
                }
            )
        return run

    def _build_scenario_snapshot(self, scenario):
        """Build a JSON snapshot of the scenario configuration."""
        rules = []
        for rule in scenario.entitlement_rule_ids:
            rules.append(
                {
                    "amount_mode": rule.amount_mode,
                    "amount": rule.amount,
                    "multiplier_field": rule.multiplier_field,
                    "max_multiplier": rule.max_multiplier,
                    "amount_cel_expression": rule.amount_cel_expression,
                    "condition_cel_expression": rule.condition_cel_expression,
                }
            )
        return {
            "name": scenario.name,
            "target_type": scenario.target_type,
            "targeting_expression": scenario.targeting_expression,
            "budget_amount": scenario.budget_amount,
            "budget_strategy": scenario.budget_strategy,
            "entitlement_rules": rules,
            "ideal_population_expression": scenario.ideal_population_expression,
        }

    def _get_cel_profile(self, scenario):
        """Get the CEL profile name based on scenario target type."""
        return "registry_groups" if scenario.target_type == "group" else "registry_individuals"

    def _execute_targeting(self, scenario):
        """Execute the targeting expression and return all matching IDs.

        NOTE: In Phase 6, this should use spp.aggregation.scope for unified
        targeting. For now, it continues using CEL directly for backward
        compatibility.
        """
        # Load the CEL profile configuration
        profile = self._get_cel_profile(scenario)
        registry = self.env["spp.cel.registry"]
        cfg = registry.load_profile(profile)

        # Execute with profile context
        executor = self.env["spp.cel.executor"].with_context(cel_cfg=cfg)
        all_ids = []
        for batch_ids in executor.compile_for_batch("res.partner", scenario.targeting_expression, batch_size=5000):
            all_ids.extend(batch_ids)
        return all_ids

    def _get_total_registry_count(self, scenario):
        """Get the total count of registrants in the registry.

        Uses the same base domain as the CEL profile to ensure consistency.
        """
        profile = self._get_cel_profile(scenario)
        registry = self.env["spp.cel.registry"]
        cfg = registry.load_profile(profile)
        base_domain = cfg.get("base_domain", [])
        return self.env["res.partner"].search_count(base_domain)

    def _compute_entitlements(self, scenario, beneficiary_ids):
        """Compute entitlement amounts for all beneficiaries.

        For fixed/multiplier modes: use SQL aggregation for speed.
        For CEL mode: use per-record evaluation in batches of 5000.
        """
        if not beneficiary_ids or not scenario.entitlement_rule_ids:
            return [0.0] * len(beneficiary_ids)

        # Initialize per-beneficiary amounts
        amounts_by_id = {beneficiary_id: 0.0 for beneficiary_id in beneficiary_ids}

        for rule in scenario.entitlement_rule_ids:
            # Determine which beneficiaries this rule applies to
            applicable_ids = beneficiary_ids
            if rule.condition_cel_expression:
                applicable_ids = self._filter_by_condition(
                    rule.condition_cel_expression,
                    beneficiary_ids,
                    scenario.target_type,
                )

            if rule.amount_mode == "fixed":
                for beneficiary_id in applicable_ids:
                    amounts_by_id[beneficiary_id] += rule.amount

            elif rule.amount_mode == "multiplier":
                self._apply_multiplier_rule(rule, applicable_ids, amounts_by_id)

            elif rule.amount_mode == "cel":
                self._apply_cel_rule(rule, applicable_ids, amounts_by_id)

        return [amounts_by_id[beneficiary_id] for beneficiary_id in beneficiary_ids]

    def _filter_by_condition(self, condition_expression, beneficiary_ids, target_type):
        """Filter beneficiary IDs using a CEL condition expression."""
        cel_service = self.env["spp.cel.service"]
        profile = "registry_groups" if target_type == "group" else "registry_individuals"
        try:
            result = cel_service.compile_expression(
                condition_expression,
                profile=profile,
                base_domain=[("id", "in", beneficiary_ids)],
                limit=-1,
            )
            return result.get("ids", [])
        except Exception:
            _logger.warning(
                "Condition expression failed, including all beneficiaries",
                exc_info=True,
            )
            return beneficiary_ids

    def _apply_multiplier_rule(self, rule, applicable_ids, amounts_by_id):
        """Apply a multiplier rule to compute amounts based on a field value."""
        if not applicable_ids:
            return
        field_name = rule.multiplier_field
        # Validate the field exists
        partner_model = self.env["res.partner"]
        if field_name not in partner_model._fields:
            _logger.warning("Multiplier field '%s' does not exist on res.partner", field_name)
            return

        batch_size = 5000
        for i in range(0, len(applicable_ids), batch_size):
            batch = applicable_ids[i : i + batch_size]
            records = partner_model.browse(batch)
            for record in records:
                value = getattr(record, field_name, 0) or 0
                if isinstance(value, int | float):
                    if rule.max_multiplier and rule.max_multiplier > 0:
                        value = min(value, rule.max_multiplier)
                    amounts_by_id[record.id] += rule.amount * value

    def _apply_cel_rule(self, rule, applicable_ids, amounts_by_id):
        """Apply a CEL amount rule by evaluating per-record in batches."""
        if not applicable_ids:
            return
        cel_service = self.env["spp.cel.service"]
        partner_model = self.env["res.partner"]

        batch_size = 5000
        for i in range(0, len(applicable_ids), batch_size):
            batch = applicable_ids[i : i + batch_size]
            records = partner_model.browse(batch)
            for record in records:
                try:
                    context = {"me": record, "base_amount": rule.amount or 0.0}
                    result = cel_service.evaluate_expression(rule.amount_cel_expression, context)
                    if isinstance(result, int | float) and result >= 0:
                        amounts_by_id[record.id] += float(result)
                except Exception:
                    _logger.debug(
                        "CEL amount evaluation failed for record %d",
                        record.id,
                        exc_info=True,
                    )

    def _apply_budget_strategy(self, scenario, amounts):
        """Apply budget constraints to the computed amounts."""
        if scenario.budget_strategy == "none" or not scenario.budget_amount:
            return amounts

        total = sum(amounts)
        if total <= 0:
            return amounts

        budget = scenario.budget_amount

        if scenario.budget_strategy == "cap_total":
            if total <= budget:
                return amounts
            # Include beneficiaries at full amount until budget runs out
            capped = []
            remaining_budget = budget
            for amount in amounts:
                if remaining_budget >= amount:
                    capped.append(amount)
                    remaining_budget -= amount
                else:
                    capped.append(0.0)
            return capped

        elif scenario.budget_strategy == "proportional_reduction":
            if total <= budget:
                return amounts
            # Reduce all amounts proportionally to fit within budget
            ratio = budget / total
            return [a * ratio for a in amounts]

        return amounts

    def _compute_custom_metrics(self, scenario, beneficiary_ids):
        """Evaluate custom metrics for the simulation."""
        results = {}
        cel_service = self.env["spp.cel.service"]
        profile = "registry_groups" if scenario.target_type == "group" else "registry_individuals"

        for metric in scenario.metric_ids:
            try:
                if metric.metric_type == "aggregate":
                    result = cel_service.compile_expression(
                        metric.cel_expression,
                        profile=profile,
                        base_domain=[("id", "in", beneficiary_ids)],
                        limit=0,
                    )
                    count = result.get("count", 0)
                    results[metric.name] = {
                        "type": "aggregate",
                        "aggregation": metric.aggregation,
                        "value": count,
                    }

                elif metric.metric_type == "coverage":
                    result = cel_service.compile_expression(
                        metric.cel_expression,
                        profile=profile,
                        base_domain=[("id", "in", beneficiary_ids)],
                        limit=0,
                    )
                    matching = result.get("count", 0)
                    total = len(beneficiary_ids) if beneficiary_ids else 1
                    results[metric.name] = {
                        "type": "coverage",
                        "matching": matching,
                        "total": total,
                        "rate": matching / total * 100 if total else 0,
                    }

                elif metric.metric_type == "ratio":
                    numerator_result = cel_service.compile_expression(
                        metric.numerator_expression,
                        profile=profile,
                        base_domain=[("id", "in", beneficiary_ids)],
                        limit=0,
                    )
                    denominator_result = cel_service.compile_expression(
                        metric.denominator_expression,
                        profile=profile,
                        base_domain=[("id", "in", beneficiary_ids)],
                        limit=0,
                    )
                    numerator = numerator_result.get("count", 0)
                    denominator = denominator_result.get("count", 0)
                    results[metric.name] = {
                        "type": "ratio",
                        "numerator": numerator,
                        "denominator": denominator,
                        "ratio": numerator / denominator if denominator else 0,
                    }
            except Exception:
                _logger.warning(
                    "Custom metric '%s' evaluation failed",
                    metric.name,
                    exc_info=True,
                )
                results[metric.name] = {"type": metric.metric_type, "error": True}

        return results

    def _compute_geographic_breakdown(self, scenario, beneficiary_ids, amounts):
        """Compute per-area aggregated counts and amounts."""
        if not beneficiary_ids:
            return {}

        partner_model = self.env["res.partner"]
        amount_map = dict(zip(beneficiary_ids, amounts, strict=False))

        # Build area_id -> list of partner IDs mapping using read()
        beneficiary_records = partner_model.browse(beneficiary_ids).read(["area_id"])
        area_to_ids = {}
        for record in beneficiary_records:
            area_val = record.get("area_id")
            if area_val:
                area_key = str(area_val[0])
                area_name = area_val[1]
            else:
                area_key = "none"
                area_name = "No Area"
            if area_key not in area_to_ids:
                area_to_ids[area_key] = {"name": area_name, "ids": []}
            area_to_ids[area_key]["ids"].append(record["id"])

        geographic_data = {}
        total_count = len(beneficiary_ids)
        for area_key, area_info in area_to_ids.items():
            ids = area_info["ids"]
            count = len(ids)
            area_amount = sum(amount_map.get(pid, 0) for pid in ids)
            geographic_data[area_key] = {
                "name": area_info["name"],
                "count": count,
                "amount": area_amount,
                "coverage_rate": count / total_count * 100 if total_count else 0,
            }

        return geographic_data

    @api.model
    def convert_to_program(self, scenario, options):
        """Convert a simulation scenario into a real program.

        Uses the program creation wizard programmatically to ensure all
        managers (eligibility, cycle, entitlement, program) are created
        consistently with wizard-based creation.

        Args:
            scenario: spp.simulation.scenario record
            options: dict with optional overrides (name, currency_code,
                     is_one_time_distribution, import_beneficiaries,
                     rrule_type, cycle_duration, day, month_by, weekday,
                     byday, mon-sun)

        Returns:
            dict with keys: program (record), warnings (list[str])

        Raises:
            UserError: if preconditions are not met
        """
        scenario.ensure_one()
        warnings = []

        # Validate preconditions
        self._validate_conversion_preconditions(scenario, options)

        # Resolve currency
        currency = self._resolve_currency(options)

        # Build wizard values
        wizard_vals = self._build_wizard_values(scenario, options, currency)

        # Create wizard transient record
        wizard = self.env["spp.program.create.wizard"].create(wizard_vals)

        # Create cash entitlement items on the wizard
        self._create_wizard_entitlement_items(wizard, scenario, warnings)

        # Execute wizard to create program
        action = wizard.create_program()
        program = self.env["spp.program"].browse(action["res_id"])

        # Link scenario to converted program
        scenario.converted_program_id = program.id

        # Post chatter message
        scenario.message_post(
            body=_("Converted to program: %s") % program.name,
        )

        _logger.info(
            "Scenario '%s' (id=%d) converted to program '%s' (id=%d)",
            scenario.name,
            scenario.id,
            program.name,
            program.id,
        )

        return {"program": program, "warnings": warnings}

    def _validate_conversion_preconditions(self, scenario, options):
        """Validate that the scenario can be converted."""
        if scenario.state != "ready":
            raise UserError(_("Only scenarios in 'ready' state can be converted to programs."))

        if scenario.converted_program_id:
            raise UserError(_("Scenario already converted to program '%s'.") % scenario.converted_program_id.name)

        if not scenario.entitlement_rule_ids:
            raise UserError(_("Scenario must have at least one entitlement rule to convert."))

    def _resolve_currency(self, options):
        """Resolve currency from options or use company default."""
        currency_code = options.get("currency_code")
        if currency_code:
            currency = self.env["res.currency"].search([("name", "=", currency_code)], limit=1)
            if not currency:
                raise UserError(_("Currency code '%s' not found.") % currency_code)
            return currency
        return self.env.company.currency_id

    def _build_wizard_values(self, scenario, options, currency):
        """Build values dict for the program creation wizard."""
        name = options.get("name") or scenario.name
        is_one_time = options.get("is_one_time_distribution", False)
        import_beneficiaries = "yes" if options.get("import_beneficiaries") else "no"

        vals = {
            "name": name,
            "currency_id": currency.id,
            "target_type": scenario.target_type,
            "eligibility_cel_expression": scenario.targeting_expression,
            "entitlement_type": "cash",
            "is_one_time_distribution": is_one_time,
            "import_beneficiaries": import_beneficiaries,
            "auto_approve_entitlements": False,
            "rrule_type": options.get("rrule_type", "monthly"),
            "cycle_duration": options.get("cycle_duration", 1),
            "day": options.get("day", 1),
            "month_by": options.get("month_by", "date"),
        }

        # Recurrence fields
        if options.get("weekday"):
            vals["weekday"] = options["weekday"]
        if options.get("byday"):
            vals["byday"] = options["byday"]

        # Weekly day flags
        for day_field in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
            if options.get(day_field):
                vals[day_field] = options[day_field]

        return vals

    def _create_wizard_entitlement_items(self, wizard, scenario, warnings):
        """Create cash entitlement items on the wizard from scenario rules."""
        CashItem = self.env["spp.program.create.wizard.entitlement.cash.item"]

        for rule in scenario.entitlement_rule_ids:
            item_vals = {
                "program_id": wizard.id,
                "sequence": rule.sequence,
                "amount": rule.amount,
            }

            if rule.amount_mode == "cel":
                item_vals["amount_mode"] = "cel"
                item_vals["amount_cel_expression"] = rule.amount_cel_expression or ""

            elif rule.amount_mode == "multiplier":
                # Multiplier mode cannot be directly mapped because
                # simulation rules use a Char field name while wizard items
                # use a Many2one to ir.model.fields. Fall back to fixed.
                warnings.append(
                    _(
                        "Entitlement rule '%s' uses multiplier mode with field '%s'. "
                        "Multiplier rules cannot be automatically converted. "
                        "Using fixed amount (%.2f) instead."
                    )
                    % (
                        rule.name or f"Rule #{rule.sequence}",
                        rule.multiplier_field or "unknown",
                        rule.amount,
                    )
                )

            # Map condition CEL expression
            if rule.condition_cel_expression:
                item_vals["has_condition"] = True
                item_vals["condition_mode"] = "cel"
                item_vals["cel_condition"] = rule.condition_cel_expression

            CashItem.create(item_vals)
