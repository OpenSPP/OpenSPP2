# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the IBR callback router (/ibr/on-search, /ibr/on-subscribe)."""

import asyncio
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException

from .common import IBRClientCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _request():
    req = MagicMock()
    req.client.host = "203.0.113.5"
    return req


@tagged("post_install", "-at_install")
class TestIBRCallback(IBRClientCommon):
    def setUp(self):
        super().setUp()
        self.test_sender = self.create_test_ibr_sender()
        from odoo.addons.spp_dci_client_ibr.routers import callback

        self.callback = callback
        self.Partner = self.env["res.partner"]
        self.DupCheck = self.env["spp.dci.duplication.check"].sudo()

    def _envelope(self, message):
        data = self.create_signed_envelope(action="on-search", message=message)
        return DCIEnvelope(**data)

    def _call_search(self, message, sender_id=None):
        return _run(
            self.callback.receive_ibr_search_response(
                _request(),
                self._envelope(message),
                self.env,
                verified_sender_id=sender_id or self.test_sender_id,
            )
        )

    # --- on-search -----------------------------------------------------------

    def test_on_search_ack(self):
        result = self._call_search({"transaction_id": "t1", "correlation_id": "c1", "search_response": []})
        self.assertEqual(result["message"]["ack_status"], "rcvd")
        self.assertEqual(result["message"]["correlation_id"], "c1")

    def test_on_search_updates_pending_check_to_match(self):
        partner = self.Partner.create({"name": "Dup Target", "is_registrant": True})
        check = self.DupCheck.create(
            {
                "partner_id": partner.id,
                "identifier_type": "UIN",
                "identifier_value": "U-1",
                "result": "no_match",
                "state": "checking",
                "notes": "correlation: CORR-9",
            }
        )
        message = {
            "transaction_id": "t2",
            "correlation_id": "CORR-9",
            "search_response": [
                {
                    "status": "succ",
                    "data": {
                        "reg_records": [
                            {"programs": [{"name": "Cash Transfer"}]},
                        ]
                    },
                }
            ],
        }
        self._call_search(message)
        check.invalidate_recordset()
        self.assertEqual(check.state, "completed")
        self.assertEqual(check.result, "confirmed_match")
        self.assertIn("Cash Transfer", check.matched_programs)

    def test_on_search_no_records_is_no_match(self):
        partner = self.Partner.create({"name": "NoDup", "is_registrant": True})
        check = self.DupCheck.create(
            {
                "partner_id": partner.id,
                "identifier_type": "UIN",
                "identifier_value": "U-2",
                "result": "no_match",
                "state": "checking",
                "notes": "correlation: CORR-NONE",
            }
        )
        self._call_search(
            {
                "correlation_id": "CORR-NONE",
                "search_response": [{"status": "succ", "data": {"reg_records": []}}],
            }
        )
        check.invalidate_recordset()
        self.assertEqual(check.result, "no_match")
        self.assertEqual(check.state, "completed")

    def test_on_search_non_success_item_skipped(self):
        # No pending check, non-succ status -> just logged, still acks.
        result = self._call_search(
            {
                "correlation_id": "C-X",
                "search_response": [{"status": "rjct", "status_reason_message": "bad"}],
            }
        )
        self.assertEqual(result["message"]["ack_status"], "rcvd")

    def test_on_search_processing_error_returns_500(self):
        with patch.object(self.callback, "_process_ibr_search_result", side_effect=RuntimeError("boom")):
            with self.assertRaises(HTTPException) as ctx:
                self._call_search({"correlation_id": "C", "search_response": [{"status": "succ"}]})
        self.assertEqual(ctx.exception.status_code, 500)

    # --- on-subscribe --------------------------------------------------------

    def test_on_subscribe_ack(self):
        data = self.create_signed_envelope(action="on-subscribe", message={"correlation_id": "S-1"})
        result = _run(
            self.callback.receive_ibr_subscribe_response(
                _request(),
                DCIEnvelope(**data),
                self.env,
                verified_sender_id=self.test_sender_id,
            )
        )
        self.assertEqual(result["message"]["ack_status"], "rcvd")
        self.assertEqual(result["message"]["correlation_id"], "S-1")
