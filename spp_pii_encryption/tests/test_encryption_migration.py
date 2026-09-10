# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the PII encryption migration wizard."""

import base64
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import config

from .fake_model_loader import FakeModelLoader

WIZARD_LOGGER = "odoo.addons.spp_pii_encryption.wizard.encryption_migration_wizard"


class TestEncryptionMigrationWizard(TransactionCase):
    """Wizard behavior against a concrete mixin consumer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Master key + default provider, as in test_encrypted_field_mixin
        cls._original_master_key = config.get("spp_master_key")
        config["spp_master_key"] = base64.b64encode(b"M" * 32).decode()
        if not cls.env["spp.key.provider.registry"].search([("is_default", "=", True)]):
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

        # Register the fake mixin consumer
        cls.loader = FakeModelLoader(cls.env, "spp_pii_encryption")
        cls.loader.backup_registry()
        from .fake_models import EncryptionTestRecord  # noqa: PLC0415 — must import after backup_registry

        cls.loader.update_registry((EncryptionTestRecord,))
        cls.TestRecord = cls.env["spp.encryption.test.record"]

        cls.Wizard = cls.env["spp.encryption.migration.wizard"]
        cls.Classification = cls.env["spp.field.classification"]

        # Classify the fake model's secret field as PII (what the scan keys on)
        cls.secret_classification = cls.Classification.ensure_classification(
            "spp.encryption.test.record",
            "secret",
            "RESTRICTED",
            source="manual",
            pii_category="direct_id",
        )
        cls.test_model = cls.secret_classification.model_id

    @classmethod
    def tearDownClass(cls):
        cls.loader.restore_registry()
        if cls._original_master_key:
            config["spp_master_key"] = cls._original_master_key
        elif "spp_master_key" in config.options:
            del config.options["spp_master_key"]
        super().tearDownClass()

    def _make_legacy_rows(self, values):
        """Create rows holding raw plaintext with no blind index — the state
        of data written before the mixin/encryption was enabled. ORM creates
        would auto-encrypt, so the plaintext is restored with direct SQL."""
        records = self.TestRecord.create([{"name": f"r{i}", "secret": value} for i, value in enumerate(values)])
        for record, value in zip(records, values, strict=True):
            self.env.cr.execute(
                "UPDATE spp_encryption_test_record SET secret = %s, secret_index = NULL WHERE id = %s",
                (value, record.id),
            )
        records.invalidate_recordset()
        return records

    def _raw_row(self, record):
        """Raw stored (secret, secret_index) straight from SQL."""
        self.env.cr.execute(
            "SELECT secret, secret_index FROM spp_encryption_test_record WHERE id = %s",
            (record.id,),
        )
        return self.env.cr.fetchone()

    def test_batch_size_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.Wizard.create({"batch_size": 0})

    def test_scan_finds_encryptable_pii_field(self):
        """Scan reports the mixin-backed field as encryptable and a plain
        classified field as not."""
        self._make_legacy_rows(["111", "222"])
        self.Classification.ensure_classification("res.partner", "phone", "CONFIDENTIAL", pii_category="contact")

        wizard = self.Wizard.create({})
        wizard.action_scan()

        self.assertEqual(wizard.state, "ready")
        by_model = {r.model_name: r for r in wizard.scan_result_ids}
        fake_row = by_model["spp.encryption.test.record"]
        self.assertTrue(fake_row.is_encrypted)
        self.assertEqual(fake_row.field_name, "secret")
        self.assertEqual(fake_row.records_with_data, 2)
        self.assertEqual(fake_row.needs_migration, 2)
        partner_row = by_model["res.partner"]
        self.assertFalse(partner_row.is_encrypted, "res.partner has no phone_index — not encryptable")

    def test_scan_respects_model_filter(self):
        self.Classification.ensure_classification("res.partner", "phone", "CONFIDENTIAL", pii_category="contact")
        wizard = self.Wizard.create({"model_ids": [Command.set(self.test_model.ids)]})
        wizard.action_scan()
        self.assertEqual(wizard.scan_result_ids.mapped("model_id"), self.test_model)

    def test_scan_skips_unreadable_model(self):
        """A model the operator cannot read is logged and skipped, not fatal.
        The encryption admin is deliberately not a system admin."""
        self.Classification.ensure_classification(
            "ir.config_parameter", "value", "RESTRICTED", pii_category="sensitive"
        )
        operator = self.env["res.users"].create(
            {
                "name": "Encryption Operator",
                "login": "encryption_operator",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref("spp_pii_encryption.group_encryption_admin").id),
                ],
            }
        )
        wizard = self.Wizard.with_user(operator).create({})
        wizard.action_scan()

        self.assertEqual(wizard.state, "ready")
        skipped = wizard.migration_log_ids.filtered(lambda log: log.status == "skipped")
        self.assertIn("ir.config_parameter", skipped.mapped("model_name"))
        self.assertNotIn(
            "ir.config_parameter",
            wizard.scan_result_ids.mapped("model_name"),
            "unreadable models must not produce scan results",
        )
        self.assertIn("skipped", wizard.result_summary)

    def test_dry_run_counts_without_writing(self):
        records = self._make_legacy_rows(["AAA-1", "AAA-2", "AAA-3"])
        wizard = self.Wizard.create({})
        wizard.action_scan()
        wizard.action_dry_run()

        self.assertEqual(wizard.state, "done")
        self.assertIn("Would process 3", wizard.result_summary)
        for record, plain in zip(records, ["AAA-1", "AAA-2", "AAA-3"], strict=True):
            stored, index = self._raw_row(record)
            self.assertEqual(stored, plain, "dry run must not modify data")
            self.assertFalse(index)
        dry_logs = wizard.migration_log_ids.filtered(lambda log: log.status == "dry_run")
        self.assertEqual(len(dry_logs), 1)

    def test_migrate_encrypts_legacy_plaintext(self):
        legacy = self._make_legacy_rows(["PLAIN-1", "PLAIN-2"])
        # An already-encrypted row (ORM create → mixin encrypts) is untouched
        encrypted = self.TestRecord.create({"name": "enc", "secret": "ALREADY"})
        _stored_before, index_before = self._raw_row(encrypted)

        wizard = self.Wizard.create({})
        wizard.action_scan()
        scan_row = wizard.scan_result_ids.filtered(lambda r: r.model_id == self.test_model)
        self.assertEqual(scan_row.needs_migration, 2)

        wizard.action_migrate()

        self.assertEqual(wizard.state, "done")
        self.assertIn("Processed 2", wizard.result_summary)
        for record, plain in zip(legacy, ["PLAIN-1", "PLAIN-2"], strict=True):
            stored, index = self._raw_row(record)
            self.assertNotEqual(stored, plain, "stored value must be ciphertext after migration")
            self.assertTrue(index, "blind index must be computed")
            # Decryption happens in read() (attribute access returns the
            # raw stored value by design)
            self.assertEqual(record.read(["secret"])[0]["secret"], plain)
        stored_after, index_after = self._raw_row(encrypted)
        self.assertEqual(index_after, index_before, "already-encrypted rows must not be touched")

    def test_migrate_loops_all_batches(self):
        """One click processes every batch, not just the first."""
        legacy = self._make_legacy_rows(["B-1", "B-2", "B-3"])
        wizard = self.Wizard.create({"batch_size": 1})
        wizard.action_scan()
        wizard.action_migrate()

        self.assertEqual(wizard.state, "done")
        self.assertIn("Processed 3", wizard.result_summary)
        for record in legacy:
            _stored, index = self._raw_row(record)
            self.assertTrue(index)

    def test_migrate_isolates_failing_record(self):
        """A record whose write blows up is excluded and reported; the rest
        of the field still migrates and the batch loop terminates."""
        legacy = self._make_legacy_rows(["F-1", "F-2", "F-3"])
        bad = legacy[1]
        TestRecordClass = self.env.registry["spp.encryption.test.record"]
        original_write = TestRecordClass.write

        def failing_write(record_self, vals):
            if bad.id in record_self.ids:
                raise ValueError("simulated storage failure")
            return original_write(record_self, vals)

        wizard = self.Wizard.create({"batch_size": 1})
        wizard.action_scan()
        with patch.object(TestRecordClass, "write", failing_write):
            with self.assertLogs(WIZARD_LOGGER, level="ERROR") as capture:
                wizard.action_migrate()
        self.assertIn("Error migrating record", capture.output[0])

        self.assertEqual(wizard.state, "error")
        self.assertIn("Processed 2", wizard.result_summary)
        self.assertIn("1 record(s) failed", wizard.result_summary)
        _stored, bad_index = self._raw_row(bad)
        self.assertFalse(bad_index, "failed record stays unmigrated")
        for record in (legacy[0], legacy[2]):
            _stored, index = self._raw_row(record)
            self.assertTrue(index)
        error_logs = wizard.migration_log_ids.filtered(lambda log: log.status == "error")
        self.assertTrue(error_logs)

    def test_nothing_to_migrate(self):
        wizard = self.Wizard.create({})
        wizard.action_scan()
        wizard.action_migrate()
        self.assertEqual(wizard.state, "done")
        self.assertEqual(wizard.result_summary, "No fields need migration.")
