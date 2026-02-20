import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class TargetingEfficiencyService(models.AbstractModel):
    """Service for computing targeting efficiency metrics."""

    _name = "spp.simulation.targeting.efficiency.service"
    _description = "Targeting Efficiency Service"

    @api.model
    def compute_targeting_efficiency(self, scenario, simulated_ids):
        """Compute targeting efficiency against the ideal population.

        Uses set operations on IDs (in memory only):
        - True positives: simulated ∩ ideal
        - False positives (leakage): simulated - ideal
        - False negatives (undercoverage): ideal - simulated
        - True negatives: registry - simulated - ideal

        Returns dict with confusion matrix counts and rates.
        """
        if not scenario.ideal_population_expression:
            return {}

        # Get ideal population IDs
        ideal_ids = self._get_ideal_population_ids(scenario)
        if not ideal_ids:
            return {"error": "Could not determine ideal population."}

        simulated_set = set(simulated_ids)
        ideal_set = set(ideal_ids)

        true_positives = len(simulated_set & ideal_set)
        false_positives = len(simulated_set - ideal_set)  # leakage
        false_negatives = len(ideal_set - simulated_set)  # undercoverage

        total_simulated = len(simulated_set)
        total_ideal = len(ideal_set)

        leakage_rate = false_positives / total_simulated * 100 if total_simulated else 0
        undercoverage_rate = false_negatives / total_ideal * 100 if total_ideal else 0

        return {
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "total_simulated": total_simulated,
            "total_ideal": total_ideal,
            "leakage_rate": leakage_rate,
            "undercoverage_rate": undercoverage_rate,
        }

    @api.model
    def _get_ideal_population_ids(self, scenario):
        """Get the ideal population IDs from the ideal population expression.

        Loads the CEL profile matching the scenario target type so that the
        executor evaluates the expression in the correct model context (same
        pattern used by _execute_targeting in simulation_service.py).
        """
        # Load the CEL profile so the executor has the correct base domain
        # and model context, matching _execute_targeting in simulation_service.py
        profile = "registry_groups" if scenario.target_type == "group" else "registry_individuals"
        registry = self.env["spp.cel.registry"]
        cfg = registry.load_profile(profile)

        executor = self.env["spp.cel.executor"].with_context(cel_cfg=cfg)
        all_ids = []
        try:
            for batch_ids in executor.compile_for_batch(
                "res.partner",
                scenario.ideal_population_expression,
                batch_size=5000,
            ):
                all_ids.extend(batch_ids)
        except Exception:
            _logger.warning(
                "Failed to compute ideal population for scenario '%s'",
                scenario.name,
                exc_info=True,
            )
        return all_ids
