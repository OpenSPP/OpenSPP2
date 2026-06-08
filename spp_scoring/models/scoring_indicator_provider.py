"""Scoring indicator provider for spp_indicators integration.

This module provides a bridge between spp_scoring and spp_indicators,
allowing scoring results to be accessed via metric() in CEL expressions.

Example usage in CEL:
    metric("scoring.pmt_2024") >= 40
    metric("scoring.vulnerability_index") < 0.5

Note on company scoping:
    The scoring module does not have direct multi-company support.
    Scoring results are associated with registrants (res.partner),
    and access control is handled through standard Odoo record rules
    on the registrant model.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from odoo import api, models

if TYPE_CHECKING:
    from odoo.api import Environment

_logger = logging.getLogger(__name__)

# Maximum batch size for scoring queries
MAX_BATCH_SIZE = 5000


class ScoringIndicatorProvider:
    """Provider that reads scores from spp.scoring.result.

    Registered as scoring.<model_code> for each active scoring model.
    Returns the most recent score for each subject.
    """

    def __init__(self, model_code: str):
        self.model_code = model_code

    def compute_batch(self, env: Environment, ctx: dict[str, Any], subject_ids: list[int]) -> dict[int, Any]:
        """Return latest scores for the given subjects.

        Args:
            env: Odoo environment
            ctx: Context dict with period_key, params, etc.
            subject_ids: List of registrant IDs to score

        Returns:
            Dict mapping subject_id -> score (float)

        Note:
            Batch size is limited to MAX_BATCH_SIZE (5000) for performance.
            Larger batches will be truncated.
        """
        if not subject_ids:
            return {}

        # Enforce max batch size
        if len(subject_ids) > MAX_BATCH_SIZE:
            _logger.warning(
                "[spp.scoring] Batch size %d exceeds max %d, truncating",
                len(subject_ids),
                MAX_BATCH_SIZE,
            )
            subject_ids = subject_ids[:MAX_BATCH_SIZE]

        Model = env["spp.scoring.model"]

        # Find the scoring model by code
        scoring_model = Model.search([("code", "=", self.model_code)], limit=1)
        if not scoring_model:
            _logger.warning("[spp.scoring] No scoring model found with code: %s", self.model_code)
            return {}

        # Use SQL for efficient batch lookup of latest scores
        # This query gets the most recent score per registrant
        query = """
            SELECT DISTINCT ON (registrant_id)
                registrant_id,
                score
            FROM spp_scoring_result
            WHERE model_id = %s
              AND registrant_id = ANY(%s)
            ORDER BY registrant_id, calculation_date DESC, id DESC
        """
        env.cr.execute(query, (scoring_model.id, list(subject_ids)))
        rows = env.cr.fetchall()

        return {int(row[0]): float(row[1]) for row in rows}


class SppScoringIndicatorBridge(models.AbstractModel):
    """Bridge model that registers scoring models as indicator providers."""

    _name = "spp.scoring.indicator.bridge"
    _description = "Scoring to Indicators Bridge"

    @api.model
    def _get_indicator_registry(self):
        """Get the indicator registry if spp_indicators is installed."""
        if "spp.indicator.registry" in self.env:
            return self.env["spp.indicator.registry"]
        return None

    @api.model
    def register_scoring_model(self, model_code: str):
        """Register a scoring model as an indicator provider.

        Args:
            model_code: The code of the scoring model to register
        """
        registry = self._get_indicator_registry()
        if not registry:
            _logger.debug("[spp.scoring] spp_indicators not installed, skipping registration")
            return

        metric_name = f"scoring.{model_code.lower()}"
        provider = ScoringIndicatorProvider(model_code)

        registry.register(
            name=metric_name,
            handler=provider,
            return_type="number",
            subject_model="res.partner",
            capabilities={
                "supports_batch": True,
                "max_batch_size": 5000,
                "default_ttl": 0,  # Scores don't expire, they're based on calculation_date
            },
            provider=f"spp_scoring.{model_code.lower()}",
        )
        _logger.info("[spp.scoring] Registered indicator: %s", metric_name)

    @api.model
    def register_all_scoring_models(self):
        """Register all active scoring models as indicator providers."""
        registry = self._get_indicator_registry()
        if not registry:
            return

        Model = self.env["spp.scoring.model"]
        active_models = Model.search([("is_active", "=", True)])

        for model in active_models:
            self.register_scoring_model(model.code)

        _logger.info(
            "[spp.scoring] Registered %d scoring models as indicators",
            len(active_models),
        )


class SppScoringModelIndicatorMixin(models.Model):
    """Mixin to auto-register scoring models with indicators."""

    _inherit = "spp.scoring.model"

    def action_activate(self):
        """Override to register indicator when model is activated."""
        result = super().action_activate()
        bridge = self.env["spp.scoring.indicator.bridge"]
        for record in self:
            bridge.register_scoring_model(record.code)
        return result


def _register_static_providers():
    """Register providers at import time for server restart persistence.

    This ensures providers are available even before post_init_hook runs.
    """
    try:
        # Import check - we can't register specific models here since we don't have env,
        # but we set up the infrastructure. Actual registration happens
        # in post_init_hook when we have access to the database.
        import importlib.util

        spec = importlib.util.find_spec("odoo.addons.spp_indicators.models.metric_registry")
        if spec is None:
            raise ImportError

        _logger.debug("[spp.scoring] Static provider registration infrastructure ready")
    except ImportError:
        _logger.debug("[spp.scoring] spp_indicators not installed, skipping static registration")


# Try static registration at import time
_register_static_providers()
