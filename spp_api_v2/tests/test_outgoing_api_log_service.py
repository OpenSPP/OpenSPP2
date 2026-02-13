# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for OutgoingApiLogService"""

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
        import json

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

        import json

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
