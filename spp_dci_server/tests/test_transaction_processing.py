# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the process_async_* methods and callback-related helpers on
``spp.dci.transaction``.

The existing test_transaction.py covers dci_status mapping and
_send_callback's HTTP path. This file fills in the orchestration
methods that job_worker hands off to (process_async_search, _subscribe,
_unsubscribe, _txn_status) plus the small pure helpers
(_get_callback_action, _build_minimal_txn_status, action_retry_callback,
action_view_job).
"""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import SearchResponse, SearchResponseItem

from .common import DCIServerCommon


@tagged("post_install", "-at_install")
class TestTransactionProcessing(DCIServerCommon):
    def setUp(self):
        super().setUp()
        self.test_sender = self.create_test_sender()
        self.Transaction = self.env["spp.dci.transaction"].sudo()

    def _make_search_payload(self):
        return {
            "header": {
                "version": "1.0.0",
                "message_id": str(uuid.uuid4()),
                "message_ts": datetime.now(UTC).isoformat(),
                "action": "search",
                "sender_id": self.test_sender.sender_id,
                "total_count": 1,
            },
            "message": {
                "transaction_id": f"txn-{uuid.uuid4()}",
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
            },
        }

    def _make_txn(self, action="search", state="received", **overrides):
        payload = self._make_search_payload()
        defaults = {
            "transaction_id": payload["message"]["transaction_id"],
            "message_id": payload["header"]["message_id"],
            "correlation_id": str(uuid.uuid4()),
            "action": action,
            "reg_type": "SOCIAL_REGISTRY",
            "sender_id": self.test_sender.id,
            "sender_uri": self.test_sender.sender_id,
            "request_payload": json.dumps(payload),
            "state": state,
        }
        defaults.update(overrides)
        return self.Transaction.create(defaults)

    # --- _get_callback_action ------------------------------------------------

    def test_get_callback_action_known_actions(self):
        cases = {
            "search": "on-search",
            "subscribe": "on-subscribe",
            "unsubscribe": "on-unsubscribe",
            "txn_status": "txn-on-status",
            "notify": "on-notify",
        }
        for action, expected in cases.items():
            with self.subTest(action=action):
                txn = self._make_txn(action=action)
                self.assertEqual(txn._get_callback_action(), expected)

    # --- _build_minimal_txn_status ------------------------------------------

    def test_build_minimal_txn_status_search(self):
        txn = self._make_txn()
        result = txn._build_minimal_txn_status(
            transaction_id="txn-1",
            status="succ",
            txn_type="search",
        )
        self.assertEqual(result["transaction_id"], "txn-1")
        self.assertEqual(result["search_response"][0]["status"], "succ")

    def test_build_minimal_txn_status_search_with_reason(self):
        txn = self._make_txn()
        result = txn._build_minimal_txn_status(
            transaction_id="txn-2",
            status="rjct",
            txn_type="search",
            status_reason_code="rjct.invalid",
            status_reason_message="something bad",
        )
        item = result["search_response"][0]
        self.assertEqual(item["status_reason_code"], "rjct.invalid")
        self.assertEqual(item["status_reason_message"], "something bad")

    def test_build_minimal_txn_status_subscribe(self):
        txn = self._make_txn()
        result = txn._build_minimal_txn_status(
            transaction_id="txn-3",
            status="succ",
            txn_type="subscribe",
        )
        self.assertIn("subscribe_response", result)
        self.assertNotIn("search_response", result)

    # --- process_async_search -----------------------------------------------

    def _make_search_response(self):
        return SearchResponse(
            transaction_id="txn-async",
            correlation_id="corr-async",
            search_response=[
                SearchResponseItem(
                    reference_id="ref-async",
                    timestamp=datetime.now(UTC),
                    status="succ",
                )
            ],
        )

    def test_process_async_search_success_without_callback(self):
        """Happy path: service returns a SearchResponse, transaction
        transitions to 'success' and persists the payload."""
        txn = self._make_txn(callback_uri=False)
        response = self._make_search_response()
        with patch("odoo.addons.spp_dci_server_social.services.DCISocialSearchService") as service_cls:
            service_cls.return_value.execute_search.return_value = response
            txn.process_async_search()

        self.assertEqual(txn.state, "success")
        self.assertTrue(txn.processed_at)
        # Response payload is the JSON-serialised response
        body = json.loads(txn.response_payload)
        self.assertEqual(body["transaction_id"], "txn-async")

    def test_process_async_search_sends_callback_when_uri_set(self):
        """When callback_uri is set, _send_callback is invoked."""
        txn = self._make_txn(callback_uri="https://cb.example.test/cb")
        response = self._make_search_response()
        with (
            patch("odoo.addons.spp_dci_server_social.services.DCISocialSearchService") as service_cls,
            patch.object(type(txn), "_send_callback") as send,
        ):
            service_cls.return_value.execute_search.return_value = response
            txn.process_async_search()
        send.assert_called_once_with(response)
        self.assertEqual(txn.state, "success")

    def test_process_async_search_rejects_on_service_error(self):
        """When the search service raises, the transaction is rejected
        with the error captured."""
        txn = self._make_txn()
        with patch("odoo.addons.spp_dci_server_social.services.DCISocialSearchService") as service_cls:
            service_cls.return_value.execute_search.side_effect = RuntimeError("service exploded")
            txn.process_async_search()
        self.assertEqual(txn.state, "rejected")
        self.assertIn("service exploded", txn.error_message)

    def test_process_async_search_rejects_unsupported_registry(self):
        """Only SOCIAL_REGISTRY is implemented; other valid reg_type
        values fall through to the UserError path."""
        txn = self._make_txn(reg_type="DR")
        txn.process_async_search()
        self.assertEqual(txn.state, "rejected")
        self.assertIn("Unsupported registry type", txn.error_message)

    # --- action_retry_callback ----------------------------------------------

    def test_action_retry_callback_reschedules_failed_callback(self):
        """Operators can manually retry a callback_failed transaction; the
        action stays callable but does not raise."""
        txn = self._make_txn(state="callback_failed", callback_uri="https://cb.example.test/cb")
        # Stub _send_callback so we don't actually issue an HTTP request.
        with patch.object(type(txn), "_send_callback") as send:
            txn.action_retry_callback()
        # No exception raised.

    # --- action_view_job ----------------------------------------------------

    def test_action_view_job_raises_when_job_missing(self):
        """If the job_uuid points at a non-existent queue.job, the action
        surfaces a UserError so the user sees a clear message."""
        from odoo.exceptions import UserError

        txn = self._make_txn(job_uuid="job-does-not-exist")
        with self.assertRaises(UserError):
            txn.action_view_job()


@tagged("post_install", "-at_install")
class TestTransactionAsyncProcessors(DCIServerCommon):
    """Cover process_async_subscribe / _unsubscribe / _txn_status and the
    dict-based callback sender they all delegate to."""

    def setUp(self):
        super().setUp()
        self.test_sender = self.create_test_sender()
        self.Transaction = self.env["spp.dci.transaction"].sudo()
        self.Subscription = self.env["spp.dci.subscription"].sudo()

    def _make_txn(self, action, message, state="received", **overrides):
        payload = {
            "header": {
                "version": "1.0.0",
                "message_id": str(uuid.uuid4()),
                "message_ts": datetime.now(UTC).isoformat(),
                "action": action,
                "sender_id": self.test_sender.sender_id,
                "total_count": 1,
            },
            "message": message,
        }
        defaults = {
            "transaction_id": message.get("transaction_id", f"txn-{uuid.uuid4()}"),
            "message_id": payload["header"]["message_id"],
            "correlation_id": str(uuid.uuid4()),
            "action": action,
            "reg_type": "SOCIAL_REGISTRY",
            "sender_id": self.test_sender.id,
            "sender_uri": self.test_sender.sender_id,
            "request_payload": json.dumps(payload),
            "state": state,
        }
        defaults.update(overrides)
        return self.Transaction.create(defaults)

    # --- process_async_subscribe ---------------------------------------------

    def test_subscribe_builds_response_from_subscriptions(self):
        txn_id = f"txn-sub-{uuid.uuid4()}"
        sub = self.Subscription.create(
            {
                "sender_id": self.test_sender.id,
                "callback_uri": "https://cb.example.test/cb",
                "event_type": "registration",
                "reg_type": "SOCIAL_REGISTRY",
                "original_transaction_id": txn_id,
            }
        )
        txn = self._make_txn(
            "subscribe",
            {"transaction_id": txn_id},
            callback_uri=False,
        )
        txn.process_async_subscribe()

        self.assertEqual(txn.state, "success")
        body = json.loads(txn.response_payload)
        codes = [r.get("subscription_code") for r in body["subscribe_response"]]
        self.assertIn(sub.subscription_code, codes)

    def test_subscribe_adds_placeholder_when_no_subscriptions(self):
        txn = self._make_txn(
            "subscribe",
            {"transaction_id": f"txn-sub-empty-{uuid.uuid4()}"},
            callback_uri=False,
        )
        txn.process_async_subscribe()
        self.assertEqual(txn.state, "success")
        body = json.loads(txn.response_payload)
        self.assertEqual(len(body["subscribe_response"]), 1)
        self.assertEqual(body["subscribe_response"][0]["status"], "succ")

    def test_subscribe_sends_callback_when_uri_set(self):
        txn = self._make_txn(
            "subscribe",
            {"transaction_id": f"txn-sub-cb-{uuid.uuid4()}"},
            callback_uri="https://cb.example.test/cb",
        )
        with patch.object(type(txn), "_send_callback_dict") as send:
            txn.process_async_subscribe()
        send.assert_called_once()
        self.assertEqual(txn.state, "success")

    def test_subscribe_rejects_on_error(self):
        txn = self._make_txn("subscribe", {"transaction_id": "x"}, callback_uri=False)
        txn.request_payload = "not valid json"
        txn.process_async_subscribe()
        self.assertEqual(txn.state, "rejected")
        self.assertEqual(txn.error_code, "rjct.subscribe.error")

    # --- process_async_unsubscribe -------------------------------------------

    def test_unsubscribe_builds_status_per_code(self):
        txn = self._make_txn(
            "unsubscribe",
            {
                "transaction_id": f"txn-unsub-{uuid.uuid4()}",
                "subscription_codes": ["SUB-1", "SUB-2"],
            },
            callback_uri=False,
        )
        txn.process_async_unsubscribe()
        self.assertEqual(txn.state, "success")
        body = json.loads(txn.response_payload)
        self.assertEqual(len(body["subscription_status"]), 2)
        self.assertEqual(body["subscription_status"][0]["status"], "unsubscribe")

    def test_unsubscribe_sends_callback_when_uri_set(self):
        txn = self._make_txn(
            "unsubscribe",
            {"transaction_id": f"txn-unsub-cb-{uuid.uuid4()}", "subscription_codes": ["SUB-1"]},
            callback_uri="https://cb.example.test/cb",
        )
        with patch.object(type(txn), "_send_callback_dict") as send:
            txn.process_async_unsubscribe()
        send.assert_called_once()
        self.assertEqual(txn.state, "success")

    def test_unsubscribe_rejects_on_error(self):
        txn = self._make_txn("unsubscribe", {"transaction_id": "x"}, callback_uri=False)
        txn.request_payload = "not valid json"
        txn.process_async_unsubscribe()
        self.assertEqual(txn.state, "rejected")
        self.assertEqual(txn.error_code, "rjct.unsubscribe.error")

    # --- process_async_txn_status --------------------------------------------

    def test_txn_status_returns_referenced_payload(self):
        ref = self._make_txn(
            "search",
            {"transaction_id": "txn-ref-known"},
            state="success",
            response_payload=json.dumps({"stored": "response"}),
        )
        txn = self._make_txn(
            "txn_status",
            {
                "transaction_id": f"txn-stat-{uuid.uuid4()}",
                "txnstatus_request": {
                    "attribute_type": "transaction_id",
                    "attribute_value": ref.transaction_id,
                    "txn_type": "search",
                },
            },
            callback_uri=False,
        )
        txn.process_async_txn_status()
        self.assertEqual(txn.state, "success")
        body = json.loads(txn.response_payload)
        self.assertEqual(body["txnstatus_response"]["txn_status"], {"stored": "response"})

    def test_txn_status_minimal_when_no_payload(self):
        ref = self._make_txn(
            "search",
            {"transaction_id": "txn-ref-nopayload"},
            state="success",
        )
        txn = self._make_txn(
            "txn_status",
            {
                "transaction_id": f"txn-stat-{uuid.uuid4()}",
                "txnstatus_request": {
                    "attribute_type": "transaction_id",
                    "attribute_value": ref.transaction_id,
                    "txn_type": "search",
                },
            },
            callback_uri=False,
        )
        txn.process_async_txn_status()
        self.assertEqual(txn.state, "success")
        body = json.loads(txn.response_payload)
        self.assertIn("search_response", body["txnstatus_response"]["txn_status"])

    def test_txn_status_not_found_returns_rjct(self):
        txn = self._make_txn(
            "txn_status",
            {
                "transaction_id": f"txn-stat-{uuid.uuid4()}",
                "txnstatus_request": {
                    "attribute_type": "transaction_id",
                    "attribute_value": "txn-nowhere",
                    "txn_type": "search",
                },
            },
            callback_uri=False,
        )
        txn.process_async_txn_status()
        self.assertEqual(txn.state, "success")
        body = json.loads(txn.response_payload)
        item = body["txnstatus_response"]["txn_status"]["search_response"][0]
        self.assertEqual(item["status"], "rjct")
        self.assertEqual(item["status_reason_code"], "rjct.reference_id.invalid")

    def test_txn_status_correlation_id_lookup(self):
        ref = self._make_txn(
            "search",
            {"transaction_id": "txn-ref-corr"},
            state="success",
            response_payload=json.dumps({"by": "correlation"}),
        )
        txn = self._make_txn(
            "txn_status",
            {
                "transaction_id": f"txn-stat-{uuid.uuid4()}",
                "txnstatus_request": {
                    "attribute_type": "correlation_id",
                    "attribute_value": ref.correlation_id,
                    "txn_type": "search",
                },
            },
            callback_uri=False,
        )
        txn.process_async_txn_status()
        body = json.loads(txn.response_payload)
        self.assertEqual(body["txnstatus_response"]["txn_status"], {"by": "correlation"})

    def test_txn_status_rejects_on_error(self):
        txn = self._make_txn("txn_status", {"transaction_id": "x"}, callback_uri=False)
        txn.request_payload = "not valid json"
        txn.process_async_txn_status()
        self.assertEqual(txn.state, "rejected")
        self.assertEqual(txn.error_code, "rjct.txnstatus.error")

    # --- _send_callback_dict --------------------------------------------------

    @patch("odoo.addons.spp_dci_server.models.transaction.validate_callback_url")
    @patch("requests.post")
    def test_send_callback_dict_success(self, mock_post, mock_validate):
        mock_validate.return_value = "https://cb.example.test/cb"
        mock_post.return_value = MagicMock(raise_for_status=MagicMock())
        txn = self._make_txn(
            "subscribe",
            {"transaction_id": "txn-cbd-1"},
            callback_uri="https://cb.example.test/cb",
        )
        txn._send_callback_dict({"some": "response"})
        self.assertEqual(txn.state, "callback_sent")
        self.assertTrue(txn.callback_sent_at)
        mock_post.assert_called_once()

    @patch("odoo.addons.spp_dci_server.models.transaction.validate_callback_url")
    def test_send_callback_dict_ssrf_blocked(self, mock_validate):
        from odoo.exceptions import ValidationError

        mock_validate.side_effect = ValidationError("Blocked IP")
        txn = self._make_txn(
            "subscribe",
            {"transaction_id": "txn-cbd-2"},
            callback_uri="http://169.254.169.254/latest",
        )
        txn._send_callback_dict({"some": "response"})
        self.assertEqual(txn.state, "callback_failed")
        self.assertEqual(txn.error_code, "rjct.callback.invalid_url")

    def test_send_callback_dict_noop_without_uri(self):
        txn = self._make_txn("subscribe", {"transaction_id": "txn-cbd-3"}, callback_uri=False)
        # No callback_uri -> early return, state unchanged.
        txn._send_callback_dict({"some": "response"})
        self.assertEqual(txn.state, "received")
