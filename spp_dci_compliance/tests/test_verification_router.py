# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI compliance verification router.

Covers routers/verification.py by calling each endpoint function directly
with the test Odoo environment, following the same pattern used in
spp_dci_server/tests/test_callback_routers.py.

FastAPI endpoint functions are called directly here, bypassing the FastAPI
dependency injection layer. All Query() parameters must therefore be supplied
explicitly; their default Query() descriptor objects are NOT valid values for
the underlying business logic.

Design note on Odoo False vs None:
  Odoo ORM returns False (not None) for unset Char fields. get_callbacks()
  coerces those to None so the dicts validate against Pydantic's str|None
  fields (see test_minimal_log_round_trips_through_endpoint).
"""

import asyncio

from odoo.tests import TransactionCase, tagged

from fastapi import HTTPException


def _run(coro):
    """Run a coroutine synchronously in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_full_log(callback_log_model, transaction_id, registry_type="sr", callback_type="on_search"):
    """Create a callback log with all optional Char fields set to non-False values.

    Odoo returns False (not None) for unset Char fields. Passing False to
    Pydantic's str|None raises ValidationError. This helper ensures all Char
    fields have a string value, making the records safe to pass through the
    router's CallbackRecord(**cb) construction.
    """
    log = callback_log_model.log_callback(
        transaction_id=transaction_id,
        registry_type=registry_type,
        callback_type=callback_type,
        correlation_id=f"corr-{transaction_id}",
        endpoint="/test/on-search",
        sender_id="test.sender.org",
        payload={"test": "payload"},  # sets payload_hash
    )
    # error_message is only set by mark_failed(); write a placeholder so the
    # Char field has a string value rather than Odoo's False sentinel.
    log.write({"error_message": "none"})
    return log


@tagged("post_install", "-at_install")
class TestGetCallbacksEndpoint(TransactionCase):
    """Tests for the GET /test/callbacks endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CallbackLog = cls.env["spp.dci.callback.log"]

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_compliance.routers.verification import get_callbacks

        self.get_callbacks = get_callbacks

    def _call(self, **kwargs):
        """Call get_callbacks with all optional params defaulted to None/100.

        FastAPI Query() objects are not valid argument values when calling
        endpoint functions directly, so we pass plain Python defaults.
        """
        defaults = {
            "transaction_id": None,
            "correlation_id": None,
            "registry_type": None,
            "callback_type": None,
            "status_filter": None,
            "since_minutes": None,
            "limit": 100,
        }
        defaults.update(kwargs)
        return _run(self.get_callbacks(env=self.env, **defaults))

    def test_returns_empty_when_no_logs(self):
        """Endpoint returns an empty list when no callback logs exist."""
        result = self._call(transaction_id="vr-definitely-not-there-xyz123")
        self.assertEqual(result.total, 0)
        self.assertEqual(result.callbacks, [])

    def test_returns_existing_logs(self):
        """Endpoint returns logs that exist in the database."""
        _make_full_log(self.CallbackLog, "vr-txn-001")
        result = self._call(transaction_id="vr-txn-001")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.callbacks[0].transaction_id, "vr-txn-001")

    def test_filter_by_transaction_id(self):
        """Filtering by transaction_id returns only matching records."""
        _make_full_log(self.CallbackLog, "vr-filter-txn")
        result = self._call(transaction_id="vr-filter-txn")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.callbacks[0].transaction_id, "vr-filter-txn")

    def test_filter_by_registry_type(self):
        """Filtering by registry_type returns only matching records."""
        _make_full_log(self.CallbackLog, "vr-reg-txn", registry_type="crvs")
        result = self._call(registry_type="crvs")
        for cb in result.callbacks:
            self.assertEqual(cb.registry_type, "crvs")

    def test_filter_by_callback_type(self):
        """Filtering by callback_type returns only matching records."""
        _make_full_log(self.CallbackLog, "vr-cbtype-txn", registry_type="dr", callback_type="on_subscribe")
        result = self._call(callback_type="on_subscribe")
        for cb in result.callbacks:
            self.assertEqual(cb.callback_type, "on_subscribe")

    def test_filter_by_status(self):
        """Filtering by status returns only records with that status."""
        log = _make_full_log(self.CallbackLog, "vr-status-txn")
        log.mark_failed(error_message="test error")

        result = self._call(status_filter="failed")
        for cb in result.callbacks:
            self.assertEqual(cb.status, "failed")

    def test_filter_by_since_minutes(self):
        """since_minutes filter only returns recent callbacks."""
        _make_full_log(self.CallbackLog, "vr-since-txn")
        result = self._call(since_minutes=60, transaction_id="vr-since-txn")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.callbacks[0].transaction_id, "vr-since-txn")

    def test_filter_by_correlation_id(self):
        """Filtering by correlation_id returns only matching records."""
        _make_full_log(self.CallbackLog, "vr-corr-txn")
        result = self._call(correlation_id="corr-vr-corr-txn")
        self.assertEqual(result.total, 1)
        self.assertEqual(result.callbacks[0].transaction_id, "vr-corr-txn")

    def test_invalid_registry_type_returns_http_400(self):
        """An invalid registry_type filter must surface as HTTPException(400).

        Regression: the handler previously referenced `status.HTTP_400_BAD_REQUEST`
        where `status` was the query-param variable shadowing fastapi.status,
        raising AttributeError instead of a clean 400.
        """
        with self.assertRaises(HTTPException) as ctx:
            self._call(registry_type="bogus_type")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_invalid_callback_type_returns_http_400(self):
        """An invalid callback_type filter must surface as HTTPException(400)."""
        with self.assertRaises(HTTPException) as ctx:
            self._call(callback_type="not_a_type")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_invalid_status_value_returns_http_400(self):
        """An invalid status filter value must surface as HTTPException(400)."""
        with self.assertRaises(HTTPException) as ctx:
            self._call(status_filter="unknown_status")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_minimal_log_round_trips_through_endpoint(self):
        """A log with only the required fields must validate as CallbackRecord.

        Regression: Odoo returns False for unset Char fields; get_callbacks()
        passed those through and Pydantic rejected False for str|None fields,
        so any minimally-populated record broke the endpoint.
        """
        self.CallbackLog.log_callback(
            transaction_id="vr-minimal-txn",
            registry_type="sr",
            callback_type="on_search",
        )
        result = self._call(transaction_id="vr-minimal-txn")
        self.assertEqual(result.total, 1)
        record = result.callbacks[0]
        self.assertEqual(record.transaction_id, "vr-minimal-txn")
        self.assertIsNone(record.correlation_id)
        self.assertIsNone(record.error_message)
        self.assertIsNone(record.sender_id)

    def test_limit_caps_results(self):
        """The limit parameter caps the number of returned records."""
        for i in range(5):
            _make_full_log(self.CallbackLog, f"vr-limit-txn-{i}")
        result = self._call(limit=2)
        self.assertLessEqual(len(result.callbacks), 2)


@tagged("post_install", "-at_install")
class TestGetCallbackStatsEndpoint(TransactionCase):
    """Tests for the GET /test/callbacks/stats endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CallbackLog = cls.env["spp.dci.callback.log"]

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_compliance.routers.verification import get_callback_stats

        self.get_callback_stats = get_callback_stats

    def test_returns_stats_shape(self):
        """Stats endpoint returns total, by_status, by_registry_type, by_callback_type."""
        result = _run(self.get_callback_stats(env=self.env, since_minutes=60))
        self.assertIsInstance(result.total, int)
        self.assertIsInstance(result.by_status, dict)
        self.assertIsInstance(result.by_registry_type, dict)
        self.assertIsInstance(result.by_callback_type, dict)

    def test_stats_count_matches_logs(self):
        """Stats total reflects newly created logs within the time window."""
        _make_full_log(self.CallbackLog, "vr-stats-txn-1")
        _make_full_log(self.CallbackLog, "vr-stats-txn-2", registry_type="crvs", callback_type="on_subscribe")

        result = _run(self.get_callback_stats(env=self.env, since_minutes=60))
        self.assertGreaterEqual(result.total, 2)

    def test_stats_by_registry_type_counts(self):
        """by_registry_type correctly groups callbacks."""
        _make_full_log(self.CallbackLog, "vr-stats-sr-1")
        _make_full_log(self.CallbackLog, "vr-stats-sr-2")

        result = _run(self.get_callback_stats(env=self.env, since_minutes=60))
        self.assertIn("sr", result.by_registry_type)
        self.assertGreaterEqual(result.by_registry_type["sr"], 2)

    def test_stats_without_since_minutes(self):
        """Stats endpoint works when since_minutes is None (no time filter)."""
        result = _run(self.get_callback_stats(env=self.env, since_minutes=None))
        self.assertIsInstance(result.total, int)


@tagged("post_install", "-at_install")
class TestClearCallbacksEndpoint(TransactionCase):
    """Tests for the DELETE /test/callbacks endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CallbackLog = cls.env["spp.dci.callback.log"]

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_compliance.routers.verification import clear_callbacks

        self.clear_callbacks = clear_callbacks

    def test_clear_all_logs(self):
        """Calling clear_callbacks with no older_than_days clears all logs."""
        # Create known logs
        log1 = _make_full_log(self.CallbackLog, "vr-clear-txn-1")
        log2 = _make_full_log(self.CallbackLog, "vr-clear-txn-2")

        result = _run(self.clear_callbacks(env=self.env, older_than_days=None))

        self.assertIsInstance(result.deleted, int)
        self.assertGreaterEqual(result.deleted, 2)
        # The records must be gone
        self.assertFalse(self.CallbackLog.search([("id", "in", [log1.id, log2.id])]))

    def test_clear_returns_message(self):
        """clear_callbacks includes a human-readable message."""
        result = _run(self.clear_callbacks(env=self.env, older_than_days=None))
        self.assertIsNotNone(result.message)
        self.assertIn("Cleared", result.message)

    def test_clear_with_older_than_days_queues_cleanup(self):
        """With older_than_days set, clear_callbacks delegates to cleanup_old_logs."""
        log = _make_full_log(self.CallbackLog, "vr-clear-old-txn")
        self.env.cr.execute(
            "UPDATE spp_dci_callback_log SET create_date = NOW() - INTERVAL '30 days' WHERE id = %s",
            (log.id,),
        )
        self.CallbackLog.invalidate_model()

        result = _run(self.clear_callbacks(env=self.env, older_than_days=7))
        self.assertIsInstance(result.deleted, int)
        self.assertGreaterEqual(result.deleted, 1)


@tagged("post_install", "-at_install")
class TestWaitForCallbackEndpoint(TransactionCase):
    """Tests for the POST /test/callbacks/wait endpoint."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CallbackLog = cls.env["spp.dci.callback.log"]

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_compliance.routers.verification import wait_for_callback

        self.wait_for_callback = wait_for_callback

    def test_returns_immediately_when_callback_present(self):
        """When the requested callback is already logged, it is returned immediately.

        Note: wait_for_callback constructs CallbackRecord(**cb) from the dict
        returned by get_callbacks(). Odoo returns False for unset Char fields,
        which Pydantic 2.x rejects for str|None. We populate all Char fields
        to avoid this.
        """
        _make_full_log(self.CallbackLog, "vr-wait-present")
        result = _run(
            self.wait_for_callback(
                env=self.env,
                transaction_id="vr-wait-present",
                timeout_seconds=1,
                poll_interval_ms=100,
            )
        )
        self.assertEqual(result.total, 1)
        self.assertEqual(result.callbacks[0].transaction_id, "vr-wait-present")

    def test_returns_empty_on_timeout(self):
        """When the callback never arrives, the endpoint returns empty after timeout."""
        result = _run(
            self.wait_for_callback(
                env=self.env,
                transaction_id="vr-wait-nonexistent-xyz",
                timeout_seconds=1,
                poll_interval_ms=500,
            )
        )
        self.assertEqual(result.total, 0)
        self.assertEqual(result.callbacks, [])

    def test_multiple_callbacks_for_same_transaction(self):
        """When multiple logs exist for a transaction, all are returned."""
        _make_full_log(self.CallbackLog, "vr-wait-multi", callback_type="on_search")
        # Second log: use _make_full_log pattern to avoid False Char fields, but
        # needs a different callback_type to avoid the unique-constraint.
        log2 = self.CallbackLog.log_callback(
            transaction_id="vr-wait-multi",
            registry_type="sr",
            callback_type="on_subscribe",
            correlation_id="corr-vr-wait-multi-b",
            endpoint="/test/on-subscribe",
            sender_id="test.sender.org",
            payload={"test": "payload2"},  # sets payload_hash
        )
        log2.write({"error_message": "none"})

        result = _run(
            self.wait_for_callback(
                env=self.env,
                transaction_id="vr-wait-multi",
                timeout_seconds=1,
                poll_interval_ms=100,
            )
        )
        self.assertGreaterEqual(result.total, 2)


@tagged("post_install", "-at_install")
class TestVerificationRouterModels(TransactionCase):
    """Tests for the Pydantic response models defined in verification.py."""

    def test_callback_record_model(self):
        """CallbackRecord can be instantiated with required fields only."""
        from odoo.addons.spp_dci_compliance.routers.verification import CallbackRecord

        record = CallbackRecord(
            id=1,
            transaction_id="txn-model-test",
            registry_type="sr",
            callback_type="on_search",
            status="received",
        )
        self.assertEqual(record.transaction_id, "txn-model-test")
        self.assertIsNone(record.correlation_id)

    def test_callbacks_response_model(self):
        """CallbacksResponse can be instantiated with a list of CallbackRecord."""
        from odoo.addons.spp_dci_compliance.routers.verification import (
            CallbackRecord,
            CallbacksResponse,
        )

        cb = CallbackRecord(
            id=2,
            transaction_id="txn-resp-test",
            registry_type="dr",
            callback_type="on_subscribe",
            status="processed",
        )
        response = CallbacksResponse(callbacks=[cb], total=1)
        self.assertEqual(response.total, 1)
        self.assertEqual(len(response.callbacks), 1)

    def test_callback_stats_model(self):
        """CallbackStats can be instantiated with all grouping dicts."""
        from odoo.addons.spp_dci_compliance.routers.verification import CallbackStats

        stats = CallbackStats(
            total=10,
            by_status={"received": 5, "processed": 5},
            by_registry_type={"sr": 10},
            by_callback_type={"on_search": 10},
        )
        self.assertEqual(stats.total, 10)

    def test_clear_callbacks_response_model(self):
        """ClearCallbacksResponse can be instantiated with a count and message."""
        from odoo.addons.spp_dci_compliance.routers.verification import ClearCallbacksResponse

        resp = ClearCallbacksResponse(deleted=3, message="Cleared 3 records")
        self.assertEqual(resp.deleted, 3)
        self.assertEqual(resp.message, "Cleared 3 records")

    def test_verification_router_has_expected_routes(self):
        """The verification_router must have the /test prefix and expected paths."""
        from odoo.addons.spp_dci_compliance.routers.verification import verification_router

        self.assertEqual(verification_router.prefix, "/test")
        # When accessed via the router object, route.path includes the prefix.
        paths = [route.path for route in verification_router.routes]
        self.assertIn("/test/callbacks", paths)
        self.assertIn("/test/callbacks/stats", paths)
        self.assertIn("/test/callbacks/wait", paths)
