# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class StatisticRegistry(models.AbstractModel):
    """Registry that maps statistic names to computation strategies.

    Replaces the fallback chain in compute_single_statistic with
    a clean lookup-based approach. Each statistic type registers
    how it should be computed.
    """

    _name = "spp.analytics.indicator.registry"
    _description = "Statistic Computation Registry"

    @api.model
    def compute(self, stat_name, registrant_ids, context=None):
        """Compute a statistic by name.

        Lookup order:
        1. Built-in statistics (count, gini)
        2. spp.indicator records (via CEL variable)
        3. spp.cel.variable records (direct)

        :param stat_name: Statistic name
        :param registrant_ids: List of partner IDs
        :param context: Optional context string
        :returns: Computed value or None
        """
        # Try built-in
        builtin_method = self._get_builtin(stat_name)
        if builtin_method is not None:
            return builtin_method(registrant_ids)

        # Try spp.indicator (if module installed)
        value = self._try_statistic_model(stat_name, registrant_ids)
        if value is not None:
            return value

        # Try spp.cel.variable (if module installed)
        value = self._try_variable_model(stat_name, registrant_ids)
        if value is not None:
            return value

        # Provide diagnostic information if debug logging is enabled
        if _logger.isEnabledFor(logging.DEBUG):
            # Check if models exist
            has_stat_model = self.env.get("spp.indicator") is not None
            has_var_model = self.env.get("spp.cel.variable") is not None

            stat_count = 0
            var_count = 0
            if has_stat_model:
                stat_count = self.env["spp.indicator"].sudo().search_count([])  # nosemgrep: odoo-sudo-without-context
            if has_var_model:
                var_count = self.env["spp.cel.variable"].sudo().search_count([])  # nosemgrep: odoo-sudo-without-context

            _logger.debug(
                "Statistic lookup failed for '%s'. Available: %d spp.indicator, %d spp.cel.variable",
                stat_name,
                stat_count,
                var_count,
            )

        _logger.warning("Unknown statistic: %s", stat_name)
        return None

    @api.model
    def list_available(self):
        """List all available statistics for discovery.

        :returns: List of dicts with name, label, source
        :rtype: list[dict]
        """
        available = []

        # Built-ins
        for name, info in self._BUILTINS.items():
            available.append({"name": name, "label": info["label"], "source": "builtin"})

        # From spp.indicator
        stat_model = self.env.get("spp.indicator")
        if stat_model:
            for stat in stat_model.sudo().search([("active", "=", True)]):  # nosemgrep: odoo-sudo-without-context
                available.append({"name": stat.name, "label": stat.label, "source": "statistic"})

        # From spp.cel.variable
        var_model = self.env.get("spp.cel.variable")
        if var_model:
            # Search for active variables (check if state field exists)
            domain = []
            if "state" in var_model._fields:
                domain = [("state", "=", "active")]

            for var in var_model.sudo().search(domain):  # nosemgrep: odoo-sudo-without-context
                if not any(a["name"] == var.name for a in available):
                    available.append({"name": var.name, "label": var.name, "source": "variable"})

        return available

    _BUILTINS = {
        "count": {"label": "Total Count", "compute": "_compute_count"},
        "gini": {"label": "Gini Coefficient", "compute": "_compute_gini"},
        "gini_coefficient": {"label": "Gini Coefficient", "compute": "_compute_gini"},
    }

    def _get_builtin(self, stat_name):
        """Get builtin computation function.

        :param stat_name: Statistic name
        :returns: Bound method or None
        """
        info = self._BUILTINS.get(stat_name)
        if info:
            method_name = info["compute"]
            return getattr(self, method_name)
        return None

    @api.model
    def _compute_count(self, registrant_ids):
        """Compute count of registrants.

        :param registrant_ids: List of partner IDs
        :returns: Count
        :rtype: int
        """
        return len(registrant_ids)

    @api.model
    def _compute_gini(self, registrant_ids):
        """Compute Gini coefficient for registrants.

        Note: This requires benefit amounts which may not be available
        in all contexts. Returns None if not applicable.

        :param registrant_ids: List of partner IDs
        :returns: Gini coefficient or None
        """
        # This would need benefit amounts - placeholder for now
        return None

    @api.model
    def _try_statistic_model(self, stat_name, registrant_ids):
        """Try computing via spp.indicator record.

        :param stat_name: Statistic name
        :param registrant_ids: List of partner IDs
        :returns: Computed value or None
        """
        stat_model = self.env.get("spp.indicator")
        if stat_model is None:
            return None
        stat = stat_model.sudo().search([("name", "=", stat_name)], limit=1)  # nosemgrep: odoo-sudo-without-context
        if stat and stat.variable_id:
            return self._compute_from_variable(stat.variable_id, registrant_ids)
        return None

    @api.model
    def _try_variable_model(self, stat_name, registrant_ids):
        """Try computing via spp.cel.variable record.

        :param stat_name: Statistic name
        :param registrant_ids: List of partner IDs
        :returns: Computed value or None
        """
        var_model = self.env.get("spp.cel.variable")
        if var_model is None:
            return None
        variable = var_model.sudo().search([("name", "=", stat_name)], limit=1)  # nosemgrep: odoo-sudo-without-context
        if variable:
            return self._compute_from_variable(variable, registrant_ids)
        return None

    @api.model
    def _compute_from_variable(self, variable, registrant_ids):
        """Compute statistic from a CEL variable.

        For aggregate variables (source_type='aggregate' with members.* expressions),
        computes the SUM of per-group values using evaluate_member_aggregate.
        For other variables, counts matching records via compile_expression.

        :param variable: spp.cel.variable record
        :param registrant_ids: List of partner IDs
        :returns: Computed value or None
        """
        if not registrant_ids:
            return 0

        cel_service = self.env.get("spp.cel.service")
        if cel_service is None:
            return None
        cel_service = cel_service.sudo()  # nosemgrep: odoo-sudo-without-context

        # Get expression
        expression = None
        if hasattr(variable, "get_cel_expression"):
            expression = variable.get_cel_expression()
        if not expression and "cel_expression" in variable._fields:
            expression = variable.cel_expression
        if not expression and "expression" in variable._fields:
            expression = variable.expression
        if not expression:
            return None

        # For member aggregate variables, compute the SUM of per-group values
        # instead of counting groups where the expression is truthy
        if self._is_member_aggregate(variable, expression):
            return self._compute_member_aggregate_sum(cel_service, expression, registrant_ids)

        # Get profile based on target type
        profile = "registry_individuals"
        if "applies_to" in variable._fields:
            target_type = variable.applies_to
            if hasattr(cel_service, "get_profile_for_target_type"):
                profile = cel_service.get_profile_for_target_type(target_type)
            elif target_type == "group":
                profile = "registry_groups"

        try:
            result = cel_service.compile_expression(
                expression,
                profile=profile,
                base_domain=[("id", "in", registrant_ids)],
                limit=0,
            )
            return result.get("count", 0)
        except Exception as e:
            variable_name = variable.name
            _logger.warning("Error computing variable %s: %s", variable_name, e)
            return None

    @api.model
    def _is_member_aggregate(self, variable, expression):
        """Check if variable is a member aggregate requiring sum computation.

        :param variable: spp.cel.variable record
        :param expression: CEL expression string
        :returns: True if this is a members.* aggregate
        :rtype: bool
        """
        if "source_type" not in variable._fields:
            return False
        if variable.source_type != "aggregate":
            return False
        return bool(expression and expression.startswith("members."))

    @api.model
    def _compute_member_aggregate_sum(self, cel_service, expression, registrant_ids):
        """Compute SUM of a member aggregate expression across groups.

        For aggregate variables like members.count(m, true), the result should be
        the total count of matching members across all groups, not the count of
        groups that have matching members.

        :param cel_service: spp.cel.service instance
        :param expression: CEL expression string (e.g. "members.count(m, true)")
        :param registrant_ids: List of partner IDs (should be group IDs)
        :returns: Sum of per-group aggregate values
        :rtype: int or float
        """
        if not hasattr(cel_service, "evaluate_member_aggregate"):
            _logger.warning(
                "CEL service missing evaluate_member_aggregate, falling back to count for expression: %s",
                expression,
            )
            return None

        try:
            groups = self.env["res.partner"].sudo().browse(registrant_ids)  # nosemgrep: odoo-sudo-without-context, odoo-sudo-on-sensitive-models  # noqa: E501  # fmt: skip
            total = 0
            for group in groups:
                if not group.is_group:
                    continue
                value = cel_service.evaluate_member_aggregate(group, expression)
                if isinstance(value, bool):
                    if value:
                        total += 1
                elif isinstance(value, int | float):
                    total += value
            return total
        except Exception as e:
            _logger.warning(
                "Error computing member aggregate sum for '%s': %s",
                expression,
                e,
            )
            return None
