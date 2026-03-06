# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import hashlib
import json
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AggregationCacheService(models.AbstractModel):
    """
    Cache service for aggregation results.

    This service manages caching of aggregation results to improve performance
    for frequently requested scopes and statistics. Results are stored in
    spp.analytics.cache.entry with TTL-based expiration.

    TTL Configuration by Scope Type:
    - area: 1 hour (3600 seconds) - administrative data is relatively static
    - cel: 15 minutes (900 seconds) - expressions may reference dynamic data
    - spatial_polygon: No cache (0) - spatial queries are too varied
    - spatial_buffer: No cache (0) - buffer queries are too varied
    - area_tag: 1 hour (3600 seconds) - tag-based queries are relatively static
    - explicit: 30 minutes (1800 seconds) - explicit lists may change
    """

    _name = "spp.analytics.cache"
    _description = "Aggregation Cache Service"

    # TTL configuration in seconds
    TTL_CONFIG = {
        "area": 3600,  # 1 hour
        "cel": 900,  # 15 minutes
        "spatial_polygon": 0,  # No cache
        "spatial_buffer": 0,  # No cache
        "area_tag": 3600,  # 1 hour
        "explicit": 1800,  # 30 minutes
    }

    @api.model
    def get_cached_result(self, scope, statistics=None, group_by=None):
        """
        Get cached aggregation result if available and not expired.

        :param scope: spp.analytics.scope record, ID, or dict
        :param statistics: List of statistic names (None for defaults)
        :param group_by: List of dimension names for breakdown
        :returns: Cached result dictionary or None if not found/expired
        :rtype: dict or None
        """
        # Resolve scope to get scope type
        scope_record = self._resolve_scope(scope)
        scope_type = self._get_scope_type(scope_record)

        # Check if caching is enabled for this scope type
        ttl = self._get_ttl_for_scope_type(scope_type)
        if ttl == 0:
            _logger.debug("Caching disabled for scope type: %s", scope_type)
            return None

        # Generate cache key
        cache_key = self._generate_cache_key(scope_record, statistics, group_by)

        # Find cache entry (use sudo for internal caching operation)
        entry = (
            self.env["spp.analytics.cache.entry"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [("cache_key", "=", cache_key)],
                limit=1,
            )
        )

        if not entry:
            _logger.debug("Cache miss for key: %s", cache_key)
            return None

        # Check if expired
        now = fields.Datetime.now()
        expires_at = entry.computed_at + timedelta(seconds=ttl)

        if now > expires_at:
            _logger.debug(
                "Cache expired for key: %s (computed at %s, expired at %s)", cache_key, entry.computed_at, expires_at
            )
            # Clean up expired entry
            entry.unlink()
            return None

        _logger.debug("Cache hit for key: %s (computed at %s, expires at %s)", cache_key, entry.computed_at, expires_at)

        # Parse and return result
        try:
            result = json.loads(entry.result_json)
            # Mark that this result came from cache
            result["from_cache"] = True
            return result
        except json.JSONDecodeError as e:
            _logger.warning("Invalid JSON in cache entry %s: %s", entry.id, e)
            entry.unlink()
            return None

    @api.model
    def store_result(self, scope, statistics, group_by, result):
        """
        Store aggregation result in cache.

        :param scope: spp.analytics.scope record, ID, or dict
        :param statistics: List of statistic names
        :param group_by: List of dimension names
        :param result: Aggregation result dictionary
        :returns: True if stored, False if caching disabled
        :rtype: bool
        """
        # Resolve scope to get scope type
        scope_record = self._resolve_scope(scope)
        scope_type = self._get_scope_type(scope_record)

        # Check if caching is enabled for this scope type
        ttl = self._get_ttl_for_scope_type(scope_type)
        if ttl == 0:
            _logger.debug("Caching disabled for scope type: %s", scope_type)
            return False

        # Generate cache key
        cache_key = self._generate_cache_key(scope_record, statistics, group_by)

        # Serialize result
        try:
            result_json = json.dumps(result, default=str)
        except (TypeError, ValueError) as e:
            _logger.warning("Failed to serialize result for caching: %s", e)
            return False

        # Store or update cache entry (use sudo for internal caching operation)
        cache_model = self.env["spp.analytics.cache.entry"].sudo()  # nosemgrep: odoo-sudo-without-context
        existing = cache_model.search(
            [("cache_key", "=", cache_key)],
            limit=1,
        )

        values = {
            "cache_key": cache_key,
            "scope_type": scope_type,
            "result_json": result_json,
            "computed_at": fields.Datetime.now(),
        }

        if existing:
            existing.write(values)
            _logger.debug("Updated cache entry for key: %s", cache_key)
        else:
            cache_model.create(values)
            _logger.debug("Created cache entry for key: %s", cache_key)

        return True

    @api.model
    def invalidate_scope(self, scope):
        """
        Invalidate all cache entries for a specific scope.

        This is useful when the underlying data for a scope changes
        (e.g., registrants are added/removed from an area).

        Note: Currently this invalidates all cache entries of the same scope type.
        For more granular invalidation, consider adding a scope_id foreign key
        to the cache entry model in a future update.

        :param scope: spp.analytics.scope record, ID, or dict
        :returns: Number of cache entries invalidated
        :rtype: int
        """
        scope_record = self._resolve_scope(scope)
        scope_type = self._get_scope_type(scope_record)

        # Invalidate all cache entries of this scope type
        # This is a conservative approach - it may invalidate more than needed,
        # but ensures consistency
        entries = (
            self.env["spp.analytics.cache.entry"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search([("scope_type", "=", scope_type)])
        )

        count = len(entries)
        if count > 0:
            entries.unlink()
            _logger.info(
                "Invalidated %d cache entries for scope type %s",
                count,
                scope_type,
            )

        return count

    @api.model
    def invalidate_all(self):
        """
        Invalidate all aggregation cache entries.

        This is useful for debugging or when performing bulk data updates
        that affect many scopes.

        :returns: Number of cache entries invalidated
        :rtype: int
        """
        entries = self.env["spp.analytics.cache.entry"].sudo().search([])  # nosemgrep: odoo-sudo-without-context
        count = len(entries)

        if count > 0:
            entries.unlink()
            _logger.info("Invalidated all %d cache entries", count)

        return count

    @api.model
    def cleanup_expired(self):
        """
        Clean up expired cache entries.

        This should be called periodically (e.g., via cron) to prevent
        the cache table from growing indefinitely.

        :returns: Number of cache entries removed
        :rtype: int
        """
        now = fields.Datetime.now()
        removed = 0

        for scope_type, ttl in self.TTL_CONFIG.items():
            if ttl == 0:
                continue  # Skip non-cached types

            expires_before = now - timedelta(seconds=ttl)

            entries = (
                self.env["spp.analytics.cache.entry"]  # nosemgrep: odoo-sudo-without-context
                .sudo()
                .search(
                    [
                        ("scope_type", "=", scope_type),
                        ("computed_at", "<", expires_before),
                    ]
                )
            )

            count = len(entries)
            if count > 0:
                entries.unlink()
                removed += count
                _logger.debug("Removed %d expired %s cache entries", count, scope_type)

        if removed > 0:
            _logger.info("Cleaned up %d expired cache entries", removed)

        return removed

    def _generate_cache_key(self, scope, statistics, group_by):
        """
        Generate a unique cache key for an aggregation query.

        The key is a hash of:
        - Scope definition (type + parameters)
        - Statistics list
        - Group by dimensions

        :param scope: Scope record or dict
        :param statistics: List of statistic names
        :param group_by: List of dimension names
        :returns: Cache key string (hex hash)
        :rtype: str
        """
        # Normalize inputs
        statistics = sorted(statistics) if statistics else []
        group_by = sorted(group_by) if group_by else []

        # Build key components
        key_parts = self._get_scope_key_parts(scope)

        # Add statistics and group_by
        key_parts.extend(statistics)
        key_parts.extend(group_by)

        # Generate hash
        key_string = "|".join(str(p) for p in key_parts)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()

        return key_hash

    def _get_scope_key_parts(self, scope):
        """
        Extract key components from scope for cache key generation.

        :param scope: Scope record or dict
        :returns: List of key components
        :rtype: list
        """
        key_parts = []

        if isinstance(scope, dict):
            # Inline scope definition
            scope_type = scope.get("scope_type")
            key_parts.append(scope_type)

            if scope_type == "area":
                key_parts.append(f"area:{scope.get('area_id')}")
                key_parts.append(f"children:{scope.get('include_child_areas', True)}")
            elif scope_type == "cel":
                key_parts.append(f"expr:{scope.get('cel_expression')}")
                key_parts.append(f"profile:{scope.get('cel_profile', 'registry_individuals')}")
            elif scope_type == "spatial_polygon":
                key_parts.append(f"geojson:{scope.get('geometry_geojson')}")
            elif scope_type == "spatial_buffer":
                key_parts.append(f"lat:{scope.get('buffer_center_latitude')}")
                key_parts.append(f"lon:{scope.get('buffer_center_longitude')}")
                key_parts.append(f"radius:{scope.get('buffer_radius_km')}")
            elif scope_type == "area_tag":
                tag_ids = scope.get("area_tag_ids", [])
                key_parts.append(f"tags:{sorted(tag_ids)}")
            elif scope_type == "explicit":
                partner_ids = scope.get("explicit_partner_ids", [])
                key_parts.append(f"partners:{sorted(partner_ids)}")
        else:
            # Scope record
            scope_type = scope.scope_type
            key_parts.append(scope_type)
            key_parts.append(f"scope_id:{scope.id}")

        return key_parts

    def _get_scope_type(self, scope):
        """
        Get scope type from scope record or dict.

        :param scope: Scope record or dict
        :returns: Scope type string
        :rtype: str
        """
        if isinstance(scope, dict):
            return scope.get("scope_type", "explicit")
        return scope.scope_type

    def _get_ttl_for_scope_type(self, scope_type):
        """
        Get TTL (time-to-live) in seconds for a scope type.

        :param scope_type: Scope type string
        :returns: TTL in seconds (0 = no cache)
        :rtype: int
        """
        return self.TTL_CONFIG.get(scope_type, 0)

    def _resolve_scope(self, scope):
        """
        Resolve scope input to a scope record or dict.

        :param scope: Record, ID, or dict
        :returns: Scope record or dict
        """
        if isinstance(scope, dict):
            return scope

        if isinstance(scope, int):
            return self.env["spp.analytics.scope"].browse(scope)

        return scope


class AggregationCacheEntry(models.Model):
    """
    Cache entry for aggregation results.

    Stores cached results with TTL-based expiration. Each entry represents
    a single aggregation query result.
    """

    _name = "spp.analytics.cache.entry"
    _description = "Aggregation Cache Entry"
    _order = "computed_at desc"

    cache_key = fields.Char(
        string="Cache Key",
        required=True,
        index=True,
        help="Unique cache key (SHA256 hash of scope + statistics + group_by)",
    )
    scope_type = fields.Selection(
        selection=[
            ("cel", "CEL Expression"),
            ("spatial_polygon", "Within Polygon"),
            ("spatial_buffer", "Within Distance"),
            ("area", "Administrative Area"),
            ("area_tag", "Area Tags"),
            ("explicit", "Explicit IDs"),
        ],
        required=True,
        index=True,
        help="Scope type for this cache entry",
    )
    result_json = fields.Text(
        string="Result (JSON)",
        required=True,
        help="Cached aggregation result as JSON",
    )
    computed_at = fields.Datetime(
        string="Computed At",
        required=True,
        default=fields.Datetime.now,
        index=True,
        help="When this result was computed",
    )

    _sql_constraints = [
        (
            "cache_key_unique",
            "UNIQUE(cache_key)",
            "Cache key must be unique",
        ),
    ]

    @api.model
    def cron_cleanup_expired(self):
        """
        Cron job method to clean up expired cache entries.

        This is a wrapper around the cache service's cleanup_expired method
        that can be called from ir.cron.

        :returns: Number of cache entries removed
        :rtype: int
        """
        return self.env["spp.analytics.cache"].cleanup_expired()
