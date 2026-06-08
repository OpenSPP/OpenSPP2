# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Additional tests for callback_log.py to reach uncovered branches.

Covers:
- log_callback() with a non-dict payload (triggers '[NON-DICT PAYLOAD REDACTED]' path)
- get_callbacks() with since_minutes filter
- _DCICallbackLogContext (context manager __enter__/__exit__ success and failure)
- DCICallbackLogMixin.log_dci_callback() (returns the correct context manager)
- _sanitize_payload() edge: falsy payload returns None
"""

from odoo.tests import TransactionCase


class TestCallbackLogExtraBranches(TransactionCase):
    """Extra coverage tests for spp.dci.callback.log."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CallbackLog = cls.env["spp.dci.callback.log"]

    # ------------------------------------------------------------------
    # non-dict payload
    # ------------------------------------------------------------------

    def test_log_callback_non_dict_payload_redacted(self):
        """A string (non-dict) payload is stored as '[NON-DICT PAYLOAD REDACTED]'."""
        log = self.CallbackLog.log_callback(
            transaction_id="extra-nondict-txn",
            registry_type="sr",
            callback_type="on_search",
            payload="raw_string_payload",
        )
        self.assertEqual(log.payload, "[NON-DICT PAYLOAD REDACTED]")
        # Hash is still calculated for non-dict payloads
        self.assertTrue(log.payload_hash)

    def test_log_callback_none_payload_no_hash(self):
        """No payload produces None for both payload and payload_hash."""
        log = self.CallbackLog.log_callback(
            transaction_id="extra-none-payload-txn",
            registry_type="sr",
            callback_type="on_search",
            payload=None,
        )
        self.assertFalse(log.payload)
        self.assertFalse(log.payload_hash)

    # ------------------------------------------------------------------
    # get_callbacks() since_minutes branch
    # ------------------------------------------------------------------

    def test_get_callbacks_since_minutes_returns_recent(self):
        """get_callbacks(since_minutes=60) returns logs created in the last hour."""
        log = self.CallbackLog.log_callback(
            transaction_id="extra-since-txn",
            registry_type="sr",
            callback_type="on_search",
        )
        results = self.CallbackLog.get_callbacks(since_minutes=60)
        txn_ids = [r["transaction_id"] for r in results]
        self.assertIn(log.transaction_id, txn_ids)

    def test_get_callbacks_since_minutes_excludes_old(self):
        """get_callbacks(since_minutes=1) excludes logs older than 1 minute."""
        log = self.CallbackLog.log_callback(
            transaction_id="extra-old-txn",
            registry_type="sr",
            callback_type="on_search",
        )
        # Backdate the record to 2 hours ago.
        self.env.cr.execute(
            "UPDATE spp_dci_callback_log SET create_date = NOW() - INTERVAL '2 hours' WHERE id = %s",
            (log.id,),
        )
        self.CallbackLog.invalidate_model()

        results = self.CallbackLog.get_callbacks(since_minutes=1)
        txn_ids = [r["transaction_id"] for r in results]
        self.assertNotIn("extra-old-txn", txn_ids)

    # ------------------------------------------------------------------
    # _DCICallbackLogContext: success path
    # ------------------------------------------------------------------

    def test_callback_log_context_success_marks_processed(self):
        """Context manager marks the log as 'processed' when no exception is raised."""
        log_record = self.CallbackLog.log_callback(
            transaction_id="extra-ctx-ok-txn",
            registry_type="sr",
            callback_type="on_search",
        )

        from odoo.addons.spp_dci_compliance.models.callback_log import _DCICallbackLogContext

        ctx = _DCICallbackLogContext(
            self.env,
            transaction_id="extra-ctx-ok-txn-2",
            registry_type="sr",
            callback_type="on_search",
        )
        with ctx as inner_log:
            self.assertEqual(inner_log.status, "processing")

        # After the with-block exits cleanly, the log must be 'processed'.
        self.assertEqual(inner_log.status, "processed")
        self.assertEqual(inner_log.response_code, 200)
        self.assertIsNotNone(inner_log.processing_time_ms)

        # Ensure we didn't accidentally change the unrelated log.
        self.assertNotEqual(log_record.id, inner_log.id)

    def test_callback_log_context_failure_marks_failed(self):
        """Context manager marks the log as 'failed' when an exception is raised."""
        from odoo.addons.spp_dci_compliance.models.callback_log import _DCICallbackLogContext

        ctx = _DCICallbackLogContext(
            self.env,
            transaction_id="extra-ctx-fail-txn",
            registry_type="crvs",
            callback_type="on_subscribe",
        )

        caught_log = None
        try:
            with ctx as inner_log:
                caught_log = inner_log
                raise ValueError("intentional test error")
        except ValueError:
            pass  # The context manager must not suppress the exception.

        self.assertIsNotNone(caught_log)
        self.assertEqual(caught_log.status, "failed")
        self.assertEqual(caught_log.response_code, 500)
        self.assertIn("intentional test error", caught_log.error_message)

    def test_callback_log_context_does_not_suppress_exceptions(self):
        """The context manager must propagate exceptions (return False from __exit__)."""
        from odoo.addons.spp_dci_compliance.models.callback_log import _DCICallbackLogContext

        ctx = _DCICallbackLogContext(
            self.env,
            transaction_id="extra-ctx-reraise-txn",
            registry_type="dr",
            callback_type="on_search",
        )

        with self.assertRaises(RuntimeError):
            with ctx:
                raise RuntimeError("must propagate")

    # ------------------------------------------------------------------
    # DCICallbackLogMixin
    # ------------------------------------------------------------------

    def test_log_dci_callback_mixin_returns_context_manager(self):
        """log_dci_callback() on the mixin model returns a _DCICallbackLogContext."""
        from odoo.addons.spp_dci_compliance.models.callback_log import (
            _DCICallbackLogContext,
        )

        mixin = self.env["spp.dci.callback.log.mixin"]
        ctx = mixin.log_dci_callback(
            transaction_id="extra-mixin-txn",
            registry_type="ibr",
            callback_type="notify",
        )
        self.assertIsInstance(ctx, _DCICallbackLogContext)

    def test_log_dci_callback_mixin_full_round_trip(self):
        """Using the mixin as a context manager creates and completes a log record."""
        mixin = self.env["spp.dci.callback.log.mixin"]
        with mixin.log_dci_callback(
            transaction_id="extra-mixin-rt-txn",
            registry_type="fr",
            callback_type="on_txn_status",
            endpoint="/test/endpoint",
            sender_id="test.sender.id",
        ) as log:
            self.assertEqual(log.status, "processing")
            self.assertEqual(log.endpoint, "/test/endpoint")
            self.assertEqual(log.sender_id, "test.sender.id")

        self.assertEqual(log.status, "processed")
