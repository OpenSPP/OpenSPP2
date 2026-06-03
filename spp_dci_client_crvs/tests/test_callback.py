# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the CRVS callback router (/crvs notification endpoint)."""

import asyncio
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException

from .common import CRVSClientCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _request():
    req = MagicMock()
    req.client.host = "203.0.113.9"
    return req


CRVS_SERVICE = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService"


@tagged("post_install", "-at_install")
class TestCRVSCallback(CRVSClientCommon):
    def setUp(self):
        super().setUp()
        self.test_sender = self.create_test_crvs_sender()
        from odoo.addons.spp_dci_client_crvs.routers import callback

        self.callback = callback

    def _envelope(self, message=None):
        data = self.create_signed_envelope(action="notify", message=message)
        return DCIEnvelope(**data)

    def _call(self, message=None, sender_id=None):
        return _run(
            self.callback.receive_crvs_notification(
                _request(),
                self._envelope(message),
                self.env,
                verified_sender_id=sender_id or self.test_sender_id,
            )
        )

    def test_notification_via_service(self):
        """Happy path: CRVSService.process_notification handles the event."""
        with (
            patch(f"{CRVS_SERVICE}.process_notification", return_value=42),
            patch(f"{CRVS_SERVICE}.__init__", return_value=None),
        ):
            result = self._call({"event_type": "birth", "event_date": "2024-01-01"})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["event_id"], 42)

    def test_notification_fallback_creates_event_directly(self):
        """If CRVSService init fails, the router falls back to creating the
        event record directly via _create_event_directly."""
        message = {
            "event_type": "birth",
            "event_date": "2024-01-02",
            "identifiers": [{"type": "national_id", "value": "FALLBACK-1"}],
        }
        with patch(f"{CRVS_SERVICE}.__init__", side_effect=RuntimeError("no data source")):
            result = self._call(message)
        self.assertEqual(result["status"], "success")
        ev = self.env["spp.dci.crvs.event"].search([("identifier_value", "=", "FALLBACK-1")], limit=1)
        self.assertTrue(ev)

    def test_notification_processing_error_returns_500(self):
        with (
            patch(f"{CRVS_SERVICE}.__init__", return_value=None),
            patch(f"{CRVS_SERVICE}.process_notification", side_effect=RuntimeError("boom")),
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._call({"event_type": "death"})
        self.assertEqual(ctx.exception.status_code, 500)

    def test_create_event_directly_helper(self):
        """Directly exercise the fallback helper."""
        notification = {
            "header": {"sender_id": "crvs.national.gov", "action": "notify"},
            "message": {
                "event_type": "DEATH",
                "event_date": "2024-05-05",
                "identifiers": [{"type": "national_id", "value": "DIRECT-1"}],
            },
        }
        event_id = self.callback._create_event_directly(self.env, notification)
        ev = self.env["spp.dci.crvs.event"].browse(event_id)
        self.assertEqual(ev.event_type, "death")
        self.assertEqual(ev.identifier_value, "DIRECT-1")
