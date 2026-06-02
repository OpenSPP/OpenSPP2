# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the JWKS router."""

import asyncio
from unittest.mock import patch

from odoo.tests import tagged

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@tagged("post_install", "-at_install")
class TestJWKSRouter(DCIServerCommon):
    """The /.well-known/jwks.json endpoint must:

    - return ``{"keys": []}`` when no active keys exist (cold install),
    - surface every active key's JWKS entry,
    - tolerate a per-key serialisation error and keep going,
    - tolerate a catastrophic error and return an empty key set instead
      of breaking external systems that cache JWKS.
    """

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers.jwks import get_jwks

        self.get_jwks = get_jwks
        self.SigningKey = self.env["spp.dci.signing.key"].sudo()
        self.env["ir.config_parameter"].sudo().set_param("dci.sender_id", "openspp.test")
        # Drop any default-installed keys so each test starts from a
        # known state.
        self.SigningKey.search([]).unlink()

    def _make_active_key(self, key_id):
        key = self.SigningKey.create(
            {
                "name": f"Test Key {key_id}",
                "key_id": key_id,
                "algorithm": "ed25519",
            }
        )
        key.action_generate_key()
        key.action_activate()
        return key

    def _call(self):
        return _run(self.get_jwks(self.env))

    def test_no_active_keys_returns_empty(self):
        result = self._call()
        self.assertEqual(result, {"keys": []})

    def test_active_keys_are_returned(self):
        self._make_active_key("jwks-1")
        result = self._call()
        self.assertEqual(len(result["keys"]), 1)
        entry = result["keys"][0]
        self.assertEqual(entry["kid"], "openspp.test|jwks-1|ed25519")
        self.assertEqual(entry["alg"], "EdDSA")

    def test_only_active_keys_surface(self):
        """draft and revoked keys must not leak into the JWKS response."""
        self._make_active_key("active-1")
        # Draft key (just created, not activated)
        self.SigningKey.create({"name": "Draft", "key_id": "draft-1", "algorithm": "ed25519"})
        # Revoked key
        revoked = self._make_active_key("revoked-1")
        revoked.action_revoke()

        result = self._call()
        self.assertEqual(len(result["keys"]), 1)
        self.assertEqual(result["keys"][0]["kid"], "openspp.test|active-1|ed25519")

    def test_bad_key_does_not_break_the_set(self):
        """If one key's get_jwks_entry blows up, the others still ship."""
        self._make_active_key("good")
        bad = self._make_active_key("bad")

        real_get_jwks_entry = type(bad).get_jwks_entry

        def selective_failure(self):
            if self.key_id == "bad":
                raise RuntimeError("simulated serialisation failure")
            return real_get_jwks_entry(self)

        with patch.object(type(bad), "get_jwks_entry", selective_failure):
            result = self._call()

        self.assertEqual(len(result["keys"]), 1)
        self.assertEqual(result["keys"][0]["kid"], "openspp.test|good|ed25519")

    def test_catastrophic_failure_returns_empty_set(self):
        """A failure outside the per-key loop must still return ``{"keys": []}``
        - JWKS callers cache the response and breaking them would cascade."""
        with patch.object(
            type(self.env["spp.dci.signing.key"]),
            "search",
            side_effect=RuntimeError("registry down"),
        ):
            result = self._call()
        self.assertEqual(result, {"keys": []})
