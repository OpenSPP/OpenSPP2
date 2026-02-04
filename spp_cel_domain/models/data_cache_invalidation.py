# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Cache invalidation logic for the Unified Variable System.

This module provides automatic cache invalidation when records change.
It extends res.partner (the primary subject model) to invalidate cached
variable values when relevant fields are modified.

Invalidation strategies:
1. Field-based: When invalidate_on_field_change triggers match changed fields
2. Member-based: When group membership changes and invalidate_on_member_change is set
3. Manual: Variables can also be invalidated via API call
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class DataCacheInvalidation(models.AbstractModel):
    """Mixin for automatic cache invalidation on record changes.

    This mixin should be applied to models whose data is used in cached variables.
    By default, it's applied to res.partner.

    When records are modified, this mixin:
    1. Checks which variables are affected by the changed fields
    2. Invalidates the cached values for those variables/subjects
    """

    _name = "spp.data.cache.invalidation.mixin"
    _description = "Data Cache Invalidation Mixin"

    @api.model
    def _get_cached_variable_fields(self):
        """Get mapping of fields to variables that should be invalidated.

        Returns:
            dict: {field_name: [variable_records], ...}
        """
        # Use sudo() for internal cache management - shouldn't depend on user permissions
        Variable = self.env["spp.cel.variable"].sudo()

        # Get all active variables with persistent caching
        cached_vars = Variable.search(
            [
                ("active", "=", True),
                ("cache_strategy", "in", ["ttl", "manual"]),
            ]
        )

        field_to_vars = {}
        for var in cached_vars:
            # Check invalidate_on_field_change
            if var.invalidate_on_field_change:
                for field_name in var.invalidate_on_field_change.split(","):
                    field_name = field_name.strip()
                    if field_name:
                        if field_name not in field_to_vars:
                            field_to_vars[field_name] = Variable
                        field_to_vars[field_name] |= var

            # For field-type variables, also trigger on source_field change
            if var.source_type == "field" and var.source_field:
                field_name = var.source_field
                if field_name not in field_to_vars:
                    field_to_vars[field_name] = Variable
                field_to_vars[field_name] |= var

        return field_to_vars

    def _invalidate_variable_cache(self, variable_names, subject_ids, reason="field_change"):
        """Invalidate cached values for given variables/subjects.

        Args:
            variable_names: List of variable names to invalidate
            subject_ids: List of subject IDs
            reason: Reason for invalidation (for logging)
        """
        if not variable_names or not subject_ids:
            return

        # Use sudo() for internal cache management
        DataValue = self.env["spp.data.value"].sudo()
        for var_name in variable_names:
            DataValue.invalidate(var_name, subject_ids)

        _logger.debug(
            "Invalidated cache for variables %s on subjects %s (reason: %s)",
            variable_names,
            subject_ids,
            reason,
        )


class ResPartnerCacheInvalidation(models.Model):
    """Extend res.partner with automatic cache invalidation."""

    _name = "res.partner"
    _inherit = ["res.partner", "spp.data.cache.invalidation.mixin"]

    def write(self, vals):
        """Override write to invalidate variable cache on field changes."""
        # Get field-to-variable mapping before write
        field_to_vars = self._get_cached_variable_fields()

        # Identify affected variables
        affected_vars = self.env["spp.cel.variable"]
        for field_name in vals:
            if field_name in field_to_vars:
                affected_vars |= field_to_vars[field_name]

        result = super().write(vals)

        # Invalidate cache for affected variables
        if affected_vars:
            var_names = affected_vars.mapped("name")
            self._invalidate_variable_cache(var_names, self.ids, reason="field_write")

        # Check for membership changes (for aggregate variables)
        membership_fields = {"member_ids", "individual_ids", "group_ids", "parent_id"}
        if membership_fields & set(vals.keys()):
            self._invalidate_aggregate_cache()

        return result

    def unlink(self):
        """Override unlink to invalidate cache before deletion."""
        # Get all cached variables for these subjects
        # Use sudo() for internal cache management
        DataValue = self.env["spp.data.value"].sudo()
        if self:
            # Invalidate all cached values for these subjects
            DataValue.search(
                [
                    ("subject_model", "=", "res.partner"),
                    ("subject_id", "in", self.ids),
                ]
            ).unlink()

        return super().unlink()

    def _invalidate_aggregate_cache(self):
        """Invalidate aggregate variable cache when membership changes.

        When group membership changes:
        1. Invalidate group-level aggregate caches
        2. For child count variables, update group counts
        """
        # Use sudo() for internal cache management
        Variable = self.env["spp.cel.variable"].sudo()

        # Get aggregate variables with member change invalidation
        aggregate_vars = Variable.search(
            [
                ("active", "=", True),
                ("source_type", "=", "aggregate"),
                ("invalidate_on_member_change", "=", True),
                ("cache_strategy", "in", ["ttl", "manual"]),
            ]
        )

        if not aggregate_vars:
            return

        var_names = aggregate_vars.mapped("name")

        # Collect all group IDs that might be affected
        group_ids = set()
        for partner in self:
            # If this is a group, invalidate its cache
            if partner.is_group:
                group_ids.add(partner.id)
            # If this is an individual with groups, invalidate those group caches
            if hasattr(partner, "group_ids"):
                group_ids.update(partner.group_ids.ids)
            # Also check parent_id for group membership
            if partner.parent_id and partner.parent_id.is_group:
                group_ids.add(partner.parent_id.id)

        if group_ids:
            self._invalidate_variable_cache(var_names, list(group_ids), reason="member_change")


class CelVariableCacheInvalidation(models.Model):
    """Extend spp.cel.variable with cache invalidation methods."""

    _inherit = "spp.cel.variable"

    def invalidate_all_cached_values(self):
        """Invalidate all cached values for this variable.

        This is useful for manual refresh triggers or when the
        variable definition changes significantly.
        """
        # Use sudo() for internal cache management
        DataValue = self.env["spp.data.value"].sudo()
        for var in self:
            if var.uses_persistent_cache():
                DataValue.invalidate_pattern(var.name)
                _logger.info("Invalidated all cached values for variable ID %s", var.id)

    def action_invalidate_cache(self):
        """UI action to invalidate all cached values."""
        self.invalidate_all_cached_values()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Cache Invalidated",
                "message": f"Invalidated cache for {len(self)} variable(s).",
                "type": "success",
            },
        }

    def write(self, vals):
        """Override write to invalidate cache when definition changes."""
        # Check if we need to invalidate cache based on changed fields
        definition_fields = {
            "cel_expression",
            "source_type",
            "source_field",
            "source_model",
            "aggregate_type",
            "aggregate_filter",
            "aggregate_field",
            "aggregate_target",
            "value_type",
        }

        result = super().write(vals)

        # If definition changed, invalidate all cached values
        if definition_fields & set(vals.keys()):
            for var in self:
                if var.uses_persistent_cache():
                    var.invalidate_all_cached_values()

        return result
