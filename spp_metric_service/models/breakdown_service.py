# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class BreakdownService(models.AbstractModel):
    """
    Service for computing breakdowns by demographic dimensions.

    Categorizes registrants by one or more dimensions and provides
    counts and statistics per dimension combination.
    """

    _name = "spp.metric.breakdown"
    _description = "Breakdown Computation Service"

    @api.model
    def compute_breakdown(self, registrant_ids, group_by, statistics=None, context=None):
        """
        Compute breakdown by dimensions with caching.

        Uses dimension cache for 5-10x performance improvement.

        Expansion semantics (deliberate): if ANY requested dimension has
        ``applies_to == "individuals"``, the ENTIRE registrant set is expanded
        from groups to their active individual members before evaluation —
        including for any non-individual dimensions mixed into the same
        request (mixing scopes in one breakdown is inherently ambiguous; the
        expansion is all-or-nothing by design). Consequently breakdown totals
        count members and intentionally need not reconcile with a group-level
        scope count.

        :param registrant_ids: List of partner IDs
        :param group_by: List of dimension names
        :param statistics: List of statistic names (optional)
        :param context: Context string (optional)
        :returns: Breakdown dictionary keyed by pipe-separated dimension values
        :rtype: dict

        Returns:
            {
                "dimension1|dimension2|...": {
                    "count": int,
                    "statistics": {},
                    "labels": {
                        "dimension_name": {
                            "value": str,
                            "display": str,
                        }
                    }
                }
            }
        """
        if not registrant_ids or not group_by:
            return {}

        # Get dimension records (use sudo - they're configuration data)
        dimension_model = self.env["spp.demographic.dimension"].sudo()  # nosemgrep: odoo-sudo-without-context
        dimensions = [dimension_model.get_by_name(name) for name in group_by]
        dimensions = [d for d in dimensions if d]  # Filter out None

        if not dimensions:
            return {}

        # Auto-expand groups to members when any dimension applies to individuals only
        needs_expansion = any(d.applies_to == "individuals" for d in dimensions)
        if needs_expansion:
            registrant_ids = self._expand_groups_to_members(registrant_ids)

        if not registrant_ids:
            return {}

        # Get cache service
        cache_service = self.env["spp.metric.dimension.cache"]

        # Get cached evaluations for all dimensions
        dimension_evaluations = {}
        for dimension in dimensions:
            dimension_evaluations[dimension.name] = cache_service.evaluate_dimension_batch(dimension, registrant_ids)

        # Build breakdown using cached evaluations
        breakdown = {}
        for partner_id in registrant_ids:
            # Build the breakdown key from cached evaluations
            key_parts = []
            for dimension in dimensions:
                value = dimension_evaluations[dimension.name].get(partner_id, "unknown")
                key_parts.append(str(value))

            key = "|".join(key_parts)

            if key not in breakdown:
                breakdown[key] = {
                    "count": 0,
                    "statistics": {},
                    "labels": {},
                }
                # Store labels for each dimension
                for dim, value in zip(dimensions, key_parts, strict=False):
                    breakdown[key]["labels"][dim.name] = {
                        "value": value,
                        "display": dim.get_label_for_value(value),
                    }

            breakdown[key]["count"] += 1

        # Optionally compute statistics per cell (expensive)
        # For now, just return counts
        # TODO: Add per-cell statistics if needed

        return breakdown

    @api.model
    def _expand_groups_to_members(self, registrant_ids):
        """
        Expand group IDs to their individual member IDs.

        Groups are replaced by their active members. Individual IDs pass through.
        The result is deduplicated.

        :param registrant_ids: List of partner IDs (groups and/or individuals)
        :returns: Deduplicated list of individual partner IDs
        :rtype: list
        """
        # sudo: aggregate breakdown metrics must expand groups to their members
        # across all registrants regardless of the caller's record rules.
        # Read-only (no writes); callers are authorized at the service entry point.
        Partner = self.env["res.partner"].sudo()  # nosemgrep: odoo-sudo-without-context,odoo-sudo-on-sensitive-models
        records = Partner.browse(registrant_ids).exists()

        groups = records.filtered("is_group")
        group_ids = groups.ids
        individual_ids = set((records - groups).ids)

        if not group_ids:
            return list(individual_ids)

        # Expand groups via active memberships
        Membership = self.env["spp.group.membership"].sudo()  # nosemgrep: odoo-sudo-without-context
        memberships = Membership.search(
            [
                ("group", "in", group_ids),
                ("is_ended", "=", False),
            ]
        )

        individual_ids.update(memberships.individual.ids)

        return list(individual_ids)
