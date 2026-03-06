# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class PrivacyEnforcerService(models.AbstractModel):
    """
    Service for enforcing privacy protections on aggregation results.

    Implements k-anonymity with complementary suppression to prevent
    differencing attacks. When a cell is suppressed due to low count,
    at least one sibling cell is also suppressed to prevent derivation.

    Example of differencing attack prevention:
    - Area A total = 1000
    - Area A, Male = 995 → if not suppressed, Female = 5 can be derived
    - Solution: If Female is suppressed, suppress at least one Male sibling

    Also handles access level enforcement (aggregate vs individual).
    """

    _name = "spp.metric.privacy"
    _description = "Privacy Enforcement Service"

    DEFAULT_K_THRESHOLD = 5

    @api.model
    def enforce(self, result, k_threshold=None, access_level="aggregate"):
        """
        Apply privacy protections to aggregation results.

        :param result: Dictionary with aggregation results
        :param k_threshold: Minimum count before suppression (default: 5)
        :param access_level: "aggregate" or "individual"
        :returns: Privacy-protected result dictionary
        :rtype: dict
        """
        if k_threshold is None:
            k_threshold = self.DEFAULT_K_THRESHOLD

        result = dict(result)  # Don't modify original

        # Apply access level restrictions
        if access_level == "aggregate":
            result = self._strip_individual_ids(result)

        # Apply k-anonymity to breakdowns
        if "breakdown" in result:
            result["breakdown"] = self._apply_k_anonymity(result["breakdown"], k_threshold)

        return result

    def _strip_individual_ids(self, result):
        """
        Remove any individual record IDs from results.

        :param result: Result dictionary
        :returns: Result with IDs removed
        :rtype: dict
        """
        result = dict(result)

        # Remove top-level IDs
        for key in ("registrant_ids", "partner_ids", "ids"):
            result.pop(key, None)

        # Remove IDs from breakdown cells
        if "breakdown" in result:
            for cell_data in result["breakdown"].values():
                if isinstance(cell_data, dict):
                    for id_key in ("registrant_ids", "partner_ids", "ids"):
                        cell_data.pop(id_key, None)

        return result

    def _apply_k_anonymity(self, breakdown, k_threshold):
        """
        Apply k-anonymity with complementary suppression.

        Uses dimension-aware complementary suppression to prevent derivation attacks:
        for each suppressed cell, we check each dimension and ensure at least one
        sibling in each dimension slice is also suppressed. This prevents derivation
        from ANY marginal total.

        :param breakdown: Dictionary of breakdown cells
        :param k_threshold: Minimum count threshold
        :returns: Suppressed breakdown dictionary
        :rtype: dict
        """
        if not breakdown:
            return breakdown

        breakdown = {k: dict(v) if isinstance(v, dict) else v for k, v in breakdown.items()}

        # Step 1: Mark cells below threshold (primary suppression)
        suppressed_keys = set()
        for key, cell in breakdown.items():
            if isinstance(cell, dict):
                count = cell.get("count", 0)
                if isinstance(count, int) and count < k_threshold:
                    suppressed_keys.add(key)

        # Step 2: Complementary suppression (dimension-aware)
        # For each suppressed cell, check EACH dimension slice
        for suppressed_key in list(suppressed_keys):
            parts = suppressed_key.split("|")
            num_dims = len(parts)

            if num_dims == 1:
                # Single dimension - use simple sibling logic
                siblings = self._find_siblings(suppressed_key, breakdown)
                non_suppressed = [s for s in siblings if s not in suppressed_keys]
                if len(non_suppressed) == 1:
                    suppressed_keys.add(non_suppressed[0])
                elif len(non_suppressed) > 1:
                    smallest = self._get_smallest_sibling(non_suppressed, breakdown)
                    if smallest:
                        suppressed_keys.add(smallest)
            else:
                # Multi-dimensional - check each dimension slice
                for dim_idx in range(num_dims):
                    # Find siblings that share this dimension value
                    slice_siblings = self._find_dimension_siblings(suppressed_key, dim_idx, breakdown)
                    non_suppressed = [s for s in slice_siblings if s not in suppressed_keys]

                    # If only one cell left in this slice, must suppress it
                    if len(non_suppressed) == 1:
                        suppressed_keys.add(non_suppressed[0])
                    elif len(non_suppressed) > 1:
                        # Check if this slice needs any suppression yet
                        already_suppressed_in_slice = any(
                            s in suppressed_keys and s != suppressed_key for s in slice_siblings
                        )
                        if not already_suppressed_in_slice:
                            smallest = self._get_smallest_sibling(non_suppressed, breakdown)
                            if smallest:
                                suppressed_keys.add(smallest)

        # Step 3: Apply suppression
        for key in suppressed_keys:
            if key in breakdown:
                original_cell = breakdown[key]
                if isinstance(original_cell, dict):
                    breakdown[key] = {
                        "count": f"<{k_threshold}",
                        "suppressed": True,
                        "statistics": {},  # No statistics for suppressed cells
                        "original_key": key,
                    }
                    # Preserve any non-sensitive metadata
                    for meta_key in ("label", "display_name"):
                        if meta_key in original_cell:
                            breakdown[key][meta_key] = original_cell[meta_key]

        return breakdown

    def _find_dimension_siblings(self, key, dim_idx, breakdown):
        """
        Find sibling cells that share the same value at a specific dimension.

        For key "male|urban" and dim_idx=0, this finds cells like "male|rural"
        (same first dimension "male", different other dimensions).

        :param key: Cell key (pipe-separated dimensions)
        :param dim_idx: Index of dimension that must match
        :param breakdown: Breakdown dictionary
        :returns: List of sibling keys (excludes the key itself)
        :rtype: list[str]
        """
        parts = key.split("|")
        if dim_idx >= len(parts):
            return []

        target_value = parts[dim_idx]
        siblings = []

        for other_key in breakdown:
            if other_key == key:
                continue
            other_parts = other_key.split("|")
            # Must have same number of dimensions
            if len(other_parts) != len(parts):
                continue
            # Must have same value at the target dimension
            if other_parts[dim_idx] == target_value:
                siblings.append(other_key)

        return siblings

    def _find_cells_in_slice(self, key, dim_idx, breakdown):
        """
        Find all cells that share the same value at a specific dimension index.

        For example, for key "male|urban" and dim_idx=0, this finds all cells
        starting with "male" (male|urban, male|rural, etc.).

        :param key: Cell key (pipe-separated dimensions)
        :param dim_idx: Index of dimension to match
        :param breakdown: Breakdown dictionary
        :returns: List of keys in this dimension slice
        :rtype: list[str]
        """
        parts = key.split("|")
        if dim_idx >= len(parts):
            return []

        target_value = parts[dim_idx]
        slice_cells = []

        for other_key in breakdown:
            other_parts = other_key.split("|")
            # Must have same number of dimensions and same value at dim_idx
            if len(other_parts) == len(parts) and other_parts[dim_idx] == target_value:
                slice_cells.append(other_key)

        return slice_cells

    def _find_siblings(self, key, breakdown):
        """
        Find sibling cells that share all but one dimension.

        Siblings are cells that:
        - Have the same number of dimension parts
        - Differ by exactly one part

        :param key: Cell key (pipe-separated dimensions)
        :param breakdown: Breakdown dictionary
        :returns: List of sibling keys
        :rtype: list[str]
        """
        parts = key.split("|")
        siblings = []

        for other_key in breakdown:
            if other_key == key:
                continue

            other_parts = other_key.split("|")

            # Same number of dimensions
            if len(other_parts) != len(parts):
                continue

            # Differ by exactly one part
            diff_count = sum(1 for a, b in zip(parts, other_parts, strict=False) if a != b)
            if diff_count == 1:
                siblings.append(other_key)

        return siblings

    def _get_smallest_sibling(self, siblings, breakdown):
        """
        Get the sibling with the smallest count.

        :param siblings: List of sibling keys
        :param breakdown: Breakdown dictionary
        :returns: Key of smallest sibling, or None
        :rtype: str or None
        """
        smallest_key = None
        smallest_count = float("inf")

        for sibling_key in siblings:
            cell = breakdown.get(sibling_key)
            if isinstance(cell, dict):
                count = cell.get("count", 0)
                if isinstance(count, int) and count < smallest_count:
                    smallest_count = count
                    smallest_key = sibling_key

        return smallest_key

    @api.model
    def is_count_suppressed(self, count, k_threshold=None):
        """
        Check if a count should be suppressed.

        :param count: The count value
        :param k_threshold: Minimum threshold (default: 5)
        :returns: True if count should be suppressed
        :rtype: bool
        """
        if k_threshold is None:
            k_threshold = self.DEFAULT_K_THRESHOLD

        if not isinstance(count, int):
            return False

        return count < k_threshold

    @api.model
    def format_suppressed_count(self, count, k_threshold=None, display_mode="less_than"):
        """
        Format a suppressed count for display.

        :param count: The count value
        :param k_threshold: Minimum threshold
        :param display_mode: "null", "asterisk", or "less_than"
        :returns: Formatted display value
        :rtype: str or None
        """
        if k_threshold is None:
            k_threshold = self.DEFAULT_K_THRESHOLD

        if not self.is_count_suppressed(count, k_threshold):
            return str(count)

        if display_mode == "null":
            return None
        elif display_mode == "asterisk":
            return "*"
        else:  # less_than
            return f"<{k_threshold}"

    @api.model
    def suppress_value(self, value, count, k_threshold=None, stat_config=None):
        """
        Unified suppression with precedence: max(user_threshold, stat_threshold).

        Single source of truth for all suppression decisions.

        :param value: The computed value to potentially suppress
        :param count: The underlying count for suppression check
        :param k_threshold: User-level k-anonymity threshold (from access rules)
        :param stat_config: Optional dict with per-statistic config:
            - minimum_count: Statistic-level threshold
            - suppression_display: How to display ('null', 'asterisk', 'less_than')
        :returns: Tuple of (display_value, is_suppressed)
        :rtype: tuple
        """
        if value is None:
            return value, False

        # Determine effective threshold with precedence
        base_threshold = k_threshold or self.DEFAULT_K_THRESHOLD
        effective_threshold = base_threshold
        display_mode = "less_than"

        if stat_config:
            stat_threshold = stat_config.get("minimum_count") or 0
            if stat_threshold:
                effective_threshold = max(effective_threshold, stat_threshold)
            display_mode = stat_config.get("suppression_display") or display_mode

        # Check suppression
        if self.is_count_suppressed(count, effective_threshold):
            formatted = self.format_suppressed_count(count, k_threshold=effective_threshold, display_mode=display_mode)
            return formatted, True

        return value, False

