# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the authenticated DCI ping endpoint."""

import asyncio

from odoo.tests import tagged

from odoo.addons.spp_dci_server.middleware.signature import verify_bearer_token
from odoo.addons.spp_dci_server.routers.ping import dci_ping_router, ping

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@tagged("post_install", "-at_install")
class TestPingRouter(DCIServerCommon):
    def test_ping_returns_ok_with_sender_id(self):
        """A reachable, authenticated ping returns the server's sender id."""
        self.env["ir.config_parameter"].sudo().set_param("dci.sender_id", "openspp.test.server")
        result = _run(ping(self.env, "a-valid-token"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["sender_id"], "openspp.test.server")

    def test_ping_requires_bearer_token(self):
        """The route must be gated by verify_bearer_token so a bad/missing
        token yields 401 rather than a misleading success."""
        route = next(r for r in dci_ping_router.routes if getattr(r, "path", None) == "/ping")
        dependency_calls = [dep.call for dep in route.dependant.dependencies]
        self.assertIn(
            verify_bearer_token,
            dependency_calls,
            "ping endpoint must depend on verify_bearer_token",
        )
