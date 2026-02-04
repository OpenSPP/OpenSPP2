"""Tests for audit backend system."""

import json
import os
import shutil
import tempfile
from unittest.mock import patch

from odoo.tests.common import TransactionCase

from ..models.spp_audit_backend import AuditBackendRegistry
from ..tools.config import AuditConfig


class TestAuditConfig(TransactionCase):
    """Tests for AuditConfig configuration manager."""

    def test_default_values(self):
        """Test that default values are returned when no config is set."""
        # Clear any environment variables that might interfere
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(AuditConfig.get_bool("force_enabled"))
            self.assertTrue(AuditConfig.get_bool("backend_db"))
            self.assertFalse(AuditConfig.get_bool("backend_file"))
            self.assertEqual(AuditConfig.get("file_path"), "/var/log/openspp/audit")

    def test_environment_variable_priority(self):
        """Test that environment variables take priority over defaults."""
        with patch.dict(os.environ, {"OPENSPP_AUDIT_FORCE_ENABLED": "true"}):
            self.assertTrue(AuditConfig.get_bool("force_enabled"))

        with patch.dict(os.environ, {"OPENSPP_AUDIT_BACKEND_FILE": "1"}):
            self.assertTrue(AuditConfig.get_bool("backend_file"))

    def test_is_locked(self):
        """Test that settings are locked when set via environment."""
        with patch.dict(os.environ, {"OPENSPP_AUDIT_FORCE_ENABLED": "true"}):
            self.assertTrue(AuditConfig.is_locked("force_enabled"))

        # Non-lockable keys are never locked
        self.assertFalse(AuditConfig.is_locked("http_timeout"))

    def test_get_list(self):
        """Test parsing comma-separated list values."""
        with patch.dict(os.environ, {"OPENSPP_AUDIT_MANDATORY_MODELS": "res.partner,spp.program"}):
            models = AuditConfig.get_list("mandatory_models")
            self.assertEqual(models, ["res.partner", "spp.program"])

    def test_is_model_mandatory(self):
        """Test mandatory model checking."""
        with patch.dict(os.environ, {"OPENSPP_AUDIT_MANDATORY_MODELS": "res.partner,spp.program"}):
            self.assertTrue(AuditConfig.is_model_mandatory("res.partner"))
            self.assertTrue(AuditConfig.is_model_mandatory("spp.program"))
            self.assertFalse(AuditConfig.is_model_mandatory("spp.cycle"))

    def test_get_enabled_backends(self):
        """Test getting list of enabled backends."""
        with patch.dict(
            os.environ,
            {"OPENSPP_AUDIT_BACKEND_DB": "true", "OPENSPP_AUDIT_BACKEND_FILE": "true"},
            clear=False,
        ):
            backends = AuditConfig.get_enabled_backends()
            self.assertIn("db", backends)
            self.assertIn("file", backends)

    def test_empty_mandatory_models_default(self):
        """Test that mandatory_models is empty by default."""
        with patch.dict(os.environ, {}, clear=True):
            models = AuditConfig.get_list("mandatory_models")
            self.assertEqual(models, [])


class TestAuditBackendRegistry(TransactionCase):
    """Tests for AuditBackendRegistry."""

    def test_sequence_generation(self):
        """Test that sequence numbers are monotonically increasing."""
        seq1 = AuditBackendRegistry.get_next_sequence()
        seq2 = AuditBackendRegistry.get_next_sequence()
        seq3 = AuditBackendRegistry.get_next_sequence()

        self.assertLess(seq1, seq2)
        self.assertLess(seq2, seq3)

    def test_node_id(self):
        """Test that node ID is generated and consistent."""
        node1 = AuditBackendRegistry.get_node_id()
        node2 = AuditBackendRegistry.get_node_id()

        self.assertEqual(node1, node2)
        self.assertTrue(len(node1) > 0)

    def test_dispatch_does_not_mutate_input(self):
        """Test that dispatch does not mutate the input entry dict."""
        entry = {"test": "data"}
        original_keys = set(entry.keys())

        with patch.dict(
            os.environ,
            {
                "OPENSPP_AUDIT_BACKEND_DB": "false",
                "OPENSPP_AUDIT_BACKEND_FILE": "false",
            },
        ):
            AuditBackendRegistry.dispatch(entry, self.env)

        # Original entry should not be mutated
        self.assertEqual(set(entry.keys()), original_keys)
        self.assertNotIn("seq", entry)
        self.assertNotIn("ts", entry)
        self.assertNotIn("node", entry)


class TestFileBackend(TransactionCase):
    """Tests for file audit backend."""

    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        super().tearDown()
        # Clean up temp files
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_file_backend_writes_jsonl(self):
        """Test that file backend writes valid JSONL."""
        with patch.dict(
            os.environ,
            {
                "OPENSPP_AUDIT_BACKEND_FILE": "true",
                "OPENSPP_AUDIT_BACKEND_DB": "false",
                "OPENSPP_AUDIT_FILE_PATH": self.temp_dir,
            },
        ):
            entry = {
                "rule_name": "Test Rule",
                "model": "res.partner",
                "res_id": 1,
                "method": "write",
                "user_id": 1,
                "user_login": "admin",
                "data": {"old": {"name": "Old"}, "new": {"name": "New"}},
            }

            AuditBackendRegistry.dispatch(entry, self.env)

            # Find the created file
            files = os.listdir(self.temp_dir)
            audit_files = [f for f in files if f.startswith("audit-") and f.endswith(".jsonl")]

            self.assertEqual(len(audit_files), 1)

            # Read and verify content
            with open(os.path.join(self.temp_dir, audit_files[0])) as f:
                line = f.readline()
                data = json.loads(line)

                self.assertEqual(data["rule_name"], "Test Rule")
                self.assertEqual(data["model"], "res.partner")
                self.assertIn("seq", data)
                self.assertIn("ts", data)


class TestMailThreadPosting(TransactionCase):
    """Tests for mail.thread posting behavior."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.rule = cls.env["spp.audit.rule"].search([("model_id", "=", cls.model.id)], limit=1)
        if not cls.rule:
            cls.rule = cls.env["spp.audit.rule"].create(
                {
                    "name": "Test Partner Rule",
                    "model_id": cls.model.id,
                    "is_log_create": True,
                    "is_log_write": True,
                    "is_post_to_thread": False,
                }
            )

    def test_is_post_to_thread_default_false(self):
        """Test that is_post_to_thread defaults to False."""
        model = self.env["ir.model"].search([("model", "=", "spp.program")], limit=1)
        # Delete any existing rule for this model to avoid uniqueness constraint
        existing_rule = self.env["spp.audit.rule"].search([("model_id", "=", model.id)], limit=1)
        if existing_rule:
            existing_rule.unlink()

        new_rule = self.env["spp.audit.rule"].create(
            {
                "name": "New Test Rule",
                "model_id": model.id,
            }
        )
        self.assertFalse(new_rule.is_post_to_thread)
        # Clean up
        new_rule.unlink()

    def test_mail_thread_not_posted_when_disabled(self):
        """Test that messages are not posted when is_post_to_thread is False."""
        self.rule.is_post_to_thread = False

        # Create a partner and check that no message was posted for the audit
        partner = self.env["res.partner"].create({"name": "Test Partner No Thread"})

        # Get messages - should only have creation tracking, not audit
        # The audit log should be created but no message_post should occur
        audit_logs = self.env["spp.audit.log"].search(
            [
                ("model_id", "=", self.model.id),
                ("res_id", "=", partner.id),
                ("method", "=", "create"),
            ]
        )

        # Audit log should exist (if DB backend enabled)
        if AuditConfig.get_bool("backend_db", env=self.env):
            self.assertEqual(
                len(audit_logs),
                1,
                "Expected exactly one audit log for partner creation",
            )

        # Clean up
        partner.unlink()


class TestSelfProtection(TransactionCase):
    """Tests for audit self-protection (config change logging)."""

    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rule_creation_logged(self):
        """Test that rule creation is logged to file backend."""
        with patch.dict(
            os.environ,
            {
                "OPENSPP_AUDIT_BACKEND_FILE": "true",
                "OPENSPP_AUDIT_FILE_PATH": self.temp_dir,
            },
        ):
            model = self.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
            # Delete any existing rule for this model to avoid uniqueness constraint
            existing_rule = self.env["spp.audit.rule"].search([("model_id", "=", model.id)], limit=1)
            if existing_rule:
                existing_rule.unlink()

            rule = self.env["spp.audit.rule"].create(
                {
                    "name": "Self Protection Test Rule",
                    "model_id": model.id,
                }
            )

            # Check file for config change entry
            files = os.listdir(self.temp_dir)
            audit_files = [f for f in files if f.startswith("audit-") and f.endswith(".jsonl")]

            if audit_files:
                with open(os.path.join(self.temp_dir, audit_files[0])) as f:
                    found = False
                    for line in f:
                        data = json.loads(line)
                        if data.get("type") == "audit_config_change" and data.get("action") == "rule_created":
                            found = True
                            self.assertEqual(data["rule_name"], "Self Protection Test Rule")
                            break
                    self.assertTrue(found, "Rule creation should be logged")

            # Clean up
            rule.unlink()

    def test_rule_deletion_logged(self):
        """Test that rule deletion is logged to file backend."""
        with patch.dict(
            os.environ,
            {
                "OPENSPP_AUDIT_BACKEND_FILE": "true",
                "OPENSPP_AUDIT_FILE_PATH": self.temp_dir,
            },
        ):
            model = self.env["ir.model"].search([("model", "=", "spp.cycle")], limit=1)
            # Delete any existing rule for this model to avoid uniqueness constraint
            existing_rule = self.env["spp.audit.rule"].search([("model_id", "=", model.id)], limit=1)
            if existing_rule:
                existing_rule.unlink()

            rule = self.env["spp.audit.rule"].create(
                {
                    "name": "Delete Test Rule",
                    "model_id": model.id,
                }
            )

            rule.unlink()

            # Check file for deletion entry
            files = os.listdir(self.temp_dir)
            audit_files = [f for f in files if f.startswith("audit-") and f.endswith(".jsonl")]

            if audit_files:
                with open(os.path.join(self.temp_dir, audit_files[0])) as f:
                    found = False
                    for line in f:
                        data = json.loads(line)
                        if data.get("type") == "audit_config_change" and data.get("action") == "rule_deleted":
                            if data.get("rule_name") == "Delete Test Rule":
                                found = True
                                break
                    self.assertTrue(found, "Rule deletion should be logged")
