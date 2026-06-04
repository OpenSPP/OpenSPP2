# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI search router.

The router stitches together: envelope parsing, search-service dispatch,
overall-status aggregation (``succ``/``part``/``rjct``), and response
signing. We exercise each branch independently by mocking
DCISocialSearchService.execute_search to control what the per-item
responses look like.
"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import DCIEnvelope, SearchResponse, SearchResponseItem
from odoo.addons.spp_dci.schemas.constants import (
    MsgHeaderStatusReasonCode,
    SearchStatusReasonCode,
)

from fastapi import HTTPException

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@tagged("post_install", "-at_install")
class TestSearchRouter(DCIServerCommon):
    """Exercise every branch of ``search_registry``."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers.search import search_registry

        self.search_registry = search_registry
        self.test_sender = self.create_test_sender()

    def _build_envelope(self, message=None):
        if message is None:
            message = {
                "transaction_id": "test-txn-router",
                "search_request": [
                    {
                        "reference_id": "test-ref-router-1",
                        "timestamp": datetime.now(UTC).isoformat(),
                        "search_criteria": {
                            "reg_type": "SOCIAL_REGISTRY",
                            "reg_event_type": "ACTIVE",
                            "query_type": "idtype-value",
                            "query": {"type": "ns:id-type:test", "value": "X-001"},
                        },
                    }
                ],
            }
        envelope_data = self.create_signed_envelope(message=message)
        return DCIEnvelope(**envelope_data)

    def _build_response(self, statuses=("succ",)):
        """Build a SearchResponse with one search_response item per status."""
        items = []
        for i, status in enumerate(statuses):
            items.append(
                SearchResponseItem(
                    reference_id=f"test-ref-router-{i}",
                    timestamp=datetime.now(UTC),
                    status=status,
                    data=None,
                    pagination=None,
                )
            )
        return SearchResponse(
            transaction_id="test-txn-router",
            correlation_id="test-corr-router",
            search_response=items,
        )

    def _call(self, envelope, search_response, sender_id="external.test.gov"):
        with patch(
            "odoo.addons.spp_dci_server_social.services.search_service.DCISocialSearchService"
        ) as mock_service_cls:
            instance = mock_service_cls.return_value
            instance.execute_search.return_value = search_response
            return _run(
                self.search_registry(
                    envelope,
                    self.env,
                    _bearer_token="test-token",
                    verified_sender_id=sender_id,
                    _rate_limit_check=None,
                )
            )

    # --- happy path -----------------------------------------------------------

    def test_all_succ_returns_overall_succ(self):
        envelope = self._build_envelope()
        response = self._build_response(statuses=("succ",))
        result = self._call(envelope, response)

        self.assertIsInstance(result, DCIEnvelope)
        self.assertEqual(result.header.status, "succ")
        self.assertEqual(result.header.completed_count, 1)
        self.assertEqual(result.header.total_count, 1)
        # Success path must omit reason_code per SPDCI
        self.assertIsNone(result.header.status_reason_code)
        # action becomes on-<action>
        self.assertEqual(result.header.action, "on-search")
        # receiver_id flips to the original envelope sender
        self.assertEqual(result.header.receiver_id, envelope.header.sender_id)

    def test_partial_success_maps_to_succ_with_count_message(self):
        """SPDCI v1.0.0 restricts envelope status to rcvd/pdng/succ/rjct.
        Mixed per-item outcomes surface as ``succ`` with a count in
        status_reason_message; per-item statuses carry the detail."""
        envelope = self._build_envelope()
        response = self._build_response(statuses=("succ", "rjct"))
        result = self._call(envelope, response)
        self.assertEqual(result.header.status, "succ")
        self.assertEqual(result.header.completed_count, 1)
        self.assertEqual(result.header.total_count, 2)
        self.assertIn("1/2", result.header.status_reason_message)

    def test_all_rejected_uses_errors_too_many(self):
        envelope = self._build_envelope()
        response = self._build_response(statuses=("rjct", "rjct"))
        result = self._call(envelope, response)
        self.assertEqual(result.header.status, "rjct")
        self.assertEqual(
            result.header.status_reason_code,
            MsgHeaderStatusReasonCode.ERRORS_TOO_MANY.value,
        )

    # --- request validation ---------------------------------------------------

    def test_invalid_search_request_returns_400(self):
        envelope_data = self.create_signed_envelope(message={"bogus": "payload"})
        envelope = DCIEnvelope(**envelope_data)
        with self.assertRaises(HTTPException) as ctx:
            _run(
                self.search_registry(
                    envelope,
                    self.env,
                    _bearer_token="t",
                    verified_sender_id="s",
                    _rate_limit_check=None,
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)

    # --- consent wiring -------------------------------------------------------

    def test_sync_search_passes_verified_sender_to_service(self):
        """The sync path must resolve the verified sender registry entry and
        hand it to the search service - otherwise the consent adapter sees no
        sender and silently disengages consent filtering."""
        envelope = self._build_envelope()
        response = self._build_response(statuses=("succ",))
        with patch("odoo.addons.spp_dci_server_social.services.search_service.DCISocialSearchService") as mock_cls:
            mock_cls.return_value.execute_search.return_value = response
            _run(
                self.search_registry(
                    envelope,
                    self.env,
                    _bearer_token="t",
                    verified_sender_id=self.test_sender.sender_id,
                    _rate_limit_check=None,
                )
            )
        args, kwargs = mock_cls.call_args
        passed_sender = kwargs.get("sender_registry")
        if passed_sender is None and len(args) > 1:
            passed_sender = args[1]
        self.assertEqual(
            passed_sender,
            self.test_sender,
            "verified sender was not passed to the search service (consent bypass)",
        )

    # --- service errors -------------------------------------------------------

    def test_search_service_exception_rejects_all_items(self):
        envelope = self._build_envelope()
        with patch(
            "odoo.addons.spp_dci_server_social.services.search_service.DCISocialSearchService"
        ) as mock_service_cls:
            mock_service_cls.return_value.execute_search.side_effect = RuntimeError("service exploded")
            result = _run(
                self.search_registry(
                    envelope,
                    self.env,
                    _bearer_token="t",
                    verified_sender_id="s",
                    _rate_limit_check=None,
                )
            )
        self.assertEqual(result.header.status, "rjct")
        # All items rejected
        message = result.message
        items = message["search_response"]
        self.assertTrue(all(i["status"] == "rjct" for i in items))
        self.assertEqual(
            items[0]["status_reason_code"],
            SearchStatusReasonCode.SEARCH_CRITERIA_INVALID.value,
        )

    def test_social_module_import_error_falls_back_to_rjct(self):
        envelope = self._build_envelope()
        with patch.dict(
            "sys.modules",
            {"odoo.addons.spp_dci_server_social.services.search_service": None},
        ):
            # Force ImportError on the in-function import.
            result = _run(
                self.search_registry(
                    envelope,
                    self.env,
                    _bearer_token="t",
                    verified_sender_id="s",
                    _rate_limit_check=None,
                )
            )
        self.assertEqual(result.header.status, "rjct")
        items = result.message["search_response"]
        self.assertIn("not installed", items[0]["status_reason_message"])

    # --- signing branches -----------------------------------------------------

    def test_no_active_signing_key_returns_unsigned(self):
        """When no active signing key exists, the response must still be
        returned with an empty signature - clients can fall back to TLS or
        out-of-band verification."""
        # Drop default signing keys
        self.env["spp.dci.signing.key"].sudo().search([("state", "=", "active")]).unlink()
        envelope = self._build_envelope()
        response = self._build_response(statuses=("succ",))
        result = self._call(envelope, response)
        self.assertEqual(result.signature, "")

    def test_signing_failure_is_tolerated(self):
        envelope = self._build_envelope()
        response = self._build_response(statuses=("succ",))
        with patch(
            "odoo.addons.spp_dci_server_social.services.search_service.DCISocialSearchService"
        ) as mock_service_cls:
            mock_service_cls.return_value.execute_search.return_value = response

            # Force the signing branch to raise but the route must still
            # produce a valid envelope (unsigned).
            with patch(
                "odoo.addons.spp_dci.services.signing.DCISigner.sign",
                side_effect=RuntimeError("boom"),
            ):
                result = _run(
                    self.search_registry(
                        envelope,
                        self.env,
                        _bearer_token="t",
                        verified_sender_id="s",
                        _rate_limit_check=None,
                    )
                )
        self.assertEqual(result.signature, "")
        self.assertEqual(result.header.status, "succ")

    # --- top-level catch-all --------------------------------------------------

    def test_unexpected_error_returns_500(self):
        envelope = self._build_envelope()
        # Force an exception outside the known branches by making get_sender_id raise.
        with (
            patch(
                "odoo.addons.spp_dci_server.routers.search.get_sender_id",
                side_effect=RuntimeError("config explosion"),
            ),
            patch(
                "odoo.addons.spp_dci_server_social.services.search_service.DCISocialSearchService"
            ) as mock_service_cls,
        ):
            instance = mock_service_cls.return_value
            instance.execute_search.return_value = self._build_response(("succ",))
            with self.assertRaises(HTTPException) as ctx:
                _run(
                    self.search_registry(
                        envelope,
                        self.env,
                        _bearer_token="t",
                        verified_sender_id="s",
                        _rate_limit_check=None,
                    )
                )
        self.assertEqual(ctx.exception.status_code, 500)
