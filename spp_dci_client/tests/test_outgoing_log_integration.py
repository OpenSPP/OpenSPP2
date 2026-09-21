# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for outgoing API log integration in DCI client"""

import unittest
import uuid
from unittest.mock import MagicMock, patch

from odoo.tests import TransactionCase


class TestOutgoingLogClientMethods(TransactionCase):
    """Test DCI client logging helper methods (no spp_api_v2 dependency needed)"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]

    def _create_test_data_source(self, **kwargs):
        """Helper to create a test data source"""
        vals = {
            "name": "Test CRVS",
            "code": "test_crvs",
            "base_url": "https://crvs.example.org/api",
            "auth_type": "none",
            "our_sender_id": "openspp.example.org",
            "our_callback_uri": "https://openspp.example.org/callback",
            "registry_type": "ns:org:RegistryType:Civil",
        }
        vals.update(kwargs)
        return self.DataSource.create(vals)

    def test_log_skips_if_model_missing(self):
        """_log_outgoing_call does nothing if spp.api.outgoing.log model is not installed"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        # Mock env to not contain the outgoing log model
        with patch.object(client, "env") as mock_env:
            mock_env.__contains__ = lambda self, key: False

            # Should not raise
            client._log_outgoing_call(
                url="https://example.org/test",
                endpoint="/test",
                envelope={"header": {"action": "search"}, "message": {}},
                response_data=None,
                status_code=None,
                duration_ms=100,
                status="success",
                error_detail=None,
            )

    def test_copy_envelope_for_log_preserves_signature(self):
        """_copy_envelope_for_log preserves signature for auditability"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = {
            "signature": "cryptographic_signature_12345",
            "header": {"action": "search"},
            "message": {"test": "data"},
        }

        copied = client._copy_envelope_for_log(envelope)

        # Signature is preserved for audit trail / non-repudiation
        self.assertEqual(copied["signature"], "cryptographic_signature_12345")
        self.assertEqual(copied["header"], {"action": "search"})
        self.assertEqual(copied["message"], {"test": "data"})

    def test_copy_envelope_for_log_none(self):
        """_copy_envelope_for_log returns None for None/empty input"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        self.assertIsNone(client._copy_envelope_for_log(None))
        self.assertIsNone(client._copy_envelope_for_log({}))

    def test_copy_envelope_for_log_returns_copy(self):
        """_copy_envelope_for_log returns a copy, not the original"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        envelope = {"header": {"action": "search"}, "message": {}}
        copied = client._copy_envelope_for_log(envelope)

        self.assertIsNot(copied, envelope)
        self.assertEqual(copied, envelope)


class TestOutgoingLogIntegration(TransactionCase):
    """Test DCI client integration with outgoing API log.

    These tests require spp_api_v2 to be installed (provides spp.api.outgoing.log),
    so they run only on a database that has both modules — a full stack, never
    spp_dci_client's own module CI.

    Assertions are made at the ``OutgoingApiLogService`` seam rather than by
    reading rows back. ``_log_outgoing_call`` deliberately writes through a
    separate, committed cursor so the audit row survives the request's
    rollback; a plain ``TransactionCase`` runs at REPEATABLE READ and cannot
    see rows committed after its snapshot, while it can see rows committed by
    earlier test classes, so a "latest row" query returns another class's row.
    One test still proves the real write, reading it back through a fresh
    cursor of its own and cleaning up.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "spp.api.outgoing.log" not in cls.env:
            raise unittest.SkipTest("spp_api_v2 not installed (spp.api.outgoing.log model not available)")
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.OutgoingLog = cls.env["spp.api.outgoing.log"]

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_api_v2.services.outgoing_api_log_service import OutgoingApiLogService

        # The service is imported inside _log_outgoing_call from this module, so
        # patching the class attribute is seen by production code. The cursor is
        # still opened and the service still constructed for real; only the
        # INSERT is replaced, so nothing is committed.
        patcher = patch.object(OutgoingApiLogService, "log_call", autospec=True)
        self.log_call = patcher.start()
        self.addCleanup(patcher.stop)

    def _create_test_data_source(self, **kwargs):
        """Helper to create a test data source"""
        vals = {
            "name": "Test CRVS",
            "code": "test_crvs",
            "base_url": "https://crvs.example.org/api",
            "auth_type": "none",
            "our_sender_id": "openspp.example.org",
            "our_callback_uri": "https://openspp.example.org/callback",
            "registry_type": "ns:org:RegistryType:Civil",
        }
        vals.update(kwargs)
        return self.DataSource.create(vals)

    def _make_mock_response(self, status_code=200, json_data=None):
        """Helper to create a mock HTTP response"""
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {"header": {"status": "success"}}
        mock_response.text = str(json_data or {"header": {"status": "success"}})
        mock_response.raise_for_status = MagicMock()
        return mock_response

    def _mock_http(self, mock_client_class, *, response=None, side_effect=None):
        """Wire ``httpx.Client`` to one canned response or exception per call."""
        mock_http_client = MagicMock()
        if side_effect is not None:
            mock_http_client.post.side_effect = side_effect
        else:
            mock_http_client.post.return_value = response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client
        return mock_http_client

    def _build_test_envelope(self, client):
        """Helper to build a test envelope"""
        return client._build_envelope(action="search", message={"test": "data"})

    def _logged(self):
        """The kwargs of every log_call made during the test, in call order."""
        return [call.kwargs for call in self.log_call.call_args_list]

    def _single_logged(self):
        logged = self._logged()
        self.assertEqual(len(logged), 1, f"expected exactly one outgoing log call, got {len(logged)}")
        return logged[0]

    def _request_expecting_user_error(self, client, envelope):
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            client._make_request("/registry/sync/search", envelope)

    @patch("httpx.Client")
    def test_make_request_logs_success(self, mock_client_class):
        """Successful request logs status=success with the call's details."""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)
        self._mock_http(mock_client_class, response=self._make_mock_response())

        client._make_request("/registry/sync/search", self._build_test_envelope(client))

        log = self._single_logged()
        self.assertEqual(log["status"], "success")
        self.assertEqual(log["response_status_code"], 200)
        self.assertEqual(log["endpoint"], "/registry/sync/search")
        self.assertEqual(log["url"], "https://crvs.example.org/api/registry/sync/search")
        self.assertEqual(log["origin_model"], "spp.dci.data.source")
        self.assertEqual(log["origin_record_id"], ds.id)
        # A mocked HTTP round trip completes in well under a millisecond.
        self.assertGreaterEqual(log["duration_ms"], 0)
        self.assertIsNone(log["error_detail"])

    @patch("httpx.Client")
    def test_service_is_built_for_the_data_source(self, mock_client_class):
        """The log service carries the client's identity, not the model's default."""
        from odoo.addons.spp_api_v2.services.outgoing_api_log_service import OutgoingApiLogService

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)
        self._mock_http(mock_client_class, response=self._make_mock_response())

        with patch.object(OutgoingApiLogService, "__init__", return_value=None, autospec=True) as init:
            client._make_request("/registry/sync/search", self._build_test_envelope(client))

        self.assertEqual(init.call_count, 1)
        kwargs = init.call_args.kwargs
        self.assertEqual(kwargs["service_name"], "DCI Client")
        self.assertEqual(kwargs["service_code"], "test_crvs")
        self.assertEqual(kwargs["user_id"], self.env.uid)

    @patch("httpx.Client")
    def test_make_request_logs_http_error(self, mock_client_class):
        """HTTP error logs status=http_error with the response code."""
        import httpx

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.return_value = {"error": "server_error"}

        def raise_status():
            raise httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response)

        mock_response.raise_for_status = raise_status
        self._mock_http(mock_client_class, response=mock_response)

        self._request_expecting_user_error(client, self._build_test_envelope(client))

        log = self._single_logged()
        self.assertEqual(log["status"], "http_error")
        self.assertEqual(log["response_status_code"], 500)
        self.assertTrue(log["error_detail"])

    def _assert_exception_logged_as(self, mock_client_class, exception, status, detail_contains=None):
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)
        self._mock_http(mock_client_class, side_effect=exception)

        self._request_expecting_user_error(client, self._build_test_envelope(client))

        log = self._single_logged()
        self.assertEqual(log["status"], status)
        self.assertTrue(log["error_detail"])
        if detail_contains:
            self.assertIn(detail_contains, log["error_detail"].upper())
        self.assertIsNone(log["response_status_code"])

    @patch("httpx.Client")
    def test_make_request_logs_connection_error(self, mock_client_class):
        import httpx

        self._assert_exception_logged_as(mock_client_class, httpx.ConnectError("Connection refused"), "connection_error")

    @patch("httpx.Client")
    def test_make_request_logs_timeout(self, mock_client_class):
        import httpx

        self._assert_exception_logged_as(mock_client_class, httpx.ReadTimeout("Read timed out"), "timeout")

    @patch("httpx.Client")
    def test_make_request_logs_ssl_error(self, mock_client_class):
        import httpx

        self._assert_exception_logged_as(
            mock_client_class,
            httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"),
            "connection_error",
            detail_contains="SSL",
        )

    @patch("httpx.Client")
    def test_make_request_logs_dns_error(self, mock_client_class):
        import httpx

        self._assert_exception_logged_as(
            mock_client_class, httpx.ConnectError("Name or service not known"), "connection_error"
        )

    @patch("httpx.Client")
    def test_make_request_logs_generic_exception(self, mock_client_class):
        self._assert_exception_logged_as(mock_client_class, RuntimeError("Something unexpected"), "error")

    @patch("httpx.Client")
    def test_401_retry_creates_two_log_entries(self, mock_client_class):
        """The 401 retry path logs both the 401 and the retried result, in call order.

        The retried request runs inside the first one, so its ``finally`` logs
        first (the success), and the outer call's ``finally`` logs second (the
        401). Call order is what the code guarantees; row ids are not asserted.
        """
        from ..services.client import DCIClient

        ds = self._create_test_data_source(
            auth_type="oauth2",
            oauth2_token_url="https://auth.example.org/token",
            oauth2_client_id="client123",
            oauth2_client_secret="secret456",
        )
        client = DCIClient(ds, self.env)
        mock_401_response = MagicMock()
        mock_401_response.status_code = 401
        mock_401_response.text = "Unauthorized"
        mock_401_response.json.return_value = {"error": "invalid_token"}
        mock_401_response.raise_for_status = MagicMock()
        self._mock_http(mock_client_class, side_effect=[mock_401_response, self._make_mock_response()])

        # get_headers() would fetch the OAuth2 token over the same patched HTTP
        # client and consume the canned 401; the token flow is not under test.
        with (
            patch.object(type(ds), "get_headers", return_value={"Content-Type": "application/json"}),
            patch.object(type(ds), "clear_oauth2_token_cache") as clear_cache,
        ):
            client._make_request("/registry/sync/search", self._build_test_envelope(client))

        clear_cache.assert_called_once()
        logged = self._logged()
        self.assertEqual(len(logged), 2, "one log call for the retried success, one for the 401")
        retried, first = logged
        self.assertEqual(retried["status"], "success")
        self.assertEqual(retried["response_status_code"], 200)
        self.assertEqual(first["status"], "http_error")
        self.assertEqual(first["response_status_code"], 401)
        self.assertIn("retrying", first["error_detail"].lower())
        # The 401 response body is captured for troubleshooting.
        self.assertEqual(first["response_summary"], {"error": "invalid_token"})

    @patch("httpx.Client")
    def test_log_row_is_committed_on_a_separate_cursor(self, mock_client_class):
        """The audit row really is written, on its own cursor, so it survives the
        request's rollback. Read back through a fresh cursor (a new snapshot),
        scoped by a per-test service code, and removed the same way."""
        from ..services.client import DCIClient

        # Let the real service write for this test only.
        patch.stopall()
        code = f"e2e_{uuid.uuid4().hex[:8]}"
        ds = self._create_test_data_source(code=code, base_url=f"https://{code}.example.org/api")
        client = DCIClient(ds, self.env)
        self._mock_http(mock_client_class, response=self._make_mock_response())

        client._make_request("/registry/sync/search", self._build_test_envelope(client))

        with self.env.registry.cursor() as cr:
            rows = self.env(cr=cr)["spp.api.outgoing.log"].search([("service_code", "=", code)])
            try:
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows.status, "success")
                self.assertEqual(rows.response_status_code, 200)
            finally:
                rows.unlink()

    @patch("httpx.Client")
    def test_log_failure_does_not_block_request(self, mock_client_class):
        """Logging failure does not prevent the actual request from succeeding"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)
        self._mock_http(mock_client_class, response=self._make_mock_response())
        self.log_call.side_effect = RuntimeError("Database error")

        # This should not raise despite broken logging
        client._log_outgoing_call(
            url="https://example.org/test",
            endpoint="/test",
            envelope={"header": {"action": "search"}, "message": {}},
            response_data=None,
            status_code=200,
            duration_ms=100,
            status="success",
            error_detail=None,
        )
