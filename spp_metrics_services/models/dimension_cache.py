# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import hashlib
import logging

from odoo import api, models, tools

_logger = logging.getLogger(__name__)


class DimensionCacheService(models.AbstractModel):
    """
    Service for caching dimension evaluation results.

    Dramatically improves breakdown performance by caching:
    - Field-based dimension evaluations (gender, disability, etc.)
    - CEL expression evaluations (age groups, custom categories)

    Cache key: (dimension_id, dimension_write_date, hash(registrant_ids))
    Cache TTL: 1 hour (default Odoo ormcache)
    Invalidation: On dimension write/unlink
    """

    _name = "spp.metrics.dimension.cache"
    _description = "Dimension Evaluation Cache"

    @api.model
    def _make_registrant_key(self, registrant_ids):
        """
        Create a compact hash key from registrant IDs.

        Using a hash instead of frozenset avoids unbounded cache key growth
        with large registrant populations (e.g., 100k+ records).

        :param registrant_ids: List or frozenset of registrant IDs
        :returns: MD5 hash of sorted IDs
        :rtype: str
        """
        if isinstance(registrant_ids, frozenset):
            registrant_ids = list(registrant_ids)
        sorted_ids = sorted(registrant_ids)
        id_str = ",".join(str(i) for i in sorted_ids)
        return hashlib.md5(id_str.encode()).hexdigest()

    @api.model
    @tools.ormcache("dimension_id", "dimension_write_date", "registrant_ids_key")
    def _compute_evaluations(self, dimension_id, dimension_write_date, registrant_ids_key, registrant_ids_list):
        """
        Compute and cache dimension evaluations for a set of registrants.

        This method is cached via @ormcache. The cache key includes write_date
        to auto-invalidate when dimension changes.

        :param dimension_id: ID of spp.demographic.dimension
        :param dimension_write_date: dimension.write_date (for cache invalidation)
        :param registrant_ids_key: Hash of registrant IDs (compact cache key)
        :param registrant_ids_list: Actual list of registrant IDs (not cached)
        :returns: Dictionary mapping registrant_id → category value
        :rtype: dict
        """
        dimension = self.env["spp.demographic.dimension"].sudo().browse(dimension_id)
        if not dimension.exists():
            return {}

        result = {}
        partner_model = self.env["res.partner"].sudo()
        partners = partner_model.browse(registrant_ids_list)

        for partner in partners:
            value = dimension.evaluate_for_record(partner)
            result[partner.id] = value

        return result

    @api.model
    def evaluate_dimension_batch(self, dimension, registrant_ids):
        """
        Evaluate dimension for a batch of registrants with caching.

        Uses @ormcache decorator for automatic caching and invalidation.

        :param dimension: spp.demographic.dimension record
        :param registrant_ids: List of partner IDs
        :returns: Dictionary mapping partner_id → category value
        :rtype: dict
        """
        if not dimension or not registrant_ids:
            return {}

        # Create compact hash key from registrant IDs
        registrant_ids_key = self._make_registrant_key(registrant_ids)

        # Get write_date for cache key
        write_date = dimension.write_date.isoformat() if dimension.write_date else "none"

        # Call cached method - this will use cache if available
        # Pass both hash key (for cache) and actual list (for computation)
        result = self._compute_evaluations(dimension.id, write_date, registrant_ids_key, list(registrant_ids))

        if result:
            _logger.debug("Evaluated dimension %s for %d registrants", dimension.name, len(registrant_ids))

        return result

    @api.model
    def clear_dimension_cache(self, dimension_id=None):
        """
        Clear dimension evaluation cache.

        Invalidates this model's cache, which is more targeted than clearing
        the entire registry but still clears all ormcache entries for this model.

        :param dimension_id: Specific dimension to clear, or None for all
        """
        if dimension_id:
            _logger.info("Clearing cache for dimension ID %s", dimension_id)
        else:
            _logger.info("Clearing all dimension caches")

        # Invalidate this model's cache
        # More targeted than self.env.registry.clear_cache() but still broad
        # within this model. Granular per-dimension clearing would require
        # restructuring the cache key to make dimension_id the primary key.
        self.invalidate_model()

    @api.model
    def warm_cache(self, dimensions, registrant_ids):
        """
        Pre-warm cache for common dimension sets.

        :param dimensions: List of spp.demographic.dimension records
        :param registrant_ids: List of partner IDs
        """
        _logger.info("Warming cache for %d dimensions, %d registrants", len(dimensions), len(registrant_ids))
        for dimension in dimensions:
            self.evaluate_dimension_batch(dimension, registrant_ids)
