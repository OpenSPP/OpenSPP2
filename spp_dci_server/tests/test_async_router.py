# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI async router.

Covers async_search, subscribe, unsubscribe, and txn_status. Job_worker
dispatch is mocked: ``transaction.with_delay`` is patched on the
spp.dci.transaction class so we exercise the routing/transaction-record
plumbing without enqueueing real jobs.
"""

import asyncio
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException, Response

from odoo.tests import tagged

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _stub_delay():
    """Return a ``with_delay``-style stub: returns an object whose chained
    method calls produce a job-like with a uuid attribute."""

    def with_delay(*_args, **_kwargs):
        delayed = MagicMock()
        delayed.process_async_search.return_value = MagicMock(uuid="job-uuid-1")
        delayed.process_async_subscribe.return_value = MagicMock(uuid="job-uuid-2")
        delayed.process_async_unsubscribe.return_value = MagicMock(uuid="job-uuid-3")
        return delayed

    return with_delay


@tagged("post_install", "-at_install")
class _AsyncRouterCommon(DCIServerCommon):
    """Shared setup for every async-router test class."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers import async_router

        self.async_router = async_router
        self.test_sender = self.create_test_sender()
        # Auto-approve so subscribe goes through the action_confirm branch.
        self.test_sender.write({"auto_approve": True})

        self.Transaction = self.env["spp.dci.transaction"].sudo()
        # Patch with_delay on the transaction class so jobs aren't really
        # enqueued. apply per-test in tearDown handling.
        self._delay_patch = patch.object(
            type(self.Transaction),
            "with_delay",
            new=_stub_delay(),
        )
        self._delay_patch.start()
        self.addCleanup(self._delay_patch.stop)


# =============================================================================
# /search
# =============================================================================


@tagged("post_install", "-at_install")
class TestAsyncSearch(_AsyncRouterCommon):
    def _build_envelope(self, message=None):
        if message is None:
            message = {
                "transaction_id": f"txn-async-{uuid.uuid4()}",
                "search_request": [
                    {
                        "reference_id": "ref-1",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "search_criteria": {
                            "reg_type": "SOCIAL_REGISTRY",
                            "reg_event_type": "ACTIVE",
                            "query_type": "idtype-value",
                            "query": {"type": "ns:test", "value": "X-001"},
                        },
                    }
                ],
            }
        return DCIEnvelope(**self.create_signed_envelope(message=message, action="search"))

    def _call(self, envelope):
        return _run(
            self.async_router.async_search(
                envelope,
                self.env,
                _bearer_token="t",
                verified_sender_id=self.test_sender.sender_id,
                _rate_limit_check=None,
                response=Response(),
            )
        )

    def test_valid_request_creates_transaction_and_acks(self):
        envelope = self._build_envelope()
        ack = self._call(envelope)
        self.assertEqual(ack.message.ack_status, "ACK")
        # Transaction record exists
        txn = self.Transaction.search(
            [("message_id", "=", envelope.header.message_id)], limit=1
        )
        self.assertTrue(txn)
        self.assertEqual(txn.action, "search")
        self.assertEqual(txn.state, "pending")
        self.assertEqual(txn.job_uuid, "job-uuid-1")

    def test_invalid_search_request_returns_400(self):
        envelope = self._build_envelope(message={"bogus": "payload"})
        with self.assertRaises(HTTPException) as ctx:
            self._call(envelope)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unexpected_error_returns_500(self):
        envelope = self._build_envelope()
        with patch.object(
            type(self.Transaction),
            "create",
            side_effect=RuntimeError("db down"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._call(envelope)
        self.assertEqual(ctx.exception.status_code, 500)


# =============================================================================
# /subscribe
# =============================================================================


@tagged("post_install", "-at_install")
class TestSubscribe(_AsyncRouterCommon):
    def _build_envelope(self, message=None, sender_uri="https://cb.example.test/cb"):
        if message is None:
            message = {
                "transaction_id": f"txn-sub-{uuid.uuid4()}",
                "subscribe_request": [
                    {
                        "reference_id": "ref-sub-1",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "subscribe_criteria": {
                            "reg_type": "SOCIAL_REGISTRY",
                            "reg_event_type": "REGISTRATION",
                            "filter_type": "predicate",
                            "filter": {"any": "thing"},
                            "notify_record_type": "PERSON",
                        },
                    }
                ],
            }
        envelope = DCIEnvelope(
            **self.create_signed_envelope(message=message, action="subscribe")
        )
        envelope.header.sender_uri = sender_uri
        return envelope

    def _call(self, envelope, verified_sender_id=None):
        return _run(
            self.async_router.subscribe(
                envelope,
                self.env,
                _bearer_token="t",
                verified_sender_id=verified_sender_id or self.test_sender.sender_id,
                _rate_limit_check=None,
            )
        )

    def test_valid_subscribe_creates_subscription_and_transaction(self):
        envelope = self._build_envelope()
        ack = self._call(envelope)
        self.assertEqual(ack.message.ack_status, "ACK")
        # Subscription was created and (sender.auto_approve=True) confirmed
        subs = self.env["spp.dci.subscription"].sudo().search(
            [("sender_id", "=", self.test_sender.id)]
        )
        self.assertTrue(subs)
        self.assertEqual(subs[0].state, "active")  # action_confirm fires
        # Transaction record was created
        txn = self.Transaction.search(
            [("message_id", "=", envelope.header.message_id)], limit=1
        )
        self.assertTrue(txn)
        self.assertEqual(txn.action, "subscribe")

    def test_invalid_subscribe_request_returns_400(self):
        envelope = self._build_envelope(message={"bogus": "payload"})
        with self.assertRaises(HTTPException) as ctx:
            self._call(envelope)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unknown_sender_returns_403(self):
        envelope = self._build_envelope()
        with self.assertRaises(HTTPException) as ctx:
            self._call(envelope, verified_sender_id="sender.not.registered")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_missing_callback_uri_still_acks(self):
        """Operator may submit without sender_uri; subscription still records,
        callback is just not queued (logged as warning)."""
        envelope = self._build_envelope(sender_uri=None)
        # The envelope schema may require sender_uri; only run this when
        # we can build one without it.
        if envelope.header.sender_uri is None:
            ack = self._call(envelope)
            self.assertEqual(ack.message.ack_status, "ACK")
        else:
            self.skipTest("DCIMessageHeader populates sender_uri; can't suppress")


# =============================================================================
# /unsubscribe
# =============================================================================


@tagged("post_install", "-at_install")
class TestUnsubscribe(_AsyncRouterCommon):
    def setUp(self):
        super().setUp()
        # Create a subscription to cancel.
        self.subscription = self.env["spp.dci.subscription"].sudo().create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://cb.example.test/cb",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
            }
        )
        self.subscription.action_confirm()

    def _build_envelope(self, subscription_codes=None):
        message = {
            "transaction_id": f"txn-unsub-{uuid.uuid4()}",
            "timestamp": datetime.now(UTC).isoformat(),
            "subscription_codes": subscription_codes
            or [self.subscription.subscription_code],
        }
        envelope = DCIEnvelope(
            **self.create_signed_envelope(message=message, action="unsubscribe")
        )
        envelope.header.sender_uri = "https://cb.example.test/cb"
        return envelope

    def _call(self, envelope):
        return _run(
            self.async_router.unsubscribe(
                envelope,
                self.env,
                _bearer_token="t",
                verified_sender_id=self.test_sender.sender_id,
                _rate_limit_check=None,
            )
        )

    def test_valid_unsubscribe_cancels_subscription(self):
        envelope = self._build_envelope()
        ack = self._call(envelope)
        self.assertEqual(ack.message.ack_status, "ACK")
        self.subscription.invalidate_recordset()
        self.assertEqual(self.subscription.state, "cancelled")

    def test_unknown_subscription_code_still_acks(self):
        """The route logs a warning and continues; we still record a
        transaction so the caller knows we processed the request."""
        envelope = self._build_envelope(subscription_codes=["SUB-NOT-MINE"])
        ack = self._call(envelope)
        self.assertEqual(ack.message.ack_status, "ACK")

    def test_invalid_unsubscribe_request_returns_400(self):
        envelope = DCIEnvelope(
            **self.create_signed_envelope(message={"bogus": "payload"}, action="unsubscribe")
        )
        with self.assertRaises(HTTPException) as ctx:
            self._call(envelope)
        self.assertEqual(ctx.exception.status_code, 400)


# =============================================================================
# /sync/txn/status
# =============================================================================


@tagged("post_install", "-at_install")
class TestTxnStatus(_AsyncRouterCommon):
    def _build_envelope(self, attribute_type="transaction_id", attribute_value="txn-1", txn_type="search"):
        message = {
            "transaction_id": f"txn-stat-{uuid.uuid4()}",
            "txnstatus_request": {
                "reference_id": "ref-stat-1",
                "timestamp": datetime.now(UTC).isoformat(),
                "txn_type": txn_type,
                "attribute_type": attribute_type,
                "attribute_value": attribute_value,
            },
        }
        return DCIEnvelope(
            **self.create_signed_envelope(message=message, action="txn-status")
        )

    def _make_transaction(self, **overrides):
        defaults = {
            "transaction_id": "txn-stat-known",
            "message_id": "msg-stat-1",
            "correlation_id": str(uuid.uuid4()),
            "action": "search",
            "reg_type": "SOCIAL_REGISTRY",
            "sender_id": self.test_sender.id,
            "sender_uri": self.test_sender.sender_id,
            "state": "callback_sent",
            "dci_status": "succ",
        }
        defaults.update(overrides)
        return self.Transaction.create(defaults)

    def _call(self, envelope):
        return _run(
            self.async_router.txn_status(
                envelope,
                self.env,
                _bearer_token="t",
                verified_sender_id=self.test_sender.sender_id,
                _rate_limit_check=None,
            )
        )

    def test_known_transaction_returns_succ(self):
        self._make_transaction(transaction_id="txn-stat-known")
        envelope = self._build_envelope(attribute_value="txn-stat-known")
        result = self._call(envelope)
        self.assertIsInstance(result, DCIEnvelope)
        self.assertEqual(result.header.status, "succ")

    def test_unknown_transaction_returns_rjct(self):
        envelope = self._build_envelope(attribute_value="txn-stat-nowhere")
        result = self._call(envelope)
        self.assertEqual(result.header.status, "rjct")

    def test_correlation_id_lookup(self):
        corr = "corr-1-test"
        self._make_transaction(correlation_id=corr, transaction_id="txn-stat-corr")
        envelope = self._build_envelope(
            attribute_type="correlation_id",
            attribute_value=corr,
        )
        result = self._call(envelope)
        self.assertEqual(result.header.status, "succ")

    def test_reference_id_list_lookup_uses_message_id(self):
        self._make_transaction(
            transaction_id="txn-stat-ref",
            message_id="msg-stat-ref",
        )
        envelope = self._build_envelope(
            attribute_type="reference_id_list",
            attribute_value=["msg-stat-ref"],
        )
        result = self._call(envelope)
        self.assertEqual(result.header.status, "succ")

    def test_stored_response_payload_returned_verbatim(self):
        payload = {"custom": "stored response"}
        self._make_transaction(
            transaction_id="txn-stat-payload",
            response_payload=json.dumps(payload),
        )
        envelope = self._build_envelope(attribute_value="txn-stat-payload")
        result = self._call(envelope)
        # The payload is wrapped inside txnstatus_response.txn_status
        message = result.message
        self.assertEqual(
            message["txnstatus_response"]["txn_status"], payload
        )

    def test_malformed_response_payload_falls_back_to_minimal(self):
        self._make_transaction(
            transaction_id="txn-stat-malformed",
            response_payload="not json",
        )
        envelope = self._build_envelope(attribute_value="txn-stat-malformed")
        result = self._call(envelope)
        # Falls back to minimal search-response shape
        message = result.message
        txn_status = message["txnstatus_response"]["txn_status"]
        self.assertIn("search_response", txn_status)

    def test_invalid_txn_status_request_returns_400(self):
        envelope = DCIEnvelope(
            **self.create_signed_envelope(message={"bogus": "payload"}, action="txn-status")
        )
        with self.assertRaises(HTTPException) as ctx:
            self._call(envelope)
        self.assertEqual(ctx.exception.status_code, 400)
