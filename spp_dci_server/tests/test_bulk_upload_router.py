# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI bulk upload router endpoints.

The parser helpers (_parse_json_file, _parse_csv_file,
_identifiers_to_search_requests) are already covered by
test_bulk_upload.py. This module exercises the two HTTP endpoints
themselves: bulk_search_upload (async, queues a job) and
bulk_verify_identifiers (sync, returns found/not_found split).
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from odoo.tests import tagged

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _fake_upload_file(content: bytes):
    """Stand-in for fastapi.UploadFile whose .read() yields the given bytes once."""
    file = MagicMock()
    state = {"yielded": False}

    async def read(chunk_size):
        if state["yielded"]:
            return b""
        state["yielded"] = True
        return content

    file.read = read
    return file


def _stub_delay():
    def with_delay(*_args, **_kwargs):
        delayed = MagicMock()
        delayed.process_async_search.return_value = MagicMock(uuid="bulk-job-1")
        return delayed

    return with_delay


@tagged("post_install", "-at_install")
class _BulkRouterCommon(DCIServerCommon):
    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.routers import bulk_upload

        self.bulk = bulk_upload
        self.test_sender = self.create_test_sender()
        self.Transaction = self.env["spp.dci.transaction"].sudo()
        self._delay_patch = patch.object(
            type(self.Transaction),
            "with_delay",
            new=_stub_delay(),
        )
        self._delay_patch.start()
        self.addCleanup(self._delay_patch.stop)


# =============================================================================
# bulk_search_upload (async)
# =============================================================================


@tagged("post_install", "-at_install")
class TestBulkSearchUpload(_BulkRouterCommon):
    def _call(
        self,
        content,
        file_format="json",
        action="search",
        sender_id=None,
        callback_uri=None,
    ):
        return _run(
            self.bulk.bulk_search_upload(
                env=self.env,
                _bearer_token="t",
                _rate_limit_check=None,
                file=_fake_upload_file(content),
                file_format=file_format,
                action=action,
                sender_id=sender_id or self.test_sender.sender_id,
                callback_uri=callback_uri,
            )
        )

    def test_valid_json_queues_async_job(self):
        payload = json.dumps(
            {"identifiers": [{"type": "urn:test", "value": "X-001"}]}
        ).encode()
        result = self._call(payload)

        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["item_count"], 1)
        self.assertTrue(result["transaction_id"].startswith("bulk-"))

        txn = self.Transaction.search(
            [("transaction_id", "=", result["transaction_id"])], limit=1
        )
        self.assertTrue(txn)
        self.assertEqual(txn.state, "pending")
        self.assertEqual(txn.job_uuid, "bulk-job-1")

    def test_valid_csv_queues_async_job(self):
        csv_payload = b"identifier_type,identifier_value\nurn:test,X-002\nurn:test,X-003\n"
        result = self._call(csv_payload, file_format="csv")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["item_count"], 2)

    def test_empty_file_returns_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(b"")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Empty", ctx.exception.detail)

    def test_unknown_format_returns_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(b"anything", file_format="xml")
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Unsupported", ctx.exception.detail)

    def test_invalid_json_returns_400_with_parse_error(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(b"{not valid json")
        self.assertEqual(ctx.exception.status_code, 400)
        # BulkUploadError surfaces as structured detail
        self.assertEqual(ctx.exception.detail["error"], "err.file.parse_error")

    def test_pending_job_quota_returns_429(self):
        """When a sender already has MAX_PENDING_JOBS_PER_SENDER pending
        transactions, new bulk uploads are rejected with 429."""
        # Fabricate the quota's worth of pending transactions
        for i in range(self.bulk.MAX_PENDING_JOBS_PER_SENDER):
            self.Transaction.create(
                {
                    "transaction_id": f"existing-{i}",
                    "message_id": f"msg-existing-{i}",
                    "action": "search",
                    "reg_type": "SOCIAL_REGISTRY",
                    "sender_id": self.test_sender.id,
                    "sender_uri": self.test_sender.sender_id,
                    "state": "pending",
                }
            )
        payload = json.dumps({"identifiers": [{"type": "urn:test", "value": "X"}]}).encode()
        with self.assertRaises(HTTPException) as ctx:
            self._call(payload)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_oversize_file_returns_413(self):
        """Files larger than MAX_FILE_SIZE must be rejected early."""
        payload = b"x" * (self.bulk.MAX_FILE_SIZE + 1)
        with self.assertRaises(HTTPException) as ctx:
            self._call(payload)
        self.assertEqual(ctx.exception.status_code, 413)

    def test_unknown_sender_still_queues(self):
        """An unrecognised sender doesn't block the upload; quota check is
        skipped and the transaction is recorded without sender FK."""
        payload = json.dumps({"identifiers": [{"type": "urn:test", "value": "Y"}]}).encode()
        result = self._call(payload, sender_id="stranger.example.test")
        self.assertEqual(result["status"], "accepted")
        txn = self.Transaction.search(
            [("transaction_id", "=", result["transaction_id"])], limit=1
        )
        self.assertFalse(txn.sender_id)

    def test_unexpected_exception_returns_500(self):
        payload = json.dumps({"identifiers": [{"type": "urn:test", "value": "Z"}]}).encode()
        with patch.object(
            type(self.Transaction), "create", side_effect=RuntimeError("db down")
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._call(payload)
        self.assertEqual(ctx.exception.status_code, 500)


# =============================================================================
# bulk_verify_identifiers (sync)
# =============================================================================


@tagged("post_install", "-at_install")
class TestBulkVerifyIdentifiers(_BulkRouterCommon):
    def setUp(self):
        super().setUp()
        self.env.user.write(
            {
                "group_ids": [
                    (4, self.env.ref("spp_registry.group_registry_viewer").id)
                ]
            }
        )

    def _call(
        self,
        content,
        file_format="json",
        sender_id=None,
    ):
        return _run(
            self.bulk.bulk_verify_identifiers(
                env=self.env,
                _bearer_token="t",
                _rate_limit_check=None,
                file=_fake_upload_file(content),
                file_format=file_format,
                sender_id=sender_id or self.test_sender.sender_id,
            )
        )

    def _seed_registry_record(self, namespace, value):
        """Create a partner with a single reg_id so bulk_verify_identifiers
        can match it. The route surfaces the namespace#value pair as the
        external registry_id."""
        partner = self.env["res.partner"].create(
            {"name": "Bulk Verify Target", "is_registrant": True}
        )
        code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        self.env["spp.registry.id"].create(
            {
                "partner_id": partner.id,
                "id_type_id": code.id,
                "value": value,
            }
        )
        return partner, code

    def test_permission_required(self):
        # Strip the registry_viewer group from a fresh user (admin keeps
        # has_group True regardless, so use a plain internal user).
        plain = self.env["res.users"].create(
            {
                "name": "Plain",
                "login": "plain_bulk@example.test",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        payload = json.dumps({"identifiers": [{"type": "urn:test", "value": "X"}]}).encode()
        with self.assertRaises(HTTPException) as ctx:
            _run(
                self.bulk.bulk_verify_identifiers(
                    env=self.env(user=plain.id),
                    _bearer_token="t",
                    _rate_limit_check=None,
                    file=_fake_upload_file(payload),
                    file_format="json",
                    sender_id=self.test_sender.sender_id,
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_found_and_not_found_split(self):
        code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        namespace = code.namespace_uri
        self._seed_registry_record(namespace, "BULK-FOUND")

        payload = json.dumps(
            {
                "identifiers": [
                    {"type": namespace, "value": "BULK-FOUND"},
                    {"type": namespace, "value": "BULK-MISSING"},
                ]
            }
        ).encode()
        result = self._call(payload)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["found_count"], 1)
        self.assertEqual(result["not_found_count"], 1)
        self.assertEqual(result["found"][0]["identifier_value"], "BULK-FOUND")
        # registry_id is the namespace#value form per ADR-016
        self.assertEqual(
            result["found"][0]["registry_id"],
            f"{namespace}#BULK-FOUND",
        )
        self.assertEqual(result["not_found"][0]["identifier_value"], "BULK-MISSING")

    def test_empty_identifier_list_returns_zero_totals(self):
        """A file whose identifiers parse to nothing returns the empty
        envelope, not an error."""
        # JSON envelope with valid format but no extractable identifiers
        payload = json.dumps(
            {
                "search_request": [
                    {"search_criteria": {"query": {"query_params": {}}}},
                ]
            }
        ).encode()
        result = self._call(payload)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["found"], [])
        self.assertEqual(result["not_found"], [])

    def test_too_many_items_returns_400(self):
        max_items = 10000
        identifiers = [
            {"type": "urn:test", "value": f"V-{i:05d}"} for i in range(max_items + 1)
        ]
        payload = json.dumps({"identifiers": identifiers}).encode()
        with self.assertRaises(HTTPException) as ctx:
            self._call(payload)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Too many items", ctx.exception.detail)

    def test_unknown_format_returns_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(b"anything", file_format="xml")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_invalid_json_returns_400(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(b"{not valid")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unexpected_exception_returns_500(self):
        payload = json.dumps({"identifiers": [{"type": "urn:test", "value": "X"}]}).encode()
        with patch.object(
            type(self.env["spp.registry.id"]),
            "search",
            side_effect=RuntimeError("db down"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._call(payload)
        self.assertEqual(ctx.exception.status_code, 500)
