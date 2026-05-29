# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Callback Log model."""

import hashlib
import json

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestDCICallbackLog(TransactionCase):
    """Test cases for spp.dci.callback.log model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.CallbackLog = cls.env["spp.dci.callback.log"]

    def test_log_callback_creates_record(self):
        """Test that log_callback creates a callback log record."""
        log = self.CallbackLog.log_callback(
            transaction_id="txn-001",
            registry_type="sr",
            callback_type="on_search",
        )

        self.assertTrue(log.id)
        self.assertEqual(log.transaction_id, "txn-001")
        self.assertEqual(log.registry_type, "sr")
        self.assertEqual(log.callback_type, "on_search")
        self.assertEqual(log.status, "received")

    def test_log_callback_hashes_payload(self):
        """Test that payload is hashed correctly."""
        payload = {"message": {"data": "test"}, "header": {"sender": "test"}}
        log = self.CallbackLog.log_callback(
            transaction_id="txn-002",
            registry_type="sr",
            callback_type="on_search",
            payload=payload,
        )

        # Verify hash is calculated
        self.assertTrue(log.payload_hash)

        # Verify hash is correct
        expected_hash = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        self.assertEqual(log.payload_hash, expected_hash)

    def test_log_callback_sanitizes_pii(self):
        """Test that PII fields are redacted in stored payload."""
        payload = {
            "message": {
                "given_name": "John",
                "family_name": "Doe",
                "birthdate": "1990-01-01",
                "email": "john@example.com",
                "non_pii_field": "safe_value",
            }
        }
        log = self.CallbackLog.log_callback(
            transaction_id="txn-003",
            registry_type="sr",
            callback_type="on_search",
            payload=payload,
        )

        # Parse stored payload
        stored = json.loads(log.payload)

        # PII should be redacted
        self.assertEqual(stored["message"]["given_name"], "[REDACTED]")
        self.assertEqual(stored["message"]["family_name"], "[REDACTED]")
        self.assertEqual(stored["message"]["birthdate"], "[REDACTED]")
        self.assertEqual(stored["message"]["email"], "[REDACTED]")

        # Non-PII should be preserved
        self.assertEqual(stored["message"]["non_pii_field"], "safe_value")

    def test_log_callback_validates_registry_type(self):
        """Test that invalid registry_type raises ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            self.CallbackLog.log_callback(
                transaction_id="txn-004",
                registry_type="invalid_type",
                callback_type="on_search",
            )

        self.assertIn("Invalid registry_type", str(ctx.exception))

    def test_log_callback_validates_callback_type(self):
        """Test that invalid callback_type raises ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            self.CallbackLog.log_callback(
                transaction_id="txn-005",
                registry_type="sr",
                callback_type="invalid_callback",
            )

        self.assertIn("Invalid callback_type", str(ctx.exception))

    def test_mark_processing_updates_status(self):
        """Test that mark_processing updates status to processing."""
        log = self.CallbackLog.log_callback(
            transaction_id="txn-006",
            registry_type="sr",
            callback_type="on_search",
        )

        log.mark_processing()
        self.assertEqual(log.status, "processing")

    def test_mark_processed_sets_response_code(self):
        """Test that mark_processed updates status and response_code."""
        log = self.CallbackLog.log_callback(
            transaction_id="txn-007",
            registry_type="sr",
            callback_type="on_search",
        )

        log.mark_processed(response_code=200, processing_time_ms=150)

        self.assertEqual(log.status, "processed")
        self.assertEqual(log.response_code, 200)
        self.assertEqual(log.processing_time_ms, 150)

    def test_mark_failed_stores_error(self):
        """Test that mark_failed stores error message."""
        log = self.CallbackLog.log_callback(
            transaction_id="txn-008",
            registry_type="sr",
            callback_type="on_search",
        )

        log.mark_failed(error_message="Test error", response_code=500)

        self.assertEqual(log.status, "failed")
        self.assertEqual(log.error_message, "Test error")
        self.assertEqual(log.response_code, 500)

    def test_get_callbacks_filters_correctly(self):
        """Test that get_callbacks applies filters correctly."""
        # Create test records
        self.CallbackLog.log_callback(
            transaction_id="txn-filter-1",
            registry_type="sr",
            callback_type="on_search",
        )
        self.CallbackLog.log_callback(
            transaction_id="txn-filter-2",
            registry_type="dr",
            callback_type="on_subscribe",
        )

        # Filter by registry_type
        sr_callbacks = self.CallbackLog.get_callbacks(registry_type="sr")
        self.assertTrue(all(cb["registry_type"] == "sr" for cb in sr_callbacks))

        # Filter by callback_type
        search_callbacks = self.CallbackLog.get_callbacks(callback_type="on_search")
        self.assertTrue(all(cb["callback_type"] == "on_search" for cb in search_callbacks))

        # Filter by transaction_id
        specific = self.CallbackLog.get_callbacks(transaction_id="txn-filter-1")
        self.assertEqual(len(specific), 1)
        self.assertEqual(specific[0]["transaction_id"], "txn-filter-1")

    def test_get_callbacks_validates_registry_type(self):
        """Test that get_callbacks validates registry_type filter."""
        with self.assertRaises(ValueError) as ctx:
            self.CallbackLog.get_callbacks(registry_type="invalid")

        self.assertIn("Invalid registry_type", str(ctx.exception))

    def test_get_callbacks_validates_callback_type(self):
        """Test that get_callbacks validates callback_type filter."""
        with self.assertRaises(ValueError) as ctx:
            self.CallbackLog.get_callbacks(callback_type="invalid")

        self.assertIn("Invalid callback_type", str(ctx.exception))

    def test_get_callbacks_validates_status(self):
        """Test that get_callbacks validates status filter."""
        with self.assertRaises(ValueError) as ctx:
            self.CallbackLog.get_callbacks(status="invalid")

        self.assertIn("Invalid status", str(ctx.exception))

    def test_cleanup_old_logs_queues_jobs(self):
        """Test that cleanup_old_logs queues cleanup jobs."""
        # Create test records
        log1 = self.CallbackLog.log_callback(
            transaction_id="txn-cleanup-1",
            registry_type="sr",
            callback_type="on_search",
        )
        log2 = self.CallbackLog.log_callback(
            transaction_id="txn-cleanup-2",
            registry_type="sr",
            callback_type="on_search",
        )

        # Manually set create_date to 10 days ago
        self.env.cr.execute(
            """
            UPDATE spp_dci_callback_log
            SET create_date = NOW() - INTERVAL '10 days'
            WHERE id IN %s
            """,
            ((log1.id, log2.id),),
        )

        # Invalidate cache
        self.CallbackLog.invalidate_model()

        # Call cleanup_old_logs - it should queue jobs
        total = self.CallbackLog.cleanup_old_logs(days=7, batch_size=1)

        # Verify it found 2 old logs
        self.assertEqual(total, 2)

        # Verify jobs were queued (there should be 2 jobs for 2 records with batch_size=1)
        jobs = self.env["queue.job"].search([("name", "like", "Cleanup DCI logs batch%")])
        self.assertGreaterEqual(len(jobs), 1)

    def test_cleanup_batch_deletes_records(self):
        """Test that _cleanup_batch deletes old records."""
        # Create a test record
        log = self.CallbackLog.log_callback(
            transaction_id="txn-cleanup-batch",
            registry_type="sr",
            callback_type="on_search",
        )

        # Manually set create_date to 10 days ago
        self.env.cr.execute(
            """
            UPDATE spp_dci_callback_log
            SET create_date = NOW() - INTERVAL '10 days'
            WHERE id = %s
            """,
            (log.id,),
        )

        # Invalidate cache
        self.CallbackLog.invalidate_model()

        # Call _cleanup_batch directly
        from odoo import fields

        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=7)
        deleted_count = self.CallbackLog._cleanup_batch(cutoff, limit=1000, offset=0)

        # Verify record was deleted
        self.assertGreaterEqual(deleted_count, 1)
        self.assertFalse(self.CallbackLog.search([("id", "=", log.id)]))

    def test_unique_constraint_prevents_duplicates(self):
        """Test that unique constraint prevents duplicate callbacks."""
        import uuid

        # Use unique IDs to avoid conflicts with other tests
        unique_txn_id = f"txn-unique-{uuid.uuid4()}"
        unique_corr_id = f"corr-{uuid.uuid4()}"

        # Create first record
        self.CallbackLog.log_callback(
            transaction_id=unique_txn_id,
            registry_type="sr",
            callback_type="on_search",
            correlation_id=unique_corr_id,
        )

        # Attempt to create duplicate - should raise IntegrityError.
        # Must use a savepoint so the DB transaction is not aborted,
        # which would break subsequent tests in this module.
        with self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.CallbackLog.log_callback(
                    transaction_id=unique_txn_id,
                    registry_type="sr",
                    callback_type="on_search",
                    correlation_id=unique_corr_id,
                )

    def test_all_registry_types_valid(self):
        """Test that all documented registry types are accepted."""
        valid_types = ["sr", "crvs", "dr", "ibr", "fr"]

        for reg_type in valid_types:
            log = self.CallbackLog.log_callback(
                transaction_id=f"txn-{reg_type}",
                registry_type=reg_type,
                callback_type="on_search",
            )
            self.assertEqual(log.registry_type, reg_type)

    def test_all_callback_types_valid(self):
        """Test that all documented callback types are accepted."""
        valid_types = ["on_search", "on_subscribe", "on_unsubscribe", "on_txn_status", "notify"]

        for cb_type in valid_types:
            log = self.CallbackLog.log_callback(
                transaction_id=f"txn-cb-{cb_type}",
                registry_type="sr",
                callback_type=cb_type,
            )
            self.assertEqual(log.callback_type, cb_type)
