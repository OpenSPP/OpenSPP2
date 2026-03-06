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

    _name = "spp.metrics.breakdown"
    _description = "Breakdown Computation Service"

    @api.model
    def compute_breakdown(self, registrant_ids, group_by, statistics=None, context=None):
        """
        Compute breakdown by dimensions with caching.

        Uses dimension cache for 5-10x performance improvement.

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

        # Get cache service
        cache_service = self.env["spp.metrics.dimension.cache"]

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
