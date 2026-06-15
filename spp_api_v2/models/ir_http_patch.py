# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Temporary patch for ir.http.routing_map to work around Odoo 19 cache bug.

This patch removes the problematic @tools.ormcache decorator that causes
NameError: name 'self' is not defined when building the routing map cache key.

This workaround should be removed when Odoo core fixes the cache bug.
"""

import hashlib
import logging
import threading

import werkzeug.routing

from odoo import models, tools
from odoo.http import ROUTING_KEYS
from odoo.modules.registry import Registry
from odoo.tools.misc import submap

from odoo.addons.base.models.ir_http import FasterRule

_logger = logging.getLogger(__name__)

# Stable 64-bit signed key for the transaction-scoped advisory lock that
# serializes FastAPI endpoint sync attempts across workers. Derived from a
# SHA-256 of the qualified name so it is deterministic and unlikely to collide
# with other modules' advisory locks in the same database.
_FASTAPI_SYNC_ADVISORY_LOCK_KEY = int.from_bytes(
    hashlib.sha256(b"spp_api_v2.fastapi_endpoint_sync").digest()[:8],
    byteorder="big",
    signed=True,
)


def _try_acquire_fastapi_sync_lock(cr):
    """Try to acquire the cross-worker FastAPI endpoint sync advisory lock.

    Returns True if this transaction got the lock, False otherwise (either
    because another backend holds it, or because the lock SQL itself failed —
    e.g. exhausted shared-lock memory, permissions). The lock is transaction-
    scoped (released automatically at COMMIT/ROLLBACK), so callers do not need
    to release it explicitly.

    Failing closed (returning False) is the safe default: callers will skip
    the sync, and the next routing_map call will retry. Logging at WARNING so
    a persistently broken lock primitive is visible — silently degrading to
    every-worker-races behaviour would mask the regression this patch fixes.
    """
    try:
        cr.execute(
            "SELECT pg_try_advisory_xact_lock(%s)",
            (_FASTAPI_SYNC_ADVISORY_LOCK_KEY,),
        )
        (got_lock,) = cr.fetchone()
        return got_lock
    except Exception as e:
        _logger.warning(
            "FastAPI endpoint sync advisory-lock acquire failed (%s); "
            "treating as 'lock held elsewhere' and skipping sync this round.",
            e,
        )
        return False


class IrHttp(models.AbstractModel):
    """Patch ir.http to fix routing_map cache bug"""

    _inherit = "ir.http"

    def routing_map(self, key=None):
        """
        Override routing_map to work around Odoo 19 cache bug.

        The original method uses @tools.ormcache('key', cache='routing') which
        has a bug where it tries to reference 'self._name' in a lambda that
        doesn't have 'self' in scope.

        This workaround bypasses the cache decorator and implements manual caching.
        """
        _logger.debug("ir_http_patch.routing_map called with key=%s", key)
        # Manual cache key generation (avoiding the buggy ormcache decorator)
        registry = Registry(threading.current_thread().dbname)
        installed = registry._init_modules.union(tools.config["server_wide_modules"])
        mods = sorted(installed)

        # Include endpoint route version in cache key to invalidate when routes change
        endpoint_route_version = 0
        try:
            from odoo.addons.endpoint_route_handler.registry import EndpointRegistry

            with registry.cursor() as cr:
                endpoint_registry = EndpointRegistry.registry_for(cr)
                endpoint_route_version = endpoint_registry.last_version()
        except Exception:
            pass

        cache_key = (
            self._name,
            "routing_map",
            key,
            tuple(mods),
            endpoint_route_version,
        )

        # Try to get from cache manually
        try:
            cache = registry._Registry__caches.get("routing")
            if cache and cache_key in cache:
                return cache[cache_key]
        except (AttributeError, KeyError, TypeError):
            pass

        # Ensure endpoint registry is synced for this database
        # This is critical in multi-db mode where endpoints might not be synced yet
        try:
            if "fastapi.endpoint" in registry:
                # Create a temporary environment to sync endpoints
                from odoo import SUPERUSER_ID
                from odoo.api import Environment

                with registry.cursor() as cr:
                    # Serialize concurrent sync attempts across workers. After a
                    # registry reload (e.g. -u all) every worker's routing_map()
                    # races to update the same fastapi_endpoint rows; without
                    # this lock all but one fail with SerializationFailure.
                    if not _try_acquire_fastapi_sync_lock(cr):
                        # Skipping is safe: the worker that DID get the lock will
                        # bump endpoint_route_version when it commits action_sync_registry().
                        # That version is part of our routing-map cache key (line ~89),
                        # and we re-read it per call, so any degraded routing map this
                        # worker caches now is keyed at the old version and is naturally
                        # invalidated on the next call after the winner commits. Bad
                        # window is bounded by winner-commit latency (seconds at most).
                        #
                        # INFO (not DEBUG) so it's visible at default log level —
                        # otherwise diagnosing transient missing routes after a
                        # cold start has nothing to go on. Fires at most once
                        # per registry reload per worker, so not noisy.
                        _logger.info(
                            "FastAPI endpoint sync skipped for %s — another worker is syncing",
                            registry.db_name,
                        )
                    else:
                        env = Environment(cr, SUPERUSER_ID, {})

                        # First check for endpoints with registry_sync=False (never synced)
                        unsynced_endpoints = env["fastapi.endpoint"].search([("registry_sync", "=", False)])

                        # Also check for endpoints that claim to be synced but have no routes
                        # This catches cases where routes were deleted or DB was reset
                        synced_endpoints = env["fastapi.endpoint"].search([("registry_sync", "=", True)])
                        if synced_endpoints and "endpoint.route" in env:
                            for endpoint in synced_endpoints:
                                route_exists = env["endpoint.route"].search_count(
                                    [("endpoint_id", "=", endpoint.id)], limit=1
                                )
                                if not route_exists:
                                    _logger.warning(
                                        "Endpoint '%s' (id=%d) claims to be synced but has no routes - forcing re-sync",
                                        endpoint.name,
                                        endpoint.id,
                                    )
                                    # Reset flag to trigger re-sync
                                    endpoint.registry_sync = False
                                    unsynced_endpoints |= endpoint

                        if unsynced_endpoints:
                            unsynced_endpoints.action_sync_registry()
                            _logger.info(
                                "Synced %d FastAPI endpoints for database %s",
                                len(unsynced_endpoints),
                                registry.db_name,
                            )
                            # cr.commit() ends the transaction and RELEASES the
                            # advisory lock acquired above. Do not add any sync
                            # work below this line — it would run unlocked and
                            # re-introduce the SerializationFailure race this
                            # patch exists to prevent.
                            cr.commit()
        except Exception as e:
            # If endpoint model doesn't exist or sync fails, continue anyway
            _logger.debug("Could not sync FastAPI endpoints: %s", e)

        # Generate routing map
        _logger.debug(
            "Generating routing map for key %s (version %s)",
            str(key),
            endpoint_route_version,
        )

        routing_map = werkzeug.routing.Map(strict_slashes=False, converters=self._get_converters())
        route_count = 0
        fastapi_routes = []
        for url, endpoint in self._generate_routing_rules(mods, converters=self._get_converters()):
            route_count += 1
            if endpoint.routing.get("type") == "fastapi":
                fastapi_routes.append(url)
            # Ensure endpoint.routing has 'readonly' key (required by Odoo HTTP routing)
            # FastAPI endpoints may not include this, so we add it with a default
            if "readonly" not in endpoint.routing:
                # Default to False (read/write) for FastAPI endpoints
                # Public endpoints (auth='public') could be readonly, but FastAPI handles auth differently
                endpoint.routing["readonly"] = False

            routing = submap(endpoint.routing, ROUTING_KEYS)
            if routing["methods"] is not None and "OPTIONS" not in routing["methods"]:
                routing["methods"] = [*routing["methods"], "OPTIONS"]
            rule = FasterRule(url, endpoint=endpoint, **routing)
            rule.merge_slashes = False
            routing_map.add(rule)

        _logger.debug(
            "Routing map built with %d routes, FastAPI routes: %s",
            route_count,
            fastapi_routes,
        )

        # Store in cache manually
        try:
            cache = registry._Registry__caches.get("routing")
            if cache is not None:
                cache[cache_key] = routing_map
        except (AttributeError, KeyError, TypeError):
            pass

        return routing_map
