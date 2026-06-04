# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the social-search and SR-alias routers."""

import asyncio
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from fastapi import HTTPException

from .common import DCISocialServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


SERVICE = "odoo.addons.spp_dci_server_social.services.search_service.DCISocialSearchService"


@tagged("post_install", "-at_install")
class TestSocialSearchRouter(DCISocialServerCommon):
    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server_social.routers import social_search, sr_alias

        self.social_search = social_search
        self.sr_alias = sr_alias

    def _request(self):
        # The router only forwards the request object to the service, which
        # we mock; a bare sentinel is sufficient.
        return MagicMock(name="SearchRequest")

    def test_sync_search_returns_service_response(self):
        sentinel = MagicMock(name="SearchResponse")
        with patch(SERVICE) as svc:
            svc.return_value.execute_search.return_value = sentinel
            result = _run(self.social_search.sync_search(self._request(), self.env))
        self.assertIs(result, sentinel)

    def test_sync_search_wraps_errors_as_500(self):
        with patch(SERVICE) as svc:
            svc.return_value.execute_search.side_effect = RuntimeError("kaboom")
            with self.assertRaises(HTTPException) as ctx:
                _run(self.social_search.sync_search(self._request(), self.env))
        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("kaboom", ctx.exception.detail)

    def test_sync_notify_returns_not_implemented_payload(self):
        result = _run(self.social_search.sync_notify(self.env))
        self.assertEqual(result["status"], "rjct")
        self.assertIn("not yet implemented", result["status_reason_message"])
        self.assertIn("T", result["timestamp"])

    def test_sr_alias_delegates_to_sync_search(self):
        sentinel = MagicMock(name="SearchResponse")
        with patch(SERVICE) as svc:
            svc.return_value.execute_search.return_value = sentinel
            result = _run(self.sr_alias.sr_sync_search(self._request(), self.env))
        self.assertIs(result, sentinel)
