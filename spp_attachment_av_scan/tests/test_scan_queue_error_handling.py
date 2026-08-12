"""Queueing a malware scan is best-effort; swallowing a DB error is not.

Incident this pins (dev payroll instance, 2026-07-31): a routine attachment write
during a module upgrade hit a transient

    ERROR: could not serialize access due to concurrent update

on ``ir_attachment``. The ``create``/``write`` hooks in this module caught it with a
bare ``except Exception``, logged it, and continued. The transaction was already
unusable, so the next statement to touch the database — an unrelated
``env.ref("stock.menu_stock_root")`` inside OpenSPP's menu-icon refresh — failed with
``InFailedSqlTransaction``, and *that* was the only error the operator ever saw.
Every module upgrade failed identically, with four different modules blamed in turn.

The swallow also defeated the recovery Odoo already provides:
``odoo.service.model.retrying`` retries a request on ``IntegrityError`` /
``OperationalError`` / ``ConcurrencyError``, and ``SerializationFailure`` reaches that
tuple through ``TransactionRollbackError -> OperationalError``. Left alone, the
conflict would have been retried transparently. Caught, it became a hard failure
attributed to the wrong subsystem.

So the contract is two-sided, and both sides are asserted here:

* a **database** error must propagate — it is recoverable, but only if it is allowed
  to reach the retry machinery;
* a **non-database** error must still be swallowed and logged — enqueueing a scan is
  genuinely best-effort and must not block the attachment write.
"""

import base64
from unittest.mock import patch

import psycopg2

from odoo.exceptions import ConcurrencyError
from odoo.service import model as service_model
from odoo.tests import TransactionCase, tagged

LOGGER = "odoo.addons.spp_attachment_av_scan.models.ir_attachment"


def _raise_serialization_failure(*args, **kwargs):
    """The exact error class from the incident."""
    raise psycopg2.errors.SerializationFailure("could not serialize access due to concurrent update")


def _raise_concurrency_error(*args, **kwargs):
    """The other member of ``_MUST_NOT_SWALLOW`` — Odoo's own concurrency check."""
    raise ConcurrencyError("write concurrency check failed")


def _raise_value_error(*args, **kwargs):
    """A non-database failure, e.g. a misconfigured queue channel."""
    raise ValueError("scan queue is misconfigured")


@tagged("post_install", "-at_install")
class TestScanQueueErrorHandling(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Attachment = cls.env["ir.attachment"]

    def _binary_vals(self, name="av-guard-probe.txt", payload=b"probe"):
        return {
            "name": name,
            "datas": base64.b64encode(payload),
            "mimetype": "text/plain",
        }

    def test_a_database_error_while_queueing_propagates_on_create(self):
        """``create`` must not swallow a serialization failure."""
        with patch.object(type(self.Attachment), "with_delay", _raise_serialization_failure):
            with self.assertRaises(psycopg2.errors.SerializationFailure):
                self.Attachment.create(self._binary_vals())

    def test_a_database_error_while_queueing_propagates_on_write(self):
        """``write`` is the site the incident actually went through."""
        attachment = self.Attachment.create(self._binary_vals(name="av-guard-write.txt"))
        with patch.object(type(self.Attachment), "with_delay", _raise_serialization_failure):
            with self.assertRaises(psycopg2.errors.SerializationFailure):
                attachment.write({"datas": base64.b64encode(b"changed")})

    def test_a_concurrency_error_while_queueing_propagates_on_create(self):
        """``ConcurrencyError`` is the second member of ``_MUST_NOT_SWALLOW``."""
        with patch.object(type(self.Attachment), "with_delay", _raise_concurrency_error):
            with self.assertRaises(ConcurrencyError):
                self.Attachment.create(self._binary_vals(name="av-guard-concurrency.txt"))

    def test_a_non_database_error_is_still_swallowed_on_create(self):
        """Anti-vacuity: the fix must not turn best-effort queueing into a hard gate.

        Re-raising everything would pass both tests above while making any queue
        misconfiguration block attachment creation across the platform.
        """
        with patch.object(type(self.Attachment), "with_delay", _raise_value_error):
            with self.assertLogs(LOGGER, "ERROR") as logs:
                attachment = self.Attachment.create(self._binary_vals(name="av-guard-nondb.txt"))
        self.assertTrue(attachment.exists(), "the attachment must still be created")
        self.assertIn("Failed to queue malware scan", logs.output[0])

    def test_a_non_database_error_is_still_swallowed_on_write(self):
        attachment = self.Attachment.create(self._binary_vals(name="av-guard-nondb-write.txt"))
        with patch.object(type(self.Attachment), "with_delay", _raise_value_error):
            with self.assertLogs(LOGGER, "ERROR") as logs:
                attachment.write({"datas": base64.b64encode(b"changed")})
        self.assertIn("Failed to queue malware scan", logs.output[0])

    def test_the_retry_machinery_can_see_the_error_class_we_re_raise(self):
        """Guards the *reason* re-raising works, not just that it happens.

        If a future refactor re-raised some wrapped exception instead, the request
        would no longer be retried and the incident would recur in a new disguise.
        ``odoo/service/model.py`` retries on ``(IntegrityError, OperationalError,
        ConcurrencyError)``, then only re-runs the request when the exception is in
        ``PG_CONCURRENCY_EXCEPTIONS_TO_RETRY``.
        """
        self.assertTrue(
            issubclass(
                psycopg2.errors.SerializationFailure,
                (psycopg2.IntegrityError, psycopg2.OperationalError),
            ),
            "SerializationFailure must remain catchable by service.model.retrying",
        )
        self.assertTrue(
            issubclass(
                psycopg2.errors.SerializationFailure,
                service_model.PG_CONCURRENCY_EXCEPTIONS_TO_RETRY,
            ),
            "SerializationFailure must remain in Odoo's retry-eligible set (PG_CONCURRENCY_EXCEPTIONS_TO_RETRY)",
        )
