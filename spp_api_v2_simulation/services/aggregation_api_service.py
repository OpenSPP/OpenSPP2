# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for delegating to the aggregation engine."""

import json
import logging

from odoo.addons.spp_aggregation.services import build_explicit_scope

_logger = logging.getLogger(__name__)


class AggregationApiService:
    """Thin adapter between API layer and spp.aggregation.service."""

    def __init__(self, env):
        """Initialize aggregation API service.

        Args:
            env: Odoo environment
        """
        self.env = env

    def compute_aggregation(self, scope_dict, statistics=None, group_by=None):
        """Compute aggregation for a scope with optional breakdown.

        Translates the API-level scope (target_type, cel_expression, area_id)
        into the aggregation engine's scope format (scope_type, cel_profile).

        Args:
            scope_dict: Inline scope definition dict with target_type, cel_expression, area_id
            statistics: List of statistic names to compute (or None for defaults)
            group_by: List of dimension names for breakdown (max 3)

        Returns:
            dict: Aggregation result with total_count, statistics, breakdown, etc.
        """
        engine_scope = self._build_engine_scope(scope_dict)
        # nosemgrep: odoo-sudo-without-context
        aggregation_service = self.env["spp.aggregation.service"].sudo()
        result = aggregation_service.compute_aggregation(
            scope=engine_scope,
            statistics=statistics,
            group_by=group_by,
            context="api",
        )
        return result

    @staticmethod
    def _parse_value_labels(value):
        """Parse value_labels_json which may be a dict, JSON string, or None."""
        if not value:
            return None
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def _build_engine_scope(self, scope_dict):
        """Translate API scope dict to aggregation engine scope dict.

        Uses explicit scope with Odoo ORM search to resolve registrant IDs,
        since the CEL scope resolver has issues with certain expressions.
        If a cel_expression is provided, uses the CEL executor's
        compile_for_batch to filter the base registrant set.

        Args:
            scope_dict: API scope with target_type, cel_expression, area_id

        Returns:
            dict: Engine-compatible scope dict with scope_type="explicit"
        """
        target_type = scope_dict.get("target_type", "group")
        cel_expression = scope_dict.get("cel_expression")
        area_id = scope_dict.get("area_id")

        is_group = target_type == "group"

        # Build Odoo domain for base registrant filtering
        domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", is_group),
            ("active", "=", True),
        ]
        if area_id is not None:
            domain.append(("area_id", "=", area_id))

        # API service requires sudo to search all registrants regardless of user access rules
        # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models
        partner_ids = self.env["res.partner"].sudo().search(domain).ids

        # Apply CEL expression filter if provided
        if cel_expression and partner_ids:
            try:
                executor = self.env["spp.cel.executor"].sudo()  # nosemgrep: odoo-sudo-without-context
                filtered_ids = []
                for batch_ids in executor.compile_for_batch(
                    "res.partner",
                    cel_expression,
                    batch_size=5000,
                ):
                    filtered_ids.extend(batch_ids)
                # Intersect with our base set
                partner_id_set = set(partner_ids)
                partner_ids = [pid for pid in filtered_ids if pid in partner_id_set]
            except Exception:
                _logger.warning(
                    "CEL expression filter failed, using base registrant set",
                    exc_info=True,
                )

        return build_explicit_scope(partner_ids)

    def list_dimensions(self, applies_to=None):
        """List active demographic dimensions.

        Args:
            applies_to: Optional filter: 'individuals', 'groups', or None for all

        Returns:
            list[dict]: List of dimension info dicts
        """
        dimensions = (
            self.env["spp.demographic.dimension"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .get_active_dimensions(
                applies_to=applies_to,
            )
        )

        result = []
        for dimension in dimensions:
            result.append(
                {
                    "name": dimension.name,
                    "label": dimension.label,
                    "description": dimension.description or None,
                    "dimension_type": dimension.dimension_type,
                    "applies_to": dimension.applies_to,
                    "value_labels": self._parse_value_labels(dimension.value_labels_json),
                }
            )

        return result
