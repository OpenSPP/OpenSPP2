# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI receipt router (POST /receipt and /sync/receipt).

The router looks up a notification log by notification_id or
subscription_code, marks it received, and returns a signed DCI
envelope. Cases:

- valid receipt for an existing notification → status 'succ'
- valid receipt for a missing notification → status 'succ' with
  ``warn.notification.not_found``
- malformed ReceiptRequest → 400
- unexpected exception → 500
- ``/sync/receipt`` is a thin wrapper that delegates
"""

import asyncio
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@tagged("post_install", "-at_install")
class TestReceiptRouter(DCIServerCommon):
    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers.receipt import (
            submit_receipt,
            sync_receipt,
        )

        self.submit_receipt = submit_receipt
        self.sync_receipt = sync_receipt
        self.test_sender = self.create_test_sender()
        self.Subscription = self.env["spp.dci.subscription"].sudo()
        self.NotificationLog = self.env["spp.dci.notification.log"].sudo()

    def _build_envelope(self, message):
        envelope_data = self.create_signed_envelope(message=message, action="receipt")
        return DCIEnvelope(**envelope_data)

    def _build_receipt_message(
        self,
        transaction_id="txn-receipt-1",
        notification_id=None,
        subscription_code=None,
    ):
        receipt_info = {"receipt_type": "notification"}
        if notification_id:
            receipt_info["notification_id"] = notification_id
        if subscription_code:
            receipt_info["subscription_code"] = subscription_code
        return {
            "transaction_id": transaction_id,
            "receipt_information": receipt_info,
        }

    def _call(self, envelope, verified_sender_id=None):
        return _run(
            self.submit_receipt(
                envelope,
                self.env,
                _bearer_token="t",
                verified_sender_id=verified_sender_id or self.test_sender.sender_id,
                _rate_limit_check=None,
            )
        )

    def _make_notification(self, notification_id="NOTIF-001"):
        """Create a subscription + notification log entry."""
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://callback.example.com/notify",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )
        log = self.NotificationLog.create(
            {
                "subscription_id": sub.id,
                "notification_id": notification_id,
                "event_type": "registration",
                "record_count": 1,
                "status": "sent",
            }
        )
        return sub, log

    # --- matched receipt updates the log -------------------------------------

    def test_receipt_with_known_notification_marks_received(self):
        sub, log = self._make_notification("NOTIF-MATCH-001")
        envelope = self._build_envelope(
            self._build_receipt_message(notification_id="NOTIF-MATCH-001"),
        )

        response = self._call(envelope)
        self.assertIsInstance(response, DCIEnvelope)
        self.assertEqual(response.header.status, "succ")
        self.assertIsNone(response.header.status_reason_code)

        log.invalidate_recordset()
        self.assertTrue(log.receipt_received)
        self.assertEqual(log.receipt_transaction_id, "txn-receipt-1")
        self.assertEqual(log.status, "received")

    def test_subscription_code_fallback_finds_latest_unacked(self):
        sub, log = self._make_notification("NOTIF-SUB-001")
        envelope = self._build_envelope(
            self._build_receipt_message(subscription_code=sub.subscription_code),
        )

        response = self._call(envelope)
        self.assertEqual(response.header.status, "succ")

        log.invalidate_recordset()
        self.assertTrue(log.receipt_received)

    # --- unmatched receipt still ACKs but warns ------------------------------

    def test_receipt_for_unknown_notification_warns(self):
        envelope = self._build_envelope(
            self._build_receipt_message(notification_id="NOTIF-NOWHERE"),
        )
        response = self._call(envelope)
        # Receipt itself succeeds; the warning is carried in the reason
        # code so callers can tell the difference.
        self.assertEqual(response.header.status, "succ")
        self.assertEqual(
            response.header.status_reason_code,
            "warn.notification.not_found",
        )

    # --- request validation --------------------------------------------------

    def test_invalid_receipt_request_returns_400(self):
        envelope = self._build_envelope({"bogus": "payload"})
        with self.assertRaises(HTTPException) as ctx:
            self._call(envelope)
        self.assertEqual(ctx.exception.status_code, 400)

    # --- top-level catch-all -------------------------------------------------

    def test_unexpected_error_returns_500(self):
        envelope = self._build_envelope(
            self._build_receipt_message(notification_id="NOTIF-BOOM"),
        )
        with patch(
            "odoo.addons.spp_dci_server.routers.receipt.get_sender_id",
            side_effect=RuntimeError("config exploded"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._call(envelope)
        self.assertEqual(ctx.exception.status_code, 500)

    # --- sync wrapper delegates ----------------------------------------------

    def test_sync_receipt_delegates_to_submit_receipt(self):
        sub, log = self._make_notification("NOTIF-SYNC-001")
        envelope = self._build_envelope(
            self._build_receipt_message(notification_id="NOTIF-SYNC-001"),
        )
        response = _run(
            self.sync_receipt(
                envelope,
                self.env,
                _bearer_token="t",
                verified_sender_id=self.test_sender.sender_id,
                _rate_limit_check=None,
            )
        )
        self.assertEqual(response.header.status, "succ")
        log.invalidate_recordset()
        self.assertTrue(log.receipt_received)
