# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Process-local cache of PyJWKClient instances keyed by issuer record id.

Each `spp.oauth.issuer` record with `key_source == 'jwks_uri'` gets its own
PyJWKClient, which in turn manages key caching with its own TTL. We keep one
PyJWKClient per record so that TTL/timeout config changes take effect on next
fetch and so that records can be invalidated independently when admins edit
or unlink them.

The cache is process-local. Multi-worker Odoo deployments each maintain their
own copy; that's fine — JWKS responses are public.
"""

import logging
import threading

from jwt import PyJWKClient

_logger = logging.getLogger(__name__)

_lock = threading.Lock()
_clients: dict[int, PyJWKClient] = {}


def get_jwks_client(issuer_record) -> PyJWKClient:
    """Return a (cached) PyJWKClient for the given spp.oauth.issuer record."""
    issuer_record.ensure_one()
    issuer_id = issuer_record.id
    with _lock:
        client = _clients.get(issuer_id)
        if client is None:
            client = PyJWKClient(
                issuer_record.jwks_uri,
                cache_keys=True,
                lifespan=issuer_record.jwks_cache_ttl_seconds or 3600,
                timeout=issuer_record.http_timeout_seconds or 5,
            )
            _clients[issuer_id] = client
            _logger.debug("Built new PyJWKClient for issuer id=%s uri=%s", issuer_id, issuer_record.jwks_uri)
    return client


def invalidate(issuer_ids):
    """Drop cached PyJWKClient(s) for the given record IDs."""
    if not issuer_ids:
        return
    with _lock:
        for issuer_id in issuer_ids:
            _clients.pop(issuer_id, None)
    _logger.debug("Invalidated JWKS client cache for issuer ids=%s", list(issuer_ids))


def clear():
    """Drop the entire cache. Intended for tests."""
    with _lock:
        _clients.clear()
