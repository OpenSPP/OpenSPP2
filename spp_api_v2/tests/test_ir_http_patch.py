# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the ir.http routing_map patch — specifically the cross-worker
serialization of FastAPI endpoint sync via Postgres advisory lock.

The patch lives at: spp_api_v2/models/ir_http_patch.py
"""

import hashlib
from unittest.mock import MagicMock

from odoo.sql_db import db_connect
from odoo.tests.common import TransactionCase

from ..models.ir_http_patch import (
    _FASTAPI_SYNC_ADVISORY_LOCK_KEY,
    _try_acquire_fastapi_sync_lock,
)


class TestFastAPISyncAdvisoryLockKey(TransactionCase):
    """The advisory lock key must be deterministic and fit Postgres' bigint."""

    def test_key_is_within_postgres_bigint_range(self):
        """Postgres pg_advisory_*_lock(bigint) requires a signed 64-bit integer."""
        self.assertGreaterEqual(_FASTAPI_SYNC_ADVISORY_LOCK_KEY, -(2**63))
        self.assertLess(_FASTAPI_SYNC_ADVISORY_LOCK_KEY, 2**63)

    def test_key_is_deterministic(self):
        """Key is derived from a SHA-256 of a stable identifier — recomputing
        from the same source must yield the same value, otherwise different
        workers would lock on different keys and the serialization would not
        actually serialize anything."""
        expected = int.from_bytes(
            hashlib.sha256(b"spp_api_v2.fastapi_endpoint_sync").digest()[:8],
            byteorder="big",
            signed=True,
        )
        self.assertEqual(_FASTAPI_SYNC_ADVISORY_LOCK_KEY, expected)


class TestTryAcquireFastAPISyncLock(TransactionCase):
    """Unit tests for the lock-acquisition helper used by the routing_map patch."""

    def test_returns_true_when_postgres_grants_lock(self):
        """When pg_try_advisory_xact_lock returns true, the helper returns True."""
        cr = MagicMock()
        cr.fetchone.return_value = (True,)

        self.assertIs(_try_acquire_fastapi_sync_lock(cr), True)

        cr.execute.assert_called_once_with(
            "SELECT pg_try_advisory_xact_lock(%s)",
            (_FASTAPI_SYNC_ADVISORY_LOCK_KEY,),
        )

    def test_returns_false_when_lock_held_elsewhere(self):
        """When pg_try_advisory_xact_lock returns false, the helper returns False —
        this is the signal that another worker is doing the sync, so the caller
        must skip and not try to update the same fastapi_endpoint rows."""
        cr = MagicMock()
        cr.fetchone.return_value = (False,)

        self.assertIs(_try_acquire_fastapi_sync_lock(cr), False)

    def test_returns_false_and_warns_when_lock_sql_raises(self):
        """If the lock SQL itself fails (e.g. exhausted shared-lock memory),
        the helper must fail closed: return False (skip the sync this round)
        AND log at WARNING so a persistently broken primitive is visible
        rather than silently degrading to the every-worker-races state."""
        cr = MagicMock()
        cr.execute.side_effect = RuntimeError("simulated PG failure")

        with self.assertLogs(
            "odoo.addons.spp_api_v2.models.ir_http_patch",
            level="WARNING",
        ) as captured:
            result = _try_acquire_fastapi_sync_lock(cr)

        self.assertIs(result, False)
        self.assertTrue(
            any("advisory-lock acquire failed" in msg for msg in captured.output),
            f"Expected a WARNING about the lock acquire failure; got: {captured.output}",
        )

    def test_real_lock_is_visible_across_backends(self):
        """End-to-end check against a real Postgres backend: when one connection
        holds the xact lock, a second connection's pg_try_advisory_xact_lock
        must return false. This is the primitive the patch relies on; if the
        Postgres semantics ever change, this test catches it."""
        db = db_connect(self.env.cr.dbname)
        blocker_cr = db.cursor()
        probe_cr = db.cursor()
        try:
            # Sanity: blocker and probe must be on different PG backends,
            # otherwise advisory_xact_lock is re-entrant within the same xact
            # and the test would not be meaningful.
            blocker_cr.execute("SELECT pg_backend_pid()")
            blocker_pid = blocker_cr.fetchone()[0]
            probe_cr.execute("SELECT pg_backend_pid()")
            probe_pid = probe_cr.fetchone()[0]
            self.assertNotEqual(
                blocker_pid,
                probe_pid,
                "Test setup invariant: blocker and probe cursors must be on different Postgres backends.",
            )

            blocker_cr.execute(
                "SELECT pg_advisory_xact_lock(%s)",
                (_FASTAPI_SYNC_ADVISORY_LOCK_KEY,),
            )

            self.assertFalse(
                _try_acquire_fastapi_sync_lock(probe_cr),
                "probe must not acquire a lock already held by blocker",
            )
        finally:
            blocker_cr.rollback()
            blocker_cr.close()
            probe_cr.rollback()
            probe_cr.close()
