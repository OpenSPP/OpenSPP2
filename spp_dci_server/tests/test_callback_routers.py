# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI callback routers (callbacks + registry aliases).

Covers:
- ``routers.callbacks``: every on-* / async-* endpoint plus the
  ``_validate_callback_payload`` helper used by all of them.
- ``routers.registry_aliases``: the six 501-stub endpoints for
  disability, crvs, and farmer registries.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas.constants import MsgHeaderStatusReasonCode
from odoo.addons.spp_dci.schemas.search import (
    SearchCriteria,
    SearchRequest,
    SearchRequestItem,
)

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fake_request(payload):
    """Build a stand-in for fastapi.Request that returns ``payload`` from .json().

    Pass ``payload=None`` to simulate a body that fails to parse (the
    real Request would raise json.JSONDecodeError; we raise ValueError
    which the routers also catch).
    """
    req = MagicMock()
    if payload is None:
        req.json = AsyncMock(side_effect=ValueError("not json"))
    else:
        req.json = AsyncMock(return_value=payload)
    return req


# =============================================================================
# Callback helper + on-* endpoints
# =============================================================================


@tagged("post_install", "-at_install")
class TestValidateCallbackPayload(DCIServerCommon):
    """The helper drives every on-* endpoint's response shape."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers.callbacks import (
            _validate_callback_payload,
        )

        self.validate = _validate_callback_payload

    def test_empty_body_returns_ack(self):
        """Empty body is valid for compliance testing - returns ACK."""
        result = self.validate(None)
        self.assertEqual(result.message.ack_status, "ACK")
        self.assertIsNone(result.message.error)

    def test_empty_dict_returns_ack(self):
        result = self.validate({})
        self.assertEqual(result.message.ack_status, "ACK")

    def test_complete_payload_returns_ack(self):
        result = self.validate({"header": {}, "message": {}})
        self.assertEqual(result.message.ack_status, "ACK")

    def test_missing_required_fields_returns_err(self):
        result = self.validate({"header": {}})
        self.assertEqual(result.message.ack_status, "ERR")
        self.assertEqual(result.message.error.code, "err.request.bad")
        self.assertIn("message", result.message.error.message)

    def test_explicit_required_fields(self):
        result = self.validate({"header": {}}, required_fields=["header"])
        self.assertEqual(result.message.ack_status, "ACK")

    def test_null_required_fields_treated_as_missing(self):
        result = self.validate({"header": {}, "message": None})
        self.assertEqual(result.message.ack_status, "ERR")


@tagged("post_install", "-at_install")
class TestCallbackEndpoints(DCIServerCommon):
    """The four on-* endpoints all delegate to the helper; verify each
    route handles JSON parsing errors gracefully and surfaces the right
    ACK/ERR shape."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers import callbacks

        self.endpoints = [
            callbacks.on_search,
            callbacks.on_subscribe,
            callbacks.on_unsubscribe,
            callbacks.on_txn_status,
        ]

    def test_each_endpoint_returns_ack_for_valid_payload(self):
        valid = {"header": {"sender_id": "test"}, "message": {}}
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint.__name__):
                result = _run(endpoint(_fake_request(valid), self.env, _bearer_token="t"))
                self.assertEqual(result.message.ack_status, "ACK")

    def test_each_endpoint_returns_err_for_invalid_payload(self):
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint.__name__):
                result = _run(endpoint(_fake_request({"only": "this"}), self.env, _bearer_token="t"))
                self.assertEqual(result.message.ack_status, "ERR")

    def test_each_endpoint_tolerates_invalid_json(self):
        """Routes catch JSON parse errors and treat the body as empty."""
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint.__name__):
                result = _run(endpoint(_fake_request(None), self.env, _bearer_token="t"))
                # Empty -> ACK (compliance testing convention)
                self.assertEqual(result.message.ack_status, "ACK")


@tagged("post_install", "-at_install")
class TestAsyncTxnStatusEndpoint(DCIServerCommon):
    """async_txn_status branches on JSON validity and field presence
    before delegating to _validate_callback_payload."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers.callbacks import async_txn_status

        self.endpoint = async_txn_status

    def test_invalid_json_returns_err(self):
        result = _run(self.endpoint(_fake_request(None), self.env, _bearer_token="t"))
        self.assertEqual(result.message.ack_status, "ERR")
        self.assertEqual(result.message.error.code, "err.request.bad")

    def test_missing_required_fields_returns_err(self):
        result = _run(self.endpoint(_fake_request({"header": {}}), self.env, _bearer_token="t"))
        self.assertEqual(result.message.ack_status, "ERR")

    def test_valid_payload_returns_ack(self):
        result = _run(
            self.endpoint(
                _fake_request(
                    {
                        "header": {"sender_id": "external.test.gov"},
                        "message": {"transaction_id": "txn-async-1"},
                    }
                ),
                self.env,
                _bearer_token="t",
            )
        )
        self.assertEqual(result.message.ack_status, "ACK")


# =============================================================================
# Registry alias 501-stub endpoints
# =============================================================================


@tagged("post_install", "-at_install")
class TestRegistryAliasStubs(DCIServerCommon):
    """The disability / crvs / farmer alias endpoints all return a
    'not implemented' rjct response per SPDCI compliance testing
    expectations until the matching server modules ship."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers import registry_aliases

        self.search_endpoints = {
            "disability": registry_aliases.disability_sync_search,
            "crvs": registry_aliases.crvs_sync_search,
            "farmer": registry_aliases.farmer_sync_search,
        }
        self.notify_endpoints = {
            "disability": registry_aliases.disability_sync_notify,
            "crvs": registry_aliases.crvs_sync_notify,
            "farmer": registry_aliases.farmer_sync_notify,
        }

    def _build_search_request(self, n_items=1):
        items = []
        for i in range(n_items):
            items.append(
                SearchRequestItem(
                    reference_id=f"ref-{i}",
                    timestamp=datetime.now(UTC),
                    search_criteria=SearchCriteria(
                        reg_type="DISABILITY_REGISTRY",
                        reg_event_type="ACTIVE",
                        query_type="idtype-value",
                        query={"type": "ns:test", "value": "x"},
                    ),
                )
            )
        return SearchRequest(transaction_id="txn-alias", search_request=items)

    def test_search_stubs_return_per_item_rjct(self):
        request = self._build_search_request(n_items=2)
        # Each alias mentions its corresponding spp_dci_server_* module in
        # the rejection message so operators can find the missing addon.
        expected_module = {
            "disability": "spp_dci_server_disability",
            "crvs": "spp_dci_server_crvs",
            "farmer": "spp_dci_server_farmer",
        }
        for registry, endpoint in self.search_endpoints.items():
            with self.subTest(registry=registry):
                response = _run(endpoint(request, self.env, _bearer_token="t"))
                self.assertEqual(response.transaction_id, "txn-alias")
                self.assertEqual(len(response.search_response), 2)
                for item in response.search_response:
                    self.assertEqual(item.status, "rjct")
                    self.assertEqual(
                        item.status_reason_code,
                        MsgHeaderStatusReasonCode.ACTION_NOT_SUPPORTED.value,
                    )
                    self.assertIn(expected_module[registry], item.status_reason_message)

    def test_notify_stubs_return_rjct(self):
        for registry, endpoint in self.notify_endpoints.items():
            with self.subTest(registry=registry):
                response = _run(endpoint(self.env, _bearer_token="t"))
                self.assertEqual(response["status"], "rjct")
                self.assertIn("not yet implemented", response["message"])
                # Has an ISO-formatted timestamp
                self.assertIn("T", response["timestamp"])
