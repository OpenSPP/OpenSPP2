# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging
import math

from odoo import api, models

_logger = logging.getLogger(__name__)


class DistributionService(models.AbstractModel):
    """
    Service for computing distribution statistics.

    Provides Gini coefficient, Lorenz curve, percentiles, and other
    inequality metrics from a list of numerical values.
    """

    _name = "spp.metric.distribution"
    _description = "Distribution Computation Service"

    @api.model
    def compute_distribution(self, amounts):
        """
        Compute distribution statistics from a list of amounts.

        :param amounts: List of numerical values (e.g., benefit amounts)
        :returns: Dictionary with distribution statistics
        :rtype: dict

        Returns:
            {
                "count": int,
                "total": float,
                "minimum": float,
                "maximum": float,
                "mean": float,
                "median": float,
                "standard_deviation": float,
                "percentiles": {"p10": float, "p25": float, "p50": float, "p75": float, "p90": float},
                "gini_coefficient": float,  # 0.0 (perfect equality) to 1.0 (perfect inequality)
                "lorenz_deciles": [{"population_share": int, "income_share": float}, ...]
            }
        """
        if not amounts:
            return self._empty_distribution()

        sorted_amounts = sorted(amounts)
        count = len(sorted_amounts)
        total = sum(sorted_amounts)
        minimum = sorted_amounts[0]
        maximum = sorted_amounts[-1]
        mean = total / count if count else 0

        # Median
        mid = count // 2
        if count % 2 == 0:
            median = (sorted_amounts[mid - 1] + sorted_amounts[mid]) / 2
        else:
            median = sorted_amounts[mid]

        # Standard deviation
        variance = sum((x - mean) ** 2 for x in sorted_amounts) / count if count else 0
        standard_deviation = math.sqrt(variance)

        # Percentiles
        percentiles = {
            "p10": self._percentile(sorted_amounts, 10),
            "p25": self._percentile(sorted_amounts, 25),
            "p50": self._percentile(sorted_amounts, 50),
            "p75": self._percentile(sorted_amounts, 75),
            "p90": self._percentile(sorted_amounts, 90),
        }

        # Gini coefficient
        gini = self._compute_gini(sorted_amounts)

        # Lorenz curve deciles
        lorenz_deciles = self._compute_lorenz_deciles(sorted_amounts, total)

        return {
            "count": count,
            "total": total,
            "minimum": minimum,
            "maximum": maximum,
            "mean": mean,
            "median": median,
            "standard_deviation": standard_deviation,
            "percentiles": percentiles,
            "gini_coefficient": gini,
            "lorenz_deciles": lorenz_deciles,
        }

    @api.model
    def _empty_distribution(self):
        """Return empty distribution statistics."""
        return {
            "count": 0,
            "total": 0,
            "minimum": 0,
            "maximum": 0,
            "mean": 0,
            "median": 0,
            "standard_deviation": 0,
            "percentiles": {"p10": 0, "p25": 0, "p50": 0, "p75": 0, "p90": 0},
            "gini_coefficient": 0,
            "lorenz_deciles": [],
        }

    @api.model
    def _percentile(self, sorted_values, percent):
        """
        Compute the percentile value using linear interpolation.

        :param sorted_values: List of sorted numerical values
        :param percent: Percentile to compute (0-100)
        :returns: The percentile value
        :rtype: float
        """
        if not sorted_values:
            return 0
        count = len(sorted_values)
        rank = percent / 100.0 * (count - 1)
        lower = int(rank)
        upper = min(lower + 1, count - 1)
        fraction = rank - lower
        return sorted_values[lower] + fraction * (sorted_values[upper] - sorted_values[lower])

    @api.model
    def _compute_gini(self, sorted_amounts):
        """
        Compute the Gini coefficient from sorted amounts.

        Uses the formula: G = (2 * sum(i * y_i) - (n + 1) * sum(y_i)) / (n * sum(y_i))
        where y_i are sorted in ascending order.

        :param sorted_amounts: List of amounts sorted in ascending order
        :returns: Gini coefficient (0.0 to 1.0)
        :rtype: float
        """
        n = len(sorted_amounts)
        if n == 0:
            return 0.0
        total = sum(sorted_amounts)
        if total == 0:
            return 0.0

        weighted_sum = sum((i + 1) * y for i, y in enumerate(sorted_amounts))
        gini = (2.0 * weighted_sum - (n + 1) * total) / (n * total)
        return max(0.0, min(1.0, gini))

    @api.model
    def _compute_lorenz_deciles(self, sorted_amounts, total):
        """
        Compute Lorenz curve points at each decile (10%, 20%, ..., 100%).

        :param sorted_amounts: List of amounts sorted in ascending order
        :param total: Sum of all amounts
        :returns: List of decile points with population_share and income_share
        :rtype: list[dict]
        """
        if not sorted_amounts or total == 0:
            return []

        n = len(sorted_amounts)
        deciles = []
        cumulative = 0.0

        for decile in range(1, 11):
            cutoff_index = int(n * decile / 10) - 1
            cutoff_index = max(0, min(cutoff_index, n - 1))
            cumulative = sum(sorted_amounts[: cutoff_index + 1])
            deciles.append(
                {
                    "population_share": decile * 10,
                    "income_share": round(cumulative / total * 100, 2),
                }
            )

        return deciles
