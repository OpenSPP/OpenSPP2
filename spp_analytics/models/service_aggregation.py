# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
from datetime import datetime

from odoo import _, api, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class AggregationService(models.AbstractModel):
    """
    Main aggregation service for unified statistics computation.

    This is THE entry point for all aggregation queries. All consumers
    (simulation, GIS API, dashboards) should use this service.

    Access level is determined from user permissions, not passed as
    a parameter, to prevent callers bypassing restrictions.
    """

    _name = "spp.analytics.service"
    _description = "Analytics Service"

    MAX_GROUP_BY_DIMENSIONS = 3

    @api.model
    def compute_aggregation(
        self,
        scope,
        statistics=None,
        group_by=None,
        context=None,
        use_cache=True,
    ):
        """
        Compute aggregation for a scope with optional breakdown.

        Access level is determined from user permissions (AggregationAccessRule),
        NOT passed as a parameter. This prevents callers bypassing restrictions.

        :param scope: spp.analytics.scope record, ID, or inline dict definition
        :param statistics: List of statistic names to compute (or None for defaults)
        :param group_by: List of dimension names for breakdown (max 3)
        :param context: Context string for configuration (e.g., "api", "dashboard")
        :param use_cache: Whether to use cached results (default: True)
        :returns: Aggregation result dictionary
        :rtype: dict

        Returns:
            {
                "total_count": int,
                "statistics": {stat_name: {"value": ..., "suppressed": bool}},
                "breakdown": {  # Only if group_by specified
                    "dimension1|dimension2|...": {"count": int, "statistics": {...}},
                },
                "from_cache": bool,
                "computed_at": datetime,
                "access_level": str,  # "aggregate" or "individual"
            }
        """
        # Resolve scope
        scope_record = self._resolve_scope(scope)

        # Resolve user access context once (single DB lookup)
        rule = self._get_effective_rule()

        # Validate group_by dimensions
        group_by = group_by or []
        self._validate_group_by(group_by, rule)

        # Determine access level and k-threshold from the resolved rule
        access_level = self._access_level_from_rule(rule)
        k_threshold = self._k_threshold_from_rule(rule)

        # Check scope is allowed for user
        self._check_scope_allowed(scope, rule)

        # Check cache if enabled
        cache_service = self.env["spp.analytics.cache"]
        if use_cache:
            cached_result = cache_service.get_cached_result(scope_record, statistics, group_by)
            if cached_result:
                # Apply access level to cached result (in case user permissions changed)
                cached_result["access_level"] = access_level
                _logger.debug("Returning cached result for scope")
                return cached_result

        # Get registrant IDs from scope
        registrant_ids = self._get_registrant_ids(scope_record)

        # Build result
        result = {
            "total_count": len(registrant_ids),
            "statistics": {},
            "from_cache": False,
            "computed_at": datetime.now().isoformat(),
            "access_level": access_level,
        }

        # Compute statistics if requested
        if statistics:
            result["statistics"] = self._compute_statistics(
                registrant_ids,
                statistics,
                context=context,
                k_threshold=k_threshold,
            )

        # Compute breakdown if group_by specified
        if group_by:
            result["breakdown"] = self._compute_breakdown(registrant_ids, group_by, statistics, context)

        # Apply privacy protections
        privacy_service = self.env["spp.metric.privacy"]
        result = privacy_service.enforce(result, k_threshold, access_level)

        # Store in cache if enabled
        if use_cache:
            cache_service.store_result(scope_record, statistics, group_by, result)

        return result

    def _resolve_scope(self, scope):
        """
        Resolve scope input to a scope record.

        :param scope: Record, ID, or dict
        :returns: spp.analytics.scope record or dict
        """
        if isinstance(scope, dict):
            # Inline scope definition
            return scope

        if isinstance(scope, int):
            # Scope ID
            return self.env["spp.analytics.scope"].browse(scope)

        # Assume it's already a record
        return scope

    def _get_effective_rule(self, user=None):
        """
        Look up the effective access rule for a user (single DB query).

        :param user: res.users record (defaults to current user)
        :returns: access rule record or None
        """
        user = user or self.env.user
        # Use sudo() to read access rules - this is an internal security check
        return self.env["spp.analytics.access.rule"].sudo().get_effective_rule_for_user(user)  # nosemgrep: odoo-sudo-without-context  # noqa: E501  # fmt: skip

    def _validate_group_by(self, group_by, rule=None):
        """
        Validate group_by dimensions.

        :param group_by: List of dimension names
        :param rule: Pre-resolved access rule (or None)
        :raises: ValidationError if invalid
        """
        if len(group_by) > self.MAX_GROUP_BY_DIMENSIONS:
            raise ValidationError(
                _("Maximum %d group_by dimensions allowed, got %d.") % (self.MAX_GROUP_BY_DIMENSIONS, len(group_by))
            )

        # Check dimensions exist (use sudo for internal validation)
        dimension_model = self.env["spp.demographic.dimension"].sudo()  # nosemgrep: odoo-sudo-without-context
        for dim_name in group_by:
            if not dimension_model.get_by_name(dim_name):
                raise ValidationError(_("Unknown dimension: %s") % dim_name)

        # Check access rule dimension restrictions
        if rule and group_by:
            rule.check_dimensions_allowed(group_by)

    def _access_level_from_rule(self, rule):
        """
        Extract access level from a pre-resolved rule.

        :param rule: access rule record or None
        :returns: "aggregate" or "individual"
        :rtype: str
        """
        if rule:
            return rule.access_level
        # Default to aggregate-only for safety
        return "aggregate"

    def _k_threshold_from_rule(self, rule):
        """
        Extract k-anonymity threshold from a pre-resolved rule.

        :param rule: access rule record or None
        :returns: k threshold value
        :rtype: int
        """
        if rule:
            return rule.minimum_k_anonymity
        return self.env["spp.metric.privacy"].DEFAULT_K_THRESHOLD

    def _check_scope_allowed(self, scope, rule=None):
        """
        Check if scope is allowed for current user.

        :param scope: Scope record or dict
        :param rule: Pre-resolved access rule (or None)
        :raises: AccessError if not allowed
        """
        if not rule:
            # No explicit rule - allow with defaults
            return

        try:
            rule.check_scope_allowed(scope)
        except ValidationError as e:
            raise AccessError(str(e)) from e

    def _get_registrant_ids(self, scope):
        """
        Get registrant IDs from scope.

        :param scope: Scope record or dict
        :returns: List of partner IDs
        :rtype: list[int]
        """
        resolver = self.env["spp.analytics.scope.resolver"]
        return resolver.resolve(scope)

    def _compute_statistics(self, registrant_ids, statistics, context=None, k_threshold=None):
        """
        Compute statistics for registrants.

        :param registrant_ids: List of partner IDs
        :param statistics: List of statistic names
        :param context: Context string
        :returns: Dictionary of statistic results
        :rtype: dict
        """
        result = {}
        total_count = len(registrant_ids)

        statistic_by_name = {}
        statistic_model = self.env.get("spp.indicator")
        if statistic_model is not None:
            statistic_records = statistic_model.sudo().search(  # nosemgrep: odoo-sudo-without-context
                [("name", "in", statistics)]
            )
            statistic_by_name = {record.name: record for record in statistic_records}

        privacy_service = self.env["spp.metric.privacy"]

        for stat_name in statistics:
            try:
                value = self._compute_single_statistic(stat_name, registrant_ids, context)
                value, suppressed = self._apply_statistic_suppression(
                    stat_name=stat_name,
                    value=value,
                    total_count=total_count,
                    context=context,
                    k_threshold=k_threshold,
                    statistic_by_name=statistic_by_name,
                    privacy_service=privacy_service,
                )
                result[stat_name] = {
                    "value": value,
                    "suppressed": suppressed,
                }
            except (ValueError, AttributeError, TypeError, KeyError, ValidationError) as e:
                _logger.warning("Error computing statistic %s: %s", stat_name, e)
                result[stat_name] = {
                    "value": None,
                    "error": str(e),
                    "suppressed": False,
                }

        return result

    def _apply_statistic_suppression(
        self,
        stat_name,
        value,
        total_count,
        context,
        k_threshold,
        statistic_by_name,
        privacy_service,
    ):
        """
        Apply top-level statistic suppression, delegating to unified privacy service.

        Precedence rule:
        - Base threshold comes from access rules (user-level k-anonymity)
        - Statistic/context threshold can raise privacy further
        - Effective threshold = max(user threshold, statistic/context threshold)
        """
        if value is None:
            return value, False

        # Build stat config from statistic record
        stat_config = None
        stat = statistic_by_name.get(stat_name)
        if stat:
            config = stat.get_context_config(context) if context else {}
            stat_config = {
                "minimum_count": config.get("minimum_count") or stat.minimum_count or 0,
                "suppression_display": config.get("suppression_display", stat.suppression_display) or "less_than",
            }

        return privacy_service.suppress_value(value, total_count, k_threshold=k_threshold, stat_config=stat_config)

    def _compute_single_statistic(self, stat_name, registrant_ids, context=None):
        """
        Compute a single statistic.

        Delegates to statistic registry for clean lookup and computation.

        :param stat_name: Statistic name
        :param registrant_ids: List of partner IDs
        :param context: Context string
        :returns: Computed value
        """
        registry = self.env["spp.analytics.indicator.registry"]
        return registry.compute(stat_name, registrant_ids, context)

    def _compute_breakdown(self, registrant_ids, group_by, statistics, context=None):
        """
        Compute breakdown by dimensions.

        Delegates to spp.metric.breakdown service.

        :param registrant_ids: List of partner IDs
        :param group_by: List of dimension names
        :param statistics: List of statistic names
        :param context: Context string
        :returns: Breakdown dictionary
        :rtype: dict
        """
        breakdown_service = self.env["spp.metric.breakdown"]
        return breakdown_service.compute_breakdown(registrant_ids, group_by, statistics, context)

    # -------------------------------------------------------------------------
    # Convenience Methods
    # -------------------------------------------------------------------------
    @api.model
    def compute_for_area(self, area_id, include_children=True, **kwargs):
        """
        Compute aggregation for an administrative area.

        :param area_id: spp.area ID
        :param include_children: Include child areas
        :param kwargs: Additional arguments for compute_aggregation
        :returns: Aggregation result
        :rtype: dict
        """
        scope = {
            "scope_type": "area",
            "area_id": area_id,
            "include_child_areas": include_children,
        }
        return self.compute_aggregation(scope, **kwargs)

    @api.model
    def compute_for_expression(self, cel_expression, profile="registry_individuals", **kwargs):
        """
        Compute aggregation for a CEL expression.

        :param cel_expression: CEL expression string
        :param profile: CEL profile
        :param kwargs: Additional arguments for compute_aggregation
        :returns: Aggregation result
        :rtype: dict
        """
        scope = {
            "scope_type": "cel",
            "cel_expression": cel_expression,
            "cel_profile": profile,
        }
        return self.compute_aggregation(scope, **kwargs)

    @api.model
    def compute_fairness(self, scope, dimensions=None, **kwargs):
        """
        Compute fairness analysis for a scope.

        :param scope: Scope record, ID, or dict
        :param dimensions: Dimension names for analysis
        :returns: Fairness result
        :rtype: dict
        """
        scope_record = self._resolve_scope(scope)
        registrant_ids = self._get_registrant_ids(scope_record)

        # Get base domain for population
        base_domain = [("is_registrant", "=", True)]

        fairness_service = self.env["spp.metric.fairness"]
        return fairness_service.compute_fairness(registrant_ids, base_domain, dimensions)

    @api.model
    def compute_distribution(self, amounts):
        """
        Compute distribution statistics for a list of amounts.

        :param amounts: List of numerical values
        :returns: Distribution result
        :rtype: dict
        """
        distribution_service = self.env["spp.metric.distribution"]
        return distribution_service.compute_distribution(amounts)
