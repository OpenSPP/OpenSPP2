# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for OutgoingApiLogService"""

import json

from odoo.tests.common import TransactionCase

from ..services.outgoing_api_log_service import OutgoingApiLogService


class TestOutgoingApiLogService(TransactionCase):
    """Test OutgoingApiLogService functionality"""

    def setUp(self):
        super().setUp()
        self.outgoing_log_model = self.env["spp.api.outgoing.log"]

    def test_log_call_creates_record(self):
        """log_call creates outgoing log record via the service"""
        service = OutgoingApiLogService(
            self.env,
            service_name="DCI Client",
            service_code="crvs_main",
        )

        result = service.log_call(
            url="https://crvs.example.org/api/registry/sync/search",
            endpoint="/registry/sync/search",
            http_method="POST",
            request_summary={"header": {"action": "search"}},
            response_summary={"header": {"status": "success"}},
            response_status_code=200,
            duration_ms=350,
            origin_model="spp.dci.data.source",
            origin_record_id=42,
            status="success",
        )

        self.assertTrue(result)
        self.assertEqual(result.url, "https://crvs.example.org/api/registry/sync/search")
        self.assertEqual(result.service_name, "DCI Client")
        self.assertEqual(result.service_code, "crvs_main")
        self.assertEqual(result.status, "success")

    def test_log_call_failure_returns_none(self):
        """Logging failures return None and don't raise exceptions"""
        # Create a service with a broken env to trigger a failure
        bad_service = OutgoingApiLogService(
            self.env,
            service_name="Bad Service",
            service_code="bad",
        )

        # Monkey-patch the model to raise an error
        original_log_call = self.outgoing_log_model.__class__.log_call

        def broken_log_call(self_model, **kwargs):
            raise RuntimeError("Database error")

        self.outgoing_log_model.__class__.log_call = broken_log_call
        try:
            result = bad_service.log_call(
                url="https://example.org/test",
            )
            self.assertIsNone(result)
        finally:
            self.outgoing_log_model.__class__.log_call = original_log_call

    def test_truncate_payload(self):
        """_truncate_payload truncates large payloads"""
        service = OutgoingApiLogService(
            self.env,
            service_name="Test",
            service_code="test",
        )

        # Small payload should pass through unchanged
        small = {"key": "value"}
        self.assertEqual(service._truncate_payload(small), small)

        # None should return None
        self.assertIsNone(service._truncate_payload(None))

        # Large payload should be truncated
        large = {"data": "x" * 20000}
        result = service._truncate_payload(large, max_length=100)
        self.assertTrue(result["_truncated"])
        self.assertIn("_original_length", result)
        self.assertIn("_preview", result)

    def test_service_stores_user_id(self):
        """Service records the correct user_id"""
        service = OutgoingApiLogService(
            self.env,
            service_name="Test",
            service_code="test",
            user_id=self.env.uid,
        )

        result = service.log_call(
            url="https://example.org/test",
        )

        self.assertTrue(result)
        self.assertEqual(result.user_id.id, self.env.uid)

    def test_service_stores_service_context(self):
        """Service stores service_name and service_code on log records"""
        service = OutgoingApiLogService(
            self.env,
            service_name="My Integration",
            service_code="my_integration_v1",
        )

        result = service.log_call(
            url="https://example.org/test",
        )

        self.assertTrue(result)
        self.assertEqual(result.service_name, "My Integration")
        self.assertEqual(result.service_code, "my_integration_v1")

    def test_service_default_user_id(self):
        """Service defaults to env.uid when user_id not provided"""
        service = OutgoingApiLogService(
            self.env,
            service_name="Test",
            service_code="test",
        )

        self.assertEqual(service.user_id, self.env.uid)

    def test_truncate_payload_non_serializable(self):
        """_truncate_payload handles non-JSON-serializable payloads"""
        service = OutgoingApiLogService(
            self.env,
            service_name="Test",
            service_code="test",
        )

        # Object that can't be serialized
        result = service._truncate_payload({"key": object()})
        self.assertTrue(result["_truncated"])
        self.assertIn("_error", result)

    def test_truncate_payload_exact_boundary(self):
        """_truncate_payload passes through payload at exactly max_length"""
        service = OutgoingApiLogService(
            self.env,
            service_name="Test",
            service_code="test",
        )

        # Build a payload whose JSON serialization is exactly max_length
        max_length = 50
        # {"k": "..."} — adjust value to hit exact length
        base = json.dumps({"k": ""})  # '{"k": ""}' = 10 chars
        filler = "x" * (max_length - len(base))
        payload = {"k": filler}
        serialized = json.dumps(payload)
        self.assertEqual(len(serialized), max_length)

        result = service._truncate_payload(payload, max_length=max_length)
        # Should pass through unchanged (equal to limit)
        self.assertEqual(result, payload)
        self.assertNotIn("_truncated", result)

    def test_truncate_payload_one_over_boundary(self):
        """_truncate_payload truncates payload one byte over max_length"""
        service = OutgoingApiLogService(
            self.env,
            service_name="Test",
            service_code="test",
        )

        max_length = 50
        base = json.dumps({"k": ""})
        filler = "x" * (max_length - len(base) + 1)
        payload = {"k": filler}
        serialized = json.dumps(payload)
        self.assertEqual(len(serialized), max_length + 1)

        result = service._truncate_payload(payload, max_length=max_length)
        self.assertTrue(result["_truncated"])
        self.assertEqual(result["_original_length"], max_length + 1)
        self.assertEqual(len(result["_preview"]), max_length)

    def test_mask_sensitive_keys_top_level(self):
        """_mask_sensitive_keys masks known sensitive keys at top level"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        payload = {
            "Authorization": "Bearer secret-token-123",
            "Content-Type": "application/json",
            "data": "visible",
        }

        result = service._mask_sensitive_keys(payload)
        self.assertEqual(result["Authorization"], "***MASKED***")
        self.assertEqual(result["Content-Type"], "application/json")
        self.assertEqual(result["data"], "visible")

    def test_mask_sensitive_keys_nested(self):
        """_mask_sensitive_keys masks sensitive keys in nested dicts"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        payload = {
            "header": {
                "authorization": "Bearer xyz",
                "action": "search",
            },
            "body": {"password": "s3cret", "username": "admin"},
        }

        result = service._mask_sensitive_keys(payload)
        self.assertEqual(result["header"]["authorization"], "***MASKED***")
        self.assertEqual(result["header"]["action"], "search")
        self.assertEqual(result["body"]["password"], "***MASKED***")
        self.assertEqual(result["body"]["username"], "admin")

    def test_mask_sensitive_keys_case_insensitive(self):
        """_mask_sensitive_keys matches key names case-insensitively"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        payload = {
            "API_KEY": "key123",
            "api_key": "key456",
            "Api_Key": "key789",
        }

        result = service._mask_sensitive_keys(payload)
        for key in payload:
            self.assertEqual(result[key], "***MASKED***")

    def test_mask_sensitive_keys_various_sensitive_names(self):
        """_mask_sensitive_keys masks all common sensitive key names"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        sensitive_keys = [
            "authorization",
            "password",
            "token",
            "access_token",
            "refresh_token",
            "api_key",
            "apikey",
            "secret",
            "client_secret",
            "credential",
            "private_key",
        ]

        payload = {key: f"value_{key}" for key in sensitive_keys}
        result = service._mask_sensitive_keys(payload)

        for key in sensitive_keys:
            self.assertEqual(
                result[key],
                "***MASKED***",
                f"Key '{key}' should be masked",
            )

    def test_mask_sensitive_keys_preserves_non_dict_values(self):
        """_mask_sensitive_keys handles lists and non-dict nested structures"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        payload = {
            "items": [
                {"password": "secret", "name": "item1"},
                {"token": "abc", "name": "item2"},
            ],
            "count": 2,
        }

        result = service._mask_sensitive_keys(payload)
        self.assertEqual(result["items"][0]["password"], "***MASKED***")
        self.assertEqual(result["items"][0]["name"], "item1")
        self.assertEqual(result["items"][1]["token"], "***MASKED***")
        self.assertEqual(result["items"][1]["name"], "item2")
        self.assertEqual(result["count"], 2)

    def test_mask_sensitive_keys_none_input(self):
        """_mask_sensitive_keys returns None for None input"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        self.assertIsNone(service._mask_sensitive_keys(None))

    def test_mask_sensitive_keys_does_not_mutate_original(self):
        """_mask_sensitive_keys returns a new dict without mutating the input"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        payload = {"password": "secret", "data": "visible"}
        result = service._mask_sensitive_keys(payload)

        self.assertEqual(payload["password"], "secret")
        self.assertEqual(result["password"], "***MASKED***")

    def test_log_call_masks_sensitive_keys_in_payloads(self):
        """log_call applies masking to request and response payloads"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        result = service.log_call(
            url="https://example.org/api/test",
            request_summary={"authorization": "Bearer xyz", "action": "search"},
            response_summary={"token": "resp-token", "status": "ok"},
        )

        self.assertTrue(result)
        self.assertEqual(result.request_summary["authorization"], "***MASKED***")
        self.assertEqual(result.request_summary["action"], "search")
        self.assertEqual(result.response_summary["token"], "***MASKED***")
        self.assertEqual(result.response_summary["status"], "ok")

    def test_sanitize_url_no_sensitive_params(self):
        """_sanitize_url leaves URLs without sensitive params unchanged"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        url = "https://example.org/api/search?q=hello&limit=10"
        result = service._sanitize_url(url)
        self.assertIn("q=hello", result)
        self.assertIn("limit=10", result)

    def test_sanitize_url_masks_sensitive_params(self):
        """_sanitize_url replaces sensitive query parameter values with MASKED"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        url = "https://example.org/api/search?api_key=secret123&q=hello"
        result = service._sanitize_url(url)
        self.assertNotIn("secret123", result)
        self.assertIn("***MASKED***", result)
        self.assertIn("q=hello", result)

    def test_sanitize_url_masks_multiple_sensitive_params(self):
        """_sanitize_url masks all sensitive params in a single URL"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        url = "https://example.org/api?token=abc&api_key=xyz&page=1"
        result = service._sanitize_url(url)
        self.assertNotIn("abc", result)
        self.assertNotIn("xyz", result)
        self.assertIn("page=1", result)

    def test_sanitize_url_case_insensitive_params(self):
        """_sanitize_url matches sensitive param names case-insensitively"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        url = "https://example.org/api?API_KEY=secret&Access_Token=tok"
        result = service._sanitize_url(url)
        self.assertNotIn("secret", result)
        self.assertNotIn("tok", result)

    def test_sanitize_url_no_query_string(self):
        """_sanitize_url returns URL unchanged when there is no query string"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        url = "https://example.org/api/search"
        result = service._sanitize_url(url)
        self.assertEqual(result, url)

    def test_sanitize_url_none_input(self):
        """_sanitize_url returns None for None input"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        self.assertIsNone(service._sanitize_url(None))

    def test_log_call_sanitizes_url(self):
        """log_call strips sensitive query parameters from URL before storing"""
        service = OutgoingApiLogService(self.env, service_name="Test", service_code="test")

        result = service.log_call(
            url="https://example.org/api/search?api_key=supersecret&q=hello",
        )

        self.assertTrue(result)
        self.assertNotIn("supersecret", result.url)
        self.assertIn("***MASKED***", result.url)
        self.assertIn("q=hello", result.url)
