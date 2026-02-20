# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.api.outgoing.log model"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestApiOutgoingLog(TransactionCase):
    """Test spp.api.outgoing.log model functionality"""

    def setUp(self):
        super().setUp()
        self.outgoing_log_model = self.env["spp.api.outgoing.log"]

    def test_log_call_creates_record(self):
        """log_call creates outgoing log record with all fields"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://crvs.example.org/api/registry/sync/search",
            http_method="POST",
            endpoint="/registry/sync/search",
            request_summary={"header": {"action": "search"}, "message": {}},
            response_summary={"header": {"status": "success"}},
            response_status_code=200,
            user_id=self.env.uid,
            origin_model="spp.dci.data.source",
            origin_record_id=42,
            duration_ms=350,
            service_name="DCI Client",
            service_code="crvs_main",
            status="success",
        )

        self.assertTrue(log, "Log record should be created")
        self.assertEqual(log.url, "https://crvs.example.org/api/registry/sync/search")
        self.assertEqual(log.http_method, "POST")
        self.assertEqual(log.endpoint, "/registry/sync/search")
        self.assertEqual(log.request_summary, {"header": {"action": "search"}, "message": {}})
        self.assertEqual(log.response_summary, {"header": {"status": "success"}})
        self.assertEqual(log.response_status_code, 200)
        self.assertEqual(log.user_id.id, self.env.uid)
        self.assertEqual(log.origin_model, "spp.dci.data.source")
        self.assertEqual(log.origin_record_id, 42)
        self.assertEqual(log.duration_ms, 350)
        self.assertEqual(log.service_name, "DCI Client")
        self.assertEqual(log.service_code, "crvs_main")
        self.assertEqual(log.status, "success")
        self.assertIsNotNone(log.timestamp)

    def test_log_call_required_fields_only(self):
        """log_call works with only required fields (url)"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
        )

        self.assertTrue(log)
        self.assertEqual(log.url, "https://example.org/api/test")
        self.assertEqual(log.http_method, "POST")
        self.assertEqual(log.status, "success")
        self.assertIsNotNone(log.timestamp)
        # Optional fields should be falsy
        self.assertFalse(log.endpoint)
        self.assertFalse(log.request_summary)
        self.assertFalse(log.response_summary)
        self.assertFalse(log.response_status_code)
        self.assertFalse(log.origin_model)
        self.assertFalse(log.duration_ms)
        self.assertFalse(log.service_name)
        self.assertFalse(log.service_code)
        self.assertFalse(log.error_detail)

    def test_log_call_all_status_options(self):
        """log_call accepts all status options"""
        statuses = ["success", "http_error", "connection_error", "timeout", "error"]

        for status in statuses:
            log = self.outgoing_log_model.sudo().log_call(
                url="https://example.org/api/test",
                status=status,
            )
            self.assertEqual(log.status, status)

    def test_log_call_all_http_methods(self):
        """log_call accepts all HTTP method options"""
        methods = ["POST", "GET", "PUT", "PATCH", "DELETE"]

        for method in methods:
            log = self.outgoing_log_model.sudo().log_call(
                url="https://example.org/api/test",
                http_method=method,
            )
            self.assertEqual(log.http_method, method)

    def test_display_name_computed(self):
        """display_name is computed from http_method, endpoint, and timestamp"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
            http_method="POST",
            endpoint="/registry/sync/search",
        )

        self.assertTrue(log.display_name)
        self.assertIn("POST", log.display_name)
        self.assertIn("/registry/sync/search", log.display_name)

    def test_display_name_falls_back_to_url(self):
        """display_name uses url when endpoint is not set"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
            http_method="GET",
        )

        self.assertTrue(log.display_name)
        self.assertIn("GET", log.display_name)
        self.assertIn("https://example.org/api/test", log.display_name)

    def test_ordering_timestamp_desc(self):
        """Records are ordered by timestamp desc (most recent first)"""
        log1 = self.outgoing_log_model.sudo().log_call(url="https://example.org/1")
        log2 = self.outgoing_log_model.sudo().log_call(url="https://example.org/2")
        log3 = self.outgoing_log_model.sudo().log_call(url="https://example.org/3")

        # Search with default ordering (id desc since timestamp identical in transaction)
        logs = self.outgoing_log_model.search(
            [("id", "in", [log1.id, log2.id, log3.id])],
            order="id desc",
        )

        self.assertEqual(logs[0].id, log3.id)
        self.assertEqual(logs[1].id, log2.id)
        self.assertEqual(logs[2].id, log1.id)

    def test_json_fields_store_dicts(self):
        """Json fields store and return dict objects"""
        request_data = {"header": {"action": "search"}, "message": {"query": "test"}}
        response_data = {"header": {"status": "success"}, "results": [1, 2, 3]}

        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
            request_summary=request_data,
            response_summary=response_data,
        )

        self.assertEqual(log.request_summary, request_data)
        self.assertEqual(log.response_summary, response_data)
        self.assertIsInstance(log.request_summary, dict)
        self.assertIsInstance(log.response_summary, dict)

    def test_optional_fields_can_be_none(self):
        """Optional fields can be omitted without error"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
        )

        self.assertTrue(log)
        self.assertFalse(log.endpoint)
        self.assertFalse(log.request_summary)
        self.assertFalse(log.response_summary)
        self.assertFalse(log.response_status_code)
        self.assertFalse(log.origin_model)
        self.assertFalse(log.origin_record_id)
        self.assertFalse(log.duration_ms)
        self.assertFalse(log.service_name)
        self.assertFalse(log.service_code)
        self.assertFalse(log.error_detail)

    def test_log_call_with_error_detail(self):
        """log_call stores error detail text"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
            status="http_error",
            response_status_code=500,
            error_detail="Internal Server Error: Database connection failed",
        )

        self.assertEqual(log.status, "http_error")
        self.assertEqual(log.response_status_code, 500)
        self.assertEqual(log.error_detail, "Internal Server Error: Database connection failed")

    def test_default_user_id(self):
        """user_id defaults to current user when not specified"""
        log = self.outgoing_log_model.sudo().create(
            {
                "url": "https://example.org/api/test",
            }
        )

        self.assertTrue(log.user_id)

    def test_zero_integer_values(self):
        """Zero is a valid value for integer fields (status_code=0, duration_ms=0)"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
            response_status_code=0,
            duration_ms=0,
            origin_record_id=0,
        )

        self.assertEqual(log.response_status_code, 0)
        self.assertEqual(log.duration_ms, 0)
        self.assertEqual(log.origin_record_id, 0)

    def test_empty_string_fields(self):
        """Empty strings for optional Char fields are stored as falsy"""
        log = self.outgoing_log_model.sudo().log_call(
            url="https://example.org/api/test",
            endpoint="",
            service_name="",
            service_code="",
            origin_model="",
        )

        # Empty strings are falsy in Odoo Char fields
        self.assertFalse(log.endpoint)
        self.assertFalse(log.service_name)
        self.assertFalse(log.service_code)
        self.assertFalse(log.origin_model)


class TestOutgoingLogAuditorSecurity(TransactionCase):
    """Test field-level security for auditor group on spp.api.outgoing.log"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.auditor_group = cls.env.ref("spp_api_v2.group_api_v2_auditor")
        cls.viewer_group = cls.env.ref("spp_api_v2.group_api_v2_viewer")

        # Create user with auditor group
        cls.auditor_user = cls.env["res.users"].create(
            {
                "name": "Test Auditor",
                "login": "test_auditor_outgoing",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.auditor_group.id),
                ],
            }
        )

        # Create user with viewer group only (no auditor)
        cls.viewer_user = cls.env["res.users"].create(
            {
                "name": "Test Viewer",
                "login": "test_viewer_outgoing",
                "group_ids": [
                    Command.link(cls.env.ref("base.group_user").id),
                    Command.link(cls.viewer_group.id),
                ],
            }
        )

        # Create a log record with sensitive data
        cls.log_record = (
            cls.env["spp.api.outgoing.log"]
            .sudo()
            .log_call(
                url="https://crvs.example.org/api/registry/sync/search",
                http_method="POST",
                endpoint="/registry/sync/search",
                request_summary={"header": {"action": "search"}, "message": {"national_id": "123456"}},
                response_summary={"header": {"status": "success"}, "records": [{"name": "John"}]},
                status="http_error",
                error_detail="Connection refused: internal proxy at 10.0.0.5:8443",
            )
        )

    def test_auditor_can_read_sensitive_fields(self):
        """User with auditor group can read url, request_summary, response_summary, error_detail"""
        log = self.log_record.with_user(self.auditor_user)
        self.assertEqual(log.url, "https://crvs.example.org/api/registry/sync/search")
        self.assertTrue(log.request_summary)
        self.assertEqual(log.request_summary["message"]["national_id"], "123456")
        self.assertTrue(log.response_summary)
        self.assertEqual(log.response_summary["records"][0]["name"], "John")
        self.assertTrue(log.error_detail)
        self.assertIn("10.0.0.5", log.error_detail)

    def test_non_auditor_cannot_read_sensitive_fields(self):
        """User without auditor group gets AccessError for sensitive fields"""
        log = self.log_record.with_user(self.viewer_user)
        with self.assertRaises(AccessError):
            _ = log.url
        with self.assertRaises(AccessError):
            _ = log.request_summary
        with self.assertRaises(AccessError):
            _ = log.response_summary
        with self.assertRaises(AccessError):
            _ = log.error_detail

    def test_non_auditor_can_read_metadata_fields(self):
        """User without auditor group can still read non-sensitive metadata"""
        log = self.log_record.with_user(self.viewer_user)
        self.assertEqual(log.endpoint, "/registry/sync/search")
        self.assertEqual(log.http_method, "POST")
        self.assertEqual(log.status, "http_error")
        self.assertTrue(log.timestamp)

    def test_sensitive_fields_hidden_in_fields_get(self):
        """fields_get for non-auditor user excludes sensitive fields"""
        fields_info = (
            self.env["spp.api.outgoing.log"]
            .with_user(self.viewer_user)
            .fields_get(["url", "request_summary", "response_summary", "error_detail"])
        )
        self.assertNotIn("url", fields_info)
        self.assertNotIn("request_summary", fields_info)
        self.assertNotIn("response_summary", fields_info)
        self.assertNotIn("error_detail", fields_info)
