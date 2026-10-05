# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for outgoing API log integration in DCI client"""

import unittest
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


@unittest.skipUnless(
    True,  # Actual check is in setUpClass since we need the Odoo env
    "spp_api_v2 required",
)
class TestOutgoingLogIntegration(TransactionCase):
    """Test DCI client integration with outgoing API log.

    These tests require spp_api_v2 to be installed (provides spp.api.outgoing.log).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "spp.api.outgoing.log" not in cls.env:
            raise unittest.SkipTest("spp_api_v2 not installed (spp.api.outgoing.log model not available)")
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.OutgoingLog = cls.env["spp.api.outgoing.log"]

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

    def _build_test_envelope(self, client):
        """Helper to build a test envelope"""
        return client._build_envelope(action="search", message={"test": "data"})

    def _find_latest_log(self, url_filter="crvs.example.org"):
        """Helper to find the most recent outgoing log entry"""
        return self.OutgoingLog.search(
            [("url", "like", url_filter)],
            order="id desc",
            limit=1,
        )

    @patch("httpx.Client")
    def test_make_request_logs_success(self, mock_client_class):
        """Successful request creates outgoing log with status=success"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        mock_response = self._make_mock_response()
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)
        client._make_request("/registry/sync/search", envelope)

        log = self._find_latest_log()
        self.assertTrue(log, "Outgoing log should be created on success")
        self.assertEqual(log.status, "success")
        self.assertEqual(log.response_status_code, 200)
        self.assertEqual(log.endpoint, "/registry/sync/search")
        self.assertEqual(log.service_name, "DCI Client")
        self.assertEqual(log.service_code, "test_crvs")
        self.assertGreater(log.duration_ms, 0)

    @patch("httpx.Client")
    def test_make_request_logs_http_error(self, mock_client_class):
        """HTTP error creates outgoing log with status=http_error"""
        import httpx

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.json.return_value = {"error": "server_error"}
        mock_request = MagicMock()

        def raise_status():
            raise httpx.HTTPStatusError("Server Error", request=mock_request, response=mock_response)

        mock_response.raise_for_status = raise_status

        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)

        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            client._make_request("/registry/sync/search", envelope)

        log = self._find_latest_log()
        self.assertTrue(log, "Outgoing log should be created on HTTP error")
        self.assertEqual(log.status, "http_error")
        self.assertEqual(log.response_status_code, 500)
        self.assertTrue(log.error_detail)

    @patch("httpx.Client")
    def test_make_request_logs_connection_error(self, mock_client_class):
        """Connection error creates outgoing log with status=connection_error"""
        import httpx

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)

        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            client._make_request("/registry/sync/search", envelope)

        log = self._find_latest_log()
        self.assertTrue(log, "Outgoing log should be created on connection error")
        self.assertEqual(log.status, "connection_error")
        self.assertTrue(log.error_detail)

    @patch("httpx.Client")
    def test_make_request_logs_timeout(self, mock_client_class):
        """Timeout creates outgoing log with status=timeout"""
        import httpx

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.ReadTimeout("Read timed out")
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)

        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            client._make_request("/registry/sync/search", envelope)

        log = self._find_latest_log()
        self.assertTrue(log, "Outgoing log should be created on timeout")
        self.assertEqual(log.status, "timeout")
        self.assertTrue(log.error_detail)

    @patch("httpx.Client")
    def test_make_request_logs_ssl_error(self, mock_client_class):
        """SSL error creates outgoing log with status=connection_error"""
        import httpx

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.ConnectError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed"
        )
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)

        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            client._make_request("/registry/sync/search", envelope)

        log = self._find_latest_log()
        self.assertTrue(log, "Outgoing log should be created on SSL error")
        self.assertEqual(log.status, "connection_error")
        self.assertIn("SSL", log.error_detail.upper())

    @patch("httpx.Client")
    def test_make_request_logs_dns_error(self, mock_client_class):
        """DNS resolution error creates outgoing log with status=connection_error"""
        import httpx

        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = httpx.ConnectError("Name or service not known")
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)

        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            client._make_request("/registry/sync/search", envelope)

        log = self._find_latest_log()
        self.assertTrue(log, "Outgoing log should be created on DNS error")
        self.assertEqual(log.status, "connection_error")
        self.assertTrue(log.error_detail)

    @patch("httpx.Client")
    def test_make_request_logs_generic_exception(self, mock_client_class):
        """Generic exception creates outgoing log with status=error"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = RuntimeError("Something unexpected")
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)

        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            client._make_request("/registry/sync/search", envelope)

        log = self._find_latest_log()
        self.assertTrue(log, "Outgoing log should be created on generic exception")
        self.assertEqual(log.status, "error")
        self.assertTrue(log.error_detail)

    @patch("httpx.Client")
    def test_401_retry_creates_two_log_entries(self, mock_client_class):
        """401 retry path creates log entry for both the 401 and the retry result"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source(auth_type="oauth2")
        client = DCIClient(ds, self.env)

        # First call returns 401, second returns 200
        mock_401_response = MagicMock()
        mock_401_response.status_code = 401
        mock_401_response.text = "Unauthorized"
        mock_401_response.json.return_value = {"error": "invalid_token"}
        mock_401_response.raise_for_status = MagicMock()

        mock_200_response = self._make_mock_response()

        mock_http_client = MagicMock()
        mock_http_client.post.side_effect = [mock_401_response, mock_200_response]
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        envelope = self._build_test_envelope(client)

        with patch.object(ds, "_clear_oauth2_token_cache"):
            client._make_request("/registry/sync/search", envelope)

        # Should have two log entries: one for 401, one for retry success
        logs = self.OutgoingLog.search(
            [("url", "like", "crvs.example.org")],
            order="id desc",
            limit=2,
        )
        self.assertEqual(len(logs), 2, "Should have two log entries (401 + retry)")

        # With order="id desc", logs[0] has the highest ID (created last).
        # Due to try-finally semantics, the recursive retry's finally runs first
        # (lower ID = success), then the outer call's finally runs (higher ID = 401).
        # So logs[0] (highest ID) is the 401 entry, logs[1] (lower ID) is the success.
        self.assertEqual(logs[0].status, "http_error")
        self.assertEqual(logs[0].response_status_code, 401)
        self.assertIn("retrying", logs[0].error_detail.lower())
        # M-1 fix: 401 response body should be captured
        self.assertTrue(logs[0].response_summary)

        # Earlier log (lower ID) is the retry success
        self.assertEqual(logs[1].status, "success")
        self.assertEqual(logs[1].response_status_code, 200)

    @patch("httpx.Client")
    def test_log_failure_does_not_block_request(self, mock_client_class):
        """Logging failure does not prevent the actual request from succeeding"""
        from ..services.client import DCIClient

        ds = self._create_test_data_source()
        client = DCIClient(ds, self.env)

        # Mock HTTP response (success)
        mock_response = self._make_mock_response()
        mock_http_client = MagicMock()
        mock_http_client.post.return_value = mock_response
        mock_http_client.__enter__.return_value = mock_http_client
        mock_http_client.__exit__.return_value = None
        mock_client_class.return_value = mock_http_client

        # Monkey-patch the model to raise
        original_log_call = self.OutgoingLog.__class__.log_call

        def broken_log_call(self_model, **kwargs):
            raise RuntimeError("Database error")

        self.OutgoingLog.__class__.log_call = broken_log_call
        try:
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
        finally:
            self.OutgoingLog.__class__.log_call = original_log_call
