"""Audit internals are server-side only and not RPC-dispatchable.

The audit backends and the rule's logging entry points write to the audit
trail on behalf of the server.
"""

import json
import os
import shutil
import tempfile
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError
from odoo.service.model import call_kw
from odoo.tests.common import TransactionCase, new_test_user

BACKEND_MODELS = [
    "spp.audit.backend",
    "spp.audit.backend.db",
    "spp.audit.backend.file",
    "spp.audit.backend.syslog",
    "spp.audit.backend.http",
]

SAMPLE_ENTRY = {
    "seq": 1,
    "ts": "2000-01-01T00:00:00+00:00",
    "node": "test-node",
    "rule_name": "Sample",
    "model": "res.partner",
    "res_id": 1,
    "method": "write",
    "user_id": 1,
    "user_login": "sample.user",
    "data": {"old": {"name": "Old"}, "new": {"name": "New"}},
}

PRIVATE_ERROR = "cannot be called remotely"


class RpcExposureCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.internal_user = new_test_user(cls.env, login="audit_rpc_internal", groups="base.group_user")
        cls.portal_user = new_test_user(cls.env, login="audit_rpc_portal", groups="base.group_portal")
        cls.audit_manager = new_test_user(
            cls.env,
            login="audit_rpc_manager",
            groups="base.group_user,spp_audit.group_audit_manager",
        )
        partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.partner_rule = cls.env["spp.audit.rule"].search([("model_id", "=", partner_model.id)], limit=1)
        name_field = cls.env["ir.model.fields"].search(
            [("model_id", "=", partner_model.id), ("name", "=", "name")], limit=1
        )
        rule_vals = {
            "is_log_create": True,
            "is_log_write": True,
            "field_to_log_ids": [Command.link(name_field.id)],
        }
        if cls.partner_rule:
            cls.partner_rule.write(rule_vals)
        else:
            cls.partner_rule = cls.env["spp.audit.rule"].create(
                dict(rule_vals, name="RPC exposure partner rule", model_id=partner_model.id)
            )

    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir, ignore_errors=True)

    def _reset_file_handle(self):
        """Drop the file backend's cached handle, which is kept per process."""
        file_backend = type(self.env["spp.audit.backend.file"])
        if file_backend._file_handle is not None:
            file_backend._file_handle.close()
        file_backend._file_handle = None

    def _audit_lines(self):
        lines = []
        for file_name in os.listdir(self.temp_dir):
            with open(os.path.join(self.temp_dir, file_name)) as audit_file:
                lines.extend(json.loads(line) for line in audit_file if line.strip())
        return lines

    def _assert_not_rpc_callable(self, model, method, args, user):
        with self.assertRaises(AccessError) as error:
            call_kw(model.with_user(user), method, args, {})
        self.assertIn(PRIVATE_ERROR, str(error.exception))


class TestBackendNotRpcCallable(RpcExposureCommon):
    def test_write_entry_refused_for_every_backend(self):
        """write_entry is private on every backend, for every user."""
        with patch.dict(os.environ, {"OPENSPP_AUDIT_FILE_PATH": self.temp_dir}):
            # Point the file backend at this test's directory
            self._reset_file_handle()
            self.addCleanup(self._reset_file_handle)
            for user in (self.portal_user, self.internal_user, self.audit_manager):
                for model_name in BACKEND_MODELS:
                    with self.subTest(model=model_name, user=user.login):
                        self._assert_not_rpc_callable(self.env[model_name], "write_entry", [dict(SAMPLE_ENTRY)], user)
        self.assertEqual(self._audit_lines(), [], "A refused call must not write to the audit file")

    def test_is_enabled_refused_for_every_backend(self):
        """is_enabled is private on every backend."""
        for model_name in BACKEND_MODELS:
            with self.subTest(model=model_name):
                self._assert_not_rpc_callable(self.env[model_name], "is_enabled", [], self.internal_user)


class TestRuleLoggingNotRpcCallable(RpcExposureCommon):
    def test_log_refused(self):
        """rule.log is private."""
        self._assert_not_rpc_callable(
            self.env["spp.audit.rule"],
            "log",
            [[self.partner_rule.id], "write", [{"id": 1, "name": "Old"}], [{"id": 1, "name": "New"}]],
            self.audit_manager,
        )

    def test_log_lifecycle_action_refused(self):
        """log_lifecycle_action is private."""
        self._assert_not_rpc_callable(
            self.env["spp.audit.rule"],
            "log_lifecycle_action",
            ["res.partner", 1, "approve", {"state": "draft"}, {"state": "approved"}],
            self.audit_manager,
        )

    def test_get_audit_rules_refused(self):
        """get_audit_rules is private on the rule model and on audited models."""
        for model_name in ("spp.audit.rule", "res.partner"):
            with self.subTest(model=model_name):
                self._assert_not_rpc_callable(self.env[model_name], "get_audit_rules", ["write"], self.internal_user)


class TestServerSideLoggingStillWorks(RpcExposureCommon):
    def test_audited_write_reaches_database_and_file(self):
        """A real write still produces its log line in the database and the file backend."""
        partner = self.env["res.partner"].create({"name": "RPC exposure before"})
        log_domain = [("model_id.model", "=", "res.partner"), ("res_id", "=", partner.id), ("method", "=", "write")]
        with patch.dict(
            os.environ,
            {
                "OPENSPP_AUDIT_BACKEND_DB": "true",
                "OPENSPP_AUDIT_BACKEND_FILE": "true",
                "OPENSPP_AUDIT_FILE_PATH": self.temp_dir,
            },
        ):
            # Start from a file handle pointing at this test's directory
            self._reset_file_handle()
            self.addCleanup(self._reset_file_handle)

            partner.write({"name": "RPC exposure after"})

        self.assertEqual(self.env["spp.audit.log"].search_count(log_domain), 1)
        written = [
            line for line in self._audit_lines() if line.get("res_id") == partner.id and line.get("method") == "write"
        ]
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["data"]["new"]["name"], "RPC exposure after")

    def test_lifecycle_action_still_logs_server_side(self):
        """Server code can still record a lifecycle action."""
        partner = self.env["res.partner"].create({"name": "RPC exposure lifecycle"})
        log_domain = [("model_id.model", "=", "res.partner"), ("res_id", "=", partner.id), ("method", "=", "revoke")]
        logged = self.env["spp.audit.rule"].log_lifecycle_action(
            "res.partner", partner.id, "revoke", {"state": "valid"}, {"state": "revoked"}
        )
        self.assertTrue(logged)
        self.assertEqual(self.env["spp.audit.log"].search_count(log_domain), 1)
